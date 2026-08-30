# Báo cáo Mini-Spec P3a — Sẵn sàng cho Pilot/UAT trên VibeHost

**Ngày:** 2026-08-31 · **Phạm vi:** **một** trang smoke, **không** phải Pilot/UAT
**Môi trường:** VibeHost **staging/production-like** (chưa được xác nhận là production chính thức)

## 1. Summary

**Kết quả: `BLOCKED`.**

Một trang smoke đi trọn pipeline trên host — nhưng **redeploy đã xoá sạch ảnh**, trong khi CSDL
vẫn ghi `typeset_done`. Đây là điều kiện no-go §8.3. **KHÔNG được chạy Pilot/UAT 10–20 trang.**

| | |
|---|---|
| Web | `https://translation.cmc-1.vibenode.matbao.ai` — v13 |
| API | `https://translation-api.cmc-1.vibenode.matbao.ai` — **v22** (v21 lúc bắt đầu P3a) |
| Mã đã triển khai | `45c0af2` (= `origin/main`) |
| Rollback | api → v20 · web → v12 |

Một trang smoke **tự vẽ** (không dùng tranh có bản quyền) đã đi trọn pipeline trên host trong
**157 giây**, không OOM. Worker **chứng minh được là đang tiêu thụ việc thật**.

Nhưng sau khi chủ dự án bấm **Triển khai lại (v22)** từ giao diện VibeHost, toàn bộ ảnh biến mất:

```
TRƯỚC v22:  clean-image  200 · image/png · 69.486 byte
            preview      200 · image/png · 98.060 byte
SAU   v22:  clean-image  404 · "Đường dẫn ảnh clean có trong DB nhưng file không còn: …_clean.png"
            preview      404
CSDL:       status = typeset_done · image_path và clean_image_path VẪN CÒN
```

⇒ **`/app/storage` là lớp ghi của container, không phải volume bền.**

⚠️ **Không** phải production-ready. Đây chỉ là cổng cho Pilot/UAT — và cổng này **đóng**.

## 2. Audit Before Run

### 2.1 Dịch vụ / phiên bản

| Dịch vụ | ID | Phiên bản | Deploy | Tài nguyên |
|---|---|---|---|---|
| `translation-api` | `cmtcexscl005o…` | **v21** | 31/08 00:12 | 1.6 vCPU / 4096 MB (trần 2.6 / 5376) |
| `translation-web` | `cmtcg12h500kq…` | **v13** | 31/08 00:13 | 0.6 vCPU / 2048 MB |

Nguồn: `git-url` / GitHub. Cơ chế: redeploy **thủ công** (push không tự deploy).
Topology: **`ROLE=all`** — API và Celery worker chạy chung một container. Log worker nằm chung
log runtime của `translation-api`.

### 2.2 Secret — audit metadata, KHÔNG đọc giá trị

`GEMINI_API_KEYS` hiện `isSecret: false`.

**Không thể chuyển sang Secret mà không nhập lại giá trị:**

- `list_env` **cố ý không trả giá trị** — kể cả biến không đánh dấu bí mật. (Tốt: tôi không có
  cách nào đọc được nó.)
- `set_env` có tham số `isSecret`, nhưng `value` nằm trong danh sách **bắt buộc**. Không có
  đường lật cờ mà giữ nguyên giá trị.

⇒ Đúng ca §7.1 mục 4: **`BLOCKED: user must re-enter GEMINI_API_KEYS in VibeHost Secret field`**.
Tôi **không đọc, không sao chép, không nhập lại, không ghi ra bất cứ đâu**.

**Chủ dự án đã chọn: chấp nhận rủi ro tạm thời, có ghi chép.** Riêng mục này không chặn —
nhưng kết luận cuối vẫn là `BLOCKED` vì lý do khác (§7.4).

Log **không** rò giá trị: dòng translate ghi `token=***`, dòng celery ghi
`redis://:**@vays-db-…` — cả hai đều tự che.

