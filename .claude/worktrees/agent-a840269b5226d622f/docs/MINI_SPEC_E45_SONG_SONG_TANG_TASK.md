# MINI-SPEC ID: E45

**Name:** Song song hoá tầng task — đo xem có khả thi trong trần RAM hiện tại không
**Author + Date:** Phiên Claude Opus 5 / 2026-09-24
**Status:** Audit xong — **CHỜ QUYẾT ĐỊNH ở §3**, chưa được code
**Nguồn:** `REPORT_E25.md` §2.8 — hướng duy nhất E25 để mở, vì phép đo của chính nó thất bại

---

# 1. Đính chính trước: tôi đã gọi hướng này là "rẻ". Nó KHÔNG rẻ.

Khi báo cáo miệng, tôi xếp song song hoá là *"hướng rẻ còn lại chưa ai đo"*, dựa vào câu kết của
E25 §2.8: *"RSS ~1117MB mỗi tiến trình ⇒ 2 worker ≈ 2,2GB, nhét được vào 4096MB"*.

**Phép tính đó sai.** Audit ngày 24-09 tìm ra ba chỗ nó bỏ sót.

## 1.1. Ngân sách thật không phải 4096MB

Production chạy `ROLE=all`: **một** container 4096MB chứa **cả** uvicorn (API) lẫn Celery worker
(`deploy/docker-compose.e23-mem.yml` §đầu). API lúc rảnh đo được ~104MB.

⇒ Ngân sách thật của worker là **~3950MB**, không phải 4096MB.

## 1.2. Đỉnh RSS một worker KHÔNG phải 1117MB

Con số 1117MB của E25 là RSS của tiến trình ở bàn thử riêng. Số **đo trên đường thật** cao hơn
nhiều (`config.py:405-420`, đo lại 14-09):

| Ô cắt xoá chữ | Đỉnh RSS một worker |
|---|---|
| 1,4 Mpx | 2401 MB |
| **1,6 Mpx ← trần hiện tại** | **2295 MB** |
| 1,8 Mpx | 2951 MB |
| 2,6 Mpx | 3912 MB |

Với trần hiện tại (`inpaint_max_crop_mpx = 1.6`), **một** worker đã đỉnh ~2295MB.

⇒ **Hai worker phổ thông ≈ 4590MB > 3950MB. Không vừa. Sẽ OOM.**

Đây không phải rủi ro lý thuyết: worker production **đã bị SIGKILL/137 hai lần**
(`/healthz: so_lan_chet: 2`), và người dùng đã chốt **KHÔNG nâng RAM hai lần** (11-09 và 14-09).
`inpaint_max_crop_mpx` bị hạ 2,6 → 1,6 chính vì 96% ngân sách vẫn chưa đủ.

## 1.3. `--pool=solo` là điều kiện ĐÚNG ĐẮN, không phải tuỳ chọn hiệu năng

Đây là chỗ nguy hiểm nhất, và E25 không nhắc tới.

`worker_sweep_orphan_jobs_on_start = True` đánh dấu **mọi** job đang `running` lúc worker khởi
động là hỏng. `config.py:53` nói thẳng điều kiện đúng đắn của nó:

> *"ĐÚNG ĐẮN CỦA CỜ NÀY PHỤ THUỘC TOPOLOGY: hiện chỉ có MỘT worker... Ngày nào chạy nhiều worker
> thì **phải tắt cờ này trước**, rồi mới đổi sang cơ chế job-có-chủ (id worker + nhịp tim)."*

`hoi_phuc.py` lặp lại cảnh báo đó ở đầu tệp và gọi nó là *"điều kiện đúng đắn của cả tệp"*.

⇒ Bật worker thứ hai mà không làm gì trước: **worker B khởi động sẽ đánh hỏng job đang chạy hợp lệ
của worker A.** Mất việc đang chạy, không phải chậm.

Ít nhất 5 nơi đang dựa vào giả định một worker: `config.py:53`, `hoi_phuc.py`, migration
`0017_e22_job_heartbeat`, `routes.py:1496`, `routes.py:1573`.

---

# 2. Vậy còn gì để đo?

