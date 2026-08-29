# ARCH.md — Translation (Phase MTE: Manga Translation Extension)

> Trạng thái: **M8 hoàn tất** — pipeline chạy trọn từ ảnh gốc tới file CBZ giao được
> (M1 contract · M2 khung chữ · M3 đọc chữ · M4 xoá chữ · M5 dịch · M6 canh chữ · M7 sửa tay ·
> M8 xuất chapter, M9 chạy cả chapter theo mẻ).

## 1. Bức tranh tổng thể

```
       upload ảnh                 job queue (Redis/Celery)
Client ──────────► FastAPI (api) ──────────────────────────► Worker(s)
                      │                                        │
                      │  SQLAlchemy 2.0 async                  │ M2 detect  (comic-text-detector)
                      ▼                                        │ M3 ocr     (manga-ocr / PaddleOCR)
                 Postgres (Supabase)  ◄──────────────────────► │ M4 inpaint (LaMa)
                      │                                        │ M5 translate (Google fast / LLM context)
                      ▼                                        │ M6 typeset (Pillow font-metrics)
              Storage ảnh (local volume ở M1)                  │ M8 export  (PNG/CBZ)
```

Quy tắc kiến trúc **giữ nguyên xuyên suốt Phase** (M1 chốt, M2–M10 không được vi phạm):

1. **Không nhúng code GPL** (BallonsTranslator / Koharu). Chỉ dùng model weight độc lập
   (comic-text-detector, manga-ocr, PaddleOCR, LaMa) qua interface riêng trong `app/services/interfaces.py`.
2. **Mỗi bước pipeline là service riêng**, test độc lập được, nối với nhau bằng job queue.
   Tuyệt đối không viết 1 hàm monolith chạy end-to-end.
3. **Evidence-first**: bước chưa chạy → field kết quả `NULL`; bước fail/confidence thấp →
   `detection_failed` / `low_confidence` / `needs_manual` / `overflow_warning`. Không bao giờ mặc định "done".
4. **Không xử lý AI đồng bộ trong HTTP request**. Endpoint kích hoạt AI trả `202 Accepted` + `job_id`.
5. **API versioned**: mọi route dưới `/api/v1/`.

## 2. Thành phần

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| API | FastAPI 0.115 + Pydantic v2 | Swagger tự sinh tại `/docs` |
| ORM | SQLAlchemy 2.0 (async, asyncpg) | Không trả ORM object ra API — luôn qua Pydantic schema |
| Migration | Alembic (driver sync `psycopg`) | Đã test 2 chiều `upgrade head` / `downgrade base` |
| DB | Postgres 16 (local) hoặc Supabase managed | Đổi bằng `DATABASE_URL`, không sửa code |
| Queue | Redis + Celery | M1 chỉ ghi record `Job`; task Celery thật bắt đầu ở M2 |
| Storage | Volume local (`LocalObjectStorage`) | Adapter Supabase Storage **chưa implement** — xem §6 (nợ kỹ thuật) |
| Detector (M2) | comic-text-detector qua ONNX Runtime (CPU) | Chỉ chạy trong worker; tiến trình API không nạp model |
| OCR (M3) | manga-ocr (`ja`) · PaddleOCR (`zh`/`en`) | Cùng worker; **image worker tách khỏi image api** (multi-stage) |
| Inpaint (M4) | LaMa bản finetune manga, qua ONNX Runtime (CPU) | Cùng worker; sinh ảnh clean thành **file mới**, không đụng ảnh gốc |
| Dịch (M5) | `google_fast` (miễn phí) · `llm_context` (Gemini) | Gọi API qua HTTPS, **không nạp model**; key chỉ đọc từ `.env` |
| Canh chữ (M6) | Pillow + font SIL OFL | Đo font metrics thật; **không nạp model**; font mount `FONT_DIR`, chỉ worker |
| Sửa tay (M7) | React 18 + Vite | Chỉ là bên tiêu thụ API; không đụng DB/Redis; chạy service riêng |
| Xuất chapter (M8) | `zipfile` builtin + renderer M6 | **Không thêm phụ thuộc**; không nạp model; chạy trong worker |

## 3. Data model (7 bảng chốt ở M1 + `ExportJob` ở M8 + `BatchRun`/`BatchItem` ở M9 + `ExportComplianceLog` ở M10 + `RegionQualityAssessment` ở E12)

```
Project 1─n Page 1─n TextRegion 1─1 OCRResult
                     │            1─1 TranslationResult
                     │            1─1 TypesetResult
            1─n Job
```

- `Project`: `source_lang(ja|zh|en)`, `target_lang(vi)`, `intended_use(personal|study|other)` —
  `intended_use` tạo sẵn từ M1 nên **M10 không phải migrate** — chỉ thêm phần khai báo ở giao diện (§11).
- `Page.status`: state machine chính, khai báo **đủ 10 giá trị ngay ở M1**
  (`queued → detecting → detected/detection_failed → ocr_done → inpainted/inpaint_needs_review →
  translated → typeset_done → ready_for_export`) để tránh `ALTER TYPE` enum nhiều lần trên Postgres.
  Cạnh hợp lệ khai báo trong `PAGE_STATUS_TRANSITIONS` (`app/models/enums.py`) + helper `assert_transition`.
- `TextRegion`: `bbox_x/y/w/h` (pixel, gốc trên-trái), `confidence` NULL cho tới M2,
  `overlap_suspect` (cờ của M2), `reading_order` NULL cho tới M5.
- 3 bảng kết quả (`OCRResult`, `TranslationResult`, `TypesetResult`) đều `unique(region_id)`
  → rerun job là **idempotent theo region**, không sinh bản ghi trùng.
