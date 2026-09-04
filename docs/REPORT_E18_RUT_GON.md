# REPORT E18 — Dịch lại ngắn hơn cho vừa bong bóng

*2026-09-05 · làm sau khi A1 nới khung xong mà vẫn còn 2/8 vùng tràn*

## Summary

Sau A1 (nới khung ra chỗ trống), trang manga thật của người dùng cải thiện thật nhưng chưa hết:

| | Trước A1 | Sau A1 |
|---|---|---|
| Căn chữ | vừa 5 · **tràn 3** | vừa 6 · **tràn 2** |
| Bố cục | dự phòng 4 · cần xem 4 | dự phòng 5 · cần xem 3 |

Hai vùng còn lại tràn vì lý do **khác hẳn**: khung đã trùm gần hết bong bóng rồi, mà bản dịch
vẫn dài hơn chỗ chứa. Vùng 6 của trang đó: *"TÔI NGHE NÓI RẰNG CÔ GÁI TÔI TỪNG THÍCH KAZUDAKE
ĐÃ KỂ VỀ NHỮNG CHUYẾN PHIÊU LƯU THỜI THƠ ẤU CỦA CÔ ẤY!?"* — khoảng **105 ký tự** nhét vào một
bong bóng vẽ vừa chừng **30 ký tự tiếng Nhật**.

Tới đó thì **không có cách xếp chữ nào cứu được**: chữ dài hơn chỗ chứa là chuyện vật lý. Chỗ
duy nhất còn sửa được là **chính bản dịch**.

Vấn đề gốc: bước dịch **không hề biết bong bóng to bao nhiêu**. Nó dịch xong rồi mới có người
đi tìm chỗ nhét.

## Design Choice

### Đo sức chứa bằng chính font sẽ vẽ

`app/services/typeset/suc_chua.py` đo bề rộng trung bình thật của một mẫu chữ Việt **có dấu**
qua đúng `FontResolver` của M6, rồi nhân số dòng. Không có bảng bề rộng đoán sẵn, không có hằng
số ma thuật — đổi font là con số tự đổi theo.

**Cỡ chữ mục tiêu** lấy theo `E18_CO_CHU_MUC_TIEU_TY_LE` — vị trí giữa dải min–max. Không lấy
cỡ nhỏ nhất: "vừa khung ở cỡ 10" là vừa một thứ không ai đọc nổi. Không lấy cỡ lớn nhất: ép bản
dịch ngắn tới mức mất nghĩa.

Mặc định **0,35** (⇒ cỡ 20 trên dải thật 10–40 của bản chạy). Con số này ban đầu để 0,5 và phải
hạ xuống sau lượt kiểm chứng đầu tiên — xem *Live Verification*, đó là chỗ đắt giá nhất của cả
mini-spec này.

### Sức chứa là ƯỚC LƯỢNG, và nói thẳng ra như vậy

Bề rộng mỗi ký tự khác nhau, chỗ ngắt dòng phụ thuộc dấu cách — không con số nào đúng tuyệt đối.
Nên sau khi dịch lại **vẫn chạy `fit()` thật**, và vẫn tràn thì vẫn báo tràn. Bộ căn chữ của M6
là bên duy nhất có thẩm quyền nói "vừa".

Test `test_uoc_luong_doi_chieu_voi_phep_CAN_CHU_THAT` canh đúng chỗ dễ tự lừa nhất: cắt câu về
đúng sức chứa rồi hỏi `fit()` — phải ra `fit_ok` trên cả 4 cỡ khung.

### Vì sao là một bước RIÊNG, phải bấm tay

Ba lý do, không phải một:

1. **Rút gọn là làm mất chữ.** Máy tự quyết định bỏ bớt lời thoại của người khác là việc không
   ai xin. Phải do người dùng bấm.
2. **Đường `google_fast` không nhận chỉ dẫn độ dài.** Google Translate chỉ dịch, không nghe lời.
   Nhét sức chứa vào bước dịch chỉ ăn ở đường LLM — mà người dùng đang dùng đường miễn phí.
3. **Chỉ tốn token cho vùng thật sự tràn.** Cả trang 8 vùng chỉ hỏi mô hình về 2 vùng.

### Ba ranh giới cứng

- **Không đụng vùng người dùng đã sửa tay** (`edited_by_user`). Đè lên chữ người ta tự gõ là
  việc không ai xin, và bản gốc của họ không lưu ở đâu để lấy lại. Số vùng bị bỏ qua được
  **trả về**, không im lặng.
