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
