# Translation Companion — tiện ích Chrome (E1)

Tiện ích **mở nhanh** công cụ Translation đang chạy trên máy bạn. Nó **không** đọc trang web bạn
đang xem, **không** tự tải ảnh từ internet, và **không** dịch gì cả — mọi xử lý vẫn nằm ở web app
và backend local như cũ.

---

## 1. Audit trước khi dựng — bằng chứng

Đo ngày **2026-08-30**, trên hệ đang chạy thật (`deploy/docker-compose.yml`, 5 container `Up`).
Spec E1 §5 bắt buộc ghi lại phần này **trước** khi viết mã, vì 4 trong 9 mục audit đã làm hẹp
phạm vi so với bản spec.

### 1.1 Cổng & lệnh chạy

| Thứ | Giá trị đo được | Nguồn |
|---|---|---|
| API | `http://127.0.0.1:8010` (container `8000`) | `deploy/docker-compose.yml` → `API_PORT:-8010` |
| Giao diện (docker) | `http://127.0.0.1:5174` | compose `frontend: "5174:5173"` |
| Giao diện (vite dev) | `http://127.0.0.1:5173` | `frontend/package.json` → `vite --port 5173` |
| Chromium đo thật | Google Chrome for Testing **151.0.7922.34** | `chrome --version` |

`5173` **không** chạy lúc đo (`curl` → 000); `5174` và `8010` trả 200. Ô nhập địa chỉ trong tiện
ích để gợi ý `http://127.0.0.1:5174`, **không** phải cổng đoán từ ảnh chụp màn hình.

### 1.2 Bảng buộc (route/endpoint) — spec §C

| Tiện ích cần | Đường thật đang có | Trạng thái |
|---|---|---|
| Sống chưa | `GET /healthz` (app-level, kèm trạng thái worker) | ✅ có sẵn |
| Sống chưa (dự phòng) | `GET /api/v1/health` (có kiểm DB, `include_in_schema=False`) | ✅ có sẵn |
| Danh sách chapter | — | ❌ **không tồn tại** (xem 1.3) |
| Chi tiết + tiến độ chapter | `GET /api/v1/projects/{project_id}` → `ProjectDetail` | ✅ có sẵn |
| Màn tạo chapter | `<base>/` (trang chủ, không có hash) | ✅ có sẵn |
| Màn chapter / tiến độ | `<base>/#project=<uuid>` | ✅ có sẵn |
| Màn rà soát tay (M7) | `<base>/#page=<uuid>` | ✅ có sẵn |
| Màn xuất (M8) | — không có route riêng, `ExportPanel` nằm **trong** màn chapter | ⚠️ dùng `#project=` |

**Không** endpoint nào được thêm hay sửa cho E1.

### 1.3 Phát hiện chặn phạm vi

**A. Không có endpoint liệt kê chapter.** `GET /api/v1/projects` trả **405 Method Not Allowed** —
route `/projects` chỉ có `POST`. Web app hiện lấy danh sách "gần đây" từ `localStorage` **của
chính nó** (khoá `translation:chapter-gan-day`, `frontend/src/App.jsx`), mà tiện ích thì không
được phép đọc — đọc được phải có content script + quyền host, đúng thứ E1 cấm.

→ Tiện ích **không tự dò ra** chapter nào. Nó chỉ hiện chapter bạn **tự ghim bằng mã**, rồi làm
mới từng cái qua `GET /projects/{id}`. Spec §B4 cho phép đúng đường này: dùng endpoint đã có,
không bịa `/api/v1/extension/*`.

**B. CORS: chặn nếu gọi thẳng API, KHÔNG chặn nếu đi qua địa chỉ web app.**

Lần đo đầu tiên tôi kết luận sai. Đo thẳng vào API thì đúng là bị chặn — `CORS_ALLOW_ORIGINS`
rỗng trong `.env`, và:

```
curl -i -H "Origin: chrome-extension://<id>" http://127.0.0.1:8010/api/v1/health
→ 200 OK, KHÔNG có header access-control-allow-origin      (server: uvicorn)
```

Nhưng địa chỉ người dùng nhập vào tiện ích là địa chỉ **giao diện**, không phải API. Và qua đó:

```
curl -i -H "Origin: chrome-extension://<id>" http://127.0.0.1:5174/api/v1/health
→ 200 OK, access-control-allow-origin: *                   (server: uvicorn)
```

Máy chủ **dev của Vite** proxy `/api` xuống backend và **tự thêm `ACAO: *`** vào phản hồi. Nên với
cách chạy hiện tại (`deploy/docker-compose.yml`, frontend dựng ở stage `dev`), tiện ích đọc được
trạng thái **ngay, không cần cấu hình gì**. Đã đo thật: 20/20 mục ở `scripts/do_run_e1_cors.py`.

Bảng đầy đủ:

| Cách chạy Translation | Nhập vào tiện ích | Đọc được trạng thái? |
|---|---|---|
| Docker dev (đang dùng) | `http://127.0.0.1:5174` | ✅ Được ngay — Vite proxy `/api` + `ACAO: *` |
| `npm run dev` ở `frontend/` | `http://127.0.0.1:5173` | ✅ Được ngay, cùng lý do |
| Bản dựng prod (nginx) | địa chỉ giao diện | ❌ nginx **không** proxy `/api` (xem `default.conf.template`) |