- **Đưa cả chữ gốc vào prompt.** Không có nó thì model chỉ còn cách cắt cụt câu tiếng Việt —
  mất nghĩa mà vẫn sai. Có nó thì model dịch lại cho gọn theo nghĩa gốc.
- **Model trả rác / viết dài thêm / thiếu dòng ⇒ giữ nguyên bản cũ.** Không bịa, không cắt bừa.
  Model hỏng hẳn ⇒ job `failed`, **không vùng nào bị đổi** — thà không đổi gì còn hơn để lại
  một trang nửa cũ nửa mới không ai lần ra được.

### Cái gì KHÔNG làm

**Không hạ `TYPESET_MIN_FONT_SIZE`.** Thu chữ nhỏ hơn 10 để hết cảnh báo là giấu vấn đề đi chứ
không giải quyết gì — và người đọc thì không đọc được.

## Changed Files

| File | Đổi gì |
|---|---|
| `app/services/typeset/suc_chua.py` *(mới)* | Đo sức chứa một khung theo font thật |
| `app/services/translate/rut_gon.py` *(mới)* | Prompt rút gọn + bộ đối chiếu phản hồi |
| `app/workers/tasks.py` | `_run_rut_gon` + task `translate.run_rut_gon_job` |
| `app/services/dispatch.py` | `dispatch_rut_gon_job` |
| `app/api/v1/routes.py` | `POST /pages/{id}/fit-translation` |
| `app/core/config.py` | `E18_RUT_GON_TIMEOUT_SECONDS`, `E18_CO_CHU_MUC_TIEU_TY_LE` |
| `frontend/src/api.js`, `App.jsx` | Nút **"Rút gọn cho vừa khung (N)"**, chỉ hiện khi có vùng tràn |

## New API

`POST /api/v1/pages/{page_id}/fit-translation` → **202** `{job_id, page_id, so_vung_tran, status}`

- Trang không có vùng nào tràn ⇒ **422** `khong_co_vung_tran`. Hỏi suông vẫn tốn token, và bản
  dịch đang vừa khung mà đem rút gọn là làm mất chữ vô cớ.
- Job xong trả: `so_vung_rut_gon`, `bo_qua_sua_tay` (danh sách id), `con_tran`, `vua_khung`,
  `suc_chua_nho_nhat/lon_nhat`, `token_cost`.

## Tests

**Unit** (`test_rut_gon_unit.py`, 20 test): cỡ chữ mục tiêu · sức chứa theo khung/cỡ chữ, tất
định · **đối chiếu ước lượng với `fit()` thật trên 4 cỡ khung** · prompt có số ký tự tối đa của
từng mục và có chữ gốc · bộ đối chiếu loại dòng dài hơn bản cũ, dòng rỗng, dòng thiếu, phản hồi
rác — nhưng **không** loại chỉ vì lệch ước lượng vài ký tự.

**Integration** (`test_rut_gon_integration.py`, 10 test, DB thật): rút gọn xong tự căn lại và
hết tràn · prompt mang theo sức chứa + chữ gốc · **không đụng vùng đã sửa tay và nói ra là đã bỏ
qua** · model trả rác/viết dài thêm ⇒ bản dịch không đổi · model hỏng ⇒ job `failed`, bản dịch
không đổi · trang không tràn ⇒ 422, không gọi model.

### Hai lần bộ test tự lừa mình, sửa được nhờ đo

1. **Bong bóng của fixture quá to.** `sample_page_image` có bong bóng 470×280 — từ A1, khung nới
   ra tới cả lòng bong bóng nên bản dịch dài mấy cũng vừa, tiền đề "đang tràn" không bao giờ
   đúng. Phải dựng trang riêng có bong bóng **140×100**, đúng cỡ bong bóng manga thật.
2. **Ảnh clean của fixture trắng tinh.** `fake_inpainter` ghi ra một ảnh **không một nét mực
   nào** — mà từ A1, không có mực nghĩa là không có gì chặn phép nới: khung phình tới kịch trần.
   Bộ test khi đó đang đo một thế giới không tồn tại. Phải vẽ viền bong bóng vào ảnh clean.

Cả hai đều là hệ quả trực tiếp của A1 — bản sửa trước làm sai lệch tiền đề của bộ test sau.

## Live Verification

Chạy thật trên bản chạy, **có gọi Gemini thật**. Trang dựng đúng kiểu manga đen trắng: bong bóng
nhỏ, bên trong là câu tiếng Nhật thật, để cả pipeline chạy bằng đường thật.

