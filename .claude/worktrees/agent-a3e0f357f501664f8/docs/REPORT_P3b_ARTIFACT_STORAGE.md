# Báo cáo Mini-Spec P3b — Lưu trữ hiện vật bền & cổng toàn vẹn

**Ngày:** 2026-08-31 · **Trạng thái:** ⛔ **BLOCKED** — §5.2(5): nền tảng không có cơ chế volume bền
**Phụ thuộc:** P3a `BLOCKED` · hosted web v13 / API v22

## Kết quả: `BLOCKED`

Audit Step 1 hoàn tất. **Không viết một dòng mã nào, không đụng cấu hình VibeHost nào** — đúng
theo §7 Step 1 và §5.2(5): *"If no persistent volume capability exists or cannot mount
/app/storage, stop BLOCKED before coding misleading integrity behavior alone."*

**Tiêu chí hỏng: §9 mục 1** — không chứng minh được volume bền gắn tại `/app/storage`, vì
**nền tảng không cung cấp cơ chế đó**.

Viết lớp toàn vẹn hiện vật lúc này chỉ đổi một lời nói dối (*"typeset_done" mà ảnh 404*) lấy một
lời nói dối tinh vi hơn (*"đã có lưu trữ bền"* trong khi vẫn là lớp ghi container).

---

## §5.1 — Kiểm kê đường lưu trữ thật

### Đã có sẵn một lớp trừu tượng

`backend/app/services/storage.py` (111 dòng) — `IObjectStorage` (Protocol) + `LocalObjectStorage`:
`save_page_image`, `read`, `exists`, `delete`, `abs_path`, `to_relative`.

⇒ **Không cần dựng lớp mới**, chỉ cần siết và mở rộng lớp đang có (§B1).

### Người ghi / người đọc

| Vai | Nơi | Cách gọi |
|---|---|---|
| Ghi ảnh gốc (M1) | `storage.save_page_image()` | qua lớp trừu tượng |
| Ghi ảnh clean (M4) | `tasks.py:1178` `storage.abs_path(clean_rel)` | **đưa đường tuyệt đối cho engine tự ghi** |
| Ghi preview (M6/M7) | `tasks.py:1180` `storage.abs_path(preview_rel)` | như trên |
| Ghi file xuất (M8) | `tasks.py:1881` `_Path(storage.abs_path(export_relative_dir(...)))` | như trên |
| Đọc clean (API) | `routes.py:362` `FileResponse(storage.abs_path(...))` | |
| Đọc preview (API) | `routes.py:507` | |
| Tải file xuất (API) | `routes.py:931` | |
| Vùng an toàn E14 | `tasks.py:494,1268` `SafeAreaService(settings.storage_local_root, …)` | **nhận thẳng root, không qua lớp** |

⇒ **Không có chỗ nào ghi thẳng `/app/storage` bằng hằng số** — tất cả đều đi qua
`settings.storage_local_root`. Đó là tin tốt: **đã có một nguồn sự thật duy nhất** cho root.

Nhưng nhiều nơi dùng `abs_path()` rồi tự ghi bằng `Path`, nên lớp trừu tượng **không kiểm soát**
được lượt ghi — không có ghi nguyên tử, không có cập nhật trạng thái hiện vật sau khi ghi.

### Vì sao là `/app/storage` chứ không phải `/data/storage`

- `config.py:22` mặc định `storage_local_root = "/data/storage"`.
- Local (docker compose) đặt volume `storage_data:/data/storage` ⇒ đúng mặc định, **và bền**.
- Hosted: biến `STORAGE_LOCAL_ROOT` **có mặt** trong danh sách biến của `translation-api`
  (giá trị không đọc được qua MCP), và log worker chứng minh đường thật:
  `preview typeset -> /app/storage/previews/…`

⇒ Trên host, biến môi trường **đã ghi đè** mặc định thành `/app/storage`. Mặc định `/data/storage`
**không bị dùng sai** — nó chỉ không phải giá trị hiệu lực trên host. **Không có** cảnh
"người ghi ở A, người đọc ở B": cả hai cùng đọc một biến.

⇒ Vấn đề **không phải** lệch đường dẫn, mà là **`/app/storage` trên host không được gắn volume bền**.

### Khe hở an toàn trong lớp hiện tại (§B1)

```python
def _abs(self, rel: str) -> Path:
    return self.root / rel        # KHÔNG kiểm gì
```

- `root / "../../etc/passwd"` → thoát khỏi root.
- `root / "/etc/passwd"` → **đường tuyệt đối NUỐT luôn root**, trả về `/etc/passwd`.
- Ghi **không nguyên tử**: `target.write_bytes(data)` — không temp + rename.
- Không có `stat()`.

