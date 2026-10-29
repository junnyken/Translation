# Báo cáo Mini-Spec P3e — Kho hiện vật trong Postgres

**Ngày:** 2026-08-31 · **Trạng thái:** ✅ **XONG — chưa deploy** (chờ một quyết định, xem §Deploy)
**Phụ thuộc:** P3c `HOÀN TẤT` · P3d `XONG` · hosted web v13 / API v22

## Summary

P3c dò ra VibeHost **không cấp được volume bền**. P3d gỡ `abs_path()` để đổi backend chỉ còn là
viết một lớp. P3e **viết lớp đó**: hiện vật (ảnh gốc, ảnh clean, ảnh xem thử, file xuất) nằm
trong bảng `artifact_blob` của chính CSDL ứng dụng.

Đây là mảnh cuối cùng khiến trang "đã canh chữ xong" mà bấm vào thì 404.

## Quyết định: **A — Postgres**, không phải B

Chủ dự án cung cấp con số còn thiếu: **hạn mức gói = 20 GB**. Đó là thứ P3c bị chặn.

| | |
|---|---|
| Đang dùng (`trieunt1@`) | 1,26 GB ⇒ **còn ~18,7 GB** |
| Pilot 20 trang (đo trên 41 trang Pepper&Carrot thật) | ~262 MB · hệ số an toàn ×3 ≈ **786 MB** |
| Sức chứa còn lại quy ra trang | ~18,7 GB ÷ 13,1 MB ≈ **~1.400 trang** |
| Nhà cung cấp mới | **không** |
| Bí mật mới phải giữ | **không** — B thì có, mà `GEMINI_API_KEYS` hiện còn chưa đánh dấu secret |
| Được nền tảng sao lưu | **có** (`backups` là hạng mục riêng trong sổ lưu trữ) |

⇒ Với 20 GB, A dư sức cho pilot **và** cho giai đoạn sau nó. B (S3/Supabase) đổi lấy một nhà cung
cấp mới, một bộ khoá mới và một khoản chi phí chưa đo — để giải một bài toán dung lượng **không
tồn tại** ở quy mô này.

**Nói thẳng: nhét ảnh vào CSDL bình thường là ý tồi.** Ở đây nó không phải lựa chọn kiến trúc đẹp
mà là lựa chọn *khả thi duy nhất còn lại* trên nền tảng này — và nhờ P3d, đổi sang B về sau chỉ
là viết thêm một lớp, không phải làm lại hệ thống. Ngưỡng nên xét đổi: **quá ~10 GB hiện vật**,
hoặc khi cần phục vụ ảnh qua CDN.

---

## Design Choice

### Bảng

```sql
artifact_blob (path TEXT PK, data BYTEA, size_bytes BIGINT, created_at, updated_at)
```

`path` **giữ nguyên chuỗi** mà backend `local` vẫn dùng (`projects/<pid>/pages/<page_id>.png`)
⇒ cột `page.clean_image_path`, `export_job.output_path` **không phải migrate**.

Bốn quyết định nhỏ, mỗi cái chữa một lỗi cụ thể:

| Quyết định | Chữa gì |
|---|---|
| `SET STORAGE EXTERNAL` trên `data` | PNG/ZIP **đã nén sẵn**. Mặc định (`EXTENDED`) Postgres còn thử nén lại: tốn CPU mỗi lượt ghi mà gần như không giảm byte nào |
| `size_bytes` là cột riêng | `stat()` chỉ cần kích thước. Không tách thì mỗi lượt gọi `stat()` kéo cả 3 MB `data` lên chỉ để đếm — mà `stat()` bị gọi ở **mọi** lượt phục vụ HTTP (dựng ETag) |
| Index `text_pattern_ops` | `LIKE 'tiền tố/%'` **không** dùng được index dưới collation mặc định |
| Thoát `_` và `%` khi dựng mẫu LIKE | `_` là ký tự đại diện của LIKE, mà tên thật của hệ thống **có** `_`: `<page_id>_clean.png`. Quên thoát ⇒ `list_prefix("p_1")` nuốt luôn `pX1/` |

### Ghi đè là **upsert một câu lệnh**

Chạy lại xoá chữ hay vẽ lại ảnh xem thử đều ghi đè. Làm bằng "xoá rồi chèn" sẽ có một khoảnh
khắc hiện vật **không tồn tại** — người dùng đang xem đúng lúc đó thì thấy 404. Dùng
`INSERT … ON CONFLICT DO UPDATE`: nguyên tử, không có khe hở.

### Sync/async: một lớp kho, chạy qua threadpool

Kho dùng **session đồng bộ** (worker Celery vốn đồng bộ). Tầng HTTP thì async — gọi thẳng vào đó
sẽ **chặn event loop**, mọi request khác đứng chờ theo. Với backend `local` không ai nhận ra (vài
syscall); với CSDL thì đó là một lượt đi mạng nội bộ mỗi lần.

