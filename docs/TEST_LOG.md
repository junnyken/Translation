# TEST_LOG.md — Translation

Ghi **số liệu thật** của từng lần chạy. Không ước lượng, không ghi "pass" khi chưa chạy.

---

## M1 — Project Scaffolding & Pipeline Contract

**Ngày:** 2026-08-27 · **Môi trường:** workspace `trieunt-c`, Docker 29.1.3, Python 3.12.3,
Postgres 16-alpine (container `translation-db-1`), Redis 7-alpine.

### 1. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
42 passed in 5.52s
```

| Nhóm | File | Số test | Kết quả |
|---|---|---|---|
| Unit — Pydantic schema | `tests/test_schemas_unit.py` | 12 | pass |
| Unit — state machine Page | `tests/test_state_machine_unit.py` | 6 | pass |
| Unit — interface engine | `tests/test_interfaces_unit.py` | 6 | pass |
| Guardrail — không có logic AI ở M1 | `tests/test_no_ai_logic.py` | 2 | pass |
| Integration — HTTP + Postgres thật | `tests/test_api_integration.py` | 12 | pass |
| Migration — upgrade/downgrade thật | `tests/test_migration.py` | 4 | pass |

Ghi chú: integration test chạy trên **Postgres thật** (DB `translation_test`), không dùng SQLite/mock;
ảnh upload trong test là **PNG thật do Pillow render**, không phải file rỗng.

### 2. Migration 2 chiều (chạy tay, ngoài test)

```
$ alembic upgrade head      → tạo 7 bảng + alembic_version   (OK)
$ alembic downgrade base    → 0 bảng, 0 enum type còn sót     (OK)
$ alembic upgrade head      → dựng lại sạch, không lỗi "type already exists" (OK)
```

### 3. Live verification (chạy thật qua HTTP trên container)

```
POST /api/v1/projects                      -> 201  id=416da44c… name="MTE Live Test Chapter" source_lang=ja intended_use=personal
POST /api/v1/projects/{id}/pages           -> 202  {"page_id":"2bfbe09f…","status":"queued","job_id":"388e42be…"}
     (upload ảnh JPEG THẬT 148.593 byte, 1400x2000)
GET  /api/v1/pages/{page_id}               -> 200  status=queued, order=1, clean_image_path=null
GET  /api/v1/pages/{page_id}/regions       -> 200  []            (đúng: M2 chưa chạy, không bịa region)
GET  /api/v1/jobs/{job_id}                 -> 200  type=detect, status=queued, retry_count=0, error_log=null
GET  /api/v1/jobs/<uuid không tồn tại>     -> 404
POST /api/v1/projects (thiếu intended_use) -> 422
GET  /docs                                 -> 200  (Swagger liệt kê đúng 6 endpoint /api/v1)
```

Đối chiếu dữ liệu thật sau flow trên:

| Kiểm | Kết quả |
|---|---|
| File lưu trên volume | `/data/storage/projects/<pid>/pages/<page_id>.jpg`, 148.593 byte |
| md5 ảnh gốc vs ảnh đã lưu | `4beff20947efb0152fb9d2f68e1d5d89` — **trùng khớp**, không hỏng byte |
| `page` trong Postgres | order=1, status=`queued`, `clean_image_path` = NULL |
| `job` trong Postgres | type=`detect`, status=`queued`, retry_count=0 |
| `text_region` / `ocr_result` / `translation_result` / `typeset_result` | **0 record** — đúng, chưa bước nào chạy |

Ghi chú trung thực: ảnh dùng để verify là **trang mẫu tự dựng bằng Pillow** (khung panel + bubble trắng,
chữ Latin), **không phải trang manga scan thật**. Đủ để chứng minh đường đi upload → lưu file → vào hàng đợi
của M1; **không đủ** để kết luận gì về chất lượng nhận diện — M2 cần ảnh manga thật.

### 4. Regression

**N/A — Mini-Spec đầu tiên của Phase**, chưa có invariant cũ để bảo vệ.

### 5. Giới hạn của lần đo này

- Ảnh dùng để verify là **trang mẫu tự dựng**, chưa phải trang manga scan thật.
  Đủ cho M1 (chỉ kiểm lưu file + tạo job), **không đủ** cho M2 — M2 cần ảnh manga thật để đo tỷ lệ miss.
- Chưa đo thời gian xử lý/trang (chưa có bước AI nào chạy).

---

## M2 — Text Region Detection (comic-text-detector)

**Ngày:** 2026-08-27 · **Môi trường:** worker container (Celery, CPU-only, `--concurrency=1`),
onnxruntime 1.20.1, model `comic-text-detector.onnx` 91MB
(sha256 `1a86ace7…d718f`, nguồn `mayocream/comic-text-detector-onnx`).

### 1. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
84 passed, 3 skipped in 13.67s
```
(3 skipped = test chạy ONNX thật, phải bật `MTE_RUN_MODEL_TESTS=1` vì mất ~40s/ảnh)

| Nhóm | File | Số test | Kết quả |
|---|---|---|---|
| Unit — hình học bbox (convert, clamp, overlap, NMS) | `tests/test_detect_geometry_unit.py` | 17 | pass |
| Unit — CTDDetector (Protocol, letterbox, giải mã, thiếu weight) | `tests/test_detect_ctd_unit.py` | 11 | pass |
| Integration — Celery task detect trên DB thật | `tests/test_detect_task_integration.py` | 11 | pass |
| Guardrail kiến trúc (M1 mở rộng cho M2) | `tests/test_no_ai_logic.py` | 5 | pass |
| Model thật trên fixture | `tests/test_detect_real_model.py` | 3 | skipped (opt-in) |
| Kế thừa M1 (schema, state machine, API, migration) | các file M1 | 40 | pass |

Bài test đáng chú ý của M2:
- `test_confidence_thap_van_duoc_luu_voi_low_confidence` — chặn việc lọc bỏ âm thầm region điểm thấp.
- `test_chay_lai_khong_tao_region_trung_lap` — chạy lại job không nhân đôi region.
- `test_timeout_ghi_failed_va_detection_failed` — quá giờ thì ghi `failed`/`detection_failed`, worker không treo.
- `test_upload_tra_202_ngay_khong_cho_detect_chay_xong` — cắm detector ngủ 5s, upload vẫn < 2s ⇒ không chạy đồng bộ.
- `test_import_app_khong_keo_theo_onnxruntime` — tiến trình API không nạp model.
- `test_nguong_bien_79_phan_tram` / `81_phan_tram` / `dung_80_phan_tram` — ngưỡng `overlap_suspect`.

### 2. Live verification — chạy model THẬT qua worker

Chạy qua đúng đường thật: `POST /pages` → Redis → Celery worker → ONNX CPU → DB.

| Ảnh | Kích thước | Vùng chữ đếm tay | Region detect được | bbox âm/vượt ảnh | low_confidence | overlap_suspect | Thời gian |
|---|---|---|---|---|---|---|---|
| `many_bubbles.png` | 1400×2000 | 6 | **6** | 0 | 1 | 0 | 39,6s |
| `few_bubbles.png` | 1200×1700 | 2 | **2** | 0 | 0 | 0 | 40,3s |
| `loose_sfx.png` | 1300×1800 | 4 (1 bubble + 3 SFX rời) | **4** | 0 | 0 | 0 | 40,1s |

Cả 3 page kết thúc ở `status=detected`, cả 3 job `status=done`, `error_log=null`.

Region của `many_bubbles.png` (toạ độ thật đọc từ API):

```
conf=0.88 pending         (240,164)  192x85
conf=0.85 pending         (964,1716) 183x82
conf=0.79 pending         (986,837)  108x83
conf=0.70 pending         (284,1481) 163x80
conf=0.56 pending         (959,212)  192x81
conf=0.50 low_confidence  (292,808)  106x85   <- dưới ngưỡng 0.5, VẪN được lưu, không bị bỏ
```

Region `low_confidence` này nằm đúng trên bubble "I AM / HERE" — là case khó thật (chữ nhỏ, nền xám),
không phải lỗi model.

**Idempotent — chạy lại thật:**
```
POST /pages/{id}/retry-detect                    -> 202, job mới eca4f4b5…
region TRƯỚC retry: 6 (id đầu 2b7e8c56…)
region SAU   retry: 6 (id đầu 333f6c32…)
worker log: "6 region (1 low_confidence, 0 overlap_suspect), xóa 6 region cũ, 44.6s"
page.status sau retry = detected
```
⇒ số region **không nhân đôi**, region cũ bị thay chứ không cộng dồn.

**Thời gian thật:** ~40s/ảnh trên CPU của workspace (`--concurrency=1`), nạp model lần đầu thêm ~1s.
Vì vậy `DETECT_TIMEOUT_SECONDS` trong `.env` đặt **120s** (mặc định trong code vẫn là 60s theo spec):
với 60s, một trang lớn hơn hoặc máy bận sẽ chạm timeout oan.

### 3. Giới hạn của lần đo này (đọc kỹ trước khi tin số)

- **Fixture là ảnh TỔNG HỢP do repo tự sinh** (`test_fixtures/make_fixtures.py`), không phải trang manga scan thật.
  Chúng chứng minh pipeline chạy đúng đầu-cuối và cách giải mã output của model là đúng —
  **không** chứng minh được tỷ lệ nhận diện trên manga thật.
- Tiêu chí "detect đúng ≥90% bubble có chữ thật" của M2 vì vậy **CHƯA được nghiệm thu**.
  Chặn: chưa có bộ ảnh có license rõ. Manga109-s trên Hugging Face đang `gated` (tải không token → HTTP 401);
  Roboflow cần API key. Cần bạn cấp bộ ảnh hoặc token để chạy lại chính bài đo này.
- Thời gian đo trên CPU của workspace, không phải GPU.

---

## M3 — OCR Extraction (manga-ocr / PaddleOCR)

**Ngày:** 2026-08-27 · **Môi trường:** container `worker` (image riêng, 4,45GB) —
torch 2.13.0+cpu · transformers 5.16.1 · paddlepaddle 3.3.1 · paddleocr 3.7.0 · onnxruntime 1.20.1 · numpy 2.2.1.
Image `api` giữ nguyên 1,06GB (không có thư viện AI).

### 1. Audit Before Build — kết quả kiểm chứng thật

| # | Mục | Kết quả |
|---|---|---|
| 1 | `IOCREngine.recognize(image_path, bbox) -> tuple[str, float]` chưa đổi | Đạt |
| 2 | bbox của M2 crop ra đúng vùng chữ | **Đạt — kiểm bằng mắt**: crop 6 region thật của `many_bubbles.png` từ DB, cả 6 ảnh crop chứa trọn chữ trong bubble, không lệch/không cụt |
| 3 | manga-ocr + PaddleOCR cài được trong worker | Đạt (xem §2) |
| 4 | manga-ocr có trả confidence không? | **KHÔNG** — đọc source 0.1.16: `MangaOcr.__call__` chỉ trả chuỗi. Xử lý: `confidence=NULL` + tiêu chí `needs_manual` theo text rỗng/không có ký tự có nghĩa |
| 5 | Xung đột dependency onnxruntime (M2) ↔ torch/paddle (M3)? | **Không có xung đột** — resolve 108 package thành công, cùng numpy 2.x. Nhưng phát hiện 2 bẫy thật, xem dưới |
| 6 | Gap = `IOCREngine` chưa implement | Đúng, M3 chỉ lấp đúng phần đó |

