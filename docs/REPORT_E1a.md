# Báo cáo Mini-Spec E1a — Siết CORS của API local & proxy Vite

**Project:** Translation · **Phase:** E (hardening) · **Ngày:** 2026-08-30
**Nền:** E15 CLOSED (`fff82d0`, tag `v1.5-E15-closed`) · E1 (`5bd3007`)
**Trạng thái:** ✅ **CLOSED** — 17/17 đo thật trên Chromium ở **cả hai** chế độ

## 1. Summary

Trước E1a, **bất kỳ website nào** đang mở trong trình duyệt cũng đọc được API Translation local:
máy chủ dev Vite gắn `Access-Control-Allow-Origin: *` vào mọi phản hồi, kể cả phản hồi proxy
`/api` xuống backend — bao gồm cả `GET /api/v1/projects/{id}` chứa metadata chapter thật.

E1a chuyển sang **chặn mặc định**: máy chủ dev không phát header CORS nào trừ khi có origin được
khai tường minh. Giao diện web **không bị ảnh hưởng** vì nó gọi API cùng nguồn. Tiện ích E1 lùi
về **chỉ-mở-link** ở cấu hình mặc định, và đọc được trạng thái nếu người dùng tự khai đúng ID
tiện ích của máy mình.

Không đổi API/DB/state/AI pipeline. Không thêm quyền nào cho tiện ích.

## 2. Audit Before Build

### 2.1 Quan sát terminal của người dùng — tách bạch từng tầng

Người dùng chạy `docker compose -f deploy/docker-compose.yml up -d` tại `/home/coder/workspace`
và nhận `no such file or directory`, nhưng `curl http://127.0.0.1:8010/healthz` vẫn trả `ok`.

| Câu hỏi | Đo được |
|---|---|
| Compose ở đâu | `/home/coder/workspace/projects/Translation/deploy/docker-compose.yml` |
| Đường người dùng gõ có tồn tại | **Không** — `/home/coder/workspace/deploy/...` không có |
| Container | 5/5 `Up`: api, frontend, worker, db (healthy), redis (healthy) |
| API còn sống | `HTTP 200`, `content-type: application/json`, `server: uvicorn` |
| Frontend dev | cổng host **5174** → 5173 trong container |
| Worker | **sống** — `celery inspect ping` → `pong, 1 node online`; **158 job `done`** trong 3 giờ gần nhất |

⇒ Lỗi compose là **lỗi đường dẫn**, không phải Docker/API chết. Đây đúng là loại false negative
mà mini-spec yêu cầu ghi nhận. Không sửa đường dẫn compose để "cho qua" — đường dẫn vốn đã đúng
khi chạy từ gốc repo.

**Đính chính nhỏ về số liệu:** thân JSON thật là `{"status":"ok","worker":{"trang_thai":"khong_ro"}}`
— **không dấu**. Bản người dùng chép lại có thêm dấu (`trạng_thái`/`không_rõ`); tên trường thật
trong mã là `trang_thai`.

**`worker: khong_ro` KHÔNG nói worker khoẻ hay chết.** Nó chỉ có nghĩa API không biết: API đọc
`/tmp/trang-thai-worker.json`, tệp chỉ tồn tại khi API và worker chạy chung container (`ROLE=all`).
Đã xác nhận tệp này **không tồn tại** trong container api. Sức khoẻ worker phải đo riêng — và đã
đo (ping + 158 job done).

### 2.2 Kiểm kê tầng phát header CORS

| Tầng | Tệp | Trạng thái trước E1a |
|---|---|---|
| Máy chủ dev Vite | `frontend/vite.config.js` | **không khai `cors`** ⇒ Vite 6.0.7 mặc định `true` ⇒ **`ACAO: *`** |
| API FastAPI | `backend/app/main.py` | middleware **chỉ gắn khi** `CORS_ALLOW_ORIGINS` khác rỗng; `.env` để rỗng ⇒ **không có ACAO** |
| nginx bản prod | `frontend/default.conf.template` | **không** có `add_header` CORS, **không** proxy `/api` |
| Route ảnh/tải file | `routes.py` (`FileResponse`) | không tự đặt header; đi theo middleware FastAPI |

