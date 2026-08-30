# SECURITY.md — Ranh giới truy cập của Translation (local-only)

Tài liệu này mô tả **ai được đọc API Translation trên máy bạn**, tầng nào chịu trách nhiệm, và
cách thêm một origin mới cho đúng. Chốt ở mini-spec **E1a** (2026-08-30).

> ⚠️ **CORS không phải xác thực.** Nó chỉ ngăn *trang web trong trình duyệt* đọc phản hồi.
> Bất cứ chương trình nào chạy trên máy bạn (curl, script, app khác) vẫn gọi thẳng được API —
> CORS không đụng tới chúng. Translation hiện **chưa có auth, chưa multi-user, chưa TLS**;
> nó là công cụ chạy trên máy cá nhân.

---

## 1. Vì sao E1a tồn tại — lỗ hổng đo được

Đo ngày 2026-08-30, **trước** khi sửa:

```
curl -H "Origin: https://evil.example" http://127.0.0.1:5174/api/v1/projects/<id>
→ HTTP 200
→ Access-Control-Allow-Origin: *
```

Nghĩa là: **bất kỳ website nào** bạn đang mở trong trình duyệt cũng đọc được tên chapter, trạng
thái trang, và metadata dịch của Translation local — chỉ cần máy chủ dev đang chạy.

Nguồn phát wildcard là **một tầng duy nhất**: Vite 6.0.7 mặc định `server.cors: true`, tức gắn
`Access-Control-Allow-Origin: *` vào **mọi** phản hồi, kể cả phản hồi đã proxy `/api` xuống
backend. Backend FastAPI **không** liên quan — nó vốn đã chặn mặc định.

---

## 2. Ai sở hữu cấu hình CORS ở tầng nào

Có **hai** cấu hình riêng, cố ý không gộp. Lý do: chúng bảo vệ hai thứ khác nhau, ở hai giai
đoạn khác nhau. Gộp lại thì một origin khai cho lúc deploy sẽ vô tình được mở luôn trên máy chủ
dev của mọi người.

| Tầng | Biến | Mặc định | Bảo vệ điều gì |
|---|---|---|---|
| **Máy chủ dev Vite** (`frontend/vite.config.js`) | `DEV_SERVER_CORS_ALLOW_ORIGINS` | **rỗng ⇒ chặn hết** | Máy dev của bạn, nơi cổng 5173/5174 mở ra trong lúc code |
| **API FastAPI** (`backend/app/main.py`) | `CORS_ALLOW_ORIGINS` | **rỗng ⇒ không gắn middleware** | Lúc chạy thật, khi giao diện và API nằm ở hai tên miền khác nhau |
| **nginx bản prod** (`frontend/default.conf.template`) | — | không có header CORS nào, không proxy `/api` | Chỉ phục vụ tệp tĩnh của SPA |

Bộ kiểm dùng chung cho tầng dev: `frontend/cors-allowlist.js` (có 68 test đơn vị ở
`frontend/src/test/cors-allowlist.test.js`).

**Máy chủ dev không kế thừa gì sang prod, và ngược lại.**

---

## 3. Luật — chặn mặc định

1. **Không bao giờ** `Access-Control-Allow-Origin: *` ở bất kỳ tầng nào.
2. **Không phản chiếu Origin của request.** Chỉ so khớp **tuyệt đối** với danh sách đã khai.
3. **Không mẫu, không regex.** `*`, `localhost.*`, `*.local`, `chrome-extension://*` đều bị bộ
   kiểm từ chối ngay lúc đọc cấu hình.
4. **Không** `Access-Control-Allow-Credentials` — hệ thống chưa có auth/cookie nào để bảo vệ.
5. Origin không nằm trong danh sách: **không có** header `Access-Control-Allow-Origin` nào.
6. Origin có trong danh sách: trả **đúng** origin đó, kèm `Vary: Origin`.
7. Chỉ mở method/header thật sự dùng: `GET, POST, PATCH, OPTIONS` và `Content-Type`.
8. http/https chỉ nhận `localhost` và `127.0.0.1`. LAN IP, private IP, tên miền công cộng,
   `file:`, `data:`, `javascript:`, `null` — đều bị từ chối.

### Giao diện web KHÔNG cần CORS

Trang tải từ `http://127.0.0.1:5174` gọi `/api/v1/...` cũng ở `http://127.0.0.1:5174` — **cùng
nguồn**, nên trình duyệt không hề chạy phép kiểm CORS. Đó là lý do tắt hẳn CORS mặc định vừa an
toàn vừa không hỏng gì.

---

## 4. Tiện ích E1 — mặc định là chỉ-mở-link

Tiện ích chạy ở origin `chrome-extension://<id>`, tức **khác** nguồn với web app. Với cấu hình
mặc định (danh sách rỗng), tiện ích **không đọc được** trạng thái chapter và tự lùi về chế độ
**chỉ-mở-link**: vẫn mở đúng route web app, và nói thẳng lý do trên giao diện thay vì hiện danh
sách rỗng như thể bạn chưa có chapter nào.

**Đây là trạng thái mặc định được khuyến nghị.** Tiện ích không phải lý do để mở API local cho
người khác.

### Muốn tiện ích đọc được trạng thái

1. Lấy ID thật ở `chrome://extensions` (chuỗi 32 chữ cái a–p), hoặc mở trang **Cài đặt kết nối**
   của tiện ích — nó in sẵn `chrome-extension://<id>` của bản cài trên máy bạn.
