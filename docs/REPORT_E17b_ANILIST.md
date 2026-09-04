# Báo cáo Mini-Spec E17b — Đối chiếu danh xưng với CSDL nhân vật (AniList)

**Ngày:** 2026-09-04 · **Trạng thái:** ✅ **XONG** (chưa deploy lúc viết)

## Summary

Thêm **tầng 3b** vào E17: lấy danh xưng **của chính chapter** đi tra CSDL nhân vật AniList để biết
**cách viết chính thức** và **tên gốc**.

Nguyên tắc không đổi: **chapter quyết định CẦN GÌ, CSDL chỉ trả lời VIẾT THẾ NÀO.**

## Audit Before Build — đo API thật trước, rồi mới thiết kế

| Đo (2026-09-04) | Kết quả |
|---|---|
| AniList GraphQL | **200** — miễn phí, không cần khoá |
| Jikan (MyAnimeList) | **504** — chập chờn, không dựa vào được |
| One Piece / Chainsaw Man (MANGA) | **500** nhân vật |
| Một chapter thật | **3** danh xưng |
| "Naruto" bản MANGA | **2** nhân vật (bản ANIME: 500) |
| Mô tả nhân vật | chiều cao, gia đình, liên kết — **không một chữ nào về cách xưng hô** |

Ba con số này định hình toàn bộ thiết kế:

1. **Lệch 150 lần** ⇒ đổ danh sách CSDL vào glossary là làm mọi lượt rà soát nhất quán ngập cảnh
   báo vô nghĩa. Nên **không lấy danh sách từ CSDL** — lấy danh sách của chapter đi hỏi CSDL.
2. **Phủ sóng không đều** (cùng "Naruto": manga 2, anime 500) ⇒ "không tìm thấy" là chuyện bình
   thường, phải nói thẳng chứ không im lặng để người dùng tưởng đã đối chiếu xong.
3. **Không có dữ liệu xưng hô** ⇒ tầng 2 (đọc kính ngữ/đại từ **có thật trong bản gốc**) vẫn là
   nguồn duy nhất cho giọng nhân vật. AniList không thay được, và không được giả vờ thay được.

## Design Choice

### Cổng đối chiếu — y hệt tầng 3a

Nhân vật nào CSDL trả về mà **không khớp danh xưng nào của chapter** đều bị **loại thẳng** và đếm
vào `bo_qua`. Con số đó **hiện ra cho người dùng đọc**: nó chính là bằng chứng cho lập luận "vì
sao không đổ cả CSDL vào".

Đo thật: One Piece → khớp 3, **bỏ qua 22**. Naruto → khớp 1, bỏ qua 1.

### Tách phần quyết định khỏi phần gọi mạng

`doi_chieu()` thuần tính toán, không chạm mạng ⇒ **test được đúng/sai mà không phụ thuộc một dịch
vụ bên ngoài có thể sập bất cứ lúc nào**. `hoi_anilist()` lo phần mạng và **không bao giờ ném**.

### "Không tìm thấy" ≠ "AniList đang hỏng"

Ba loại hỏng được phân biệt và nói khác nhau:

```
429            -> "đang giới hạn số lượt hỏi, thử lại sau một phút"   (chờ được)
mạng/timeout   -> "không kết nối được tới AniList"
Media = null   -> "AniList không có bộ truyện nào tên '...'"
```

Gộp chúng lại là nói dối: người dùng sẽ đi sửa sai chỗ.

### Ghép tên: phải tách phần của tên đầy đủ

Chapter viết `Naruto`, CSDL ghi `Naruto Uzumaki`. Không tách thì gần như không bao giờ khớp được
gì. Nhưng chặn phần **quá ngắn** (< 2 ký tự) — tách `D` từ `Monkey D Luffy` rồi khớp mọi chữ `D`
là nhận bừa.

### Giữ NGUYÊN cách chapter viết

Kết quả trả về `danh_xung` đúng như chapter viết, **không** thay bằng dạng của CSDL. Thay là sửa
dữ liệu của người dùng bằng dữ liệu của người khác. CSDL chỉ *thêm thông tin bên cạnh*.

### `urllib` chứ không `httpx`

Theo tiền lệ của `translate/engines.py`. `httpx` hiện chỉ là phụ thuộc **gián tiếp**, không khai
trong `requirements.txt` — dựa vào nó là dựa vào thứ có thể biến mất ở lần nâng phiên bản bất kỳ.

### `User-Agent` là BẮT BUỘC

AniList đứng sau Cloudflare và trả **403** cho UA mặc định của urllib. Đo được: cùng truy vấn,
`curl` 200 / `urllib` 403 — khác biệt duy nhất là dòng UA. Bắt được ngay ở lần chạy thật đầu tiên
**vì phần xử lý lỗi trả về lý do thật thay vì sập**.

### Giao diện: MỘT ô "Tên bộ truyện", HAI nút

Bản đầu tôi thêm ô nhập riêng ⇒ hai ô cùng nhãn trên một màn. Đó là lỗi UX thật (gõ hai lần,
trình đọc màn hình không phân biệt được), và bộ test cũ bắt được ngay bằng
`Found multiple elements with the text of: /Tên bộ truyện/`. Sửa: dùng chung ô, hai nút.

## Changed Files

| Tệp | Việc |
|---|---|
| `app/services/consistency/anilist.py` | **Mới** — `doi_chieu` (thuần) + `hoi_anilist` + `tra_ten_chinh_thuc` |
| `app/schemas/common.py` | `DoiChieuTenRequest` · `TenChinhThucRead` · `DoiChieuTenResponse` |
| `app/api/v1/routes.py` | **Mới** `POST /projects/{id}/term-official-names` |
| `frontend/src/api.js` · `App.jsx` · `GlossaryManager.jsx` · `TermCandidatePanel.jsx` | nối tầng 3b |
| `tests/test_anilist_unit.py` | **Mới** — 14 test |
| `tests/test_e17_integration.py` | +4 test endpoint |
| `frontend/src/components/consistency/anilist-ui.test.jsx` | **Mới** — 6 test |

## Tests

```
backend : exit 0        frontend: 265 passed (nền 259)
```

Nhóm test đáng kể nhất **không** kiểm việc khớp, mà kiểm việc **không khớp bừa và không nói dối**:
`nhân vật ngoài chapter bị loại thẳng` · `tên quá ngắn không được dùng làm mảnh ghép` ·
`không thay danh xưng của chapter bằng dạng CSDL` · `mỗi danh xưng chỉ khớp một lần (tất định)` ·
`ba loại hỏng nói ba câu khác nhau`.

## Remaining Limits

- **Chỉ có MANGA.** Cùng tên có thể phủ sóng khác nhau giữa MANGA và ANIME (Naruto: 2 vs 500).
  Chưa cho người dùng chọn loại — việc kế tiếp rõ ràng nhất.
- **Không giúp gì cho giọng nhân vật.** CSDL không có dữ liệu xưng hô; tầng 2 vẫn là nguồn duy nhất.
- **Phụ thuộc một dịch vụ ngoài miễn phí**: 90 lượt/phút, có thể sập, có thể đổi lược đồ. Hỏng thì
  tính năng này mất — nhưng bảng danh xưng (tầng 1) **không** phụ thuộc nó.
- **Chưa lưu kết quả**: mỗi lần bấm là một lượt hỏi mới. Chưa cần cache vì một chapter hỏi vài lần.
- **Khớp theo chuỗi**, không hiểu ngữ nghĩa: CSDL ghi khác cách chapter viết (viết tắt, phiên âm
  khác) thì không khớp — và im lặng bỏ qua chứ không đoán.