Với bản prod, tiện ích lùi về **chế độ chỉ-mở-link**: vẫn mở web app bình thường, chỉ không hiện
được trạng thái. Đây là giới hạn được nói thẳng trên giao diện, không phải lỗi giấu đi. Nối được
trạng thái ở bản prod cần một mini-spec backend riêng (allowlist theo extension ID cố định) —
**không** thuộc E1, và tuyệt đối **không** giải quyết bằng `Access-Control-Allow-Origin: *`.

> ⚠️ **Một nhận xét bảo mật, không phải việc của E1:** vì máy chủ dev của Vite gắn `ACAO: *` cho
> mọi phản hồi proxy, **bất kỳ website nào** bạn đang mở cũng đọc được API Translation local qua
> cổng 5173/5174 khi máy chủ dev đang chạy. Đây là tính chất có sẵn của máy chủ dev, tồn tại từ
> trước E1 và không liên quan tới tiện ích. E1 cố ý **không** đụng vào nó.

**C. Giao diện không có router.** `frontend/src/App.jsx` là một màn duy nhất, chọn màn bằng
**hash** (`#project=`, `#page=`) chứ không phải `react-router`. Không có `/create`, `/review`,
`/export`. Bảng 1.2 ghi đúng đường thật; tiện ích **không** bịa route mới.

**D. Kho mã không có TypeScript.** Giao diện là **JSX thuần + Vite 6 + React 18**, `npm`,
không có `tsconfig`. Bản spec vẽ cây thư mục `.ts/.tsx`; dựng theo đó thì phải kéo cả bộ
TypeScript + bundler vào một kho chưa từng dùng.

→ Tiện ích viết bằng **JavaScript ES module thuần, KHÔNG có bước build**. Thứ Chrome nạp chính là
thứ nằm trong repo — không bundler, không sourcemap, không mã sinh ra. Cách này thoả điều kiện
"no remote hosted code" ở mức mạnh nhất: **không có gì để so lệch giữa nguồn và bản đóng gói**.

### 1.4 Quyền — thực đo

`chrome.tabs.create()` **không** cần quyền `tabs` (quyền đó chỉ để đọc `url`/`title`/`favIconUrl`
của tab). Nên manifest không xin `tabs`.

Manifest cuối cùng chỉ có: `storage`, `sidePanel`. `host_permissions` **rỗng**.

### 1.5 Khoảng trống đã xác nhận

Web app hiện **không có** lối mở nhanh từ trình duyệt. E1 lấp đúng chỗ đó — và **chỉ** chỗ đó.

---

## 2. Cài (load unpacked)

1. Chrome → `chrome://extensions` → bật **Developer mode**.
2. **Load unpacked** → chọn thư mục `extension/` này.
3. Bấm biểu tượng tiện ích trên thanh công cụ → Side Panel mở ra.
4. Nhập địa chỉ Translation local, ví dụ `http://127.0.0.1:5174` → **Lưu & kiểm tra kết nối**.

Chưa phát hành lên Chrome Web Store — E1 cố ý dừng ở bản load unpacked.

## 3. Nếu tiện ích báo "chưa kết nối"

Với cách chạy docker dev hiện tại thì **không cần cấu hình gì** — nhập đúng `http://127.0.0.1:5174`
là xong. Nếu vẫn báo chưa kết nối:

1. Ứng dụng Translation chưa chạy → `docker compose -f deploy/docker-compose.yml up -d`.
2. Sai cổng → đọc `.env`, hoặc thử `5173` nếu bạn chạy `npm run dev` tay.
3. Bạn đang dùng **bản dựng prod (nginx)** → nginx không proxy `/api`, tiện ích chỉ mở link được.
   Muốn đọc trạng thái ở bản prod thì cần thêm ID tiện ích vào `CORS_ALLOW_ORIGINS` trong `.env`
   **và** trỏ tiện ích vào một giao diện có proxy `/api` — chuyện này thuộc một mini-spec riêng.

Lấy ID tiện ích ở `chrome://extensions`, hoặc mở trang **Cài đặt kết nối** của tiện ích — nó in
sẵn `chrome-extension://<id>` của bản cài trên máy bạn.

## 4. Giới hạn cố ý

| Không làm | Vì sao |
|---|---|
| Đọc nội dung trang web đang xem | Không có content script, không có quyền host |
| Tải ảnh từ URL | Thuộc E2, cần kiểm SSRF/nguồn/bản quyền riêng |
| Phủ bản dịch lên trang truyện | Thuộc E3, cần content script + quyền từng site |
| Tải ảnh lên thẳng từ tiện ích | Upload vẫn đi qua form của web app (spec §B5) |
| Nhớ API key / ảnh / chữ OCR / bản dịch | Xem `PRIVACY.md` |
| Nối tới server LAN/từ xa | Chỉ cho loopback (`localhost` / `127.0.0.1`) |

## 5. Chạy test

```bash
cd extension && npm install && npm test
```