⇒ Wildcard đến từ **đúng một tầng**: máy chủ dev Vite. Xử lý đúng ở tầng đó, không đổ sang backend.

### 2.3 Bảng bằng chứng TRƯỚC khi sửa (Origin thật)

| Origin | URL đích | HTTP | ACAO | Tầng đặt header | Trình duyệt đọc được? |
|---|---|---|---|---|---|
| `http://localhost:5174` | `:8010/api/v1/health` (API trực tiếp) | 200 | *(không có)* | — | ❌ |
| `http://localhost:5174` | `:5174/api/v1/health` (qua proxy) | 200 | `*` | Vite | ✅ |
| `https://evil.example` | `:5174/api/v1/health` | 200 | `*` | Vite | ✅ **lỗ hổng** |
| `http://localhost.evil.example` | `:5174/api/v1/health` | 200 | `*` | Vite | ✅ **lỗ hổng** |
| `chrome-extension://gppdc…` | `:5174/api/v1/health` | 200 | `*` | Vite | ✅ |
| `null` | `:5174/api/v1/health` | 200 | `*` | Vite | ✅ **lỗ hổng** |
| `https://evil.example` | `:5174/api/v1/projects/{id}` **dữ liệu thật** | 200 | `*` | Vite | ✅ **lỗ hổng** |
| `https://evil.example` | `:5174/api/v1/pages/{id}/preview` | 404 | `*` | Vite | ✅ |
| `https://evil.example` | `:5174/healthz` | 200 | `*` + `content-type: text/html` | Vite | ✅ (là trang SPA) |

### 2.4 Cổng thật — không giả định

`5174` (host) → `5173` (container). `5173` trên host **không** chạy lúc đo. Danh sách trắng chỉ
liệt kê cổng có bằng chứng.

### 2.5 E1 cần endpoint nào

Từ `REPORT_E1.md`: `GET /api/v1/projects` trả **405** (không có API liệt kê). E1 chỉ dùng
`GET /api/v1/health` và `GET /api/v1/projects/{id}` cho chapter người dùng **tự ghim**. Không
bịa thêm endpoint nào.

### 2.6 ID tiện ích có ổn định không

ID đo được: `gppdcagfjgnekmdfbiplpfeahillicgi`. Chrome suy ID của tiện ích nạp-thủ-công từ
**đường dẫn tuyệt đối** của thư mục ⇒ ổn định trên **một** máy/đường dẫn, **không** ổn định khi
đổi máy. ⇒ **Không** đưa ID nào vào mặc định repo; mỗi người tự khai ID của mình.

## 3. Kiểm kê nguồn/tầng CORS sau E1a

| Tầng | Ai sở hữu | Biến | Mặc định |
|---|---|---|---|
| Máy chủ dev Vite | `frontend/vite.config.js` + `frontend/cors-allowlist.js` | `DEV_SERVER_CORS_ALLOW_ORIGINS` | **rỗng ⇒ chặn hết** |
| API FastAPI (chạy thật) | `backend/app/main.py` | `CORS_ALLOW_ORIGINS` | rỗng ⇒ không gắn middleware |
| nginx prod | `default.conf.template` | — | không có CORS |

Hai biến **cố ý không gộp**: một cái bảo vệ máy dev, một cái dành cho lúc deploy khi giao diện và
API ở hai tên miền. Gộp lại thì một origin khai cho prod sẽ vô tình mở trên máy dev của mọi người.
Ownership ghi ở `docs/SECURITY.md` §2 và `.env.example`.

## 4. Design Choice

**Chặn mặc định bằng cách tắt hẳn CORS ở máy chủ dev, thay vì khai sẵn origin của giao diện.**

Lý do: giao diện web **không cần** CORS. Trang tải từ `127.0.0.1:5174` gọi `/api/...` cũng ở
`127.0.0.1:5174` — cùng nguồn, trình duyệt không chạy phép kiểm CORS. Khai sẵn origin giao diện
vào danh sách trắng sẽ tạo cảm giác "phải có thì mới chạy", rồi người sau copy thêm origin khác
vào cho tiện. Danh sách **rỗng** nói đúng sự thật: chưa ai cần đọc chéo nguồn cả.