- `Job`: `type(detect|ocr|inpaint|translate|typeset|export)` khai báo đủ enum cho cả Phase từ M1;
  `retry_count` có từ M1 và **M9 mới dùng tới** — chính sách thử lại thống nhất nằm ở §10.
- **Không tạo `APIKeyPool`** — ở M5 vì key chỉ nằm trong `.env`, và ở M9 vì đã đo được rằng xoay key
  trong cùng một project Gemini **không** tăng hạn mức (§8, §10). `ExportJob` thêm ở M8,
  `BatchRun`/`BatchItem` thêm ở M9 — đúng nguyên tắc chỉ tạo đủ cho mini-spec hiện tại.

## 4. Interface engine (contract cho M2–M6)

`app/services/interfaces.py` khai báo `BBox` + 5 Protocol: `IDetector.detect`, `IOCREngine.recognize`,
`IInpainter.inpaint`, `ITranslator.translate`, `ITypesetter.fit`.
Kèm 5 stub `Unimplemented*` — **ném `NotImplementedError` kèm tên mini-spec phụ trách**, không trả kết quả giả.
Implementation thật (M2–M6) phải giữ nguyên tên method để không phải sửa lại contract DB/API.

**M2 — `CTDDetector`:** implement đúng `IDetector.detect(image_path) -> list[BBox]`. Vì `BBox` không
có chỗ chứa confidence, M2 **bổ sung** `detect_regions()` trả `DetectedRegion(bbox, confidence, cls)`;
Protocol M1 giữ nguyên, không đổi tên method nào. Detector **không tự lọc** theo `conf_threshold` —
lọc/gắn cờ là việc của Celery task, để detector chỉ làm đúng 1 việc: trả kết quả thô.


## 5. Model weight (M2)

| Mục | Giá trị |
|---|---|
| Model | comic-text-detector (dmMaze) — YOLOv5 head + UNet mask + DBNet line |
| File dùng | `comic-text-detector.onnx` (~91 MB) |
| Nguồn tải | `https://huggingface.co/mayocream/comic-text-detector-onnx` (file `comic-text-detector.onnx`) |
| SHA-256 | `1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f` |
| License ghi trên HF card | `apache-2.0` |
| License repo gốc (dmMaze/comic-text-detector) | **GPL-3.0** |

**Xử lý mâu thuẫn license:** HF card của bản ONNX ghi `apache-2.0` nhưng repo gốc sinh ra weight này là
GPL-3.0 (bản convert SafeTensors `mayocream/comic-text-detector` cũng ghi GPL-3.0). Vì không chắc bản ONNX
được relicense hợp lệ, dự án **áp theo điều kiện chặt hơn (GPL-3.0)**:

- Dùng cho **mục đích cá nhân/nội bộ**, không phân phối lại file weight kèm sản phẩm.
- **Không** dùng cho SaaS thương mại nếu chưa xin phép nguồn gốc.
- **Không** copy code inference của repo gốc vào codebase — chỉ nạp weight qua `onnxruntime`;
  toàn bộ tiền/hậu xử lý (letterbox, giải mã YOLO, NMS, clamp bbox) do dự án tự viết trong
  `app/services/detect/`. Đây là ranh giới giữ đúng guardrail "không nhúng code GPL" của M1.

Weight **không commit vào git** (`.gitignore`: `models/`, `*.onnx`, `*.pt`). Cách lấy:

```bash
mkdir -p models
curl -L -o models/comic-text-detector.onnx \
  https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx
# docker-compose mount ./models -> /models (chỉ cho service worker, api không cần)
```

### Đường đi của bước detect

```
POST /pages  ──►  lưu ảnh + Job(detect, queued)  ──►  Celery (Redis)
                        │ 202 ngay, không chờ            │
                        ▼                                ▼
                    client polling                 worker: CTDDetector.detect_regions()
                    GET /jobs/{id}                    letterbox 1024 → ONNX → NMS → clamp
                                                        │
                                                        ▼
                                          xóa region cũ của page (idempotent)
                                          ghi TextRegion + confidence + overlap_suspect
                                          Page: queued → detecting → detected | detection_failed
```

Tham số điều chỉnh được qua `.env` (không hard-code): `CTD_CONF_THRESHOLD` (0.5 — dưới ngưỡng là
`low_confidence`, **vẫn lưu**), `CTD_RAW_MIN_CONF` (0.25 — sàn nhiễu trước NMS), `CTD_NMS_IOU` (0.45),
`CTD_OVERLAP_SUSPECT_RATIO` (0.8), `CTD_INPUT_SIZE` (1024), `DETECT_TIMEOUT_SECONDS`.


## 6. OCR engine (M3)

| source_lang | Engine | Confidence | Ghi chú |
|---|---|---|---|
| `ja` | manga-ocr 0.1.16 (`kha-white/manga-ocr-base`) | **không có** → `NULL` | ViT+BERT sinh chuỗi, thư viện chỉ trả text |
| `zh` | PaddleOCR 3.7 (`lang="ch"`) | có thật, theo dòng | trung bình các dòng trong 1 vùng |
| `en` | PaddleOCR 3.7 (`lang="en"`) | có thật, theo dòng | |

### `confidence = NULL` của manga-ocr KHÔNG phải bug

Đã kiểm **source thật** của manga-ocr 0.1.16: `MangaOcr.__call__` chạy `model.generate()` rồi decode
và **chỉ trả về chuỗi text** — không có điểm tin cậy nào để lấy. Thay vì bịa một con số (ví dụ 1.0
hay điểm proxy tự chế), M3 ghi `confidence = NULL` và dùng tiêu chí thay thế minh bạch:

