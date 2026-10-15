# REPORT E69 · E70 · E71 — Ba thuật toán chuyển từ Koharu

**Ngày:** 2026-10-15 · **Nguồn yêu cầu:** chủ dự án, tham khảo https://github.com/koharu-rs/koharu và
lấy những phần làm tốt hơn Translation.

---

## Summary

| Mã | Việc | Trạng thái |
|---|---|---|
| **E69** | Tô phẳng vùng chữ nằm trên nền một màu, không chạy LaMa cho vùng đó | `BUILT` · đo trên 6 trang thật |
| **E70** | Đo màu chữ, màu viền và bề dày viền của chữ GỐC, vẽ chữ dịch đúng như vậy | `BUILT` · chưa chạy trên trang thật |
| **E71** | `llm_context` gửi đoạn có `id`, ép schema JSON, ghép bản dịch theo `id` | `BUILT` · A/B 5+5 lượt gọi Gemini thật |

Chưa deploy, chưa push. Cả ba có cờ để tắt: `INPAINT_FLAT_FILL`, `E70_MAU_CHU_THEO_VUNG`,
`LLM_DICH_JSON` (mặc định bật).

## Audit Before Build

**Giấy phép.** Koharu ở HEAD `ac32b83` là **MIT OR Apache-2.0** (`LICENSE-MIT`, `LICENSE-APACHE`,
`Cargo.toml`). Luật 1 trong `CLAUDE.md` ("không nhúng code GPL (BallonsTranslator, Koharu)") viết lúc
Koharu còn GPL. Lượt này **không chép mã**: Koharu viết bằng Rust, ở đây chỉ viết lại thuật toán bằng
numpy/OpenCV và ghi nguồn trong docstring.

**Đối chiếu từng bước** (khảo sát đọc mã, không chạy Koharu):

| Bước | Koharu | Translation trước lượt này |
|---|---|---|
| Xoá chữ | Bong bóng có nền phẳng thì tô màu trung vị, không gọi model | Mọi vùng đều qua LaMa |
| Màu chữ | Gom 4 cụm màu; viền nhận ra bằng hình (dải màu bao kín màu khác) | Cả trang chữ đen, không viền |
| Dịch | JSON theo `id`, đầu ra bị ép schema | Dòng đánh số, ghép theo vị trí dòng |

Phần dịch của Translation **mạnh hơn** Koharu ở mọi chỗ khác: Koharu không có bảng thuật ngữ, không có
ngữ cảnh xuyên trang, không có cờ "đang đoán". Ở bước dịch chỉ lấy giao thức `id`.

## Design Choice

### E69 — dải viền thay cho đa giác bong bóng

Koharu lấy mẫu nền trong **đa giác bong bóng**, vì model nhận diện của nó trả về mặt nạ bong bóng.
Translation chỉ có **khung chữ nhật đã nới**, nên mẫu nền lấy ở **dải viền bên ngoài khung**.

Bản đầu dùng nguyên công thức độ lệch chuẩn của Koharu trên cả dải. Trên trang thật nó chỉ tô được
**3/38 vùng**. Chẩn đoán cho thấy dải viền của chữ trong bong bóng trắng có **95–99% điểm là nền**,
phần còn lại là nét viền bong bóng lọt vào dải. Mấy điểm mực đó đẩy độ lệch lên 18–24 và vùng bị loại
oan. Koharu không gặp chuyện này vì nó bỏ 3px sát viền đa giác.

Bản sửa có ba bước:
1. Dải viền phải có ≥95% điểm gần màu nền.
2. Độ phẳng (đúng công thức Koharu) chỉ đo trên các điểm gần nền đó.
3. **Chốt bù:** mép trong 2px của khung phải ≥95% là nền. Nét vẽ cắt vào khung thì không tô, vì tô sẽ
   xoá mất nét đó.

Kết quả lên **8/38**. Vùng nào không chắc chắn vẫn chạy LaMa như cũ.

### E70 — chuyển gần nguyên văn, khác ở một chỗ