### 2.3 Lưu trữ

| Câu hỏi | Trả lời |
|---|---|
| Công cụ quản lý volume trên MCP | **Không có** — không phơi metadata mount |
| Đường lưu thật | **`/app/storage/…`** (log: `preview typeset -> /app/storage/previews/…`) — **không** phải `/data/storage` như mặc định trong `config.py` |
| Route phục vụ ảnh gốc | **Không có** (chỉ có `clean-image`, `typeset-preview`) ⇒ không dùng chapter cũ làm phép thử gián tiếp được |

Đã thử dùng chapter có sẵn `ddc7019b…` (tạo **28/08 19:23**, trước cả hai lần deploy) làm phép
thử: nhưng nó dừng ở `ocr_done` với `clean_image_path: null`, nên 404 ở `clean-image` là **đúng**,
không phải bằng chứng mất dữ liệu.

⇒ Lúc audit: persistence = **`unknown until controlled redeploy`** theo §7.2(4), nên đi tiếp bằng
ảnh smoke **tự sinh, chấp nhận mất**. **Câu trả lời có ở §7.4: lưu trữ là TẠM.**

### 2.4 Worker / tài nguyên / model / font

Bằng chứng worker sống **không** lấy từ `worker.trang_thai` (trường đó kẹt `starting` vĩnh viễn ở
`ROLE=all` vì `deploy-start.sh` không bao giờ ghi `running`). Lấy từ log thật:

```
2026-08-30T17:12:16Z [MainProcess] Connected to redis://:**@vays-db-…-redis-6379:6379/0
2026-08-30T17:12:16Z [MainProcess] celery@70d910a961c2 ready.
```

Model: build v21 có chặng `RUN mkdir -p /models && curl … comic-text-detector.onnx …
lama-manga-dynamic.onnx`, **11/11 chặng build `success`**.
Font: `Bangers` được dùng thật lúc căn chữ (log typeset).

### 2.5 CORS — mốc nền

| Origin | ACAO |
|---|---|
| `https://translation.cmc-1.vibenode.matbao.ai` | khớp chính xác |
| `https://evil.example` · `http://localhost:5174` · `null` | *(không có)* |

Wildcard 0 · Credentials 0.

## 3. Design Choice

**Một trang smoke qua đúng giao diện hosted**, không dùng curl/Postman/DB/Celery thay thế. Lý do:
nó đi trọn con đường mà người dùng thật sẽ đi — cùng CSDL, cùng Redis, cùng API, cùng giao diện,
cùng đường lưu trữ — nên chứng minh được nhiều thứ hơn hẳn việc đọc log hay tạo tệp bằng shell.

**Không đụng tới `worker.trang_thai`.** Sửa telemetry để nó ghi `running` sẽ là *đổi lời khai* chứ
không phải *tăng bằng chứng*. Bằng chứng thật là việc được tiêu thụ và trạng thái cuối trung thực.

## 4. Changed Files / Platform Changes

**Kho mã:** không đổi một dòng mã sản phẩm nào. Chỉ thêm:

```
scripts/do_run_p3a.py        kịch bản smoke qua giao diện hosted
docs/REPORT_P3a_HOSTED_READINESS.md
```

**VibeHost:** **không** đổi biến môi trường, **không** tạo/gắn volume, **không** đổi tài nguyên,
**không** rollback.

- Một lượt `redeploy_project` qua MCP bị nền tảng **từ chối** (`NO_CHANGE`) — không tác dụng phụ.
- **Chủ dự án** bấm "Triển khai lại" trên giao diện VibeHost → **v22**, cùng mã `45c0af2`.
  Đây là thao tác có xác nhận trước, và chính nó cho ra kết quả đo ở §7.4.

**Không giá trị bí mật nào xuất hiện ở bất kỳ đâu trong báo cáo, log hay commit.**

## 5. New API / DB / State