Hai bẫy phát hiện khi audit dependency (nếu không xử lý thì hỏng lúc chạy, không hỏng lúc cài):

1. `torch` trên PyPI kéo theo **toàn bộ stack CUDA** (`nvidia-*`, `cuda-toolkit-13`, `triton`) — vô dụng
   trên máy chỉ có CPU. → cài từ `--index-url https://download.pytorch.org/whl/cpu`.
2. `paddleocr` **không** kéo theo `paddlepaddle` (framework thật để chạy). Cài xong vẫn "thành công"
   rồi chết lúc nhận diện. → khai `paddlepaddle==3.3.1` tường minh trong `requirements-worker.txt`.

### 2. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
150 passed, 5 skipped in 26.14s
```
(5 skipped = test chạy model thật: 3 của M2 `MTE_RUN_MODEL_TESTS=1`, 2 của M3 `MTE_RUN_OCR_TESTS=1`)

| Nhóm | File | Số test |
|---|---|---|
| Unit — crop bbox float→pixel | `tests/test_ocr_crop_unit.py` | 10 |
| Unit — factory engine, parse output PaddleOCR, cờ runtime | `tests/test_ocr_engines_unit.py` | 28 |
| Integration — task OCR trên DB thật | `tests/test_ocr_task_integration.py` | 15 |
| Guardrail kiến trúc (M1+M2+M3) | `tests/test_no_ai_logic.py` | 10 |
| Engine OCR thật | `tests/test_ocr_real_engine.py` | 2 (skipped, opt-in) |
| Kế thừa M1+M2 | các file trước | 90 |

Bài test đáng chú ý của M3:
- `test_moi_region_deu_co_ocrresult_ke_ca_low_confidence` — region detect điểm thấp vẫn phải được OCR.
- `test_text_rong_thi_needs_manual_van_giu_record` — không xoá record khi OCR không ra chữ.
- `test_manga_ocr_ghi_confidence_null_va_status_ok` — không bịa confidence.
- `test_engine_hong_toan_tap_thi_bao_failed_khong_gia_vo_ocr_done` — **sinh ra từ sự cố thật ở §3**.
- `test_ocr_loi_thi_page_giu_nguyen_detected` — lỗi giữa chừng không đẩy page sang `ocr_done`.
- `test_ocr_lai_khong_tao_ket_qua_trung_lap` — idempotent theo `region_id`.
- `test_sap_lai_dong_theo_toa_do_tren_xuong_duoi` + `test_tat_phan_loai_huong_trang_cho_crop_bubble`
  — **sinh ra từ sự cố thật ở §3**.
- `test_import_app_khong_keo_theo_thu_vien_ocr`, `test_engine_ocr_import_tre_khong_nap_luc_import_module`.

### 3. Live verification — engine THẬT qua worker

Chạy đúng đường thật: `POST /pages` → detect (M2) → **tự nối** job OCR → PaddleOCR/manga-ocr → DB.

#### Nhánh `en` (PaddleOCR) — 2 trang, 8 vùng

| Ảnh | Vùng | Đọc ra chữ | Khớp CHÍNH XÁC từng ký tự | Thời gian OCR |
|---|---|---|---|---|
| `few_bubbles.png` | 2 | 2/2 (`ok`) | 2/2 | 13,1s |
| `many_bubbles.png` | 6 | 6/6 (`ok`) | 5/6 | 8,0s |

Đối chiếu tay từng vùng (bản gốc ⟶ OCR đọc được):

```
HELLO / THERE      -> "HELLO\nTHERE"     conf 1.000   khớp
GOODBYE            -> "GOODBYE"          conf 1.000   khớp
GOOD / MORNING     -> "GOOD\nMORNING"    conf 1.000   khớp
THE END / FOR NOW  -> "THE END\nFOR NOW" conf 0.999   khớp
LOOK / OUT!        -> "LOOK\nOUT!"       conf 1.000   khớp
LET US / GO NOW    -> "LET US\nGO NOW"   conf 0.998   khớp
WHO / ARE YOU?     -> "WHO\nARE YOU?"    conf 0.992   khớp
I AM / HERE        -> "IAM\nHERE"        conf 0.990   LỆCH: mất dấu cách
```

Chỗ lệch duy nhất là `IAM` thiếu dấu cách. **Cố ý không sửa** — constraint 5 của M3 cấm normalize
`raw_text`; việc sửa lỗi OCR là của bước dịch (M5) theo ngữ cảnh.

**Idempotent chạy thật:** gọi `retry-ocr` → log worker ghi `xóa 2 kết quả cũ` / `xóa 6 kết quả cũ`,
số record không đổi (2 và 6), `page.status` vẫn `ocr_done`.

#### Nhánh `ja` (manga-ocr)

Dùng chính ảnh mẫu tiếng Nhật mà thư viện manga-ocr đóng gói sẵn (`assets/example.jpg`, 600×341) —
không cần ảnh manga có bản quyền:

```
đọc được: 徹篇購訴珀騫隋被乭澄枉常参奉果章違値嶋人嘩饅午雉
confidence: None   (đúng thiết kế — thư viện không cung cấp)
```

Đối chiếu bằng mắt với ảnh gốc: đây là bubble chứa **kanji hiếm, cố ý vô nghĩa** (ảnh dùng để
stress-test model), viết dọc đọc **phải→trái**. Model chép lại gần như chính xác từng chữ và
đúng chiều đọc. Nhánh `ja` chạy đúng.

Thời gian: **8,8s/vùng** khi có `torchvision`, **55,8s** khi thiếu (transformers lùi về bộ tiền xử lý
PIL và cảnh báo). → `torchvision` đã được thêm vào image worker.

#### Thời gian detect đo lại (M2) trên image worker mới

61,4s và 57,5s/ảnh — **chậm hơn con số ~40s đo ở M2**. Đáng chú ý: 61,4s đã **vượt mặc định 60s
trong code**; nhờ `.env` đặt `DETECT_TIMEOUT_SECONDS=120` (điểm lệch spec #3 của M2) mà job không
chết oan. Đây là bằng chứng thực tế cho quyết định đó.


### 3b. Hai sự cố thật do live verification lộ ra (test giả lập KHÔNG bắt được)

**Sự cố 1 — PaddleOCR không chạy được dòng nào.** Lần chạy live đầu tiên: 8/8 vùng `needs_manual`,
`raw_text` rỗng, job vẫn `done`. Soi output thô trong worker thấy:

```
NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>] (at .../new_executor/instruction/onednn/onednn_instruction.cc:116)
```

paddlepaddle 3.3.1 vỡ ở nhánh oneDNN/PIR trên CPU này. `FLAGS_use_mkldnn=0` **không** cứu được;
truyền `enable_mkldnn=False` vào `PaddleOCR(...)` thì chạy. → thành `OCR_PADDLE_ENABLE_MKLDNN=false`.

**Lỗ hổng của chính code M3 mà sự cố 1 phơi ra:** task bắt exception theo từng vùng để "1 vùng hỏng
không giết cả trang" — nhưng khi engine chết ở **mọi** vùng, nó ghi 100% `needs_manual` rồi tự nhận
`ocr_done`. Nhìn từ ngoài giống "trang này không có chữ". Đã sửa: **mọi vùng đều lỗi ⇒ job `failed`**,
page giữ `detected`, không ghi record rỗng. Có test canh (`test_engine_hong_toan_tap...`).

**Sự cố 2 — thứ tự dòng bị đảo.** Sau khi sửa sự cố 1, 2/8 vùng trả `"OUT!\nLOOK"` và
`"ARE YOU?\nWHO"`. Cắt đúng vùng đó ra **nhìn bằng mắt**: LOOK nằm trên OUT!. Nhưng PaddleOCR báo
`OUT!` ở `y_min=0`, `LOOK` ở `y_min=40`.

Nguyên nhân: bộ **phân loại hướng TRANG TÀI LIỆU** (`use_doc_orientation_classify`) xoay crop 180° —
crop 1 bubble không có "hướng trang" để dựa vào nên nó đoán bừa. Tắt `use_doc_orientation_classify`
+ `use_doc_unwarping` (vẫn giữ `use_textline_orientation` cho hướng DÒNG chữ):
`['LOOK','OUT!']`, `y_min` 10 < 53, khớp ảnh. Kèm theo: OCR nhanh hơn hẳn (30,0s/48,6s → 13,1s/8,0s).

Ngoài ra vẫn giữ bước **sắp lại dòng theo toạ độ** (trên→dưới, trái→phải) như lưới an toàn —
chỉ sắp thứ tự dòng, không đụng ký tự nào trong text.

### 4. Giới hạn của lần đo này

- Vẫn là **ảnh tổng hợp** (`test_fixtures/`), không phải manga scan thật →
  **provisional, cần đo lại khi có ảnh thật**. Đúng như spec M3 §7.4 yêu cầu đánh dấu.
- Tiêu chí "≥80% region đọc ra text đúng nghĩa trên ảnh thật" **CHƯA nghiệm thu** —
  chung một nút thắt với tiêu chí ≥90% của M2 (đang chờ ảnh có license rõ).

---

## M4 — Inpainting (xoá chữ gốc bằng LaMa)

**Ngày:** 2026-08-27 · **Môi trường:** container `worker` (CPU), onnxruntime 1.20.1,
model `lama-manga-dynamic.onnx` 197MB (sha256 `de31ffa5…5315f9`, nguồn `ogkalu/lama-manga-onnx-dynamic`).

### 1. Audit Before Build — kết quả kiểm chứng thật

| # | Mục | Kết quả |
|---|---|---|
| 1 | `IInpainter.inpaint(image_path, masks) -> str` chưa đổi | Đạt |
| 2 | `Page.clean_image_path` tồn tại, nullable, không NOT NULL | Đạt (`character varying(1024)`, nullable) |
| 3 | Weight LaMa tải được + mount vào worker | Đạt — 197MB, mount sẵn qua `./models:/models:ro` (không cần build lại image) |
| 4 | **LaMa có trả ảnh cùng kích thước ảnh gốc không?** | **Có** — `image[b,3,h,w]` + `mask[b,1,h,w]` → `inpainted[b,3,h,w]`, cùng h×w. Nhưng lộ ra 1 ràng buộc cứng, xem dưới |
| 5 | Đĩa đủ chỗ cho ảnh clean | Đạt — còn 70GB; ảnh clean ~2/3 kích thước ảnh gốc (PNG) |
| 6 | Gap = `IInpainter` chưa implement | Đúng phạm vi, không lấn sang M5 |

**Ràng buộc cứng phát hiện ở Audit 4 (nếu không xử lý thì hỏng lúc chạy):**

```
1401x2001 (không chia hết 8) -> ONNXRuntimeError: Non-zero status code ... Mul node
                                 "Attempting to broadcast an axis by a dimension other than 1. 2001 by 2008"