Các hằng số và thứ tự quyết định giữ đúng Koharu. **Khác một chỗ:** Koharu quy màu về đen hoặc trắng
chỉ theo độ sáng, nên chữ **vàng tươi** (250,220,40) bị quy thành trắng. Ca thử E70 tái hiện được đúng
lỗi này. Ở đây chỉ quy khi màu gần xám (chênh kênh ≤48).

Màu được đo **ở bước căn chữ**, trên ảnh gốc, và lưu cạnh kết quả căn chữ. Lý do: bề dày viền làm
khối chữ to ra nên phải được tính vào phép đo cỡ chữ, hai thứ phải sống chết cùng nhau. Bề dày lưu theo
px ảnh gốc; bộ vẽ nhân hệ số E65 ở cùng chỗ nhân hình học.

### E71 — giao thức theo `id`, giữ nguyên luật nội dung

Ép `responseSchema` vì chính dự án đã có số đo ở E46: xin JSON bằng lời đúng 24/30 lần, ép schema đúng
45/45. Cờ "đang đoán" chuyển từ dấu `[?]` gõ trong chữ sang trường `doan`, nên cờ không thể lọt vào bong
bóng. `[?]` lỡ lọt vào `text` vẫn được bóc và tính là đoán. JSON hỏng thì ném `TranslationFailed` để
đường lùi `google_fast` có sẵn bắt lấy. Chế độ dòng đánh số **giữ nguyên từng ký tự**.

## Changed Files

- `backend/app/services/inpaint/to_phang.py` (mới), `inpaint/lama.py`
- `backend/app/services/typeset/mau_chu.py` (mới), `typeset/preview.py`
- `backend/app/services/translate/engines.py`
- `backend/app/workers/tasks.py`: đo màu ở căn chữ; truyền màu cho ảnh xem thử, file xuất và sửa tay;
  `json_mode`
- `backend/app/core/config.py`: ba cờ
- `backend/app/models/__init__.py`, `backend/alembic/versions/0025_e70_mau_chu.py`
- Test: `test_inpaint_to_phang_unit.py`, `test_e70_mau_chu.py`, `test_e71_dich_json.py` (mới);
  `test_inpaint_lama_unit.py` và `test_inpaint_real_model.py` đặt `flat_fill=False`, vì chúng kiểm đường
  chạy model trên ảnh nền phẳng nhân tạo

## New API / DB / State

- `typeset_result` có thêm `text_color`, `stroke_color` (`#rrggbb`) và `stroke_width` (px ảnh gốc).
  Cả ba cho phép NULL và **không có giá trị mặc định**: NULL nghĩa là chưa đo, khi đó bộ vẽ dùng màu cấu
  hình như trước E70. Dòng cũ không bị điền giá trị giả.
- API không đổi. Ba cột mới **chưa** được trả ra ở `GET /pages/{id}/typeset`.

## Tests

- `test_inpaint_to_phang_unit.py`: 13 test. **Đối chứng âm:**
  - nâng ngưỡng để không vùng nào được tô ⇒ 3 đỏ
  - bỏ nét viền khỏi ca "chạm viền" ⇒ đúng ca đó đỏ
  - gỡ chốt mép trong ⇒ đúng ca "nét cắt ngang mép" đỏ
- `test_e70_mau_chu.py`: 13 test.
  - Đo trên chữ vẽ bằng font Bangers thật, có cả ca nhiễu JPEG q60.
  - Bộ vẽ có ca hệ số E65.
  - Chạy trọn bước căn chữ trên DB thật: ghi cột, ảnh xem thử có điểm vàng, sửa tay giữ màu, tắt cờ thì
    NULL.
  - **Đối chứng âm:** bộ vẽ bỏ qua màu ⇒ 2 đỏ; quên nhân viền theo hệ số ⇒ đúng ca đó đỏ.
- `test_e71_dich_json.py`: 22 test. **Đối chứng âm:** không gửi schema ⇒ 1 đỏ; ghép theo vị trí thay vì
  `id` ⇒ 3 đỏ.
- Các bộ có sẵn của xoá chữ, căn chữ, xuất file, migration và dịch: xanh.

