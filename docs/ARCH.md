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
| Storage | `IObjectStorage`: `local` (thư mục) hoặc **`postgres`** (bảng `artifact_blob`) | **P3e**: chạy thật phải là `postgres` — VibeHost không cấp volume bền (P3c) nên `local` KHÔNG giữ được gì qua redeploy. Adapter Supabase vẫn chưa implement |
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

## 8b. Ranh giới lưu trữ hiện vật (P3d)

Bối cảnh: P3c chứng minh VibeHost **không cấp được volume bền**, nên hiện vật ghi ra hệ tệp
container mất sạch mỗi lần triển khai lại. Lối thoát chỉ còn CSDL hoặc kho đối tượng ngoài — và
cả hai đều bị chặn bởi cùng một thứ, nên P3d gỡ thứ đó ra.

**Thứ bị gỡ:** `abs_path()`. Trước P3d nó là hợp đồng đọc/ghi — bên gọi xin đường dẫn tuyệt đối
rồi tự mở tệp, hoặc đưa đường dẫn cho engine tự ghi vào. Hợp đồng ấy trói hệ thống vào hệ tệp
cục bộ: không kho đối tượng nào phục vụ được kiểu gọi đó.

**Thay bằng** (`app/services/storage.py`):

| Nhóm | Hàm | Ghi chú |
|---|---|---|
| Đọc | `read` · `open_read` · `exists` · `stat` | `stat` trả `(size, mtime)` — đủ cho vân tay E14 và ETag HTTP |
| Ghi | `save` · `save_file` · `save_page_image` | **nguyên tử**: ghi tệp tạm rồi `os.replace` |
| Liệt kê/xoá | `list_prefix` · `delete_prefix` · `delete` | kho là thứ duy nhất biết mình đang giữ gì |
| Vật chất hoá | `workspace()` + `fetch_to()` | ranh giới cho engine bên thứ ba |

**Ranh giới vật chất hoá** là điểm mấu chốt. Các engine (comic-text-detector, manga-ocr,
PaddleOCR, LaMa, bộ vẽ M6, bộ xuất M8) đều nhận **đường dẫn tệp** — nên phải có tệp thật ở đâu
đó. Chỗ đó **không được là lòng kho**; nếu là lòng kho thì kho buộc phải là hệ tệp mãi mãi. Nên:
chép hiện vật ra thư mục tạm → engine làm việc ở đó → `save_file()` kết quả ngược vào kho →
dọn thư mục tạm. Chép thêm vài MB rẻ hơn nhiều so với một lượt chạy model.

Hệ quả kèm theo (không phải mục tiêu, nhưng có thật):

- **Đóng lỗ hổng path traversal.** `_abs()` cũ ghép thẳng `root / rel` và không kiểm gì:
  `root / "/etc/passwd"` cho ra `/etc/passwd` (path tuyệt đối **nuốt** luôn root). Nay
  `chuan_hoa_path()` chặn path tuyệt đối, `..`, và path rỗng; `_abs()` chặn thêm symlink trỏ
  ra ngoài. Chưa từng khai thác được (mọi lời gọi lấy giá trị từ CSDL) nhưng vẫn là lỗ thật.
- **Ghi nguyên tử ở mọi đường ghi**, không chỉ đường xuất. Trước đây ảnh clean/preview ghi
  bằng `write_bytes` — hỏng giữa chừng để lại tệp cụt trông như hiện vật hợp lệ.
- **Vân tay E14 rẻ đi.** `vung_an_toan_dung_duoc()` trước đây tự `stat()` lại tệp cho **mỗi**
  vùng; một trang 30 vùng là 30 lượt hỏi kho cho cùng một tệp. Nay nhận vân tay tính sẵn.

**Đường ghi ảnh clean không đổi path.** LaMa vẫn tự đặt tên ảnh clean cạnh ảnh gốc, nhưng nay
làm việc đó trong thư mục tạm; path tương đối lưu vào CSDL vẫn là
`projects/<pid>/pages/<page_id>_clean.png` ⇒ **không cần migrate dữ liệu cũ**.

## 8c. Kho hiện vật trong Postgres (P3e)

`artifact_blob (path TEXT PK, data BYTEA, size_bytes BIGINT, created_at, updated_at)`.

`path` **giữ nguyên chuỗi** của backend `local` ⇒ `page.clean_image_path` và
`export_job.output_path` không phải migrate khi đổi backend.

Bốn quyết định nhỏ, mỗi cái chữa một lỗi cụ thể:

| | Vì sao |
|---|---|
| `SET STORAGE EXTERNAL` trên `data` | PNG/ZIP đã nén sẵn; để mặc định thì Postgres nén lại lần nữa — tốn CPU, không giảm byte |
| `size_bytes` tách khỏi `data` | `stat()` bị gọi ở **mọi** lượt phục vụ HTTP (dựng ETag); không tách thì mỗi lượt kéo cả 3 MB lên chỉ để đếm |
| Index `text_pattern_ops` | `LIKE 'tiền tố/%'` không dùng được index dưới collation mặc định |
| Thoát `_`/`%` khi dựng mẫu LIKE | `_` là ký tự đại diện của LIKE, mà tên thật có `_` (`…_clean.png`) — quên thoát là `delete_prefix` xoá nhầm project khác |

**Ghi đè = upsert một câu lệnh** (`ON CONFLICT DO UPDATE`). "Xoá rồi chèn" có một khoảnh khắc
hiện vật không tồn tại — ai đang xem đúng lúc đó thì thấy 404.

**Sync/async:** kho là đồng bộ (worker Celery vốn đồng bộ); tầng HTTP async gọi nó qua
`run_in_threadpool`. Gọi thẳng sẽ chặn event loop — với `local` không ai nhận ra, với CSDL thì
mỗi lời gọi là một lượt đi mạng nội bộ. Không viết bản async riêng: nhân đôi đường đọc là nhân
đôi số chỗ có thể lệch nhau.

**`open_read()` là luồng LƯỜI** (P3g): `LuongHienVatLuoi` hiện thực `seek/tell/readinto` trên
`read_range()`, bọc `BufferedReader` khối 256KB. RAM tỉ lệ với **khối đang đọc**, không phải với
kích thước hiện vật. Phải tua được vì PIL tua tới lui trong header ảnh — luồng chỉ-đọc-tiếp sẽ
làm hỏng mọi chỗ dùng ảnh.

**`read_range()`** dùng `substr()` phía máy chủ. Đây là chỗ `SET STORAGE EXTERNAL` trả công lần
thứ hai: cột không nén nên Postgres giải TOAST được **một phần**. Nó cũng là nền của HTTP `Range`.

**Đo thật trên host** (kết nối dùng lại, mốc nền `/healthz` = 3,4 ms p50): `stat()`+ETag ≈ 3,4 ms;
đọc+phát nguyên hiện vật ≈ 6,2 ms; đọc một đoạn 8KB ≈ 5,2 ms. Không phải chỗ nghẽn.

## 8d. Bộ nhớ worker — vì sao arena ONNX bị TẮT cho LaMa mà vẫn BẬT cho CTD (P3h)

Pilot 6 trang trên host làm worker bị **OOM killer giết** (`exit 137`). Nguyên nhân không phải
"thiếu RAM" mà là một tương tác cụ thể giữa hai lựa chọn đã có từ M4:

```
LaMa = model DYNAMIC SHAPE  ×  chạy theo TỪNG CỤM bong bóng (mỗi cụm một kích thước)
                             ×  SessionOptions() mặc định = CPU memory arena BẬT
⇒ arena cấp một khối cho MỖI shape mới và KHÔNG trả lại ⇒ phình theo số cụm/số trang
```

Đây là lý do **một** trang (P3a) chạy trọn 157 s không sao, còn **sáu** trang thì chết — hình dạng
mà giả thuyết "thiếu RAM" không giải thích được.

| Engine | `enable_cpu_mem_arena` | Vì sao |
|---|---|---|
| **LaMa** (`inpaint_cpu_mem_arena`) | **False** | dynamic shape + chạy theo cụm ⇒ nhiều shape ⇒ arena phình không trả lại |
| **CTD** (`ctd_cpu_mem_arena`) | **True** | letterbox về **một** kích thước cố định ⇒ **một** shape ⇒ arena vô hại và còn nhanh hơn |

Phân biệt này là **có bằng chứng**, không phải "tắt cho an toàn". Tắt bừa cả hai là trả tiền tốc
độ của CTD để mua một thứ CTD không cần.

**Trộn ảnh theo dải** — `_tron_theo_dai(rgb, pred, mask)` trong `lama.py`, và **đường chạy thật
lẫn test gọi chung đúng hàm đó** (tách ra ở lượt hậu kiểm P3h; trước đó vòng lặp nằm inline trong
`inpaint()` nên test chỉ so được với một bản chép lại của chính nó). Bước cuối của inpaint ghép
ảnh gốc với ảnh model theo mask. Viết một dòng
`rgb*(1-m) + pred*m` thì numpy dựng 5–6 mảng `float32` **cỡ nguyên trang** cùng lúc. Nay lặp theo
dải `_DAI_TRON = 256` dòng, ghi tại chỗ bằng `out=`. Đo `tracemalloc`: 1200×1660 đỉnh
**71,7 → 14,6 MB**; 1400×2000 đỉnh **100,8 → 18,5 MB** — kết quả **giống nhau từng byte**. Điểm
quan trọng không phải "nhỏ hơn 80 %" mà là **đỉnh thôi phụ thuộc cỡ trang**.

**Van xả, không phải chế độ thường trực.** `app/workers/bo_nho.py`:

```
rss_mb()                 đọc /proc/self/statm — không thêm psutil chỉ để lấy một con số
ghi_moc(nhan)            mốc RSS ở ranh giới detect / ocr / inpaint
ep_giai_phong_neu_cang() CHỈ nhả model khi RSS > worker_rss_soft_limit_mb (mặc định 2200, 0 = tắt)
```

Đường chạy bình thường **giữ nguyên cache** — nhả rồi nạp lại là LaMa ~197 MB + CTD ~91 MB mỗi
lượt. Mỗi bước khai đúng thứ nó cần, và **inpaint giữ lại OCR** vì `inpaint_verify_by_ocr` cần
ngay sau đó.

⚠️ **Ranh giới quan sát — đọc kỹ chỗ này.** `/healthz` trả `rss_mb` của **tiến trình API**, không
phải của worker. Trên host `ROLE=all`: uvicorn ở tiền cảnh, celery `--pool=solo` ở **tiến trình
nền riêng** — và **celery mới là thứ bị OOM giết**. RSS của worker hiện chỉ đi vào **log**, thứ
không sống sót qua deploy (P3f) và đang không lấy được từ nền tảng (`wings_error`). Thứ thật sự
tố giác cái chết vẫn là `worker.so_lan_chet` + `ma_thoat_gan_nhat = 137` trong `WORKER_STATE_FILE`
— có từ trước P3h. **Đường đóng rẻ nhất (chưa làm):** cho worker tự ghi RSS vào chính tệp trạng
thái đó, rồi `/healthz` trả cả hai.

## 8d. Cổng cảnh báo trước khi xuất — vì sao "không có việc" ≠ "không có rủi ro" (P3i)

