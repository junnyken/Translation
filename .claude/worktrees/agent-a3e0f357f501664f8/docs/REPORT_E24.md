# Báo cáo Mini-Spec E24 — Báo tab đang chạy bundle cũ

**Project:** Translation · **Phase:** E — Hosted Reliability & Performance
**Ngày:** 2026-09-10 · **Nền:** `faec936` (sau E25 đóng)
**Trạng thái:** **LIVE** (deploy 2026-09-11, web v33→34 rồi api v58→59, build từ commit `44fcb854`)
· code + test xong · **live-verified ĐẠT** (§6)

## 1. Summary

`REPORT_E21b.md §11.3` ghi lại một lỗi thật đã xảy ra và **chưa có gì chặn**: ai mở sẵn tab từ
trước lúc deploy thì chạy **frontend cũ trên backend mới**. Cụ thể: sửa chữ gốc OCR rồi bấm Lưu ⇒
phần sửa **đã ghi thành công** nhưng giao diện báo lỗi tải job (`/jobs/null`), người dùng không biết
đã lưu hay chưa và nhiều khả năng bấm lại. Dữ liệu không mất, nhưng đó là **thông báo sai**.

Deploy frontend trước (E21b đã làm đúng thứ tự) **không** đóng được cửa sổ này, vì tab đang mở
không tự nạp lại bundle. Lỗi này sẽ tái diễn ở **mọi** lần deploy đổi hợp đồng API.

E24 thêm một banner "có bản mới — tải lại đi", phát hiện bằng cách tự so bundle.

**Giới hạn phải nói trước:** cơ chế này **không cứu được tab đang chạy bundle cũ hiện tại** —
bundle cũ không chứa mã này. Nó chỉ có tác dụng từ lần deploy **sau**. Không có cách nào sửa được
điều đó từ phía frontend; đó là bản chất của việc mã kiểm tra phải nằm trong mã được kiểm.

## 2. Audit Before Build

| Hạng mục | Kết quả audit |
|---|---|
| Có hạ tầng version/build-id nào ở frontend chưa? | **KHÔNG.** Toàn repo chỉ có `package.json` `"version": "0.7.0"` (không được nội tuyến vào bundle) và `import.meta.env.VITE_API_BASE`. Không có `__BUILD_ID__`, không có service worker. |
| Backend có endpoint version không? | Có `GET /health` (`routes.py:2547`, `include_in_schema=False`) và `app.version = "0.1.0-M1"` ở `main.py` — nhưng **không dùng được** cho việc này, xem §3. |
| `index.html` có mấy script? | Sau build: đúng 2 — `assets/index-<hash>.js` (điểm vào, có hash) và `config.js` (**không** hash, do `docker-entrypoint.sh` ghi lại lúc khởi động). |
| Vite `preview` có proxy `/api` không? | **KHÔNG** — chỉ `server` có (`vite.config.js`). Ảnh hưởng tới cách kiểm live, xem §6. |

## 3. Design Choice

**Phép so: "bundle tôi đang chạy có còn được `index.html` hiện tại tham chiếu không?"**
Không còn ⇒ tab đã cũ.

Ba lựa chọn đã cân, và lý do loại hai cái kia:

| Cách | Vì sao KHÔNG chọn |
|---|---|
| Backend gửi header version, FE so với hằng số build-time | **Không dùng được**: frontend và backend là hai lần deploy **tách nhau** (`REPORT_E21b §11.1`), backend không thể biết version frontend. Và deploy chỉ-frontend sẽ không phát hiện được gì. |
| Bắt lỗi API rồi suy ra lệch hợp đồng | Quá hẹp và giòn — chỉ bắt được đúng những lỗi đã biết, mà vấn đề là những lỗi **chưa** biết ở lần đổi hợp đồng sau. |
| **So bundle qua `index.html`** ✓ | Chính kỹ thuật đã dùng để phân biệt dứt điểm "cache trình duyệt" với "deploy hỏng" ở §11.3 — đã được chứng minh trên hiện trường. Không cần backend đổi gì. Bắt được cả deploy chỉ-frontend. |

**Không đoán tên chunk.** Không dò `index-<hash>.js` bằng regex hình dạng, vì tên đó do bộ đóng gói
quyết định và đổi được. Chỉ kiểm **sự hiện diện** của tên tệp mình đang chạy trong danh sách script
của `index.html`. Hệ quả tốt: ở chế độ dev bundle là `/src/main.jsx` và `index.html` **vẫn** trỏ
tới nó ⇒ tự đúng, **không cần nhánh đặc biệt cho dev** (có test canh: `CHƯA cũ ở chế độ dev`).

