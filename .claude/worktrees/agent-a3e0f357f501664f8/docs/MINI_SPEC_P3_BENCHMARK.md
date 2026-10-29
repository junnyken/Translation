# MINI-SPEC ID: P3

**Name:** Đo chất lượng dịch — chọn engine bằng số, không bằng cảm giác
**Author + Date:** Phiên Claude Opus 5 / 2026-09-24
**Status:** Ready for audit — **Phase 3.0 (chốt cách chấm) phải xong trước khi code**
**Nguồn sự thật:** `docs/TONG_HOP_TINH_NANG.md` (chốt 24-09) + đo trực tiếp trên production

---

# 1. Context

## Vì sao cần

`TONG_HOP_TINH_NANG.md` §5.2 ghi: *"Đang chọn engine theo cảm giác, không có số nào."*

Hệ thống có **hai engine** với chênh lệch chi phí rất lớn, đo thật trên production 24-09:

| Engine | Chi phí đo được | Ghi chú |
|---|---|---|
| `google_fast` | **0 token** | dịch từng dòng rời rạc, không nhìn câu trước sau |
| `llm_context` | **1.416 token / trang** (`gemini-3.5-flash`) | gộp cả trang, giữ mạch văn, tự sửa lỗi OCR |

Chưa ai đo được `llm_context` **đáng giá bao nhiêu** so với `google_fast`. Người dùng đang chọn
mù, và production đặt mặc định là engine **tốn tiền**.

## Vì sao KHÔNG copy cách của Ichigo

`REPORT_ICHIGO_BLACKBOX_BENCHMARK.md` §4.2 ghi nhận Ichigo công khai leaderboard "BLEU + nhiều mô
hình frontier chấm chéo". Nhưng:

1. **Bảng của họ đo dịch sang TIẾNG ANH** (mô tả Play: *"translate… to English"*). Thứ hạng đó
   **không tự động đúng cho tiếng Việt**.
2. Công thức `Score` của họ **không công bố** — nhãn UNKNOWN trong báo cáo.
3. Ta có **2 engine**, không phải 21 mô hình. Bài toán nhỏ hơn hẳn.

Cái đáng học là **cách vận hành**: công bố số đo thay vì lời quảng cáo. Không phải copy bảng.

## Ràng buộc đã chốt của dự án (không được vi phạm)

1. Không nhúng code GPL.
2. Không kéo thư viện nặng vào container API.
3. Không nâng RAM — trần bộ nhớ là lớp bảo vệ duy nhất.
4. **Tuyệt đối không bịa số.** Mọi con số trình ra phải truy ngược được về một lượt chạy thật.
5. Fixture phải **hợp pháp và công bố được**. Chapter có bản quyền trong repo đo xong **không
   dùng làm bằng chứng công khai được**.

---

# 2. Goal

Trả lời được **bằng số, tái lập được**: với cặp EN→VI (và JA→VI nếu có fixture), `llm_context`
hơn `google_fast` bao nhiêu, ở mặt nào, và đáng bao nhiêu token cho mỗi đơn vị cải thiện đó.

**Không** phải mục tiêu: dựng leaderboard nhiều mô hình, chấm điểm tuyệt đối, hay so với đối thủ.

---

# 3. Phase 3.0 — CHỐT CÁCH CHẤM (cổng chặn, không code)

> Giống Phase 0 của Mini-Spec P0-P1: phase này **không sinh code**, chỉ sinh **một quyết định
> bằng văn bản**. Không có quyết định ⇒ không mở 3.1.

Đây là phần khó thật của cả mini-spec. Ba câu hỏi phải trả lời, và **không câu nào có đáp án hiển
nhiên**:

## 3.0.a — Chấm bằng gì?