Cổng xuất gom cảnh báo thành các **nhóm tách bạch** (E12 chất lượng · E13 nhất quán · E14 bố cục ·
E15 hướng chữ · M10 pháp lý). Gộp lại thì người dùng tick một ô rồi tưởng đã xử lý hết.

Nhưng kiến trúc ấy có một lỗ mà pilot hosted 03/09 lộ ra: mỗi nhóm chỉ hiện khi **đếm được việc**.
Nhóm E13 đếm *việc rà soát nhất quán* — mà việc đó chỉ sinh ra khi **đã có thuật ngữ được duyệt**.
Chapter chưa khai thuật ngữ nào ⇒ 0 việc ⇒ **nhóm biến mất**. Kết quả đo được: nhân vật *Pepper*
bị dịch thành "Hạt tiêu" và cổng xuất im lặng hoàn toàn.

⇒ Nguyên tắc rút ra, áp cho mọi nhóm cảnh báo về sau:

> **Đếm việc còn tồn không đủ. Phải đếm cả điều kiện tiền đề.** Khi tiền đề chưa có, "0 việc" là
> tin xấu chứ không phải tin tốt — và đó chính là lúc phải nói to nhất.

Hiện thực: `export-warnings` trả thêm `glossary_approved_count`, và giao diện hiện cảnh báo khi
bằng **0**. Chỉ đếm mục **đã duyệt** — bản nháp không được dùng khi rà soát nên đếm vào sẽ tắt
cảnh báo trong khi rủi ro còn nguyên.

## 9. Giới hạn đã biết (cố ý để lại)

- **Supabase Storage chưa có adapter.** M1 chạy `STORAGE_BACKEND=local` (đã verify thật).
  Khi đặt `STORAGE_BACKEND=supabase`, app **fail ngay** với thông báo rõ ràng thay vì im lặng ghi sai chỗ.
  Nối Supabase Storage cần credential thật → làm khi có key (ưu tiên trước M4 vì M4 sinh thêm ảnh clean).
- ~~Chưa dispatch Celery task~~ → **đã xong ở M2**: upload page enqueue `detect.run_detect_job`.
  Nếu broker chết, job đứng ở `queued` kèm `error_log=enqueue_failed:…` (không giả vờ đã gửi).
- ~~Chưa có adapter kho bền~~ → **đã xong ở P3e**: `PostgresObjectStorage`. Hạn mức gói là
  **20 GB** (chủ dự án xác nhận), còn ~18,7 GB ≈ **~1.400 trang** ⇒ chọn Postgres, không cần nhà
  cung cấp ngoài. Ngưỡng nên xét đổi sang S3/Supabase: **quá ~10 GB hiện vật**, hoặc cần CDN.
- **Hiện vật trên host vẫn KHÔNG bền cho tới khi `STORAGE_BACKEND=postgres` được đặt và deploy.**
  Mã đã sẵn sàng; cấu hình host thì chưa đổi. Đừng đọc "P3e xong" thành "host đã hết lỗi".
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


## E1. Tiện ích Chrome — cổng mở nhanh (2026-08-30)

### E1.1 Chỗ đứng trong kiến trúc

```
Chrome ──► Side Panel (chrome-extension://…)
              │
              ├─ tabs.create  ──►  Web app  (http://127.0.0.1:5174)  ──proxy /api──►  API
              │                      #project= / #page= / trang chủ
              └─ fetch (chỉ ĐỌC) ──► <base>/api/v1/health
                                     <base>/api/v1/projects/{id}
```

Tiện ích là **consumer thuần**, giống hệt vai trò của giao diện M7: không đụng CSDL, không đụng
Redis, không đụng Celery, không có endpoint riêng. Nó **không** phải một tầng mới trong pipeline.

Ranh giới cứng: tiện ích **không có** content script và **không có** `host_permissions`, nên nó
không có đường nào chạm vào trang web người dùng đang xem. Đây là sự thật về sản phẩm, không phải
giới hạn tạm thời — E2 (nhập ảnh theo URL) và E3 (phủ bản dịch lên trang) mỗi cái cần audit
SSRF / nguồn / bản quyền / consent riêng.

### E1.2 Bảng buộc route — đường THẬT, không phải đường đặt ra cho đẹp

Giao diện Translation **không có router**: `frontend/src/App.jsx` chọn màn bằng hash.

| Tiện ích cần | Đường thật | Ghi chú |
|---|---|---|
| Tạo chapter | `<base>/` | form tạo nằm ở trang chủ |
| Tiến độ chapter | `<base>/#project=<uuid>` | |
| Rà soát tay (M7) | `<base>/#page=<uuid>` | |
| Xuất (M8) | `<base>/#project=<uuid>` | **không có route riêng** — `ExportPanel` nằm trong màn chapter |
| Sống chưa | `GET /api/v1/health` | có kiểm CSDL |
| Chi tiết chapter | `GET /api/v1/projects/{id}` | `ProjectDetail` |

**Không** có endpoint liệt kê project (`GET /api/v1/projects` → 405). Nên tiện ích không tự dò ra
chapter; người dùng ghim bằng mã. Nếu sau này muốn bỏ bước ghim tay thì cần một mini-spec backend
riêng thêm `GET /api/v1/projects` chỉ-đọc có phân trang — **không** được bịa `/api/v1/extension/*`.

### E1.3 Ba lớp kiểm trước khi một chuỗi được dùng

Chuỗi do người dùng gõ đi qua ba cổng trước khi tới `fetch` hoặc `tabs.create`:

1. `kiemDiaChiLocal()` — phân tích bằng `new URL()` rồi soi từng phần (giao thức / tên máy / tài
   khoản / cổng / đường dẫn / query). **Không** so tiền tố. Trả về địa chỉ **đã chuẩn hoá**, và
   mọi lượt gọi về sau dùng chuỗi trả về đó ⇒ không có khe hở "bộ kiểm đọc một đằng, bộ gọi đọc
   một nẻo".
2. `chuanHoaMa()` — mã chapter/trang phải khớp mẫu UUID, hạ về chữ thường.
3. `chotChanGhi()` — ném lỗi nếu có khoá ngoài khuôn được đưa vào `chrome.storage.local`.

### E1.4 Vì sao service worker không được nhớ gì

MV3 chạy service worker theo sự kiện; Chrome tắt nó sau một lúc rảnh rồi dựng lại từ đầu. Nên
`src/service-worker.js` **chỉ** nối dây sự kiện: không cache chapter, không đếm job, không hẹn giờ.
Chỗ nhớ duy nhất là `chrome.storage.local` (địa chỉ local + tối đa 5 mã chapter đã ghim). Trạng
thái backend **luôn** được hỏi lại khi panel mở — có test canh không có `let`/`var` ở mức tệp
trong service worker.

### E1.5 CORS — đo được, không suy đoán

| Đường đi | `Access-Control-Allow-Origin` | Tiện ích đọc được? |
|---|---|---|
| Thẳng vào API `:8010` | không có (`CORS_ALLOW_ORIGINS` rỗng) | ❌ |
| Qua giao diện dev `:5174` hoặc `:5173` | `*` (Vite dev server tự thêm) | ✅ ngay, không cần cấu hình |
| Qua giao diện prod (nginx) | — nginx **không** proxy `/api` | ❌ → chế độ chỉ-mở-link |

E1 **không** đụng vào cấu hình CORS của backend. Ở bản prod, tiện ích nói thẳng là chưa đọc được
trạng thái thay vì hiện danh sách rỗng.

⚠️ Ghi nhận (ngoài phạm vi E1, cố ý không sửa): vì Vite dev server gắn `ACAO: *` cho mọi phản hồi
proxy, **bất kỳ website nào** đang mở cũng đọc được API Translation local qua cổng 5173/5174 khi
máy chủ dev đang chạy. Tính chất này có sẵn từ trước E1.


## E15b. Giao diện hướng chữ + vì sao chữ dọc vẫn chưa dựng được (2026-08-30)

### E15b.1 Đường đi của một phán quyết hướng chữ ra tới màn hình

```
PaddleOCR ──line_polygons──► OCRResult.line_polygons  (chỉ tồn tại ở bước OCR)
                                     │
                          OrientationAnalyzer  ──► RegionTextOrientation
                                     │                (orientation, status, reason_codes)
              GET /regions/{id}/orientation ──► api.layHuongChu()
              GET /pages/{id}/orientation-summary ──► api.tomTatHuongChu()
                                     │
        nhanHuongChu(orientation, status, reason_codes)  ← nguồn sự thật DUY NHẤT của nhãn
                                     │
        StatusBadge (E11, prop `dienGiai`) · OrientationBox · OrientationSummaryCard
```

**Nhãn phụ thuộc CẢ hướng lẫn trạng thái**, nên không tra được bằng `dienGiaiTrangThai(loai, tt)`
như các bảng khác. "Chữ dọc + `ready`" nghĩa là hệ thống đã dựng chữ theo cột thật; "chữ dọc +
`unavailable`" nghĩa là mới nhận ra chứ chưa dựng được. Gộp hai thứ đó vào một nhãn là đúng kiểu
nói quá mà cả E15 sinh ra để chống — nên `StatusBadge` được thêm prop `dienGiai` thay vì đẻ ra
một huy hiệu thứ hai.

**404 ≠ `unknown`.** Backend cố ý trả 404 cho vùng chưa phân tích. `api.layHuongChu()` dịch 404
thành `null` và **chỉ** 404 — mọi lỗi khác vẫn ném ra, nếu không thì "API chết" hiện y hệt "chưa
kiểm". Bộ lọc "Cần kiểm tra hướng chữ" **có** bắt các vùng `null`.

### E15b.2 Vì sao chữ dọc vẫn BLOCKED — bốn vật cản đo được

| # | Vật cản | Số đo (2026-08-30) |
|---|---|---|
| 1 | Dữ liệu | không có ảnh chữ dọc tiếng Nhật license rõ |
| 2 | **Kiến trúc** | `MangaOCREngine.recognize()` → `(text, None)`, không đường bao dòng |
| 3 | Môi trường | `PIL.features.check("raqm")` trong worker = `False` |
| 4 | Glyph | 0 font có kana/kanji trên máy |

Vật cản 2 quyết định nhất và ít ai ngờ: `analyzer` chỉ tới được `vertical_ttb` qua
`ocr_line_geometry_vertical`. Tiếng Nhật — thứ tiếng có nhiều chữ dọc nhất — lại dùng engine
**không** trả hình học dòng. ⇒ **Có ảnh hoàn hảo cũng không mở khoá được.** Muốn làm thật cần một
mini-spec riêng cho nguồn hình học tiếng Nhật (ví dụ chạy PaddleOCR `lang='japan'` song song chỉ
để lấy đường bao dòng, còn nội dung vẫn do manga-ocr đọc).

Vật cản 3 là cái bẫy nguy hiểm nhất cho người làm tiếp: **libraqm có trên máy dev (`True`) nhưng
không có trong worker (`False`)**. Ai dựng Option A (Pillow `direction="ttb"`) trên máy dev sẽ
thấy chữ dọc vẽ ra đẹp, merge, rồi nó ném `KeyError` im lặng ở nơi thật sự chạy. Option B (vẽ theo
grapheme) là đường duy nhất còn lại — `regex` đã có sẵn trong worker.

### E15b.3 Bẫy vận hành: worker không nạp lại mã

