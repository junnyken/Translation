# Báo cáo Mini-Spec E13 — Thuật ngữ, giọng nhân vật & rà soát nhất quán

**Project:** Translation · **Phase:** E — nâng chất lượng bản dịch · **Ngày:** 2026-08-29
**Nền:** M1–M10 (`v1.0-M10`) · E11 (`v1.1-E11`) · E12 (`v1.2-E12`, `781971b`)

## 1. Summary

E13 cho người biên tập **chốt cách dịch cho cả chapter** rồi tìm những chỗ chưa theo: tạo bảng
thuật ngữ riêng cho từng chapter, quét toàn bộ để tìm chỗ dùng khác thuật ngữ đã chốt, và cho
duyệt/sửa/bỏ qua **từng chỗ một**.

Điểm cốt lõi: **E13 không tự sửa gì cả.** Nó chỉ chỉ ra vấn đề kèm bằng chứng, người quyết định.
Không có nút "áp dụng cho cả chapter", không chấm điểm chất lượng, không để máy tự phán bản dịch
nào hay hơn.

**3 bảng mới**, 1 migration, **697 test backend + 91 test giao diện pass** (+70 backend, +18 giao diện so với E12). Giao diện D1–D5 đã dựng và **đã kiểm bằng Chromium thật** (Run C/D, 17/17 đạt).

## 2. Audit Before Build

10/10 mục có bằng chứng ở `TEST_LOG § E13.1`. Phát hiện quan trọng nhất là **mục 6**:

Spec cảnh báo đừng tin ràng buộc duy nhất khi khoá ngoại để trống. Kiểm chứng trên chính Postgres
16.15 đang chạy: `UNIQUE (a, b)` với `b = NULL` **cho chèn trùng** (2 dòng giống hệt lọt qua), vì
Postgres coi mỗi NULL là một giá trị khác nhau. `UNIQUE NULLS NOT DISTINCT` mới chặn đúng.

Điều này quyết định cả thiết kế: `ConsistencyReviewTask` có **hai** khoá ngoại tuỳ chọn và việc do
luật sinh ra luôn để trống một trong hai — không có `NULLS NOT DISTINCT` thì mỗi lần quét lại sẽ
đẻ thêm một bộ việc trùng.

## 3. Design Choice

- **Luật tất định trước, LLM sau (và mặc định TẮT).** Luật kiểu "thuật ngữ đã chốt là X mà chỗ này
  không có X" thì rẻ, chạy lại ra đúng kết quả cũ, và **giải thích được cho người dùng**. Nó cũng
  thành thật về giới hạn: máy không biết câu nào dịch hay hơn, nó chỉ biết chỗ nào không theo quy
  ước đã chốt.
- **Thuật ngữ theo từng chapter, không dùng chung.** Cách dịch hợp ở truyện này có thể sai hẳn ở
  truyện khác — mỗi bộ có thế giới riêng.
- **`definition` bắt buộc.** Một cặp chữ trần trụi không đủ để giữ bản dịch nhất quán; người duyệt
  sau cần biết thuật ngữ đó nghĩa là gì mới quyết được từng chỗ.
- **Sửa nội dung thuật ngữ đã duyệt ⇒ quay về nháp.** Không làm vậy thì một luật cả chapter đang
  dùng bị đổi nghĩa âm thầm, và mọi việc rà soát tạo ra từ luật cũ thành vô nghĩa mà không ai biết.
  Sửa *ghi chú* thì không — ghi chú không đổi nghĩa của luật.
- **Vân tay bản dịch (`snapshot_hash`) là chốt chặn quan trọng nhất.** Bản dịch đổi kể từ lần quét
  ⇒ việc thành `stale` và **không áp được nữa**. Áp một đề xuất tính trên bản dịch cũ là xoá mất
  phần người khác vừa sửa ở M7.
- **Chỉ biến thể người dùng tự khai mới bị gắn cờ cấm.** Máy không tự nghĩ ra từ đồng nghĩa rồi
  bảo là sai.
