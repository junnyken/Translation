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

## M10 — Khai báo mục đích & nhắc trách nhiệm trước khi giao file

> Số liệu do `scripts/do_run_m10.py` in ra. Chạy lại:
> `.venv/bin/python scripts/do_run_m10.py <project_id>`.
> Chạy trên chapter thật của Run A (Pepper&Carrot 3 trang) — **không dựng dữ liệu giả**: vùng
> tràn khung được tạo bằng đúng thao tác người dùng làm ở màn sửa tay, không ghi thẳng
> `overflow_warning` vào DB.

### 1. Test tự động

| Nhóm | Số test | Kết quả |
|---|---|---|
| Toàn bộ M1–M10 | **579** | pass, 0 fail |
| Riêng M10 (`test_compliance_unit.py` + `test_compliance_integration.py`) | 27 | pass |
| Guardrail (`test_no_ai_logic.py`) | 53 | pass |

Guardrail của M10:

- giao diện **không chọn hộ** mục đích sử dụng (`useState('')`, nút mờ khi chưa chọn),
- nút xuất trong hộp thoại có `disabled={!daTick}`,
- hộp thoại hiện **đủ cả hai** loại cảnh báo, không ẩn bớt,
- **không** watermark/DRM ở bất kỳ đâu — quét **phần mã**, bỏ chú thích và chuỗi tài liệu,
- không có `public_url`/`share_link`/`make_public`/`publish` trong tầng API,
- bảng nhật ký tuân thủ **chỉ có 10 cột số liệu**, không cột nào chứa nội dung.

### 2. Live — khai báo là bắt buộc, không có mặc định

| Gửi lên | HTTP |
|---|---|
| thiếu hẳn `intended_use` | **422** |
| `intended_use: "commercial"` (ngoài enum) | **422** |
| `intended_use: ""` | **422** |
| `intended_use: "study"` | **201** |

### 3. Live — cảnh báo hiện đúng số thật

Tạo vùng tràn khung bằng thao tác thật: sửa bản dịch một vùng thành câu **170 ký tự** qua màn sửa
tay → hệ thống canh lại → vùng đó thành `overflow_warning` **ở cỡ chữ 10** (đã thu tới đáy
`TYPESET_MIN_FONT_SIZE` mà vẫn không vừa — đúng hành vi M6).

```
GET /projects/{id}/export-warnings
{"overflow_warning_count": 1, "needs_manual_count": 2,
 "acknowledged": false, "acknowledged_at": null}
```

`needs_manual_count = 2` là **số thật có sẵn** từ Run A: hai bong bóng OCR không đọc ra chữ, nên
sẽ **trống** trong file xuất — đúng thứ người dùng cần biết trước khi mang file đi.

### 4. Live — xác nhận, ghi nhận, và không hỏi lại

| Bước | Kết quả |
|---|---|
| `POST /projects/{id}/export` | `202`, có `job_id` |
| `POST /export-jobs/{job_id}/acknowledge {user_acknowledged:true}` | `200`, bản ghi có `overflow_warning_count=1`, `needs_manual_count=2`, `intended_use=study`, `acknowledged_at` có mốc |
| việc xuất | `done` |
| `GET export-warnings` lần sau | `acknowledged: true` ⇒ hộp thoại **không hiện lại** |
| Tải file về | `200`, **10.140.252 byte** — xuất không bị chặn |

Nhật ký trong DB đúng 10 cột: `id, project_id, export_job_id, intended_use,
overflow_warning_count, needs_manual_count, user_acknowledged, acknowledged_at, created_at,
updated_at`. **Không** đường dẫn file, **không** ảnh, **không** bản dịch.

### 5. Hai lỗi thật lộ ra khi chạy M10

| # | Lỗi | Vì sao đáng ghi |
|---|---|---|
| 1 | Bộ quét khoá bí mật đỏ vì một **khoá giả** trong test của M9 | Chuỗi `AIzaSyD-…` viết liền trong `test_batch_unit.py` chỉ lộ ra sau khi M9 được commit (bộ quét chỉ soi file git đã theo dõi). **Một cảnh báo kêu sai là một cảnh báo sẽ bị tắt** — sửa bằng cách ghép chuỗi lúc chạy, không nới lỏng bộ quét |
| 2 | Guardrail "không watermark" đỏ vì **chính đoạn văn giải thích** "không làm watermark" | Soi lời văn thay vì soi mã ⇒ test đỏ vì đúng lý do ngược hẳn ý nghĩa của nó. Sửa: bỏ chú thích + chuỗi tài liệu bằng `tokenize` rồi mới quét |

Ngoài ra script đo của chính M10 từng treo 10 phút vì hỏi trạng thái việc xuất ở sai bảng
(`/jobs/{id}` thay vì `/export-jobs/{id}`, luôn trả 404 rồi ngồi chờ hết giờ). Không phải lỗi sản
phẩm, nhưng ghi lại vì nó cho thấy **chờ mà không kiểm tra mã trả về** là cái bẫy im lặng.

### 6. Giới hạn của lần đo này

- **Giao diện chưa bấm tay trên trình duyệt.** Hộp thoại đã dựng, build sạch, guardrail canh phần
  logic; nhưng chưa có phiên thao tác thật như M7.
- **Chưa đo trường hợp chapter hoàn toàn sạch** (0 tràn khung, 0 chưa đọc được) trên hệ thật —
  mới kiểm bằng test tích hợp.
- `user_acknowledged=false` mới kiểm bằng test, chưa bấm "Để sau" trên giao diện thật.

## E11 — Làm lại giao diện & luồng thao tác

> Số liệu do hai script in ra, chạy lại được:
> `scripts/soi_giao_dien.py --nhan truoc|sau` (đo tràn ngang, điểm dừng tab, lỗi console, chụp ảnh)
> và `scripts/kiem_e11.py` (chạy đúng thao tác người dùng trên Chromium thật).
> E11 **không** đụng vào backend: không đổi API, schema, enum, Celery hay mô hình AI.

### 1. Audit trước khi sửa — đo, không phán bằng mắt

| Mục | Bằng chứng |
|---|---|
| Stack | React 18.3.1 · Vite 6.0.7 · CSS thuần · điều hướng bằng `#hash` · **không có** thư viện icon, không có bộ khung giao diện, **không có bộ chạy test** |
| Enum backend | 17 enum trong `API.md`; giao diện cần diễn giải **8 họ trạng thái** |
| 360×800 | **TRÀN NGANG** — rộng cuộn 398 > khung nhìn 360; thủ phạm: `div.hang` + ô nhập |
| 768 / 1280 / 1600 | không tràn |
| Điểm dừng tab ở trang chủ | **6** |
| Console | **4 lỗi** mỗi lần mở trang (thiếu `favicon`, và `config.js` không có ở môi trường máy nhà) |
| Danh sách chapter | **Không có endpoint liệt kê project** — danh sách "gần đây" lấy từ bộ nhớ trình duyệt |
| Copy hứa thời gian | Giao diện cũ ghi **"mỗi trang mất khoảng 3–6 phút"** — con số này **không có trong bất kỳ phép đo nào**; đo thật ở M9/M10 là ~40–100 giây/trang |

### 2. Sau khi làm lại

| Đo | Trước | Sau |
|---|---|---|
| Tràn ngang 360px | **có** | **không** |
| Tràn ngang 768 / 1280 / 1600 | không | không |
| Lỗi console | **4** | **0** |
| Điểm dừng tab (trang chủ) | 6 | 11 |
| Ô chọn tệp | `<input type=file>` gốc của trình duyệt | vùng kéo-thả, **vẫn giữ input thật ẩn** cho bàn phím và trình đọc màn hình |
| Chữ hứa thời gian | "3–6 phút/trang" (bịa) | "Xử lý chạy nền. Bạn có thể rời trang và mở lại chapter để xem tiến độ." |

### 3. Test tự động

| Nhóm | Số test | Kết quả |
|---|---|---|
| Frontend (`vitest`) | **57** | pass |
| Backend M1–M10 (hồi quy) | **579** | pass — không sửa một kỳ vọng cũ nào |

Trong đó lưới an toàn quan trọng nhất: test **đối chiếu từng giá trị enum trong `API.md`** với bảng
diễn giải của giao diện. Backend thêm trạng thái mà quên cập nhật giao diện thì test đỏ ngay, và
trạng thái lạ bị hiện là *"Trạng thái chưa được hỗ trợ"* kèm mã thô chứ **không** bị đoán là thành công.

### 4. Lỗi thật tìm được khi chạy trên trình duyệt

| # | Lỗi | Đo được | Vì sao đáng sửa |
|---|---|---|---|
| 1 | **Giao diện bỏ cuộc sớm hơn máy chủ rất nhiều** (lỗi có từ M7) | Việc căn lại chữ mất **108 giây** vì đứng sau một chapter 3 trang; giao diện chỉ chờ **42 giây** (60 lượt × 700ms) rồi báo *"Việc chạy nền quá lâu, chưa xong"* | Người dùng tưởng hỏng và sửa lại lần nữa, trong khi việc vẫn chạy và xong bình thường ngay sau đó. Nay chờ tới 10 phút, hiện rõ **"đang chờ tới lượt"**, và nếu hết kiên nhẫn thì nói *"vẫn đang chạy"* chứ không nói là hỏng |
| 2 | Tràn ngang ở 360px | rộng cuộn 398 > 360 | Điện thoại phải cuộn ngang mới thấy hết form |
| 3 | Console 404 mỗi lần mở trang | 4 lỗi/lần | Console nhiễu là console không ai còn đọc — che mất lỗi thật |
| 4 | Chữ hứa "3–6 phút/trang" | đo thật 40–100 giây/trang | Hứa sai về sản phẩm của chính mình |

### 5. Giới hạn của lần làm này

- **Không có chế độ tối, không có bộ nhận diện thương hiệu đầy đủ** — ngoài phạm vi E11.
- **Chưa có endpoint liệt kê chapter**: danh sách "gần đây" vẫn nằm trong bộ nhớ trình duyệt, mở
  máy khác là không thấy. Giao diện **nói rõ điều đó** thay vì giả vờ là danh sách đầy đủ.
  Ghi thành khoảng trống ở `REPORT_E11.md`, không lén thêm API trong E11.
- **Chưa đo bằng trình đọc màn hình thật** (NVDA/VoiceOver) — mới kiểm nhãn liên kết, vòng focus
  và thao tác bàn phím.
- Màn sửa tay (M7) giữ nguyên cách làm việc; E11 chỉ thêm vỏ điều hướng quanh nó.

## E12 — Cổng chất lượng từng vùng

> Số liệu do `scripts/do_run_e12.py` (Run B/C/D) và một script Chromium in ra. Run A đo trực tiếp
> trên **trang truyện thật** đã chạy hết pipeline từ M9 (Pepper&Carrot, CC BY-SA).
> E12 **không** gọi mô hình nào: bộ chấm là luật thuần, không chạm mạng.

### 1. Test tự động

| Nhóm | Số test | Kết quả |
|---|---|---|
| Backend M1–M10 + E11 + E12 | **633** | pass (E12 thêm 54) |
| Riêng E12 backend (`test_quality_unit.py` + `test_quality_integration.py`) | 41 + 13 | pass |
| Frontend (`vitest`) | **66** | pass (E12 thêm 9) |

Test đơn vị chạy **bảng-lái qua đủ 18 mã lý do**, cộng thêm các mệnh đề mà spec coi là ranh giới:
không mã nào ngoài bảng trắng, số/chữ ngắn/chữ hoa không bao giờ bị tự bỏ, "không có điểm tin cậy"
không bị hiểu thành "điểm thấp", và độ dài tính theo **ký tự hiển thị** chứ không theo byte
(`Đừng` = 4 ký tự / 7 byte; `こんにちは` = 5 ký tự / 15 byte).

### 2. Run A — trang truyện thật (bắt buộc)

Trang `57dab44d` của chapter Run A, 4 vùng, chấm bằng `e12-rules-v1`:

| Vùng | Chữ gốc | Kết quả chấm | Lý do máy đưa ra |
|---|---|---|---|
| 1 | `ha... perfect.` | `likely_translatable` · rõ ràng | — |
| 2 | `NO! Don't even think about it.` | `likely_translatable` · rõ ràng | — |
| 3 | *(rỗng)* | `uncertain` · **cần rà soát** | OCR không đọc được nội dung · bước đọc chữ tự đánh dấu cần kiểm tra tay · engine không cung cấp điểm tin cậy |
| 4 | `SPLASH / 18` | `uncertain` · **cần rà soát** | Khung chữ có điểm nhận diện thấp (0,384) |

Không vùng nào bị xoá; bằng chứng số kèm theo từng vùng (`so_ky_tu_goc`, `ty_le_do_dai`,
`ty_le_dien_tich`, điểm tin cậy).

### 3. Run B — bơm lỗi có kiểm soát (bắt buộc)

| Bơm vào | Máy nói ra |
|---|---|
| Đặt bản dịch thành `fallback_used` | *"Đã lùi về đường dịch nhanh vì dịch theo ngữ cảnh lỗi."* |
| Xoá bản dịch của một vùng | *"Chưa có bản dịch cho vùng này."* |
| Đặt căn chữ thành tràn khung | *"Chữ dịch chưa vừa khung."* |
| — | Cả hai vùng đều chuyển sang **cần rà soát** |

Số trên API **khớp chính xác** số đếm thẳng bằng SQL (4 = 4), và hộp thoại xuất nhận đủ ba số mới.
Đáng chú ý: `quality_unassessed_count = 7` — đó là các vùng đã căn chữ **từ trước khi có E12**,
và chúng được đếm là **chưa đánh giá** chứ không bị coi là sạch.

### 4. Run C — quyết định của người dùng (bắt buộc)

| Kiểm | Kết quả |
|---|---|
| Ghi "bỏ qua" và "giữ để dịch" | 200, trạng thái đổi đúng |
| Dữ liệu sau khi bỏ qua | `TextRegion` còn, `OCRResult` còn — **không xoá gì** |
| Khởi động lại API | quyết định vẫn còn |
| Chấm lại | quyết định của người **được giữ** |

### 5. Run D — sửa tay xong thì chấm lại (bắt buộc)

Sửa bản dịch một vùng thành câu 301 ký tự → căn lại → vùng đó được chấm lại và xuất hiện lý do
*"Chữ dịch chưa vừa khung"*. **Vùng không liên quan giữ nguyên đánh giá cũ** — chấm lại có phạm vi,
không quét lại cả chapter.

### 6. Kiểm trên Chromium (10/10 đạt)

Màn chapter có bảng "Vùng cần rà soát" đếm riêng ô *chưa đánh giá được*; màn sửa tay có hộp
"Đánh giá chất lượng" với lý do bằng **câu tiếng Việt** (không lộ mã), hai nút quyết định của
người dùng, và dòng nói rõ *"khung chữ, chữ gốc và bản dịch vẫn được giữ"*. Bấm "Bỏ qua vùng này"
thì nhãn đổi thành **Đã bỏ qua thủ công**. Console 0 lỗi.

Guardrail về câu chữ: không màn nào dùng "bản dịch chuẩn" / "đạt chất lượng" / "dịch đúng hoàn
toàn" — E12 là kết quả của một bộ luật, không phải lời bảo đảm dịch đúng nghĩa.

### 7. Một chỗ tôi sửa TEST chứ không sửa luật

Test đầu tiên của tôi khẳng định `SPLASH` phải bị gắn "có thể là hiệu ứng âm thanh". Nó **đỏ**:
`SPLASH` dài 6 ký tự, còn ngưỡng "chữ ngắn" của spec là ≤5.

Nới ngưỡng lên 6 cho test xanh chính là sửa luật cho vừa test. Sự thật đo được: luật độ dài
**không** bắt được mọi tiếng động — nhưng trên trang thật, vùng `SPLASH` **vẫn** được đẩy cho
người xem, vì một lý do khác: điểm nhận diện khung chỉ 0,384. Tôi giữ ngưỡng ≤5, sửa test cho
đúng sự thật, và thêm một test dựng lại **đúng ca thật** đó.

### 8. Giới hạn của lần làm này

- **Luật độ dài không nhận ra tiếng động dài** (`SPLASH`, `CRASH!!`). Chúng chỉ được đẩy đi rà
  soát khi có dấu hiệu khác. Nhận ra tiếng động theo nghĩa là việc của mô hình, không phải của luật.
- **Không xử lý chữ dọc / chữ xoay / bong bóng hình elip** — thuộc mini-spec khác.
- **Vùng "bỏ qua" vẫn được vẽ vào ảnh xem thử và file xuất.** E12 chỉ ghi quyết định; đổi cách vẽ
  là sửa hợp đồng render của M6/M8, spec cho phép hoãn và tôi hoãn.
- **Chưa có endpoint chấm lại thủ công** — chấm lại đi kèm bước căn chữ. Thêm nó cần một loại
  `Job` mới, mà `ALTER TYPE` trên enum Postgres không an toàn trong một giao dịch.

---

## E13 — Thuật ngữ, giọng nhân vật & rà soát nhất quán

**Ngày:** 2026-08-29 · **Môi trường:** workspace `trieunt-c`, Docker, Python 3.12.3,
Postgres **16.15**, Redis 7-alpine, worker Celery.

### 1. Audit Before Build — 10 mục