`deploy/docker-compose.yml` mount `../backend:/app`, nên **tệp** trên đĩa luôn mới. Nhưng Celery
nạp module lúc khởi động và không nạp lại. Container worker chạy 44 giờ = khởi động trước khi E15
được commit ⇒ mã E15 **chưa từng được thực thi** dù đã nằm đó cả ngày, và bảng
`region_text_orientation` rỗng sạch.

⇒ **Mọi mini-spec đụng vào worker phải `docker compose -f deploy/docker-compose.yml restart worker`
trước khi đo.** Không làm là đo nhầm mã cũ rồi kết luận sai về chính thứ mình vừa viết.


## E1a. Ranh giới truy cập (CORS) — xem `docs/SECURITY.md`

Từ 2026-08-30, quy tắc origin của Translation nằm ở **`docs/SECURITY.md`** (nguồn sự thật duy
nhất). Tóm tắt để khỏi phải mở tệp khác:

- **Chặn mặc định.** Không tầng nào được phát `Access-Control-Allow-Origin: *`.
- **Hai tầng, hai biến, cố ý không gộp:** `DEV_SERVER_CORS_ALLOW_ORIGINS` (máy chủ dev Vite,
  `frontend/vite.config.js`) và `CORS_ALLOW_ORIGINS` (API FastAPI lúc chạy thật,
  `backend/app/main.py`). Gộp lại thì một origin khai cho prod sẽ vô tình mở trên máy dev.
- **Giao diện web không cần CORS** — nó gọi `/api` cùng nguồn qua proxy của Vite.
- **Tiện ích E1 mặc định chỉ-mở-link.** Muốn nó đọc trạng thái thì tự khai đúng
  `chrome-extension://<id>` của bản cài trên máy mình. Không bao giờ `chrome-extension://*`.
- **CORS không phải xác thực** — không có auth/multi-user/TLS.

## E17. Gợi ý thuật ngữ & xưng hô rút từ CHÍNH chapter (2026-09-01)

### E17.1 Vì sao câu hỏi bị đảo chiều

Yêu cầu gốc là "nhập tên bộ truyện → AI lấy dàn nhân vật". Không làm thế, vì ba lý do đo được:
model **luôn trả lời** kể cả khi không biết; nó **không biết chapter NÀY có ai**; và thuật ngữ đã
duyệt là **luật** để quét cả chapter, nên một tên bịa được duyệt sẽ làm mọi lượt rà soát sau đó
báo sai — hỏng đúng thứ E13 sinh ra để bảo vệ.

```
KHÔNG hỏi:  "truyện X có những nhân vật nào?"                   -> không kiểm chứng được
MÀ hỏi:     "đây là danh xưng CÓ THẬT trong chapter này của X —
             người ta thường dịch chúng thế nào?"                -> kiểm chứng được
```

### E17.2 Ba tầng, và tầng dưới không phụ thuộc tầng trên

| Tầng | Làm gì | Gọi LLM? |
|---|---|---|
| 1 | Rút **ứng viên thuật ngữ** từ `ocr_result.raw_text` | không |
| 2 | Rút **tín hiệu xưng hô** có thật trong bản gốc | không |
| 3 | Hỏi mô hình cách dịch cho đúng danh sách tầng 1 | có ⇒ job nền, `202` |

Mô hình chết thì tầng 1+2 vẫn chạy bình thường, và giao diện nói thẳng điều đó.

### E17.3 Luật theo ngôn ngữ — và cái bẫy TOÀN CHỮ HOA của tiếng Anh

Tín hiệu mạnh nhất ở cả ba thứ tiếng là **danh xưng đứng cạnh tên**: `ja` hậu tố kính ngữ
(さん/様/ちゃん…), `en` chức danh đứng trước (Sir/Lord/Master…), `zh` hậu tố xưng danh
(大人/前辈/师父…). Chỉ những ứng viên có bằng chứng loại này mới được đoán `type_guess =
character_name`.

**Bẫy:** chữ lồng truyện tranh tiếng Anh rất hay viết hoa toàn bộ. Lúc đó tín hiệu "viết hoa =
tên riêng" **chết hoàn toàn**, và luật ngây thơ trả về *mọi từ* trong chapter. Nên hệ thống đo tỉ
lệ chữ hoa của chính chapter (`NGUONG_CHU_HOA = 0.70`) rồi đổi sang luật tần suất + danh sách
chặn, và **nói ra trên giao diện** nó đang dùng luật nào.

**Đầu câu — chỗ tinh tế nhất.** Từ viết hoa đầu câu viết hoa vì ngữ pháp ⇒ tự nó không phải bằng
chứng. Nhưng nếu từ đó đã được chứng minh ở chỗ khác thì những lần nó đứng đầu câu **vẫn là những
lần xuất hiện thật**. Hiện thực bằng hai lượt:

```
"I met Pepper today. Pepper was tired."   -> Pepper: 2 lần   (lượt 1 chứng minh, lượt 2 đếm thêm)
"Pepper was tired. Pepper slept."         -> không có gì     (chưa từng có bằng chứng)
```

### E17.4 Đếm theo LẦN XUẤT HIỆN, không theo lần khớp luật

`ペッパーさん` khớp cả luật hậu tố lẫn luật katakana. Cộng theo số lần khớp luật thì con số hiện
cho người dùng bị thổi gấp đôi — và đó chính là con số họ dựa vào để duyệt. `UngVien.vi_tri` giữ
`(vùng, đầu, cuối)` của từng lần đã đếm; lý do đầy đủ nằm ở đó. Cùng loại bẫy với chế độ chỉ-đếm
của P3f.

### E17.5 Cổng đối chiếu của tầng 3

```
danh sách ứng viên (tầng 1)  ──►  prompt: "điền cách dịch cho ĐÚNG danh sách này"
                                          │
                     model trả lời ───────┤
                                          ▼
                        mỗi dòng phải nhắc lại NGUYÊN VĂN thuật ngữ đã hỏi
                              khớp ──► giữ, nhãn `goi_y_mo_hinh_chua_duyet`
                            không ──► LOẠI + dropped_count += 1
```

`dropped_count > 0` là **bằng chứng model có bịa** trong lượt đó — lưu vào CSDL, không chỉ log.
Prompt có chừa đường cho model nói **"không biết"** (`?`), và câu đó **không** tính là bịa: ép
model đoán là tự tạo ra dữ liệu giả.

### E17.6 Ranh giới cứng

- Tầng 1+2 **không ghi một dòng nào** vào `glossary_entry` / `character_voice_profile`.
- Tầng 3 lưu ở bảng riêng `term_suggestion_run` (project-level; không mượn `Job` vì `Job.page_id`
  là NOT NULL), **không** tạo thuật ngữ.
- Giao diện **không có nút "Duyệt tất cả"** — `target_term`/`definition` là quyết định biên tập.
- Không có ứng viên nào ⇒ **không gọi mô hình**: hỏi suông vẫn tốn tiền, và câu trả lời cho một
  danh sách rỗng chắc chắn là bịa.
- Vùng OCR `needs_manual` **bị bỏ nhưng có đếm và báo ra** — rút thuật ngữ từ chữ đọc sai đẻ ra
  danh sách rác mà người dùng không có cách nào biết.

## B1. Ai được đụng vào cái gì — tài khoản & chủ sở hữu chapter (2026-09-04)

### B1.1 Hai lớp, và ranh giới giữa chúng

Hệ thống có **hai** cơ chế chặn, làm hai việc khác nhau. Lẫn hai thứ này là nguồn hiểu nhầm
nguy hiểm nhất ở đây:

| | Slice A — khoá chung | Slice B — tài khoản |
|---|---|---|
| Là gì | Một chuỗi bí mật cho cả hệ thống | Email + mật khẩu riêng từng người |
| Header | `X-API-Key` | `Authorization: Bearer <mã phiên>` |
| Trả lời được câu hỏi | "Người này có phải người lạ không?" | "Người này **là ai**?" |
| Sau slice B còn gác gì | **Chỉ** `/auth/register` | Toàn bộ `/api/v1` còn lại |

Trước slice B, khoá chung gác toàn bộ dữ liệu — nghĩa là ai cầm khoá cũng đọc/xoá được chapter
của mọi người. Sau slice B, **khoá chung không mở được dữ liệu nữa**.

Vì sao đã đăng nhập thì không cần khoá chung: nếu bắt gửi cả hai, muốn cho ai dùng cũng phải
phát cho họ khoá chung — mà cầm khoá chung là tạo được tài khoản cho người khác.

### B1.2 Đường đi ngược từ một bản ghi về chủ của nó

Chỉ 16/65 endpoint nhận thẳng `project_id`. **43 endpoint tới chapter bằng đường gián tiếp** —
qua `page_id`, `region_id`, `job_id`, hoặc id của bảng con. Rải kiểm quyền thủ công ở từng chỗ
là cách chắc chắn để sót một cái, và cái bị sót sẽ là cái không ai ngờ.

Nên có **một** bộ giải quyền, đi ngược chuỗi cha bằng bảng tra (`app/core/quyen.py`, `_CHA`):

```
OCRResult ─┐
Translation ─┼─ region_id ─→ TextRegion ─ page_id ─→ Page ─┐
TypesetResult ┘                                            │
Job, BatchItem ──────────── page_id ─→ Page ───────────────┼─ project_id ─→ Project.chu_so_huu_id
ExportJob, BatchRun, GlossaryEntry, VoiceProfile, … ───────┘
```

Bảng `_CHA` là **danh sách trắng**: bảng nào chưa khai trong đó sẽ bị `project_id_cua` ném
`TypeError` thẳng, chứ không lọt qua im lặng. Thêm bảng mới mà quên khai ⇒ nổ ngay, không âm
thầm bỏ kiểm quyền.

### B1.3 Ba mức "không được vào", và vì sao đều trông giống nhau

| Tình huống | Mã trả về |
|---|---|
| Không gửi mã phiên / mã sai / mã hết hạn | `401` |
| Có phiên, nhưng chapter không tồn tại | `404` |
| Có phiên, chapter tồn tại nhưng **của người khác** | `404` — *cùng câu chữ với dòng trên* |

Hai dòng cuối cố ý không phân biệt. Trả `403` cho dòng cuối là xác nhận "id này có thật", và
người dò sẽ quét id để lập danh sách chapter tồn tại.

Cùng logic đó áp cho đăng nhập: "email không tồn tại", "sai mật khẩu" và "tài khoản bị khoá" trả
**y hệt** nhau — và khi email không tồn tại, hệ thống vẫn **băm một mật khẩu giả** để không lộ
qua chênh lệch thời gian (1ms so với 83ms là đủ để dò ra danh sách email có thật).

### B1.4 Chapter chưa có chủ

Chapter tạo trước slice B có `chu_so_huu_id = NULL`. Lúc migration chạy thì **chưa có tài khoản
nào tồn tại** để gán, nên gán bừa là đoán mò và giấu đi là làm mất việc của người dùng.

Quy ước: `NULL` = "chưa có chủ" — mọi tài khoản đăng nhập đều thấy, kèm nhãn phân biệt, và nhận
về được. Nhận rồi thì người khác mất quyền ngay và không cướp lại được.

Từ slice B trở đi **không còn đường nào sinh chapter vô chủ**: `create_project` luôn đặt chủ.

### B1.5 Vì sao mã phiên trong CSDL chứ không phải JWT