**None.** Không endpoint, migration, enum, state hay tính năng mới.

Dữ liệu test do luồng bình thường sinh ra (**không** xoá tự động, vì xoá không phải năng lực đã
được audit):

```
project_id = 7bb1b714-3206-44c6-9080-2ef63c655401   ("P3a hosted smoke — DO NOT TREAT AS PILOT")
page_id    = 4b955242-37f3-468b-8423-fccefd310e54
```

## 6. Tests

Không đổi mã ⇒ dùng lại mốc hồi quy của bản phát hành (Deploy 001): **785 backend · 226 frontend ·
282 extension · vite build ✅**. **Lint chưa phải cổng phát hành.**

## 7. Live Verification

### 7.1 Ảnh smoke — hợp lệ về bản quyền

Tự vẽ bằng PIL: 1200×1700 PNG, nền có hoạ tiết (để LaMa thật sự có việc), **2 bong bóng trắng**
chữ tiếng Anh — một câu ngắn (`WAIT! LOOK AT THIS.`) và một câu **5 dòng**
(`I HAVE BEEN SEARCHING FOR THIS PLACE FOR A VERY LONG TIME NOW.`) để thử dịch + căn chữ.

**Không** dùng tranh manga có bản quyền. Ảnh gốc để **ngoài kho mã**, không commit.

### 7.2 Step C/D — worker tiêu thụ việc thật · **11/11 ĐẠT**

Tải lên qua **đúng giao diện E11 hosted** (điền form, chọn ảnh qua dropzone thật, bấm nút tạo).

```
  3.3s  ->  detecting
 90.6s  ->  detected
141.5s  ->  ocr_done
151.6s  ->  inpainted
156.7s  ->  typeset_done
```

| Bước | Bằng chứng |
|---|---|
| Nhận diện | **2 vùng** — khớp đúng 2 bong bóng |
| OCR | **2/2** vùng đọc được chữ |
| **Inpaint (LaMa)** | **11,4s**, `còn chữ ở 0 vùng`, **không OOM/không SIGKILL/không restart** |
| Dịch | 0,7s · `engine=google_fast` · `fallback: False` · `token=***` |
| Căn chữ | 0,28s · `fit_ok: 2, overflow_warning: 0` · font `Bangers` |
| E14 vùng an toàn | `fallback_rectangle: 2, shape_derived: 0` |
| **E15 hướng chữ** | `horizontal_ltr: 2, tt_ready: 2` ← xác nhận mã E15 chạy trên host |
| Lỗi JS giao diện | 0 |

### 7.3 Step E — hiện vật

```
clean-image      HTTP 200 · image/png · 69.486 byte
typeset-preview  HTTP 200 · image/png · 98.060 byte
```

Đã tải preview về **nhìn tận mắt**: chữ tiếng Anh bị xoá sạch khỏi bong bóng, chữ tiếng Việt nằm
gọn trong bong bóng, hoạ tiết nền ngoài bong bóng giữ nguyên.

**Quan sát chất lượng (P3, không chặn):** bản dịch `google_fast` thô — `WAIT!` → `CHỜ ĐỢI!`
(đúng ngữ cảnh phải là *KHOAN ĐÃ!*), `LOOK AT THIS` → `nhìn vào NÀY` (vỡ nghĩa), và thiếu dấu cách
sau dấu phẩy ở `NƠI NÀY,DÀNH CHO`. Đây là chất lượng dịch, không phải lỗi hạ tầng.

### 7.4 Step F — **HIỆN VẬT KHÔNG SỐNG SÓT** ⛔

Lượt đầu, `redeploy_project` qua MCP bị nền tảng từ chối:

```
redeploy_project(translation-api) -> NO_CHANGE: Không có thay đổi mới so với phiên bản hiện tại
```