1400x2000 (chia hết 8)       -> OK, output (1,3,1400,2000), 54,3s
```

⇒ code **luôn pad** mép phải/dưới về bội số 8 (mode `edge` để không tạo viền đen giả), chạy xong cắt lại
đúng kích thước gốc. Có unit test canh cả hai chiều.

### 2. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
192 passed, 6 skipped in 30.65s
```

| Nhóm | File | Số test |
|---|---|---|
| Unit — mask + dilate + clamp | `tests/test_inpaint_mask_unit.py` | 13 |
| Unit — LamaInpainter (pad, ghép ảnh, không ghi đè) | `tests/test_inpaint_lama_unit.py` | 12 |
| Integration — task inpaint trên DB thật | `tests/test_inpaint_task_integration.py` | 12 |
| Guardrail kiến trúc (M1→M4) | `tests/test_no_ai_logic.py` | 15 |
| LaMa thật trên fixture | `tests/test_inpaint_real_model.py` | 1 (skipped, opt-in) |
| Kế thừa M1+M2+M3 | các file trước | 139 |

Bài test đáng chú ý của M4:
- `test_khong_ghi_de_anh_goc` + `test_anh_goc_khong_bi_ghi_de` — **invariant quan trọng nhất**, so md5 trước/sau.
- `test_chi_thay_pixel_trong_mask` — model chỉ được đụng vùng mask, ngoài mask giữ nguyên từng pixel.
- `test_anh_le_duoc_pad_truoc_khi_vao_model` — sinh ra từ ràng buộc bội số 8 ở §1.
- `test_ratio_vuot_tran_bi_kep_xuong_15_phan_tram` — nới mask không bao giờ quá 15%.
- `test_ocr_lai_con_chu_thi_danh_dau_can_review` — kiểm chứng khách quan, còn chữ thì không tự nhận xong.
- `test_chay_lai_xoa_anh_clean_cu_khong_de_file_rac` — idempotent, so danh sách file trong thư mục.
- `test_page_chua_ocr_thi_tu_choi_inpaint`, `test_thieu_ket_qua_ocr_cua_mot_vung_thi_tu_choi` — không xoá chữ trên dữ liệu dở dang.
- `test_khong_lang_le_fallback_opencv_khi_lama_loi` — constraint 10.

### 3. Live verification — LaMa THẬT qua worker

Chạy đúng đường thật (`POST /pages/{id}/retry-inpaint` → Redis → worker → LaMa → DB):

| Ảnh | Vùng | Diện tích bị mask | Kết quả | OCR lại còn chữ | Thời gian |
|---|---|---|---|---|---|
| `few_bubbles.png` (1200×1700) | 2 | 1,3% | `inpainted` | **0/2 vùng** | 63,2s |
| `many_bubbles.png` (1400×2000) | 6 | 3,3% | `inpainted` | **0/6 vùng** | 44,8s |

**Invariant ảnh gốc — so md5 trước/sau:**

```
few_bubbles  gốc: 3eb2acc6aec7a2d0a504b2bf42ce591e -> 3eb2acc6aec7a2d0a504b2bf42ce591e  (y nguyên)
many_bubbles gốc: bf9df4751a3f9517a453ba9804154650 -> bf9df4751a3f9517a453ba9804154650  (y nguyên)
```

Thư mục `pages/` sau khi chạy có **đúng 4 file**: 2 ảnh gốc + 2 ảnh clean (`<id>_clean.png`) — không file rác.

**Nhìn bằng mắt** (tải qua `GET /pages/{id}/clean-image`): cả 6 bubble của `many_bubbles.png` trở thành
hình ellipse trắng sạch, viền bubble và khung panel giữ nguyên nét, nền xám không bị loang, không còn
bóng chữ. Không thấy artifact.

**Idempotent — chạy lại thật:**

```
TRƯỚC retry: 4 file trong pages/, md5 ảnh clean = 267f160b4759ef9318633359ef85b56f
POST /pages/{id}/retry-inpaint  -> 202
SAU   retry: 4 file trong pages/, md5 ảnh clean = 267f160b4759ef9318633359ef85b56f
md5 ảnh gốc: bf9df4751a3f9517a453ba9804154650  (không đổi)
log worker : "6 vùng, inpainted, còn chữ ở 0 vùng, xoá ảnh clean cũ=True, 43,5s"
```

⇒ số file **không tăng** (xoá cũ trước khi ghi mới), ảnh gốc không đổi. md5 ảnh clean trùng nhau
giữa 2 lần chạy cho thấy model chạy tất định — không phải do bỏ qua bước xử lý.

### 4. Giới hạn của lần đo này

- Vẫn là **ảnh tổng hợp** (`test_fixtures/`) → **provisional, cần đo lại khi có ảnh manga thật**,
  đúng như spec M4 §7.4 yêu cầu đánh dấu.
- Ảnh tổng hợp có nền phẳng (trắng/xám) nên inpaint dễ hơn thực tế rất nhiều. Trang manga thật có
  nét vẽ, lưới halftone, viền bubble cách điệu — **không được suy ra kết quả sẽ tương đương**.
- Tiêu chí "≥90% vùng OCR lại không còn chữ **trên ảnh thật**" vì vậy **CHƯA nghiệm thu** —
  cùng nút thắt với M2/M3.

---

## M5 — Dịch 2 đường + thứ tự đọc

**Ngày:** 2026-08-27 · **Môi trường:** workspace `trieunt-c`, Docker, Python 3.12.3,
Postgres 16-alpine (`translation-db-1`), Redis 7-alpine, worker Celery `translation-worker-1`.
API dịch gọi qua HTTPS — **không nạp model**, nên chạy được cả ở image `api` lẫn `worker`.

### 1. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
256 passed, 6 skipped in 34.28s
```

| Nhóm | File | Số test |
|---|---|---|
| Unit — 2 engine dịch, parse response, xoay key | `tests/test_translate_engines_unit.py` | 30 |
| Unit — thứ tự đọc (ltr/rtl, gom dải ngang) | `tests/test_translate_reading_order_unit.py` | 15 |
| Integration — task translate trên DB thật | `tests/test_translate_task_integration.py` | 13 |
| Guardrail kiến trúc (M1→M5) | `tests/test_no_ai_logic.py` | 21 (+6 của M5) |
| Kế thừa M1+M2+M3+M4 | các file trước | 177 |
| Model/OCR thật (opt-in) | `test_*_real_*.py` | 6 (skipped) |

Bài test đáng chú ý của M5:
- `test_khong_co_api_key_nao_bi_commit_vao_git` — quét **toàn bộ file git track** tìm chuỗi giống API key.
- `test_file_env_that_khong_duoc_track` + `test_key_khong_bi_ghi_vao_db_hay_tra_ra_api` — constraint 7:
  key chỉ sống trong `.env`, không lọt vào DB, không lọt ra response.
- `test_mac_dinh_khong_tu_tieu_token_cua_nguoi_dung` — canh `TRANSLATE_DEFAULT_ENGINE=google_fast`.
  Đổi mặc định sang `llm_context` sẽ **làm đỏ test**, không lặng lẽ tiêu tiền người dùng.
- `test_mac_dinh_tat_thinking_de_khong_dot_token` — canh `LLM_THINKING_BUDGET=0` (xem §3).
- `test_bon_task_co_bon_timeout_rieng` → nay là **bốn** timeout riêng (detect/OCR/inpaint/translate).
- `parse_response`: thiếu dòng → chuỗi rỗng + `status=pending`, **không bịa nội dung**; thừa dòng → cắt.
- `test_engine_la_bao_loi_khong_fallback_am_tham` — engine lạ raise `UnsupportedTranslationEngine`, không fallback âm thầm.

### 2. Live verification — gọi API dịch THẬT qua worker

Đường thật: `POST /pages/{id}/retry-translate` → Redis → worker Celery → HTTPS → DB.

**2a. `llm_context` (Gemini) — trang 6 bubble, en → vi:**

| # | OCR đọc được | Bản dịch | token_cost |
|---|---|---|---|
| 1 | `GOOD\nMORNING` | Chào buổi sáng. | **227** |
| 2 | `WHO\nARE YOU?` | Ngươi là ai? | NULL |
| 3 | `IAM\nHERE` | Ta ở đây. | NULL |
| 4 | `LOOK\nOUT!` | Cẩn thận! | NULL |
| 5 | `LET US\nGO NOW` | Đi thôi nào. | NULL |
| 6 | `THE END\nFOR NOW` | Tạm kết tại đây. | NULL |

- `reading_order` được điền **1..6** (cột này để NULL từ M1, M5 chịu trách nhiệm điền).
- `IAM` là **lỗi OCR** của `I AM` — LLM tự sửa theo ngữ cảnh, đúng như thiết kế (`raw_text` giữ nguyên,
  không normalize ở M3).
- `token_cost` ghi ở **đúng 1 dòng đầu trang**: `SUM(token_cost)` toàn bảng = 227 = chi phí thật của
  1 request, không bị nhân bản 6 lần.

**2b. Đối chứng 2 engine trên CÙNG một trang (2 bubble, en → vi):**

| Engine | `HELLO\nTHERE` → | `GOODBYE` → | Token | Thời gian |
|---|---|---|---|---|
| `google_fast` | **"Xin chào\nĐÓ"** ❌ | "TẠM BIỆT" | 0 (miễn phí) | <1s |
| `llm_context` | **"Chào nhé."** ✅ | "Tạm biệt." | 164 | ~5s |

Đây là **bằng chứng thật cho lý do tồn tại của 2 đường**: `google_fast` dịch rời từng dòng nên
`THERE` thành `ĐÓ` — vô nghĩa trong ngữ cảnh chào hỏi. `llm_context` gộp 2 dòng của cùng 1 bubble
thành một câu thoại tự nhiên. Không suy đoán — đo trên đúng dữ liệu đó.

Chạy lại trên cùng page **thay thế** bản dịch cũ (xoá theo `region_id` rồi ghi mới), không tích luỹ
bản trùng — cùng cách M4 xử lý ảnh clean.

### 3. Đo bẫy "thinking" đốt token

Cùng 1 trang 6 dòng, cùng prompt, chỉ đổi model/cấu hình:

| Model | thinking token | tổng token | thời gian |
|---|---|---|---|
| `gemini-3.6-flash` (không tắt thinking) | **938** | 1072 | 7,0s |
| `gemini-3-flash-preview` + `thinkingBudget=0` | 0 | 133 | 2,0s |
| **`gemini-3.1-flash-lite` + `thinkingBudget=0`** (mặc định) | **0** | **140** | **1,6s** |

⇒ Không tắt thinking thì **đắt gấp ~7,7 lần, chậm gấp 4 lần** mà chất lượng dịch trên mẫu này
tương đương. Nếu model vẫn trả `thoughtsTokenCount > 0` dù đã yêu cầu tắt, worker **ghi cảnh báo
vào log** — hoá đơn phình lên sẽ không diễn ra âm thầm.

### 4. Hai giả định của spec bị thực tế bác bỏ

| Spec giả định | Thực tế đo được |
|---|---|
| Dùng `gemini-2.5-flash` | **404 NOT_FOUND** — *"This model is no longer available to new users"*. Phải đổi sang dòng 3.x. |
| Nhiều API key ⇒ nhiều quota | Tài liệu Gemini: *"Rate limits are applied per project, not per API key."* ⇒ **xoay key trong cùng project không tăng hạn mức**. Cơ chế xoay vẫn giữ (có test) nhưng chỉ có tác dụng khi key thuộc **project khác nhau**. |

Cả hai đều ghi vào `ARCH.md §8` để người sau không kỳ vọng sai.

### 5. Giới hạn của lần đo này

- Vẫn là **ảnh tổng hợp** (`test_fixtures/`) với thoại tiếng Anh ngắn — **chưa đo trên manga thật**,
  chưa đo tiếng Nhật/Trung. Cùng nút thắt với M2/M3/M4.
- Hướng đọc `rtl` (manga Nhật) mới chỉ verify bằng **unit test**, chưa có trang JP thật chạy đầu-cuối:
  các page `ja` trong DB đang dừng ở `detected`.
- Nhánh `fallback_used` (LLM chết → lùi về Google) mới verify bằng **integration test giả lập lỗi**,
  chưa gặp tình huống hết quota thật.

---

## M6 — Canh cỡ chữ & ngắt dòng cho vừa bubble

**Ngày:** 2026-08-27 · **Môi trường:** workspace `trieunt-c`, Docker, Python 3.12.3,
Postgres 16-alpine, Redis 7-alpine, worker Celery `translation-worker-1`, Pillow 11.0.0.
Font: `fonts/` mount vào worker theo `FONT_DIR=/fonts` (API **không** mount, không cần).

### 1. Audit Before Build — 7 mục, có bằng chứng

| # | Mục | Kết quả |
|---|---|---|
| 1 | `ITypesetter.fit(text, bbox, font_family) -> dict` + bảng `TypesetResult` | Nguyên vẹn từ M1: đủ 6 cột (`font_family`, `font_size`, `wrapped_text`, `padding_ratio`, `fit_status`, `edited_by_user`), `region_id` unique, enum `FitStatus(pending/fit_ok/overflow_warning)`, `JobType.typeset` có sẵn ⇒ **không cần migration** |
| 2 | Page `translated` thật + đơn vị bbox | Page `e08da9e4` (6 vùng / 6 bản dịch / 0 typeset). bbox max `(x+w, y+h) = (1147, 1798)` nằm gọn trong ảnh clean `1400×2000` ⇒ **bbox đúng pixel của ảnh clean**, không phải thumbnail |
| 3 | Pillow trong worker | `11.0.0`; có `getlength` ✓, có `multiline_textbbox` ✓, **`textsize`/`getsize` đã bị gỡ khỏi Pillow 11** (`hasattr = False`) nên không có nguy cơ lỡ tay dùng API cũ |
| 4 | File font + hỗ trợ tiếng Việt | `fonts/` chưa được mount vào worker ⇒ **đã bổ sung volume `./fonts:/fonts:ro`**. Độ phủ dấu đã đo ở `docs/FONTS.md`: 4 font bundle đều 134/134 |
| 5 | License font trước khi commit | Cả 4 font **SIL OFL 1.1**, có `OFL.txt` đi kèm ⇒ **có quyền phân phối**, nên được commit (spec cấm commit font *trừ khi* quyền phân phối được xác nhận — điều kiện này đã thoả) |
| 6 | Đường dẫn preview + quyền ghi/đọc | Worker ghi `/data/storage/previews/_audit/probe.txt` → **API đọc lại được** đúng nội dung ⇒ chung volume `storage_data`. Đĩa còn **68 GB** |
| 7 | Gap | `typeset_result` có **0 record**, không có implementation nào của `ITypesetter` ⇒ đúng phạm vi M6 |

**Phát hiện lớn nhất của audit — `raqm` KHÔNG có trong worker.**
Workspace có `features.check("raqm") = True` nhưng **worker là `False`**. Đo hậu quả thật:

| Dạng chuỗi | `getlength()` | Render ra |
|---|---|---|
| NFC (dựng sẵn) | 325.0 | `ĐỪNG NGOẢNH LẠI! CẨN THẬN` ✅ |
| NFD (tách dấu) | **325.0 — y hệt** | `ĐUNG NGOANH LAỊ! CAN THAN` ❌ |

⇒ Chuỗi NFD render **sai** mà phép đo **vẫn trả đúng con số của NFC**, nên sai không lộ ra qua
bất kỳ assert nào về kích thước. Dữ liệu M5 hiện tại tình cờ là NFC (đã kiểm 3 mẫu), nhưng Gemini
không cam kết trả NFC. → M6 **chuẩn hoá NFC trong đường đo/vẽ** (xem REPORT_M6 §3).

### 2. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
329 passed, 6 skipped in 44.22s
```

