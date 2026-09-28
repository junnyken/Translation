# REPORT E65 — Tách độ phân giải VẼ khỏi độ phân giải ĐỌC

**Ngày:** 2026-09-28 · **Nguồn yêu cầu:** chủ dự án — *"giúp tôi tách độ phân giải ra, hãy làm liền
vấn đề lỗi dịch tiếng Việt, tôi không chấp nhận bị lỗi quá nặng như thế"*

---

## 1. Lỗi đang sửa — đo trên trang thật, không suy luận

Chạy trang gốc của chủ dự án (368×543) qua production ngày 28-09:

| Chữ đúng | Hiện ra trên ảnh |
|---|---|
| RĂNG | `---R` / `ĂNG` / `!` |
| ĐỘT NHIÊN | `ĐỘ T` / `NHI` / `ẾN !` |
| AKI-CHAN | `AKI-CHA` / `N, NGAY` |
| GIẤC CỦA CON GÁI | `GIẤ C` / `CỦA` / `CO N` / `GÁI` |

Đo bằng chính phông (Bangers) và cỡ chữ nhỏ nhất (10px) của hệ thống:

```
12/19 bong bóng KHÔNG chứa nổi MỘT từ tiếng Việt ở cỡ chữ nhỏ nhất
chật nhất : ô còn  8px sau lề · từ "Aliator"   cần 27px
kế đó     : ô còn  9px sau lề · từ "Umi-chan?" cần 38px
```

**Không phải lỗi thuật toán ngắt dòng** — E60 đã vá phần đó. Là hình học: bong bóng tiếng Nhật xếp
chữ **dọc** nên rất hẹp; từ tiếng Việt nằm **ngang** và dài hơn nhiều. Không có cách xếp nào nhét
một từ 27px vào ô 8px, nên bộ căn chữ rơi vào nhánh cắt-giữa-từ — thứ E60 gọi là "lựa chọn cuối".

## 2. Vì sao KHÔNG phóng ảnh ĐẦU VÀO — đã thử, đã đo

Chạy **cả hai** đường trên production rồi so:

| Ảnh vào | Bong bóng không chứa nổi một từ | Chất lượng đọc chữ |
|---|---|---|
| 368×543 (gốc) | **12/19** | tên riêng đúng: `SEYAMA`, `AKI-CHAN` |
| 1200×1770 (phóng trước khi đọc) | 3/14 | **hỏng**: `MUYAMA`, `LAI-CHAN`, "LEHMAN THÔNG MINH?" |

Phóng ảnh vào sửa được hình học nhưng **phá chất lượng đọc**: model OCR được huấn luyện ở độ phân
giải tự nhiên, ảnh nội suy làm nét chữ nhoè theo kiểu nó chưa từng thấy. Bản phóng còn tìm được ít
vùng hơn (14 so với 19) — có chữ bị bỏ sót hẳn.

## 3. Cách của E65

Hai độ phân giải, tách hẳn:

* **ĐỌC** (dò khung · OCR · dịch · xoá chữ) — **giữ nguyên ảnh gốc**. Không đụng gì tới chất lượng đọc.
* **VẼ** (căn chữ · chèn chữ) — phóng ảnh *đã xoá chữ* lên `k` lần, nhân toạ độ khung lên `k`, rồi
  căn chữ trong khung đã to ra.

Cùng cỡ chữ tối thiểu 10px, nhưng khung rộng gấp `k` ⇒ từ vừa.

`k` **đo riêng cho từng trang**: lấy chỗ chật nhất (`từ dài nhất / bề rộng còn lại`) rồi làm tròn
lên theo bước 0,25. Trang vốn đủ rộng nhận đúng **1.0** và **không bị đụng vào** — không phóng,
không nội suy, không phình dung lượng.

### 3.1. Trần: một thiết kế sai đã phải sửa giữa chừng

Bản đầu chặn theo **tỉ lệ** (`k ≤ 4,0`). Bài test bắt được là sai thước đo — thứ cần chặn là **chi
phí**, mà chi phí đi theo **số điểm ảnh của ảnh ra**:

* trang 2000px × 4 = 8000px (≈94 triệu điểm — đủ giết worker);
* và nó cắt nhầm **đúng ca đang sửa**: bong bóng `"Umi-chan?"` cần 4,22×, trần 4,0 bỏ lại đúng một
  bong bóng vỡ — nhìn y như chưa sửa gì.