| # | Mục | Kết quả |
|---|---|---|
| 1 | E11/E12 đã đóng | `REPORT_E11.md`, `REPORT_E12.md` có; bảng `region_quality_assessment` đang chạy; `ReviewStatus` = `not_required`/`needs_review`/`reviewed_keep`/`reviewed_skip` |
| 2 | Hợp đồng dịch M5 | model `gemini-3.1-flash-lite` (đúng dòng 3.x), engine mặc định `google_fast` |
| 3 | Đường sửa tay M7 | `PATCH /regions/{id}` trả `pending` + `refit_job_id`; `fit_at_size()` là chỗ giữ cỡ chữ đã ghim |
| 4 | E12 `reviewed_skip` | có, và là **quyết định của người** — E13 loại vùng này khỏi quét |
| 5 | Dữ liệu thật | 3 trang Pepper&Carrot (CC BY-SA, David Revoy) còn trong `test_fixtures/external/` |
| 6 | **NULL trong ràng buộc duy nhất** | **Đo thật, xem §2** |
| 7 | Chuẩn hoá Unicode | M6 đã có `normalize_for_layout` (NFC) cho việc vẽ; E13 dựng bộ chuẩn hoá **riêng** cho việc so khớp, không đụng văn bản đã lưu |
| 8 | Thành phần giao diện E11 | `Alert`, `Button`, `Dialog`, `Dropzone`, `EmptyState`, `Field`, `Icon`, `ProgressStage`, `StatusBadge` + nhóm `chapter/` — dùng lại, không dựng bộ sửa thứ hai |
| 9 | Gợi ý bằng LLM | để **TẮT** mặc định (`E13_LLM_SUGGESTIONS_ENABLED=false`) |
| 10 | Gap | không có gì về glossary trong toàn bộ mã nguồn ⇒ đúng phạm vi E13 |

### 2. Đo thật: `UNIQUE` thường **không** chống được trùng khi có NULL

Spec cảnh báo đừng tin vào ràng buộc duy nhất khi khoá ngoại để trống. Kiểm chứng trên chính DB:

```
create table thu (a int, b int, unique (a, b));
insert into thu values (1, null);   -- OK
insert into thu values (1, null);   -- OK  ← LỌT, có 2 dòng giống hệt

create table thu2 (a int, b int, unique nulls not distinct (a, b));
insert into thu2 values (1, null);  -- OK
insert into thu2 values (1, null);  -- ERROR: duplicate key ← đúng
```

Postgres coi **mỗi NULL là một giá trị khác nhau**, nên `UNIQUE` thường vô dụng ở đây —
`ConsistencyReviewTask` có hai khoá ngoại tuỳ chọn (`glossary_entry_id`, `voice_profile_id`) và
việc do luật sinh ra luôn để trống một trong hai. Dùng `UNIQUE NULLS NOT DISTINCT` (Postgres 15+;
bản đang chạy là 16.15). Xác nhận trong DB thật sau khi migrate:

```
uq_consistency_task_idem | UNIQUE NULLS NOT DISTINCT
                           (region_id, task_type, glossary_entry_id, voice_profile_id, snapshot_hash)
```

Đây là thứ khiến **quét lại không đẻ ra việc trùng**.

### 3. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
697 passed, 6 skipped in 204.13s
```

| Nhóm | File | Số test |
|---|---|---|
| Unit — so khớp theo ngôn ngữ | `tests/test_consistency_matching_unit.py` | 25 |
| Integration — thuật ngữ, quét, áp dụng, API | `tests/test_consistency_integration.py` | 37 |
| Guardrail kiến trúc (M1→E13) | `tests/test_no_ai_logic.py` | +8 của E13 |
| Kế thừa M1–M10, E11, E12 | các file trước | 627 |

Bài test đáng chú ý:
- `test_giu_hanh_vi_cua_dau_nhay_va_gach_noi` — `\b` của Python coi `'` và `-` là ranh giới nên
  dùng thẳng sẽ khớp sai; test canh `Don't` ≠ `Dont`, `well-known` ≠ `wellknown`.
- `test_giu_nguyen_dau_tieng_viet` — bỏ dấu để so sẽ khiến `ma` khớp cả `mà`/`má`/`mã` và sinh
  hàng loạt cảnh báo sai.
- `test_thuat_ngu_dai_thang_thuat_ngu_ngan` — `魔法薬` phải thắng `魔法`, nếu không một chỗ bị
  đếm thành hai.
- `test_ban_dich_doi_roi_thi_tu_choi_ap_de` — **chốt chặn quan trọng nhất**: áp bản cũ sẽ xoá mất
  phần người khác vừa sửa.
- `test_khong_ghi_de_quyet_dinh_cua_nguoi` — quét lại KHÔNG mở lại việc người đã từ chối.
- `test_khong_tu_nghi_ra_tu_dong_nghia_de_cam` — chỉ biến thể **người dùng tự khai** mới bị gắn cờ.
- `test_bo_quet_khong_goi_mang` — quét theo luật chạy offline hoàn toàn, không token.
- `test_khong_co_diem_chat_luong_0_100` — kiểm **tên trường** thật; bản đầu của test này bắt nhầm
  chính dòng chú thích giải thích luật.

### 4. Live verification — Run A (bắt buộc)

Chạy trên chapter chứa **3 trang Pepper&Carrot thật** (CC BY-SA), qua đường thật
HTTP → Redis → worker.

**Thuật ngữ đã tạo** (đều bắt đầu ở *nháp*):

| Nguồn | Tiếng Việt đã chốt | Loại | Ghi chú |
|---|---|---|---|
| `SPLASH` | `TÕM` | general_term | Từ tượng thanh — dịch thành tiếng động. Cấm: `TUYỆT VỜI` |
| `Pepper` | `Pepper` | character_name | Giữ nguyên tên |
| `perfect` | `hoàn hảo` | general_term | |

**Quét khi chưa duyệt:** `open_count = 0`, `approved_glossary_count = 0` — đúng: thuật ngữ nháp
không tham gia quét.

**Sau khi duyệt cả 3 rồi quét lại:**

```
open_count = 2   approved_glossary_count = 3
by_type = {"glossary_missing": 1, "prohibited_variant": 1}
```

Cả hai đều trỏ vào **cùng một vùng thật** — vùng mà Run C của M8 đã phát hiện dịch sai:

| Loại việc | Bản dịch hiện tại | Lý do (nguyên văn hệ thống sinh ra) |
|---|---|---|
| `glossary_missing` | `TUYỆT VỜI\n18` | *Chữ gốc có "SPLASH" — thuật ngữ này đã được chốt là "TÕM", nhưng bản dịch hiện tại chưa dùng.* |
| `prohibited_variant` | `TUYỆT VỜI\n18` | *Bản dịch đang dùng "TUYỆT VỜI" — bạn đã ghi đây là cách dịch không dùng cho thuật ngữ "TÕM".* |

`perfect` → `hoàn hảo` **không** bị gắn cờ vì bản dịch đã dùng đúng thuật ngữ — đúng như mong đợi.

### 5. Live verification — Run B (bắt buộc)

| # | Thao tác | Kết quả |
|---|---|---|
| 1 | Áp bản **tự sửa** `TÕM!\n18` | HTTP **202**, kèm `refit_job_id` (canh lại chạy nền, đúng hợp đồng M7) |
| 2 | Việc thứ hai trên **cùng vùng** | tự chuyển `stale` — nó tính trên bản dịch trước đó nên không còn dùng được |
| 3 | Cố áp việc đã cũ | **422** `task_not_open: việc đang ở 'stale'` — không áp đè |
| 4 | Quét lại | **0 việc mở** — sửa xong thì không còn cảnh báo, không báo nhầm |
| 5 | Bản dịch cuối | `TÕM!\n18`, `edited_by_user = true` |
| 6 | **Chữ gốc OCR** | `SPLASH\n18` — **nguyên vẹn**, không bị đụng tới |

Tổng kết: `open=0 · accepted=1 · stale=1`. Đúng một vùng được sửa, đúng một việc canh lại được xếp.

### 6. Giao diện E13 (D1–D5) — dựng ở lần làm thứ hai

`ConsistencyPanel` (D1), `GlossaryManager` (D2), `VoiceProfileManager` (D3),
`ConsistencyReviewQueue` (D4), khối cảnh báo trong `ExportWarningModal` (D5).

**Test giao diện: 91 pass** (`vitest run`, +18 của E13, `src/components/consistency/consistency.test.jsx`).
Những test đáng kể — đều canh **câu chữ có thể lừa người dùng**, không canh màu sắc hay bố cục:

| Test | Chặn điều gì |
|---|---|
| `chưa duyệt thuật ngữ nào thì KHÔNG được trình bày như "đã ổn"` | 0 việc lúc chưa có thuật ngữ nào là **chưa đo**, không phải "đạt" |
| `hết việc thì nói rõ "không còn chỗ lệch thuật ngữ", KHÔNG nói "dịch đúng"` | không nhận vơ đã kiểm được nghĩa |
| `gợi ý đã cũ thì KHÔNG cho áp dụng` | nút áp dụng biến mất hẳn khi việc `stale` |
| `bắt buộc nhập giải nghĩa` | không cho lưu cặp chữ trần trụi |
| `cảnh báo rõ khi sửa mục đã duyệt` | sửa mục đã duyệt ⇒ quay về nháp, phải nói trước |
| `KHÔNG hiện thanh "độ tin cậy của AI"` | hồ sơ giọng là hướng dẫn của người, không phải suy luận máy |
| `hồ sơ giọng KHÔNG được tự chèn vào ô bản dịch` | ngữ cảnh chỉ để đọc |
| `đếm việc nhất quán TÁCH RIÊNG khỏi tràn khung và bản quyền` | ba khối khác bản chất, tick một ô không xử lý cả ba |
| `gợi ý đã từ chối KHÔNG bị tính là việc còn tồn` | quyết định của người không bị đếm ngược lại thành nợ |
| `nhãn tiếng Việt, không phải mã enum` | bắt được đúng lỗi ở mục 8 dưới đây |

### 7. Live verification — Run C (hồ sơ giọng nhân vật)

Chạy bằng **Chromium thật** trên chính hệ thống đang chạy (`scripts/do_run_e13_ui.py`), click
thật từ đầu: tạo hồ sơ → bật → thêm thuật ngữ → duyệt → quét → mở hàng đợi.

Thuật ngữ mới dùng cho lần đo: `Happy` → `Vui chưa` (Carrot **trêu** Pepper, là câu hỏi "vui
chưa?", không phải cảm thán "vui mừng"). Bản dịch máy đang để `Vui mừng?!`.

| # | Đo gì | Kết quả |
|---|---|---|
| C1 | Tạo hồ sơ `Pepper` qua giao diện | ✅ |
| C1b | Hồ sơ mới ở trạng thái **Nháp** | ✅ chưa bật thì không có hiệu lực |
| C1c | Bật lên thành **Đang dùng** | ✅ |
| C2 | Không có chữ "độ tin cậy" ở bất kỳ đâu trên màn hình | ✅ |
| C3 | Hàng đợi hiện đúng việc kèm thuật ngữ đã chốt | ✅ |
| C4 | Hồ sơ giọng hiện **trong** hàng đợi kèm nhãn tiếng Việt (`Pepper · Thân mật`) | ✅ |
| C5 | Có câu nói thẳng "**không** tự sửa lời thoại theo" hồ sơ | ✅ |
| C6 | Ô sửa nạp **bản dịch hiện tại** (`Vui mừng?!`), không phải bản máy tự viết | ✅ |
| C7 | **Toàn bộ bản dịch trong CSDL y nguyên trước–sau** (băm md5 từng dòng + cờ `edited_by_user`) | ✅ |
| — | Lỗi console | **0** |

C7 là chốt chặn thật của Run C: chỉ *xem* hồ sơ giọng và mở hàng đợi thì **không** được đụng vào
một ký tự nào của bản dịch.

### 8. Live verification — Run D (cảnh báo lúc xuất)

Hộp thoại xuất phải để **ba** loại cảnh báo ở ba khối tách biệt, vì chúng khác bản chất: bố cục
(tràn khung) · chất lượng (E12) · nhất quán thuật ngữ (E13) · và pháp lý (bản quyền).

| # | Đo gì | Kết quả |
|---|---|---|
| D1 | Có khối riêng "Nhất quán thuật ngữ" | ✅ |
| D2 | Tách khỏi khối "Chất lượng bản đang xuất" | ✅ |
| D3 | Tách khỏi đoạn trách nhiệm bản quyền | ✅ |
| D4 | Đếm đúng: `1 chỗ chưa rà soát` + `1 gợi ý đã cũ` | ✅ |
| D5 | **Vẫn xuất được**, nhãn nút nói thẳng: `Xuất dù còn 1 chỗ cần rà soát (CBZ)` | ✅ |
| D6/D7 | Chưa tick ⇒ nút khoá; tick rồi ⇒ mở | ✅ |
| D8 | Bấm "Để sau" ⇒ **không** có việc xuất nào chạy ngầm (đếm `export_job` trước/sau) | ✅ |

Điều kiện đầu phải dựng lại bằng tay: chapter này **đã xác nhận bản quyền từ lần xuất 28/08**, mà
hộp thoại cố ý chỉ hiện **một lần cho mỗi chapter** — không xoá dấu xác nhận thì Run D không có gì
để quan sát. `don_dep()` trong script làm việc đó và nói rõ lý do.

### 9. Ba lỗi thật lộ ra ở khâu dựng giao diện

**a) Nhãn giọng nói ra thành mã máy.** `GIONG_NOI` là bảng **chuỗi**, nhưng khối ngữ cảnh mới
viết `GIONG_NOI[ma]?.nhan ?? ma` — `.nhan` trên một chuỗi là `undefined` nên rơi xuống nhánh dự
phòng và in thẳng `casual` ra màn hình. Không có gì đổ vỡ, chỉ là người dùng đọc phải chữ máy.
Đã sửa, và test giờ canh cả hai đầu: **phải** thấy `Thân mật`, **không** được thấy `casual`.

**b) Trang trôi ngang 23px trên điện thoại 360px.** Tiêu đề cột ẩn cho trình đọc màn hình
(`.an-nhin`) là `position: absolute`, mà phần tử absolute **chỉ bị cắt bởi khung cuộn có định
vị**. `.bang-cuon` thiếu `position: relative` nên nó đứng ở mép phải của bảng rộng 560px và kéo
cả trang. Đo được bằng `window.scrollX = 23` sau khi `scrollTo(500, 0)`; ẩn `.bang-cuon` đi thì
về đúng 360. Sau khi sửa: **không tràn ngang ở cả 4 kích thước** (360/768/1280/1600), 0 lỗi
console, 29 điểm dừng tab.

**c) Mượn nhầm lưới của E12.** Khối "Vì sao các chỗ này được nêu" dùng lại `.ds-phan-loai`, mà
CSS ở đó có `li b { margin-left: auto }` vì bên E12 con số đứng **cuối** dòng. Ở E13 con số đứng
**đầu**, nên nó bị đẩy sang phải và cả dòng vỡ cột. Đã tách `.ds-vi-sao` riêng.

Cả ba đều chỉ lộ ra khi **nhìn vào màn hình thật** — không test đơn vị nào bắt được, vì cả ba đều
là mã chạy đúng mà hiển thị sai.

### 10. Giới hạn của lần đo này

- **Gợi ý bằng LLM chưa bật và chưa thử** (`E13_LLM_SUGGESTIONS_ENABLED=false`). Đường luật tất
  định chạy độc lập, không cần LLM.
- Luật "giọng nhân vật" ở v1 **cố ý chưa sinh việc tự động**: hồ sơ giọng chỉ là ngữ cảnh biên
  tập hiển thị lúc rà soát. Máy không tự phán một câu có đúng giọng nhân vật hay không.
- Vẫn chỉ đo trên **một** chapter; chưa thử trên chapter dài nhiều chục trang.
- Run C/D chạy trên **Chromium**; chưa thử Firefox/Safari.
- Chưa đo với **bàn phím và trình đọc màn hình thật** cho các thành phần mới — mới chỉ đếm điểm
  dừng tab (29, không đổi so với trước khi thêm E13).


---

## E14 — Vùng an toàn theo hình bong bóng (đang làm)

### 1. Audit Before Build — bằng chứng đo được

Spec E14 đặt một **cổng chặn**: nếu thăm dò trên trang thật cho thấy heuristic chọn nhầm vùng
trắng, phải dừng lại và báo `E14 blocked` chứ không được deploy. Dưới đây là số đo thật.