| Nhóm | File | Số test |
|---|---|---|
| Unit — ngắt dòng, đo chữ, FontResolver, chặn tofu | `tests/test_typeset_layout_unit.py` | 21 |
| Unit — thuật toán chọn cỡ chữ | `tests/test_typeset_fitter_unit.py` | 13 |
| Integration — task typeset + 3 endpoint trên DB thật | `tests/test_typeset_task_integration.py` | 17 |
| Guardrail kiến trúc (M1→M6) | `tests/test_no_ai_logic.py` | 27 (+6 của M6) |
| Font bundle đủ dấu tiếng Việt | `tests/test_fonts_vietnamese.py` | 16 |
| Kế thừa M1–M5 | các file trước | 235 |

Bài test đáng chú ý của M6:
- `test_giam_1px_lay_duoc_co_lon_nhat_ke_ca_khi_khong_don_dieu` — **khoá lại bằng chứng §4**: ca
  `"Cẩn thận!"` phải KHÔNG đơn điệu, và `fit()` phải trả đúng cỡ lớn nhất trong tập vừa.
- `test_thieu_glyph_bao_loi_khong_am_tham_ra_o_vuong` — tự cắt một font chỉ còn ASCII rồi bắt buộc
  phải ném `font_missing_glyph`.
- `test_khong_co_chu_thi_pending_khong_phai_overflow` — vùng chưa có bản dịch không được gắn "tràn khung".
- `test_preview_that_su_co_ve_chu_len` — preview phải KHÁC ảnh clean; giống hệt nghĩa là không vẽ được gì.
- `test_khong_dung_toi_du_lieu_cua_m2_m5` — so nguyên bộ `(reading_order, bbox, translated_text, token_cost)`
  trước/sau typeset.
- `test_api_khong_nap_engine_render_cua_m6` + `test_package_typeset_khong_keo_theo_pillow` — API
  không được nạp Pillow; vì thế quy ước đường dẫn preview tách sang `typeset/paths.py`.
- `test_endpoint_preview_chi_phuc_vu_file_khong_tu_render` — quét thân hàm, cấm mọi dấu vết renderer.
- `test_nam_task_co_nam_timeout_rieng` — nay là **năm** timeout độc lập.

### 3. Live verification — Run A (bắt buộc)

Đường thật: `POST /pages/{id}/retry-typeset` → Redis → worker Celery → Pillow → DB + file preview.
Page `e08da9e4`, 6 bubble, bản dịch **thật từ Gemini** (M5), ảnh clean 1400×2000, font `Bangers`.

| # | Bản dịch | bbox | Cỡ chữ | Ngắt dòng | Trạng thái |
|---|---|---|---|---|---|
| 1 | Chào buổi sáng. | 192×85 | 30 | 2 dòng | `fit_ok` |
| 2 | Ngươi là ai? | 192×81 | **36** | 1 dòng | `fit_ok` |
| 3 | Ta ở đây. | 106×85 | 33 | 2 dòng | `fit_ok` |
| 4 | Cẩn thận! | 108×84 | **27** | 2 dòng | `fit_ok` |
| 5 | Đi thôi nào. | 163×80 | 32 | 1 dòng | `fit_ok` |
| 6 | Tạm kết tại đây. | 183×82 | 29 | 2 dòng | `fit_ok` |

**Thời gian: 0,5–0,6 s/trang** (rẻ hơn detect 40-61s, OCR, inpaint 45-63s rất nhiều — M6 không nạp model).

**Checksum — bằng chứng M6 không đụng output của M4:**

```
TRƯỚC: gốc bf9df4751a3f9517a453ba9804154650 · clean 267f160b4759ef9318633359ef85b56f
SAU  : gốc bf9df4751a3f9517a453ba9804154650 · clean 267f160b4759ef9318633359ef85b56f
```
Preview là **file thứ ba**: `previews/<page_id>/typeset.png`, đúng 1400×2000 = kích thước ảnh clean.

**Nhìn bằng mắt** (tải qua `GET /pages/{id}/typeset-preview`): cả 6 bubble có chữ tiếng Việt căn giữa
cả hai chiều, **đủ dấu** (`CHÀO BUỔI SÁNG`, `NGƯƠI LÀ AI?`, `TA Ở ĐÂY`, `CẨN THẬN!`, `ĐI THÔI NÀO`,
`TẠM KẾT TẠI ĐÂY`), không chữ nào chạm viền bubble, không có ô vuông.

**Ca tràn khung có chủ ý** (spec Run A yêu cầu) — nhét 1 câu 208 ký tự vào bubble 192×81:

| Vùng | Cỡ chữ | Số dòng | Trạng thái |
|---|---|---|---|
| câu dài 208 ký tự | **10 = đúng `TYPESET_MIN_FONT_SIZE`** | 7 | `overflow_warning` |
| "Tạm biệt." | 29 | 1 | `fit_ok` |

⇒ Hệ thống **không co chữ xuống dưới min để giả vờ vừa khung**. Preview vẽ khung đỏ quanh vùng tràn,
chữ nằm trong bbox, không tràn vô hạn ra trang. Cảnh báo đọc được ở `GET /pages/{id}/typeset`.

**Idempotent — chạy lại thật 2 lần:**

```
TRƯỚC : 6 bản ghi typeset_result, thư mục previews/<page_id>/ có đúng 1 file typeset.png
retry x2 -> log: "6 vùng (vừa 6, tràn 0, chưa có chữ 0), xoá 6 kết quả cũ"
SAU   : 6 bản ghi typeset_result, vẫn đúng 1 file typeset.png, không có file .tmp.png sót lại
```

### 4. Đo tính đơn điệu — vì sao KHÔNG dùng tìm kiếm nhị phân

Spec §6 cho phép nhị phân *nếu* quan hệ "vừa khung theo cỡ chữ" đơn điệu. **Đo thật trên 8 ca**
(6 bubble thật + 2 ca khắc nghiệt), chuỗi `fits(10..28)`:

| Ca | Chuỗi `fits(10→28)` | Đơn điệu? |
|---|---|---|
| Chào buổi sáng. (192×85) | `1111111111111111111` | có |
| **Cẩn thận! (108×84)** | `1111111111111110110` | **KHÔNG** |
| **token dài (300×200)** | `1111111111101111111` | **KHÔNG** |
| 5 ca còn lại | đơn điệu | có |