- `raw_text` rỗng hoặc **không chứa ký tự có nghĩa** (chỉ dấu câu/khoảng trắng) → `needs_manual`.
- Ngược lại → `ok`, `confidence = NULL`.
- Với PaddleOCR (có confidence thật): thêm điều kiện `confidence < OCR_CONF_THRESHOLD` → `needs_manual`.

### Đường đi (nối tiếp M2)

```
detect xong (Page=detected) ──► tự tạo Job(type=ocr) + đẩy sang worker   [OCR_AUTO_CHAIN=true]
                                          │
                                          ▼
                     lấy TẤT CẢ TextRegion của page (kể cả low_confidence)
                     crop theo bbox (round toạ độ tuyệt đối, clamp trong ảnh)
                     1 lần nạp model → OCR lần lượt N vùng  (batch theo Page)
                     xóa OCRResult cũ của chính các region đó → ghi mới (idempotent)
                                          │
                                          ▼
                          Page: detected → ocr_done  ·  Job: done
             lỗi/timeout → Job=failed + error_log, Page GIỮ `detected` để còn retry
```

Region `low_confidence` từ M2 **vẫn được OCR** — detect yếu không đồng nghĩa OCR sẽ hỏng,
2 bước độc lập nhau về bằng chứng.

### Image worker tách khỏi image api

`backend/Dockerfile` có 2 stage: `base` (api — không có thư viện AI) và `worker` (base + torch CPU +
manga-ocr + PaddleOCR + paddlepaddle). Lý do: giữ API nhẹ và biến ranh giới "API không chạm model"
thành sự thật ở tầng image, không chỉ là quy ước.

**torch phải cài từ index CPU của PyTorch** (`--index-url https://download.pytorch.org/whl/cpu`):
bản trên PyPI kéo theo toàn bộ stack CUDA (`nvidia-*`, `cuda-toolkit`, `triton`) ~vài GB, vô dụng
trên máy chỉ có CPU. **PaddleOCR không tự kéo `paddlepaddle`** — phải khai tường minh trong
`requirements-worker.txt`, nếu không sẽ lỗi lúc chạy chứ không lỗi lúc cài.

Model OCR tải lúc chạy lần đầu (manga-ocr ~440MB từ HuggingFace, PaddleOCR ~20MB) và được cache
vào volume `model_cache` (`HF_HOME=/model-cache/hf`, `PADDLE_PDX_CACHE_HOME=/model-cache/paddle`)
— không tải lại mỗi lần khởi động container.


## 7. Model weight inpaint (M4)

| Mục | Giá trị |
|---|---|
| Model | LaMa finetune trên 300k ảnh manga/anime (`lama_large_512px`) |
| File dùng | `lama-manga-dynamic.onnx` (~197 MB) |
| Nguồn tải | `https://huggingface.co/ogkalu/lama-manga-onnx-dynamic` |
| SHA-256 | `de31ffa5ba26916b8ea35319f6c12151ff9654d4261bccf0583a69bb095315f9` |
| License bản ONNX | `apache-2.0` |
| License checkpoint gốc (`dreMaz/AnimeMangaInpainting`) | **`mit`** |
| Base model (`advimman/lama` big-lama) | code Apache-2.0; **weight gốc của big-lama là CC BY-NC-SA (phi thương mại)** |

**Xử lý license:** chuỗi bản quyền ở đây sạch hơn M2 — checkpoint manga (`lama_large_512px.ckpt`)
công bố theo **MIT**, bản ONNX theo Apache-2.0. Tuy vậy nó là bản finetune từ big-lama, mà weight
big-lama gốc mang giấy phép **phi thương mại**. Vì vậy dự án giữ nguyên lập trường thận trọng như M2:
dùng cho **cá nhân/nội bộ**, không phân phối lại weight, **không** dùng cho SaaS thương mại nếu chưa
kiểm tra lại chuỗi license với tác giả. Không copy code inference của repo gốc — chỉ nạp weight qua
`onnxruntime`, toàn bộ dựng mask / pad / ghép ảnh tự viết trong `app/services/inpaint/`.

Weight **không commit vào git**. Cách lấy:

```bash
curl -L -o models/lama-manga-dynamic.onnx \
  https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/main/lama-manga-dynamic.onnx
```

### Ràng buộc kỹ thuật đã đo thật

- Input: `image[b,3,h,w]` + `mask[b,1,h,w]` (0..1 float), output `inpainted[b,3,h,w]`
  **cùng kích thước ảnh vào** — không phải resize về 512 rồi phóng lại.
- **Cạnh ảnh phải chia hết 8**: `1401×2001` → `ONNXRuntimeError` ở node `Mul`;
  `1400×2000` → chạy bình thường. Vì vậy code **luôn pad** mép phải/dưới (mode `edge`) rồi cắt lại.
- Tốc độ: **54,3s/ảnh 1400×2000 trên CPU** (chưa tính bước kiểm chứng).

### Đường đi của bước xoá chữ

```
OCR xong (Page=ocr_done) ──► tự tạo Job(type=inpaint) + đẩy sang worker   [INPAINT_AUTO_CHAIN=true]
                                          │
                                          ▼
              kiểm điều kiện: page phải ocr_done, mọi region phải có OCRResult
              dựng mask từ TextRegion.bbox, nới ≤15% (INPAINT_DILATE_RATIO), clamp trong ảnh
              xoá ảnh clean CŨ (nếu có) → chạy LaMa → ghép: ngoài mask giữ nguyên pixel gốc
              lưu file MỚI <tên gốc>_clean.png  (ảnh gốc không bao giờ bị đụng)
                                          │
                                          ▼
              KIỂM CHỨNG: OCR lại đúng vùng vừa xoá trên ảnh clean
                 còn chữ  → Page = inpaint_needs_review
                 sạch     → Page = inpainted
              lỗi/timeout → Job=failed, Page GIỮ trạng thái cũ, không ghi clean_image_path
```

