# Báo cáo Mini-Spec P3d — Bỏ `abs_path()` làm hợp đồng đọc/ghi

**Ngày:** 2026-08-31 · **Trạng thái:** ✅ **XONG (chưa deploy)**
**Phụ thuộc:** P3c `HOÀN TẤT` · P3b/P3a `BLOCKED` · hosted web v13 / API v22

## Summary

P3c kết luận VibeHost **không cấp được volume bền**, nên lối thoát chỉ còn **A — Postgres làm
kho hiện vật** hoặc **B — kho đối tượng ngoài**. P3c cũng chỉ ra: cả A và B gánh **chung đúng
một phần việc nặng**, và phần đó chặn cả hai. P3d làm xong phần chung đó.

Phần chung: **`abs_path()` thôi làm hợp đồng đọc/ghi.** Trước P3d, bên gọi xin một đường dẫn
tuyệt đối rồi tự mở tệp — hoặc tệ hơn, đưa đường dẫn đó cho engine tự ghi vào. Hợp đồng ấy trói
hệ thống vào hệ tệp cục bộ: **không kho đối tượng nào phục vụ được kiểu gọi đó.**

Sau P3d, `abs_path()` **không còn tồn tại**. Viết adapter Postgres/S3 nay là **viết một lớp
duy nhất** hiện thực `IObjectStorage` — không phải sờ lại từng chỗ gọi.

⚠️ **P3d KHÔNG làm hiện vật bền.** Nó dọn đường, không lát đường. Trên host, ảnh vẫn mất sạch
mỗi lần triển khai lại, y như trước. Nói rõ để không ai đọc nhầm tiến độ.

---

## Audit Before Build — phạm vi thật lớn hơn con số P3c ghi

P3c ước lượng **"3 chỗ ghi, 3 chỗ đọc, + `SafeAreaService` nhận thẳng root"**. Đếm lại bằng mã:

| Loại | Đếm | Ở đâu |
|---|---|---|
| Đọc qua `abs_path` | 4 | `routes.py:362,507,931` · `quality/gate.py:127` |
| Ghi qua `abs_path` | 3 | `tasks.py:1178,1180,1881` |
| **Nhận thẳng gốc kho** | 4 | `tasks.py:494,1268,1872` · `resolve_image_path` (`tasks.py:116`) |
| **Đường dẫn tuyệt đối cho engine** (P3c bỏ sót) | 4 | `tasks.py:151,315,712,1563` qua `resolve_image_path` |
| `abs_path` để tính vân tay | 3 | `tasks.py:1154,1256,1800` → `nap_o_dat_chu` |

⇒ **18 chỗ**, không phải 7. Chỗ P3c bỏ sót là `resolve_image_path()` — một hàm **thứ hai** làm
đúng việc của `abs_path()` nhưng mang tên khác, nên không lọt vào phép đếm dựa trên tên.

**Bài học:** đếm theo *tên hàm* thì trượt; phải đếm theo *hành vi* (chỗ nào cần đường dẫn thật).

### Chỗ khó nhất: engine tự chọn nơi ghi

`LaMaInpainter.inpaint(image_path, masks)` **tự đặt tên ảnh clean cạnh ảnh gốc** rồi trả về
đường dẫn tuyệt đối; bên gọi `to_relative()` để quy ngược. Tức là **engine quyết định layout của
kho** — thứ mà không kho đối tượng nào chiều được.

---

## Design Choice — ranh giới vật chất hoá

Sự thật không né được: engine bên thứ ba (comic-text-detector, manga-ocr, PaddleOCR, LaMa, bộ vẽ
M6, bộ xuất M8) **nhận đường dẫn tệp**. Phải có tệp thật ở đâu đó.

Quyết định: **chỗ đó không được là lòng kho.**

```
kho ──fetch_to()──> thư mục tạm ──engine làm việc──> save_file() ──> kho
                         └── luôn được dọn, kể cả khi lỗi
```

Ba phương án đã cân nhắc:

| | Cách | Vì sao không chọn |
|---|---|---|
| 1 | Zero-copy: backend local trả thẳng đường dẫn thật | Đúng cái bẫy cũ. Engine ghi tệp cạnh đó là ghi thẳng vào lòng kho ⇒ backend local vẫn "đặc biệt", và người sau lại dựa vào |
| 2 | Đổi mọi engine sang nhận luồng byte | Không làm được: engine là mã bên thứ ba, và ONNX/OpenCV nhiều chỗ đòi path |
| **3** | **Luôn chép ra thư mục tạm** ✅ | Đồng nhất mọi backend, không có đường tắt để lạm dụng |

