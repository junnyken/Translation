# REPORT E55 — Worker báo `starting` vĩnh viễn

**Ngày:** 2026-09-27 · **Nguồn:** lỗi tự phát hiện khi kiểm production 26-09

---

## 1. Summary

`/healthz` nay có `worker.trang_thai_thuc` và `worker.san_sang_luc`, suy từ một dấu hiệu **do chính
worker ghi**. Trường `trang_thai` cũ giữ nguyên nghĩa: thứ **shell** nghĩ.

---

## 2. Lỗi — đo được trên bản chạy thật

`deploy-start.sh` nhánh `ROLE=all`:

```sh
ghi_trang_thai starting 0      # ← một lần, rồi không bao giờ ghi `running`
( while true; do lenh_worker; …; ghi_trang_thai restarting …; done ) &
```

Không có chỗ nào ghi `running`. Nên worker chạy tốt hai ngày vẫn báo `starting`.

Đo 26-09 trên production:

```json
"worker": {"trang_thai": "starting", "luc": "2026-09-25T04:35:45Z",
           "rss_mb": 1513.9, "rss_moc": "inpaint: sau", "rss_luc": "2026-09-25T09:55:23+00:00"}
```

`starting` từ 04:35 — **42 giờ** trước lúc đo — trong khi `rss_moc` chứng minh worker ĐÃ chạy xong
một bước xoá chữ lúc 09:55. Hai trường trong cùng một phản hồi **nói ngược nhau**.

### Vì sao đây là lỗi thật, không phải chuyện thẩm mỹ

Một trạng thái đứng im **tệ hơn không có trạng thái**: người vận hành không phân biệt được

* "đang nạp model" — bình thường, mất tới cả phút; với
* "chạy tốt hai ngày rồi".

Và nó phá đúng mục tiêu E22 đã đặt ra: *"worker chết mà API vẫn 200 là loại sự cố tệ nhất"*. Ở đây
là chiều ngược lại — worker sống mà báo như đang khởi động.

---

## 3. Design Choice

### 3.1. Dấu sẵn sàng phải do WORKER ghi, không phải shell

Shell **không có cách nào biết** worker đã nạp xong model — nó chỉ biết mình đã gọi lệnh. Ghi
`running` ngay trước khi gọi là **đoán**, và đoán sai suốt khoảng thời gian nạp model.

Celery có tín hiệu `worker_ready`, phát ra khi worker thật sự nhận được việc. Đó là chỗ duy nhất
biết sự thật.

### 3.2. Tệp THỨ BA, một người ghi

Không ghi vào hai tệp đã có:

* **tệp trạng thái của shell** — do shell ghi. Hai người ghi một tệp là mất dữ liệu của cả hai
  (lý do đã ghi sẵn ở `config.worker_rss_file` từ P3m);
* **`worker_rss_file`** — bị ghi **đè toàn bộ** mỗi lần đo RSS, nên một trường "sẵn sàng" nhét vào
  đó sẽ bị xoá ở mốc RSS kế tiếp.

⇒ `worker_ready_file`, ghi nguyên tử (temp + `os.replace`), **một** người ghi.

### 3.3. Ghi dấu TRƯỚC lượt dọn job mồ côi

Tín hiệu `worker_ready` nghĩa là Celery đã nạp xong; lượt dọn job mồ côi sau đó có thể mất vài giây.
Ghi dấu sau nó sẽ báo "sẵn sàng" muộn hơn sự thật — và nếu lượt dọn nổ thì **không bao giờ** ghi
được dấu, trong khi worker vẫn chạy bình thường.

### 3.4. Ba nhánh, và thứ tự có ý nghĩa

```
shell nói `restarting`  ⇒ tin SHELL
có dấu sẵn sàng         ⇒ `running`
còn lại                 ⇒ giữ nguyên thứ shell nói
```

Nhánh đầu **phải** đứng trước: shell vừa **quan sát** một lần thoát, đó là bằng chứng mạnh hơn một
dấu sẵn sàng còn sót từ lần chạy trước. Đảo thứ tự là báo `running` cho một worker vừa chết — có bài
canh riêng, và đối chứng âm đã chạy.

### 3.5. KHÔNG sửa trường `trang_thai` cũ

Có thứ đang đọc nó (`API.md §healthz`). Thêm trường mới, và để trường cũ nói đúng thứ nó vẫn nói:
**shell nghĩ gì**. Đổi nghĩa một trường đang được đọc là cách âm thầm làm hỏng người tiêu thụ.

---

## 4. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/core/config.py` | `worker_ready_file` |
| `app/workers/trang_thai_worker.py` | `ghi_dau_san_sang()` — ghi nguyên tử, hỏng thì log chứ không nổ |
| `app/workers/celery_app.py` | Gọi ở `worker_ready`, **trước** lượt dọn |
| `app/main.py` | `/healthz` suy `trang_thai_thuc` + `san_sang_luc` |

`deploy-start.sh` **không đổi** — không cần, và sửa nó sẽ là đoán.

---

## 5. Tests

8 bài (`test_e55_trang_thai_worker_that.py`).

| Bài canh | Canh cái gì |
|---|---|
| `test_shell_noi_starting_ma_worker_DA_san_sang_thi_bao_running` | Chính lỗi đang vá |
| `test_chua_co_dau_san_sang_thi_GIU_NGUYEN_starting` | Đang nạp model thật — không đoán là xong |
| `test_shell_noi_restarting_thi_TIN_SHELL` | **Bài canh nặng nhất** — thứ tự nhánh |
| `test_ghi_khong_duoc_thi_tra_None_chu_KHONG_no` | Một dấu hiệu quan sát không được ngăn worker nhận việc |
| `test_mac_dinh_cua_config_khop_voi_healthz` | Lệch một chữ là đọc một tệp, ghi một tệp khác |

**Đối chứng âm đã chạy:** đảo thứ tự hai nhánh ⇒ `test_shell_noi_restarting_thi_TIN_SHELL` đỏ.

---

## 6. Remaining Limits

* ~~Chưa kiểm trên production.~~ **ĐÃ kiểm 27-09**, đúng như dự đoán ghi trước khi deploy:

  ```json
  {"trang_thai": "starting", "san_sang_luc": "2026-09-27T09:26:31+00:00", "trang_thai_thuc": "running"}
  ```

  Shell ghi `starting` lúc 09:26:30; worker tự báo sẵn sàng lúc 09:26:31 — lệch **1 giây**, và
  trường cũ `trang_thai` giữ đúng nghĩa "shell nghĩ gì" như §3.5 đã chốt.
* Dấu sẵn sàng nằm ở `/tmp` nên **mất khi container khởi động lại** — đó đúng là điều muốn: dấu của
  lần chạy trước không được nói thay cho lần chạy này.
* Worker chết **im lặng** (bị SIGKILL, shell chưa kịp ghi `restarting`) vẫn báo `running` cho tới
  khi shell ghi. Cửa sổ đó nhỏ và đã có cơ chế khác lo (quét job mồ côi lúc khởi động, P3j), nhưng
  nó tồn tại thật.