Nay chặn theo **cạnh dài ảnh ra ≤ 2400px** (cỡ một trang quét tốt), kèm trần tuyệt đối 6,0 cho ca
bệnh hoạn. Trang 543px được phóng tới 4,42×; trang 2000px chỉ 1,2× — mà trang lớn thì vốn không cần.

## 4. Vì sao hệ số phải LƯU xuống CSDL

Bước căn chữ fit chữ vào khung đã nhân `k`, nên `font_size` trong `typeset_result` là pixel **của
ảnh đã phóng**. Bước vẽ phải phóng đúng `k` đó.

Tính lại ở cả hai nơi bằng "cùng một công thức" là đúng bẫy `feedback_tinh_nang_chet_vi_hai_dau_
khong_gap`. Một cột (`page.he_so_ve`) là một nguồn sự thật. `server_default="1.0"` ⇒ mọi trang cũ
giữ nguyên hành vi, không trang nào phải chạy lại.

## 5. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/services/typeset/ti_le_ve.py` | **MỚI** — tính hệ số phóng từ hình học thật |
| `alembic/versions/0024_e65_he_so_ve.py` | **MỚI** — cột `page.he_so_ve` |
| `app/models/__init__.py` | Cột `he_so_ve` |
| `app/workers/tasks.py` | Tính hệ số + căn chữ trong khung đã nhân; lưu; truyền sang hai đường vẽ |
| `app/services/typeset/preview.py` | Phóng ảnh + nhân TOÀN BỘ hình học một lần; hệ số theo từng lượt vẽ |
| `app/services/export/chapter.py` | `TrangCanXuat.he_so_ve` — mỗi trang một hệ số |
| `app/schemas/common.py` | `PageRead.he_so_ve` |
| `frontend/src/components/BboxOverlay.jsx` | `tyLeVe = tyLe × heSoVe`; kéo khung quy về toạ độ gốc; viewBox chia lại hệ số |
| `frontend/src/App.jsx` | Truyền `heSoVe` |
| `tests/test_export_unit.py` | Bộ vẽ giả mang đúng chữ ký mới |

## 6. Tests

`tests/test_e65_tach_do_phan_giai.py` — **18 bài**. Ba bài đáng kể:

* `test_trang_DA_DU_RONG_thi_KHONG_phong_gi_ca` — **đối chứng âm quan trọng nhất**: bản vá "luôn
  phóng cho chắc" sẽ làm xấu mọi trang vốn đang đúng, đắt hơn nhiều so với lỗi đang sửa.
* `test_CAU_dai_hon_khung_KHONG_lam_phong___chi_TU_dai_moi_lam` — câu dài hơn khung là bình thường
  (nó xuống dòng). Viết nhầm thành đo cả câu thì **mọi** trang bị phóng kịch trần.
* `test_KHUNG_PHONG_LEN_thi_het_cat_giua_tu___doi_chung_cap` — cùng câu, cùng bong bóng 12×42 (cỡ
  đo được trên trang thật), chỉ khác có nhân hệ số hay không.

**Đối chứng âm đã chạy**: ghim `k = 1.0` trong bộ vẽ ⇒ **5 bài đỏ**; khôi phục ⇒ xanh.

Bài test cũng bắt được **một lỗi thiết kế của tôi** (§3.1) và **một khẳng định sai của tôi** (đòi hệ
thống thu nhỏ ảnh của người dùng khi trang vốn đã lớn hơn trần).

Bộ backend đầy đủ chạy với `-x`, tới 100%, thoát mã 0. Giao diện 457/457. Migration đã thử **lên và
xuống** trên CSDL thật: cột mất khi downgrade, có lại khi upgrade.

## 7. Remaining Limits

* **Chưa chạy trang thật sau khi vá** tại thời điểm viết báo cáo này — số liệu §1 là của bản TRƯỚC.
* Vùng nào vẫn vượt trần cạnh dài thì **vẫn cắt giữa từ**, kèm cảnh báo tràn. Đỡ được đa số, không
  phải tất cả.
* **Chưa đo lại chất lượng dịch** (`LEHMAN THÔNG MINH?`) — đó là chuyện của bước ĐỌC, E65 không đụng
  tới. E65 chỉ bảo đảm bước đọc vẫn chạy trên ảnh gốc, tức là không tệ đi.
* Ảnh ra **to hơn trước** với trang độ phân giải thấp (368×543 → ~1560×2300). Người dùng tải về tệp
  nặng hơn; đây là đánh đổi có chủ ý, không phải lỗi.