Vì sao kiểm chứng bằng OCR lại: đó là tiêu chí **khách quan, đo được**, thay cho đánh giá cảm tính
"nhìn có thấy artifact không". Nếu LaMa xoá hụt, OCR sẽ đọc lại được chữ và page bị đánh dấu cần review.

Tham số `.env`: `INPAINT_DILATE_RATIO` (0.08 — trần cứng 0.15 trong code), `INPAINT_TIMEOUT_SECONDS`
(riêng, không dùng chung với detect/OCR), `INPAINT_VERIFY_BY_OCR`, `INPAINT_ALLOW_OPENCV_FALLBACK`
(**mặc định false** — LaMa lỗi thì job fail, không lặng lẽ lùi về `cv2.inpaint` chất lượng kém).


## 8. Dịch (M5)

Hai đường **cố ý tách rời**, người dùng kiểm soát khi nào tốn tiền:

| Đường | Cách chạy | Chi phí | Điểm yếu |
|---|---|---|---|
| `google_fast` | dịch **từng dòng** qua endpoint Google Translate công khai | miễn phí | không có ngữ cảnh liên câu |
| `llm_context` | gộp **cả trang** thành 1 request Gemini, giữ mạch văn | tốn token | phụ thuộc quota/API key |

**Mặc định của pipeline tự chảy là `google_fast`** — hệ thống không bao giờ tự tiêu token của người
dùng khi họ chưa chọn. Muốn chất lượng cao thì gọi `POST /pages/{id}/retry-translate?engine=llm_context`
hoặc đổi `TRANSLATE_DEFAULT_ENGINE` trong `.env`.

### Chọn model — và cái bẫy "thinking" đốt token

Đo thật trên cùng 1 trang 6 dòng, cùng prompt:

| Model | thinking token | tổng token | thời gian |
|---|---|---|---|
| `gemini-3.6-flash` (không tắt thinking) | **938** | 1072 | 7,0s |
| `gemini-3-flash-preview` + `thinkingBudget=0` | 0 | 133 | 2,0s |
| **`gemini-3.1-flash-lite` + `thinkingBudget=0`** (mặc định) | **0** | **140** | **1,6s** |

Chất lượng dịch của 3 model trên mẫu này tương đương, nhưng để mặc định (không tắt thinking) thì
**đắt gấp ~7,7 lần và chậm gấp 4 lần**. Vì vậy:

- `LLM_THINKING_BUDGET=0` là **mặc định**, có test canh.
- Nếu model vẫn trả về `thoughtsTokenCount > 0` dù đã yêu cầu tắt, worker **ghi cảnh báo vào log**
  — để hoá đơn phình lên không diễn ra âm thầm.
- `token_cost` thật của mỗi trang được ghi vào DB (xem dưới).

`gemini-2.5-flash` — đúng model mà spec lấy làm ví dụ — **không dùng được nữa**:
`404 NOT_FOUND: "This model is no longer available to new users"`. Google trỏ sang `gemini-3.6-flash`.

### Rate limit: tính theo PROJECT, không theo key

Tài liệu chính thức của Gemini API **không còn công bố con số free-tier** (phải xem trong AI Studio),
và ghi rõ: *"Rate limits are applied per project, not per API key."*

⇒ **Xoay nhiều key trong CÙNG một project không tăng được hạn mức.** Cơ chế xoay key vẫn được
implement (và có test), nhưng chỉ thực sự có tác dụng khi các key thuộc **project khác nhau**.
Đây là điểm khác với giả định ban đầu của spec, ghi lại để không ai kỳ vọng sai.

### Chi phí token ghi vào đâu

`llm_context` gọi **1 request cho cả trang**, nên chi phí là của trang chứ không của từng vùng.
`TranslationResult.token_cost` được ghi **đúng 1 dòng đầu trang**, các dòng còn lại `NULL` —
cộng `token_cost` toàn bảng vẫn ra tổng chi phí thật, không bị nhân bản.

### Thứ tự đọc

`TextRegion.reading_order` để `NULL` từ M1; **M5 là bước điền cột này**. Thuật toán: gom bbox thành
các dải ngang (dải cao ≈ trung vị chiều cao bbox × 0,6 — để bubble lệch vài chục pixel vẫn tính cùng
hàng), sắp dải từ trên xuống, trong mỗi dải sắp theo hướng đọc:

- `ja` → **phải sang trái** (manga Nhật)
- `en`, `zh` → trái sang phải
- ép cứng được bằng `READING_DIRECTION_OVERRIDE=ltr|rtl`

Thứ tự này quyết định thứ tự dòng gửi cho LLM, nên sai ở đây là hỏng mạch văn cả trang.

### API key

Key **chỉ nằm trong `.env`** (`GEMINI_API_KEYS`, nhiều key ngăn cách bằng dấu phẩy). **Không** tạo bảng
`APIKeyPool` ở M5: spec §4A của M5 không liệt kê bảng này, và constraint 7 yêu cầu key chỉ ở `.env`/secrets
— đưa key vào Postgres sẽ cần mã hoá + xoay khoá, đó là việc của M9 nếu thật sự cần chia trạng thái
quota giữa nhiều worker. Có 3 guardrail test quét toàn bộ file được git track để chặn key lọt vào commit.

### Khi LLM chết

`llm_context` lỗi/hết quota → **tự lùi về `google_fast`**, mọi dòng của trang được đánh dấu
`status=fallback_used` và `Job.error_log` ghi lý do gốc. Không bao giờ trả bản dịch rỗng mà báo thành công.
Nếu model không trả về dòng nào đó, dòng ấy giữ `status=pending` (enum `TranslationStatus` chốt ở M1
không có `needs_manual`) — nghĩa là "chưa có bản dịch", không phải "đã xong".