- **Không có chữ gốc thì không kết luận gì.** OCR rỗng/cần xem lại ⇒ bỏ qua vùng đó. Đoán thuật
  ngữ từ bản dịch là bịa bằng chứng; chất lượng vùng là việc của E12.
- **Tôn trọng quyết định ở E12.** Vùng người dùng đã bấm "bỏ qua" không bị quét lại — dựng lại việc
  cho vùng đó là phớt lờ quyết định của họ.
- **Không tự bỏ qua chữ tượng thanh/số/chữ ngắn.** E13 không tự quyết định cái gì là "nhiễu" —
  và Run A cho thấy vì sao: chính vùng `SPLASH` mới là chỗ dịch sai.
- **Áp xong dùng lại đúng đường canh chữ của M7**, chỉ cho **một** vùng. Cỡ chữ đã ghim giữ nguyên;
  chữ mới không vừa thì báo tràn khung chứ không tự bỏ ghim.
- **Hồ sơ giọng nhân vật là hướng dẫn của NGƯỜI**, cố ý không có trường "độ tin cậy". v1 chưa sinh
  việc tự động từ hồ sơ giọng — máy không tự phán một câu có đúng giọng nhân vật hay không.

## 4. Changed Files

| File | Đổi gì |
|---|---|
| `app/services/consistency/matching.py` | **mới** — so khớp theo ngôn ngữ: ranh giới từ tiếng Anh (giữ hành vi `'`/`-`), chuỗi con JP/CN ưu tiên dài trước, chuẩn hoá NFC |
| `app/services/consistency/glossary.py` | **mới** — vòng đời thuật ngữ + hồ sơ giọng |
| `app/services/consistency/scanner.py` | **mới** — quét theo luật, idempotent, phát hiện việc cũ |
| `app/services/consistency/apply.py` | **mới** — áp/từ chối, chốt chặn vân tay bản dịch |
| `app/models/__init__.py`, `enums.py` | +3 bảng, +6 enum |
| `alembic/versions/0006_e13_glossary.py` | migration, `NULLS NOT DISTINCT`, downgrade drop đúng enum mới |
| `app/api/v1/routes.py` | +13 endpoint |
| `app/schemas/common.py` | +13 schema |
| `app/workers/tasks.py` | `run_consistency_scan_job` |
| `tests/test_consistency_*.py` | **mới** — 62 test |
| `tests/test_no_ai_logic.py` | +8 guardrail |

## 5. New API / DB

**13 endpoint mới** dưới `/api/v1`: quản lý thuật ngữ (5), hồ sơ giọng (5), quét & rà soát (5 —
`consistency-scans`, `consistency-summary`, `consistency-tasks`, `accept`, `reject`).

**DB:** `glossary_entry`, `character_voice_profile`, `consistency_review_task`. Không đổi bảng cũ.

## 6. Tests

`697 passed, 6 skipped` — 25 unit so khớp, 37 integration, 8 guardrail. Chi tiết `TEST_LOG § E13.3`.

## 7. Live Verification

**Run A + Run B chạy trên 3 trang Pepper&Carrot thật (CC BY-SA).** Số liệu đầy đủ:
`TEST_LOG § E13.4–5`.

Điểm đáng giá nhất: E13 **tự tìm ra đúng lỗi mà Run C của M8 đã phát hiện bằng tay** — từ tượng
thanh `SPLASH` bị `google_fast` dịch thành `"TUYỆT VỜI"`. Cả hai luật cùng bắt được:
`glossary_missing` (chưa dùng thuật ngữ đã chốt "TÕM") và `prohibited_variant` (đang dùng đúng
biến thể người dùng đã cấm).