| Cách | Ưu | Nhược |
|---|---|---|
| **BLEU / chrF** so với bản dịch tham chiếu | Rẻ, tất định, tái lập 100% | **Phải có bản dịch tham chiếu tiếng Việt do người làm.** Ta chưa có, và tự dịch tay 5 trang là công việc thật |
| **LLM chấm chéo** (một mô hình khác chấm) | Không cần tham chiếu | Tốn token; **không tất định** (chạy 2 lần ra 2 điểm); và đang lấy AI chấm AI |
| **Người chấm** (1 người, thang 1-5, mù engine) | Đáng tin nhất cho "đọc có xuôi không" | Không mở rộng được; phụ thuộc một người |
| **Chỉ số đo được, không cần chấm** — số câu bỏ sót, số lần dính tiếng Anh, số vùng `pending`, số lần `fallback_used` | **Tất định, rẻ, tái lập** | Không đo được "dịch hay", chỉ đo được "dịch sót/hỏng" |

**Khuyến nghị:** bắt đầu bằng **cách thứ tư**, vì nó tất định và trả lời được câu hỏi có giá trị
nhất ngay lập tức: *`llm_context` có thật sự ít bỏ sót hơn không?* Ba cách kia thêm sau nếu cần.

## 3.0.b — Đo trên fixture nào?

| Fixture | Tình trạng |
|---|---|
| Pepper&Carrot (CC BY-SA) | **5 trang lành, riêng biệt** — đã lọc bỏ 1 tệp cụt. Công bố được |
| Chapter manga có bản quyền trong repo | Đo được nhưng **không công bố được** |
| **Tiếng Nhật public-domain** | **KHÔNG CÓ.** Đây là chặn thật cho việc đo JA→VI |

**Phải quyết:** đo EN→VI trước (có fixture sạch), hay bỏ công đi tìm fixture JA trước?

> ⚠️ 5 trang là **mẫu rất nhỏ**. Mọi kết luận rút ra phải ghi kèm cỡ mẫu. Dự án đã có tiền lệ
> `Run C là pass RỖNG` — 3/3 assertion đạt trên n=9 mà không chứng minh được gì.

## 3.0.c — Chi phí trần là bao nhiêu?

Một lượt `llm_context` = **1.416 token/trang** (đo thật). Chạy 5 trang × 2 engine × 3 lượt lặp
(để thấy độ dao động) ≈ **21.000 token**. Cần chủ dự án chốt trần trước khi chạy.

> `llm_context` **không tất định**: cùng một trang chạy 2 lần có thể ra 2 bản dịch khác nhau.
> Không lặp ít nhất 2-3 lượt thì không biết chênh lệch đo được là **do engine** hay **do may rủi**.

## Sản phẩm đầu ra của 3.0

```text
Ngày quyết định:
Cách chấm đã chọn:        (a / b / c / d hoặc kết hợp)
Fixture đã chọn:          (EN→VI trước, hay đi tìm fixture JA trước)
Trần chi phí:             (số token tối đa cho cả đợt đo)
Số lượt lặp mỗi cấu hình:
Người quyết định:
```

---

# 4. Phase 3.1 — Code (chỉ mở sau khi 3.0 có văn bản)

## 4.1. Audit Before Build — BẮT BUỘC

Mini-Spec P0-P1 sai **4 tiền đề** vì không audit trước. Lần này audit trước, và ghi lại:

1. **Hạ tầng đo đã có gì?** Dự án đã có `token_cost` (hiện ra API + UI từ P1), `fallback_used`,
   `TranslationStatus`, `needs_manual`. Kiểm xem **đã có sẵn bao nhiêu phần** trước khi dựng mới
   — P0-P1 cho thấy phần lớn thứ tưởng phải làm thì **đã tồn tại**.
2. **Có script đo nào sẵn trong `scripts/` không?** Repo có nhiều `do_run_*.py`. Đọc trước.
3. **Bảng thuật ngữ (E13) ảnh hưởng thế nào?** `llm_context` nhận bối cảnh thuật ngữ + giọng nhân
   vật đã duyệt. Đo mà không kiểm soát biến này là so hai thứ khác nhau.