JWT không thu hồi được. Bấm "đăng xuất" mà token vẫn sống tới lúc hết hạn là hành vi sai. Mã
phiên đục tra trong CSDL thì xoá một dòng là mất hiệu lực tức thì; giá phải trả là một truy vấn
mỗi request, mà đằng nào mỗi request cũng đã mở một phiên CSDL rồi.

**Mật khẩu băm scrypt (83ms), mã phiên băm SHA-256 — không mâu thuẫn.** scrypt cố tình chậm để
chống dò thứ *người nghĩ ra* (ít entropy). Mã phiên là 256 bit ngẫu nhiên từ máy: không có gì để
đoán, nên scrypt ở đó chỉ tốn 83ms mỗi request mà không mua thêm chút an toàn nào. Nhưng vẫn
**phải băm** trước khi lưu — kẻ đọc trộm được CSDL sẽ mạo danh được ngay mà không cần mật khẩu.

## F1. Font thiếu glyph — vì sao một dấu chấm giết được cả trang (2026-09-04)

### F1.1 Chuyện đã xảy ra

Chapter thật trên bản chạy: 8 vùng, detect 49,5s → OCR 39,4s → xoá chữ 13,1s → dịch 9,6s, tất cả
đạt. Bước căn chữ **thất bại sau 0,034 giây**:

```
MissingGlyph: font thiếu glyph cho '．' — sẽ render ra ô vuông
```

`．` là U+FF0E, dấu chấm **toàn rộng** của tiếng Nhật, khác `.` (U+002E). Engine dịch
(`google_fast`) đổi chữ sang tiếng Việt nhưng **bê nguyên dấu câu kiểu Nhật** sang. Đo lại cả 7
font trong whitelist: không font nào có glyph cho `．，！？：；（）「」『』。、・〜～－‥`, và font nào
cũng có đủ `. , ! ? : ; ( ) " ' - ~ · — … “ ”`.

Ba khuyết tật độc lập cùng lộ ra trong một sự cố, và cả ba đều đã sửa.

### F1.2 Gấp dấu câu — ranh giới "xếp chữ" và "dịch hộ"

`normalize_for_layout()` gấp dấu câu toàn rộng/CJK về dạng nửa rộng **trước khi đo và vẽ**. Bản
dịch trong `TranslationResult` không bị đụng tới; thứ đi qua đây là chuỗi đem vẽ (`wrapped_text`).

Đây không phải sửa nội dung: `．` và `.` là cặp tương đương tương thích của Unicode, chỉ khác bề
rộng ô chữ — thứ chỉ có nghĩa khi xếp chữ **dọc** kiểu Nhật.

Bảng viết **tường minh** thay vì gọi thẳng NFKC: NFKC còn đổi `㎏`→`kg`, `①`→`1`, chữ ghép… rộng
hơn hẳn thứ cần và khó test cho hết.

Ranh giới cứng: `ー` (U+30FC, dấu kéo dài âm của kana) **không** nằm trong bảng. Nó là một phần
của *từ* tiếng Nhật chứ không phải dấu câu; đổi nó thành `—` là dịch hộ người dùng. Kana/kanji
còn sót cũng vậy — vùng đó phải kêu lên, và F1.3 lo phần kêu.

### F1.3 Một vùng hỏng không được giết cả trang

Trước F1, vòng lặp căn chữ gọi `fit()` cho từng vùng và **không ai bắt** `MissingGlyph`. Một ký
tự sai kiểu ở vùng thứ 8 xoá sạch công của 7 vùng kia: job hỏng, trang giữ `translated`, người
dùng không nhận được gì.

Từ F1, vùng không vẽ được nhận `fit_status = font_missing_glyph` và **các vùng khác vẫn đi tiếp**.

Vì sao là trạng thái RIÊNG chứ không dùng lại `pending`: `pending` nghĩa là "không có chữ để
chèn". Vùng này **có chữ**, dịch xong hẳn hoi, nhưng chèn không được. Gộp hai thứ lại thì một
bong bóng **mất chữ** trông y hệt một bong bóng vốn dĩ trống — và người dùng mang file đi mà
không biết mình mất gì. Trạng thái riêng thì đếm được, hiện được, và chặn được ở cổng xuất.

Trường hợp **mọi** vùng đều hỏng thì job vẫn báo hỏng như cũ: công bố một trang trắng rồi gọi nó
là "đã căn chữ" còn tệ hơn báo lỗi.

Đường sửa tay một vùng (`re-fit`) **cố ý giữ nguyên hành vi cũ** — ném lỗi. Người dùng đang yêu
cầu đúng vùng đó; nuốt lỗi rồi trả về "xong" là nói dối thẳng vào mặt người hỏi.

### F1.4 Lỗi phải tự hiện ra

Cơ chế báo lý do có từ P3j, nhưng nằm sau nút "Vì sao?" — phải bấm mới biết. Trang đứng ở
`translated`, mà `translated` không thuộc nhóm "đã xong", nên màn tiến độ quay *"đang cập nhật…"*
vô hạn. Người dùng đợi **10 phút** một việc đã chết sau 34 mili giây.

Sửa: thêm `GET /projects/{id}/failed-jobs` (một lời gọi cho cả chapter, chỉ trả job hỏng **mới
nhất của mỗi trang**), màn tiến độ hỏi ngay lúc mở và mỗi nhịp, hiện thẳng "bước nào hỏng + lý
do". Trang đã có việc hỏng thì **thôi tính là đang chạy** — vòng quay quanh một cái xác là nói
dối bằng hoạt hình.

Nút "Vì sao?" vẫn còn cho trường hợp trang đứng im mà **không** có job hỏng nào (worker chết
giữa chừng, việc treo ở `running`): lúc đó không có gì để hiện sẵn, phải hỏi mới biết.

## A1. Nới khung ra chỗ trống — khi không tách được bong bóng khỏi nền (2026-09-04)

### A1.1 Vì sao E14 bó tay trên manga đen trắng

E14 tìm bong bóng bằng **ngưỡng sáng**: vùng sáng + ít bão hoà, rồi chọn đường viền khít nhất
chứa tâm bbox. Cách đó đúng với truyện màu — bong bóng trắng nổi hẳn trên nền vẽ có màu.

Manga đen trắng phá vỡ tiền đề đó: bong bóng trắng nằm trên **trang cũng trắng**. Vùng sáng loang
ra hết cả ROI, nên ứng viên chứa tâm hoặc chạm biên ROI hoặc chiếm gần hết ROI — cả hai đều bị
loại đúng theo luật, và đúng ra phải bị loại: đó **thật sự** không phải hình bong bóng.

Đo trên trang thật của người dùng (04/09): `shape_derived: 0/8`.

### A1.2 Vấn đề nằm ở khung dự phòng, không nằm ở phép tách

Rơi về dự phòng thì khung chữ = **bbox của bộ nhận diện, thụt vào**. Với manga chữ dọc, bbox đó
là **cột chữ Nhật**: cao và rất hẹp. Chữ Việt viết ngang nhét vào cột hẹp thì mỗi dòng 2–3 ký
tự, và tràn khung ngay cả ở cỡ chữ nhỏ nhất — trong khi lòng bong bóng còn trống mênh mông ngay
bên cạnh.

### A1.3 Không tách bong bóng nữa, chỉ nới cho tới khi chạm mực

Viền bong bóng **là nét mực**. Nên bỏ hẳn việc phải tách bong bóng khỏi nền: nới khung ra bốn
phía chừng nào **dải mới còn sạch hoàn toàn**, phép nới tự dừng ở mép trong của viền. Cả hai
phía đều trắng cũng không sao — cái ngăn chúng là nét mực, không phải độ sáng.

Hệ quả đáng giá: vùng chữ **ngoài** bong bóng (tiếng động, chữ trên nền vẽ) thì nét vẽ chặn ngay,
khung gần như không nới được. Không cần luật riêng cho trường hợp đó.

### A1.4 Ranh giới: nới khung KHÔNG phải là nhận ra bong bóng

`source` vẫn là `fallback_rectangle`, mọi lý do vì sao E14 bó tay được giữ nguyên, chỉ thêm mã
`fallback_grown_to_free_space`. Một cái khung rộng hơn không phải bằng chứng về hình bong bóng —
và E14 tồn tại chính là để không nhận vơ mức chắc chắn mình không có.

### A1.5 Hai con số phải chọn đúng, đã trả giá để biết

**Thứ tự nới**: một thứ tự cố định làm ô bị khoá ở dạng cao-hẹp (44×280 → 166×352). Thử **ba**
thứ tự rồi lấy ô lớn nhất — đúng bài học `layout.py` đã học một lần.

**Thước đo giới hạn**: chặn theo cạnh **DÀI** của bbox, không phải cạnh tương ứng. Cột chữ rộng
44px mà chặn ngang theo 44 thì khung không bao giờ vượt 176px. Bong bóng gần vuông, khung chữ
bên trong có thể rất dẹt — cạnh dài mới nói lên "bong bóng này to cỡ nào".

Đo cuối: ô đặt chữ 36×230 → **232×320**, cỡ chữ **10 → 28**, ngắt dòng từ 15 mẩu vụn còn 5 dòng.

### A1.6 Bố cục chỉ được tính lúc xoá chữ — nên phải có nút tính lại

`retry-safe-area` có từ E14 nhưng chưa nút nào gọi. Không có nút thì mọi bản sửa hình học chỉ ăn
vào trang **tải lên mới**; trang đang làm dở không có đường nào chạm tới. Nay nút "Tính lại bố
cục cả trang" nằm ngay thẻ hình bong bóng ở màn sửa tay.

Cố ý **không** tự tính lại hàng loạt cho mọi trang cũ: đổi bố cục của một trang người dùng đã sửa
tay xong là phá việc của họ mà không ai xin phép.

## E18. Sức chứa bong bóng — vì sao bước dịch phải biết chỗ trống có bao nhiêu (2026-09-05)

### E18.1 Giới hạn mà A1 không chạm tới được

A1 nới khung ra hết lòng bong bóng, và trên trang thật đưa số vùng tràn từ 3 xuống 2. Hai vùng
còn lại tràn vì lý do khác hẳn: khung đã trùm gần hết bong bóng, mà bản dịch vẫn dài hơn chỗ
chứa — 105 ký tự tiếng Việt trong một bong bóng vẽ vừa ~30 ký tự tiếng Nhật.

Tiếng Nhật viết cực gọn: một kanji thay cho cả một từ tiếng Việt. Bong bóng được hoạ sĩ vẽ vừa
đúng lượng chữ Nhật, nên bản dịch dài gấp hai ba lần là **chuyện thường**, không phải sự cố.

Tới đó không cách xếp chữ nào cứu được nữa. Chỗ duy nhất còn sửa được là chính bản dịch.

### E18.2 Chỗ hổng trong kiến trúc: dịch xong rồi mới đi tìm chỗ nhét

Pipeline hiện tại là một chiều: detect → OCR → xoá chữ → **dịch** → căn chữ. Bước dịch không hề
biết bong bóng to bao nhiêu; bước căn chữ biết thì đã muộn, nó chỉ còn cách báo tràn.

E18 nối chỗ hổng đó bằng một con số: **sức chứa** — khung này chứa được bao nhiêu ký tự tiếng
Việt ở một cỡ chữ đọc được.