`"Cẩn thận!"` **vừa ở cỡ 25, hỏng ở 26, lại vừa ở 27** — vì tăng cỡ làm ngắt dòng nhảy từ 2 dòng
xuống 1 dòng (hoặc ngược lại) một cách rời rạc. Tìm kiếm nhị phân sẽ dừng ở **25** và bỏ sót **27**.

⇒ **2/8 ca không đơn điệu ⇒ chuyển hẳn sang giảm dần 1px**, chỉ giữ một thuật toán trong production
đúng như spec §6 yêu cầu. Có test khoá lại ca này để không ai "tối ưu" ngược về nhị phân.

### 5. Đo trần cỡ chữ — vì sao đổi mặc định 28 → 40

Chạy Run A lần đầu với `TYPESET_MAX_FONT_SIZE=28` (giá trị spec đề xuất): **5/6 vùng dừng đúng ở 28**.
Nhiều vùng cùng chạm đúng trần là dấu hiệu **trần đang chặn, không phải bubble**. Đo lại khi nới trần:

| Trần | Cỡ chọn được cho 6 vùng | Còn chạm trần? |
|---|---|---|
| 28 | 28, 28, 28, 27, 28, 28 | **có — 5/6** |
| **40** | 30, 36, 33, 27, 32, 29 | không |
| 56 | 30, 36, 33, 27, 32, 29 | không (giống hệt 40) |
| 72 | 30, 36, 33, 27, 32, 29 | không (giống hệt 40) |

Trên 40 thì hình học bubble mới là ràng buộc, nới thêm vô ích. → **mặc định đổi thành 40**, ghi rõ
lý do trong `.env.example` và `config.py`.

### 6. Giới hạn của lần đo này

- Vẫn là **ảnh tổng hợp** nền phẳng, bubble hình ellipse đều đặn — **Run C (manga scan thật) CHƯA chạy**,
  cùng nút thắt với M2/M3/M4/M5.
- **Run B (font comic mà spec chỉ định) KHÔNG chạy được**: `HL Comic2` chỉ có 38/134 ký tự tiếng Việt,
  Anime Ace "Limited European Characters" + phải mua license, MTO Comic không tồn tại (`docs/FONTS.md`).
  M6 chạy bằng **Bangers — font comic thật, SIL OFL, đủ 134/134 dấu**, không phải font hệ thống chữa cháy.
  Nhưng đây **chưa phải** typography đã được duyệt bởi người làm truyện.
- Chưa có **text dọc / chữ xoay / SFX** — M6 chỉ layout chữ Việt nằm ngang trong bbox (đúng phạm vi spec).
- Chưa đo trên bubble **không phải hình chữ nhật**: bbox là hình chữ nhật bao quanh bubble ellipse, nên
  chữ căn giữa vẫn có thể chạm mép cong ở bubble dẹt. Trên fixture chưa thấy, cần Run C xác nhận.

---

## M7 — Màn sửa tay từng vùng

**Ngày:** 2026-08-28 · **Môi trường:** workspace `trieunt-c`, Docker, Python 3.12.3, Node 22,
Postgres 16-alpine, Redis 7-alpine, worker Celery, frontend Vite/React 18 (cổng 5174),
kiểm giao diện bằng Playwright + Chromium 151.

### 1. Audit Before Build — 6 mục, có bằng chứng

| # | Mục | Kết quả |
|---|---|---|
| 1 | `edited_by_user` trên `TranslationResult` + `TypesetResult` | Có sẵn từ M1, `nullable=False, default=False`. DB thật: **16/16 record đều `false`** ⇒ chưa có gì được sửa tay |
| 2 | `TextRegion.bbox_x/y/w/h` | Có sẵn — nhưng **`nullable=False`**, không phải nullable như spec ghi. Không sao: bbox luôn bắt buộc |
| 3 | `GET /pages/{id}/typeset-preview` từ M6 | Có, trả PNG đúng kích thước ảnh clean |
| 4 | `FitToBoxTypesetter.fit()` từ M6 | Nguyên vẹn `fit(text, bbox, font_family) -> dict` ⇒ M7 gọi lại, không viết lại logic |
| 5 | Chuẩn hoá NFC của M6 | Có ở `fitter.py` + `layout.py`, **không** ghi ngược vào `TranslationResult` ⇒ M7 giữ nguyên |
| 6 | Gap | Không có endpoint `PATCH` nào, không có thư mục frontend nào ⇒ đúng phạm vi M7 |

**Về việc thêm cột:** spec §4A yêu cầu nêu rõ nếu cần cột mới. **Không cần cột nào** —
`TimestampMixin` đã có `updated_at` với `onupdate=func.now()` nên thời điểm sửa tay tự được ghi;
chưa có auth nên không có user id để lưu.

**Phát hiện của audit — ảnh xem thử bị trình duyệt nhớ bản cũ.** Endpoint preview của M6 trả
`etag` + `last-modified` nhưng **không có `Cache-Control`**, mà đường dẫn lại cố định theo page.
Sửa xong mà trình duyệt hiện ảnh cũ thì phạm đúng constraint 8 của M7. → thêm
`Cache-Control: no-cache, must-revalidate` ở server **và** tham số `?v=` ở client (hai lớp).

### 2. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
366 passed, 6 skipped in 72.99s
```

| Nhóm | File | Số test |
|---|---|---|
| Integration — PATCH vùng, canh lại, đọc lại, dịch lại, chi tiết trang | `tests/test_region_edit_integration.py` | 31 |
| Guardrail kiến trúc (M1→M7) | `tests/test_no_ai_logic.py` | 32 (+5 của M7) |
| M6 + bất biến "chữ không tràn ra ngoài khung" | `tests/test_typeset_task_integration.py` | 18 (+1) |
| Kế thừa M1–M6 | các file trước | 315 |

Bài test đáng chú ý của M7:
- `test_canh_lai_mot_vung_khong_dung_vung_khac` — chụp nguyên trạng vùng B trước/sau khi sửa vùng A.
- `test_auto_fit_khong_bao_gio_danh_dau_sua_tay` — quét mã nguồn: nhánh tự động chỉ được có
  `edited_by_user=False`, nhánh sửa tay mới được `True`.
- `test_sua_tay_khong_dung_chu_goc_ocr` — sửa bản dịch không được đụng `raw_text` của M3.
- `test_sua_vung_khong_dung_anh_goc_va_anh_clean` — so md5 trước/sau.
- `test_ghim_co_qua_lon_thi_bao_tran_khong_gia_vo_vua` — ghim cỡ to quá khung vẫn dùng cỡ đó
  nhưng phải gắn `overflow_warning`.
- `test_sua_tay_khong_render_dong_bo_trong_request` — quét thân hàm `patch_region`, cấm mọi dấu vết
  renderer/typesetter.
- `test_preview_khong_duoc_cache` + `test_preview_co_header_chong_cache` — canh lỗi ở §1.
- `test_chu_khong_bao_gio_ve_ra_ngoai_khung` — **sinh ra từ lỗi thật ở §4**: bôi trắng mọi bbox trên
  cả ảnh clean lẫn ảnh preview rồi so **từng pixel**; khác nhau nghĩa là có chữ vẽ ra ngoài khung.

### 3. Live verification — thao tác THẬT trên giao diện

Chạy Chromium thật, click/gõ/kéo chuột trên UI ở `localhost:5174`, đối chiếu DB qua API và md5 ảnh
preview trong volume. Trang `e08da9e4`, 6 bubble, bản dịch thật từ M5.

| # | Thao tác trên UI | Kết quả DB | Ảnh preview |
|---|---|---|---|
| 0 | mở trang | 6 khung vẽ đúng vị trí bubble, 6 thẻ vùng, 0 lỗi JS | `8ad51c74…` |
| 1 | gõ câu dài 118 ký tự → **Lưu & canh lại** | cỡ **30 → 13**, 4 dòng, `fit_ok`, `edited_by_user=true` | `3992003…` **đã vẽ lại** |
| 2 | sửa lại thành `"Chào cậu!"` | cỡ **13 → 40** (kịch trần), `fit_ok` | `07f2d78…` **đã vẽ lại** |
| 3 | đổi kiểu chữ `Mansalva` + ghim cỡ **16** | `font_family=Mansalva`, `font_size=16`, `fit_ok` | `f03c91d…` **đã vẽ lại** |
| 4 | **kéo khung chữ** bằng chuột 60×40 px màn hình | bbox `(240,164)` → `(324,220)` = **+84, +56 px ảnh gốc** | `d0cb404…` **đã vẽ lại** |
| 5 | bật/tắt ô “Hiện cảnh báo” | khung cảnh báo: 1 → **0** → 1 | — |
| 6 | ghim cỡ **40** cho câu dài | cỡ **40** (đúng cỡ ghim), `overflow_warning`, nhãn đỏ “Tràn khung”, bộ đếm “1 vùng tràn khung” | có khung đỏ |

**Phép thử tỷ lệ ở bước 4 là bằng chứng quan trọng:** kéo 60 px trên màn hình cho ra **84 px** trên
ảnh gốc — đúng bằng `60 ÷ (1000/1400)`. Nếu quy đổi sai thì khung sẽ lệch khỏi bubble.

Ảnh gốc và ảnh clean **không đổi md5** sau toàn bộ chuỗi thao tác trên (có test tự động canh).

### 4. Hai lỗi thật do live verification làm lộ ra

**Lỗi A — khung chữ vẽ lệch hẳn khỏi bubble (lỗi của M7, đã sửa).**
Ảnh chụp đầu tiên cho thấy khung vùng 2 và vùng 4 nằm **ngoài ảnh**. Nguyên nhân: tỷ lệ quy đổi
được tính lúc ảnh **chưa tải xong** nên `naturalWidth = 0`, hàm bỏ qua và tỷ lệ kẹt ở `1`.
Sửa: overlay tự sở hữu thẻ `<img>` và tính lại tỷ lệ đúng lúc sự kiện `load`; trước khi đo được thì
**không vẽ khung nào** (`tyLe = null`) — thà chưa hiện còn hơn hiện sai chỗ.

**Lỗi B — chữ tràn khung chạy dọc suốt trang (lỗi của M6, đã sửa).**
Khi ghim cỡ chữ 40 cho một câu dài, chữ được vẽ **đè lên các khung tranh khác**, chạy dọc gần hết
trang. M6 mới chỉ kẹp *điểm bắt đầu* vào biên ảnh chứ chưa cắt chữ theo khung, nên vi phạm chính
ràng buộc của M6: *“không tràn vô hạn ra ảnh”*. Lỗi này **không lộ ra ở M6** vì ca tràn khi đó ở cỡ
nhỏ nhất (10 px) nên khối chữ vẫn gần bằng bbox.
Sửa: mỗi vùng được vẽ vào **một ô riêng đúng bằng bbox** rồi dán đè lên trang, nên chữ luôn bị cắt
gọn trong khung của chính nó. Kèm test bất biến so từng pixel ngoài bbox.

### 5. Giới hạn của lần đo này

- Vẫn là **ảnh tổng hợp** — Run C (manga scan thật) vẫn treo, cùng nút thắt từ M2.
- **Chưa có auth**: ai mở được URL là sửa được, và `edited_by_user` chỉ nói “có người sửa”, không
  nói **ai** sửa. Đúng phạm vi spec (multi-user là mini-spec riêng).
- **Chưa có lịch sử phiên bản**: sửa đè lên bản cũ, không lùi lại được. Dữ liệu gốc của M2/M3/M5 thì
  vẫn còn nguyên để đối chiếu.
- **Giao diện chỉ mới thử ở 1600×1100** bằng Chromium. Chưa thử màn hình nhỏ, chưa thử Firefox/Safari,
  chưa kiểm khả năng dùng bằng bàn phím cho thao tác kéo khung.
- **Dịch lại 1 vùng lẻ thì `llm_context` mất ngữ cảnh cả trang** — đánh đổi có ý thức của việc sửa
  từng vùng, đã ghi trong mô tả endpoint.

---

## M8 — Xuất chapter (PNG / CBZ / ZIP)

**Ngày:** 2026-08-28 · **Môi trường:** workspace `trieunt-c`, Docker, Python 3.12.3,
Postgres 16-alpine, Redis 7-alpine, worker Celery, frontend Vite/React.

### 1. Audit Before Build — 6 mục, có bằng chứng

| # | Mục | Kết quả |
|---|---|---|
| 1 | Bảng `ExportJob` đề xuất | Đủ field, **không thiếu cột nào** phải migrate thêm. `status` **dùng lại enum `job_status`** của M1 thay vì tạo enum trùng nghĩa |
| 2 | `Page.order` | Có sẵn (`Integer`, `NOT NULL`), lại có sẵn index `ix_page_project_order` ⇒ sắp trang khi xuất không phải quét bảng |
| 3 | Dùng lại `PagePreviewRenderer` của M6 | **Chưa dùng lại được ngay**: `render()` chỉ ghi thẳng ra file, trong khi spec yêu cầu PNG binary trong RAM ⇒ tách `draw()` (trả ảnh) + `render()` (= `draw()` rồi ghi file). Không nhân bản logic vẽ |
| 4 | Thư mục `exports/`, quyền ghi worker / đọc API | Worker tạo `exports/_audit/p.txt` → **API đọc lại đúng nội dung**; đĩa còn **66 GB** |
| 5 | Thư viện CBZ/ZIP | `zipfile` là **builtin** (Python 3.12.3), có `ZIP_DEFLATED` ⇒ **không thêm phụ thuộc nào** |
| 6 | Gap | Không có `ExportJob`, không có enum `export_format`, không có logic xuất ⇒ đúng phạm vi M8 |

**Về "Project save/load" ở tiêu đề spec:** toàn bộ state (project, page, region, OCR, bản dịch,
kết quả canh chữ, cờ sửa tay) **đã nằm trong Postgres từ M1** — không có gì giữ trong RAM hay file
tạm để mất. Mở lại project bằng `GET /projects/{id}` là tiếp tục làm việc được ngay; M7 đã dùng đúng
đường đó. Vì vậy **không xây thêm cơ chế save/load nào** — đó sẽ là bảng thứ hai lưu cùng một sự thật.

**Migration `0002_m8`** — dính đúng 2 bẫy mà M1 đã ghi lại, đã xử lý trước khi chạy:
- Alembic sinh `sa.Enum(..., name='job_status')` cho cột `status`, nhưng type này **M1 đã tạo rồi**
  ⇒ phải `postgresql.ENUM(..., create_type=False)`, không thì lỗi *"type already exists"*.
- `downgrade` không tự xoá enum ⇒ thêm `DROP TYPE IF EXISTS export_format`. **Không** drop
  `job_status` vì bảng `job` của M1 vẫn dùng.
- Đã chạy thật **upgrade → downgrade → upgrade** sạch cả 3 lượt.

### 2. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
421 passed, 6 skipped in 113.40s
```