4. **E32 (cho mô hình xem ảnh trang) đang TẮT mặc định.** Xác nhận nó tắt trong suốt đợt đo, hoặc
   coi nó là một cấu hình riêng.

## 4.2. Việc code (giả định chọn cách "chỉ số đo được")

Một script chạy được nhiều lần, ghi ra bảng tái lập được:

```text
scripts/do_chat_luong_dich.py
  - Nhận: danh sách trang fixture, danh sách engine, số lượt lặp
  - Với mỗi (trang, engine, lượt): chạy qua pipeline THẬT, không mô phỏng
  - Ghi: số vùng, số vùng dịch được, số vùng `pending`, số lần `fallback_used`,
         số vùng còn dính nguyên văn nguồn, token đã tiêu, thời gian
  - Xuất: bảng markdown + JSON thô, kèm ngày/commit/cấu hình
```

**Không** tự chấm điểm tổng hợp thành một con số duy nhất. Trình bày từng chỉ số riêng — gộp lại
thành "điểm chất lượng" là đúng thứ Ichigo làm mà ta **không kiểm chứng được công thức**.

## 4.3. Những gì KHÔNG làm

- Không dựng leaderboard nhiều mô hình.
- Không quy đổi token → tiền.
- Không đổi engine mặc định dựa trên kết quả mà chưa hỏi chủ dự án.
- Không công bố số đo chạy trên fixture có bản quyền.

---

# 5. Test Plan

- Script chạy 2 lần trên cùng cấu hình `google_fast` ⇒ **kết quả phải giống hệt** (engine này tất
  định). Khác nhau ⇒ script có lỗi, không phải engine.
- Script chạy trên fixture rỗng / 0 vùng ⇒ không nổ, ghi rõ "không có dữ liệu" thay vì 0.
- Token ghi trong bảng phải **khớp** `token_cost` đọc từ API — hai nguồn không được lệch.

---

# 6. Success Criteria

1. Có văn bản quyết định 3.0 (cách chấm, fixture, trần chi phí, số lượt lặp).
2. Script chạy lại cho ra **cùng kết quả** với `google_fast`.
3. Bảng kết quả ghi đủ: ngày, commit, cấu hình, cỡ mẫu, token đã tiêu.
4. Mọi con số truy ngược được về một lượt chạy thật.
5. Kết luận ghi kèm **cỡ mẫu** và nói rõ cái gì **chưa** đo được.
6. Không vượt trần chi phí đã chốt.

---

# 7. Stop Rules

1. Không code trước khi 3.0 có văn bản quyết định.
2. Audit Before Build phát hiện thứ đã tồn tại ⇒ **dùng lại**, không dựng nguồn sự thật thứ hai.
   (Bài học P0-P1: `export-warnings` và `token_cost` đều đã có sẵn.)
3. Phát hiện vấn đề mới ngoài phạm vi ⇒ DỪNG, báo cáo 4 phần, không tự code.
4. Vượt trần chi phí ⇒ DỪNG, báo cáo, xin trần mới.
5. Kết quả đo mâu thuẫn với kỳ vọng ⇒ **báo đúng số đo**, không chỉnh script cho ra kết quả "đẹp".

---

# 8. Rủi ro đã biết

| Rủi ro | Mức |
|---|---|
| 5 trang là mẫu quá nhỏ để kết luận rộng | **Cao** — phải ghi cỡ mẫu ở mọi kết luận |
| `llm_context` không tất định ⇒ chênh lệch có thể là may rủi | **Cao** — bắt buộc lặp ≥2 lượt |
| Không có fixture JA ⇒ không đo được cặp quan trọng nhất (manga Nhật) | **Cao** — chặn thật |
| Đo tốn token thật | Trung bình — có trần thì kiểm soát được |
| Chỉ số đo được không nói lên "dịch hay" | Trung bình — nói rõ giới hạn, đừng bán nó thành "điểm chất lượng" |