| # | Mục audit | Kết quả |
|---|---|---|
| 1 | Adapter CTD đưa ra gì | **Chỉ bbox + confidence + chỉ số lớp.** `ctd.py:161-162` chỉ lấy `outputs[0]`; hai nhánh `seg`/`det` của model **chưa bao giờ được giải mã** (`REPORT_M2.md:121` khai đúng). Guardrail "đừng nhầm text mask thành bubble mask" vì vậy là hiển nhiên — không có mask nào để mà nhầm |
| 2 | Ảnh clean của M4 | Kích thước **giống hệt** ảnh gốc (1600×2213 / 1600×2259, đo cả 3 trang) ⇒ toạ độ bbox dùng thẳng được. **Nhưng** mảng LaMa vá vào có độ bão hoà khác lòng bong bóng — đo được: nó rơi khỏi ngưỡng và tạo **lỗ thủng ngay giữa** vùng an toàn |
| 3 | Bộ vẽ chuẩn | `PagePreviewRenderer.draw()` là **một đường duy nhất**; M8 gọi lại đúng hàm đó (`export/chapter.py:44`). Không có hai bộ vẽ |
| 4 | Thư viện trong worker | cv2 **4.10.0**, Pillow 11.0.0, numpy 2.2.1; đủ `findContours`, `distanceTransform`, `morphologyEx`, `connectedComponentsWithStats`, `approxPolyDP`, `erode`. API **không nạp** cv2/torch (test guardrail đo ở mức `sys.modules`) |
| 4b | **Cực tính `distanceTransform`** — đo chứ không đoán | Ô vuông 11×11 giá trị 255 trên nền 0: tâm = **6.0**, sát mép = **1.0**, ngoài ô = **0.0**; đảo mask thì tâm = **0.0**. ⇒ vùng cần đo phải mang giá trị **khác 0**, biên là 0 |
| 5 | **Thăm dò trên 9 vùng thật** | xem §2 |
| 6 | Bất biến theo độ phân giải | Chạy lại toàn bộ 9 vùng ở **0.5× / 0.75× / 1× / 1.5×**: **9/9 ra cùng quyết định ở cả 4 mức**. Tham số tỉ lệ theo kích thước bbox nên không có magic number pixel |
| 7 | `manual_override` | **Ngoài phạm vi v1** — không dựng trình sửa đa giác; M7 đã có sửa bbox tay làm đường lui |
| 10 | Khoảng trống đã xác nhận | `fitter.py:56-60` `content_rect()` chỉ trừ padding theo tỉ lệ của **bbox chữ nhật** — không hề biết biên cong của bong bóng |

### 2. Thăm dò trên trang Pepper&Carrot thật (mục audit 5)

9 vùng thật từ 3 trang đã chạy hết pipeline (`scripts/tham_do/e14_tham_do.py` — **mã thăm dò,
không phải mã sản xuất**; không import `app.*`, không ghi CSDL).

**Kết quả cuối:** 5 bong bóng thật → `shape_derived` (**5/5**); 4 vùng không phải bong bóng
(chữ trên tranh, dòng bản quyền, 2 vùng OCR rỗng) → `fallback` (**4/4**). **0 lần chọn nhầm.**

Bốn lần chạy hỏng trước đó đều là **tham số của tôi sai, không phải phương pháp sai** — và mỗi
lần đều phải nhìn ảnh gỡ lỗi mới biết:

| Lần | Kết quả | Nguyên nhân thật |
|---|---|---|
| 1 | 0/9 | ROI nới theo bbox **chữ** nên nhỏ hơn bong bóng; và phép thử tâm đọc **một pixel** — rơi trúng vệt chữ sót |
| 2 | 1/9 | Vẫn chạm biên ROI. Đổi sang xét cả **đĩa quanh tâm** thay vì 1 điểm |
| 3 | 2/9 | Nới ngưỡng sáng để cứu lỗ thủng ⇒ bong bóng **dính vào nền sáng** (thành phần to gấp 4–7 lần bbox, chạm biên 15–31%) — đúng cái bẫy "chọn vùng trắng lớn nhất" mà spec cảnh báo |
| 4 | 2/9 | Lấp lỗ trên **toàn ROI** ⇒ vùng tối bị nền sáng bao quanh cũng bị nuốt (tỉ lệ so với bbox vọt lên 10.7) |
| 5 | **5/9** | Lấp lỗ **theo từng ứng viên**, chọn đường viền **khít nhất chứa tâm** (không phải to nhất), và tách nhân hình thái ra khỏi ROI |

Khiếm khuyết cấu trúc tìm được ở lần 5: **nhân hình thái đang tỉ lệ theo ROI**, mà ROI lại tỉ lệ
theo bbox — nên nới ROI là vô tình đổi luôn thuật toán, kết quả nhảy 2 → 1 → 3 không đơn điệu.
Sau khi cho nhân bám theo bbox, dãy trở nên đơn điệu và đọc được: 2 → 4 → 4 → 5.

**Tham số v1 chọn theo bằng chứng này** (chưa phải giá trị cuối, sẽ đưa hết vào `.env`):

| Tham số | Giá trị | Vì sao |
|---|---|---|
| ROI nới | 4.0× bbox, trần 1400px | bong bóng lớn hơn bbox **chữ** rất nhiều; nhỏ hơn thì bị cắt và bị loại oan |
| Ngưỡng sáng / bão hoà | V ≥ 200, S ≤ 60 | nới lỏng hơn thì dính nền sáng (đo ở lần 3) |
| Nhân đóng/mở | 6% cạnh ngắn bbox | bám bbox, không bám ROI |
| Lề ăn vào | 6% cạnh ngắn bbox, tối thiểu 3px | |
| Loại nếu chạm biên ROI | > 2% chu vi ROI | tiếp xúc nhỏ không có nghĩa là hình bị cắt |

### 3. Điều phải nói thẳng về chất lượng đa giác

Nhìn tận mắt cả 5 đa giác được chấp nhận: **đúng bong bóng, không cái nào chọn nhầm** — nhưng
hình **còn thô**: có khía lẹm vào, và ở một bong bóng thì cái **đuôi** cũng bị tính vào vùng an
toàn. Lẹm vào là **an toàn** (vùng nhỏ hơn lòng bong bóng thật), còn cái đuôi thì phải để bước
tìm hình chữ nhật nội tiếp loại ra.

⇒ **E14 KHÔNG bị chặn.** Nhưng đây là bằng chứng để đặt kỳ vọng đúng: v1 cho *vị trí đặt chữ
an toàn hơn*, chứ không phải *nhận diện bong bóng chính xác*.


### 4. Test tự động

| Nhóm | Tệp | Số |
|---|---|---|
| Đơn vị — hình học, chọn ứng viên, ô nội tiếp | `tests/test_safe_area_unit.py` | 23 |
| Integration — CSDL thật + ảnh thật, API, ảnh xem thử ↔ file xuất | `tests/test_safe_area_integration.py` | 20 |
| Chốt chặn kiến trúc | `tests/test_no_ai_logic.py` | +6 |
| **Tổng backend** | | **743 pass** (M1–E13 không xước) |
| Giao diện | `vitest run` | **95 pass** (+4 của E14) |

Những test đáng kể — mỗi cái ứng với một cách hệ thống có thể **nói dối**:

- `test_khong_chon_nen_trang_lon_khong_chua_tam_bbox` — cái bẫy "vơ lấy vùng trắng lớn nhất".
- `test_kiem_ca_o_chu_chu_khong_phai_moi_diem_neo` — điểm neo nằm trong mà cả khối chữ vẫn thò
  ra ngoài; đúng kiểu lỗi M6 từng mắc.
- `test_anh_clean_doi_thi_hinh_cu_khong_duoc_dung_lai` — vẽ theo hình của một bong bóng **không
  còn ở đó** là lỗi im lặng tệ nhất mà E14 có thể gây ra.
- `test_e14_ready_phai_co_hinh_that` — `ready` rỗng ruột bị chặn ngay ở tầng kiểu dữ liệu.
- `test_api_chua_tinh_thi_404_chu_khong_tra_hinh_rong` — `geometry=[]` mà đọc thành "vừa khít".
- `test_khung_du_phong_cho_dung_vung_chu_nhu_M6` — xem §5, đây là test sinh ra từ một lệch thật.
- `test_e14_khong_goi_ctd_text_mask_la_bubble_mask` — canh cả **cách dùng từ**: mask của bộ nhận
  diện là mask CHỮ, gọi nó là mask bong bóng là nói sai về bằng chứng.

### 5. Live verification — Run A (bắt buộc)

Chạy trên **9 vùng thật** của 3 trang Pepper&Carrot (CC BY-SA), qua đúng dịch vụ sản xuất.

| Vùng | bbox | Ô đặt chữ | Nguồn | Cỡ chữ M6 → E14 | Chữ nằm trọn trong bong bóng |
|---|---|---|---|---|---|
| …và điều cuối cùng | 167×66 | 91×111 | shape_derived | 19 → **25** | ✅ |
| …mmm có lẽ là không | 174×101 | 111×113 | shape_derived | 25 → **27** | ✅ |
| ha… hoàn hảo. | 96×64 | 69×65 | shape_derived | 21 → 21 | ✅ |
| KHÔNG! thậm chí… | 196×100 | 159×87 | shape_derived | 21 → 20 | ✅ |
| Vui mừng?! | 106×35 | 117×51 | shape_derived | 21 → **29** | ✅ |
| TÕM! 18 (SFX trên tranh) | 603×177 | — | fallback | 40 → 40 | — |
| WWW.PEPPERCARROT.COM | 147×46 | — | fallback | 14 → 14 | — |
| 2 vùng OCR rỗng | | — | fallback | — | — |

- **5/5 vùng shape_derived có toàn bộ dấu chân chữ nằm trong đa giác bong bóng** (tiêu chí đòi
  ≥90%). Đo bằng điểm ảnh: dựng mặt nạ đa giác rồi kiểm cả ô chữ, không phải mỗi điểm neo.
- **0 lần chọn nhầm** trên 4 vùng không phải bong bóng (chữ trên tranh, dòng bản quyền, 2 vùng
  OCR rỗng) — tất cả đều lùi về khung dự phòng kèm lý do đọc được.
- Trái với lo ngại ban đầu, cỡ chữ **tăng** ở 3/5 vùng: vùng an toàn thường **rộng hơn** bbox
  trừ lề, vì bbox chỉ ôm lấy chữ chứ không ôm lấy bong bóng.
- Nhìn ảnh trước/sau: chữ giờ nằm giữa **lòng bong bóng**, không còn lệch sang một bên như khi
  căn theo khung chữ nhật.

### 6. Live verification — Run B (fallback trung thực)

4 ca khó trong bộ trên: chữ tượng thanh nằm trên tranh (`TÕM!`), dòng địa chỉ web trên nền
tranh, và 2 vùng bộ nhận diện bắt được nhưng OCR không ra chữ. **Không ca nào bị gán hình giả**;
mã lý do lần lượt là `shape_candidate_not_centered` (không có vùng sáng nào bao quanh chữ) và
`shape_candidate_touches_roi_boundary` (hình bị cắt ở mép vùng tìm kiếm).

### 7. Một lệch thật do đo mới thấy — và cách sửa

Đường **dự phòng** ban đầu dùng lề ăn-vào của E14, nên cỡ chữ của dòng bản quyền nhảy **14 → 16**
— tức là E14 đổi bố cục ở ngay chỗ nó **không nhận ra hình gì cả**. Không ai xin thay đổi đó và
không có cách nào giải thích cho người dùng.

Đã sửa: khung dự phòng lấy đúng `typeset_padding_ratio` của M6. Đo lại: **2/2 vùng dự phòng cho
cỡ chữ và trạng thái y hệt M6**. Khoá lại bằng `test_khung_du_phong_cho_dung_vung_chu_nhu_M6`.

### 8. Giới hạn của lần đo này

- Mới đo trên **Pepper&Carrot** — bong bóng màu bạc hà trên tranh màu. **Chưa đo trên truyện đen
  trắng** (bong bóng trắng trên nền tối), là ca phổ biến nhất của manga.
- Chưa đo bong bóng tối, bong bóng gradient, chữ dọc, SFX cong.
- Run C (sửa bbox tay rồi tính lại) mới có **test integration**, chưa bấm tay trên trình duyệt.
- Lớp phủ vùng an toàn trên giao diện đã dựng và build sạch, nhưng **chưa xem trên trình duyệt
  thật** với dữ liệu thật.


### 9. Đo trước rủi ro của ảnh đen trắng (dẫn xuất — KHÔNG phải manga thật)

Chưa có trang manga đen trắng nào có bản quyền rõ trong kho, nên chưa thể coi đây là bằng chứng
về manga thật. Nhưng có một rủi ro **đo được ngay**: ở ảnh xám thì **mọi** điểm ảnh đều thoả điều
kiện bão hoà `S ≤ 60`, tức một nửa bộ lọc mất tác dụng và chỉ còn độ sáng gánh việc phân biệt.

Chạy lại cả 9 vùng trên 3 biến thể dẫn xuất từ chính trang màu thật:

| Biến thể | Nhận được hình | Chọn nhầm |
|---|---|---|
| Màu (gốc) | **5/9** | 0 |
| Xám | **3/9** | 0 |
| Xám + tương phản cao | **1/9** | 0 |
| Xám + chấm tram (screentone) | **3/9** | 0 |

Lý do tụt: ở bản tương phản cao, **8/9 vùng** báo `shape_candidate_touches_roi_boundary` — vùng
sáng của tranh bị đẩy lên trắng và **dính liền vào bong bóng**, nên hình bị coi là cắt dở.

Điều đáng giá: tụt là tụt về **dự phòng**, **0 lần sinh hình sai** ở cả 4 biến thể. Tức là ở ảnh
đen trắng, E14 v1 nhiều khả năng **giúp ít hơn** chứ không **hại**. Vẫn phải đo trên trang thật
mới biết con số thật.


---

## E15 — Hướng chữ, thoại dọc & SFX cách điệu (mới audit, CHƯA build)

### 1. Audit Before Build — bằng chứng đo được

| # | Mục audit | Kết quả đo |
|---|---|---|
| 1 | Bộ nhận diện có cho hình học dòng chữ không | **KHÔNG.** Adapter chỉ giải mã bbox; hai nhánh `seg`/`det` chưa bao giờ được đọc (đã chứng minh ở `§E14.1`). ⇒ nguồn bằng chứng mạnh nhất mà spec trông đợi **không tồn tại** |
| 2 | OCR có cho bố cục dòng không | PaddleOCR **có** trả `rec_polys`/`dt_polys` (`ocr/engines.py:153-157`) nhưng chỉ dùng để sắp thứ tự dòng rồi **vứt đi** — `OCRResult` chỉ lưu `raw_text`, `ocr_engine`, `confidence`, `status`. manga-ocr chỉ trả chuỗi. ⇒ muốn dùng phải **lưu thêm**, tức là migration |
| 3 | Ảnh mẫu tiếng Nhật dọc có license rõ | **KHÔNG CÓ.** Kho chỉ có Pepper&Carrot (tiếng Anh, chữ ngang) |
| 4 | Pillow có RAQM không | **KHÔNG** (`features.check("raqm") = False`, harfbuzz/fribidi cũng False). `direction="ttb"` ném `KeyError` **rõ ràng**, không im lặng ⇒ Phương án A bị chặn trừ khi cài thêm |
| 5 | Vẽ chữ dọc theo từng grapheme có được không | **ĐƯỢC.** `regex` 2026.7.19 đã có sẵn (`\X` tách grapheme). Vẽ thử `"Chào bạn nhé, đừng đi!"` theo cột: **dấu tiếng Việt nguyên vẹn**, không tách rời — đã nhìn tận mắt |
| 7 | Quy ước góc của `minAreaRect` | **Đúng là cái bẫy spec cảnh báo.** Đo trên hình biết trước đáp án: hình 0° cho `angle = 90.0` (w/h đảo), hình 90° **cũng** cho `angle = 90.0`. ⇒ góc thô **không phân biệt được 0° với 90°**; bắt buộc phải chuẩn hoá bằng w/h |
| 8 | M7 có điều khiển xoay chữ không | Không có ⇒ ghi đè hướng bằng tay **ngoài phạm vi**, đúng như spec chốt |

### 2. Đo: xoá chữ xong thì còn dấu vết hướng chữ không?

Spec cho phép dùng "dấu vết cấu trúc còn lại trong ảnh clean". Đo thật số điểm ảnh tối trong
từng vùng, trước và sau khi xoá chữ:

| Vùng | Điểm tối ở ảnh gốc | Ở ảnh clean |
|---|---|---|
| 195×99 (thoại) | 1 499 | **0** |
| 173×100 (thoại) | … | **4** |
| 103×196 (không phải bong bóng) | 617 | 667 |
| 602×176 (SFX trên tranh) | 51 163 | 87 078 |

Với **thoại trong bong bóng** — đúng thứ E15 cần đoán hướng — chữ bị xoá **sạch** (còn 0–4 điểm).
Đó chính là việc M4 phải làm. ⇒ **Không thể** đo hướng chữ trên ảnh clean; muốn có bằng chứng
hình học thì phải đọc **ảnh gốc** (chữ còn nguyên). Đây là điểm spec chưa lường tới.

(Hai vùng còn lại tăng điểm tối vì chúng nằm trên tranh chứ không trong bong bóng, nên phép xoá
gần như không đụng tới — không mâu thuẫn với kết luận trên.)

### 3. Điều kiện dừng của spec — đối chiếu

Spec: *"Nếu không có ảnh mẫu chữ dọc hợp pháp, không có bằng chứng hình học tin cậy từ
CTD/OCR, hoặc không có renderer giữ được dấu tiếng Việt → chỉ làm phần routing và ghi rõ
**vertical rendering blocked**. Không được ship một renderer dọc giả để đánh dấu E15 xong."*

Đối chiếu: **không có ảnh mẫu hợp pháp** (mục 3) và **không có hình học từ CTD** (mục 1).
Renderer thì ngược lại — **làm được** (mục 5). Nên theo đúng chữ của spec, E15 v1 phải là
**routing + bằng chứng**, còn phần dựng chữ dọc chỉ được gắn nhãn thử nghiệm/chưa sẵn sàng cho
tới khi có ảnh mẫu thật để chạy Run B.


### 4. Đã build ở lần này (backend)