## Live Verification

### E69 — 6 trang thật, CTD thật, LaMa thật (CPU)

| Trang | Số vùng | Tô phẳng |
|---|---|---|
| E11P01 | 7 | 2 |
| E12P03 | 5 | 1 |
| E13P02 | 10 | 3 |
| E14P01 | 5 | 0 |
| pc_E01P02 (1600px) | 4 | 0 |
| ja_E12P01 (tiếng Nhật) | 7 | 2 |
| **Tổng** | **38** | **8 (21%)** |

**Xem bằng mắt cả 8 ảnh so sánh** (gốc | LaMa | tô phẳng):
- 8/8 sạch.
- 4/8 **sạch hơn LaMa**: LaMa để lại bóng mờ, vệt bẩn hoặc vệt xám ở "That's true!", "Thanks!",
  `そうですね` và `私はコモナの市場に`.
- Nét viền và đuôi bong bóng sát khung còn nguyên.

**Thời gian: CHƯA kết luận được.** Máy đang bị chia tải (cùng bước nhận diện đo lúc 39s, lúc 97s), mỗi
trang chỉ bỏ được 0–3 vùng khỏi LaMa, và lượt "cũ" của trang đầu còn gánh thời gian nạp model. Không ghi
con số tăng tốc nào.

Bộ ảnh thử là Pepper&Carrot (truyện màu) và một trang tiếng Nhật. Truyện đen trắng có bong bóng trắng
lớn nhiều khả năng được tô nhiều hơn, nhưng **chưa đo**.

### E71 — A/B 5+5 lượt, Gemini thật (`gemini-3.1-flash-lite`)

Bộ thử gồm 7 câu tiếng Nhật: có câu OCR đọc sai từ E66 (`あの暁山です`), câu hai dòng, câu tiếng
động và một câu rác.

| | Câu trống | Sót chữ Nhật | Gắn cờ đoán |
|---|---|---|---|
| Dòng đánh số | 0/35 | 0/35 | câu rác, 5/5 |
| JSON | 0/35 | 0/35 | câu rác, 5/5 |

**Trên bộ này JSON không cho chất lượng tốt hơn**, vì cách cũ chưa hỏng. Giá trị của E71 là chống hỏng
giao thức (E30, E46), thứ bộ thử này không gây ra được.

Lượt JSON đầu tiên **thụt lùi**: bỏ dấu chấm cuối câu và viết thường chữ đầu. Đã thêm một luật "mỗi
`text` là một câu thoại hoàn chỉnh"; đo lại thì 5/5 lượt có dấu câu kết thúc và viết hoa.

Cả hai chế độ đều **không** gắn cờ cho `あの暁山です` → "Đó là Akiyama". Đây là giới hạn cũ của E66,
không phải do E71.

### E70 — chưa chạy trên trang thật

Đã kiểm qua test DB thật với ảnh dựng bằng font thật, nhưng chưa có lượt chạy trên trang truyện có chữ
màu hoặc chữ viền.

## Remaining Limits

1. **E70 cần một lượt chạy thật** trên trang có chữ trắng viền đen hoặc chữ màu, xem bằng mắt.
2. **E69 chưa đo trên manga đen trắng.** Chưa có thời gian đo được trên máy rảnh.
3. **Hai lệch có sẵn từ trước, phát hiện khi rà, CHƯA sửa** (ngoài phạm vi lượt này):
   - Đường xuất file (`_thu_thap_trang`) **không truyền góc nghiêng E16**, trong khi ảnh xem thử có truyền.
     Chữ nghiêng có thể hiện đúng khi xem thử nhưng nằm ngang trong file tải về.
   - Sửa tay một vùng (`_run_refit`) căn theo khung **gốc**, không nhân hệ số E65 và không dùng ô an toàn
     E14, trong khi bộ vẽ có phóng ảnh. Nghi là cỡ chữ ghim bị lệch. **Chưa xác minh.**
4. Ba cột màu chưa được trả qua API, nên màn sửa tay chưa hiện và chưa cho đổi màu.