**Hiện chưa khai thác được**: mọi lời gọi đều truyền giá trị lấy từ CSDL, không có đường nào cho
chuỗi của client đi tới. Nhưng đây vẫn là khe hở thật, và §B1 yêu cầu đóng lại.

---

## §5.2 — Năng lực volume của VibeHost

| Câu hỏi | Trả lời |
|---|---|
| MCP có công cụ tạo/gắn volume | **KHÔNG** |
| Phạm vi khoá | `read`, `deploy`, `runtime:write`, `env:write` — **không có** quyền nào về lưu trữ |
| Nền tảng có khái niệm vùng dữ liệu riêng | **CÓ** — `whoami` trả `storageBreakdownBytes` gồm mục **`appdata`** |
| Project này đang dùng bao nhiêu `appdata` | **0 byte** |
| Gói dịch vụ | Vibe Host Pro · đang dùng 4 dịch vụ · 1,77 GB lưu trữ |

⇒ Nền tảng **có** phân loại `appdata` tách khỏi `images`/`containers`/`databases`, tức là khái
niệm lưu trữ ứng dụng bền **tồn tại**. Nhưng **tôi không có công cụ lẫn quyền để cấp phát nó.**

**Đây là cổng chặn của Step 2.** Không thể tự phân giải tên volume / dung lượng / chế độ gắn.

### Đề xuất dung lượng — theo số đo thật, không phỏng đoán

Đo trên **41 trang Pepper&Carrot thật** (1600px) trong kho local:

```
ảnh gốc  : 41 tệp · trung bình 3.380 KB
ảnh clean: 40 tệp · trung bình 3.343 KB
preview  : 39 tệp · trung bình 3.353 KB
tổng     : 486 MB cho ~41 trang  ->  ~11,9 MB/trang (đã gồm mọi thứ)

mỗi trang ≈ gốc + clean + preview          ≈  9,8 MB
       (+ đóng góp của file xuất ≈ preview) ≈ 13,1 MB
pilot     = 13,1 MB × 20 trang              ≈ 262 MB
hệ số an toàn ×3 (chạy lại, nhiều lần xuất) ≈ 786 MB
```

⇒ **Đề xuất: 1 GB.**

⚠️ Ảnh smoke tự vẽ của tôi chỉ ~256 KB cho cả 3 hiện vật — **nhỏ hơn ~40 lần** trang thật vì nó
là hình phẳng. Nếu tính theo ảnh đó sẽ ra ~21 MB và **thiếu nghiêm trọng**. Con số 1 GB lấy từ
trang thật.

---

## §5.3 — Đếm orphan trên host (chỉ đọc, không sửa gì)

| Trang | `status` | `clean_image_path` trong CSDL | `clean-image` | `preview` | Kết luận |
|---|---|---|---|---|---|
| smoke P3a (31/08) | `typeset_done` | **có** | 404 | 404 | ⛔ **ORPHAN THẬT** |
| chapter cũ (28/08) | `ocr_done` | **null** | 404 | 404 | ✅ **404 là ĐÚNG** |

### ⚠️ Đính chính một nhận định của chính tôi

Báo cáo P3a của tôi viết rằng chapter 28/08 *"cũng vậy: bản ghi còn, ảnh đã mất từ lâu"*, và spec
P3b đã chép lại thành *"already orphaned in the same way… a recurring deploy-time failure"*.

**Đo lại cho thấy nhận định đó sai.** Trang 28/08 có `clean_image_path: null` — nó **chưa từng**
có ảnh clean để mà mất. 404 ở đó là **hành vi đúng**, không phải orphan. Ảnh **gốc** của nó thì
không kiểm được vì **API không có route phục vụ ảnh gốc**.

⇒ Hiện chỉ có **MỘT** orphan được chứng minh, không phải hai. Cơ chế gây orphan thì vẫn chắc
chắn (lớp ghi container bị xoá mỗi lần deploy — P3a đã đo trực tiếp), nhưng **bằng chứng "lặp
lại nhiều lần" thì không có**. Không được để nhận định sai này lan tiếp.

### Giới hạn của phép đếm

`GET /api/v1/projects` trả **405** — không có endpoint liệt kê. Tôi **không đếm được** toàn bộ
orphan trên host, chỉ kiểm được 2 trang đã biết ID. Đếm đủ thì cần chạy lệnh đối soát ở phía
máy chủ (đúng là việc §B2 `reconcile_legacy` sinh ra để làm).

---

## §5.4 — Audit readiness / API / UI

### Tái hiện lỗi báo sai nguyên nhân

```
GET /pages/{smoke}/clean-image
  -> {"detail":"Đường dẫn ảnh clean có trong DB nhưng file không còn: …_clean.png"}   ĐÚNG

GET /pages/{smoke}/typeset-preview
  -> {"detail":"Page chưa có ảnh preview — bước canh chữ (typeset) chưa chạy xong"}   SAI
     (trang đang là typeset_done, typeset ĐÃ chạy xong — file mới là thứ biến mất)
```