2. Chạy lại máy chủ giao diện với đúng origin đó:

```bash
cd ~/workspace/projects/Translation
DEV_SERVER_CORS_ALLOW_ORIGINS="chrome-extension://<id-32-ký-tự-của-bạn>" \
  docker compose -f deploy/docker-compose.yml up -d --force-recreate frontend
```

3. Kiểm log: `docker logs translation-frontend-1 | grep cors` phải in ra đúng origin bạn khai.

⚠️ **ID tiện ích chỉ ổn định theo đường dẫn.** Chrome suy ID của tiện ích nạp-thủ-công từ
**đường dẫn tuyệt đối** của thư mục. Đổi máy hoặc đổi chỗ để thư mục ⇒ ID đổi ⇒ phải khai lại.
Vì vậy **không** đưa ID nào vào mặc định của repo — mỗi người tự khai ID của mình.

**Tuyệt đối không** dùng `chrome-extension://*` để "cho tiện ích chạy". Nó mở cửa cho **mọi**
tiện ích đang cài trong trình duyệt.

---

## 5. Cách tự kiểm không còn wildcard

```bash
# Website lạ KHÔNG được có ACAO
curl -sD- -o /dev/null -H "Origin: https://evil.example" \
  http://127.0.0.1:5174/api/v1/health | grep -i access-control

# Giao diện web vẫn chạy (cùng nguồn, không cần CORS)
curl -s http://127.0.0.1:5174/api/v1/health     # -> {"status":"ok"}
```

Nhưng **curl không phải bằng chứng cuối**: CORS do trình duyệt thi hành. Phép đo thật nằm ở
`scripts/do_run_e1a.py` — nó dựng một website lạ ở cổng 9999, ánh xạ `localhost.evil.example`
về loopback, rồi bấm thật trên Chromium.

---

## 6. Thêm một origin mới — quy trình

1. Viết mini-spec nêu **vì sao** origin đó cần đọc API local và nó có gì để mất.
2. Thêm vào đúng **một** tầng (dev hay prod), không rải hai nơi.
3. Thêm ca kiểm vào `frontend/src/test/cors-allowlist.test.js`.
4. Chạy `scripts/do_run_e1a.py`, ghi bằng chứng vào `TEST_LOG.md`.
5. Cập nhật tài liệu này.

---

## 7. Bẫy đã gặp — ghi lại để khỏi mất thời gian lần nữa

### 7.1 Đường dẫn compose

Compose **không** nằm ở `~/workspace/deploy/`. Đường thật:

```
~/workspace/projects/Translation/deploy/docker-compose.yml
```

Chạy từ gốc repo:

```bash
cd ~/workspace/projects/Translation
docker compose -f deploy/docker-compose.yml up -d
```

Chạy nhầm ở `~/workspace` sẽ báo `no such file or directory`. **Lỗi đó không có nghĩa là Docker
hay API đã chết** — hãy kiểm bằng `docker ps` và endpoint thật.

### 7.2 `/healthz` ở cổng giao diện KHÔNG phải health của API

```
http://127.0.0.1:8010/healthz  -> content-type: application/json   (API thật, uvicorn)
http://127.0.0.1:5174/healthz  -> content-type: text/html          (trang SPA!)
```

Máy chủ dev trả trang SPA cho mọi đường lạ, nên `/healthz` ở cổng 5174 trả **200 kèm HTML** ngay
cả khi API đã chết. Bộ kiểm kết nối của tiện ích vì thế gọi `/api/v1/health` và **bắt buộc thân
phải là JSON đúng khuôn** — 200 không phải bằng chứng.

### 7.3 `worker: khong_ro` không nói worker khoẻ hay chết

```json
{"status":"ok","worker":{"trang_thai":"khong_ro"}}
```

`khong_ro` chỉ có nghĩa **API không biết**: nó đọc `/tmp/trang-thai-worker.json`, tệp chỉ tồn tại
khi API và worker chạy chung một container (`ROLE=all`). Ở bản docker dev, chúng là hai container
riêng nên API không thể biết — và nó nói thẳng thay vì đoán.

Muốn biết worker có sống không thì đo riêng:

```bash
docker exec translation-worker-1 celery -A app.workers.celery_app.celery_app inspect ping
docker exec translation-db-1 psql -U translation -d translation \
  -c "select status, count(*), max(updated_at) from job \
      where updated_at > now() - interval '1 hour' group by status;"
```

### 7.4 Worker không nạp lại mã Python

Thư mục `backend/` được mount làm volume nên **tệp** luôn mới, nhưng Celery nạp module lúc khởi
động. Sửa mã worker xong **phải** `docker compose -f deploy/docker-compose.yml restart worker`,
nếu không là đo nhầm mã cũ. (Bài học từ E15 — xem `REPORT_E15.md` §7.3.)

---

## 8. Giới hạn còn lại — nói thẳng

- **CORS không thay auth.** Không có đăng nhập, không phân quyền, không multi-user, không TLS.
- **Chỉ dành cho máy cá nhân.** Đưa ra LAN hay internet cần một mini-spec riêng về
  TLS/auth/origin.
- **Phần siết ở đây áp cho máy chủ dev local.** Không được đọc thành "đã an toàn cho production".
- Bất kỳ tiến trình nào **trên chính máy bạn** vẫn gọi được API — CORS không ngăn điều đó.