Chủ dự án bấm **Triển khai lại** trên giao diện VibeHost — nút này **không** kiểm `NO_CHANGE` và
đã dựng **v22** từ đúng nguồn GitHub cũ (`45c0af2`). Đây chính là sự kiện tạo lại container mà
phép thử cần.

**Kết quả — đo ngay sau khi v22 trực tuyến:**

| | Trước v22 | Sau v22 |
|---|---|---|
| `clean-image` | **200** · `image/png` · **69.486 byte** | **404** |
| `typeset-preview` | **200** · `image/png` · **98.060 byte** | **404** |
| Bản ghi CSDL | `typeset_done` | **`typeset_done`** *(vẫn nguyên)* |
| `image_path` / `clean_image_path` | có | **vẫn có** |

Nguyên văn lỗi — **chính API tự nói ra sự lệch pha**:

```
{"detail":"Đường dẫn ảnh clean có trong DB nhưng file không còn:
           projects/7bb1b714…/pages/4b955242…_clean.png"}
```

⇒ **`/app/storage` là lớp ghi của container.** Postgres managed giữ nguyên bản ghi, còn ảnh gốc,
ảnh đã xoá chữ và preview **mất sạch** sau mỗi lần triển khai lại.

Hệ quả thực tế: chapter rơi vào trạng thái **nói dối** — giao diện đọc CSDL thấy `typeset_done`
nên trình bày như đã xong, nhưng mọi ảnh đều 404. Chapter cũ `ddc7019b…` (28/08) cũng vậy: bản ghi
còn, `ocr_done`, ảnh đã mất từ lâu.

**Ghi nhận phụ (P3):** route `clean-image` phân biệt đúng "có trong DB nhưng file mất";
route `typeset-preview` lại trả `"Page chưa có ảnh preview — bước căn chữ chưa chạy xong"` —
**sai nguyên nhân**, vì typeset đã chạy xong thật. Hai route không nhất quán về cách nói thật.

### 7.5 Step G — CORS sau mọi thao tác

| Origin | ACAO |
|---|---|
| `https://translation.cmc-1.vibenode.matbao.ai` | khớp chính xác |
| `https://evil.example` · `http://localhost:5174` · `null` | *(không có)* |

Wildcard **0** · Credentials **0**. Hiện vật smoke vẫn mở được sau lượt gọi bị từ chối.

## 8. Remaining Limits / Follow-ups

- **CORS không phải xác thực.** Không có auth / RBAC / multi-user / TLS riêng.
- **`ROLE=all`**: API và worker dùng chung một container và chung 4 GB RAM. Một trang smoke chạy
  vừa; **10–20 trang chưa đo**.
- **`worker.trang_thai` kẹt ở `starting` vĩnh viễn** — lỗ hổng quan sát, cố ý không sửa trong P3a.
- **E15 dựng chữ dọc: vẫn BLOCKED về cấu trúc** (`MangaOCREngine.recognize()` trả `(text, None)`).
- **Tiện ích E1: chưa bấm tay biểu tượng** — môi trường không có display server.
  `getPanelBehavior()` **không** phải bằng chứng thay thế.
- **`GEMINI_API_KEYS` vẫn là biến thường** — rủi ro do chủ dự án chấp nhận, có ghi chép.
- **Độ bền lưu trữ: CHƯA CHỨNG MINH.** Chỉ chứng minh được hiện vật tồn tại *trong cùng một vòng
  đời container*, chưa chứng minh sống sót qua khởi động lại.
- Ghi nhận nhỏ: log có `SecurityWarning: running the worker with superuser privileges` — celery
  chạy bằng root.

## 9. Pilot Gate Decision