Đồng thời `clean-image` **rò đường dẫn tương đối** trong thông báo lỗi — §B4 cấm lộ đường dẫn.

### ⚠️ Sửa một giả định của spec: M8 xuất KHÔNG cần preview

Spec §7.5 đoán rằng xuất có thể phụ thuộc preview. Đọc mã thật:

```python
# backend/app/services/export/chapter.py:44
canvas = self.renderer.draw(trang.clean_image_abs, trang.regions)
```

⇒ M8 **dựng lại từ ảnh clean + `TypesetResult`**, hoàn toàn **không đọc file preview**.

**Hiện vật bắt buộc để xuất = ảnh clean** (+ dữ liệu `TypesetResult` trong CSDL). Preview chỉ
phục vụ xem trên màn hình. Điều này thu hẹp đáng kể phạm vi cổng chặn xuất ở §B4/D3.

### Có tái dùng được giao diện không

Có. E11 có `dienGiaiTrangThai` tập trung + `StatusBadge` (đã thêm prop `dienGiai` ở E15), khối
cảnh báo xuất đã có **5 khối tách biệt** (tràn khung / E12 / E13 / E14 / E15). Thêm khối toàn vẹn
hiện vật là khối thứ sáu, **không cần dựng bảng điều khiển mới**.

---

## §5.5 — Audit triển khai / rollback

| | |
|---|---|
| API hiện tại | `translation-api` **v22** (mã `45c0af2`) |
| Web hiện tại | `translation-web` **v13** (mã `45c0af2`) |
| Rollback | api → v21/v20 · web → v12 |
| Cơ chế | redeploy thủ công; MCP **từ chối** khi không có thay đổi mã (`NO_CHANGE`), nút trên giao diện thì **không kiểm** |
| Gắn volume cần deploy web không | **Không** — web chỉ phục vụ tệp tĩnh, không đụng `/app/storage` |
| Thứ tự an toàn | **gắn volume trước** → deploy mã P3b sau → smoke kiểm chứng |

Lý do thứ tự: nếu deploy mã trước mà chưa có volume, `STORAGE_ROOT` vẫn trỏ vào lớp container —
mã mới sẽ báo "lưu trữ bền" trong khi thực tế vẫn tạm, tức là đẻ thêm một lời nói dối mới.

---

## Kết luận Step 1 và cổng chặn Step 2

Audit đã đủ để trả lời mọi câu §5, và **thu hẹp phạm vi mã** đáng kể so với bản spec:

- ✅ Đã có lớp trừu tượng — chỉ cần siết, không dựng mới.
- ✅ Đã có **một** nguồn sự thật cho root (`settings.storage_local_root`) — không có drift A/B.
- ✅ Xuất chỉ cần **ảnh clean**, không cần preview — cổng chặn hẹp hơn spec giả định.
- ✅ Giao diện tái dùng được, không cần bảng điều khiển mới.
- ⚠️ Chỉ có **1** orphan được chứng minh, không phải 2 (đính chính ở §5.3).

**Nhưng Step 2 không tự phân giải được.** Tôi **không có công cụ lẫn quyền** để tạo hay gắn
volume trên VibeHost. Việc này phải do chủ dự án làm trên giao diện.

**Và theo §7 Step 4, mã chỉ được viết SAU khi đường gắn đã được xác nhận** — vì toàn bộ ý nghĩa
của lớp toàn vẹn phụ thuộc vào việc root có thật sự bền hay không.


---

## §5.2 (tiếp) — Xác nhận trên giao diện: KHÔNG có volume

Chủ dự án đã kiểm giao diện VibeHost ngày 2026-08-31. Toàn bộ năng lực lưu trữ có sẵn:

| Mục trong dashboard | Có phục vụ hiện vật ảnh không |
|---|---|
| **Tạo database** — PostgreSQL / MySQL / Redis / MongoDB | ❌ đây là CSDL, không phải volume tệp. Spec §A1 **cấm** nhét nội dung nhị phân vào Postgres |
| **Sao lưu** | ❓ chưa rõ sao lưu cái gì — nếu chỉ sao lưu CSDL thì không cứu được ảnh |
| Tab dịch vụ: Tổng quan / Lịch sử triển khai / Cấu hình / Cài đặt | ❌ không có mục volume/disk/persistent storage |

Cộng với kết quả audit qua MCP:

- Không có công cụ tạo/gắn volume.
- Phạm vi khoá: `read`, `deploy`, `runtime:write`, `env:write` — **không có** quyền lưu trữ.
- `whoami` **có** mục `storageBreakdownBytes.appdata`, nhưng project đang dùng **0 byte** và
  không có đường nào để cấp phát.