| Nhóm | File | Số test |
|---|---|---|
| Unit — đặt tên file, đánh số trang, đóng gói CBZ/ZIP/PNG | `tests/test_export_unit.py` | 21 |
| Integration — xuất thật trên DB + storage, 4 endpoint | `tests/test_export_integration.py` | 27 |
| Guardrail kiến trúc (M1→M8) | `tests/test_no_ai_logic.py` | 38 (+6 của M8) |
| Dịch lại trang đã canh chữ (lỗi §4 phát hiện) | `tests/test_translate_task_integration.py` | 14 (+1) |
| Kế thừa M1–M7 | các file trước | 321 |

Bài test đáng chú ý của M8:
- `test_danh_so_0_o_dau_de_sap_dung_thu_tu` — `010.png` phải đứng sau `002.png`. Ứng dụng đọc truyện
  sắp trang **theo tên file**; thiếu số 0 đầu là `10.png` chen lên trước `2.png`.
- `test_export_dung_lai_renderer_cua_m6_khong_viet_lai` — quét mã: `chapter.py` **không được** chứa
  `ImageDraw`/`multiline_text`/`getlength`. Hai đường vẽ khác nhau ⇒ ảnh xuất lệch ảnh xem thử.
- `test_khong_export_trang_chua_canh_chu` — chốt danh sách trạng thái được xuất.
- `test_bo_qua_trang_chua_canh_chu_va_noi_ro` — bỏ qua trang chưa xong nhưng **ghi vào `error_log`**.
- `test_con_vung_tran_khung_van_xuat_nhung_ghi_lai` — tràn khung **không chặn** xuất, nhưng phải đếm đúng.
- `test_xuat_lai_khong_tich_tu_file_rac` + `test_doi_dinh_dang_thi_don_file_cu` — chạy lại 3 lần,
  đổi định dạng, thư mục vẫn đúng 1 kết quả, không sót `.tmp`.
- `test_xuat_khong_xoa_du_lieu_goc` — đếm `TextRegion`/`TranslationResult`/`TypesetResult` trước-sau.
- `test_ten_file_export_khong_co_ky_tu_gay_loi_he_tep` — tên project chứa `/ \ : * ? " < > |`.
- `test_bay_task_co_bay_timeout_rieng` — nay là **bảy** timeout độc lập.

### 3. Live verification — xuất chapter thật

Chapter thật 4 trang trong project `26db0621` (2 trang cũ từ M6/M7 + 2 trang mới chạy nguyên
pipeline detect → OCR → xoá chữ → dịch → canh chữ).

| Bước | Kết quả |
|---|---|
| `GET /export-preview` | `4/4 trang, bỏ qua 0, còn 1 vùng tràn khung` |
| `POST /export {format:cbz}` | `202` + job id, **không** render trong request |
| Worker | `4 trang -> …/m3_live_ocr_en_chapter.cbz, 2 vùng tràn khung, bỏ qua 0 trang, xoá 1 thứ cũ, **1,0s**` |
| `GET /export-jobs/{id}` | `done`, `page_count=4`, `error_log = "overflow_warning: 2 vùng còn tràn khung"` |
| `GET /export-jobs/{id}/download` | `200`, `content-disposition: attachment; filename="m3_live_ocr_en_chapter.cbz"`, `cache-control: no-cache` |
| Mở file tải về | ZIP hợp lệ (`testzip() = None`), đúng `001.png…004.png`, **sắp theo tên = đúng thứ tự trang**, mỗi ảnh mở được (PNG 1200×1700 và 1400×2000) |
| Thư mục `exports/` sau 2 lần xuất | **đúng 1 file**, không có `.tmp` |
| Tên file | `m3_live_ocr_en_chapter.cbz` — bỏ dấu, không ký tự lạ |

**Thời gian: 1,0 s cho 4 trang** (≈0,25 s/trang) — rẻ hơn nhiều so với detect (40–61 s/ảnh) hay
xoá chữ (45–117 s/ảnh) vì xuất **không nạp model nào**, chỉ vẽ lại chữ. `EXPORT_TIMEOUT_SECONDS=900`
vì vậy rất rộng rãi; con số này chỉ có ý nghĩa khi chapter lên hàng trăm trang.

### 4. Lỗi thật do live verification phát hiện

**Lỗi A — không trang nào dịch lại được nữa (lỗi của M5/M6, đã sửa).**
Định xuất bản `llm_context` để so sánh thì `POST /pages/{id}/retry-translate` trả **409**:
*"Page đang ở 'typeset_done' — cần xoá chữ xong trước khi dịch"*.
Danh sách điều kiện của M5 viết khi `typeset_done` chưa phải trạng thái tự động; từ M6 pipeline nối
chuỗi nên **mọi trang đều kết thúc ở `typeset_done`** ⇒ endpoint dịch lại cả trang chết hẳn, im lặng,
suốt từ M6 tới giờ. M7 chỉ mở đường dịch lại **từng vùng** nên che mất triệu chứng.
Sửa: thêm `typeset_done` vào danh sách cho phép (state machine đã cho `typeset_done → translated`),
kèm test canh.

**Lỗi B — không phải lỗi phần mềm, nhưng phải ghi: worker bị OOM giết, job kẹt `running` mãi.**
Khi chạy xoá chữ trang thứ 4, worker bị **SIGKILL (signal 9)**:
`WorkerLostError: Worker exited prematurely: signal 9`. Job giữ nguyên `status=running` **vĩnh viễn**,
`error_log` rỗng — không ai đánh dấu `failed`, pipeline đứng im mà nhìn vào không biết vì sao.
Chạy lại tay thì thành công (116,8 s). Máy có 62 GB RAM, container **không đặt giới hạn**.
⇒ Đây là lỗ hổng **thật** của hạ tầng M2–M6, ngoài phạm vi M8: cần watchdog phát hiện job `running`
quá lâu mà worker đã chết. Ghi vào phần còn treo.

### 5. Chất lượng bản dịch trong file giao đi — phát hiện lớn nhất của M8

File CBZ đầu tiên xuất ra **có chữ tiếng Anh chưa dịch**. Truy nguyên: không phải lỗi xuất — xuất
đang phản ánh trung thực thứ pipeline tạo ra.

| Chữ gốc OCR đọc | `google_fast` (mặc định, miễn phí) | `llm_context` (Gemini) |
|---|---|---|
| `ITIS` / `TOO LATE` | **`CNTT`** / `QUÁ TRỄ` | **Muộn quá rồi.** |
| `THE SUN` / `ISUP` | `MẶT TRỜI` / **`ISUP`** | **Mặt trời lên rồi.** |
| `HOLDON` / `TIGHT` | **`HOLDON`** / `CHẮC CHẮN` | **Bám chắc vào.** |
| `ISEE` / `THE END` | **`ISEE`** / `KẾT THÚC` | **Tôi thấy đích rồi.** |
| `WE MUST` / `GO` | `CHÚNG TÔI PHẢI ĐI` (tràn khung) | **Chúng ta phải đi thôi.** |

OCR dính chữ (`IT IS`→`ITIS`, `I SEE`→`ISEE`) là chuyện thường. `google_fast` dịch **từng dòng rời**
nên gặp token lạ là bỏ nguyên tiếng Anh — thậm chí đoán bậy: `ITIS` bị Google hiểu là **viết tắt** và
dịch thành `CNTT` (Công Nghệ Thông Tin). `llm_context` nhìn cả trang nên **tự sửa lỗi OCR**, đúng như
đã chứng minh ở M5 với `IAM` → "Ta ở đây."

