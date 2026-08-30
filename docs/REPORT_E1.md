# Báo cáo Mini-Spec E1 — Chrome Extension Local Companion

**Project:** Translation · **Phase:** E (Browser Companion) · **Ngày:** 2026-08-30
**Nền:** M1–M10 · E11–E15 (`7ca8af6`)
**Trạng thái:** ✅ **Xong và đã đo thật** — 282 test đơn vị/thành phần + 41 mục đo trên Chromium 151

## 1. Summary

E1 dựng một tiện ích Chrome (Manifest V3) đóng vai **cổng mở nhanh** cho web app Translation đang
chạy trên máy: mở màn tạo chapter, xem trạng thái chapter đã ghim, nhảy đúng vào màn rà soát tay
(M7) hoặc màn chapter (chứa khối xuất M8).

Nó **không** đọc trang web bạn đang xem, **không** xin quyền website nào, **không** tải ảnh từ
internet, **không** chạy mô hình AI, và **không** thêm/sửa một endpoint backend nào.

Manifest cuối cùng: `permissions: ["storage", "sidePanel"]`, `host_permissions: []`.

Không có bước build. Thứ Chrome nạp chính là thứ nằm trong repo — không bundler, không mã sinh ra,
nên "no remote hosted code" không cần ai phải tin, chỉ cần mở thư mục ra xem.

## 2. Audit Before Build — bốn phát hiện làm hẹp phạm vi

Bằng chứng đầy đủ: `extension/README.md` §1. Bốn phát hiện, cả bốn đều đổi thiết kế so với bản spec.

**a) Không có endpoint liệt kê chapter.** `GET /api/v1/projects` → **405 Method Not Allowed**;
route `/projects` chỉ có `POST`. Web app lấy "chapter gần đây" từ `localStorage` **của chính nó**
(`translation:chapter-gan-day`), mà tiện ích không được phép đọc — đọc được thì phải có content
script + quyền host, đúng thứ E1 cấm.

⇒ Tiện ích **không tự dò ra** chapter nào. Nó hiện chapter người dùng **tự ghim bằng mã UUID**, rồi
làm mới từng cái qua `GET /projects/{id}`. Đúng đường spec §B4 cho phép: dùng endpoint đã có,
không bịa `/api/v1/extension/*`.

**b) CORS — tôi kết luận SAI ở lượt đo đầu, và đây là phát hiện đáng giá nhất.**

Đo thẳng vào API thì đúng là bị chặn (`CORS_ALLOW_ORIGINS` rỗng, không có header `ACAO`). Tôi đã
định ship E1 ở chế độ "chỉ mở link" vĩnh viễn vì kết luận đó.

Nhưng địa chỉ người dùng nhập vào tiện ích là địa chỉ **giao diện**, không phải API:

| Gọi tới | Kết quả đo (2026-08-30) |
|---|---|
| `http://127.0.0.1:8010/api/v1/health` | 200, **không** có `ACAO` → trình duyệt chặn |
| `http://127.0.0.1:5174/api/v1/health` | 200, **`ACAO: *`** → đọc được |

Máy chủ **dev của Vite** proxy `/api` xuống backend và tự thêm `ACAO: *`. Nên với cách chạy hiện
tại, tiện ích đọc được trạng thái **ngay, không cần cấu hình gì**. Ở bản dựng prod (nginx) thì
`default.conf.template` **không** proxy `/api`, và tiện ích lùi về chế độ chỉ-mở-link — nói thẳng
trên giao diện, không giấu.

⚠️ **Nhận xét bảo mật kèm theo (không phải việc của E1, cố ý không đụng vào):** vì máy chủ dev
gắn `ACAO: *` cho mọi phản hồi proxy, **bất kỳ website nào** đang mở cũng đọc được API Translation
local qua cổng 5173/5174 khi máy chủ dev chạy. Đây là tính chất có sẵn của Vite dev server, tồn
tại từ trước E1.

**c) Giao diện không có router.** `frontend/src/App.jsx` là một màn duy nhất, chọn màn bằng **hash**.
Không có `/create`, `/review`, `/export`. Bảng buộc thật:

| Tiện ích cần | Đường thật | Ghi chú |
|---|---|---|
| Tạo chapter | `<base>/` | form tạo nằm ở trang chủ |
| Tiến độ chapter | `<base>/#project=<uuid>` | |
| Rà soát tay (M7) | `<base>/#page=<uuid>` | |
| Xuất (M8) | `<base>/#project=<uuid>` | **không có route riêng** — khối xuất nằm trong màn chapter |
| Sống chưa | `GET /api/v1/health` | có kiểm CSDL |

Nút "Xuất" mở đúng màn chapter thay vì bịa `#export=`. Có test khoá lại điều này.

**d) Kho mã không có TypeScript.** Giao diện là JSX thuần + Vite 6 + React 18. Spec vẽ cây
`.ts/.tsx`; làm theo thì phải kéo cả TypeScript + bundler vào một kho chưa từng dùng.

⇒ Tiện ích viết bằng **JavaScript ES module thuần, không có bước build**.

**Quyền:** `chrome.tabs.create()` **không** cần quyền `tabs` (quyền đó chỉ để đọc
`url`/`title`/`favIconUrl`). Nên manifest không xin `tabs`.

## 3. Design Choice

**Side Panel là mặt tiền chính, không dựng popup.** Panel sống cạnh tab mà không cần chạm vào tab
đó. Popup bị bỏ hẳn: spec để nó là tuỳ chọn, và một mặt tiền thứ hai chỉ nhân đôi chỗ để sai lệch.

**Điều hướng trước, tải lên sau.** Ảnh vẫn upload qua form của web app. Nhân bản đường upload trong
tiện ích sẽ đẻ ra hợp đồng upload thứ hai, ngữ nghĩa thử-lại thứ hai, và một đường vòng qua M10.

**Trạng thái kết nối có BA giá trị, không phải hai.** `null` = chưa kiểm xong. Bản đầu chỉ có
true/false nên panel nhấp nháy "Chưa kết nối Translation local" trong lúc lượt kiểm còn đang chạy
— khẳng định một thất bại **chưa hề đo được**. Lỗi này chỉ lộ ra ở lượt bấm thật (§5, K17).

**Hỏng thì kể cả hai khả năng.** Từ trong trình duyệt, "máy chủ tắt" và "bị CORS chặn" rơi vào
**cùng một** `TypeError` — không có cách nào phân biệt. Nên chữ hiển thị nêu cả ba khả năng thay
vì đoán bừa một cái rồi nói chắc nịch.

**Nút chỉ bật khi có bằng chứng.** Điều kiện bật nút "Xuất" lấy thẳng từ backend
(`routes.py::export_preview` lọc `typeset_done` + `ready_for_export`), không phải đoán. Chưa đủ
điều kiện thì nút **tắt kèm lý do trong `title`**, không ẩn đi cho gọn mắt.

**Chữ trạng thái chép từ web app.** Có test đọc thẳng
`frontend/src/lib/status-presentation.js` và so từng nhãn — một trạng thái mà panel gọi "Xong" còn
web app gọi "Cần rà soát" là cách nhanh nhất để người dùng mất lòng tin vào cả hai.

## 4. Changed Files

Toàn bộ là **thêm mới**. Không sửa một dòng nào của backend hay frontend.

```
extension/manifest.json                    MV3, 2 quyền, host_permissions rỗng
extension/README.md                        bằng chứng audit + bảng buộc route
extension/PRIVACY.md                       lưu gì / không lưu gì, kiểm chứng được
extension/package.json, vitest.config.js   chỉ devDependency: vitest + jsdom
extension/src/service-worker.js            nối dây sự kiện, KHÔNG giữ state
extension/src/lib/local-url-validator.js   cổng vào loopback + chuẩn hoá UUID
extension/src/lib/storage-schema.js        khuôn + chốt chặn lúc GHI
extension/src/lib/settings.js              bọc chrome.storage.local
extension/src/lib/navigation.js            dựng địa chỉ theo route THẬT
extension/src/lib/translation-client.js    2 endpoint đọc, có hạn giờ
extension/src/lib/status-presentation.js   bảng trạng thái + điều kiện bật nút
extension/src/sidepanel/{index,huong-dan}.html, panel.css, panel.js, panel-view.js
extension/src/options/{index.html,options.js}
extension/public/icons/icon-{16,32,48,128}.png
extension/tests/*.test.js                  7 tệp, 282 test
scripts/do_run_e1.py                       đo thật — nhánh chỉ-mở-link (21 mục)
scripts/do_run_e1_ket_noi.py               đo thật — nhánh đọc được dữ liệu (20 mục)
```