Đã bác bỏ hai phương án khác: (a) phản chiếu Origin theo mẫu — chính là wildcard trá hình;
(b) dùng chung một danh sách cho cả dev lẫn prod — trộn hai vùng bảo vệ khác nhau.

## 5. Changed Files

```
frontend/cors-allowlist.js                    MỚI  bộ kiểm + đọc cấu hình allowlist (Node-side)
frontend/src/test/cors-allowlist.test.js      MỚI  68 test
frontend/vite.config.js                       SỬA  cors: false mặc định; allowlist tường minh
deploy/docker-compose.yml                     SỬA  truyền DEV_SERVER_CORS_ALLOW_ORIGINS (rỗng)
.env.example                                  SỬA  ghi rõ hai biến thuộc hai tầng
docs/SECURITY.md                              MỚI  ranh giới truy cập, ownership, bẫy đã gặp
scripts/do_run_e1a.py                         MỚI  đo thật trên Chromium (website lạ cổng 9999)
docs/REPORT_E1a.md, TEST_LOG.md, PLAN.md      docs
```

## 6. New API / DB / State

**None.** Không endpoint, không migration, không enum, không state machine, không đổi
business response, không đụng Celery/OCR/AI/preview/export. Không thêm quyền nào cho tiện ích.

## 7. Ma trận hành vi header — SAU khi sửa

**Mặc định (danh sách rỗng):**

| Origin | ACAO | `Vary` | ACAC |
|---|---|---|---|
| `http://localhost:5174` | *(không có)* | – | không |
| `https://evil.example` | *(không có)* | – | không |
| `http://localhost.evil.example` | *(không có)* | – | không |
| `chrome-extension://gppdc…` | *(không có)* | – | không |
| `null` | *(không có)* | – | không |
| `:5174/api/v1/projects/{id}` từ origin lạ | *(không có)* | – | không |

**Khi khai `DEV_SERVER_CORS_ALLOW_ORIGINS=chrome-extension://gppdc…`:**

| Origin | ACAO | `Vary` | ACAC |
|---|---|---|---|
| `chrome-extension://gppdc…` *(khớp)* | `chrome-extension://gppdc…` | `Origin` | không |
| `chrome-extension://aaaa…` *(ID khác)* | *(không có)* | – | không |
| `https://evil.example` | *(không có)* | – | không |
| `http://localhost.evil.example` | *(không có)* | – | không |
| `http://127.0.0.1.nip.io` | *(không có)* | – | không |
| `null` / `file://` | *(không có)* | – | không |

**Preflight OPTIONS:**

```
Origin khớp   -> 204, ACAO đúng origin, Vary: Origin,
                 Allow-Methods: GET,POST,PATCH,OPTIONS · Allow-Headers: Content-Type
Origin lạ     -> 405, KHÔNG có header CORS nào
```

Không có phản hồi nào mang `*`. Không có `Access-Control-Allow-Credentials` ở bất kỳ ca nào.

## 8. Tests

| Bộ | Lệnh | Kết quả |
|---|---|---|
| Backend | `cd backend && ../.venv/bin/python -m pytest -q` | **785 thu thập, exit 0**, 0 fail |
| Frontend | `cd frontend && npx vitest run` | **226 pass / 9 tệp** (+68 của E1a), 0 fail |
| Extension | `cd extension && npx vitest run` | **282 pass / 7 tệp**, 0 fail |
| Build | `cd frontend && npx vite build` | ✅ `built in 1.98s`, 232.01 kB |

68 test mới phủ: mục cấu hình hợp lệ/không hợp lệ (đại diện, regex, LAN/private IP, IPv6, tài
khoản nhúng, đường dẫn/query/hash, `file:`/`data:`/`javascript:`/`null`, ID tiện ích sai khuôn);
đọc CSV (rỗng, trùng sau chuẩn hoá, mục hỏng bị loại kèm lý do); khớp Origin tuyệt đối (sai cổng,
giống-localhost, nip.io, ID tiện ích khác, thêm `/` ở cuối); và chốt chặn **không đường nào sinh
ra `*`**.

## 9. Live Verification — Chromium thật

`scripts/do_run_e1a.py` dựng một **website lạ thật** ở cổng 9999 và ánh xạ
`localhost.evil.example` về loopback bằng `--host-resolver-rules`, nên đây là origin thật trong
trình duyệt chứ không phải mô phỏng bằng header.