### Tái hiện được hiện tượng gốc bằng số

```
OCR đọc được : 昔好きだった女の子が子供の頃の冒険の話をしてたって聞いたんだ   (29 ký tự)
dịch (google_fast) : 125 ký tự tiếng Việt        ← nở gấp 4,3 lần
ô đặt chữ (sau A1) : 120×53 px
căn chữ            : overflow_warning, cỡ 10 (cỡ nhỏ nhất)
```

### Lượt 1 — ĐẠT về cơ chế, HỎNG về chất lượng

```
rút gọn job 259b2fa5: 1 vùng tràn, rút gọn 1, bỏ qua 0 vùng đã sửa tay
                      · sau khi căn lại: vừa 1, tràn 0 · 1,5s
```

125 ký tự → **28**, tràn → vừa khung cỡ 21. Nhưng bản rút gọn là *"Nghe bồ kể hồi nhỏ đi
phượt."* — **đánh rơi "cô gái tôi từng thích"**. Đó là mất thông tin, không còn là rút gọn.

Đo ra thì model không sai, **cấu hình sai**: sức chứa giao cho nó chỉ **22 ký tự**. Không câu
tiếng Việt nào giữ đủ ý trong 22 ký tự.

Vì sao 22: tỉ lệ cỡ chữ mục tiêu để 0,5, và tôi tính nó trên dải **10–28** của mặc định lúc phát
triển — trong khi bản chạy thật để **`TYPESET_MAX_FONT_SIZE=40`**. Điểm giữa thành **cỡ 25** thay
vì 19, sức chứa co lại theo.

**Đây là loại sai chỉ lộ ra khi chạy thật**: test xanh, cơ chế đúng, con số sai vì môi trường
thật khác môi trường phát triển ở đúng một biến.

### Lượt 2 — sau khi hạ tỉ lệ 0,5 → 0,35 và sửa prompt

Dịch lại vùng đó cho về đúng bản 125 ký tự ban đầu, rồi rút gọn lần nữa trên bản đã chỉnh:

| | Bản rút gọn | Độ dài | Căn chữ |
|---|---|---|---|
| **Lượt 1** | *"Nghe bồ kể hồi nhỏ đi phượt."* | 28 | vừa, cỡ 21 |
| **Lượt 2** | *"Nghe nói cô gái tôi thích kể về cuộc phiêu lưu hồi nhỏ."* | **55** | vừa, cỡ 15 |

Lượt 2 **giữ lại được cả "cô gái tôi thích" lẫn "cuộc phiêu lưu hồi nhỏ"** — đúng hai mẩu thông
tin lượt 1 đánh rơi — mà vẫn vừa khung. Đổi lại chữ nhỏ hơn (15 thay vì 21), và đó là đánh đổi
đúng: chữ to hơn mà mất nghĩa thì to để làm gì.

### Chưa kiểm chứng

Chưa chạy trên **đúng trang manga của người dùng** (chapter thuộc tài khoản của họ). Trang dựng
thử tái hiện đúng cơ chế nhưng chỉ có **một** bong bóng; trang thật có 8 vùng, và mỗi vùng một
sức chứa khác nhau trong cùng một lượt gọi mô hình.

## Remaining Limits

1. **Chỉ chạy trên đường LLM.** Cần `GEMINI_API_KEYS`; hết quota thì job hỏng và bản dịch giữ
   nguyên. Đường `google_fast` không rút gọn được vì engine đó không nhận chỉ dẫn.
2. **Chưa nhét sức chứa vào bước dịch chính.** Đường `llm_context` hoàn toàn có thể nhận giới
   hạn độ dài ngay từ lần dịch đầu — làm được thì đỡ hẳn một lượt gọi mô hình. Chưa làm, vì
   người dùng đang dùng `google_fast` nên chưa đo được lợi ích thật.
3. **Rút gọn có thể làm mất sắc thái.** Model được lệnh giữ ý chính và tên riêng, nhưng câu ngắn
   đi thì giọng điệu nhạt đi là chuyện khó tránh. Vì vậy nó là nút bấm, không phải mặc định.
4. **Một lượt rút gọn không đảm bảo hết tràn.** Bong bóng quá nhỏ so với câu thoại thì kể cả
   bản ngắn nhất vẫn tràn — lúc đó chỉ còn sửa tay hoặc chấp nhận.