**Cái giá:** chép thêm ~3–4 MB mỗi hiện vật mỗi lượt. So với một lượt chạy LaMa/OCR thì không
đáng kể — và đây là cái giá **có chủ đích** để đổi lấy tính đổi-được-backend.

### Path ảnh clean giữ nguyên ⇒ không phải migrate

LaMa vẫn tự đặt tên ảnh clean cạnh ảnh gốc, nhưng nay làm trong thư mục tạm. Path tương đối ghi
vào CSDL suy ra từ ảnh gốc nên **vẫn đúng chuỗi cũ**: `projects/<pid>/pages/<page_id>_clean.png`.
**Không có migration, không đụng dữ liệu cũ.**

### Vân tay E14: nhận kết quả, không nhận đường dẫn

`vung_an_toan_dung_duoc(ban, clean_image_abs)` trước đây tự `stat()` lại tệp cho **mỗi vùng** —
một trang 30 vùng là **30 lượt hỏi kho cho cùng một tệp**. Trên hệ tệp cục bộ thì rẻ; trên kho từ
xa thì đó là 30 lượt gọi mạng. Nay hàm nhận **vân tay đã tính sẵn**; bên gọi tính một lần.

---

## Changed Files

| Tệp | Việc |
|---|---|
| `app/services/storage.py` | **Viết lại.** Bỏ `abs_path`/`to_relative`; thêm `save`/`save_file`/`open_read`/`stat`/`list_prefix`/`delete_prefix`/`fetch_to`/`workspace()`; `chuan_hoa_path()` chặn traversal; ghi nguyên tử |
| `app/api/v1/routes.py` | 3 endpoint tệp → luồng + ETag/304 + Content-Length (`_phuc_vu_hien_vat`) |
| `app/workers/tasks.py` | Bỏ `resolve_image_path`, thêm `anh_cuc_bo()`; 10 chỗ gọi chuyển sang kho |
| `app/services/safearea/service.py` | `SafeAreaService` nhận kho thay vì gốc thư mục; `dau_van_tay_anh` → `van_tay_hien_vat(storage, rel)` |
| `app/services/safearea/apply.py` | `nap_o_dat_chu` nhận vân tay thay vì đường dẫn |
| `app/services/export/chapter.py` | Bộ xuất nhận kho, vẽ ra thư mục được cấp; bỏ `_don_ket_qua_cu` (chuyển về kho) |
| `app/services/quality/gate.py` | Đọc kích thước ảnh qua luồng |
| `tests/test_storage_unit.py` | **Mới** — 22 test |
| `tests/test_export_unit.py` · `tests/test_safe_area_integration.py` | Bám API mới |

---

## New API / DB / State

- **DB: không đổi gì.** Không bảng mới, không cột mới, không migration.
- **API: không endpoint mới, không đổi tên field.** Thay đổi *hành vi* ở 3 endpoint trả tệp:
  thêm `ETag` + trả **304** khi `If-None-Match` khớp.
- ⚠️ **Mất hỗ trợ `Range`.** `FileResponse` của Starlette tự lo tải-tiếp-đoạn-giữa; luồng thì
  không. Ảnh hưởng thật: đứt mạng giữa chừng khi tải gói CBZ lớn thì phải tải lại từ đầu. Chưa
  làm lại vì chưa ai gặp — ghi ra để không ai tưởng là lỗi.

### Đổi tên method đã chốt (CLAUDE.md §6 yêu cầu ghi lý do)

| Cũ | Mới | Lý do |
|---|---|---|
| `IObjectStorage.abs_path()` | *(bỏ hẳn)* | Chính là thứ P3d sinh ra để gỡ |
| `IObjectStorage.to_relative()` | *(bỏ hẳn)* | Chỉ tồn tại để quy ngược đường dẫn tuyệt đối; hết đường dẫn tuyệt đối thì hết việc |
| `dau_van_tay_anh(path)` | `van_tay_hien_vat(storage, rel)` | `Path.stat()` chỉ chạy trên hệ tệp |
| `nap_o_dat_chu(…, clean_image_abs)` | `nap_o_dat_chu(…, van_tay_clean)` | Bỏ N lượt `stat()` thừa (xem Design Choice) |
| `ChapterExporter(storage_root=…)` | `ChapterExporter(storage=…)` | Bộ xuất không được biết kho nằm ở đâu |
| `TrangCanXuat.clean_image_abs` | `.clean_image_rel` | Cùng lý do |
| `export_*() -> (path, da_xoa)` | `-> path` | Việc dọn bản cũ chuyển về kho |