**Chạy hai lần — cả hai đều 17/17:**

| # | Phép đo | Mặc định (chặn hết) | Đã khai origin tiện ích |
|---|---|---|---|
| L1 | Giao diện gọi API cùng nguồn | ✅ 200 `{"status":"ok"}` | ✅ |
| L2 | Giao diện đọc chapter thật | ✅ 200, 411 byte | ✅ |
| L3 | Trang lạ đúng là origin khác | ✅ `http://127.0.0.1:9999` | ✅ |
| L4 | Website lạ đọc `/api/v1/health` | ✅ **chặn** `TypeError: Failed to fetch` | ✅ chặn |
| L5 | Website lạ đọc **dữ liệu chapter** | ✅ **chặn** | ✅ chặn |
| L6 | Website lạ đọc API trực tiếp `:8010` | ✅ **chặn** | ✅ chặn |
| L7 | `localhost.evil.example` là origin thật | ✅ | ✅ |
| L8 | `localhost.evil.example` đọc API | ✅ **chặn** | ✅ chặn |
| L9 | Bấm biểu tượng → mở Side Panel (nối dây) | ✅ `{openPanelOnActionClick: true}` | ✅ |
| L10 | Manifest giữ quyền tối thiểu | ✅ `['storage','sidePanel']`, host rỗng | ✅ |
| L11 | "Tạo chapter mới" mở đúng route | ✅ `http://127.0.0.1:5174/` | ✅ |
| L12 | Hành vi E1 | ✅ **chỉ-mở-link**, nói thẳng lý do | ✅ **đọc metadata thật** |
| L13 | Tắt máy chủ ⇒ báo chưa kết nối kèm lý do | ✅ | ✅ |
| L13b | Không khẳng định "không có chapter" | ✅ | ✅ |
| L14 | Giao diện chạy lại sau restart | ✅ 200 | ✅ |
| L15 | Website lạ **vẫn** bị chặn sau restart | ✅ | ✅ |
| Z1 | Ngoại lệ JS | ✅ 0 | ✅ 0 |

L14/L15 chạy sau khi **stop rồi start lại** container giao diện — chứng minh hành vi không phải
chỉ đúng nhờ hot-reload.

### Về việc bấm biểu tượng bằng tay (còn treo từ REPORT_E1)

Môi trường này **không có display server** (`$DISPLAY` rỗng, không có Xvfb), và không API nào
dispatch được cú bấm vào thanh công cụ của trình duyệt. Nên đã kiểm phần **kiểm được**:
`chrome.sidePanel.getPanelBehavior()` trả `{openPanelOnActionClick: true}` — tức dây nối đã đúng
— và trang Side Panel mở/chạy đầy đủ khi truy cập bằng địa chỉ `chrome-extension://…`.

**Vẫn còn treo:** một cú bấm tay thật vào biểu tượng, trên máy có màn hình. Không tuyên bố đã
xong.

## 10. Giới hạn bảo mật — nói thẳng

1. **CORS không phải xác thực.** Nó chỉ chặn *trang web trong trình duyệt*. Mọi tiến trình trên
   chính máy bạn (curl, script, app khác) vẫn gọi API được.
2. **Phần siết này áp cho máy chủ dev local.** **Không** được đọc thành "an toàn cho production".
3. Translation vẫn **chưa có auth, chưa multi-user, chưa TLS**.
4. **ID tiện ích không ổn định giữa các máy** — đổi máy/đường dẫn là phải khai lại.
5. Bản dựng prod (nginx) không proxy `/api`, nên tiện ích ở prod vẫn chỉ-mở-link. Muốn khác thì
   cần mini-spec riêng về deployment/auth/TLS.
6. **Chưa bấm tay biểu tượng tiện ích** (§9).

## 11. Commit / tag

- Commit: `security(e1a): harden local API and Vite proxy CORS`
- Tag: **`v1.6-E1a-cors-hardening`** — theo convention sẵn có của repo (`v1.4-E14`,
  `v1.5-E15-closed`), không dùng `v1.16-…` như bản gợi ý.

## 12. Xác nhận

**Chưa push.** Không đẩy commit hay tag nào lên GitHub/GitLab.
