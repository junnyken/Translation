# DECISION LOG — Phase 0 (Mini-Spec P0-P1)

> Phase 0 không sinh code. Nó sinh ra đúng một thứ: **quyết định bằng văn bản**.
> Không có file này ở trạng thái hoàn chỉnh ⇒ **không mở Phase 1**.

---

## Quyết định

| | |
|---|---|
| **Ngày quyết định** | 2026-09-24 |
| **Hướng đã chọn** | **A** — giữ nguyên quyết định "không tick hộ người dùng", chỉ thêm thông tin |
| **Người quyết định** | Nguyễn Thiên Triều (`trieunt@matbao.com`) — chủ dự án |
| **Người ghi chép** | Phiên làm việc Claude Opus 5, theo Mini-Spec P0-P1 |

### Nội dung quyết định

Đường **"Dịch nhanh"** sẽ:

- ✅ Hiện **một dòng** báo số trang có vùng chữ cần xem lại, **sau khi** file đã tải về
- ✅ **Im lặng khi sạch** — không có trang nào bị gắn cờ thì không hiện gì thêm
- ❌ **Không** chặn hoặc trì hoãn việc tải file tự động
- ❌ **Không** thêm nút bấm hay ô tick mới
- ❌ **Không** đụng tới cổng M10 (khai báo mục đích sử dụng) hay bước ghi nhận trách nhiệm trước khi xuất

---

## Lý do — kèm một đính chính về tiền đề của Mini-Spec

Mini-Spec dựng Phase 0 như một cổng để **gỡ mâu thuẫn** giữa Mục 5.3 và Mục 5.5 của
`TONG_HOP_TINH_NANG.md`. Audit trước khi quyết định cho thấy **mâu thuẫn đó không tồn tại**:

| Mục | Nói về cái gì |
|---|---|
| **5.3** | Bước **tick xác nhận trách nhiệm bản quyền** trước khi xuất (`POST /export-jobs/{id}/acknowledge`) |
| **5.5** | Cờ **chất lượng** `needs_review` trên từng vùng chữ |

Hai chuyện khác nhau. Mục 5.3 cấm hệ thống **tick hộ** người dùng — nó **không** cấm hệ thống
**hiện thông tin**. Nên Hướng A không phải một bên của cuộc xung đột; nó **tương thích với cả
hai mục** và không cần bất kỳ quyết định nào bị đảo.

**Vì vậy quyết định này không phải "chọn giữa hai triết lý đối nghịch"**, mà chỉ là trả lời một
câu hỏi gọn: *có hiện thông tin hay không*. Câu trả lời là **có**.

### Vì sao chọn hiện thông tin

Giá trị cốt lõi của đường nhanh là tốc độ và tối giản: một màn, thả file, tự tải về. Vấn đề thật
**không phải** "ngăn người dùng xuất file có trang đáng ngờ" — việc đó thuộc đường đầy đủ. Vấn đề
thật là người dùng **không biết** file vừa tải có trang đáng ngờ. Một dòng chữ giải quyết đúng
khoảng trống đó mà không tốn một giây nào của tốc độ.

Giữ nguyên nguyên tắc xuyên suốt của dự án: *hỏng thì nói ra, không im lặng; nhưng cũng không
khẳng định "mọi thứ ổn" khi chưa đo được điều đó là đúng.* Nên khi sạch thì **im lặng**, không
hiện "0 trang cần rà soát".

---

## Ba tiền đề khác của Mini-Spec đã được audit và ĐÍNH CHÍNH

Ghi lại ở đây vì chúng **đổi phạm vi Phase 1**, không chỉ là chi tiết:

| Tiền đề trong Mini-Spec | Sự thật đo được |
|---|---|
| `ROADMAP_KHAC_PHUC_TOAN_DIEN.md` là nguồn sự thật, viện dẫn "vấn đề #1, #2, #19" | **File không tồn tại trong repo.** Mọi số hiệu vấn đề trong Mini-Spec **không truy ngược được**. `MINI_SPEC_PLAYBOOK.pdf` cũng không có |
| `token_cost` chưa expose ra API, cần audit rồi thêm vào response | **Đã expose sẵn** (`schemas/common.py:276`). Đo thật trên production 24-09: `GET /pages/{id}/translation` trả đủ `token_cost`, `engine`, `model_name`. ⇒ **Phần backend của B2 không còn việc gì**, chỉ còn giao diện |
| Đường nhanh có `batch_id`, thiết kế `get_review_flag_summary(batch_id)` | **Đường nhanh KHÔNG tạo `BatchRun`.** Nó gọi `taoProject` → `taiTrangLen`/`taiGoiLen` → `xuatChapter`. Khoá đúng là **`project_id`**. Viết theo Mini-Spec sẽ ra một hàm không có gì để nhận |
| `ocr_needs_review` là tên cờ OCR | **Không tồn tại.** Tên thật cần xác nhận lại ở Audit Before Build — Mini-Spec tự nghi ngờ điểm này và nghi ngờ đó đúng |

---

## Ảnh hưởng tới Phase 1

1. **B1 (cảnh báo)** — vẫn làm, theo Hướng A. Nhưng khoá tra cứu là **`project_id`**, không phải
   `batch_id`. Tên hàm/chữ ký trong Mini-Spec phải sửa theo thực tế, không sửa thực tế cho khớp
   Mini-Spec.
2. **B2 (token_cost)** — **chỉ còn phần giao diện**. Chủ dự án chốt hiện ở **cả hai chỗ**: cạnh
   từng trang ở màn rà soát, và tổng cả chapter ở màn tóm tắt trước khi xuất.
3. **Audit Before Build (§5 Mini-Spec) vẫn bắt buộc** — đặc biệt là xác nhận tên thật của cờ
   `needs_review` phía OCR, và endpoint thật mà đường nhanh dùng.
4. Mọi số hiệu "#1/#2/#19" trong Mini-Spec **không dùng làm căn cứ** trong báo cáo, vì tài liệu
   gốc của chúng không tồn tại trong repo.

---

## Điều kiện đóng Phase 0

- [x] Đọc lại nguyên văn Mục 5.3 và 5.5, xác nhận quan hệ thật giữa chúng
- [x] Trình bày hai hướng cho chủ dự án
- [x] Chủ dự án chọn một hướng
- [x] Ghi lại quyết định: ngày, hướng, lý do, người quyết định, ảnh hưởng tới Phase 1

**Phase 0: ĐÓNG.** Phase 1 được phép mở.