### E18.3 Sức chứa đo bằng chính font sẽ vẽ, và là ƯỚC LƯỢNG

Đo bề rộng trung bình thật của một mẫu chữ Việt có dấu qua đúng `FontResolver` của M6 — không
bảng tra đoán sẵn, đổi font là số tự đổi.

Nhưng bề rộng từng ký tự khác nhau và chỗ ngắt dòng phụ thuộc dấu cách, nên **không con số nào
đúng tuyệt đối**. Vì vậy sức chứa không bao giờ được dùng làm lời khẳng định: sau khi dịch lại
vẫn chạy `fit()` thật, và vẫn tràn thì vẫn báo tràn. M6 giữ nguyên vị trí bên duy nhất có thẩm
quyền nói "vừa khung".

### E18.4 Vì sao rút gọn là NÚT BẤM chứ không phải mặc định

Rút gọn là **làm mất chữ** của bản dịch đầy đủ. Máy tự quyết định bỏ bớt lời thoại của người
khác là việc không ai xin — cùng một ranh giới với E12 (máy chỉ ra chỗ, không tự sửa) và E13
(gợi ý thuật ngữ phải người duyệt).

Thêm hai lý do kỹ thuật: đường `google_fast` không nhận chỉ dẫn độ dài (Google Translate chỉ
dịch, không nghe lời), và chỉ hỏi mô hình về đúng những vùng tràn thì cả trang 8 vùng chỉ tốn
token cho 2.

### E18.5 Ranh giới với chữ người dùng đã gõ

Vùng có `edited_by_user` **không bị đụng tới**, và số vùng bị bỏ qua được trả về chứ không im
lặng. Bản dịch người dùng tự gõ không có chỗ nào lưu lại để hoàn tác — đè lên nó là mất hẳn.

Tương tự, model trả rác / viết dài thêm / thiếu dòng đều dẫn tới **giữ nguyên bản cũ**; model
hỏng hẳn thì job `failed` và không vùng nào bị đổi. Một trang nửa cũ nửa mới là thứ không ai lần
ra được về sau.

## E19. Tiện ích "Dịch truyện đang đọc" — phủ chữ lên bất kỳ trang nào (2026-09-05..07)

### E19.1 Vì sao là tiện ích RIÊNG, không phải bản nâng cấp E1

`extension/PRIVACY.md` (E1) hứa nguyên văn: không đọc trang đang xem, không tự tải ảnh, không
phủ bản dịch lên trang. E19 cần cả ba — sửa E1 mà giữ PRIVACY.md cũ là biến tài liệu đúng thành
tài liệu nói dối; sửa cả hai thì người cài E1 *vì đúng những lời hứa đó* bị đổi bản chất dưới
chân. Nên: tiện ích riêng (`extension-doc-truyen/`), PRIVACY.md riêng, E1 giữ nguyên không đụng.

### E19.2 Cổng chặn đã đo, và tại sao hình dung ban đầu không sống được

Giả thuyết ban đầu — bỏ bước xoá chữ để mô hình nằm lại bộ nhớ, trang sau nhanh hơn một bậc — đo
ra **SAI** (`docs/REPORT_E19_0_DO_COND_CHAN.md`): nạp mô hình chỉ tốn 0,3–0,5s, chi phí thật nằm
ở suy luận CTD (~40–50s, CPU-bound, không nóng lên). Hình dung sống được: **bấm để xếp hàng, đọc
tiếp, lát sau chữ hiện ra** — không phải "bấm là hiện chữ ngay".

### E19.3 Chế độ pipeline `chi_chu` — nối dây, không viết lại logic

Thêm `ChePipeline.chi_chu` vào `Project`: sau OCR xếp thẳng sang dịch, **bỏ qua xoá chữ (LaMa) và
căn chữ**. Đã kiểm trước khi làm: `_run_translate` chỉ đọc `TextRegion`/`OCRResult` từ CSDL,
không chạm ảnh clean hay kho lưu trữ — hai bước bị bỏ chỉ đang được nối chuỗi theo thói quen của
pipeline gốc (M2→M6), không phải phụ thuộc thật. `PageStatus.translated` là **đích cuối** của chế
độ này; nó không bao giờ tới `typeset_done`.

### E19.4 Endpoint gộp — vì sao không bắt tiện ích tự nối 4 lời gọi

`POST /api/v1/doc-truyen/trang` nhận thẳng file ảnh, tự tạo (hoặc tái dùng) một chapter ẩn tên
`"Đọc nhanh (tiện ích) — {source_lang}"` cho từng (tài khoản, ngôn ngữ nguồn) (`_chapter_doc_nhanh`),
set `che_do_pipeline=chi_chu` và `intended_use=personal` **ngay từ đầu** — đây là khai báo trung
thực nhất cho đúng việc tiện ích làm (dịch trang đang tự đọc), và **không phải đường vòng né cổng
M10**: `Project` này vẫn đi qua đúng constraint `intended_use NOT NULL` như mọi chapter, chỉ khác
là được điền hộ thay vì hỏi qua UI vì tiện ích không có màn tạo chapter. Cổng nhắc-trách-nhiệm của
M10 nằm ở bước **xuất file** — tiện ích này không bao giờ xuất, nên cổng đó không áp dụng, không
phải bị né.

**Một chapter riêng cho mỗi ngôn ngữ nguồn, không dồn chung** (thêm 07/09, sau sự cố MangaPlus ở
§E19.6b): `source_lang` chốt lúc tạo `Project` và quyết định chọn engine OCR (manga-ocr cho `ja`,
PaddleOCR cho `zh`/`en` — hợp đồng M3). Bấm dịch cùng tài khoản nhưng khác ngôn ngữ trang mà dồn
vào một chapter thì sẽ có trang chạy sai engine kể cả khi người dùng đã chọn đúng lần đó — vì
chapter nhớ `source_lang` cố định từ lần tạo đầu tiên, không phải theo từng trang.

`GET /api/v1/doc-truyen/trang/{page_id}` trả **vùng đã có kể cả khi chưa xong hết trang** — dịch
xong bong bóng nào tiện ích phủ được bong bóng đó, không đợi cả trang. `started_at` (E19-3 kế
hoạch, đã có trên `Job` từ trước) phân biệt "đang chờ" với "đang chạy": không có nó, người dùng
không biết mình còn chờ 5 giây hay 5 phút sau N việc xếp trước.

### E19.5 Chọn ảnh + quy đổi toạ độ — hai module thuần, test không cần trình duyệt

`chonTrangTruyen` (thuần, `src/lib/chon-anh.js`) loại ảnh theo cạnh/diện tích tối thiểu, tỉ lệ dẹt
(banner), bị thu nhỏ nhiều (thumbnail), ngoài khung nhìn, rồi chấm điểm phần còn lại theo **diện
tích đang hiện trong khung nhìn** — không phải theo pixel thật. `quyDoi` (thuần, `src/lib/toa-do.js`)
đổi toạ độ vùng từ pixel ảnh gốc sang pixel hiển thị bằng tỉ lệ `clientWidth/naturalWidth`.

**Sự cố thật trên `reddit.com/r/translator` (07/09), sửa qua 3 lượt:**

1. Lớp phủ dùng `absolute` + toạ độ tài liệu, gắn vào `<body>` — rơi lệch trên trang có lightbox vì
   `absolute` neo theo tổ tiên **đã định vị** gần nhất, không phải theo tài liệu; cộng thêm
   `scrollY` của trang nền (không cuộn) càng lệch thêm. Sửa: `fixed` + toạ độ khung nhìn (đúng thứ
   `getBoundingClientRect()` trả sẵn), gắn vào `<html>`.
2. Bảng debug (in thẳng 3 số đo vào thông báo: khung ảnh, khung lớp phủ, kích thước thật — vì ảnh
   chụp màn hình cho thấy "sai" mà không cho biết sai ở đâu) lộ ra: `chonTrangTruyen` chọn nhầm
   **ảnh nền mờ phóng to** của lightbox — cùng `src` với ảnh thật (750×750) nhưng hiển thị
   2304×1134, chiếm khung nhìn nhiều hơn bản rõ nên thắng phép chấm điểm. Hai bản cùng src nên
   không phân biệt được bằng kích thước — chỉ CSS `filter: blur(...)` (đọc cả tổ tiên, tối đa 4
   cấp) mới lộ ra bản nào là trang trí.
3. Nền hộp dịch để hở 6% (`rgba(255,255,255,.94)`) — chữ Nhật gốc mờ lộ ra sau chữ Việt vì chế độ
   này không xoá chữ khỏi ảnh. Đặt về đục hoàn toàn (`1`).

### E19.6 Cỡ chữ: ước lượng trước, đo thật sau

`coChu()` (thuần) ước lượng cỡ chữ ban đầu bằng `sqrt(diện_tích / số_ký_tự)`, không đo chữ thật —
không có gì bảo đảm khớp khung vì không chạy bước căn chữ của bản web (E19 cố ý bỏ, xem E19.3).
Content script co dần font-size **sau khi hộp đã vào DOM**, đo thật bằng `scrollHeight`/
`scrollWidth`, dừng khi vừa khung hoặc chạm sàn 8px. Cuộn trong ô (`overflow:auto`) là lưới an
toàn cuối cùng, không phải cách chính.

### E19.6b Sự cố thật trên MangaPlus — `blob:` chỉ sống trong đúng tài liệu tạo ra nó (2026-09-07)

Đo được sau khi phát hành v0.1.5: trên `mangaplus.shueisha.co.jp/viewer/...`, mọi lượt bấm dịch
đều báo lỗi mạng trần trụi **"Failed to fetch"**, không kèm mã HTTP nào. Người dùng bị chặn cả
chuột phải lẫn phím tắt mở DevTools (F12/Ctrl+Shift+I) nên không tự soi DOM được — thêm bảng
chẩn đoán (v0.1.6, cùng cách đã dùng cho lỗi lớp phủ §E19.5) in thẳng `src` của ảnh đã chọn vào
thông báo lỗi, lộ ra: `blob:https://mangaplus.shueisha.co.jp/1844e8f7-...`.

**Nguyên nhân:** MangaPlus tự giải mã ảnh trang truyện bằng JS của chính trang, rồi phát qua
`<img src="blob:...">` thay vì URL ảnh tĩnh thường. `blob:` URL chỉ dereference được từ ĐÚNG
NGỮ CẢNH THỰC THI đã tạo ra nó (document của trang) — service worker của tiện ích là một tiến
trình khác dù cùng origin, nên `fetch()` một `blob:` như vậy **luôn** hỏng. Đây không phải lỗi
cấu hình hay thiếu quyền — không `host_permissions` nào sửa được.

**Sửa:** đảo ngược đúng phần lý luận ở đầu `service-worker.js` (giả định gốc: mọi ảnh nên tải ở
service worker để tránh nhiễm bẩn canvas — đúng cho ảnh `https://` không CORS, nhưng SAI cho
`blob:`/`data:` do chính trang tạo). Content script giờ **thử đọc bằng canvas tại chỗ trước**:
vẽ `<img>` lên `<canvas>` cùng tài liệu (không nhiễm bẩn vì `blob:` cùng gốc với trang), xuất
`Blob` → base64, gửi kèm byte thay vì chỉ gửi URL. Canvas lỗi (ảnh `https://` cross-origin không
CORS — trường hợp phổ biến hơn) thì rơi về đường cũ: gửi URL để service worker tự tải bằng
`host_permissions`. Không đoán trước loại ảnh nào đi đường nào — thử rồi mới biết.