Cách làm hiển nhiên (`--concurrency=2`) đã bị §1.2 chặn bằng số. Nhưng có **một biến thể E25 chưa
xét**, và nó xuất phát từ chính bảng RSS theo model đã đo (`config.py:39-43`):

> detector **~1,1 GB** · PaddleOCR **~0,7 GB** · LaMa **~1,2 GB**

Một worker phổ thông phải sẵn sàng chạy **mọi** bước nên có lúc giữ nhiều model cùng lúc (đo được
`RSS 1914,7 MB` khi detector + PaddleOCR cùng thường trú). Đó là lý do nó phình.

**Ý tưởng: chuyên hoá worker theo hàng đợi.** Mỗi worker chỉ nhận một loại việc nên chỉ cần giữ
**một** model:

| Worker | Hàng đợi | Model thường trú |
|---|---|---|
| A | `detect` | detector ~1,1 GB |
| B | `inpaint` | LaMa ~1,2 GB |

Lợi thế kép nếu nó chạy được:
- **RAM có thể vừa** ở chỗ hai worker phổ thông không vừa;
- **song song theo chiều ống**: trang N đang xoá chữ thì trang N+1 đã nhận diện được rồi. Đúng
  hai bước chiếm ~86% thời gian.

> ⚠️ **Đây là GIẢ THUYẾT, không phải kết luận.** Đỉnh 2295MB lúc xoá chữ **không phải chỉ là model**
> — còn ảnh, mask và bộ đệm trung gian của LaMa. Worker chuyên hoá vẫn có thể đỉnh sát mức đó.
> Chưa đo thì chưa biết. Tôi vừa sai hai lần trong ngày vì suy luận thay cho đo (xem E44).

---

# 3. QUYẾT ĐỊNH CẦN CHỦ DỰ ÁN CHỌN — cổng chặn, chưa chọn thì chưa code

| | Hướng | Việc phải làm trước | Rủi ro |
|---|---|---|---|
| **A** | **Chỉ ĐO tính khả thi RAM** của worker chuyên hoá, chưa đụng production | Script đo ở máy dev, bó cgroup giống production | Thấp — không đổi mã sản phẩm |
| **B** | Làm thật: chuyên hoá hàng đợi | A xong + **cơ chế job-có-chủ** (id worker + nhịp tim) + tắt cờ quét mồ côi | Cao — đụng đúng phần E22 dựng để chống mất việc |
| **C** | Nâng RAM 4096 → 5376MB rồi mới `--concurrency=2` | Vẫn cần job-có-chủ | Người dùng **đã từ chối nâng RAM hai lần**; nhưng hai lần đó là để lấy *biên an toàn*, còn đây là đổi lấy *thông lượng* — bối cảnh khác, nên vẫn đáng hỏi lại |
| **D** | Không làm | — | Giữ ~100s/trang |

**Khuyến nghị: A.** Nó rẻ, không đụng production, và trả lời đúng câu chặn mọi hướng còn lại: *hai
tiến trình model có vừa 3950MB không?* Nếu A cho kết quả âm thì B và C đều vô nghĩa và ta dừng gọn,
không tốn công xây job-có-chủ cho một hướng bất khả thi.

---

# 4. Thiết kế phép đo — tránh đúng hai lỗi đã giết lượt đo của E25

E25 §2.8 tự khai báo phép đo của nó **không dùng được** vì hai lý do độc lập. Cả hai phải bị chặn
bằng thiết kế, không phải bằng lời hứa cẩn thận.

## 4.1. Lỗi 1 — đếm lượt theo GIẢ ĐỊNH

Script cũ chia thời gian tường cho `so_tien_trinh * SO_LUOT`, trong khi một tiến trình con **đã
chết** và chỉ 4/6 lượt chạy thật. Nó in ra "42,9s/trang", trông y hệt một cú thắng gấp đôi, và con
số đó **không có thật**.

