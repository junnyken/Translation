# REPORT A1 — Nới khung ra chỗ trống khi không dựng được hình bong bóng

*2026-09-04 · sửa sau khi người dùng chạy một trang manga tiếng Nhật thật*

## Summary

Người dùng chạy chapter `teer44` (1 trang manga tiếng Nhật, chữ dọc). Pipeline **không hỏng chỗ
nào** — nhưng kết quả không dùng được: chữ Việt bị nhét vào những cột dọc hẹp, mỗi dòng 2–3 ký
tự, và 3/8 vùng tràn khung tới mức chữ bị **cắt cụt** ("NÓ SI / ỰC R / PHẢI / HÔNG").

Log worker chỉ thẳng nguyên nhân:

```
vùng an toàn (inpaint): {'tong': 8, 'shape_derived': 0, 'fallback_rectangle': 4, 'needs_review': 4}
hướng chữ (inpaint):    {'tong': 8, 'unknown': 8}
typeset job:            8 vùng (vừa 5, tràn 3, chưa có chữ 0, thiếu glyph 0)
```

**0/8 vùng dựng được hình bong bóng.** E14 tách bong bóng bằng ngưỡng **sáng** — cách đó hoạt
động trên truyện màu (bong bóng trắng nổi trên nền vẽ có màu), nhưng chết trên **manga đen
trắng**: bong bóng trắng nằm trên trang cũng trắng, không có ranh giới sáng/tối nào để tách. Lý
do ghi trong bản ghi là `shape_candidate_touches_roi_boundary` / `shape_candidate_fills_roi` —
vùng sáng loang ra hết cả ROI vì cả trang đều sáng.

Rơi về khung dự phòng thì khung đó **chính là bbox chữ gốc thụt vào** — mà với manga chữ dọc,
bbox đó là **cột chữ Nhật**: cao và rất hẹp.

## Design Choice

### Không đi tìm bong bóng nữa — nới khung tới khi chạm nét mực

Viền bong bóng **là nét mực**. Nên không cần tách được bong bóng khỏi nền: cứ nới khung chữ ra
bốn phía chừng nào dải mới còn sạch, phép nới sẽ tự dừng đúng ở mép trong của viền.

Cách này còn đúng cho vùng chữ **ngoài** bong bóng (tiếng động, chữ trên nền vẽ): nét vẽ chặn
ngay, khung gần như không nới được — và đó là kết quả đúng, không phải thất bại.

### Vẫn là "khung dự phòng", không tự phong là đã tìm được bong bóng

`source` giữ nguyên `fallback_rectangle`, `status` giữ nguyên, mọi lý do vì sao E14 bó tay được
**giữ lại**, chỉ thêm mã `fallback_grown_to_free_space`. Nới được một cái khung rộng hơn **không**
có nghĩa là đã nhận ra hình bong bóng — nhận vơ mức chắc chắn mình không có là đúng thứ E14 sinh
ra để chống.

### Ba giới hạn cố ý

1. **Chỉ nới trong ROI** của E14 — để một bong bóng chạm mép panel không nuốt luôn rãnh trắng
   giữa các panel rồi tràn sang panel bên cạnh.
2. **Chặn theo bội của cạnh DÀI** của bbox (mặc định 1,5 lần, trần 400px).
3. **Dải mới phải sạch HOÀN TOÀN**. Không có ngưỡng "gần sạch": một nét mực lọt vào là chữ đè
   lên hình vẽ.

### Hai cái bẫy đo được, không phải nghĩ ra

**Bẫy 1 — nới một thứ tự thì ô bị khoá ở dạng cao-hẹp.** Nới luân phiên bốn phía trong bong bóng
tròn: vừa nới cao xong thì không nới ngang được nữa. Đo: 44×280 chỉ ra 166×352. Đã lặp lại đúng
bài học E14 từng trả giá (`layout.py` · `_CACH_NO`): thử **ba thứ tự** cố định rồi lấy ô lớn nhất.

**Bẫy 2 — chặn theo cạnh tương ứng thì khung không bao giờ đủ rộng.** Cột chữ dọc rộng 44px:
chặn ngang theo chính bề rộng đó (44 × 1,5 = 66px mỗi bên) ⇒ khung **không bao giờ** vượt 176px,
trong khi lòng bong bóng rộng hơn gấp đôi. Bong bóng thì gần vuông, còn khung chữ bên trong nó
có thể rất dẹt — nên **cạnh dài** mới là thước đo "bong bóng này to cỡ nào".

Đo trên trang dựng thử, cùng một bbox 44×280 trong bong bóng ellipse 440×400:

| | Ô đặt chữ | Cỡ chữ | Ngắt dòng |
|---|---|---|---|
| **Trước** | 36×230 | **10** (cỡ nhỏ nhất) | 15 dòng, mỗi dòng 1–2 từ |
| Nới, chặn cạnh ngắn | 170×350 | 27 | 7 dòng |
| **Sau** (chặn cạnh dài) | **232×320** | **28** (cỡ lớn nhất) | 5 dòng đọc được |

## Changed Files

| File | Đổi gì |
|---|---|
| `app/services/safearea/grow.py` *(mới)* | Thuật toán nới khung: ba thứ tự, giới hạn, mặt nạ chỗ trống |
| `app/services/safearea/extractor.py` | `khung_du_phong_co_noi()`; 5 đường lùi về dự phòng sau khi có mặt nạ đều đi qua nó |
| `app/services/safearea/decision.py` | Mã lý do `fallback_grown_to_free_space` |
| `app/services/safearea/config.py`, `app/core/config.py` | 5 tham số `E14_GROW_*` (có công tắc tắt hẳn) |
| `frontend/src/lib/status-presentation.js` | Câu tiếng Việt cho mã lý do mới |
| `frontend/src/components/RegionPanel.jsx`, `App.jsx` | **Nút "Tính lại bố cục cả trang"** |

### Vì sao phải thêm một cái nút

Bố cục của một trang chỉ được tính **một lần, lúc xoá chữ**. `POST /pages/{id}/retry-safe-area`
đã có từ E14 nhưng **không nút nào trong giao diện gọi nó** — hàm `tinhLaiVungAnToan` nằm trong
`api.js` mà không ai dùng. Nghĩa là bản sửa hình học này sẽ chỉ ăn vào trang **tải lên mới**,
còn chapter đang làm dở thì không có đường nào chạm tới, ngoài xoá đi làm lại từ đầu.

## Tests

`backend/tests/test_safearea_noi_khung.py` — 19 test:

| Nhóm | Khẳng định |
|---|---|
| Hình học thuần | Cột hẹp nới ra hơn 200px · dừng đúng ở nét mực · ô kết quả nằm trọn trong chỗ trống · **tất định** (chạy hai lần ra một kết quả) |
| Không lấn sân | Ô ban đầu đã dính mực ⇒ trả `None` chứ không nới từ chỗ sai · vùng trên nền vẽ nới được rất ít |
| Giới hạn | Chặn theo cạnh dài · cắt theo ROI · trần pixel · **và một test canh riêng cái bẫy cạnh ngắn** |
| Quyết định | Vẫn là `fallback_rectangle`, **không** tự phong `shape_candidate_found` · giữ nguyên lý do vì sao E14 bó tay · chừa lề nên không dính viền · công tắc tắt thì hành vi y như cũ · nới được ít quá thì không đổi gì |

**Một test CŨ phải sửa** — và nó đỏ đúng chỗ đáng suy nghĩ:
`test_chu_khong_bao_gio_ve_ra_ngoai_khung` bôi trắng mọi bbox rồi đòi hai ảnh giống hệt nhau.
A1 cố ý vẽ chữ **ra ngoài bbox** (vào lòng bong bóng), nên nó đỏ. Bất biến cần canh không mất đi
mà đổi chỗ: vùng được phép vẽ nay là **bbox hợp với ô đặt chữ**, và chữ vẫn tuyệt đối không được
rơi ra chỗ có hình vẽ. Đã sửa test theo đúng nghĩa đó, không phải nới lỏng cho xanh.

## Live Verification

*(chưa điền — cần chạy lại trên bản chạy thật)*

## Remaining Limits

1. **Không sửa được chuyện hướng chữ.** 8/8 vùng vẫn `unknown`; chữ Việt vẫn xếp ngang trong
   bong bóng vốn dành cho chữ dọc. A1 chỉ cho nó **đủ chỗ**, không dựng chữ dọc (E15 vẫn BLOCKED).
2. **Bong bóng có đuôi nhọn hoặc hình sao** thì khung chữ nhật nới được ít hơn hẳn hình thật.
3. **Bong bóng viền đứt nét** (hiệu ứng nghĩ thầm) có thể để phép nới lọt qua khe. Trần theo
   cạnh dài và ROI chặn hậu quả, nhưng chưa đo trên trang thật nào có kiểu viền đó.
4. **Trang đã chạy trước bản này giữ nguyên bố cục cũ** cho tới khi bấm "Tính lại bố cục cả
   trang" — cố ý: tự tính lại hàng loạt sẽ đổi bố cục của những trang người dùng đã sửa tay xong.