| Nhóm | Tệp | Số |
|---|---|---|
| Đơn vị — chuẩn hoá góc + bộ nhận biết hướng | `tests/test_orientation_unit.py` | 27 |
| Chốt chặn kiến trúc | `tests/test_no_ai_logic.py` | +6 |
| **Tổng backend** | | **779 pass** (M1–E14 không xước) |

Test đáng kể nhất — mỗi cái ứng với một cách hệ thống có thể **nói dối**:

- `test_goc_tho_KHONG_phan_biet_duoc_0_va_90_nhung_da_chuan_hoa_thi_duoc` — khoá lại **cả tiền
  đề**: nếu một bản OpenCV sau này đổi quy ước, test sẽ đỏ và bắt đọc lại phần audit này.
- `test_TI_LE_KHUNG_KHONG_BAO_GIO_TU_QUYET` — khung cao gấp 5 lần bề rộng vẫn không được tự
  thành chữ dọc. `PHEW!` viết thưa theo chiều dọc vẫn là chữ ngang cách điệu.
- `test_ti_le_khung_khong_lat_nguoc_duoc_bang_chung_hinh_hoc` — khung rất cao **nhưng** các dòng
  nằm ngang ⇒ vẫn là chữ ngang.
- `test_dong_dung_dung_thi_ra_chu_doc_nhung_CHUA_dung_duoc` — nhận ra hướng ≠ dựng được chữ.
- `test_cac_dong_cai_nhau_thi_noi_thang_la_mau_thuan` — không bỏ phiếu đa số cho xong.
- `test_khong_the_tao_chu_doc_ready_ma_khong_co_bang_chung` — ràng buộc nằm ở **tầng kiểu dữ
  liệu**, không phải ở chỗ gọi hàm, nên không lách được.
- `test_e15_khong_sua_chu_ocr_hay_ban_dich` — canh cả `[::-1]` và `reversed(`: đảo chuỗi theo
  hướng là phá bằng chứng của M3/M5.
- `test_e15_khong_dung_goc_tho_cua_minAreaRect` — mọi chỗ đọc `minAreaRect` phải đi qua bộ
  chuẩn hoá.

### 5. Chưa làm

- **Giao diện chưa dựng** (nhãn hướng chữ, bộ lọc, khối cảnh báo lúc xuất).
- **Test integration chưa viết.**
- **Run A–D chưa chạy** — cần ảnh mẫu thật, đặc biệt là ảnh chữ dọc có license rõ.
- **Bộ dựng chữ dọc cố ý chưa dựng** — xem `REPORT_E15.md` §3.


---

# E1 — Tiện ích Chrome mở nhanh (2026-08-30)

Chromium: **Google Chrome for Testing 151.0.7922.34**, nạp unpacked từ `extension/`,
`--headless=new`. ID tiện ích lúc đo: `gppdcagfjgnekmdfbiplpfeahillicgi`.

## E1.1 — Audit trước khi dựng (số đo thô)

```
GET /api/v1/projects                        -> 405 Method Not Allowed   (không có API liệt kê)
curl -H "Origin: chrome-extension://<id>" http://127.0.0.1:8010/api/v1/health
    -> 200, KHÔNG có access-control-allow-origin        (server: uvicorn)
curl -H "Origin: chrome-extension://<id>" http://127.0.0.1:5174/api/v1/health
    -> 200, access-control-allow-origin: *              (server: uvicorn, qua proxy Vite)
curl -H "Origin: chrome-extension://<id>" http://127.0.0.1:5174/healthz
    -> 200, access-control-allow-origin: *  NHƯNG thân là HTML của SPA, không phải JSON
```

Dòng cuối là cái bẫy: **200 OK không phải bằng chứng máy chủ API còn sống.**

Chuẩn hoá URL (Node 22, cùng bộ phân tích WHATWG với trình duyệt):

```
http://2130706433:8010      -> hostname = 127.0.0.1
http://0x7f000001:8010      -> hostname = 127.0.0.1
http://0177.0.0.1:8010      -> hostname = 127.0.0.1
http://127.1:8010           -> hostname = 127.0.0.1
http://[::1]:8010           -> hostname = [::1]                (bị từ chối)
http://localhost%2eevil.example:8010 -> hostname = localhost.evil.example   (bị từ chối)
```

⇒ Bốn dạng đầu **không phải** đường lách — chúng thật sự là loopback. Chỗ an toàn nằm ở việc hàm
trả về địa chỉ **đã chuẩn hoá** và mọi lượt gọi về sau dùng chuỗi đó, không dùng lại chuỗi người
dùng gõ.

## E1.2 — Test tự động

`cd extension && npm test` → **282 pass / 7 tệp**.

## E1.3 — Run A/B/C/D (`scripts/do_run_e1.py`) — 21/21 ĐẠT

Chạy với `.env` **sạch** (không có `CORS_ALLOW_ORIGINS`).

| Mục | Kết quả |
|---|---|
| A1–A3 màn đầu: ô nhập, câu nói rõ phạm vi, gợi ý cổng **đo được** (5174) | ĐẠT |
| A4 `http://evil.example:5174` bị từ chối và **không** ghi vào kho | ĐẠT |
| A5–A7 địa chỉ hợp lệ được lưu, kết nối được, mở được web app | ĐẠT |
| B1–B2 "Tạo chapter mới" → `http://127.0.0.1:5174/`, form tạo chapter hiện ra | ĐẠT |
| C1–C2 kho chỉ có khoá đã khai báo; không key/ảnh/OCR/đường dẫn/cookie | ĐẠT |
| C3 cài đặt sống sót qua lượt mở lại panel | ĐẠT |
| C4–C6 hộp xác nhận nói rõ backend không bị xoá; xoá xong kho sạch; backend vẫn sống | ĐẠT |
| D1–D5 manifest sạch; mở trang ngoài: không tiêm gì, kho không ghi địa chỉ trang | ĐẠT |
| Z1 0 lỗi JS trong console | ĐẠT |

## E1.4 — Nhánh đọc được dữ liệu (`scripts/do_run_e1_ket_noi.py`) — 20/20 ĐẠT

Chapter thật `67094721-c9e4-4231-896d-83b555205a42` (3 trang, đều `typeset_done`).

```
K3  tên thật từ máy chủ:        "E11 kiem ban phim"
K4  số trang thật:              "3 trang · 3 trang xuất được"
K8  Mở rà soát  -> http://127.0.0.1:5174/#page=194bcdf2-c30a-4dbe-8f29-b90fe6bd6f5d
K9  Xem tiến độ -> http://127.0.0.1:5174/#project=67094721-c9e4-4231-896d-83b555205a42
K10 Xuất        -> CÙNG #project= ở trên, KHÔNG có chữ "export" trong địa chỉ
K12 mã bịa 00000000-… -> 404 -> "Không tìm thấy chapter", KHÔNG ghim mục ma
```

Kho sau khi ghim 2 chapter thật:

```json
{"caiDatV1": {"lastConnectionCheckAt":"…","lastOpenedPageId":"194bcdf2-…",
  "lastOpenedProjectId":"67094721-…","preferredLaunchSurface":"side_panel",
  "schemaVersion":1,"translationBaseUrl":"http://127.0.0.1:5174"},
 "chapterGhimV1":[{"cachedAt":"…","projectId":"c10032f2-…", …}]}
```

Đúng 2 khoá, mỗi mục ghim đúng 5 trường trong khuôn, đều có `cachedAt`; **không** có
`source_lang` / `intended_use` / `image_path` / OCR / key.

## E1.5 — Ba lỗi thật do lượt bấm thật tìm ra

**1. Nút chính không bấm được.** `nut()` luôn đặt `type="button"`. Nút "Lưu & kiểm tra kết nối"
nằm trong `<form>` nên **chưa bao giờ** gửi form — màn đầu vô dụng nếu người dùng bấm chuột.
Test đơn vị không bắt được vì nó `dispatchEvent(submit)` thẳng vào `<form>`, đi vòng qua đúng cái
nút hỏng. → sửa: `type = gui_form ? 'submit' : 'button'` + test khoá `expect(b.type).toBe('submit')`.

**2. Kiểm kết nối gọi nhầm máy chủ.** Gọi `<base>/healthz` trong khi `<base>` là địa chỉ **giao
diện**. Vite trả trang SPA kèm 200 + `ACAO: *`. May là bộ đọc JSON vẫn từ chối (`du_lieu_la`) nên
không báo sai "đã kết nối" — nhưng nó báo sai "không kết nối" khi mọi thứ đều ổn. → sửa: gọi
`/api/v1/health` + test khoá endpoint không được chứa `/healthz`.

**3. Nhấp nháy "Chưa kết nối" trước khi kiểm xong.** Trạng thái kết nối chỉ có true/false, mặc
định `false`, nên panel khẳng định một thất bại **chưa hề đo được**. → sửa: ba trạng thái
(`null` = đang kiểm) + 5 test khoá.

## E1.6 — Chưa làm

- **Bấm biểu tượng để mở Side Panel** chưa bấm được trong headless — trang panel được mở thẳng
  bằng địa chỉ `chrome-extension://…`. `sidePanel.setPanelBehavior` chạy không lỗi nhưng hành vi
  bấm biểu tượng **cần một lượt bấm tay**.
- **Chưa đo trên Chrome bản người dùng thật** (mới đo Chrome for Testing).
- **Chưa đo trên bản dựng prod (nginx)** — chế độ chỉ-mở-link ở prod suy ra từ việc đọc
  `default.conf.template` (không có `location /api`), chưa dựng prod lên để bấm.


---

# E15 phần 2 — Giao diện hướng chữ + Run A–D (2026-08-30)

## E15.6 — Audit: worker chạy mã CŨ hơn E15

Trước khi đo được gì, phải tìm ra vì sao bảng `region_text_orientation` rỗng sạch:

```
select count(*) from region_text_orientation;              ->  0
select count(*) from ocr_result where line_polygons is not null;  ->  0 / 97
docker ps --format '{{.Names}}\t{{.RunningFor}}'
  translation-worker-1    44 hours ago        <-- khởi động TRƯỚC khi E15 được commit
```

Thư mục `backend/` được mount làm volume nên tệp trên đĩa là mã mới, nhưng **Celery nạp module
lúc khởi động và không nạp lại**. ⇒ Toàn bộ mã E15 chưa từng chạy một lần nào.

Sau `docker compose restart worker`, chạy lại pipeline một chapter: `line_polygons` và
`region_text_orientation` có dữ liệu ngay.

**Bài học:** mọi mini-spec đụng vào worker phải khởi động lại worker **trước khi đo**, nếu không
là đo nhầm mã cũ và kết luận sai về chính thứ mình vừa viết.

## E15.7 — libraqm: worker ≠ máy dev

```
PIL.features.check("raqm")
  translation-worker-1  -> False        (Pillow 11.0.0, freetype2=True, regex 2026.7.19)
  translation-api-1     -> False
  .venv trên máy dev    -> True         ← KHÁC
```

Vẽ thật bằng font trong `/fonts` (5 font: Bangers, Mansalva, ShantellSans, SigmarOne):

```
worker : draw.text(..., direction="ttb")
         -> KeyError: 'setting text direction, language or font features is not supported
                       without libraqm'          (cả "Đường" lẫn "カタカナ")
máy dev: draw.text(..., direction="ttb")  -> VẼ ĐƯỢC   (cả hai)
```

⇒ Option A (Pillow + libraqm) **không dùng được ở nơi cần dùng**. Một bộ dựng chữ dọc viết và
thử trên máy dev sẽ xanh hết, rồi hỏng im lặng trong worker.

Không có font nào trên máy (host lẫn worker) có glyph kana/kanji: `find / -iname "*CJK*"` → rỗng,
`/usr/share/fonts/truetype/` chỉ có `dejavu`.

## E15.8 — Run A: chữ ngang không hồi quy (6/6 ĐẠT)

Chapter `79b07f20-5afd-4e85-a816-7697240191b6`, 3 trang Pepper&Carrot, 9 vùng.

```
A1 chạy lại pipeline sinh đường bao dòng THẬT        -> 6 vùng
A2 hướng chữ được tính                                -> 6 vùng (rồi 9 sau khi thêm trang 3)
A3 nhận đúng chữ ngang                                -> 5 vùng ngang
A4 vùng ngang bị gọi nhầm thành chữ dọc               -> 0
A5 trang vẫn tới typeset_done                         -> ['typeset_done', 'typeset_done']
A6 GET /pages/{id}/orientation-summary                -> 200, đúng khuôn
```

Mã lý do THẬT xuất hiện trên dữ liệu này:
`ctd_geometry_unavailable`, `bbox_aspect_horizontal_signal`, `ocr_line_geometry_horizontal`,
`orientation_unknown`, `ocr_layout_unavailable`, `safe_area_fallback_rectangle`.

## E15.9 — Run B: BỊ CHẶN (4 vật cản độc lập)

| # | Loại | Số đo |
|---|---|---|
| 1 | Dữ liệu | không có ảnh chữ dọc tiếng Nhật license rõ trong kho |
| 2 | **Kiến trúc** | `MangaOCREngine.recognize()` trả `(text, None)` — không đường bao dòng |
| 3 | Môi trường | libraqm trong worker = False |
| 4 | Glyph | 0 font có kana/kanji |

Vật cản 2 là cái quyết định: `analyzer` chỉ tới được `vertical_ttb` qua
`ocr_line_geometry_vertical`, mà nguồn đó không tồn tại cho tiếng Nhật. **Có ảnh cũng không mở
khoá được Run B** — đây là giới hạn cấu trúc, không phải thiếu dữ liệu.

Chốt chặn: `where orientation='vertical_ttb' and status='ready'` → **0 dòng**.

## E15.10 — Run C: 3/3 ĐẠT nhưng RỖNG

```
C1 mọi vùng đều có phán quyết hướng chữ    -> 9/9
C2 vùng nghiêng thiếu mã 'chỉ rà soát tay' -> 0
C3 vùng nghiêng thiếu góc chuẩn hoá        -> 0

tần suất trên TOÀN BỘ dữ liệu đã phân tích:
    horizontal_ltr = 7
    unknown        = 2
    rotated_horizontal = 0
```

⚠️ Spec đòi tối thiểu 5 ví dụ SFX; thực tế **0**. C2/C3 vì thế là **đúng nhưng rỗng** — chúng
chỉ chứng minh "không có vùng nào vi phạm", không chứng minh đường xử lý chữ nghiêng chạy đúng.
n=9 quá nhỏ để nói gì về tần suất. **Không đủ căn cứ mở E16.**

## E15.11 — Run D: 4/4 ĐẠT

```
D1 GET /projects/{id}/export-warnings              -> 200
D2 khối hướng chữ tách riêng
   {"orientation_vertical_rendered_count": 0,
    "orientation_review_count": 0,
    "orientation_unknown_count": 2}
D3 PATCH /regions/{id} (sửa tay M7)                -> 200
D4 POST /projects/{id}/export {"format":"cbz"}     -> 202
```

Hai lỗi của chính script đo (không phải lỗi sản phẩm), đã sửa: gọi `/exports` thay vì `/export`
(404), rồi `format:"png"` thay vì giá trị enum thật `png_single|cbz|zip` (422).

## E15.12 — Giao diện trên Chromium (14/14 ĐẠT)

Trang `98e5c3bc` — CSDL: 4 vùng, 3 ngang, 1 chưa rõ.

```
U2  số 'Chữ ngang' trên giao diện        = 3, CSDL = 3        KHỚP
U3  số 'Chưa xác định hướng'             = 1, CSDL = 1        KHỚP
U4  huy hiệu tách biệt trên mỗi vùng     >= 2 (căn chữ + hướng chữ)
U6  nhãn hỏng / 'chưa được hỗ trợ' lọt ra giao diện           -> []
U7  bộ lọc                                -> đủ 5 mục
U8  lọc 'Chữ dọc'                         -> 4 vùng còn 0
U9  lọc rỗng                              -> nói rõ, không để bảng trắng
U10 lọc 'Cần kiểm tra hướng chữ'          -> 1 vùng (đúng kỳ vọng)
U12 khối giải thích                       -> tiếng Việt, không lộ mã máy
U13 không có vùng dọc ready               -> công tắc lưới cột chữ VẮNG MẶT
Z1  lỗi JS trong console                  -> 0
```

## E15.13 — Test tự động

`frontend`: **158 pass** (+63 của E15: 8 tệp). Trong đó có test canh:

- Bảng dịch **đủ 15 mã lý do**, khớp 1:1 với `LyDo.TAT_CA` của backend — không thiếu, không thừa.
- Mọi tổ hợp (4 hướng × 4 trạng thái) đều có nhãn đọc được, **không** lọt `undefined`.
- `vertical_ttb + needs_review|unavailable|failed` **tuyệt đối không** mang sắc thái thành công.
- Bộ lọc "Cần kiểm tra" **có** bắt vùng chưa phân tích (`null`).
- Lưới cột chữ chỉ hiện khi `status === 'ready'`.


## E15.14 — Số đo tại thời điểm ĐÓNG E15 (2026-08-30)

Chạy **lại từ đầu**, không chép số của lượt trước. Chapter mới:
`a4e76707-80a0-4dbf-bae6-aa67de639e54` (2 trang Pepper&Carrot, 6 vùng).

### Bộ test tự động