Chọn: giữ **một** lớp kho đồng bộ, và ở `routes.py` gọi qua `run_in_threadpool`. Phương án kia —
viết cả bản async lẫn sync cho mỗi backend — nhân đôi số đường đọc, tức nhân đôi số chỗ có thể
lệch nhau.

### `open_read()` nạp cả hiện vật vào RAM — có chủ đích

PIL (`Image.open`) đòi luồng **tua được**. Đọc lười theo khối thì phải tự hiện thực `seek`, và
với hiện vật vài MB thì công đó không đáng.

**Cái giá, nói rõ:** mỗi lượt phục vụ giữ trong RAM đúng một hiện vật. Thứ giữ con số đó không
trôi là trần `STORAGE_PG_MAX_ARTIFACT_MB` (mặc định **96 MB**), chặn ngay ở **đường ghi** —
không để phát hiện lúc đọc, vì lúc đó đã muộn và đã tốn chỗ trong CSDL.

---

## Changed Files

| Tệp | Việc |
|---|---|
| `app/core/config.py` | `storage_backend` thêm `"postgres"`; thêm `storage_pg_max_artifact_mb` |
| `app/models/__init__.py` | model `ArtifactBlob` |
| `alembic/versions/0010_p3e_artifact_blob.py` | **Mới** — bảng + `SET STORAGE EXTERNAL` + index `text_pattern_ops` |
| `app/services/storage.py` | `PostgresObjectStorage` + `ArtifactTooLarge`; `build_storage` nhận nhánh `postgres` |
| `app/api/v1/routes.py` | 8 lời gọi kho bọc `run_in_threadpool`; `_phuc_vu_hien_vat` thành `async` |
| `tests/test_storage_unit.py` | fixture `kho` **parametrize 2 backend** + lớp `TestRiengPostgres` |
| `tests/test_storage_durability_integration.py` | **Mới** — 4 test |

## New API / DB / State

- **DB: 1 bảng mới** (`artifact_blob`), migration `0010_p3e`. Không đụng bảng cũ, không đổi cột.
- **API: không đổi gì** — không endpoint mới, không đổi tên field, không đổi mã lỗi.
- **Biến môi trường mới:** `STORAGE_BACKEND=postgres` (mặc định vẫn `local`) ·
  `STORAGE_PG_MAX_ARTIFACT_MB` (mặc định 96).

---

## Tests

```
823 passed, 6 skipped in 293.06s      (nền trước P3e: 801)
```

### Cùng một hợp đồng chạy trên CẢ HAI backend

Fixture `kho` được parametrize `["local", "postgres"]`, nên **19 test hợp đồng chạy hai lượt**.
Đây là điểm mấu chốt: test riêng từng lớp thì "thay backend được" mãi mãi chỉ là lời hứa.

### Test trả lời đúng câu hỏi khiến P3a/P3b bị chặn

`tests/test_storage_durability_integration.py` mô phỏng một lượt triển khai lại bằng cách **xoá
sạch hệ tệp** — đúng điều nền tảng làm với lớp ghi container (P3a đã đo trực tiếp trên host).

Hai test là một **cặp có chủ đích**:

| Test | Khẳng định |
|---|---|
| `..._postgres_song_sot_...` | sau khi xoá sạch đĩa, `GET /clean-image` vẫn **200** và **đúng byte** |
| `..._local_mat_hien_vat_...` | cùng kịch bản, backend `local` trả **404** trong khi DB vẫn khai có ảnh |

Không có test đối chứng thứ hai thì không ai biết test đầu có đang kiểm gì thật hay không. Và
test đối chứng **khẳng định điều sai đang xảy ra trên host**: ngày nào nó bắt đầu đỏ, nghĩa là
nền tảng đã cấp được volume bền và có thể xét quay về `local`.

Thêm: test khẳng định backend `postgres` **không ghi một byte MỚI nào ra đĩa** — nếu có, nghĩa là
còn một đường ghi lén chưa đi qua kho.

### Ca hồi quy đáng nhắc

`test_ten_co_dau_gach_duoi_khong_bi_LIKE_hieu_nham` — lưu `p_1/a_clean.png` và `pX1/b.png`, rồi
đòi `list_prefix("p_1")` chỉ trả cái đầu. Quên thoát `_` thì `delete_prefix` sẽ **xoá bản xuất
của project khác**, im lặng.

---

## Live Verification — ✅ **ĐÃ CHẠY THẬT TRÊN HOST 2026-08-31**

Đặt `STORAGE_BACKEND=postgres` trên `translation-api` (vibehost1 / `trieunt1@`) rồi deploy.
Migration `0010_p3e` chạy lúc khởi động, thành công.

### Kịch bản đo

1. Tải một trang PNG thật (1200×1700, 2 bong bóng) lên host qua API.
2. Pipeline tự chạy hết chuỗi tới `typeset_done` — tức worker **đọc được ảnh gốc từ CSDL** và
   ghi ảnh clean + ảnh xem thử ngược vào đó. Detect ra **2 vùng** (conf 0,774 và 0,573), khớp
   đúng 2 bong bóng đã vẽ — không phải trạng thái nhảy suông.