Không có tên nào trong số này xuất hiện ở `docs/API.md` (hợp đồng HTTP) hay
`services/interfaces.py` (hợp đồng engine) — đây là API nội bộ của tầng lưu trữ.

---

## Tests

```
801 passed, 6 skipped in 295.38s      (nền trước P3d: 779 passed)
```

**0 test bị xoá.** +22 từ `tests/test_storage_unit.py`. Chi tiết: `TEST_LOG.md` §P3d.

Hai ca đáng nhắc, đều kiểm thứ **trước P3d không đúng**:

- `test_khong_ghi_duoc_ra_ngoai_goc_that` — dựng tệp thật ngoài kho, gọi `save("../moi-nhu.txt")`,
  khẳng định tệp đó không đổi. **Trước P3d phép ghi này thành công.**
- `test_don_ban_cu_khong_dung_toi_hang_xom` — `exports/p1` là tiền tố **chuỗi** của `exports/p10`;
  một `delete_prefix` viết bằng `startswith` sẽ xoá nhầm bản xuất của project khác.

Lint: trên đúng 9 tệp đã sửa, ruff **100 → 95**. Không thêm nợ.

### Một lỗi thật do refactor, và vì sao test bắt được còn import thì không

`anh_cuc_bo()` ở scope module dùng `get_storage`, nhưng hàm đó khi ấy **chỉ được import cục bộ
trong vài hàm** ⇒ `NameError`. Hệ quả: **mọi job detect thất bại**, kéo đổ 40+ integration test.

`import app.workers.tasks` vẫn **sạch**, và 411 unit test vẫn **xanh** — vì không đường nào trong
số đó chạm tới thân hàm ấy. Chỉ integration test chạm đường chạy thật mới lộ.

---

## Live Verification

⛔ **CHƯA CÓ. Không deploy, không chạy trên host.**

Bằng chứng hiện có **chỉ là** bộ test chạy trên máy phát triển với Postgres thật (801 passed).
Đó **không phải** bằng chứng chạy thật trên VibeHost.

Chưa deploy vì hai lẽ, xếp theo thứ tự quan trọng:

1. **P3d không sửa được thứ đang hỏng.** Hiện vật vẫn không bền. Deploy P3d không làm ai đỡ khổ
   hơn, chỉ đổi mã đang chạy.
2. Deploy là thao tác hướng ra ngoài, và chủ dự án chưa yêu cầu.

Deploy **nên** đi cùng adapter kho bền (mini-spec sau) để một lượt triển khai đổi được thực trạng.

---

## Remaining Limits

- **Hiện vật trên host vẫn KHÔNG bền** — P3d không sửa, và không hứa sửa.
- **Chưa có adapter kho bền nào.** Còn chờ **hạn mức lưu trữ của gói VibeHost** để chọn A hay B
  (`whoami` không trả trường hạn mức, `canUpgrade: false`) — xem P3c §5.
- **Mất hỗ trợ `Range`** ở 3 endpoint trả tệp (xem trên).
- `GEMINI_API_KEYS` vẫn `isSecret: false` trên host — chưa chuyển sang Secret.
- Thông báo 404 của `clean-image` **vẫn lộ path tương đối** (P3b §B4 cấm). Cố ý không sửa trong
  P3d để không trộn hai loại thay đổi vào một mini-spec; vẫn là việc còn nợ.
- `typeset-preview` vẫn báo sai nguyên nhân khi tệp biến mất ("bước canh chữ chưa chạy xong"
  trong khi đã chạy xong) — cũng chưa sửa, cùng lý do.
- Chưa có auth / RBAC / TLS riêng. `ROLE=all`. E15 chữ dọc vẫn BLOCKED.
- **Chưa chạy Pilot/UAT.** Cổng Pilot vẫn **NO-GO**.

## Git / Deploy State

```
Mã              : 9 tệp (7 app + 2 test) + 1 tệp test mới
DB              : KHÔNG đổi — không migration
Cấu hình VibeHost: KHÔNG đổi
Deploy          : KHÔNG
Rollback        : không cần (chưa deploy)
```