**Chặn bằng:**
1. Mỗi lượt xong phải tự ghi một dòng kết quả; thống kê chỉ đọc từ các dòng **thật sự có**.
2. `p.join()` xong **bắt buộc kiểm `p.exitcode`**; khác 0 thì lượt đó bị loại và **ghi rõ đã loại**.
3. **Cấm chia cho hằng số lượt dự kiến.** Mẫu số phải là số lượt đếm được.
4. In cả `số lượt dự kiến` và `số lượt tính` cạnh nhau — lệch nhau là cờ đỏ hiện ngay trên báo cáo.

## 4.2. Lỗi 2 — bàn thử nhiễu hơn hiệu ứng cần đo

Cùng một tiến trình, cùng một trang, lượt dao động **45,9–129,3s** (biên độ ~3×). Máy chủ dùng
chung đang chạy việc khác (37/62GB RAM). Với nhiễu đó thì không hiệu ứng nào dưới 3× có nghĩa.

**Chặn bằng:**
1. **Đo tải máy trước và trong lượt chạy**; vượt ngưỡng thì **huỷ lượt đo**, không "chạy cho xong".
2. **Xen kẽ A/B/A/B**, không chạy AAA rồi BBB — trôi tải theo thời gian sẽ bị gán nhầm cho nhánh.
3. Báo cáo **phân bố từng lượt**, không chỉ trung bình. Một bảng trung bình che mất biên độ 3×.
4. **Luật kết luận đặt TRƯỚC khi chạy:** hiệu ứng chỉ được công nhận nếu **lớn hơn biên độ quan sát
   được của chính nhánh đối chứng**. Không đạt ⇒ kết luận là *"chưa đo được"*, **không** phải
   *"không có tác dụng"*.

## 4.3. Lỗi 3 — bàn thử không giống production (E25 dính mà không nhận ra)

E25 đo trên máy dev **12 core, `cpu.max = max 100000`, không hạn ngạch**; production là **2,6 CPU**.
Kết luận *cấu trúc* của E25 (shape tĩnh, thiếu kernel INT8, intra_op ngược chiều) vẫn chuyển được,
nhưng **mọi con số tuyệt đối thì không**.

Riêng bài RAM này thì sai lệch môi trường là **chí mạng**, vì thứ cần đo chính là *có vừa trần
không*. Phải bó **cả hai** chiều:
- RAM: đã có sẵn `deploy/docker-compose.e23-mem.yml` (3950MB, không swap — có swap thì OOM biến
  thành "chậm kinh khủng" và che mất đúng thứ cần thấy).
- CPU: **chưa có** — phải thêm ràng buộc 2,6 CPU. Thiếu nó thì hai worker ở máy 12 core sẽ chạy
  thoải mái và cho kết luận lạc quan giả.

---

# 5. Kết quả cần có

Một bảng cho mỗi cấu hình (1 worker phổ thông ← mốc; 2 worker chuyên hoá):

```text
cấu hình | lượt dự kiến | lượt TÍNH | đỉnh RSS tổng | bị OOM? | thời gian mỗi lượt (liệt kê) | thông lượng
```

Kèm: ngày, commit, ràng buộc cgroup thật sự áp được (in ra từ `/sys/fs/cgroup`, không phải từ ý
định), tải máy lúc đo.

---

# 6. Stop Rules

1. **Chưa chọn xong §3 thì không viết một dòng code nào.**
2. Đỉnh RSS tổng vượt 3950MB ⇒ **DỪNG**, kết luận hướng chuyên hoá không vừa trần hiện tại, báo
   cáo thẳng. Kết quả âm là kết quả — E25 đã có tiền lệ `KHÔNG SHIP GÌ`.
3. **Không bật worker thứ hai trên production** trong phạm vi mini-spec này, kể cả khi đo ở máy
   dev cho kết quả tốt. Việc đó cần job-có-chủ trước (§1.3) và là mini-spec riêng.
4. Nhiễu vượt hiệu ứng ⇒ báo **"chưa đo được"**, cấm ép thành kết luận theo chiều nào.
5. Phát hiện mới ngoài phạm vi ⇒ DỪNG, báo cáo 4 phần, **đừng tự mở mini-spec giữa lượt**.
6. **Trước khi mở bất kỳ hướng tốc độ nào khác: đọc `REPORT_E25.md` §1** — bảng các hướng đã đóng.
   Bỏ bước này là đúng cách E44 ra đời và chết.