**Giá của việc sửa: 386 token cho 2 trang** (184 + 202).

⇒ Mặc định `google_fast` vẫn đúng cho nguyên tắc "không tự tiêu tiền người dùng", nhưng
**cần cảnh báo trước khi giao file**: xuất bằng bản miễn phí có thể ra chữ chưa dịch. Đây là việc của
mini-spec sau, không mở rộng M8 giữa chừng.

### 6. Giới hạn của lần đo này

- **Run C vẫn treo** — vẫn là ảnh tổng hợp. Riêng lần này ảnh mẫu còn có nhược điểm mới: chữ nguồn vẽ
  bằng font mặc định của Pillow nên rất nhỏ, khiến bbox nhận diện chỉ **~50×34 px** (so với ~190×85 ở
  fixture cũ) ⇒ chữ dịch trong ảnh xuất ra trông rất nhỏ. **Không phải lỗi xuất** — M6 canh đúng vào
  bbox nó nhận được.
- **Chưa mở file CBZ bằng ứng dụng đọc truyện thật** (Tachiyomi/Perfect Viewer) — mới kiểm bằng
  `zipfile` + Pillow: đúng cấu trúc ZIP, đúng thứ tự tên, mỗi ảnh mở được. Đủ để tin nhưng chưa phải
  bằng chứng cuối cùng.
- **Chưa đo trên chapter lớn** (hàng trăm trang) — mọi con số thời gian đều từ 4 trang.
- **Chỉ 3/6 và 4/6 bubble được nhận diện** trên 2 trang mới ⇒ tỷ lệ nhận diện của M2 trên ảnh tổng
  hợp kiểu này còn thấp, củng cố thêm lý do phải có ảnh manga thật.

---

## Run C — đo trên TRUYỆN TRANH THẬT (không còn là ảnh tự vẽ)

**Ngày:** 2026-08-28 · **Môi trường:** máy nhà (Docker), pipeline đầy đủ M2→M8.
**Chạy bằng:** `scripts/do_run_c.py` — kịch bản lặp lại được, không chép số bằng tay.

### 0. Ảnh dùng để đo

**Pepper&Carrot** tập 1, tác giả **David Revoy** — https://www.peppercarrot.com — **CC BY-SA 4.0**.

Chọn bộ này thay vì một trang manga chép từ dịch vụ đọc truyện vì hai lý do đều quan trọng:
truyện **vẽ tay thật** (nền màu, chuyển sắc, bong bóng thật) khác hẳn ảnh tổng hợp nền phẳng mà
M2–M8 vẫn dùng; và **giấy phép rõ ràng** nên số đo ghi vào đây công bố được và tái lập được.

Đo ở **1600×2259** — đúng cỡ các dịch vụ đọc truyện phục vụ, không phải cỡ in 2481×3503.

### 1. Kết quả từng trang

**Trang E01P02** — 4 vùng nhận diện, **150 s**:

| # | Khung | Tin cậy | OCR đọc được | Bản dịch (`llm_context`) | Canh chữ |
|---|---|---|---|---|---|
| 1 | 96×64 | 0,87 | `ha...\nperfect.` | Ha... hoàn hảo. | `fit_ok` cỡ 21 |
| 2 | 196×100 | 0,93 | `NO!\nDon't even think\nabout it.` | **KHÔNG! Đừng hòng nghĩ đến chuyện đó.** | `fit_ok` cỡ 23 |
| 3 | 104×197 | 0,63 | *(rỗng)* | — | `pending` |
| 4 | 603×177 | 0,38 | `SPLASH\n18` | **BÕM!** | `fit_ok` cỡ 40 |

**Trang E01P03** — 3 vùng, **99 s**:

| # | Khung | Tin cậy | OCR đọc được | Bản dịch | Canh chữ |
|---|---|---|---|---|---|
| 1 | 106×35 | 0,82 | `Happy?!` | Vui vẻ á?! | `fit_ok` cỡ 24 |
| 2 | 507×56 | 0,46 | *(rỗng)* | — | `pending` |
| 3 | 147×46 | 0,58 | `WWW.PEPPERCARROT.COM\n05/2014` | WWW.PEPPERCARROT.COM | `fit_ok` cỡ 18 |

### 2. Đối chiếu với tiêu chí đã treo từ M2

| Tiêu chí | Kết quả trên ảnh thật |
|---|---|
| **M2: nhận đúng ≥90% bong bóng có chữ** | **3/3 bong bóng thoại thật đều tìm ra (100%)** — đếm tay trên ảnh gốc |
| Nhận nhầm | **2 vùng nhận nhầm** (cây chổi, vệt sáng) — nhưng **cả hai đều có độ tin cậy thấp** (0,46 và 0,63) và OCR trả rỗng nên **tự gắn `needs_manual` + `pending`**, không lọt vào bản dịch |
| **M3: ≥80% OCR đúng nghĩa** | **3/3 câu thoại đọc CHÍNH XÁC từng chữ**, kể cả dấu nháy `Don't` và dấu chấm lửng `ha...` |
| **M4: ≥90% vùng xoá sạch** | **5/5 vùng xoá sạch**, và quan trọng hơn: **hình bong bóng giữ nguyên vẹn** trên nền vẽ tay (xem §4) |
| **M6: chữ vừa khung** | **5/5 `fit_ok`, 0 tràn khung** |

### 3. PHÁT HIỆN LỚN NHẤT — bộ nhớ xoá chữ tỉ lệ với diện tích trang

Trang thật **làm chết worker** ngay lần chạy đầu: `WorkerLostError: signal 9 (SIGKILL)`.

Đo thật mức RAM đỉnh của LaMa:

| Cỡ ảnh | Triệu điểm ảnh | RAM đỉnh | Kết quả |
|---|---|---|---|
| 1400×2000 (fixture cũ) | 2,8 | 4.481 MB | chạy được |
| **1600×2259 (trang thật, cỡ đọc)** | **3,6** | **5.415 MB** | **bị hệ điều hành giết** |
| 2481×3503 (cỡ in) | 8,7 | ~14 GB (suy ra) | không khả thi |

⇒ **~1,6 GB RAM cho mỗi triệu điểm ảnh.** Ảnh tổng hợp của M2–M8 chỉ 1200×1700 (2,0 triệu điểm)
nên **suốt 7 mini-spec không có gì làm lộ ra giới hạn này**. Đây đúng là thứ Run C sinh ra để tìm.

**Đã sửa: xoá chữ theo CỤM bong bóng thay vì cả trang.** Bộ nhớ khi đó tỉ lệ với ô cắt, không
với trang. Các vùng gần nhau được gộp làm một cụm để chỗ giao không bị vẽ đè hai lượt.

Đo lại trên đúng ảnh vừa làm chết worker (1600×2259, 4 bong bóng):

| Cách làm | RAM đỉnh | Thời gian |
|---|---|---|
| Cả trang (cách cũ) | 5.415 MB | 72 s |
| **Theo cụm (cách mới)** | **1.109 MB** | **19 s** |

**Giảm 5 lần bộ nhớ, nhanh gấp 3,8 lần.** Trang ≤ `INPAINT_WHOLE_PAGE_MAX_MPX` (mặc định 2,5
triệu điểm) vẫn chạy cả trang như M4 đã kiểm chứng — đường cũ không bị đụng tới.

### 4. Nhìn bằng mắt — thứ ảnh nền phẳng không kiểm được

Phóng to bong bóng `NO! Don't even think about it.` trên nền tranh vẽ tay:

- Chữ **xoá sạch hoàn toàn**, không còn vệt mờ nào.
- **Đường viền bong bóng còn nguyên vẹn** — LaMa không ăn lem vào nét vẽ. Đây là điều đáng lo
  nhất trước khi đo (fixture cũ chỉ có nền trắng phẳng nên không chứng minh được gì).
- Chữ Việt chèn vào nằm gọn trong bong bóng.

Trang E01P03 (nền trời đêm nhiều sao, chuyển sắc) cũng cho kết quả tương tự.

### 5. Chất lượng dịch — `llm_context` hơn hẳn, đúng như M8 đã cảnh báo

| Chữ gốc | `google_fast` (miễn phí) | `llm_context` |
|---|---|---|
| `NO! Don't even think about it.` | *"KHÔNG! thậm chí không nghĩ về nó."* — **mất hẳn nghĩa cấm đoán** | **"KHÔNG! Đừng hòng nghĩ đến chuyện đó."** |
| `SPLASH` (từ tượng thanh) | *"TUYỆT VỜI"* — **dịch sai hoàn toàn** | **"BÕM!"** — nhận đúng là tiếng động, và **bỏ luôn số `18`** vốn là hình vẽ lọt vào khung |

Đây là bằng chứng thứ hai, trên ảnh thật, cho kết luận ở `REPORT_M8 §8`.

### 6. Còn treo sau Run C

- **Chưa đo trên manga Nhật thật** (chữ dọc, đọc phải→trái). Pepper&Carrot là truyện phương Tây,
  chữ ngang — nên Run C này **chưa** kiểm được đường `ja` và giới hạn "không hỗ trợ chữ dọc"
  đã ghi ở `REPORT_M6 §10`.
- **Nhận nhầm 2/7 vùng** (~29%). Không lọt vào bản dịch nhờ ngưỡng tin cậy, nhưng vẫn tạo ra
  vùng thừa mà người biên tập phải bỏ qua bằng tay.
- **Dòng ghi công của tác giả bị coi là chữ cần dịch** (`WWW.PEPPERCARROT.COM 05/2014`). Về
  nguyên tắc không nên đụng vào; cần một luật loại trừ vùng ở rìa trang.
- **Cỡ in (8,7 triệu điểm ảnh) chưa đo** — theo tỉ lệ thì cần ~14 GB nếu chạy cả trang; với cách
  cắt cụm thì không còn phụ thuộc cỡ trang nữa, nhưng phải đo mới được nói chắc.

## M9 — Chạy cả chapter theo mẻ (batch)

> Mọi con số dưới đây do `scripts/do_run_m9.py` in ra, không chép tay. Chạy lại được:
> `.venv/bin/python scripts/do_run_m9.py A test_fixtures/external/*_1600.png`.
> Ảnh đo: **Pepper&Carrot** ep.1 trang 1–3 (CC BY-SA 4.0, David Revoy) — truyện tranh **thật**,
> không phải ảnh tổng hợp. Cấu hình lúc đo: `BATCH_MAX_CONCURRENT_PAGES=1`,
> `BATCH_MAX_RETRIES=3`, `BATCH_RETRY_BACKOFF_BASE_SECONDS=10` (số dev, cố ý để lớn hơn mặc định
> 2s cho đủ thời gian quan sát), `LLM_PROJECT_RPM=10`, tự-nối bước **tắt** để mẻ là thứ duy nhất
> điều phối.

### 1. Test tự động

| Nhóm | Số test | Kết quả |
|---|---|---|
| Toàn bộ M1–M9 | **546** | pass, 0 fail |
| Riêng M9 (`test_batch_unit.py` + `test_batch_integration.py`) | 90 | pass |
| Guardrail (`test_no_ai_logic.py`) | 47 | pass |

Guardrail của M9 canh những thứ mà "code chạy được" không phát hiện ra:

- không có `APIKeyPool`/xoay khoá cùng project ở bất kỳ file nào,
- bộ điều phối không nhắc tới bất kỳ engine nào của M2–M8 (không sao chép logic pipeline),
- mẻ không nhắc tới `ExportJob`/`run_export_job` (không tự xuất chapter),
- `gate.py` không chứa chuỗi nào liên quan khoá, bắt buộc có băm,
- Celery **không** đặt `rate_limit` ở bất kỳ đâu (nó chỉ giới hạn từng worker, không toàn cục),
- mỗi task pipeline báo kết quả về mẻ ở **cả 3 nhánh** (đếm bằng AST, không phải đọc chuỗi),
- việc thao tác tay **không** báo về mẻ,
- chỉ **một** chỗ trong toàn bộ mã được phép dựng `BatchOrchestrator`.

### 2. Run A — chạy cả chapter bằng một mẻ (bắt buộc)

Mẻ `bdf72fef`, project `c10032f2`, engine `google_fast`, 3 trang.

| Đo | Kết quả |
|---|---|
| Số trang chụp lúc tạo mẻ | 3 (đúng `Page.order` 1-2-3) |
| Trang tải lên **sau** khi tạo mẻ có lọt vào không | **không** |
| Tổng thời gian | **143,2s** cho 3 trang (4 bước/trang = 12 việc) |
| Trang 1 xong | 102,8s |
| Trang 2 xong | +26,3s |
| Trang 3 xong | +14,1s |
| Trạng thái mẻ | `completed` 3/3, 0 hỏng, 0 bị chặn |

Trang đầu chậm gấp 4–7 lần hai trang sau vì worker phải **nạp mô hình lần đầu** (PaddleOCR + LaMa
+ font). Đây là lý do chạy cả mẻ rẻ hơn chạy từng trang rời: chi phí nạp mô hình trả **một lần**.

Bằng chứng không tạo kết quả trùng — đếm sau khi mẻ xong:

| Trang | Trạng thái | Vùng | Có bản dịch | Đã canh chữ | MD5 ảnh xem thử |
|---|---|---|---|---|---|
| 1 | `typeset_done` | 2 | 2 | 2 | `9230ed1d…` |
| 2 | `typeset_done` | 4 | 3 | 3 | `b71a5e05…` |
| 3 | `typeset_done` | 3 | 2 | 2 | `1bc802db…` |

Số vùng khớp **chính xác** với Run C đo rời từng trang trước đó (trang 2: 4 vùng, trang 3: 3 vùng)
⇒ chạy theo mẻ cho kết quả y hệt chạy lẻ, không nhân bản bản ghi.

### 3. Run B — lỗi tạm thời rồi thành công (bắt buộc)

Cách gây lỗi: chặn **thật** ở tầng mạng trong container worker (`/etc/hosts` trỏ
`clients5.google.com` và `translate.googleapis.com` về `127.0.0.1`) — không mock hàm dịch, nên
đường đi của lỗi giống hệt lúc mạng thật hỏng.

| Mốc | Kết quả |
|---|---|
| 0,0s | mẻ chạy, dò khung xong từ trước |
| 28,7s | dịch **hỏng** — phân loại `transient_network`, thử lại lần 1, hẹn chờ **6,9s** |
| 28,7s | bỏ chặn mạng |
| 38,8s | trang `completed`, mẻ `completed` 1/1 |

- Đúng **1** lần thử lại, không thử lại vô hạn.
- Thời gian chờ 6,9s nằm trong dải `[5s, 10s]` của mốc lùi dần 10s (nhiễu một nửa).
- Bước **canh chữ ngay sau đó được đẩy với thời gian chờ 0s** — không bị phạt oan.
- MD5 ảnh xem thử `9230ed1d…` **trùng khít** Run A cùng trang ⇒ thử lại không tạo ra kết quả khác
  hay bản ghi thừa.

### 4. Run C — cổng hạn mức chặn, không có lời gọi nào ra nhà cung cấp (bắt buộc)

Mẻ `8c26ad61`, engine `llm_context`, cổng bị **giữ đầy liên tục** suốt mẻ.

| Mốc | Kết quả |
|---|---|
| 25,5s / 32,6s / 50,9s | 3 lần thử lại, đều bị chặn **tại cổng** — `transient_rate_limit` |
| 73,2s | mục `blocked_quota`, mẻ `blocked_quota` (0 xong, 0 hỏng, **1 bị chặn**) |
| thả cổng + `POST /resume` | `resumed_count=1` |
| +5,1s | mẻ `completed` |

- **Không một lời gọi nào ra `generativelanguage.googleapis.com`** trong cả 4 lần: lỗi được ném ra
  *trước* khi tạo HTTP request, thông điệp ghi rõ `cổng nhịp chặn (rate_limited), còn 0 lượt`.
- Mẻ **không** báo `completed` trong lúc còn trang bị chặn.
- Sau khi hạn mức hồi, chính mẻ đó chạy lại được — không phải tạo mẻ mới.
- Bản dịch sau khi qua cổng là **LLM thật** (đây cũng là Run D không bắt buộc, 1 trang):
  `NO! Don't even think about it.` → **"KHÔNG! Đừng hòng nghĩ đến chuyện đó."**,
  `SPLASH` → **"BÕM!"** — khớp với kết luận chất lượng ở `REPORT_M8 §8`.

Hai biến thể phụ, đều có ích:

| Biến thể | Cấu hình | Kết quả |
|---|---|---|
| C1 | `LLM_FALLBACK_TO_GOOGLE=true` (mặc định) | cổng chặn ⇒ **lùi về `google_fast`**, mọi dòng mang nhãn `fallback_used`, 0 lời gọi ra Gemini. Đường lùi của M5 vẫn nguyên vẹn. |
| C2 | chỉ làm đầy cổng **một lần** | lần thử thứ 4 **lọt qua** sau khi cửa sổ 60s trượt hết ⇒ cổng là bộ **giữ nhịp**, không phải khoá chặn vĩnh viễn. Đúng ý muốn, nhưng đây là lý do Run C phải giữ cổng đầy liên tục mới đo được trạng thái `blocked_quota`. |

### 5. Run E — worker chết giữa mẻ rồi chạy tiếp (bắt buộc)

Mẻ `f0b024ac`, 3 trang. Giết worker (`docker compose kill worker`) đúng lúc trang 2 đang chạy.

| Mốc | Kết quả |
|---|---|
| lúc giết | mẻ `running` 1/3 — trang 1 xong, trang 2 `running`, trang 3 `pending` |
| worker sống lại | mẻ vẫn 1/3, trang 2 kẹt `running` (việc chạy nó đã biến mất) |
| `POST /resume` | `resumed_count=1` — thu hồi mục mồ côi, `error_code=stale_reclaimed` |
| +46,4s | trang 2 xong |
| +60,5s | trang 3 xong, mẻ `completed` 3/3 |

| Kiểm | Kết quả |
|---|---|
| Ảnh chụp danh sách trang trước/sau sự cố | **không đổi** |
| MD5 ảnh xem thử 3 trang so với Run A | **giống hệt** (`9230ed1d…`, `b71a5e05…`, `1bc802db…`) |
| Số vùng / bản dịch | không nhân bản |

### 6. Hồi quy sống — chạy 1 trang lẻ khi KHÔNG có mẻ nào

Tải 1 trang lên project trắng với cấu hình mặc định (tự-nối bật): `queued → detecting(4s) →
detected(40s) → ocr_done(56s) → typeset_done(72s)`, và `GET /projects/{id}/batch-runs` trả **0 mẻ**.
Đường đi cũ của M2–M6 không bị M9 đụng vào.

### 7. Sáu lỗi thật do M9 làm lộ ra (đều đã sửa, đều có test đỏ trước khi xanh)

| # | Lỗi | Vì sao nguy hiểm | Cách phát hiện |
|---|---|---|---|
| 1 | `run_detect_job` chỉ báo kết quả về mẻ ở nhánh **thành công** | Dò khung là bước đầu và hay hỏng nhất. Hỏng ⇒ mục nằm lại `running` tới mốc thu hồi **2400s**: 40 phút giao diện hiện "đang chạy" trong khi không còn gì chạy | đọc mã + test đếm nhánh bằng AST |
| 2 | Cấu hình thử lại **không có tác dụng** ở worker | Tầng API dựng `RetryPolicy` từ `.env`, tầng worker dựng bằng tay và quên truyền — mà mọi quyết định thử lại đều ở worker. Đặt lùi dần 30s, **đo được 0,6s** | Run B |
| 3 | `next_delay_seconds` viết ra nhưng **không chỗ nào gọi** | Thử lại gọi lại ngay lập tức — đúng thứ tệ nhất ngay sau khi nhà cung cấp báo "quá nhịp" | đọc mã trước khi chạy Run B |
| 4 | Bước **kế tiếp** bị phạt chờ oan | Log thật `đẩy bước typeset …, chờ 3.7s` — canh chữ không liên quan gì tới lỗi mạng lúc dịch, nhưng lấy thẳng `retry_count` làm căn cứ nên mọi bước sau đều bị phạt | log Run B |
| 5 | Nhiễu toàn phần cho ra **0,2s** | "Có lùi dần" trên giấy nhưng thực tế chờ như không chờ. Đổi sang nhiễu **một nửa**: luôn chờ ít nhất nửa mốc | log Run B |
| 6 | Bấm "chạy lại" ngay sau sự cố **không cứu được gì** | Thu hồi mục mồ côi chỉ dựa vào đồng hồ (2400s), nên `resumed_count=0` và mẻ treo ở 2/3. Sửa: **hỏi broker** xem việc còn sống thật không | Run E |

Ngoài ra hai lỗi khác đã được phát hiện và sửa **trước** khi đo (ghi lại vì cùng một họ):
mục bị đánh `skipped` khi trang đang chạy dở (mẻ báo "3/3 hoàn thành" trong khi còn trang kẹt),
và mẻ đứng im khi vòng đẩy việc chỉ toàn mục bị bỏ qua.

### 8. Giới hạn của lần đo này

- **Chỉ 1 worker, `--concurrency=1`.** Cổng nhịp Redis có test 40 luồng tranh nhau ở mức đơn vị,
  nhưng **chưa** đo với nhiều container worker thật. Trước khi tuyên bố "giữ đúng hạn mức toàn
  cục" ở môi trường nhiều máy thì phải đo lại với Redis dùng chung.
- **Hạn mức thật của nhà cung cấp chưa đo.** `LLM_PROJECT_RPM=10` là số dev đặt ra, không phải số
  Google công bố cho project này.
- **Chưa đo mẻ dài** (10+ trang, chạy hàng giờ) — mới đo tối đa 3 trang.
- Thời gian chờ lùi dần lúc đo dùng `BATCH_RETRY_BACKOFF_BASE_SECONDS=10` cho dễ quan sát; mặc
  định đã trả về **2s**.
- **Giao diện chưa bấm thật trên trình duyệt.** Bảng "Chạy cả chapter" đã dựng và build sạch,
  các endpoint nó gọi đều đã đo ở trên, nhưng chưa có phiên thao tác tay như M7.