**`import.meta.url` phải lấy ở `main.jsx`, không phải `App.jsx`.** `index.html` trỏ tới chunk của
**điểm vào**. Lấy từ `App.jsx` thì ở chế độ dev ra `/src/App.jsx` — không có trong `index.html` ⇒
banner hiện **sai** ngay khi chạy dev. Đây là chỗ dễ sai nhất của cả slice.

**`cache: 'no-store'` là bắt buộc, và có test riêng canh nó.** Thiếu nó thì trình duyệt trả đúng
bản đã cache, phép so luôn nói "không có bản mới", và cơ chế **tự vô hiệu hoá mà không có lỗi nào
nổ ra** để ai đó phát hiện. Test `LUÔN tải index.html với cache no-store` tồn tại chỉ vì điều này.

**Thà bỏ sót hơn báo sai.** Mọi lỗi (mạng, HTML lạ, không parse được, không biết bundle đang chạy)
đều trả `false`. Một banner hiện sai sẽ dạy người dùng phớt lờ nó, và lần thật sự cần thì họ cũng
bỏ qua — hỏng luôn cả cơ chế.

**KHÔNG tự tải lại trang.** Tự tải lại sẽ xoá đúng thứ E21b vừa dựng để bảo vệ: chữ đang gõ dở.
Chỉ hiện banner để người dùng chọn thời điểm; bấm "Tải lại ngay" mà còn thay đổi chưa lưu thì
`beforeunload` của E21b vẫn chặn. Hai cơ chế xếp tầng đúng thứ tự.

**Kiểm lại lúc tab được xem lại, không chỉ theo nhịp 5 phút.** Cảnh phổ biến nhất là tab bị bỏ đó
nhiều giờ rồi mở lại — đúng lúc đó mới cần biết. Chờ hết nhịp định kỳ là để người dùng kịp bấm Lưu
và nhận thông báo lỗi giả *trước khi* được cảnh báo.

**Banner hiện cả ở màn đăng nhập.** Đăng nhập **không** nạp lại bundle, nên tab cũ vẫn cũ sau khi
vào. Báo sớm để họ tải lại **trước** khi làm việc, tốt hơn hẳn tải lại sau khi đã gõ.

**Đặt polling trong component riêng, không nhồi vào `App.jsx`.** `App.jsx` hiện **không có một
unit test nào** (khoảng trống có từ trước, ghi ở `TEST_LOG.md` mục E21b). Nhồi thêm wiring vào đó
là thêm mã không ai canh. `BangBanMoi` tự lo vòng đời và **có 9 test riêng**.

## 4. Changed Files

| Tệp | Việc |
|---|---|
| `frontend/src/lib/phien-ban-moi.js` | **MỚI** — logic thuần: `tenTep`, `cacScriptTrongHtml`, `bundleDaCu`, `kiemBanMoi`. |
| `frontend/src/lib/phien-ban-moi.test.js` | **MỚI** — 16 test. |
| `frontend/src/components/BangBanMoi.jsx` | **MỚI** — banner + vòng đời polling/visibilitychange. |
| `frontend/src/components/BangBanMoi.test.jsx` | **MỚI** — 9 test. |
| `frontend/src/main.jsx` | Truyền `urlBundle={import.meta.url}` từ **điểm vào**. |
| `frontend/src/App.jsx` | Nhận prop `urlBundle`; render `<BangBanMoi>` ở cả nhánh đã đăng nhập và nhánh đăng nhập. |
| `frontend/src/styles.css` | `.bang-ban-moi` dính đỉnh (`position: sticky`). |

Không đổi backend. Không migration. Không đổi hợp đồng API.

## 5. Tests

```
$ cd frontend && npm test -- --run
361 passed (23 file)        (331 nền E21b + 25 của E24 + 5 của E23)
$ npm run build
✓ built in 2.48s            dist/assets/index-<hash>.js
```

Kiểm thêm trên **HTML thật do Vite sinh** (không phải fixture tôi tự viết) — quan trọng vì unit
test không bắt được sai giả định về hình dạng output:

| Đầu vào | `bundleDaCu` | Mong đợi |
|---|---|---|
| bundle mới `index-FQWWfZ_R.js` | `false` | `false` ✓ |
| bundle cũ `index-BBBiktgW.js` (hash THẬT từ §11.3) | `true` | `true` ✓ |
| URL tuyệt đối của bundle mới | `false` | `false` ✓ |