| Bộ | Lệnh | Kết quả |
|---|---|---|
| Backend | `cd backend && ../.venv/bin/python -m pytest -q` | **785 thu thập, exit 0**, 0 fail |
| Frontend | `cd frontend && npx vitest run` | **158 pass / 8 tệp**, 0 fail |
| Extension | `cd extension && npx vitest run` | **282 pass / 7 tệp**, 0 fail |

### Build / lint

```
cd frontend && npx vite build     -> ✓ built in 2.98s, 57 modules
                                     dist/assets/index-DIkt_6FW.js  232.01 kB (gzip 73.87 kB)

ruff check backend scripts        -> 167 phát hiện, NHƯNG repo KHÔNG có cấu hình lint
                                     (không backend/pyproject.toml, không ruff.toml)
   phân bố: backend/tests 157 · backend/app 136 · backend/alembic 11
            do_run_m9 7 · do_run_e15 7 · do_run_e12 5 · do_run_e15_ui 2 · kiem_e11 2
```

⇒ Lint **không phải cổng đã cấu hình** của repo. Hai script E15 mới ngang mức các script đo anh
em. Không sửa trong phase này (mở rộng scope).

### Run A–D lượt đóng phase — 16/16 ĐẠT

```
Run A  A1 đường bao dòng THẬT sinh ra          -> 6 vùng
       A2 hướng chữ được tính                   -> 6 vùng
       A3 nhận đúng chữ ngang                    -> 5 vùng
       A4 vùng ngang bị gọi nhầm thành dọc       -> 0
       A5 trang tới typeset_done                 -> ['typeset_done', 'typeset_done']
       A6 orientation-summary đúng khuôn         -> 200

Run B  BLOCKED — 4 vật cản, B1/B2 đạt
       B2 vertical_ttb + ready trong CSDL        -> 0

Run C  C1 mọi vùng có phán quyết                 -> 6/6
       C2 vùng nghiêng thiếu mã rà-soát-tay      -> 0
       C3 vùng nghiêng thiếu góc chuẩn hoá       -> 0
       tần suất TOÀN BỘ dữ liệu: horizontal_ltr=17 · unknown=4 · rotated_horizontal=0

Run D  D1 export-warnings                        -> 200
       D2 khối hướng chữ tách riêng
          {"orientation_vertical_rendered_count": 0,
           "orientation_review_count": 0,
           "orientation_unknown_count": 1}
       D3 PATCH /regions/{id} (M7)                -> 200
       D4 POST /projects/{id}/export cbz (M8)     -> 202
```

⚠️ **Run C vẫn là pass RỖNG** — `rotated_horizontal=0` trên toàn bộ dữ liệu. C2/C3 đúng nhưng
không chứng minh đường xử lý chữ nghiêng chạy đúng.

### Chromium — 14/14 ĐẠT

Trang `6ff9fb4f` (4 vùng: 3 ngang + 1 chưa rõ), giao diện thật ở `localhost:5174`:

```
U2  'Chữ ngang' giao diện = 3, CSDL = 3          KHỚP
U3  'Chưa xác định hướng' = 1, CSDL = 1          KHỚP
U4  huy hiệu tách biệt mỗi vùng                  >= 2
U6  nhãn hỏng / 'chưa được hỗ trợ' lọt ra        -> []
U8  lọc 'Chữ dọc'                                -> 4 vùng còn 0
U10 lọc 'Cần kiểm tra hướng chữ'                 -> 1 (đúng kỳ vọng)
U12 khối giải thích                              -> tiếng Việt, không lộ mã máy
U13 vùng dọc ready = 0 -> công tắc lưới cột chữ  VẮNG MẶT
Z1  lỗi JS console                               -> 0
```

⇒ Tài liệu **không trái** state UI/DB: cả ba nguồn (CSDL, API, màn hình) cùng nói `vertical=0`.

### Audit 4 assertion trước khi đóng — đo lại, đều còn đúng

```
1. PIL.features.check("raqm")   worker=False · api=False · dev=True         ✓
2. MangaOCR.recognize_with_layout = False; recognize trả (text, None)       ✓
   vertical_ttb chỉ tới được qua ocr_line_geometry_vertical (analyzer:155)  ✓
3. worker đã nạp mã E15: region_text_orientation có dữ liệu thật
   (7 horizontal_ltr/ready + 2 unknown/needs_review trước lượt đóng),
   ocr_result.line_polygons 9/106 — tất cả sinh SAU khi restart worker      ✓
4. vertical_ttb + ready trong CSDL = 0                                      ✓
```


---

# E1a — Siết CORS API local & proxy Vite (2026-08-30)

## E1a.1 — Tách bạch bằng chứng từ quan sát terminal

Người dùng chạy compose ở `/home/coder/workspace` và nhận `no such file or directory`, nhưng API
vẫn trả `ok`. Đo lại từng tầng riêng:

```
compose THẬT   : /home/coder/workspace/projects/Translation/deploy/docker-compose.yml
đường gõ nhầm  : /home/coder/workspace/deploy/docker-compose.yml  -> KHÔNG tồn tại
container      : 5/5 Up (api, frontend, worker, db healthy, redis healthy)
API /healthz   : HTTP 200 · content-type: application/json · server: uvicorn
                 {"status":"ok","worker":{"trang_thai":"khong_ro"}}
worker ping    : pong — 1 node online
worker việc    : 158 job `done` trong 3 giờ gần nhất, mới nhất 13:16:50
/tmp/trang-thai-worker.json trong container api -> KHÔNG tồn tại
```

⇒ Lỗi compose là lỗi **đường dẫn**, không phải Docker/API chết.
⇒ `worker: khong_ro` chỉ nghĩa **API không biết** (tệp trạng thái chỉ có khi `ROLE=all`), không
nói worker khoẻ hay chết. Sức khoẻ worker đo riêng bằng ping + throughput job.

**Đính chính:** thân JSON thật không dấu (`trang_thai`/`khong_ro`); bản chép tay có thêm dấu.

## E1a.2 — Header TRƯỚC khi sửa (Origin thật, curl)

```
Origin: http://localhost:5174        -> :8010/api/v1/health   200  ACAO=(không có)
Origin: http://localhost:5174        -> :5174/api/v1/health   200  ACAO=*
Origin: https://evil.example         -> :5174/api/v1/health   200  ACAO=*
Origin: http://localhost.evil.example-> :5174/api/v1/health   200  ACAO=*
Origin: chrome-extension://gppdc…    -> :5174/api/v1/health   200  ACAO=*
Origin: null                         -> :5174/api/v1/health   200  ACAO=*
Origin: https://evil.example         -> :5174/api/v1/projects/{id}  200  ACAO=*   << DỮ LIỆU THẬT
Origin: https://evil.example         -> :5174/api/v1/pages/{id}/preview  404  ACAO=*
Origin: https://evil.example         -> :5174/healthz  200  ACAO=*  content-type: text/html
```

Nguồn wildcard: **một tầng duy nhất** — Vite 6.0.7 mặc định `server.cors: true`.
FastAPI vốn đã chặn (middleware chỉ gắn khi `CORS_ALLOW_ORIGINS` khác rỗng). nginx prod không có
`add_header` CORS nào.

## E1a.3 — Header SAU khi sửa

**Mặc định (danh sách rỗng):** mọi origin trên đều `ACAO=(KHÔNG CÓ)`, kể cả trên endpoint dữ
liệu thật. Giao diện web vẫn chạy: `curl :5174/api/v1/health` → `{"status":"ok"}`, trang chủ 200.

**Khi khai `DEV_SERVER_CORS_ALLOW_ORIGINS=chrome-extension://gppdcagfjgnekmdfbiplpfeahillicgi`:**

```
chrome-extension://gppdc…(khớp)  ACAO=chrome-extension://gppdc…  Vary=Origin  ACAC=0
chrome-extension://aaaa…(ID khác) ACAO=(KHÔNG CÓ)
https://evil.example              ACAO=(KHÔNG CÓ)
http://localhost.evil.example     ACAO=(KHÔNG CÓ)
http://127.0.0.1.nip.io           ACAO=(KHÔNG CÓ)
null · file://                    ACAO=(KHÔNG CÓ)

OPTIONS từ origin khớp -> 204 · ACAO đúng origin · Vary: Origin
                          Allow-Methods: GET,POST,PATCH,OPTIONS · Allow-Headers: Content-Type
OPTIONS từ origin lạ   -> 405 · KHÔNG header CORS nào
```

## E1a.4 — Bộ test

| Bộ | Lệnh | Kết quả |
|---|---|---|
| Backend | `cd backend && ../.venv/bin/python -m pytest -q` | **785 thu thập, exit 0** |
| Frontend | `cd frontend && npx vitest run` | **226 pass / 9 tệp** (+68) |
| Extension | `cd extension && npx vitest run` | **282 pass / 7 tệp** |
| Build | `cd frontend && npx vite build` | ✅ 1.98s · 232.01 kB |

## E1a.5 — Chromium thật (`scripts/do_run_e1a.py`) — 17/17, chạy HAI lần

Website lạ thật ở cổng 9999; `localhost.evil.example` ánh xạ về loopback bằng
`--host-resolver-rules` ⇒ origin thật trong trình duyệt.

```
                                        mặc định        đã khai origin tiện ích
L1  giao diện gọi API cùng nguồn        200 ok          200 ok
L2  giao diện đọc chapter thật          200, 411 byte   200
L4  website lạ đọc /api/v1/health       CHẶN            CHẶN
L5  website lạ đọc dữ liệu chapter      CHẶN            CHẶN
L6  website lạ đọc API trực tiếp :8010  CHẶN            CHẶN
L8  localhost.evil.example đọc API      CHẶN            CHẶN
L9  getPanelBehavior()                  openPanelOnActionClick: true
L10 manifest quyền                      ['storage','sidePanel'], host_permissions []
L11 "Tạo chapter mới"                   http://127.0.0.1:5174/
L12 hành vi E1                          CHỈ-MỞ-LINK     ĐỌC METADATA THẬT
L13 tắt máy chủ                         báo chưa kết nối kèm 3 lý do
L13b câu danh sách rỗng                 chỉ về ứng dụng, không khẳng định "không có chapter"
L14 sau restart: giao diện              200
L15 sau restart: website lạ             VẪN CHẶN
Z1  ngoại lệ JS                         0
```

Lỗi chặn trong trình duyệt là `TypeError: Failed to fetch` — đúng biểu hiện của CORS deny.

## E1a.6 — Hai lỗi của chính bộ đo (không phải lỗi sản phẩm)

1. **`socketserver.TCPServer` đơn luồng**: một `BrokenPipeError` làm kẹt cả máy chủ thử, khiến
   trang `localhost.evil.example` timeout. → `ThreadingTCPServer` + nuốt broken pipe.
2. **Tiêu đề render HOA do CSS `text-transform`**: `inner_text` trả `"CHAPTER ĐÃ GHIM"`, nên
   `split("Chapter đã ghim")` không bao giờ khớp và phép kiểm L13 báo hỏng oan. Panel vốn hiển
   thị **đúng** — đã dump toàn bộ text để xác nhận trước khi sửa phép kiểm.

## E1a.7 — Còn treo

Chưa bấm tay biểu tượng tiện ích trên thanh công cụ: môi trường không có display server
(`$DISPLAY` rỗng, không Xvfb) và không API nào dispatch được cú bấm vào chrome UI. Đã kiểm phần
kiểm được: `getPanelBehavior()` → `{openPanelOnActionClick: true}`.


---

# Deploy 001 — Push GitHub + VibeHost (2026-08-30/31)

Chi tiết đầy đủ: `docs/REPORT_DEPLOY_001.md`.

## D001.1 — Hồi quy trước phát hành

```
backend  : 785 thu thập, exit 0
frontend : 226 pass
extension: 282 pass
build    : vite build ✓ 2.17s
lint     : KHÔNG phải cổng phát hành (repo chưa có ruleset)
```

## D001.2 — Push

```
7ca8af6..45c0af2  main -> main   (103 object, 167.44 KiB)
git ls-remote origin main -> 45c0af26b913cd83ea43446218552126cca3bf54
tag: CHƯA đẩy (v1.5-E15-closed, v1.6-E1a-cors-hardening còn local)
```

## D001.3 — Deploy

```
translation-api  v20 -> v21   31/08 00:12   job cmtg2exdn0ede0i5f56kswhpp  succeeded
translation-web  v12 -> v13   31/08 00:13   job cmtg2i0oh0efm0i5fajnvxnii  succeeded
push KHÔNG tự deploy -> redeploy thủ công
rollback sẵn: api->20, web->12
```

## D001.4 — Bằng chứng phiên bản (không có build SHA ⇒ dùng tính năng)

```
/api/v1/khong-he-co-route-nay            -> {"detail":"Not Found"}
/api/v1/pages/{uuid}/orientation-summary -> {"detail":"page_not_found"}            <- E15 CÓ
/api/v1/regions/{uuid}/orientation       -> {"detail":"orientation_not_analyzed…"} <- E15 CÓ

bundle web /assets/index-CGGZ4XNz.js (238.952 byte) chứa:
  "Chữ dọc — đã căn theo cột" · "Chưa xác định hướng chữ" · "Hiện lưới cột chữ"
  · "Chữ nghiêng/cách điệu" · "orientation-summary"
```

## D001.5 — Smoke Chromium thật: 11/11 ĐẠT

`scripts/do_smoke_hosted.py` — website lạ ở cổng 9999 gọi API hosted.

```
H1 HTTPS                                    ĐẠT
H2 __API_BASE__ trỏ đúng API hosted         ĐẠT
H3 giao diện E11 hiện form tạo chapter      ĐẠT
H4 giao diện ĐỌC ĐƯỢC API chéo nguồn        ĐẠT  200 {"status":"ok"}
H5 website lạ đọc /api/v1/health            CHẶN (TypeError: Failed to fetch)
H5 website lạ đọc /healthz                  CHẶN
H6 không tràn ngang 360/768/1280/1600       4/4 ĐẠT
Z1 lỗi JS console                           0
```

## D001.6 — Ma trận CORS hosted (trước == sau deploy)

| Origin | ACAO |
|---|---|
| `https://translation.cmc-1.vibenode.matbao.ai` | khớp chính xác |
| `https://evil.example` | *(không có)* |
| `http://localhost:5174` | *(không có)* |
| `null` | *(không có)* |
| `…matbao.ai.evil.example` (giống tên miền thật) | *(không có)* |

`ACAO: *` → 0 · `Allow-Credentials` → 0.

## D001.7 — Worker: `starting` KHÔNG phải bằng chứng

```
{"worker":{"trang_thai":"starting","so_lan_chet":0,"luc":"2026-08-30T17:12:14Z"}}
```

`backend/deploy-start.sh` ở `ROLE=all` ghi `starting` **một lần** lúc khởi động, chỉ ghi lại khi
worker chết (`restarting`) — **không bao giờ** ghi `running`. Nên trạng thái này chỉ chứng minh
"đã bật, chưa sập", KHÔNG chứng minh worker đang tiêu thụ việc. Cần Pilot mới biết.


---

# P3a — Sẵn sàng Pilot/UAT trên VibeHost (2026-08-31) — **BLOCKED**

Chi tiết: `docs/REPORT_P3a_HOSTED_READINESS.md`.

## P3a.1 — Worker hosted: chứng minh bằng việc thật, không bằng telemetry

Một trang smoke **tự vẽ** (1200×1700, 2 bong bóng, không dùng tranh có bản quyền) tải qua **đúng
giao diện E11 hosted**:

```
  3.3s -> detecting     141.5s -> ocr_done      156.7s -> typeset_done
 90.6s -> detected      151.6s -> inpainted
```

```
inpaint  : 11.4s · 2 vùng · "còn chữ ở 0 vùng" · KHÔNG OOM/SIGKILL/restart
translate: 0.7s  · engine=google_fast · fallback=False · token=***
typeset  : 0.28s · fit_ok=2 · overflow_warning=0 · font=Bangers
E14      : fallback_rectangle=2 · shape_derived=0
E15      : horizontal_ltr=2 · tt_ready=2      <- mã E15 chạy thật trên host
celery   : "Connected to redis://:**@vays-db-…" + "celery@70d910a961c2 ready."
```

`worker.trang_thai` vẫn kẹt `starting` — **không dùng làm bằng chứng**, đúng như thiết kế phép đo.

## P3a.2 — **Lưu trữ hosted là TẠM** ⛔

MCP VibeHost từ chối redeploy cùng mã:

```
redeploy_project(translation-api) -> NO_CHANGE: Không có thay đổi mới so với phiên bản hiện tại
```

Chủ dự án bấm "Triển khai lại" trên giao diện → **v22** (cùng mã `45c0af2`). Đo ngay sau đó:

| | Trước v22 | Sau v22 |
|---|---|---|
| `clean-image` | 200 · image/png · **69.486 byte** | **404** |
| `typeset-preview` | 200 · image/png · **98.060 byte** | **404** |
| CSDL `status` | `typeset_done` | **`typeset_done`** |
| `image_path` / `clean_image_path` | có | **vẫn có** |

```
{"detail":"Đường dẫn ảnh clean có trong DB nhưng file không còn:
           projects/7bb1b714…/pages/4b955242…_clean.png"}
```

Đường lưu thật là **`/app/storage`** (log: `preview typeset -> /app/storage/previews/…`), không
phải `/data/storage` như mặc định `config.py`. Đó là **lớp ghi của container**.

Chapter cũ `ddc7019b…` (28/08) cũng vậy: bản ghi còn, ảnh đã mất từ lâu.