3. **Redeploy** — đây chính là thao tác xoá sạch lớp ghi container (P3a đã đo).
4. Đọc lại hiện vật.

### Kết quả sau khi đĩa bị xoá

| Đo | Kết quả |
|---|---|
| `GET /pages/{id}/clean-image` | **200** · 14.319 byte · PNG thật **1200×1700** |
| `GET /pages/{id}/typeset-preview` | **200** · PNG thật **1200×1700** |
| `If-None-Match` khớp ETag | **304**, tải về **0 byte** |

### Bằng chứng đối chứng, đắt giá hơn cả phép đo trên

Lượt đối chiếu tự chạy lúc khởi động (03:59:17) quét **toàn bộ** trang trên host và kết luận:
**5 trang cũ mất ảnh clean · trang vừa tải lên thì KHÔNG**. Cùng một lần quét, cùng một máy, cùng
một thời điểm — trang tạo trước P3e mất hiện vật, trang tạo sau P3e thì không.

Đó là đối chứng mà một bộ test không dựng ra được: chính dữ liệu thật của hệ thống phân đôi theo
đúng ranh giới P3e.

⚠️ Bộ test trên máy dev (832 passed) và phép đo trên host là **hai loại bằng chứng khác nhau**;
đoạn này là loại thứ hai.

### Deploy cần đúng 3 bước

1. `git push` (xong ở commit này)
2. Đặt biến trên `translation-api` (VibeHost `vibehost1` / `trieunt1@`):
   `STORAGE_BACKEND=postgres`
3. Redeploy — migration `0010_p3e` tự chạy lúc container khởi động
   (`deploy-start.sh:37 alembic upgrade head`, fail là dừng hẳn, không chạy tiếp với schema cũ)

**Rollback:** đặt lại `STORAGE_BACKEND=local` + redeploy. Bảng `artifact_blob` cứ để nguyên —
nó không làm phiền backend `local`. Không mất gì.

### Một quyết định phải hỏi chủ dự án trước

**Hàng dữ liệu cũ vẫn trỏ tới hiện vật đã mất.** P3e làm hiện vật **từ nay** bền; nó **không**
hồi sinh được ảnh đã mất (ảnh gốc mất rồi thì không dựng lại được — P3b đã ghi).

Nên các trang cũ sẽ **vẫn 404**, và vẫn nói dối theo đúng kiểu cũ. Ba lựa chọn:

| | Làm gì | Đánh đổi |
|---|---|---|
| 1 | Để nguyên | Người dùng vẫn gặp trang "đã xong" mà 404, không phân biệt được cũ/mới |
| 2 | Dọn: trang nào có `clean_image_path` mà kho không có ⇒ đưa `clean_image_path=NULL`, lùi `status` | Trung thực ngay, nhưng **ghi đè dữ liệu**, cần một mini-spec riêng (chính là §B2 `reconcile_legacy` của P3b) |
| 3 | Xoá hẳn chapter cũ rồi nạp lại từ ảnh gốc | Sạch nhất, nhưng chỉ làm được nếu chủ dự án còn ảnh gốc |

Chưa làm cái nào — đây là quyết định về **dữ liệu của người khác**, không phải quyết định kỹ thuật.

---

## Remaining Limits

- ~~Chưa deploy~~ → **đã deploy và đã đo trên host** (xem Live Verification).
- **Hàng dữ liệu cũ vẫn orphan**: đo thật được **5 trang** mất ảnh clean, **0** lần xuất mất file.
  Chủ dự án đã chọn phương án 2 (dọn cho trung thực) ⇒ làm ở **P3f**.
- **Một hiện vật/lượt phục vụ nằm trong RAM** (trần 96 MB). Đủ cho pilot 1–2 người dùng; không
  phải thiết kế cho tải cao.
- **Mất hỗ trợ `Range`** ở 3 endpoint trả tệp (thừa kế từ P3d).
- Chưa đo **độ trễ thật** khi phục vụ ảnh từ CSDL trên host — chỉ có số trên máy dev.
- `GEMINI_API_KEYS` vẫn `isSecret: false` trên host.
- 404 của `clean-image` vẫn lộ path tương đối; `typeset-preview` vẫn báo sai nguyên nhân khi tệp
  biến mất (P3b §B4) — cố ý chưa gộp vào P3e.
- Chưa có auth / RBAC / TLS riêng. `ROLE=all`. E15 chữ dọc vẫn BLOCKED.
- **Chưa chạy Pilot/UAT.**

## Git / Deploy State

```
Mã              : 5 tệp app + 1 migration + 2 tệp test
DB              : +1 bảng (artifact_blob), migration 0010_p3e — ĐÃ áp trên host
Cấu hình VibeHost: STORAGE_BACKEND=postgres — ĐÃ đặt
Deploy          : ĐÃ deploy (da5dc2f), đã đo thật, ĐẠT
Rollback        : đặt lại STORAGE_BACKEND=local + redeploy; bảng artifact_blob để nguyên
```
