# FONTS.md — Bộ font chèn chữ dịch (chuẩn bị cho M6)

> Kết luận ngắn: **3 font mà spec chỉ định đều KHÔNG dùng được cho tiếng Việt.**
> Thay bằng 4 font SIL OFL đã **đo thật đủ 134/134 ký tự có dấu** và render kiểm chứng bằng mắt.

## 1. Vì sao phải đo, không được tin tên font

Tiếng Việt cần **134 ký tự có dấu** ngoài ASCII. Phần lớn nằm ở khối Unicode
**U+1E00–U+1EFF (Latin Extended Additional)** — khối mà đại đa số font comic phương Tây **không có**.
Font thiếu glyph thì M6 sẽ chèn ra **ô vuông (tofu)** chứ không báo lỗi — hỏng âm thầm, đúng loại lỗi
tệ nhất.

Cách đo (script đã thành test canh, xem §5): đọc `cmap` của font bằng `fontTools`, đối chiếu đủ 134 ký tự,
rồi render thật bằng Pillow để chắc ra nét mực.

## 2. Ba font spec chỉ định — kết quả đo

| Font | Kết quả | Chi tiết |
|---|---|---|
| **HL Comic2** | ❌ **38/134** | Tải được từ mirror (`HL Comic2`, v2.0 **BK2**). Đây là font **mã BK HCM2/TCVN3 đời 2004**: chữ Việt bị nhét vào dải `0xA0–0xFF` dưới dạng `§ ¨ © ª ® ¯ ° ´ º`, và **0 mã trong U+1E00–U+1EFF**. Render `"ĐỪNG NGOẢNH LẠI"` ra `"▯▯NG NGO▯NH L▯I"`. Thiếu cả 2 ký tự ASCII. |
| **Anime Ace** | ❌ không dùng được | Blambot ghi rõ *"Limited European Characters"*, **không nhắc tiếng Việt**. Ngoài ra **không còn miễn phí vô điều kiện**: trang sản phẩm bắt chọn license (Non-Profit/Indie hoặc Desktop có phí). |
| **MTO Comic** | ❌ không tìm thấy | Không tra ra font nào tên như vậy trên các kho font lớn. Nhiều khả năng tên trong spec bị nhớ nhầm. |

**Về bản HL Comic Unicode:** bản dùng được thật sự tên là `HL-Comic2unicode` (hậu tố `unicode`/`Uni`),
do hoạ sĩ **Nguyễn Hùng Lân** (tác giả *Dũng Sĩ Hesman*) phát hành miễn phí. Nhưng **nguồn chính chủ đã
chết**: `hunglan.com/share/hlcomicuni.rar` nay trả về trang parked (`/lander`), và `hunglan.netfirms.com`
ghi trong metadata font cũng không còn. Chỉ còn mirror bên thứ ba **không nêu giấy phép** ⇒ không đưa vào repo.
Nếu sau này lấy được bản Unicode chính chủ + rõ giấy phép, thả vào `fonts/HLComic/` là test §5 tự kiểm.

## 3. Bộ font đã chọn (nằm trong `fonts/`)

Tất cả **SIL Open Font License 1.1** — dùng thương mại được, nhúng vào sản phẩm được, kèm `OFL.txt`.

| Font | Vai trong trang truyện | Kiểu | Việt |
|---|---|---|---|
| **Bangers** | **Thoại chính** — in hoa, chất comic cổ điển, đúng vai Anime Ace / Wild Words | 1 nét | 134/134 |
| **Shantell Sans** | Thoại có **chữ thường** + **nhấn mạnh** — có đủ Regular/Bold/Italic/Bold Italic | biến thiên `wght` ×2 file | 134/134 |
| **Mansalva** | Thoại viết tay, tự nhiên, mềm hơn Bangers | 1 nét | 134/134 |
| **Sigmar One** | **Tiếng động (SFX)** — nét dày, hét to | 1 nét | 134/134 |

Xem mặt chữ thật: `fonts/mau-chu.png` (render từ chính 4 font này, không phải ảnh quảng cáo).

**Shantell Sans là font duy nhất** trong nhóm hợp truyện tranh có đủ ma trận đậm/nghiêng và có tiếng Việt —
nên nó gánh vai nhấn mạnh mà Bangers (chỉ 1 nét) không làm được.

## 4. Font đã loại sau khi đo

| Font | Vì sao loại |
|---|---|
| **Comic Neue** | Chỉ **36/134** — Google Fonts **không** phát hành subset `vietnamese` cho font này. Đo thật xác nhận. |
| Luckiest Guy · Chewy · Gochi Hand · Titan One · Boogaloo · Comic-ish khác | Google Fonts **không có subset `vietnamese`** (tra metadata chính thức). |

Trong 1946 family của Google Fonts chỉ có **519 family** hỗ trợ tiếng Việt, và nhóm Handwriting phần lớn là
chữ ký/thư pháp — nên lựa chọn cho truyện tranh tiếng Việt **hẹp hơn nhiều** so với tiếng Anh.

## 5. Test canh (đã có, chạy trong bộ test chính)

`backend/tests/test_fonts_vietnamese.py` — 16 test:

- Mọi `fonts/*/*.ttf` phải phủ **đủ 134** ký tự có dấu + đủ ASCII in được. Thiếu ⇒ **đỏ**, kèm danh sách
  ký tự thiếu.
- Mọi thư mục font phải kèm file license và license phải là **OFL**.
- Render thật bằng Pillow, phải ra nét mực (không phải trang trắng).
- Canh chính danh sách 134 ký tự, để sai danh sách không làm mọi test kia thành vô nghĩa.

⇒ Ai thả nhầm một font kiểu HL Comic2 vào `fonts/` sẽ bị chặn ngay, không đợi tới lúc thấy ô vuông trên ảnh.

## 6. Ghi chú kỹ thuật cho M6

- **Pillow có `raqm`** trong môi trường này (`features.check("raqm") = True`) ⇒ shaping phức tạp hoạt động,
  dấu chồng tiếng Việt (`ế`, `ưở`, `ẫ`) đặt đúng vị trí. Nếu image nào thiếu raqm, dấu sẽ lệch — **phải kiểm
  lại khi đổi base image**.
- **Font biến thiên**: chọn nét bằng `ImageFont.set_variation_by_name(...)`.
  Bẫy: file nghiêng dùng tên **`"Bold Italic"`**, không phải `"Bold"` —
  `ShantellSans-Roman-VF` có `['Light','Regular','Medium','SemiBold','Bold','ExtraBold']`,
  còn `ShantellSans-Italic-VF` có `['Light Italic','Italic',…,'Bold Italic','ExtraBold Italic']`.
- **Bangers không có chữ thường** (mọi ký tự render thành dạng in hoa) — đúng quy ước lettering truyện tranh,
  nhưng nghĩa là **không dùng Bangers để phân biệt hoa/thường**. Cần chữ thường thì dùng Shantell Sans/Mansalva.
- Đo font-metrics phải dùng **`font.getbbox()` / `getlength()` trên chuỗi tiếng Việt thật**, không suy từ
  số ký tự: dấu mũ + dấu thanh chồng lên nhau làm chiều cao dòng khác hẳn tiếng Anh — đây là rủi ro số 1 của M6.