⇒ **Điều kiện no-go §8.3.** Không chạy Pilot/UAT 10–20 trang.

## P3a.3 — CORS hosted sau mọi thao tác: không đổi

| Origin | ACAO |
|---|---|
| `https://translation.cmc-1.vibenode.matbao.ai` | khớp chính xác |
| `https://evil.example` · `http://localhost:5174` · `null` | *(không có)* |

Wildcard 0 · Credentials 0.

## P3a.4 — Hai ghi nhận phụ (P3)

- Route `clean-image` nói đúng **"có trong DB nhưng file không còn"**; route `typeset-preview`
  lại trả **"bước căn chữ chưa chạy xong"** — sai nguyên nhân, vì typeset đã chạy xong thật.
  Hai route không nhất quán về cách nói thật khi tệp biến mất.
- Log có `SecurityWarning: running the worker with superuser privileges` — celery chạy bằng root.

# ==================== P3d — Bỏ `abs_path()` làm hợp đồng đọc/ghi (2026-08-31) ====================

## P3d.1 — Bộ test sau refactor

```
801 passed, 6 skipped in 295.38s
```

Nền trước P3d: **779 passed**. Chênh **+22** là tệp mới `tests/test_storage_unit.py`.
**0 test bị xoá.** Hai unit test của bộ xuất (`test_xuat_lai_khong_tich_tu_file_rac`,
`test_doi_dinh_dang_thi_don_ket_qua_cu`) được **chuyển chỗ kiểm** chứ không bỏ: việc dọn bản
xuất cũ đã đi từ bộ xuất sang kho, nên bảo đảm đó nay kiểm ở `delete_prefix`.

## P3d.2 — Test mới: `tests/test_storage_unit.py` (22 test)

Hai nhóm dưới đây trước P3d **không có test nào**:

| Nhóm | Kiểm gì |
|---|---|
| `TestChanPathNguyHiem` (6) | path tuyệt đối / `..` / rỗng bị từ chối; `exists`/`stat`/`delete` trả "không có" thay vì ném; tệp **ngoài** kho không bị ghi đè |
| `TestGhiDocXoa` (7) | ghi–đọc nguyên văn; không sót tệp `.ghi-do-*`; **lỗi giữa chừng thì bản cũ còn nguyên**; `stat` đổi khi nội dung đổi; xoá idempotent |
| `TestLietKeVaDonTheoTienTo` (3) | liệt kê đệ quy có thứ tự; **`exports/p1` không xoá lan sang `exports/p10`**; không để lại thư mục rỗng |
| `TestVatChatHoa` (3) | `fetch_to` chép ra **ngoài** kho; `workspace()` được dọn **kể cả khi lỗi**; ghi ngược vào kho từ tệp cục bộ |

Ca đáng chú ý nhất — **`test_don_ban_cu_khong_dung_toi_hang_xom`**: `exports/p1` là tiền tố
**chuỗi** của `exports/p10`. Một hiện thực `delete_prefix` dựa trên `startswith` sẽ xoá nhầm
bản xuất của project khác mà không ai biết. Test này chặn đúng lỗi đó.

Và **`test_khong_ghi_duoc_ra_ngoai_goc_that`**: dựng một tệp thật ngoài kho, gọi
`save("../moi-nhu.txt", …)`, rồi khẳng định nội dung tệp đó **không đổi**. Trước P3d phép ghi
này thành công.

## P3d.3 — Lint: không thêm nợ

Đo trên **đúng bộ 9 tệp đã sửa**, so bản HEAD với bản sau sửa:

| | ruff |
|---|---|
| Trước (HEAD) | 100 lỗi |
| Sau P3d | **95 lỗi** |

Toàn repo 270 lỗi — có sẵn từ trước, P3d không đụng tới và cũng không làm tăng.

## P3d.4 — Một lỗi thật do refactor, bắt được bằng test

`anh_cuc_bo()` đặt ở scope module nhưng `get_storage` khi đó **chỉ được import cục bộ trong vài
hàm** ⇒ `NameError: name 'get_storage' is not defined`. Hệ quả: **mọi job detect thất bại**, và
vì detect là đầu chuỗi nên OCR/inpaint/typeset/export đổ theo — 40+ integration test đỏ.

Đáng ghi lại hai điều:

- Lỗi **không** lộ ra ở `import app.workers.tasks` (import sạch), cũng không ở 411 unit test.
  Chỉ integration test chạm tới đường chạy thật mới thấy.
- Job nuốt lỗi vào `error_log` rồi trả `{"status": "failed"}`, nên traceback **không** hiện ở
  log pytest. Phải in `repr(result)` ra mới thấy nguyên nhân. Đây là cái giá của việc bắt hết
  ngoại lệ ở tầng task — đúng cho vận hành, nhưng làm chẩn đoán chậm hơn một nhịp.

# ==================== P3e — Kho hiện vật trong Postgres (2026-08-31) ====================

## P3e.1 — Bộ test

```
823 passed, 6 skipped in 293.06s      (nền trước P3e: 801)
```

## P3e.2 — Cùng MỘT hợp đồng chạy trên CẢ HAI backend

`tests/test_storage_unit.py` đổi fixture `kho` thành parametrize `["local", "postgres"]` ⇒ **19
test hợp đồng chạy hai lượt** (40 test thay vì 22).

Đây là điểm mấu chốt của cả P3d+P3e: test riêng từng lớp thì "thay backend được" mãi mãi chỉ là
lời hứa. Chạy chung một bộ khẳng định mới là bằng chứng.

Tách riêng đúng những gì thật sự đặc thù:
- `kho_local` — kiểm tệp `.ghi-do-*` và thư mục rỗng (chỉ có nghĩa với hệ tệp)
- `TestRiengPostgres` (5) — trần kích thước, upsert không đẻ hàng trùng, `stat()` không kéo cột
  `data`, mốc phiên bản phân biệt được hai lượt ghi liên tiếp cùng cỡ, và `_` không bị LIKE hiểu nhầm

## P3e.3 — Test trả lời đúng câu hỏi khiến P3a/P3b bị chặn

`tests/test_storage_durability_integration.py` (4 test). Mô phỏng một lượt triển khai lại bằng
`shutil.rmtree(storage_root)` — đúng điều nền tảng làm với lớp ghi container (P3a đo trực tiếp).

| Test | Khẳng định | Kết quả |
|---|---|---|
| `..._postgres_song_sot_...` | xoá sạch đĩa xong, `GET /clean-image` vẫn **200** + đúng byte | ✅ |
| `..._local_mat_hien_vat_...` | cùng kịch bản, `local` trả **404** trong khi DB vẫn khai có ảnh | ✅ |
| `..._ETag_304_tren_kho_CSDL` | `If-None-Match` khớp ⇒ **304**, thân rỗng | ✅ |
| `..._doi_noi_dung_thi_ETag_doi_theo` | ghi đè cùng cỡ ⇒ ETag vẫn đổi | ✅ |

**Vì sao phải có test đối chứng (`local` mất):** không có nó thì không ai biết test đầu đang kiểm
gì thật. Và nó **khẳng định điều sai đang xảy ra trên host** — ngày nào nó bắt đầu đỏ, nghĩa là
nền tảng đã cấp được volume bền và có thể xét quay về `local`.

Thêm một khẳng định phụ trong test đầu: backend `postgres` **không ghi một byte MỚI nào ra đĩa**.
Có, nghĩa là còn một đường ghi lén chưa đi qua kho.

## P3e.4 — Hai lỗi bắt được trong lúc viết test

1. **Assert quá rộng.** Bản đầu của khẳng định "không ghi ra đĩa" soi **cả** thư mục kho dùng
   chung cả phiên, nên bắt phải tệp do test khác để lại ⇒ đỏ khi chạy cả bộ, xanh khi chạy riêng.
   Sửa: chụp ảnh thư mục trước/sau, chỉ so tệp **mới**. Bài học: khẳng định trên tài nguyên dùng
   chung phải là *delta*, không phải *trạng thái tuyệt đối*.
2. **Test xoá tài nguyên dùng chung.** Hai test `rmtree` thư mục kho của cả phiên; với
   pytest-randomly thì đó là quả mìn cho test chạy sau. Thêm fixture `autouse` dựng lại thư mục
   sau mỗi test.

# ==================== P3f — Đối chiếu bản ghi ↔ hiện vật (2026-08-31) ====================

```
831 passed, 6 skipped      (nền trước P3f: 823)
```

`tests/test_reconcile_integration.py` — 8 test. Hai cái quan trọng nhất **không** kiểm việc sửa:

| Test | Vì sao nó là cái gắt nhất |
|---|---|
| `test_che_do_chi_dem_KHONG_ghi_mot_chu_nao` | Công cụ sửa dữ liệu mà lỡ ghi trong lúc người ta tưởng nó chỉ đang đếm thì **tệ hơn hẳn** việc không có công cụ nào |
| `test_khong_dung_toi_trang_con_du_hien_vat` | Trang lành lặn phải được để yên — sửa nhầm là hỏng thứ đang tốt |

Còn lại: lùi đúng mốc theo bằng chứng còn lại (3 ca), mất riêng ảnh xem thử thì **không** xoá lây
ảnh clean, lần xuất mất file bị hạ `failed`, và idempotent (chạy lần hai ra toàn số 0).

`test_png_single_la_THU_MUC_khong_bi_ket_oan` — `exists()` luôn False với thư mục ở cả hai
backend, nên nếu chỉ hỏi `exists()` thì **mọi** lần xuất `png_single` bị kết oan là đã mất file.

# ==================== P3g — Range + đọc lười + đo độ trễ (2026-08-31) ====================

```
856 passed, 6 skipped      (nền trước P3g: 832)
```
Ruff trên 2 tệp đã sửa: **84 → 83**.

## P3g.1 — Hai test đo BYTE THẬT SỰ kéo về từ CSDL

Không có phép đếm này thì "đọc lười" chỉ là một khẳng định trong docstring:

| Test | Khẳng định |
|---|---|
| `test_doc_dau_tep_KHONG_keo_ca_hien_vat_ve` | đọc **100 byte đầu** của hiện vật **2MB** ⇒ tổng byte kéo về **≤ 512KB**, **≤ 2 lượt** |
| `test_doc_het_tep_thi_chia_thanh_nhieu_luot` | đọc hết 2MB ⇒ **≥ 4 lượt** (không phải một cú `SELECT data` khổng lồ) |

Hai cái này là một cặp: cái đầu chống "vẫn nạp cả hiện vật", cái sau chống việc lách bằng cách
đọc một phát rồi cache.

## P3g.2 — Hợp đồng `read_range` chạy trên CẢ HAI backend (+8 test ×2)