Sau khi duyệt và áp bản tự sửa: bản dịch thành `TÕM!\n18`, `edited_by_user=true`, việc thứ hai
trên cùng vùng tự thành `stale`, cố áp nó bị chặn **422**, quét lại còn **0 việc mở**, và
**chữ gốc OCR `SPLASH\n18` nguyên vẹn**.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí | Kết quả |
|---|---|
| Thuật ngữ theo chapter, chỉ bản đã duyệt tham gia quét | ✅ đo live: chưa duyệt ⇒ 0 việc |
| Quét tạo việc giải thích được, **không tự sửa bản dịch** | ✅ có test so nguyên bộ trước/sau |
| Thuật ngữ chapter này không ảnh hưởng chapter khác | ✅ có test cách ly |
| Mỗi việc có bằng chứng + phát hiện được bản đã cũ, việc cũ không áp được | ✅ live 422 |
| Áp chỉ đổi đúng một vùng, đánh dấu sửa tay, giữ cỡ chữ ghim | ✅ live + test |
| Từ chối không đổi gì | ✅ |
| Vùng E12 đã bỏ qua vẫn bị loại; chữ tượng thanh/số không tự bị bỏ | ✅ |
| M1–M10/E11/E12 vẫn pass | ✅ 697 pass, không nới lỏng kỳ vọng cũ |
| **Giao diện (D1–D5)** | ✅ đã dựng, Run C 9/9 đạt trên Chromium thật |
| **Cảnh báo lúc xuất tách riêng (D5)** | ✅ Run D 8/8 — ba khối tách bạch, vẫn xuất được |
| Xem hồ sơ giọng **không** đụng vào bản dịch | ✅ băm md5 toàn bộ bản dịch giống hệt trước–sau |
| Gợi ý bằng LLM | ⚠️ để tắt mặc định, chưa thử |

## 9. Giao diện D1–D5 và ba lỗi nó làm lộ ra

Giao diện dựng xong ở lần làm thứ hai: bảng "Nhất quán" (D1), quản lý thuật ngữ (D2), hồ sơ giọng
(D3), hàng đợi rà soát (D4), khối cảnh báo riêng trong hộp thoại xuất (D5). Số liệu đầy đủ ở
`TEST_LOG § E13.6–9`.

Cả **ba** lỗi tìm được đều là mã chạy đúng nhưng **hiển thị sai** — không test đơn vị nào bắt
được, chỉ lộ ra khi nhìn màn hình thật:

1. `GIONG_NOI` là bảng chuỗi, mã mới lại đọc `.nhan` trên chuỗi ⇒ in thẳng mã `casual` ra cho
   người dùng đọc.
2. Tiêu đề cột ẩn (`position: absolute`) không bị khung cuộn cắt vì khung thiếu `position:
   relative` ⇒ **cả trang trôi ngang 23px ở 360px**, đo bằng `window.scrollX`.
3. Khối "Vì sao các chỗ này được nêu" mượn lưới của E12, nơi con số đứng cuối dòng ⇒ ở E13 con số
   đứng đầu nên bị CSS đẩy sang phải, vỡ cột.

Sau khi sửa: 0 tràn ngang ở cả 4 kích thước, 0 lỗi console, 29 điểm dừng tab (không đổi so với
trước khi thêm E13).

## 10. Remaining Limits / Follow-ups

- **Gợi ý bằng LLM chưa bật** (`E13_LLM_SUGGESTIONS_ENABLED=false`). Đường luật chạy độc lập.
- **Luật giọng nhân vật v1 chưa sinh việc tự động** — hồ sơ giọng mới là ngữ cảnh hiển thị.
- Chỉ đo trên **một** chapter 3 trang; chưa thử chapter dài vài chục trang.
- Run C/D mới chạy trên **Chromium**; chưa thử Firefox/Safari, và chưa kiểm bằng trình đọc màn
  hình thật.
- Không có bộ nhớ thuật ngữ dùng chung giữa các chapter, không tự nhận diện nhân vật đang nói,
  không đo được đúng-sai về nghĩa. Đúng phạm vi đã chốt.

**Mini-spec kế tiếp:** E14.