## 10. Chạy cả mẻ (M9)

### Vì sao mẻ nằm trong Postgres chứ không trong Celery

Trạng thái mẻ nằm ở **2 bảng `batch_run` + `batch_item`**, không nằm trong result backend của Celery
và cũng không nằm trong bộ nhớ tiến trình. Lý do: worker bị khởi động lại (hoặc bị hệ điều hành giết
vì hết bộ nhớ — đã gặp thật ở M4) thì mọi thứ giữ trong bộ nhớ biến mất, còn tiến độ mẻ thì **phải**
đọc lại được. Redis ở M9 chỉ giữ **một** thứ: cửa sổ đếm nhịp gọi provider, sống 60 giây.

```
BatchRun 1─n BatchItem ──> Page          (ảnh chụp lúc tạo mẻ)
                      └──> Job.current_job_id  (việc đang/vừa chạy)
```

- `BatchItem` có `unique(batch_run_id, page_id)` — một trang không thể vào cùng mẻ hai lần.
- `page_order` là **ảnh chụp** `Page.order` lúc tạo mẻ; sắp lại trang về sau không làm đổi thứ tự
  của mẻ cũ, nên nhìn lại một mẻ đã chạy vẫn thấy đúng thứ tự lúc đó.
- `batch_run.completed_pages/failed_pages/blocked_pages` chỉ là **bộ đếm cho nhanh**; mỗi lần gộp
  đều đếm lại từ `batch_item`. Không có đường nào ghi thẳng vào bộ đếm.

### Không có task nào ngồi chờ

Bộ điều phối **không** dùng một task Celery giữ worker rồi hỏi vòng vòng cho tới khi các trang xong.
Với `--concurrency=1` thì task chờ ấy chiếm đúng cái worker duy nhất và mẻ khoá chết chính nó.
Thay vào đó: xếp việc rồi thoát; khi một bước kết thúc, task của bước đó gọi
`BatchOrchestrator.on_page_terminal(...)` — đẩy trang đi bước kế, hoặc kết thúc mục và đẩy trang sau.

Chỗ báo về nằm ở **một hàm duy nhất** `bao_ket_thuc_buoc()` trong `workers/tasks.py`; task của M2–M6
không biết gì về mẻ. Có guardrail test đếm bằng AST: mỗi task pipeline phải báo về ở **cả ba nhánh**
(xong / hết giờ / lỗi), còn việc thao tác tay (canh lại chữ, đọc lại vùng, dịch lại vùng) thì
**không được** báo về — chúng không bao giờ là bước của mẻ.

### Cổng nhịp gọi Gemini: Redis, không phải `rate_limit` của Celery

`Task.rate_limit` của Celery giới hạn theo **từng worker instance**. Hai worker cùng đặt 10 lượt/phút
là 20 lượt/phút đập vào nhà cung cấp — đúng thứ cần tránh. M9 dùng **cửa sổ trượt nguyên tử bằng Lua
trong Redis** (`services/batch/gate.py`): toàn bộ phép kiểm-rồi-ghi nằm trong một lệnh, nên 40 luồng
tranh nhau vẫn chỉ 5 lượt lọt qua (có test canh đúng con số này).

- Khoá Redis là **băm SHA-256 rút gọn** của định danh project provider — không bao giờ chứa API key.
- `LLM_PROJECT_RPM<=0` ⇒ tắt cổng.
- **Redis hỏng ⇒ cổng TỪ CHỐI**, không mở toang. Mở toang khi cổng hỏng là đập thẳng vào quota.
- Mất trạng thái cổng sau khi Redis khởi động lại chỉ nới thêm vài lượt gọi, **không** làm sai tiến
  độ mẻ — tiến độ luôn đọc từ `batch_item`.

### Thử lại: chỉ lỗi tạm thời, và có trần

`TransientErrorClassifier` chia lỗi làm 3 nhóm chứ không phải 2:

| Nhóm | Ví dụ | Xử lý |
|---|---|---|
| tạm thời | 429 quá nhịp, 408, 5xx, DNS/socket, mất kết nối Redis | thử lại tối đa `BATCH_MAX_RETRIES` lần |
| **hết quota** | 429 kèm `quota_exceeded`/`resource_exhausted`/`billing` | `blocked_quota`, **không** thử lại |
| vĩnh viễn | 400/401/403, thiếu font, thiếu model weight, mất ảnh gốc | hỏng ngay, **zero** retry |

Hết quota được tách riêng vì nó không thuộc nhóm nào: thử lại ngay thì vẫn hỏng (nên không phải
"tạm thời"), mà quota hồi là chạy được (nên không phải "vĩnh viễn"). Gemini trả **cùng mã 429** cho
cả quá-nhịp lẫn hết-quota, nên phải đọc thân phản hồi mới phân biệt được.

Lùi dần: `min(base × 2^n, cap)` rồi nhân nhiễu toàn phần. Nhiễu **tất định theo khoá** khi test
truyền `khoa_nhieu` — nhờ vậy test khẳng định được nhiễu có thật mà vẫn lặp lại y hệt.

Cấu hình (`.env.example`): `BATCH_MAX_CONCURRENT_PAGES=1`, `BATCH_MAX_RETRIES=3`,
`BATCH_RETRY_BACKOFF_BASE_SECONDS=2`, `BATCH_RETRY_BACKOFF_MAX_SECONDS=120`, `BATCH_RETRY_JITTER=true`,
`LLM_PROJECT_RPM=10`, `LLM_QUOTA_MODE=redis_sliding_window`, `BATCH_STALE_ITEM_SECONDS=2400`.
**Đây là số dev.** Hạn mức thật của nhà cung cấp phải đo rồi ghi vào `TEST_LOG.md` trước khi chốt cho
chạy thật — xem `docs/REPORT_M9.md` §Remaining Limits.