**New API / DB / State: KHÔNG CÓ.** Không endpoint mới, không bảng mới, không migration, không
đổi CORS, không đụng Celery/model AI.

## 5. Tests

**282 test đơn vị + thành phần** (`cd extension && npm test`):

| Tệp | Số | Canh cái gì |
|---|---|---|
| `local-url-validator` | 66 | kho SSRF: IP thập phân/hex/bát phân, IPv6, `localhost.evil.example`, tài khoản nhúng, `..`, query/hash, `javascript:`/`data:`/`file:` |
| `storage` | 56 | khuôn hỏng lùi về mặc định, hạn 24h, tối đa 5, chốt chặn khoá cấm, sống sót qua worker restart |
| `manifest-guardrail` | 48 | ảnh chụp quyền, quét mã tìm API key / `chrome.scripting` / `eval` / `innerHTML` / `setInterval` |
| `panel-view` | 39 | 4 trạng thái panel, bàn phím, nhãn đọc màn hình, không dựng HTML từ dữ liệu máy chủ |
| `status-presentation` | 38 | phủ đủ 10 trạng thái, trạng thái lạ → "Không rõ", **chữ không lệch với web app** |
| `navigation` | 18 | bám đúng route hash thật, từ chối mã bẩn |
| `translation-client` | 17 | gọi đúng endpoint, phân biệt hết-giờ/404/500/dữ-liệu-lạ |

Hai chỗ test **bắt được chính tiền đề của mình sai**, và cả hai đều được ghi lại thay vì lặng lẽ
sửa cho xanh:

- **Dạng IPv4 lạ KHÔNG phải đường lách.** `new URL('http://2130706433:8010').hostname` cho ra đúng
  `127.0.0.1` — chúng thật sự là loopback. Tính chất an toàn nằm ở chỗ khác: hàm trả về địa chỉ
  **đã chuẩn hoá**, và mọi lượt `fetch`/`tabs.create` về sau dùng chuỗi trả về đó chứ không bao giờ
  dùng lại chuỗi người dùng gõ ⇒ không có khe hở "bộ kiểm đọc một đằng, bộ gọi đọc một nẻo".
- **`/healthz` ở cổng giao diện trả về trang HTML** kèm `ACAO: *`, tức "200 OK" cả khi API đã chết.

## 6. Live Verification — Chromium 151.0.7922.34

Nạp unpacked thật, bấm thật. **41/41 đạt.**

### `scripts/do_run_e1.py` — 21/21 (Run A/B/C/D)

- **A** — màn đầu có ô nhập + câu nói rõ phạm vi; gợi ý cổng là cổng **đo được** (5174), không
  phải cổng đoán; `http://evil.example:5174` bị chặn ngay và **không** được ghi vào kho.
- **B** — "Tạo chapter mới" mở đúng `http://127.0.0.1:5174/`, form tạo chapter của web app hiện ra.
- **C** — kho chỉ có khoá đã khai báo; **không** chứa key/ảnh/OCR/đường dẫn tệp/cookie; cài đặt
  sống sót qua lượt mở lại panel; hộp xác nhận xoá nói rõ backend không bị đụng; xoá xong kho sạch
  và backend vẫn sống.
- **D** — manifest không content script, `host_permissions` rỗng, quyền đúng bằng
  `{storage, sidePanel}`; mở một trang bất kỳ: tiện ích **không** tiêm gì, kho **không** ghi lại
  địa chỉ trang đó.
- **Z** — 0 lỗi JS trong console.

### `scripts/do_run_e1_ket_noi.py` — 20/20 (nhánh đọc được dữ liệu)

Ghim **chapter thật** `67094721-…` (3 trang, đều `typeset_done`):

- Lấy **tên thật** ("E11 kiem ban phim"), **số trang thật** ("3 trang · 3 trang xuất được").
- "Mở rà soát" → `#page=194bcdf2-…`; "Xem tiến độ" → `#project=67094721-…`;
  "Xuất" → **cùng** `#project=`, **không** có chữ `export` trong địa chỉ.