Đoạn giữa · từ đầu · tới hết · xin quá cuối (trả ít hơn, không ném) · đoạn rỗng · tua hai chiều ·
ghép nhiều khối ra đúng nguyên văn · **PIL mở được ảnh qua luồng** (ca này chặn đúng lỗi "luồng
không tua được").

## P3g.3 — Hành vi HTTP (10 test, `tests/test_range_integration.py`)

Test có ý nghĩa nhất là `test_noi_hai_doan_lai_ra_dung_tep_goc` — vì đó mới đúng là thứ người
dùng cần: tải dở rồi tải tiếp, ghép lại phải khớp. Các test còn lại kiểm 206/416/`If-Range`/304
và **cú pháp hỏng thì trả nguyên tệp chứ không nổ**.

## P3g.4 — Một hồi quy do chính tôi tạo, test hợp đồng bắt được

`open_read()` mới gọi `stat()` trước, mà `stat()` **cố ý nuốt** `UnsafeObjectPath` và trả `None`.
Hệ quả: path nguy hiểm hiện ra thành "không tìm thấy" — **che mất tín hiệu bảo mật**. Bắt bởi
`TestChanPathNguyHiem::test_moi_thao_tac_deu_tu_choi_chu_khong_chi_rieng_ham_kiem[postgres]`.

Bài học: một hàm "hỏi han" được phép nuốt lỗi (`exists`/`stat` trả về "không có"), nhưng hàm
"ra lệnh" (`open_read`) thì **không** — và đừng để hàm ra lệnh mượn hàm hỏi han làm cửa vào.

## P3g.5 — Đo độ trễ trên host: phép đo đầu SAI

Bản đầu dùng `curl` mỗi lượt một tiến trình ⇒ **bắt tay TLS lại từ đầu mỗi lượt**. Chi phí đó
(~130–220 ms) át hẳn phần việc máy chủ, đến mức hiệu số so với mốc nền ra **số âm** (−51,9 ms).

Đo lại bằng **một kết nối dùng lại**, bỏ 5 lượt khởi động nguội, n=40:

| Mục | p50 | p95 | min |
|---|---|---|---|
| MỐC NỀN `/healthz` | 3,4 ms | 4,0 | 3,0 |
| `clean-image` 304 (chỉ `stat`) | 6,8 ms | 13,6 | 6,2 |
| `clean-image` Range 8KB | 8,6 ms | 10,1 | 7,5 |
| `clean-image` đầy đủ (14 KB) | 9,6 ms | 14,4 | 8,2 |
| `typeset-preview` đầy đủ (16 KB) | 9,8 ms | 12,0 | 8,1 |

Trừ mốc nền: `stat()`+ETag ≈ **3,4 ms** · đọc+phát nguyên hiện vật ≈ **6,2 ms** · đoạn 8KB ≈ **5,2 ms**.

Bài học: **một phép đo không tách được chi phí thiết lập kết nối thì không đo cái nó tưởng nó đang
đo.** Dấu hiệu nhận ra ở đây rất rõ — kết quả ra số âm.

## P3g.6 — Đo trên hiện vật KÍCH THƯỚC THẬT (6,76 MB), n=25

14 KB không đại diện cho một trang truyện. Đẩy một trang 1400×2000 có nhiễu qua pipeline thật
trên host để LaMa sinh ra ảnh clean **6.763.787 byte**, rồi đo lại:

| Mục | p50 | p95 |
|---|---|---|
| MỐC NỀN `/healthz` | 3,7 ms | 8,3 |
| 304 (chỉ `stat`) | 6,8 ms | 7,4 |
| Range 8 KB (đầu tệp) | 8,6 ms | 19,0 |
| **Range 64 KB (GIỮA tệp, offset 3.000.000)** | **9,2 ms** | 10,7 |
| Đầy đủ 6,76 MB | 114,7 ms | 151,3 |

**Đây mới là phép đo chứng minh được thiết kế:**

- Đọc 64 KB ở **giữa** hiện vật 6,76 MB tốn **5,5 ms** trên mốc nền — gần y hệt đọc 8 KB ở
  **đầu** (4,8 ms), và bằng **1/20** chi phí đọc nguyên tệp (111 ms). Nếu Postgres phải bung cả
  hiện vật ra mới cắt được, đoạn giữa đã phải tốn cỡ 111 ms. ⇒ `SET STORAGE EXTERNAL` (P3e) thật
  sự cho **giải TOAST một phần**.
- `stat()` trên hiện vật 6,76 MB tốn **3,1 ms** — bằng đúng `stat()` trên hiện vật 14 KB. ⇒ tách
  `size_bytes` ra cột riêng đúng là cần: nó không hề chạm cột `data`.

# ==================== P3h — Chặn OOM worker (2026-08-31) ====================

```
867 passed, 6 skipped      (nền trước P3h: 856)      exit 0     <- tại commit 64c006a
869 passed, 6 skipped                                exit 0     <- sau lượt hậu kiểm (P3h.3/P3h.6)
```
Chạy lại lúc viết báo cáo (31/08 ~19:0x): **đúng 867/6**. Ruff trên các tệp đã sửa: **20 → 19**
(lượt hậu kiểm thêm 2 test, không thêm nợ lint: vẫn **19**).

## P3h.1 — Ba test của van xả: khẳng định đúng thứ dễ làm sai nhất

| Test | Khẳng định |
|---|---|
| `test_vuot_nguong_thi_nha_dung_thu_khong_can` | nhả `detector`, **giữ** `inpainter` + `ocr`. "Nhả model của chính bước đang chạy" là cách hỏng tệ nhất — nó biến một cơ chế cứu mạng thành một cơ chế tự bắn vào chân |
| `test_duoi_nguong_thi_giu_nguyen_cache` | chưa căng thì **không** được nhả. Van xả mà nổ suốt thì mỗi trang phải nạp lại LaMa ~197 MB + CTD ~91 MB — mất tốc độ vô ích |
| `test_khong_doc_duoc_thi_tra_None_chu_khong_phai_0` | `None` = *không đo được*, `0` = *đo được và bằng 0*. Gộp hai thứ đó là cách nhanh nhất để có một biểu đồ nói dối |
| `test_nguong_0_thi_khong_bao_gio_nha` | `nguong_mb <= 0` ⇒ tắt hẳn cơ chế (máy dev + test) |
| `test_nha_khong_no_khi_chua_nap_model_nao` | gọi van xả lúc chưa nạp model nào thì không nổ, trả `[]` |

## P3h.2 — Đo đỉnh bộ nhớ khi trộn (`tracemalloc`, cùng seed)

| Cỡ trang | Một biểu thức | Theo dải 256 dòng | Giảm | Giống từng byte |
|---|---|---|---|---|
| 1200×1660 (đúng cỡ trang pilot) | **71,7 MB** | **14,6 MB** | **80 %** | ✅ |
| 1400×2000 (cỡ trang M4) | **100,8 MB** | **18,5 MB** | **82 %** | ✅ |

Dòng thứ hai là điểm đo thêm lúc viết báo cáo, và nó nói cái mà một dòng không nói được: **cách cũ
leo theo diện tích trang, cách mới gần như đứng yên.** Một phép đo đơn lẻ không phân biệt được
"nhỏ hơn" với "không phụ thuộc cỡ".

## P3h.3 — ⚠️ Hai test phần trộn KHÔNG gọi mã sản xuất (pass yếu) — **đã đóng**

Phải ghi ra, vì đọc lướt thì hai test này trông như đã khoá phần trộn:

| Test | Nó thật sự chứng minh gì |
|---|---|
| `test_ket_qua_giong_het_cach_lam_mot_biểu_thuc` | **chép lại** vòng lặp trộn vào trong test rồi so với công thức cũ. Vòng lặp thật nằm **inline trong `LamaInpainter.inpaint()`** (`lama.py:238`), test **không gọi tới**. ⇒ chứng minh *thuật toán* tương đương, **không** chứng minh *mã đang chạy* làm đúng thuật toán đó |
| `test_ngoai_mask_giu_nguyen_anh_goc` | **không đụng đường theo dải một chút nào** — tính bản một-biểu-thức rồi assert trên chính nó. Với P3h đây là **pass rỗng**, đúng nghĩa đã dùng cho Run C của E15 |

✅ **ĐÃ ĐÓNG cùng ngày.** Tách `_tron_theo_dai(rgb, pred, mask)` trong `lama.py`; `inpaint()` và
test **gọi chung một hàm**. Bộ test phần trộn: **7 test** (4 tương đương từng byte · 2 đo đỉnh bộ
nhớ · 1 bất biến M4 — nay chạy trên chính hàm sản xuất).

*Bài học chung: test so hai bản cài đặt chỉ có giá trị khi MỘT trong hai bản là bản đang chạy thật.*

## P3h.6 — Hai test ĐO bộ nhớ (thay cho một câu trong docstring)

| Test | Khẳng định | Đo được |
|---|---|---|
| `test_re_hon_han_cach_viet_mot_bieu_thuc` | đỉnh cách mới **< 40 %** cách cũ (1400×2000) | **18 %** |
| `test_dinh_bo_nho_KHONG_leo_theo_chieu_cao_trang` | gấp đôi chiều cao ⇒ cách mới **< 1,5×**, và **đối chứng** bắt mốc cũ phải leo **> 1,8×** | mới **1,25×** · cũ **2,00×** |

Cái thứ hai mới đúng trọng tâm: điều đáng giá không phải "nhỏ hơn" mà là **không phụ thuộc cỡ
trang**. Assert đối chứng có mặt để nếu mốc cũ cũng đứng yên thì test phải **đỏ** — một phép đo
không phân biệt được hai giả thuyết thì không phải phép đo.

| Cỡ trang | Cách cũ | Theo dải | Tỉ lệ | Giống từng byte |
|---|---|---|---|---|
| 1400×800 | 40,3 MB | 13,4 MB | 0,33 | ✅ |
| 1400×1600 | 80,6 MB | 16,8 MB | 0,21 | ✅ |
| 1200×1660 | 71,7 MB | 14,6 MB | 0,20 | ✅ |
| 1400×2000 | 100,8 MB | 18,5 MB | 0,18 | ✅ |

### Mốc đối chiếu đầu tiên tôi viết đã SAI — và nó sai theo hướng có lợi cho mình

Tôi chép mã cũ "cho gọn" thành một biểu thức liền, trong khi mã cũ có gán tên `blended` cho mảng
trung gian. Chỉ khác một **tên biến**, nhưng tên đó giữ tham chiếu nên mảng 33,6 MB còn sống trong
lúc numpy dựng mảng kế tiếp:

```
1400x2000, cách cũ:  có biến `blended`         -> 100,8 MB
                     viết liền một biểu thức   ->  67,2 MB
```

⇒ bản "gọn" làm mốc đối chiếu **dễ hơn thực tế 1,5 lần**. Đã sửa để chép đúng mã cũ.

*Bài học: mốc đối chiếu phải chép NGUYÊN mã cũ, kể cả chi tiết trông như phong cách viết. Trong
numpy, một cái tên biến là một tham chiếu, và một tham chiếu là một mảng chưa được giải phóng.*

## P3h.4 — Live Verification trên host: ⛔ KHÔNG CHẠY ĐƯỢC (31/08 ~19:00–19:10)

| Kiểm | Kết quả |
|---|---|
| `GET translation-api…/healthz` | không phản hồi trong **45 s** |
| `GET translation…/` (web tĩnh, 0,6 CPU, không dính AI) | không phản hồi trong **45 s** |
| TCP `203.171.31.200:443` | **kết nối được** |
| Bắt tay TLS | **không hoàn tất** — treo sau `Client hello` |
| Dashboard VibeHost | cả hai website báo **`online`** (api v27 · web v13) |
| `get_runtime_logs` (api + web) | `available: false — wings_error` |
| Đối chứng lối ra internet | `google.com` **200** · `factory.matbao.ai` **307** |

Hai website khác nhau, cùng node `cmc-1`, chết cùng lúc, kèm `wings_error` ⇒ **tầng nền tảng**.
`status: online` trên dashboard **không phải bằng chứng đang phục vụ** — thêm một lần nữa.

⇒ **Chưa** có: RSS thật trên host · pilot 6 trang chạy lại · xác nhận hết `exit 137`.

## P3h.5 — Một lỗi của chính tôi trong lúc sửa

Phép thay chuỗi thêm dòng `import` **không đặt assert** ⇒ âm thầm không khớp ⇒ 20 test đỏ với
thông báo **lạc đề** (`ValueError` về UUID). *Mọi phép thay chuỗi phải có assert "đã thay được",
nếu không thì lần hỏng đầu tiên hiện ra ở rất xa chỗ gây lỗi.*

# ==================== E17 — gợi ý thuật ngữ & xưng hô (2026-09-01) ====================

```
backend   913 passed, 6 skipped     exit 0     (nền trước E17: 869)
          +44 test: 28 unit (tests/test_e17_ungvien_unit.py) + 16 integration
frontend  44 passed  (bộ consistency: 29 cũ + 15 mới)
```
Ruff trên các tệp MỚI của E17: **sạch**. Migration `0011_e17` chạy lên/xuống được (bộ test dựng
lại schema từ đầu mỗi lượt).

## E17.1 — Ba lỗi THẬT bắt được trong lúc viết test

| Lỗi | Nếu không bắt được thì sao |
|---|---|
| **`OCRStatus.done` không tồn tại** (enum thật: `pending·ok·needs_manual`) | `AttributeError` ngay lượt gọi API đầu tiên |
| **Đếm hai lần**: `ペッパーさん` khớp CẢ luật hậu tố lẫn luật katakana | Con số "xuất hiện 4 lần" hiện cho người dùng trong khi sự thật là 2 — mà đó đúng là con số họ dựa vào để duyệt |
| **Luật tiếng Anh vứt bằng chứng thật**: bỏ hẳn từ đứng đầu câu | "Pepper" xuất hiện 2 lần chỉ đếm được 1 ⇒ rơi dưới ngưỡng lặp ⇒ **biến mất khỏi danh sách** |

Lỗi thứ hai cùng họ với bẫy của P3f: *đếm số lần MÃ CHẠM VÀO sự vật thay vì đếm sự vật.* Sửa bằng
khử trùng theo `(vùng, vị trí)`, kèm hai test khoá:

- `test_hai_luat_cung_bat_mot_cho_thi_KHONG_dem_hai_lan` — 1 lần, và **vẫn giữ cả hai lý do**.
- `test_cung_mot_vung_xuat_hien_hai_lan_thi_dem_hai` — mặt kia, chống sửa quá tay thành khử trùng
  theo *từ* thay vì theo *vị trí*.

Lỗi thứ ba đẻ ra một cặp test đối nhau, và cặp này mới là phần đáng đọc:

```
"I met Pepper today. Pepper was tired."   -> Pepper: 2 lần   (đã chứng minh ở giữa câu)
"Pepper was tired. Pepper slept."         -> KHÔNG có gì     (chưa từng có bằng chứng)
```

## E17.2 — Test khoá LỜI HỨA, không phải khoá "chạy được"

| Test | Khoá điều gì |
|---|---|
| `test_KHONG_ghi_mot_dong_nao_vao_CSDL` | gọi cả 2 endpoint ⇒ `glossary_entry` + `character_voice_profile` vẫn **0 hàng** |
| `test_LOAI_dong_nhac_lai_mot_ten_KHONG_co_trong_danh_sach` | model trả "Naruto Uzumaki" cho chapter Pepper&Carrot ⇒ **loại + đếm vào `dropped_count`** |
| `test_cong_doi_chieu_loai_muc_bia_va_khong_tao_thuat_ngu` | cùng ca đó chạy qua worker thật; `glossary_entry` vẫn 0 hàng |
| `test_khong_co_ung_vien_thi_KHONG_goi_mo_hinh` | `build_translator` bị thay bằng hàm **ném lỗi** — gọi tới là đỏ |
| `test_model_noi_khong_biet_thi_khong_tinh_la_bia` | `?` là câu trả lời trung thực, không phải bịa |
| `test_mo_hinh_hong_thi_ghi_that_chu_khong_tra_goi_y_rong` | 429 ⇒ `failed` + `suggestions = null`, **không** trả `[]` như thể đã hỏi xong |
| `test_toan_chu_hoa_KHONG_duoc_tra_ve_moi_tu` | bẫy TOÀN CHỮ HOA của tiếng Anh |
| `test_chu_doc_chua_chac_thi_bi_bo_va_DEM_ra` | vùng `needs_manual` bị bỏ **nhưng có đếm và báo ra** |
| `test_ten_CHI_dung_dau_cau_thi_KHONG_tim_ra_duoc` | khoá đúng một GIỚI HẠN, để lần sau không ai tưởng là lỗi ngẫu nhiên |
| 3 test + 3 test giao diện cho trạng thái rỗng | "chưa đọc chữ" ≠ "không thấy" ≠ "đều đã có" |

Frontend có thêm `KHÔNG có nút duyệt hàng loạt` — quét cả DOM tìm nút "duyệt tất cả/thêm tất cả".
Nút đó mà xuất hiện thì toàn bộ ranh giới "máy tìm, người quyết" sụp trong một cú bấm.

## E17.3 — Hai lỗi của CHÍNH TEST, không phải của mã

Ghi ra để lần sau đọc lại không tưởng mã từng sai:

1. Test khẳng định `"PEPPER" in kho` trong khi khoá tiếng Anh **đã hạ chữ thường** (`pepper`).
2. Hàm dựng dữ liệu đặt `region_id` **trùng nhau giữa hai lần gọi** ⇒ bộ khử trùng coi hai vùng
   khác nhau là một, và test đếm ra 1 thay vì 2. Vùng thật là UUID nên không dính.

*Bài học: fixture đặt id trùng là một cách âm thầm làm test nói dối — và nó nói dối theo hướng
tố cáo mã sản xuất, tốn đúng số thời gian của một lỗi thật.*

## E17.4 — Chưa có: bằng chứng loại "chạy thật"

⛔ Host `cmc-1` vẫn chết nên **chưa** chạy trên chapter thật, **chưa** đo độ trễ, và **chưa từng
gọi mô hình thật** cho tầng 3 (mới kiểm bằng mô hình giả). Ba việc bắt buộc trước khi coi E17 là
đóng nằm ở `REPORT_E17_TERM_CANDIDATES.md` §7.

# ========== P3i — cảnh báo thiếu thuật ngữ ở cổng xuất (2026-09-03) ==========

```
backend : 917 passed, 6 skipped
frontend: 245 passed (11 tệp)
build   : vite build sạch
```
*Lint không phải cổng phát hành đã cấu hình.*

## P3i.1 — Backend (2 test, `test_compliance_integration.py`)

| Test | Khẳng định |
|---|---|
| `test_chapter_chua_co_thuat_ngu_thi_dem_bang_0` | chapter mới ⇒ `glossary_approved_count == 0` |
| `test_chi_dem_thuat_ngu_DA_DUYET` | thêm thuật ngữ (nháp) ⇒ vẫn 0; **duyệt** ⇒ 1 |

Test thứ hai là cái đáng giá: chỉ mục **đã duyệt** mới thực sự được dùng khi rà soát, nên đếm cả
bản nháp sẽ khiến cảnh báo tắt trong khi rủi ro còn nguyên.

## P3i.2 — Frontend (4 test, `export-thuatngu.test.jsx`)

- chapter trống thuật ngữ ⇒ khối "Nhất quán thuật ngữ" **vẫn phải hiện** (trước đây nó biến mất)
- cảnh báo phải nêu **hậu quả** (`nghĩa đen`) chứ không chỉ nói "chưa có gì"
- phải có **ví dụ thật** (`Pepper` → `Hạt tiêu`) để người dùng nhận ra vấn đề
- đã có thuật ngữ duyệt ⇒ **không lải nhải** cảnh báo này nữa
- thuật ngữ trống **không được nuốt mất** các cảnh báo cũ (tràn khung vẫn hiện)

## P3i.3 — Kiểm chứng trên host

Cổng xuất giờ hiện **5 nhóm có nhãn riêng**: `CHẤT LƯỢNG BẢN ĐANG XUẤT` · **`NHẤT QUÁN THUẬT NGỮ`**
· `BỐ CỤC TRONG BONG BÓNG` · `HƯỚNG CHỮ` · checkbox M10.

⚠️ Hai bẫy trong chính phép kiểm của tôi, ghi lại để lần sau khỏi mất thời gian:
1. Modal **không mở** ở chapter đã xuất — đúng thiết kế (`acknowledged` ⇒ nhắc **một lần**). Phải
   kiểm trên chapter chưa xác nhận.
2. Tiêu đề nhóm bị CSS viết hoa (`NHẤT QUÁN THUẬT NGỮ`) nên phép tìm phân biệt hoa/thường **trượt**
   — suýt kết luận nhầm là thiếu nhãn nhóm.

## P3i.4 — §9.2 Responsive (Chromium thật, trang pilot thật)

| Kích thước | Tràn ngang | Điều khiển | Lỗi console |
|---|---|---|---|
| 360×800 · 768×1024 · 1280×900 · 1600×1100 | **0px** cả 4 | dùng được | **0** cả 4 |

Lớp phủ M7: **9 khung, 0 khung lệch ra ngoài ảnh** ở cả 360px và 1280px (ảnh 290×400 → 694×959).

# ========== P3j — khôi phục job mồ côi (2026-09-03) ==========

```
927 passed, 6 skipped   (nền trước P3j: 917)
```

`tests/test_hoi_phuc_integration.py` — 10 test. Bốn cái đáng kể nhất **không** kiểm việc dọn, mà
kiểm việc **không đụng vào cái không được đụng**:

| Test | Khẳng định |
|---|---|
| `test_KHONG_dung_toi_job_da_xong` | job `done`/`failed` là **lịch sử**; kiểm cả việc không ghi đè `error_log` cũ |
| `test_KHONG_lui_trang_o_trang_thai_ON_DINH` | `ocr_done` là mốc đã xong thật — lùi bừa là xoá công việc đã hoàn thành |
| `test_KHONG_tu_chay_lai` | không tự xếp lại việc, không đẻ job mới |
| `test_che_do_chi_dem_KHONG_ghi_gi` | cùng bài học P3f: chế độ khô không dựa vào tác dụng phụ của chế độ ướt |

Còn lại: lý do phải **đọc được** (kiểm có cả `"hết bộ nhớ"` lẫn `"KHÔNG mất"` — một mã lỗi trần
trụi thoả mãn người viết log, không thoả mãn người đang bị kẹt), trang kẹt `detecting` được lùi về
`queued`, idempotent, endpoint `404` đúng và sắp mới-nhất-trước.

# ========== P3k + P3l — ba việc tồn đọng sau pilot (2026-09-03) ==========

```
backend : 937 passed, 6 skipped   (nền: 927)
frontend: 250 passed              (nền: 245)
```

## Cấu hình broker (`test_broker_config_unit.py`, 4 test)

Khoá ràng buộc giữa **hai tệp không ai nhắc ai**: `visibility_timeout` (celery_app) và trần thời
lượng task (config + tasks.py). Nâng một trần task vượt `visibility_timeout` ⇒ Redis giao lại
task **trong khi nó vẫn chạy** ⇒ chạy trùng trên cùng một trang.

- phải đặt **tường minh** (sống nhờ mặc định thư viện là con số không ai chọn, không ai kiểm)
- phải **lớn hơn** trần cứng lớn nhất (930s)
- phải còn **biên ≥50%** — hết trần mềm rồi còn phải dọn dẹp, ghi CSDL, nhả model
- `acks_late` phải còn bật, nếu không thì mất luôn việc giao lại

## Giao diện "Vì sao?" (`lydodung.test.jsx`, 5 test)

| Test | Khẳng định |
|---|---|
| KHÔNG hỏi máy chủ cho tới khi bấm | không thêm gánh vào vòng poll 5 giây |
| bấm rồi nói rõ BƯỚC NÀO + LÝ DO | không chỉ "có gì đó hỏng" |
| không có job hỏng ⇒ nói thẳng "đang chờ tới lượt" | im lặng cũng là một câu trả lời tồi |
| hỏi máy chủ hỏng ⇒ nói ra | **không** giả vờ là "không có gì hỏng" |
| bấm nhiều lần chỉ hỏi một lần | |

## E17 (`test_e17_ungvien_unit.py`, +6 test)

Dương tính giả: `"of"` sau "King" từng thành `character_name`. Test dùng **`"amongst"`** — một từ
chưa từng có trong danh sách chặn — để chứng minh luật bắt theo **cấu trúc** (chữ thường) chứ
không theo danh sách từ. Kèm test giữ dương tính thật (`Sir Pepper` vẫn ra `Pepper`).

`TestCoTinhKHONGBatTenODauCau` ghim một đánh đổi **có chủ ý** theo hai chiều: `Cayenne` (tên thật,
một lần, đầu câu) không lọt vào — nhưng `Wonderful`/`Terrible` cũng không. Nới một chiều là hỏng
chiều kia.

# ========== P3m — worker tự báo RSS của chính nó (2026-09-04) ==========

`/healthz` chạy trong tiến trình **API**, còn thứ bị OOM killer giết là tiến trình **worker**.
Trước P3m endpoint chỉ có một trường `rss_mb` (của API) và ai nhìn cũng tưởng đó là số của
worker — **đúng về kỹ thuật, sai về câu hỏi người ta đang hỏi**.

Nay: worker tự ghi RSS ra tệp riêng (`WORKER_RSS_FILE`, ghi nguyên tử temp+replace), `/healthz`
đọc lên thành `worker.rss_mb` kèm `rss_luc`. Giữ `rss_mb` cũ trỏ vào số của API để không phá thứ
đang đọc nó, và thêm `rss_api_mb` đặt tên cho đúng.

3 test: đọc lại được kèm mốc thời gian · ghi hỏng **không làm chết job** · không đo được thì
**không ghi** (không bịa số 0).

## ⚠️ Một báo động giả do chính phép đo của tôi

Lượt chạy sau P3m báo **"11 failed, 8 errors"**, tưởng như P3m phá vỡ thứ gì. Chạy riêng từng tệp
thì **xanh**. Chạy `-x` thì đi tới **hơn 91% không một lỗi nào** rồi bị `timeout` cắt.

Nguyên nhân: tôi để **ba lượt pytest chạy song song**, tất cả dùng chung một Postgres test ở
cổng 5433 — chúng migrate và xoá dữ liệu của nhau. Dọn hết tiến trình lạc rồi chạy đúng một lượt:
**exit 0, toàn bộ xanh.**

**Bài học vận hành:** bộ test này dùng **một** CSDL dùng chung, nên **không được chạy hai lượt
cùng lúc**. Triệu chứng khi vi phạm rất dễ đánh lừa: lỗi ở những tệp không liên quan, và "ERROR at
setup" thay vì assert hỏng.

# ========== A1 — cổng khoá truy cập (2026-09-04) ==========

```
backend : exit 0, toàn bộ xanh   (+11 test mới)
frontend: 258 passed             (nền: 251)
```

Đo trước khi làm, trên bản chạy thật: **65 thao tác API, 100% không cần xác thực, 31 ghi/xoá**.

## Bốn test đáng kể nhất — không kiểm việc CHẶN, mà kiểm việc chặn CHO ĐÚNG CHỖ

| Test | Vì sao |
|---|---|
| `test_moi_endpoint_v1_deu_co_cong` | quét **toàn bộ** route `/api/v1` — gắn cổng ở tầng router là để không sót, và đây là bằng chứng |
| `test_co_dang_kiem_that_chu_khong_phai_danh_sach_rong` | chống chính test trên tự lừa mình: "không có gì thiếu" trên danh sách rỗng thì luôn xanh |
| `test_thieu_khoa_va_khoa_sai_bao_Y_HET_nhau` | nói ra khác biệt là xác nhận cho người dò biết họ đã đoán đúng định dạng |
| `TestDuongSONG_phai_mo` | `/` và `/healthz` phải mở — khoá lại là tự làm hỏng deploy của chính mình |

## Frontend (7 test)

Lưu/đọc/xoá khoá · **các lỗi khác KHÔNG bị nhầm thành "thiếu khoá"** (nhầm 404/500 sẽ bắt người
dùng nhập lại một khoá vốn đang đúng) · có khoá thì mọi lời gọi mang `X-API-Key` · không có khoá
thì **không gửi header rỗng**.

# ========== E17b — đối chiếu CSDL nhân vật AniList (2026-09-04) ==========

```
backend : exit 0   (+14 unit +4 endpoint)
frontend: 265 passed (nền 259)   (+6)
```

Nhóm test đáng kể nhất **không** kiểm việc khớp, mà kiểm việc **không khớp bừa và không nói dối**:

| Test | Khẳng định |
|---|---|
| `test_nhan_vat_KHONG_co_trong_chapter_bi_loai_thang` | cổng đối chiếu hoạt động, và `bo_qua` được **đếm** chứ không nuốt |
| `test_ten_qua_ngan_khong_duoc_dung_lam_manh_ghep` | tách `D` từ `Monkey D Luffy` rồi khớp mọi chữ `D` là nhận bừa |
| `test_KHONG_thay_danh_xung_cua_chapter_bang_dang_cua_CSDL` | thay là sửa dữ liệu người dùng bằng dữ liệu người khác |
| `test_moi_danh_xung_chi_khop_MOT_lan` + `test_thu_tu_ket_qua_theo_CHAPTER` | kết quả phải **tất định**, không phụ thuộc thứ tự CSDL trả |
| 3 test `TestNoiThatKhiHong` | *"không tìm thấy truyện"*, *"không kết nối được"*, *"bị giới hạn nhịp"* phải là **ba câu khác nhau** |

`doi_chieu()` tách khỏi phần gọi mạng nên 11/14 test chạy **không chạm internet** — đúng/sai không
phụ thuộc một dịch vụ ngoài có thể sập bất cứ lúc nào.

# ========== B1 — tài khoản thật, chapter có chủ (2026-09-04) ==========

```
backend : exit 0   982 test  (+5 dò quyền, +6 cổng khoá viết lại)
frontend: 283 passed (nền 265)   (+18)
```

## Test đáng kể nhất: dò chéo tài khoản, tự sinh từ bảng route

`tests/test_quyen_cheo_tai_khoan.py` không liệt kê tay endpoint nào cả — nó đọc `app.openapi()`
rồi tự dựng phép thử. Endpoint thêm về sau **tự động bị dò**, không ai phải nhớ cập nhật gì.

Nhưng điều quan trọng hơn là cách nó **tự chứng minh mình không rỗng nghĩa**. Một test dò quyền
kiểu ngây thơ sẽ gửi id bịa, nhận `404`, rồi báo xanh — mà chẳng chứng minh được gì. Nên mỗi
đường dẫn được gọi **hai lần**, bằng A (chủ thật) và bằng B:

| Kết quả | Kết luận |
|---|---|
| A 2xx, B không 2xx | **chứng minh được** |
| A 4xx nghiệp vụ (409/422), B 404 | **chứng minh được** — A vào tới thân hàm, B bị chặn trước |
| B 2xx | **LỖ HỔNG** ⇒ đỏ |
| A cũng không vào được | **rỗng nghĩa** ⇒ đỏ, không cho lẫn vào phần xanh |

Kết quả cuối: **63 endpoint chứng minh được, 0 rỗng nghĩa, 0 lỗ hổng.**

## Bốn lượt siết, mỗi lượt đóng một kiểu "xanh giả"

Lượt đầu chỉ chứng minh được 44/63. 19 cái còn lại xanh mà vô nghĩa — và nếu chỉ nhìn màu test
thì đã tưởng xong từ lượt một.

| Lượt | Chứng minh | Rỗng nghĩa | Nguyên nhân đã tìm ra |
|---|---|---|---|
| 1 | 44 | 19 | — |
| 2 | 58 | 5 | Gửi `{}` làm thân request ⇒ **FastAPI trả 422 TRƯỚC khi handler chạy**, nên kiểm quyền chưa từng được gọi. Sinh thân hợp khuôn từ chính OpenAPI |
| 3 | 62 | 1 | Ba đường phục vụ file (ảnh clean, preview, file xuất) — A cũng 404 vì kho trống. Phải tạo hiện vật **thật**; và `POST /pages` nhận multipart chứ không phải JSON |
| 4 | **63** | **0** | `Literal["rules"]` của Pydantic ra `const` chứ không phải `enum` ⇒ bộ sinh gửi `null` ⇒ 422 |

Điều kiện cuối cùng đã siết thành `assert not rong_nghia`: thêm endpoint mà phép dò không chạm
tới được ⇒ **đỏ**, và người thêm phải chọn dựng thêm dữ liệu hoặc ghi vào `MIEN_TRU` **kèm lý do**.

## Ba lỗi thật do chính bộ test lôi ra

1. **`_get_project_or_404` được định nghĩa HAI lần**, nội dung giống hệt (dòng 162 và 988).
   Python lấy bản sau. Gắn kiểm quyền nhầm bản thì kiểm **không chạy chút nào** mà không có
   dấu hiệu gì. Đã gộp còn một.
2. **`get_export_warnings` gọi thẳng hàm của endpoint khác.** Khi gọi trực tiếp chứ không qua
   FastAPI, tham số `Depends` **không được giải** — nó vào hàm dưới dạng object thô và kiểm
   quyền nổ `AttributeError` thay vì trả 404.
3. **`test_migration.py` chạy `downgrade base` trên chính CSDL test**, tức là **xoá bảng
   `nguoi_dung`**. Tài khoản test tạo một lần cho cả lượt chạy nên mọi test xếp sau nó nhận 401.
   Triệu chứng: `test_range_integration` và `test_typeset_task_integration` **xanh khi chạy
   riêng, đỏ khi chạy chung** — đúng kiểu lỗi dễ đổ nhầm cho "chạy song song trên chung Postgres".
   Sửa bằng fixture tự dựng lại tài khoản khi thiếu (băm scrypt vẫn chỉ chạy một lần).

## Bốn test của cổng khoá slice A phải viết lại — và vì sao không chỉ "sửa cho xanh"

Slice B cố ý thay hợp đồng của slice A, nên 4 test cũ đỏ là **đúng**. Nhưng đổi chúng theo cho
xanh sẽ đánh mất điều cần chứng minh, nên bộ mới khẳng định slice B **mạnh hơn** chứ không phải
đổi ngang:

| Test | Khẳng định |
|---|---|
| `test_CHI_CO_KHOA_CHUNG_thi_KHONG_doc_duoc_du_lieu` | cầm khoá chung không còn đọc được gì (trước đây đọc được mọi thứ) |
| `test_CHI_CO_KHOA_CHUNG_thi_KHONG_ghi_duoc` | và cũng không ghi được |
| `test_cong_khoa_tat_van_KHONG_mo_du_lieu_cho_nguoi_chua_dang_nhap` | tắt khoá chung ≠ mở toang |
| `test_dang_ky_van_duoc_khoa_chung_gac` | khoá chung vẫn giữ đúng nhiệm vụ còn lại |
| `test_moi_endpoint_v1_deu_doi_dang_nhap` | cổng router giờ là đăng nhập, kèm `MIEN_TRU` 4 mục **mỗi mục có lý do** |

## Giao diện

14 test mới. Ba cái đáng kể:

| Test | Khẳng định |
|---|---|
| `401 dạng CHUỖI cũng nhận ra` | đúng cái bẫy đã làm hỏng `laLoiThieuKhoa` ở slice A: App lưu lỗi bằng `setLoi(e.message)` nên biến `loi` là **chuỗi**, không phải `Error` |
| `đăng nhập sai thì KHÔNG lưu mã phiên rác vào máy` | lưu trước rồi mới thử là để lại rác cho lần mở sau |
| `máy chủ không phản hồi thì VẪN xoá mã ở máy` | không thì người dùng kẹt vĩnh viễn ở màn "đã đăng nhập" mà mọi lời gọi đều 401 |

# ========== F1 — font thiếu glyph & lỗi tự hiện (2026-09-04) ==========

```
backend : (điền sau khi lượt đầy đủ chạy xong)
frontend: 294 passed             (nền: 288)
```

Bối cảnh: **bug thật trên bản chạy**, không phải test tự nghĩ ra. Log worker cho thấy bước căn
chữ chết sau **0,034 giây** vì `MissingGlyph: font thiếu glyph cho '．'`.

## Đo trước khi viết một dòng test

Chạy chính phép kiểm sentinel của `fonts.py` trên **cả 7 font** trong whitelist:

| | Ký tự |
|---|---|
| **Thiếu ở cả 7 font** | `．，！？：；（）「」『』。、・〜～－ー‥` |
| **Có đủ ở cả 7 font** | `. , ! ? : ; ( ) " ' - ~ · — – … “ ” ‘ ’` |

Nhờ vậy bảng gấp dấu câu không có ký tự đích nào là phỏng đoán — mọi đích đều đã đo là vẽ được.

## Backend (37 test mới)

`test_typeset_dau_cau_toan_rong.py` — 32 test:

| Nhóm | Khẳng định |
|---|---|
| Gấp từng ký tự | 23 cặp `nguồn → đích`, kể cả `‥`→`..` (KHÔNG gộp thành `…` ba chấm) |
| Không lấn sân | kana/kanji và `ー` **không** bị đổi · dải katakana nửa rộng `ｱｲｳ` (U+FF61+) **không** bị gấp — gấp là ra chữ Latin bậy |
| Không mất việc cũ | vẫn đưa NFD về NFC (`ĐỪNG` không ra `ĐUNG`) |
| Tái hiện sự cố | chính chuỗi `Sakamoto－san．` phải căn được, và `坂本さん` **vẫn phải** ném lỗi |

`test_typeset_task_integration.py` — 5 test mới (chạy DB thật + render thật):

| Test | Khẳng định |
|---|---|
| `test_mot_vung_hong_thi_cac_vung_khac_van_can_xong` | job `done`, 1 vùng `font_missing_glyph`, 1 vùng căn được, trang sang `typeset_done` |
| `test_vung_hong_KHONG_bi_ghi_thanh_pending` | `wrapped_text` và `font_size` phải là `NULL` — không ghi chữ mà thực tế không vẽ được |
| `test_ca_trang_hong_thi_van_bao_hong_va_GIU_nguyen_trang_thai` | mọi vùng hỏng ⇒ job `failed`, trang **giữ** `translated` |
| `test_dau_cau_toan_rong_KHONG_con_lam_hong_gi` | `？` `．` trong bản dịch ⇒ 0 vùng hỏng, `wrapped_text` sạch |
| `test_vung_hong_vao_danh_sach_can_ra_soat` | mã `layout_font_missing_glyph` có mặt ở `/pages/{id}/quality` |

## Ba test CŨ phải sửa — và vì sao không chỉ "sửa cho xanh"

| Test | Vì sao đỏ | Xử lý |
|---|---|---|
| `test_nhat_ky_tuan_thu_khong_chua_noi_dung_export` | ghim **đúng tập cột** của bảng tuân thủ | Thêm `font_missing_count` vào danh sách — cột mới ở bảng này phải là quyết định có ý thức, nên giữ nguyên kiểu ghim cứng |
| `test_xem_truoc_dem_dung_so_trang` + 1 test nữa | so **nguyên body** của `export-preview` | Thêm field mới vào body kỳ vọng, và bổ sung một khẳng định mới: tràn khung **không** được đếm lẫn vào bong bóng trống |
| `status-presentation.test.js` | danh sách enum `canh_chu` lấy thẳng từ `docs/API.md` | Thêm `font_missing_glyph` — đây chính là tấm lưới bắt "backend thêm trạng thái mà giao diện không biết", nó đỏ là nó đang làm đúng việc |

## Một test tự nó đã sai — bắt được nhờ viết trước khi tin

Bản đầu của `test_truoc_khi_gap_font_that_su_thieu_glyph` chứng minh "font thiếu glyph" bằng cách
gọi `assert_can_render` — và **đỏ**, vì chính hàm đó nay đã gấp dấu câu trước khi kiểm. Test đang
hỏi cái hàm mình vừa sửa xem nó có sai không.

Đã đổi sang đọc thẳng bảng `cmap` của file font bằng `fontTools`: hỏi **font**, không hỏi code.

## Giao diện (6 test mới)

| Test | Khẳng định |
|---|---|
| `hiện BƯỚC nào hỏng và LÝ DO mà không cần bấm gì` | lý do hỏng không còn nằm sau một cái nút |
| `trang có việc hỏng thì KHÔNG được coi là "đang cập nhật…"` | đúng cái đã lấy mất 10 phút của người dùng thật |
| `không có việc nào hỏng thì giữ nguyên hành vi cũ` | chống sửa quá tay: trang đang chạy thật vẫn phải quay và vẫn có nút "Vì sao?" |
| `hỏi danh sách việc hỏng mà lỗi thì màn tiến độ vẫn chạy` | lớp giải thích hỏng không được kéo sập màn chính |
| 2 test đếm bong bóng trống | **không** gộp vào số vùng tràn khung |

## Bài học vận hành (lặp lại lần thứ hai)

Chạy **hai lượt pytest cùng lúc trên một CSDL** làm cả hai treo ở `downgrade base`: lượt này đợi
khoá của lượt kia. Lần này chạy lượt riêng bằng `TEST_DATABASE_URL=…/translation_test_f1` — 102
test unit chạy xong trong vài giây sau khi tách DB, trong khi lượt dùng chung đứng im 4 phút.
