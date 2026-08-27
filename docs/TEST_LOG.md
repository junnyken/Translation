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
