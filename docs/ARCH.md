# ARCH.md — Translation (Phase MTE: Manga Translation Extension)

> Trạng thái: **M7 hoàn tất** (M1 contract · M2 nhận diện khung · M3 đọc chữ · M4 xoá chữ · M5 dịch ·
> M6 canh chữ + ảnh xem thử · M7 màn sửa tay). Chưa export chapter — M8.

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

## 3. Data model (7 bảng, chốt ở M1)

```
Project 1─n Page 1─n TextRegion 1─1 OCRResult
                     │            1─1 TranslationResult
                     │            1─1 TypesetResult
            1─n Job
```

- `Project`: `source_lang(ja|zh|en)`, `target_lang(vi)`, `intended_use(personal|study|other)` —
  `intended_use` tạo sẵn từ M1 để M10 không phải migrate thêm cột.
- `Page.status`: state machine chính, khai báo **đủ 10 giá trị ngay ở M1**
  (`queued → detecting → detected/detection_failed → ocr_done → inpainted/inpaint_needs_review →
  translated → typeset_done → ready_for_export`) để tránh `ALTER TYPE` enum nhiều lần trên Postgres.
  Cạnh hợp lệ khai báo trong `PAGE_STATUS_TRANSITIONS` (`app/models/enums.py`) + helper `assert_transition`.
- `TextRegion`: `bbox_x/y/w/h` (pixel, gốc trên-trái), `confidence` NULL cho tới M2,
  `overlap_suspect` (cờ của M2), `reading_order` NULL cho tới M5.
- 3 bảng kết quả (`OCRResult`, `TranslationResult`, `TypesetResult`) đều `unique(region_id)`
  → rerun job là **idempotent theo region**, không sinh bản ghi trùng.
- `Job`: `type(detect|ocr|inpaint|translate|typeset|export)` khai báo đủ enum cho cả Phase từ M1;
  `retry_count` là placeholder của M9.
- **Chưa tạo** `APIKeyPool` (M5/M9) và `ExportJob` (M8) — đúng nguyên tắc chỉ tạo đủ cho mini-spec hiện tại.

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

## 9. Giới hạn đã biết (cố ý để lại)

- **Supabase Storage chưa có adapter.** M1 chạy `STORAGE_BACKEND=local` (đã verify thật).
  Khi đặt `STORAGE_BACKEND=supabase`, app **fail ngay** với thông báo rõ ràng thay vì im lặng ghi sai chỗ.
  Nối Supabase Storage cần credential thật → làm khi có key (ưu tiên trước M4 vì M4 sinh thêm ảnh clean).
- ~~Chưa dispatch Celery task~~ → **đã xong ở M2**: upload page enqueue `detect.run_detect_job`.
  Nếu broker chết, job đứng ở `queued` kèm `error_log=enqueue_failed:…` (không giả vờ đã gửi).
- **NỢ KỸ THUẬT (tracked):** `SupabaseStorageAdapter` chưa viết — cần khi có credential Supabase.
  Nên làm trước M4 vì M4 bắt đầu sinh thêm ảnh clean. Hiện `STORAGE_BACKEND=supabase` fail có thông báo rõ.
- **Chưa có typeset** — M6.
- **M2 chưa xử lý** ảnh xoay/nghiêng, scan chất lượng kém; chưa auto-retry khi timeout (thuộc M9);
  chưa có UI vẽ overlay box (thuộc M7).
- **Chưa có auth/user management** — nếu cần multi-user phải là mini-spec riêng, không nhét vào MTE.