### Mục mồ côi: cái bẫy làm mẻ đứng im mà không ai biết

Worker chết giữa chừng ⇒ task biến mất nhưng `batch_item` vẫn nằm ở `running` **vĩnh viễn**, và
`resume` thì chỉ nhận `failed`/`blocked_quota` nên bấm "chạy lại" cũng không cứu được.
`thu_hoi_muc_mo_coi()` đưa mục `running` quá `BATCH_STALE_ITEM_SECONDS` về `pending`, và đánh hỏng
**có ghi lý do** những trang kẹt ở trạng thái tạm (`detecting`) quá lâu — thà báo hỏng còn hơn để mẻ
treo. `resume` không kèm danh sách mục sẽ tự chạy bước thu hồi này trước.

### Mẻ không tự xuất chapter

Xuất là hành động **có chủ ý** của người vận hành ở M8: tự xuất sau khi dịch xong có thể phát hành
bản còn `overflow_warning`. Giao diện chỉ dẫn người dùng sang bảng xuất sau khi mẻ xong. Có guardrail
test cấm `orchestrator.py`/`dispatch.py` nhắc tới `ExportJob`/`run_export_job`.

## 11. Cổng khai báo & cảnh báo trước khi giao file (M10)

### Cảnh báo, không chặn

Đây là công cụ cá nhân, không phải hệ thống kiểm duyệt. Chặn cứng chỉ khiến người dùng đi đường
vòng mà chẳng bảo vệ được ai. Nhưng cũng **không im lặng cho qua**: trước khi tải file về, người
dùng phải nhìn thấy đúng số vùng còn lỗi, phải **tự tick** xác nhận, và việc tick đó được ghi lại.

Ranh giới rõ ràng:

| Tầng | Vai trò |
|---|---|
| Giao diện | **Chặn**: nút xuất mờ tới khi tick ô xác nhận |
| Máy chủ | **Ghi nhận**, không cấm — `POST /export-jobs/{id}/acknowledge` chỉ ghi bằng chứng |

Có guardrail test canh cả hai đầu: một test khẳng định nút trong hộp thoại có `disabled={!daTick}`,
một test khác khẳng định máy chủ **vẫn cho xuất và cho tải về** khi chưa xác nhận.

### Số liệu trong bằng chứng do MÁY CHỦ đếm

`acknowledge` **không nhận** số cảnh báo từ trình duyệt gửi lên (gửi kèm là `422`). Số do máy
khách gửi thì không còn là bằng chứng — nó chứng minh trình duyệt nói gì, không chứng minh hệ
thống lúc đó thế nào.

### `export_compliance_log` — chỉ số liệu, không nội dung

Bảng riêng thay vì nhét vào `ExportJob.error_log`: đây là bản ghi tuân thủ cần tra cứu được
("chapter này đã xác nhận chưa, lúc nào, khai để dùng vào việc gì"), còn `error_log` là chỗ ghi
lỗi kỹ thuật — trộn vào nhau thì cả hai cùng khó đọc.

Đúng **10 cột**, không cột nào chứa đường dẫn file, ảnh hay bản dịch. Có guardrail test liệt kê
tên cột và chặn mọi cột tên chứa `output_path`/`content`/`text`/`image`/`file`.
`export_job_id` để `SET NULL` khi xoá bản ghi xuất: xoá file đã xuất **không được** xoá mất bằng
chứng đã xác nhận.

### Khai báo mục đích: không có mặc định

`Project.intended_use` đã `NOT NULL` từ M1 và `ProjectCreate` không có giá trị mặc định, nên
**không cần migrate**. Chỗ hỏng nằm ở giao diện: ô chọn trước M10 mặc định sẵn `personal`, nghĩa
là ai bấm nhanh cũng thành "đọc cá nhân" mà chưa hề tự khai. M10 bỏ mặc định (`— hãy chọn —`), và
nút tạo chapter mờ tới khi chọn.

Khai báo **không sửa được** sau khi tạo — không có endpoint nào cho sửa, và có test canh cả
`PATCH` lẫn `PUT` trên `/projects/{id}`.

### Không watermark/DRM

Mini-spec cấm, và lý do đứng vững: nó không giúp gì cho việc tuân thủ bản quyền thật, chỉ làm hỏng
ảnh của chính người dùng. Guardrail test quét **phần mã** (bỏ chú thích và chuỗi tài liệu, bằng
`tokenize`) — soi cả lời văn thì chính đoạn giải thích "không làm watermark" cũng làm test đỏ.

## 12. Kiến trúc giao diện (E11)

E11 **không đụng vào backend**: không đổi API, schema, enum, Celery hay mô hình AI. Toàn bộ thay
đổi nằm trong `frontend/`.

```
frontend/src/
  styles/tokens.css      màu · khoảng cách · bo góc · vòng focus — MỘT nguồn duy nhất
  lib/
    status-presentation.js   dịch trạng thái backend -> chữ hiển thị (có test đối chiếu API.md)
    chapter-progress.js      suy dòng thời gian pipeline từ trạng thái trang thật
  components/ui/         Button · Field · StatusBadge · EmptyState · Dropzone ·
                         ProgressStage · Dialog · Alert · Icon
  components/chapter/    ChapterCreateForm · ChapterRecentList · ChapterProgress ·
                         ChapterSummary · ReviewToolbar
  components/            RegionPanel · BboxOverlay (M7) · ExportPanel (M8) ·
                         BatchPanel (M9) · ExportWarningModal (M10) — giữ nguyên, dùng lại
```