Phát hiện phụ: `index.html` còn trỏ tới `config.js` **không có hash**. Không ảnh hưởng phép so
(chỉ kiểm sự hiện diện của chính bundle mình), nhưng nghĩa là `config.js` đổi thì trình duyệt có
thể vẫn dùng bản cache — ngoài phạm vi E24, ghi lại để biết.

## 6. Live Verification — ĐẠT, Chromium thật

Lượt kiểm đầu bị chặn: `Runtime.evaluate` và `Accessibility.getFullAXTree` đều **timeout** kể cả
với script tầm thường, vì máy đang chạy E23 (load average **17,27** trên 12 core, Celery ăn
**762% CPU**). Tab đó về sau mất cả tiêu đề — renderer Chrome gần như chắc là một trong **99** tiến
trình bị OOM killer của workspace giết (`REPORT_E23 §6.1`). Đã dựng lại từ đầu khi load về 2,10.

**Bước 1 — bundle còn mới thì KHÔNG báo gì.** Build A (`index-0VIGJVIg.js`), phục vụ tĩnh cổng
8098, mở bằng Chromium thật:

```json
{"bundleTabDangChay": ["index-0VIGJVIg.js", "config.js"], "bannerCoHien": false}
```

**Bước 2 — deploy bản mới trong khi tab vẫn mở.** Build B ra hash khác (`index-8rNPLAek.js`) — đổi
bằng biến env `VITE_API_BASE`, **không sửa tệp nguồn nào** — rồi copy vào đúng thư mục đang phục
vụ. Xác nhận `index.html` trả B, bundle A **vẫn còn** trên đĩa (tab đang mở cần nó). Đúng cảnh
production. Rồi phát `visibilitychange` để giả lập người dùng quay lại tab:

```json
{
  "bundleTabVanDangChay": "index-0VIGJVIg.js",
  "bannerTruoc": false, "bannerSau": true, "coNutTaiLai": true,
  "chu": "Có bản mới của giao diện Tab này đang chạy bản cũ nên có thể báo lỗi sai dù việc
          bạn làm đã được lưu. Tải lại trang để dùng bản mới. Nếu đang gõ dở, hệ thống sẽ…"
}
```

**Ba điều được chứng minh cùng lúc:**
1. Banner hiện đúng lúc, với đúng câu chữ, có nút "Tải lại ngay".
2. **Không tự tải lại** — `bundleTabVanDangChay` vẫn là A *sau khi* banner hiện. Đây là bằng chứng
   trực tiếp cho quyết định ở §3 (tự tải lại sẽ xoá chữ đang gõ dở của E21b).
3. Dây nối đi đúng: `import.meta.url` từ `main.jsx` → prop `urlBundle` → `BangBanMoi`. Phần này
   unit test **không** chứng minh được.

**Một chỗ tôi kiểm lại thay vì tin ảnh:** ảnh chụp cho thấy banner xuất hiện **hai lần** (đỉnh và
cuối trang). Đếm DOM thật: `soBanner: 1`, ở `top: 0`, viewport 1905×2053. Đó là tạo tác chụp ảnh
với viewport rất cao + `position: sticky`, **không** phải render trùng.

⇒ **E24 đã live-verified.** Vẫn **chưa deploy** — chờ quyết định của người dùng.

## 7. Remaining Limits

- **Không cứu được tab cũ hiện tại.** Chỉ có tác dụng từ lần deploy sau. Bản chất, không sửa được.
- Nhịp kiểm 5 phút là con số **chọn theo phán đoán**, chưa đo. Cửa sổ xấu nhất: người dùng mở tab
  đúng lúc deploy xong và làm việc ngay trong 5 phút đầu mà không rời tab — vẫn gặp lỗi giả.
  `visibilitychange` thu hẹp cảnh phổ biến nhất nhưng không đóng hết.
- Banner nói "có bản mới" chứ **không** nói mới ở chỗ nào. Muốn nói được thì cần changelog theo
  version — chưa có hạ tầng đó, và không đáng dựng chỉ cho việc này.
- `config.js` không có hash (§5) nên vẫn có thể bị cache riêng.
- **Không xử lý cảnh ngược:** backend cũ + frontend mới. E21b §11.1 đã xác định chiều đó FE-new
  tolerates BE-old nên không vỡ, nhưng E24 không kiểm gì về nó.