### E19.6c Chữ trên ảnh không phải luôn là tiếng Nhật — thêm ô chọn `source_lang` (2026-09-07)

Sửa xong §E19.6b, dịch được trang MangaPlus — nhưng **ra chữ vô nghĩa** ("2010BSTACLE
SISGHTANDTHEEANEMAN..."). Nguyên nhân khác hẳn: trang này là **bản tiếng Anh chính thức** của
MangaPlus (chữ Latin, không phải tiếng Nhật), mà `_chapter_doc_nhanh` trước đó **hardcode
`source_lang=SourceLang.ja`** — mọi trang tiện ích gửi lên đều bị ép chạy qua `manga-ocr` (huấn
luyện cho tiếng Nhật). manga-ocr đọc chữ Latin ra chuỗi rác gần giống chữ (không phải lỗi rõ ràng
kiểu crash), bước dịch dịch tiếp chuỗi rác đó — sai chồng sai mà cả hai bước đều "chạy xong bình
thường", không có tín hiệu lỗi nào để tự phát hiện.

**Đây không phải lỗi hiếm** — E19 chủ đích "bất kỳ trang nào" (§E19 mở đầu), và rất nhiều manga
đọc online là bản dịch tiếng Anh/Trung chính thức chứ không phải bản gốc tiếng Nhật. Hardcode một
ngôn ngữ nguồn duy nhất mâu thuẫn thẳng với chính mục tiêu đó.

**Sửa:** thêm `source_lang` (`ja`/`zh`/`en`, mặc định `ja` — giữ hành vi cũ cho ai chưa biết tới
tuỳ chọn này) vào form-data của `POST /doc-truyen/trang`, và một ô chọn trong trang Tuỳ chọn của
tiện ích ("Ngôn ngữ chữ TRÊN trang truyện đang đọc" — cố ý ghi rõ đây là chữ trên ảnh, không phải
ngôn ngữ muốn đọc, để không lặp lại đúng cách hiểu nhầm vừa gặp). Đổi lưu ngay, không cần đăng
nhập lại — đây là thuộc tính của trang đang đọc, không phải của tài khoản.

### E19.6d Popup khi bấm icon, và bẫy thư mục unpacked đổi ID (2026-09-08)

Hai phản hồi liền sau §E19.6c: (1) bấm icon không thấy ô chọn ngôn ngữ đâu — phải mở riêng trang
Tuỳ chọn mới đổi được, và (2) bấm icon có lúc không phản ứng gì (Chrome hiện "Không có quyền truy
cập cần thiết" trong menu mảnh ghép tiện ích).

**Nguyên nhân (2) hoá ra là do quy trình phát hành, không phải lỗi mã nguồn:** gói tải về trước
đó đặt tên kèm số phiên bản (`dich-truyen-dang-doc-v0.1.X.zip`). Trình giải nén không thấy một
thư mục gốc chung bên trong zip nên tự tạo thư mục MỚI **trùng tên zip** — khác tên zip là khác
đường dẫn, mà ID của tiện ích "Tải đã giải nén" tính theo đúng đường dẫn đó. Mỗi bản là một thư
mục mới ⇒ một ID mới ⇒ Chrome coi là **cài đặt hoàn toàn mới**: mất quyền site đã cấp, mất phiên
đăng nhập, phải làm lại từ đầu mỗi lần cập nhật — đúng những gì hai phiên trước đã phải lặp lại.
Sửa: bỏ số phiên bản khỏi tên gói (`dich-truyen-dang-doc.zip`, cố định), và README nói rõ phải
giải nén **đè vào đúng thư mục cũ** rồi bấm Tải lại trên `chrome://extensions`, không tạo thư mục
mới.

**Sửa (1):** thêm `action.default_popup` (`src/popup/index.html`) vào manifest — Chrome quy định
có `default_popup` thì **không bao giờ gửi `chrome.action.onClicked` nữa**, nên toàn bộ việc tiêm
content script (trước đây nằm trong service worker) phải dời hẳn vào script của popup, không phải
thêm — để lại ở service worker sẽ là mã chết, không báo lỗi gì nên rất dễ tưởng nhầm vẫn còn chạy.
Popup gọn: một ô chọn ngôn ngữ (đọc/ghi cùng khoá `chrome.storage.local` với trang Tuỳ chọn, đổi
là lưu ngay) + nút "Dịch trang này" + link mở trang Tuỳ chọn đầy đủ (địa chỉ máy chủ, đăng nhập).

### E19.6e "Xong" mà không hiện gì — `<img>` gốc chết trong lúc chờ 45 giây (2026-09-08)

Test lại trên MangaPlus với `source_lang=en`: bảng debug báo `ảnh: 0,0 0x0` và `lớp phủ: KHÔNG
CÓ`, nhưng thông báo cuối vẫn nói **"Xong: 11/17 bong bóng có bản dịch"**. Người dùng không thấy
gì trên trang — đúng, vì `vePhu()` đã tự gỡ lớp phủ (nhánh `!el.isConnected` trong `ve()`, xem
§E19.5) ngay khi phát hiện phần tử `<img>` đã chết, nhưng đường xử lý chính không hề biết việc gỡ
đó đã xảy ra, cứ báo "Xong" như không có gì.

**Nguyên nhân:** một trang tốn ~45 giây (đo `REPORT_E19_0`), và trong lúc đó chính trang web (SPA)
tự vẽ lại/gỡ node `<img>` gốc — có thể do cuộn, có thể do trang tự làm mới nội dung. `anh.el` được
chụp lại từ đầu quy trình; 45 giây sau nó có thể không còn nằm trong tài liệu nữa. Đây là hệ quả
tất yếu của "bấm để xếp hàng, đọc tiếp" (§E19.2) — độ trễ dài là đánh đổi đã chọn, và đổi lại là
tham chiếu phần tử có thể chết giữa chừng trên trang càng động.

**Không tự chọn lại phần tử khác để vẽ bù** — thử re-run `chonTrangTruyen` ngay trước khi vẽ có
vẻ là sửa tận gốc, nhưng nếu người dùng đã cuộn sang trang khác trong lúc chờ, phần tử chọn lại
sẽ là TRANG KHÁC — vẽ nhầm bản dịch lên nhầm trang còn tệ hơn không vẽ gì. **Sửa bằng cách nói
đúng sự thật**: kiểm `anh.el.isConnected` và sự tồn tại của lớp phủ ngay sau khi gọi `vePhu()`;
mất một trong hai thì thay thông báo "Xong" bằng lý do + hướng xử lý (cuộn về đúng trang, bấm lại
— báo trước là ảnh `blob:` đổi địa chỉ mỗi lần tạo nên khó dùng lại bản dịch vừa xong, phải chờ
lại từ đầu). Im lặng "thành công" khi màn hình trống là vi phạm evidence-first (`CLAUDE.md` #3).

### E19.6f Xếp hàng trước 1 trang theo nhịp đọc (2026-09-08)

Phản hồi sau khi các lỗi trên đã sửa: 45 giây/trang "không đáp ứng được", đề nghị tự động dịch
**toàn bộ chapter/toàn bộ truyện**. Từ chối thẳng hướng đó — hai lý do, cả hai đều đã đứng trong
`PLAN_E19` §8 từ lúc lập kế hoạch, không phải phát sinh mới:

1. **Không nhanh hơn.** Máy chủ chạy đúng 1 việc/lúc (CPU-bound, không phải hàng đợi mạng — đo
   `REPORT_E19_0`). Xếp 20 trang thì trang thứ 20 vẫn đợi ~15 phút; tổng thời gian không đổi, chỉ
   dời chỗ chờ.
2. **Ranh giới bản quyền.** MangaPlus là app đọc chính thức có DRM chủ đích (mã hoá ảnh thành
   `blob:`, chặn chuột phải + DevTools — xem §E19.6b). Tự động quét-dịch cả chapter/cả truyện mà
   không cần người bấm từng trang là hành vi của **công cụ tải hàng loạt nội dung có bản quyền**,
   khác hẳn "phụ đề khi tự đọc".

**Hướng đã chọn — xếp hàng trước ĐÚNG MỘT trang, gắn liền với mỗi lần bấm của người dùng, không
chạy nền độc lập.** Mỗi lần dịch xong một trang (dù lấy từ cache hay dịch mới), tự tìm trang KẾ
TIẾP đã có sẵn trong DOM (`chonTrangKeTiep`, dùng lại đúng bộ lọc chất lượng của `chonTrangTruyen`
qua `loaiDoChatLuong` dùng chung — tách hàm để hai nơi không lệch luật) và âm thầm gửi dịch trong
nền, không vẽ, không thông báo. Lần người dùng cuộn tới và bấm dịch trang đó, bản dịch đã có sẵn
trong `daDich` — hiện ngay, không chờ 45 giây nữa.

Vẫn cần bấm cho MỖI trang (không tự vẽ lớp phủ khi chưa ai bấm — giữ đúng nguyên tắc "chỉ đọc
trang khi bạn bấm" của `PRIVACY.md`), chỉ là độ chờ giữa các lần bấm gần như biến mất nếu đọc đúng
nhịp. Đây là hiện thực hoá đúng cách dùng đã ghi sẵn ở README từ đầu ("bấm dịch trang kế trong lúc
đang đọc trang hiện tại") — trước đây người dùng phải TỰ nhớ bấm trước, giờ tiện ích tự làm hộ.

**Chỉ hoạt động trên trang cuộn dọc liên tục** giữ sẵn vài trang kế cận trong DOM (đo trên
MangaPlus: 22-36 `<img>` cùng lúc). Trang kiểu "bấm Tiếp" mới nạp ảnh mới thì `chonTrangKeTiep`
trả `null` — không có gì để xếp hàng, không đoán bừa.

### E19.6g Bản dịch miễn phí không sửa được lỗi đọc chữ — thêm `engine` chọn được (2026-09-08)

Test lại trên MangaPlus sau khi các lỗi kỹ thuật đã sửa (§E19.6b–f): vẫn còn 3-8/12-17 bong bóng
dịch sai/thiếu — vài dòng **ra nguyên tiếng Anh** (không dịch), vài dòng dịch thành câu **vô
nghĩa** không liên quan gốc.

**Không phải bug — là giới hạn đã biết của engine đang dùng.** `_run_translate` không nhận tham
số engine từ đường tự động (chỉ nhận từ tham số retry thủ công/BatchRun — M5/M9), nên MỌI trang
tiện ích gửi lên đều rơi vào `settings.translate_default_engine` = `google_fast`: dịch **RỜI
RẠC từng dòng**, không có ngữ cảnh, và **không tự sửa được lỗi OCR đọc dính/sai** (điều này đã ghi
sẵn ở `FEATURES.md` "Xuất bằng bản dịch miễn phí có thể ra chữ chưa dịch" — chỉ là E19 lần đầu chạm
phải trên dữ liệu thật). `llm_context` (Gemini) đã có sẵn khả năng đúng thứ cần — prompt yêu cầu
"tự suy luận và sửa khi dịch" chữ OCR sai chính tả (`build_prompt`, chốt từ M5) — nhưng E19 chưa
từng dùng tới.

**Không đổi mặc định toàn hệ thống.** Đổi `settings.translate_default_engine` sẽ khiến MỌI luồng
khác (pipeline đầy đủ, M9 batch không chỉ định engine) tự tốn token Gemini — vi phạm thẳng nguyên
tắc M5 "người dùng phải kiểm soát được khi nào tốn token". Thay vào đó, thêm đường ĐI THẲNG cho
riêng E19: `Page.translate_engine_override` (cột mới, nullable, migration `0015_e19b`, tái dùng
enum Postgres `translation_engine` đã có từ 0003_m9 — `create_type=False`) ghi lựa chọn của người
dùng khi gửi ảnh; `_run_ocr` đọc cột này qua `_page_engine_override()` và truyền cho
`enqueue_translate_after_ocr(page_id, engine)` → `run_translate_job.delay(job_id, engine)`. Mọi
lời gọi từ pipeline đầy đủ giữ nguyên `engine=None` — không đụng cột này, hành vi cũ y nguyên.

Popup thêm ô chọn "Chất lượng dịch" (mặc định `google_fast`, giữ hành vi cũ cho ai chưa từng chọn)
cạnh ô ngôn ngữ — người dùng tự quyết định đánh đổi tốc độ/miễn phí lấy độ chính xác, không bị
âm thầm đổi hộ. Gỡ ô ngôn ngữ khỏi trang Tuỳ chọn (chuyển hẳn sang popup cùng ô engine) — hai nơi
cùng sửa một cấu hình là nguồn lệch, giữ đúng MỘT chỗ.

Test bắt được lỗi thật khi viết: gọi `run_translate_job` tay (bỏ qua tham số `engine` đã enqueue)
làm bài test đầu tiên xanh **giả** — `.delay()` bị chặn broker thật trong test (autouse fixture),
phải đè lại đúng `.delay` để bắt tham số THẬT đã gửi, không tự gọi lại hàm theo trí nhớ.

### E19.7 Giới hạn cố ý để lại

- Chỉ dò được `<img>` thật — trang vẽ bằng canvas hoặc chống sao chép thì nói thẳng "không hỗ trợ",
  không âm thầm thất bại.
- Không lọc trùng theo nội dung ảnh ở máy chủ — tiện ích tự nhớ theo URL ảnh (`Map` trong bộ nhớ
  trang), bấm lại đúng ảnh đó thì phủ lại ngay, không tốn 45 giây lần hai.
- `<all_urls>` là quyền rộng nhất Chrome cấp — chỉ tiêm code bằng
  `chrome.scripting.executeScript` **đúng lần bấm**, không có `content_scripts` khai sẵn.

## E21. Gõ đè `raw_text` + phóng to đối chiếu ảnh gốc (2026-09-09)

### E21.1 Vì sao mở mini-spec này

`REPORT_E20a.md`/`REPORT_E20b.md` đo được bằng benchmark thật: chữ mảnh (nghiêng) đặt trên nền
tranh phức tạp làm bước dò vùng chữ NỘI BỘ của PaddleOCR vẽ hụt biên — **không path OCR tự động
nào sửa được** (thử cả PaddleOCR + 4 kiểu tiền xử lý ảnh, cả Tesseract 4 chế độ PSM, đều 0/10
trên nhóm mục tiêu). Theo đúng "Decision gate sau E20" đã chốt trước: không path nào thắng rõ ⇒
không đổi engine ⇒ chuyển hướng sang cải thiện UX rà soát tay (M7).

### E21.2 Hai việc, một nguyên nhân

1. **`raw_text` giờ sửa được.** Trước E21, `PATCH /regions/{id}` cố tình khoá cứng `raw_text`
   ("không đụng tới") vì mọi lỗi đọc chữ trước đây coi là bug cần re-OCR sửa, không phải chuyện
   máy không bao giờ đọc đúng được. E20 đổi giả định đó bằng bằng chứng số: có lớp lỗi (chữ mảnh
   + nền bận) **không engine nào tự sửa**, buộc phải có lối thoát tay.
2. **Ảnh gốc giờ phục vụ được ra ngoài** (`GET /pages/{id}/original-image`, §API.md mục 9b).
   Trước đó KHÔNG có endpoint nào trả `page.image_path` — màn M7 chỉ vẽ khung trên
   `typeset-preview`, đã xoá chữ gốc. Không có ảnh gốc thì "gõ đè raw_text" là gõ mù: người dùng
   không có gì để đối chiếu ngoài trí nhớ.

Hai việc này PHẢI đi cùng nhau — sửa `raw_text` mà không có ảnh gốc để soi thì chỉ là đoán mò
kiểu khác, không hơn máy đọc sai bao nhiêu.

### E21.3 Vì sao KHÔNG tự dịch lại khi sửa `raw_text`

Cùng ranh giới đã có với mọi thao tác M7 khác (E12: máy chỉ ra chỗ không tự sửa; E13: gợi ý phải
người duyệt): sửa `raw_text` chỉ ghi `OCRResult.raw_text` + `edited_by_user=true`, KHÔNG dispatch
việc dịch. Hai lý do:

- **Chi phí**: `llm_context` tốn token mỗi lần gọi. Người dùng có thể đang gõ lại NHIỀU vùng liền
  nhau trước khi sẵn sàng dịch — tự dịch sau mỗi lần gõ là đốt token cho những bản dịch sẽ bị vứt.
- **Ghi đè không xin phép**: `TranslationResult` của vùng đó có thể đã được sửa tay riêng
  (`translation_edited_by_user=true`) — tự động dịch lại sẽ âm thầm xoá phần đó.

Người dùng tự bấm "Dịch lại" (endpoint đã có từ M7, không đổi) sau khi ưng ý với `raw_text` mới.

### E21.4 `edited_by_user` giờ có BA cờ độc lập, không phải một

`OCRResult.edited_by_user` (mới) đứng riêng với `TranslationResult.edited_by_user` và
`TypesetResult.edited_by_user` đã có từ trước — sửa raw_text không đụng cờ dịch, sửa dịch không
đụng cờ OCR. `_run_region_reocr` (đọc lại chữ gốc TỰ ĐỘNG từ ảnh) xoá-và-tạo-mới `OCRResult` nên
cờ tự về `false` — máy đọc lại thì đúng là "máy đọc", không còn là "người sửa" nữa, kể cả khi kết
quả MỚI trùng khớp ngẫu nhiên với bản người vừa gõ.

### E21.5 Phóng to — vẽ bằng canvas, không dùng CSS crop

`ZoomCropModal` tải riêng `original-image` (chỉ khi bấm "Phóng to", không tải sẵn cho mọi vùng —
phần lớn thời gian không cần) rồi `drawImage` đúng vùng `bbox` (nới thêm lề ~40% mỗi chiều, tối
thiểu 24px, để thấy bối cảnh quanh chữ) lên canvas phóng tới cạnh dài ~900px,
`imageSmoothingEnabled=false` để giữ nét răng cưa thật thay vì làm mờ chữ vốn đã nhỏ. Khung đỏ
đánh dấu đúng bbox máy đang đọc, phân biệt với phần lề vừa nới thêm.

### E21.6 Giới hạn đã biết

- **Live-verify trên trình duyệt thật: xong ở E21-LV** (2026-09-09, 25/25 đạt, xem
  `docs/REPORT_E21-LV.md`). "Target closed" ban đầu hoá ra là thiếu `libnspr4.so` cho Chromium
  headless (`playwright install-deps chromium` sửa được), không phải lỗi hạ tầng vĩnh viễn.
  Khung đỏ được xác nhận đúng vị trí bằng cách lấy mẫu pixel canvas thật, không chỉ nhìn ảnh
  chụp màn hình bằng mắt.
- Ảnh gốc phục vụ ra ngoài KHÔNG kiểm tra kích thước — trang gốc lớn (hiếm, nhưng có thể) thì
  modal phóng to tải nguyên ảnh, không có bước nén/resize server-side.

## E22. Worker Memory/OOM — bản THU HẸP theo audit, không phải bản nháp gốc (2026-09-09)

### E22.1 Vì sao mở mini-spec này

Test B&W tiếng Nhật (`manga_ocr`) trên production lộ ra 1 sự kiện worker bị `SIGKILL` (exit 137)
lúc 07:17, trước khi test đó chạy lúc 07:39 — worker tự phục hồi sau 10s. Người dùng đưa ra bản
nháp mini-spec E22 đầy đủ (JobAttempt + lease/heartbeat + Redis capacity-gate + watchdog định kỳ +
retry policy tự động), lấy mẫu từ một playbook hạ tầng tổng quát.

### E22.2 Audit tìm ra bản nháp gốc phần lớn ĐÃ THỪA

Ba phát hiện đổi hướng thiết kế:

1. **`deploy-start.sh` chạy celery với `--pool=solo`** — một tiến trình, không fork. Hai job AI
   nặng **không thể** chồng lên nhau về mặt cấu trúc trong topology hiện tại. Phần "Redis
   capacity-gate chặn concurrency" của bản nháp gốc bảo vệ một kịch bản không xảy ra được.
2. **`app/workers/hoi_phuc.py` (P3j, có từ trước E22) đã xử lý đúng phần lõi**: `worker_ready`
   signal tự gọi `don_job_mo_coi()` mỗi lần worker khởi động lại, đánh dấu mọi `Job.status=running`
   thành `failed` kèm lý do đọc được, lùi `Page.status` khỏi trạng thái tạm — **không tự chạy lại**
   (chủ ý, tránh vòng lặp OOM→retry→OOM). File tự ghi rõ điều kiện đúng của nó: "chỉ đúng khi có
   ĐÚNG một worker" — đúng topology E22 tự cấm thay đổi (guardrail #3 của bản nháp: không tách
   API/worker trong E22).
3. **`Job` đã là "1 lần attempt", không phải "logical work"**: mỗi lần chạy lại một stage, code
   tạo `Job` MỚI (không update `Job` cũ); mọi `OCRResult`/`TranslationResult`/`TypesetResult` đều
   xoá-rồi-tạo-mới. Theo đúng điều kiện A2 mà bản nháp gốc tự cho phép ("chỉ chọn bảng `JobAttempt`
   riêng nếu `Job` hiện tại KHÔNG đại diện 1 attempt") → audit tự loại bỏ nhu cầu bảng mới.

Người dùng chọn hướng **thu hẹp theo bằng chứng**: không build capacity-gate/`JobAttempt`/watchdog
định kỳ (code đầu cơ cho kịch bản nhiều-worker không xảy ra trong E22) — chỉ sửa 2 khoảng trống
THẬT còn lại.

### E22.3 Hai việc thật sự làm

1. **Cửa sổ ngắn "nói dối"**: giữa lúc worker chết và lúc `don_job_mo_coi()` chạy xong (~10-40s:
   `sleep 10` + Celery/Redis kết nối lại), `Job.status` vẫn ghi `running` dù worker đã chết. Thêm
   `Job.heartbeat_at` (đặt cùng lúc `started_at` trong `danh_dau_dang_chay()` — điểm gọi DUY NHẤT,
   10 nơi dùng chung) + suy luận LÚC ĐỌC (`app/services/job_status.py`,
   `suy_ra_trang_thai_hien_thi()`): nếu `running` lâu hơn hẳn `*_timeout_seconds` (trần Celery
   `soft_time_limit` thật của chính loại job đó) + 20s đệm mà không có nhịp tim mới → trả
   `processing_state="worker_interrupted"` thay vì `"running"` mù quáng. KHÔNG đổi `Job.status`
   trong DB — đó vẫn là việc riêng của `hoi_phuc.py`. `JobRead` tự tính field này qua
   `model_validator(mode="after")` nên MỌI endpoint trả `JobRead` (kể cả list `GET
   /pages/{id}/jobs`) đều nhất quán, không cần sửa từng route.
2. **Lý do job hỏng vì worker chết là MỘT câu cứng cho mọi trường hợp** — vi phạm chính guardrail
   #2 của bản nháp gốc ("không được khẳng định exit 137 = OOM khi chưa có bằng chứng"): dòng log
   cũ của `deploy-start.sh` viết thẳng "gần như chắc chắn là container hết bộ nhớ". Sửa: (a) bớt
   khẳng định trong dòng log, chỉ còn "nghi ngờ… CHƯA có xác nhận từ nền tảng"; (b)
   `app/workers/trang_thai_worker.py` đọc lại đúng `ma_thoat_gan_nhat` mà `deploy-start.sh` ĐÃ ghi
   sẵn vào `WORKER_STATE_FILE` (không cần deploy-start.sh ghi thêm gì mới) rồi phân loại: mã 137 →
   `resource_limit_suspected` (NGHI NGỜ, không phải `_confirmed`), mã khác/không rõ →
   `worker_lost`; (c) `hoi_phuc.don_job_mo_coi()` ghi 2 field mới `Job.error_class`/`Job.exit_signal`
   từ kết quả đó — chỉ ĐÚNG một nơi ghi, không đụng tới cách các lỗi khác (timeout, input hỏng…)
   ghi `error_log` tự do như cũ.

### E22.4 Cố tình KHÔNG làm (và vì sao)

- **Không** có bảng `JobAttempt`, `lease_token`, `worker_identity` — audit chứng minh `Job` hiện
  tại đã đóng đúng vai trò "1 attempt", thêm bảng là trùng lặp không ai đọc.
- **Không** có `HeavyWorkCapacityGate` (Redis Lua atomic, tái dùng được pattern của
  `app/services/batch/gate.py` — M9 Gemini rate gate) — `--pool=solo` đã đảm bảo concurrency=1 về
  mặt cấu trúc; gate chỉ có giá trị NẾU sau này tách nhiều worker (đúng điều `hoi_phuc.py` đã tự
  ghi từ trước là điều kiện phải làm lại).
- **Không** có `StaleAttemptWatchdog` chạy định kỳ (Celery beat) — suy luận LÚC ĐỌC
  (`job_status.py`) đủ cho mục đích hiển thị trung thực mà không cần thêm một tiến trình nền mới;
  và `hoi_phuc.py` (chạy lúc `worker_ready`) đã là cơ chế "quét + sửa" thật cho DB.
- **Không** có retry tự động cho `worker_lost`/`resource_limit_suspected` — giữ nguyên chủ ý gốc
  của `hoi_phuc.py`: tự chạy lại một job vừa (nghi ngờ) làm chết worker vì hết bộ nhớ là cách
  nhanh nhất giết nó lần nữa, có bằng chứng thật (07:17) chứ không phải giả định.

### E22.5 Giới hạn đã biết

- Ngưỡng "gián đoạn" (`*_timeout_seconds` + 20s) suy từ cấu hình Celery thật, nhưng CHƯA đo bằng
  live fault-injection thật trên production (worker-kill có chủ đích) — chỉ có bằng chứng quan sát
  được từ sự kiện 07:17 xảy ra tự nhiên.
- `processing_state="worker_interrupted"` nối vào ĐÚNG MỘT màn: panel "Vì sao?" của
  `ChapterProgress` — chỗ duy nhất trước đây nói sai hẳn ("không có bước nào hỏng — đang chờ tới
  lượt" trong khi worker đã chết). Các màn tiến độ khác vẫn đọc `Page.status` như cũ: chúng chỉ
  nói chung về bước đang chạy nên không sai, chỉ là chưa chi tiết tới mức phân biệt được worker
  gián đoạn.
- Nếu sau này topology đổi (nhiều worker, tách API/worker), điều kiện an toàn của `hoi_phuc.py`
  KHÔNG còn đúng nữa — phải quay lại làm đúng phần capacity-gate/lease đã audit ở đây trước khi
  đổi topology, không phải sau.

## E21b. Rà soát tay: chặn mất chữ đang gõ + bỏ việc canh lại thừa (2026-09-10)

### E21b.1 Audit bác bỏ phần lớn đề bài

Bản nháp E21b đề nghị dựng hàng đợi review với `review_state`/`reviewed_at`, xếp ưu tiên theo
điểm tin cậy OCR, và khung boundary riêng cho người rà soát. Audit trước khi build bác bỏ hai phần
ba:

1. **Trạng thái review tường minh ĐÃ CÓ ĐỦ từ E12.** `ReviewStatus` với đúng 4 giá trị
   `not_required/needs_review/reviewed_keep/reviewed_skip` (`enums.py`), lưu ở bảng
   `region_quality_assessment`, endpoint `POST /regions/{id}/quality-review`, UI đã có hai nút
   "Giữ để dịch"/"Bỏ qua vùng này". Dựng thêm `review_state` là tạo nguồn sự thật thứ hai cho
   cùng một khái niệm.
2. **Xếp ưu tiên theo confidence là bất khả thi cho tiếng Nhật.** `manga_ocr` trả `None` và code
   ghi thẳng "không bịa số" (`engines.py`); chỉ PaddleOCR (en/zh) có số thật. Dùng confidence làm
   khoá sắp xếp chung sẽ im lặng vô hiệu với đúng nguồn truyện mà E20/E21 sinh ra để phục vụ.

Còn lại hai khoảng trống THẬT, và cả hai đều là lỗi chứ không phải thiếu tính năng.

### E21b.2 Lỗi 1 — chữ đang gõ dở mất im lặng

`App` gắn `key={region.id}` cho `RegionPanel`, nên đổi vùng là **remount** ⇒ state form bị vứt.
`RegionPanel` có sẵn cờ `daDoi` nhưng chỉ dùng để bật/tắt nút Lưu; không có `beforeunload`, không
có confirm. Người dùng gõ lại nguyên câu chữ gốc OCR (đúng việc mà E21 sinh ra để phục vụ), bấm
nhầm sang vùng khác, mất sạch.

Cách chữa giữ nguyên kiến trúc: `RegionPanel` báo cờ `daDoi` lên App qua `onDoiTrangThaiSua`, và
để lại hàm `luu` mới nhất trong ref `dieuKhien` (cập nhật sau MỌI lần render, không dùng mảng phụ
thuộc — nếu không App sẽ lưu bản state cũ). App chặn ở `chonVung()` và hỏi ba lựa chọn: *Lưu rồi
chuyển · Bỏ thay đổi · Ở lại vùng này*. **Không tự lưu hộ** — lưu ngầm thứ người dùng chưa xác
nhận cũng là một kiểu mất kiểm soát.

### E21b.3 Lỗi 2 — sửa chữ gốc kéo theo một việc canh lại vô ích

`PATCH /regions/{id}` xếp `Job(type=typeset)` ở cuối **không điều kiện**, kể cả lượt chỉ sửa
`raw_text`; kèm đó đặt `fit_status=pending` và `edited_by_user=True` lên tầng typeset. Nhưng chữ
được VẼ là `translated_text` — sửa chữ gốc OCR không đổi bản vẽ. E21 thêm `raw_text` vào endpoint
này mà không sửa phần đuôi; test E21 chỉ khoá "không tự DỊCH lại" nên tác dụng phụ lọt qua.

Giá của nó không nhỏ: worker chạy `--pool=solo` (mỗi lúc đúng một việc, xem §E22), nên mỗi lượt
canh thừa chiếm mất suất của việc thật đang xếp hàng.

Điều kiện mới: canh lại khi và chỉ khi lượt sửa đụng `bbox`/`translated_text`/`font_family`/
`font_size`. Ca gộp (`raw_text` + `translated_text`) vẫn canh lại — điều kiện là "có trường nào
đổi bản vẽ không", không phải "có `raw_text` không".

### E21b.4 Điều hướng và lọc — tái dùng, không dựng mới

Nút Trước/Sau đi qua đúng tập vùng đang lọc (một biến `dsVungLoc` dùng chung cho cả danh sách lẫn
điều hướng, để hai thứ không bao giờ đi trên hai tập khác nhau). Bộ lọc trạng thái rà soát
(`LOC_RA_SOAT`) đọc thẳng `review_status` của E12, đứng **riêng hàng** với bộ lọc hướng chữ của
E15: "vùng này chữ dọc hay ngang" và "tôi đã soi vùng này chưa" là hai câu hỏi khác nhau.

Các ô lọc phải **phủ kín** miền giá trị. Bản đầu thiếu `not_required` ⇒ giao diện hiện "Tất cả 2"
mà mọi ô con đều 0, hai vùng biến mất không rõ đi đâu. Lỗi này **chỉ lộ ra khi bấm thật trên
trình duyệt**, không bộ test nào bắt được — nay đã có test canh tính phủ kín.

### E21b.5 Cố tình KHÔNG làm

- **Không** thêm `review_state`/`reviewed_at`/`reviewed_by` — trùng `ReviewStatus` của E12.
- **Không** xếp ưu tiên theo điểm tin cậy — `manga_ocr` không có số, xem §E21b.1.
- **Không** thêm phím tắt: chưa có phím tắt nào trong toàn bộ ứng dụng, thêm một hệ phím tắt là
  một lát cắt riêng cần audit xung đột trình duyệt/trợ năng đàng hoàng.
- **Không** đụng tới việc sửa bbox: nó ghi đè thẳng toạ độ detector và không có cột nào giữ nguồn
  gốc. Tách provenance cần migration + quyết định về hành vi pipeline, không nhét vào lát cắt sửa
  lỗi này.

### E21b.6 Giới hạn đã biết

- `App.jsx` **không có unit test nào** (trước và sau E21b) — phần wiring hộp thoại/điều hướng/lọc
  được kiểm bằng trình duyệt thật trên stack local, không phải bằng test tự động. Cơ chế cốt lõi
  (`RegionPanel` báo cờ + đưa hàm lưu ra) thì có test.
- Hộp thoại chặn khi ĐỔI VÙNG và khi đóng tab/tải lại. Chưa chặn đường đổi TRANG hoặc đổi bộ lọc
  làm vùng đang mở rơi khỏi danh sách — hai đường đó hiếm hơn và cần thêm test riêng.
- Chưa deploy: đây là lát cắt có đổi hợp đồng API (`refit_job_id` thành nullable), cần duyệt riêng.
  **Thứ tự deploy là FRONTEND TRƯỚC**, không phải backend-first: frontend mới chịu được cả hai đời
  backend (backend cũ luôn trả job id thật nên guard `null` không bao giờ chạm), còn backend mới
  đứng trước frontend cũ thì frontend cũ gọi `/jobs/null` mỗi lần người dùng sửa chữ gốc. Lý luận
  đầy đủ ở `REPORT_E21b.md §11.1` — bản đầu của chính báo cáo đó ghi ngược, đã sửa.