| # | Tiêu chí §9 | Kết quả |
|---|---|---|
| 1 | Secret masked | ⚠️ **Rủi ro được chấp nhận có ghi chép** (giá trị chưa từng bị đọc/ghi) |
| 2 | `/app/storage` persistent | ⛔ **HỎNG — đã chứng minh là TẠM** |
| 3 | Một trang smoke được worker tiêu thụ | ✅ |
| 4 | Detect/OCR/inpaint/dịch/căn chữ/preview xong, không chết ngầm | ✅ |
| 5 | LaMa gom cụm chạy trong 4 GB, không OOM | ✅ **11,4s** |
| 6 | Hiện vật sống sót qua redeploy | ⛔ **HỎNG — mất sạch** |
| 7 | CORS exact-origin | ✅ |
| 8 | Không thêm tính năng/API/schema/state | ✅ |
| 9 | Tài liệu cập nhật | ✅ |
| 10 | Không tuyên bố quá | ✅ |

## Quyết định: **`BLOCKED`**

Tiêu chí **hỏng: #2 và #6** — đúng điều kiện no-go §8.3
*"Original/clean/preview disappears after controlled restart/redeploy"*.

**KHÔNG chạy Pilot/UAT 10–20 trang.** Chạy pilot trên lưu trữ tạm nghĩa là: người vận hành bỏ
hàng giờ tải ảnh, sửa tay, rà soát — rồi lần deploy kế tiếp xoá sạch, trong khi giao diện vẫn
hiện `typeset_done` như thể mọi thứ còn nguyên. Đó là cách chắc chắn nhất để mất công **và** mất
lòng tin vào công cụ.

### Mini-spec kế tiếp — đúng MỘT việc

**Gắn volume bền cho đường lưu trữ của `translation-api`.**

- **Vấn đề:** `/app/storage` nằm trên lớp ghi của container; mỗi lần triển khai lại là mất toàn
  bộ ảnh gốc / ảnh đã xoá chữ / preview / file xuất, trong khi Postgres managed vẫn giữ bản ghi
  ⇒ dữ liệu rơi vào trạng thái nói dối.
- **Bằng chứng / tần suất:** đo trực tiếp ở §7.4 — 2/2 hiện vật mất sau **một** lần redeploy.
  Đã xảy ra với **cả** chapter smoke (31/08) lẫn chapter cũ `ddc7019b…` (28/08). Tần suất = **mỗi
  lần deploy**, mà deploy là việc thường xuyên.
- **Mức:** **P1** — chưa mất dữ liệu người dùng thật (mới có dữ liệu test), nhưng sẽ mất ngay ở
  pilot đầu tiên.
- **Vì sao xếp trên mọi việc khác:** nó chặn Pilot/UAT. Chất lượng dịch, `worker.trang_thai`,
  chữ dọc E15 — đều vô nghĩa nếu kết quả không sống qua đêm.
- **Ranh giới phạm vi:** chỉ gắn volume + xác minh hiện vật sống qua một lần redeploy. **Không**
  đổi `STORAGE_BACKEND`, không viết lớp lưu trữ mới, không di chuyển dữ liệu cũ (dữ liệu cũ đã
  mất rồi), không đụng pipeline.
- **Câu hỏi audit đầu tiên:** VibeHost có cơ chế volume bền cho project không, gắn được vào đường
  nào, dung lượng bao nhiêu — và `STORAGE_LOCAL_ROOT` nên trỏ vào đường đó hay giữ `/app/storage`
  rồi gắn volume đè lên?

## 10. Commit / Deploy State

```
Mã đã triển khai : 45c0af2 (origin/main) — KHÔNG đổi trong P3a
Hành động deploy : 1 lượt redeploy qua MCP bị TỪ CHỐI (NO_CHANGE)
                   1 lượt "Triển khai lại" do CHỦ DỰ ÁN bấm trên giao diện -> v22, cùng mã 45c0af2
Đổi cấu hình     : KHÔNG
Phiên bản hiện tại: translation-api **v22** (mã không đổi: 45c0af2)
Rollback         : KHÔNG thực hiện
Báo cáo này      : commit LOCAL, KHÔNG push
```

**Sau báo cáo này không có lần push, deploy hay restart nào khác được thực hiện.**