### Một chỗ duy nhất dịch trạng thái ra chữ

`lib/status-presentation.js` phủ **8 họ enum** (trang, việc, mẻ, mục mẻ, căn chữ, đọc chữ, dịch,
vùng). Rải chuỗi trạng thái khắp component là cách chắc chắn để sớm muộn có một màn gọi `pending`
là "xong" — nên chỗ này được canh bằng test **đối chiếu từng giá trị enum trong `API.md`**:

- backend thêm trạng thái mà quên cập nhật giao diện ⇒ **test đỏ**;
- trạng thái lạ lọt tới trình duyệt ⇒ hiện *"Trạng thái chưa được hỗ trợ"* kèm mã thô, **không**
  đoán là thành công;
- `typeset_done` mà còn vùng tràn khung / chưa đọc được chữ ⇒ **hạ xuống mức cảnh báo**, đổi nhãn
  thành *"Đã căn chữ, còn vùng cần sửa"*. Đây là triết lý evidence-first của M1–M10 kéo dài tới
  tầng hiển thị.

Màu **không bao giờ** là nguồn thông tin duy nhất: mỗi trạng thái luôn có nhãn chữ + icon.

### Không có thanh phần trăm giả

Backend không đo phần trăm cho một trang, nên giao diện cũng không bịa ra. Dòng thời gian hiện
**số trang đã qua từng bước** (`3/3 trang`) — con số đếm được thật.

### Vùng kéo-thả vẫn là `<input type="file">`

Vùng thả chỉ là lớp vỏ; input thật vẫn nằm đó (ẩn) và mở được bằng Enter/Space. Tự vẽ vùng thả rồi
bỏ input là đánh đổi độ tin cậy và khả năng tiếp cận lấy vẻ đẹp.

### Giao diện phải kiên nhẫn bằng máy chủ

Worker chạy **một việc một lúc**. Khi đang có chapter khác chạy thì việc của người dùng phải xếp
hàng — đo thật ở E11: căn lại chữ mất **108 giây**. Giao diện cũ bỏ cuộc ở giây 42 rồi báo *"quá
lâu, chưa xong"*, khiến người dùng tưởng hỏng. Nay chờ tới 10 phút, hiện **"đang chờ tới lượt"**,
và nếu hết kiên nhẫn thì nói *"vẫn đang chạy"* — không nói là hỏng.

### Khoảng trống còn lại

Chưa có `GET /projects` để liệt kê chapter, nên danh sách "gần đây" nằm trong bộ nhớ trình duyệt
và giao diện **nói rõ điều đó**. Không tự thêm endpoint ở E11 — xem `REPORT_E11.md §7`.

## 13. Cổng chất lượng từng vùng (E12)

### Việc duy nhất nó làm: biến bằng chứng có sẵn thành lý do đọc được

Sau khi căn chữ xong, mỗi vùng chữ được chấm bằng **luật thuần**, không gọi mô hình nào. Toàn bộ
đầu vào đã nằm sẵn trong DB từ M2–M6: điểm nhận diện khung, trạng thái/nội dung OCR, trạng
thái/độ dài bản dịch, hình học khung, kết quả căn chữ. E12 chỉ đọc chúng rồi nói thành câu.

Vì sao **không** hỏi thêm một con AI để chấm bản dịch: nhờ LLM chấm chính bản dịch của LLM là để
nó tự khen mình; kết quả không lặp lại được và tốn token mỗi lần chấm.

Vì sao **không có điểm 0–100**: một con số gộp nhiều thứ khác bản chất lại nghe như đo được chính
xác, trong khi không giải thích được vì sao. `overall_band` + `relevance` + danh sách lý do thì
nói được thành câu, và người dùng quyết định được.

### Ranh giới cứng: máy không kết luận thay người

| Cấm | Vì sao |
|---|---|
| Xoá vùng nghi ngờ | Số trang, tiếng động, chữ trong tranh — cái nào đáng dịch là tuỳ truyện |
| Sửa `raw_text` / `translated_text` | Đó là dữ liệu của M3/M5; E12 chỉ đọc |
| Luật "viết hoa = bỏ" hay "ngắn = bỏ" | `NO!`, `PHEW!`, `18` đều có thể hợp lệ |
| Tự đặt `reviewed_skip` | Chỉ người dùng bấm mới được. Bỏ qua **không** xoá dữ liệu |

Bộ chấm nằm ở `services/quality/assessor.py` là **hàm thuần**: không chạm DB, không chạm mạng,
không sửa dữ liệu vào. Nhờ vậy 41 test đơn vị chạy không cần Postgres, và không có đường nào để
lén ghi đè dữ liệu của bước khác trong lúc chấm.

### 18 mã lý do, một bảng trắng

Mã lý do đi thẳng ra giao diện và vào bảng đếm, nên chúng là **bảng trắng cố định** ở
`services/quality/reasons.py`, mỗi mã kèm một câu tiếng Việt. Có test bắt lỗi nếu bộ chấm sinh ra
mã ngoài bảng, và test khác bắt lỗi nếu một mã chưa có câu mô tả.

Một mã đặc biệt: `ocr_confidence_unavailable` **chỉ để biết**, không đủ để bắt rà soát —
manga-ocr không bao giờ trả điểm tin cậy, nên coi đó là dấu hiệu xấu sẽ bắt rà soát toàn bộ trang
tiếng Nhật. "Không có điểm" khác hẳn "điểm thấp", và giao diện **không bao giờ** hiện nó là 0%.

### Chạy ở đâu, khi nào