- Mã bịa `00000000-…` → máy chủ 404 → panel báo "Không tìm thấy chapter", **không** ghim mục ma.
- Kho sau khi ghim 2 chapter thật: đúng 2 khoá, mỗi mục ghim chỉ có 5 trường trong khuôn, đều có
  `cachedAt`; **không** có `source_lang`/`intended_use`/`image_path`/OCR/key.
- Mở lại panel → ghim còn nguyên **và** trạng thái được lấy lại từ máy chủ.

### Ba lỗi thật do lượt bấm thật tìm ra

| Lỗi | Vì sao test đơn vị không bắt được |
|---|---|
| **Nút chính không bấm được.** `nut()` luôn đặt `type="button"`, nên "Lưu & kiểm tra kết nối" nằm trong `<form>` mà **chưa bao giờ** gửi form — màn đầu vô dụng nếu người dùng bấm chuột thay vì gõ Enter. | Test đơn vị `dispatchEvent(submit)` thẳng vào form, đi vòng qua đúng cái nút hỏng. |
| **Kiểm kết nối gọi nhầm máy chủ.** Gọi `<base>/healthz` trong khi `<base>` là địa chỉ **giao diện** — Vite trả trang SPA kèm 200 + `ACAO: *`. Một bộ kiểm chỉ nhìn mã 200 sẽ báo "đã kết nối" khi API đã chết. | Test dùng `fetch` giả trả JSON đúng khuôn; không ai giả lập "200 nhưng là HTML". |
| **Nhấp nháy "Chưa kết nối" trước khi kiểm xong.** Trạng thái kết nối chỉ có true/false, mặc định false. | Test thành phần luôn truyền `noi_duoc` tường minh, không có ca "chưa biết". |

Cả ba đều đã sửa **và** có test hồi quy khoá lại (`type` phải là `submit`; endpoint không được
chứa `/healthz`; `noi_duoc: null` phải hiện "Đang kiểm tra").

### Ghi chú về `.env`

Để đo nhánh CORS, `.env` đã được thêm tạm một dòng `CORS_ALLOW_ORIGINS` rồi **khôi phục nguyên
vẹn** (đã `diff` xác nhận 0 khác biệt). Kết luận cuối cùng ở §2b được đo lại **sau khi** khôi
phục — tức là với `.env` sạch, không cấu hình gì thêm.

## 7. Remaining Limits — nói thẳng

1. **Không tự thấy chapter.** Phải ghim bằng mã UUID chép từ địa chỉ web app. Chừng nào backend
   chưa có endpoint liệt kê project thì không có đường nào khác mà không phá guardrail quyền.
   ⇒ Ứng viên mini-spec backend: `GET /api/v1/projects` chỉ-đọc, có phân trang.
2. **Bản dựng prod (nginx) chỉ mở link được** — nginx không proxy `/api`. Nối được trạng thái ở
   prod cần một mini-spec bảo mật riêng (allowlist theo extension ID cố định).
3. **Chỉ loopback.** Không hỗ trợ server LAN/từ xa. Cần TLS/auth/CORS riêng.
4. **Không truyền tệp từ tiện ích sang web app.** Người dùng chọn ảnh trong form của web app.
5. **Chưa phát hành Chrome Web Store.** Chỉ load unpacked. Phát hành cần mini-spec riêng về đóng
   gói, khai báo quyền riêng tư, extension ID cố định.
6. **Chưa đo trên Chrome bản người dùng thật** — mới đo trên Chrome for Testing 151 ở chế độ
   headless mới. Side Panel mở bằng cách bấm biểu tượng chưa bấm được trong headless; trang panel
   được mở thẳng bằng địa chỉ `chrome-extension://…`. Bản thân `sidePanel.setPanelBehavior` chạy
   không lỗi (console sạch), nhưng **hành vi bấm biểu tượng cần một lượt bấm tay để xác nhận**.
7. **E2/E3 vẫn nằm ngoài.** Không nhận URL ảnh, không quét website, không phủ bản dịch. Mỗi cái
   cần audit SSRF/nguồn/bản quyền/consent riêng.