⇒ **Không có đường mount `/app/storage` thành bền.** P3b `BLOCKED` tại đây.

---

## Phát hiện quan trọng: mã đã CHỪA SẴN đường cho lưu trữ đối tượng từ M1

```python
# backend/app/core/config.py
storage_backend: Literal["local", "supabase"] = "local"
supabase_url: str = ""
supabase_service_key: str = ""
supabase_bucket: str = "manga-pages"

# backend/app/services/storage.py
def build_storage(settings=None) -> IObjectStorage:
    if settings.storage_backend == "local":
        return LocalObjectStorage(settings.storage_local_root)
    raise SupabaseStorageNotConfigured(
        "STORAGE_BACKEND=supabase: adapter Supabase Storage chưa được implement ở M1 …")
```

`IObjectStorage` (Protocol) chính là **đường nối đã có sẵn**: `save_page_image`, `read`,
`exists`, `delete`, `abs_path`. Thay `LocalObjectStorage` bằng một adapter lưu trữ đối tượng là
thay **đúng một** lớp, không đụng pipeline.

Nghĩa là: khi nền tảng không có volume, **kiến trúc đã có sẵn lối thoát** — chỉ chưa ai dựng.

---

## §10 — Quyết định cổng Pilot: **NO-GO**

| Tiêu chí §9 | |
|---|---|
| 1. Volume bền gắn tại `/app/storage` | ⛔ **HỎNG — nền tảng không có** |
| 2–12 | không đánh giá được: mọi tiêu chí còn lại đều phụ thuộc tiêu chí 1 |

**Không chạy Pilot/UAT.** Không viết mã P3b.

### Việc kế tiếp — đúng MỘT việc, và nó là câu hỏi vận hành, không phải mã

**Hỏi Vibe Host: gói Pro có cấp được volume bền (persistent disk) gắn vào đường tuỳ ý của một
website không?**

Vì sao xếp trên mọi việc khác: câu trả lời **quyết định luôn** mini-spec tiếp theo là cái gì, và
nó rẻ hơn nhiều so với đoán rồi làm nhầm.

- **Nếu CÓ** (kể cả phải nâng gói / mở qua support): gắn **1 GB** vào `/app/storage`, rồi P3b
  chạy tiếp từ Step 3 gần như nguyên vẹn. Chi phí: vài phút cấu hình.
- **Nếu KHÔNG**: mini-spec tiếp theo là **dựng adapter lưu trữ đối tượng sau `IObjectStorage`**
  (S3-compatible hoặc Supabase — cấu hình đã chừa sẵn từ M1). Chi phí lớn hơn nhiều: adapter,
  đổi `abs_path()` sang luồng đọc (vì API đang trả `FileResponse` theo đường tuyệt đối — chỗ này
  phải đổi), khoá/bí mật của nhà cung cấp, kiểm chi phí và độ trễ.

Bằng chứng để hỏi cho trúng: `whoami` **có** mục `appdata` trong `storageBreakdownBytes`, nên nền
tảng **có** khái niệm này — chỉ là chưa thấy đường cấp phát trên giao diện lẫn API.

Câu hỏi phụ nên hỏi cùng lúc: **"Sao lưu" trong dashboard sao lưu những gì** — chỉ CSDL, hay cả
dữ liệu ứng dụng? Nếu nó có chạm tới dữ liệu ứng dụng thì đó là manh mối cho câu hỏi chính.

---

## §9 — Giới hạn còn lại

- **Hiện vật trên host vẫn KHÔNG bền.** Mỗi lần triển khai lại xoá sạch ảnh gốc/clean/preview
  trong khi CSDL giữ nguyên bản ghi ⇒ chapter tiếp tục ở trạng thái nói dối. Chưa sửa.
- **Rủi ro `GEMINI_API_KEYS`** vẫn được chủ dự án chấp nhận, chưa chuyển sang Secret.
- Chưa có auth / RBAC / TLS riêng. **CORS không phải xác thực.**
- `ROLE=all`; `worker.trang_thai` vẫn kẹt `starting`.
- E15 dựng chữ dọc vẫn BLOCKED về cấu trúc.
- Hiện vật đã mất **không thể tự phục hồi** nếu ảnh gốc đã mất.
- **Chưa chạy Pilot/UAT.**

## §11 — Git / Deploy State

```
Mã              : KHÔNG đổi một dòng nào (P3b dừng ở Step 1)
Cấu hình VibeHost: KHÔNG đổi — không tạo volume, không đổi biến, không đổi tài nguyên
Deploy          : KHÔNG
Rollback        : KHÔNG
Commit          : chỉ tài liệu này, LOCAL, KHÔNG push
```

**Sau báo cáo này không có lần push, deploy hay đổi cấu hình nào được thực hiện.**