Chấm chạy **trong worker** ngay sau khi căn chữ xong (và sau mỗi lần sửa tay + căn lại), không
chạy trong request HTTP. Không thêm loại `Job` mới: thêm giá trị vào enum `job_type` của Postgres
cần `ALTER TYPE`, mà M1 đã cố ý khai đủ mọi loại từ đầu để tránh đúng chuyện đó.

Chấm hỏng **không** kéo theo việc căn chữ: trang vẫn giữ nguyên kết quả, chỉ là chưa có đánh giá —
và bảng tổng hợp nói "chưa đánh giá" chứ không báo 0 cảnh báo.

### Quyết định của người được giữ

Chấm lại giữ nguyên `reviewed_keep`/`reviewed_skip`, **trừ khi bằng chứng đổi** (so sánh
`evidence_snapshot`). Chấm lại mà xoá mất quyết định của người là xoá công họ đã bỏ ra; ngược lại,
giữ quyết định cũ trong khi nội dung đã đổi là để họ tin vào một kết luận không còn đúng.

## 9. Giới hạn đã biết (cố ý để lại)

- **Supabase Storage chưa có adapter.** M1 chạy `STORAGE_BACKEND=local` (đã verify thật).
  Khi đặt `STORAGE_BACKEND=supabase`, app **fail ngay** với thông báo rõ ràng thay vì im lặng ghi sai chỗ.
  Nối Supabase Storage cần credential thật → làm khi có key (ưu tiên trước M4 vì M4 sinh thêm ảnh clean).
- ~~Chưa dispatch Celery task~~ → **đã xong ở M2**: upload page enqueue `detect.run_detect_job`.
  Nếu broker chết, job đứng ở `queued` kèm `error_log=enqueue_failed:…` (không giả vờ đã gửi).
- **NỢ KỸ THUẬT (tracked):** `SupabaseStorageAdapter` chưa viết — cần khi có credential Supabase.
  Nên làm trước M4 vì M4 bắt đầu sinh thêm ảnh clean. Hiện `STORAGE_BACKEND=supabase` fail có thông báo rõ.
- ~~Chưa có typeset~~ → **đã xong ở M6**.
- **M2 chưa xử lý** ảnh xoay/nghiêng, scan chất lượng kém; auto-retry khi timeout **đã có ở M9** (chỉ cho lỗi tạm thời, có trần — §10);
  chưa có UI vẽ overlay box (thuộc M7).
- **Chưa có auth/user management** — nếu cần multi-user phải là mini-spec riêng, không nhét vào MTE.

## E13. Thuật ngữ & rà soát nhất quán

Lớp này **do người điều khiển**, không phải máy tự viết lại bản dịch. Nó chốt cách dịch cho cả
chapter rồi chỉ ra chỗ chưa theo — mỗi chỗ một việc riêng, kèm bằng chứng, người quyết định.

### Vì sao dùng luật tất định thay vì hỏi máy

Luật kiểu *"thuật ngữ đã chốt là X mà chỗ này không có X"* thì rẻ, chạy lại ra đúng kết quả cũ, và
giải thích được. Quan trọng hơn: nó **thành thật về giới hạn**. Máy không biết câu nào dịch hay
hơn; nó chỉ biết chỗ nào không theo quy ước bạn đã chốt. Vì vậy E13 không chấm điểm chất lượng và
không có nút "áp dụng cho cả chapter".

### So khớp theo từng ngôn ngữ

| Ngôn ngữ | Luật | Bẫy đã tránh |
|---|---|---|
| Anh | ranh giới từ, không phân biệt hoa thường | `\b` của Python coi `'` và `-` là ranh giới ⇒ dùng thẳng sẽ khớp `Don't` với `Dont`. Phải tự dựng ranh giới |
| Nhật / Trung | chuỗi con, **ưu tiên thuật ngữ dài trước** | không có luật dài-trước thì `魔法薬` bị đếm thành hai lần `魔法` |
| Tiếng Việt (bản dịch) | không phân biệt hoa thường, **giữ nguyên dấu** | bỏ dấu để so sẽ khiến `ma` khớp cả `mà`, `má`, `mã` — sinh hàng loạt cảnh báo sai |

Mọi phép so đều chuẩn hoá **NFC trong bộ nhớ** và **không bao giờ ghi lại** — cùng bài học NFC mà
M6 đã trả giá ở khâu vẽ chữ.

### Vân tay bản dịch — chốt chặn quan trọng nhất

Mỗi việc lưu `snapshot_hash` của bản dịch tại lúc tạo. Áp một đề xuất khi bản dịch đã đổi là **xoá
mất phần người khác vừa sửa ở M7**, nên việc đó chuyển `stale` và bị chặn. Đây cũng là thứ khiến
quét lại không đẻ ra việc trùng.

### Bẫy Postgres: NULL trong ràng buộc duy nhất

`ConsistencyReviewTask` có hai khoá ngoại tuỳ chọn, và việc do luật sinh ra luôn để trống một
trong hai. Postgres coi **mỗi NULL là một giá trị khác nhau**, nên `UNIQUE` thường vẫn cho chèn
trùng — đã đo thật, xem `TEST_LOG § E13.2`. Phải dùng `UNIQUE NULLS NOT DISTINCT` (Postgres 15+).

### Ranh giới với các bước khác

- **Không đụng** `OCRResult.raw_text` (M3), ảnh gốc/clean (M4), ảnh xem thử (M6).
- **Tôn trọng** quyết định "bỏ qua" của E12 — vùng đó không bị quét lại.
- Áp xong dùng lại **đúng đường canh chữ của M7**, chỉ cho một vùng, giữ nguyên cỡ chữ đã ghim.
- Gợi ý bằng LLM là **tuỳ chọn, mặc định tắt**; bật lên mới tốn token, và vẫn phải người duyệt.
