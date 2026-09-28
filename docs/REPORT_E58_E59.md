# REPORT E58 + E59 — Engine miễn phí phải miễn phí · Dịch cả chapter

**Ngày:** 2026-09-28 · **Nguồn yêu cầu:** chủ dự án — *"kiểm tiện ích 0.1.12 chạy thật trên một trang truyện"* và *"tự quét-dịch cả chapter … này không vấn đề tôi muốn nó hoạt động xây dựng ổn"*

---

## 1. Summary

Ba việc, theo thứ tự đã làm:

1. **Kiểm tiện ích `0.1.12` chạy thật** trên trang truyện thật → **QUA**, không cần sửa gì.
2. **E58** — vá lỗi chi phí mà lượt kiểm đó ĐO ĐƯỢC: xin engine miễn phí mà chạy engine trả tiền.
3. **E59** — dựng "Dịch cả chapter" trong tiện ích (bản `0.1.15`).

---

## 2. Kiểm tiện ích 0.1.12 — chạy thật, không sửa gì

Nạp tiện ích vào Chrome thật (`--headless=new --load-extension`), mở **trang truyện thật**:
Pepper&Carrot tập 1 bản tiếng Nhật trên website của tác giả — ảnh nạp lười, đúng kiểu trang đọc
truyện — rồi gọi **đúng lời gọi mà popup dùng** (`chrome.scripting.executeScript`).

| Đo cái gì | Kết quả |
|---|---|
| Lớp phủ | **có**, 5 ô chữ đặt theo toạ độ bong bóng |
| Chữ dịch | *"...Thế là xong rồi."* · *"...Ưm, vẫn chưa đủ sao?"* · *"Ý anh là sao?"* |
| Dịch đúng nghĩa? | **Đúng** — đối chiếu bản tiếng Anh cùng trang trong `ocr_benchmark/manifest.jsonl`: *"...and the last touch"*, *"probably not strong enough"* |
| Hạn mức | 0 → **2** |

**Hạn mức tăng 2 chứ không phải 1** là bằng chứng tính năng *xếp hàng trước 1 trang* (v0.1.11) đang
chạy thật: bấm một trang, nó tự dịch sẵn trang kế.

### Hai lượt thất bại đầu là LỖI QUY TRÌNH CỦA TÔI, không phải lỗi tiện ích

* **Lượt 1:** tôi cuộn về đầu trang trước khi tiêm ⇒ không ảnh truyện nào trong khung nhìn ⇒ bộ lọc
  loại đúng (`'ngoài khung nhìn'`). Tiện ích làm đúng.
* **Lượt 2:** tôi tìm `window.__translation_doc_truyen__` bằng `page.evaluate` và thấy `false`, kết
  luận "không chạy". Sai: content script sống ở **isolated world**, `page.evaluate` ở main world
  không đọc được biến đó — trong khi lớp phủ (DOM, dùng chung) thì **có thật**.

Ghi lại vì cả hai đều là cách dễ nhất để kết luận sai về một tiện ích đang chạy tốt.

---

## 3. E58 — xin engine MIỄN PHÍ mà chạy engine TRẢ TIỀN

### 3.1. Chuỗi đo được, không phải đọc mã

```
Tiện ích gửi           engine = google_fast          (mặc định của nó)
Máy chủ lưu            translate_engine_override = None     ← đo trên CẢ HAI trang
Pipeline lùi về        settings.translate_default_engine
/healthz               translate_default_engine = llm_context
/pages/{id}/translation  →  engine: ['llm_context']         ← đo
```

Tiện ích có chú thích của chính nó: *"`google_fast` là mặc định trung thực … **không tự tốn token
Gemini khi người dùng chưa từng bật** (đúng chủ ý M5)"*. Hành vi thật ngược lại.

### 3.2. Lỗi nằm ở một câu lý luận đúng-lúc-đó

`routes.py` mã hoá `google_fast → NULL` với lý do ghi trong mã: *"cả hai đều đọc ra dùng mặc định hệ
thống, không khác nhau"*. Câu đó **đúng khi mặc định hệ thống là `google_fast`**, và sai ngay khi ai
đó đổi biến môi trường — không có gì trong mã nhắc lại điều kiện đó.

Docstring của `Page.translate_engine_override` đã cảnh báo **bằng chữ**:

> *"lưu đúng lựa chọn người dùng, kể cả `google_fast`, thay vì để NULL: có thế thì đổi
> `translate_default_engine` của hệ thống mới không biến một lựa chọn 'miễn phí' thành engine tốn
> token sau lưng người ta."*

Hai endpoint của đường đăng nhập đã sửa theo từ ĐX-3. **Chỉ endpoint của trang chủ + tiện ích còn
sót** — và nó là mặt mở cho cả internet.

### 3.3. Bản vá

`translate_engine_override=engine` (lưu thẳng). Tương thích ngược **không đổi**: trang cũ vẫn `NULL`
⇒ vẫn lùi về mặc định hệ thống, có bài canh riêng cho đúng điều đó.

### 3.4. Một bài canh CŨ phải sửa, vì nó khẳng định SAI

`test_e19_che_do_chi_chu::test_engine_mac_dinh_khong_ghi_gi_vao_cot` khẳng định `override is None`.
Nó **bảo vệ chính cái lỗi này**. Không phải bài canh yếu — bài canh *sai*. Đổi tên thành
`…_duoc_ghi_TUONG_MINH_vao_cot`, đảo khẳng định, và ghi cả lý do cũ + số đo production vào docstring
để người sau không "sửa lại cho đúng như xưa".

---

## 4. E59 — Dịch cả chapter

### 4.1. Lý do từ chối cũ: một cái VẪN ĐÚNG, một cái là quyết định của chủ dự án

`ARCH.md §E19.6f` từ chối hướng này với hai lý do. Nay:

1. **"Không nhanh hơn"** — **vẫn đúng**, và đã nói lại với chủ dự án trước khi dựng. Máy chủ chạy 1
   việc/lúc, CPU-bound, và `get_resources` cho thấy **2,6 CPU đã là trần của gói**. Tính năng này
   đổi **chỗ chờ**, không đổi tổng thời gian.
2. **"Ranh giới bản quyền"** — chủ dự án quyết định, và đã quyết (28-09).

Vì (1) vẫn đúng, **popup phải nói thẳng** *"Không nhanh hơn bấm từng trang"* thay vì để người dùng
tưởng nó tăng tốc.

### 4.2. Nhiều lớp phủ cùng lúc — và một chốt hiệu năng

Trước E59 chỉ có **một** lớp phủ, nhận theo `id`, và `vePhu` xoá lớp cũ ở dòng đầu. Bulk cần mỗi
trang giữ lớp của nó ⇒ chuyển sang `class` + `data-src`, chỉ xoá lớp của **chính ảnh đang vẽ lại**.
Giữ `id` cho đúng lớp mới nhất vì phần đo cuối quy trình một trang đọc `#translation-lop-phu`.

**Chốt hiệu năng là bắt buộc, không phải tối ưu sớm:** 24 trang = 24 lớp, mỗi lớp nghe `scroll` và
mỗi lần cuộn đều dựng lại toàn bộ ô chữ + chạy vòng co cỡ chữ. Lớp nào cách khung nhìn > 800px thì
ẩn và về ngay — chỉ 1-2 lớp quanh mắt đọc làm việc thật.

### 4.3. `chonMoiTrang` — dùng lại luật chất lượng, bỏ đúng một luật

Khác `chonTrangTruyen` ở **một** điều: không lọc theo khung nhìn. Dùng lại nguyên
`loaiDoChatLuong` (banner, icon, thumbnail, nền mờ lightbox) chứ không viết luật mới — docstring đầu
tệp đã chốt: hai bảng luật là sớm muộn lệch nhau.

Thêm **lọc trùng `src`**: lightbox dựng nền bằng chính ảnh đang xem, nên cùng một `src` có hai lần
trong DOM. Dịch hai lần một ảnh là tiêu hai lượt hạn mức cho một kết quả.

### 4.4. Dừng được, và dừng ĐÚNG CHỖ

| Điều kiện dừng | Vì sao |
|---|---|
| `429` hết hạn mức | Lỗi TOÀN CỤC — trang sau chắc chắn cũng bị. Đi tiếp là gửi thêm hàng chục request chắc chắn bị từ chối |
| `401` hết phiên | Cùng lý do |
| Nút **Dừng** | Một lượt quét chạy rất lâu và tiêu hạn mức; không có đường dừng thì cách duy nhất là đóng tab, mà đóng tab mất luôn mọi lớp phủ đã vẽ |
| Trần 200 trang / 60 nhịp cuộn | Trang cuộn vô tận không có điểm kết thúc tự nhiên |

Lỗi **lẻ** của một trang (`docByteAnh` hỏng, lỗi mạng) thì **đếm rồi đi tiếp** — một trang chống sao
chép không được làm chết cả lượt.

Vị trí cuộn được **trả về chỗ ban đầu** khi xong: bulk phải tự cuộn để nạp ảnh lười, và bỏ người
dùng ở cuối trang là bắt họ tự tìm lại chỗ đang đọc.

### 4.5. Cờ `__e59_bulk` — ĐỌC LÀ XOÁ

`executeScript` với `files:` không nhận đối số, nên popup đặt cờ qua `chrome.storage.local`. Content
script **xoá ngay khi đọc**; popup cũng xoá nếu tiêm thất bại. Để lại cờ thì lần bấm *"Dịch trang
này"* kế tiếp sẽ chạy nguyên cả chapter — tiêu hạn mức cho việc người dùng không yêu cầu.

### 4.6. Vá kèm: `doc()` của tiện ích làm mất `detail` dạng OBJECT

429 của hạn mức trả một object (`tran`, `reset_luc`, `chot`). `doc()` chỉ giữ chuỗi nên object rơi về
`res.statusText` ⇒ người dùng đọc đúng chữ **"Too Many Requests"**. Cùng lỗi bản web đã vá ở E53.

Nay `LoiApi` mang `chiTiet`, service worker chuyển tiếp, và thông báo nói được:

> *"DỪNG SỚM: hết lượt dịch hôm nay (trần 10), có lại lúc 00:00:00 29/9/2026."* ← **đo được trên
> production**

---

## 5. Kiểm trên trang thật

### 5.1. Chạy được, và hai đường quan trọng đều đúng

| Đo | Kết quả |
|---|---|
| Bulk trên tập 1 (ja) | *"Dịch cả chapter: xong 3 trang"*, 3 lớp phủ, hạn mức 2 → 5 |
| Thông báo tiến độ | *"Đang dịch trang 2… Xong 1 · lỗi 0 · còn thấy 4 trang. Cứ để tab này mở rồi làm việc khác."* |
| Đường **hết hạn mức** (tập 3, còn 2 lượt) | *"xong 2 trang … DỪNG SỚM: hết lượt dịch hôm nay (trần 10), có lại lúc 00:00 29/9"* |
| Vị trí cuộn sau khi xong | trả về `0` — đúng chỗ ban đầu |
| Console | **0 lỗi** |

### 5.2. Tôi CHẨN SAI một lần, và số đo bắt được

Lượt bulk đầu báo *"xong 3 trang"* trong khi tập 1 có **5 ảnh `ja_`** và còn **4790px chưa cuộn
tới**. Tôi kết luận "bỏ cuộc sau một nhịp cuộn" và vá `cuonDeNapThem`.

Đo lại sau khi vá: **vẫn 3 trang**. Cuộn cưỡng bức xuống đáy rồi đo từng ảnh:

```
E01P00.jpg   1200x287    ← banner tiêu đề, tỉ lệ 0,24 < 0,45 ⇒ loại ĐÚNG
E01P01.jpg   1200x1660   ← trang truyện
E01P02.jpg   1200x1660   ← trang truyện
E01P03.jpg   1200x1660   ← trang truyện
E01P04.jpg   1200x24     ← dải phân cách ⇒ loại ĐÚNG
```

⇒ Trang đó có **đúng 3 trang truyện thật**. `3` là đáp án đúng cả trước lẫn sau bản vá. **Tôi vá một
triệu chứng không tồn tại.**

Bản vá `cuonDeNapThem` vẫn giữ, nhưng vì lý do **khác** với lý do tôi đưa ra lúc vá: bỏ cuộc sau một
nhịp `0,85 × khung nhìn` (371px trên khung nhìn 437px) khi tài liệu cao 5227px là **logic sai** —
nó chỉ chưa gây hại trên trang cụ thể này. Không được ghi nó là "đã sửa lỗi mất trang".

### 5.3. Thời gian một trang: số cũ KHÔNG còn đúng, và tôi đã bỏ nó khỏi giao diện

Đo được: **2 trang trong ~8 giây**, và **3 trang trong 43 giây** — trái hẳn *~45 giây/trang* của
`REPORT_E19_0`. Kiểm `MINI_SPEC_E44` thì hướng hạ `ctd_input_size` đã **bị huỷ**, nên detect ONNX
không hề được tăng tốc.

Giải thích khả dĩ: production đặt **cả `DETECT_ENGINE` lẫn `DETECT_AI_MODEL`** (E46 — nhận diện
bong bóng bằng mô hình ngoài thay vì ONNX cục bộ). `list_env` của nền tảng **chỉ trả TÊN biến, không
trả giá trị**, nên tôi **chưa kết luận** — đã thêm `detect_engine` vào `/healthz` để biết chắc.

**ĐÃ XÁC NHẬN sau khi deploy:** `detect_engine: "ai_gemini"` và `translate_default_engine:
"llm_context"` ⇒ production chạy **cả hai bước qua Gemini**, mỗi trang **hai lượt gọi trả tiền**. E58
chỉ vá được nửa **dịch**; nửa **nhận diện** do biến toàn hệ thống, không có đường ghi đè theo trang.

Chủ dự án chốt (28-09) **giữ `ai_gemini`** — đổi tốc độ lấy tiền, có chủ đích. Kèm theo đó, popup của
tiện ích nay **đọc `/healthz` và nói thẳng bước nào đang tốn phí**: ô "Chất lượng dịch" chỉ chọn được
engine DỊCH, nên người chọn "Miễn phí" rất dễ tưởng cả lượt là miễn phí — và với nút "Dịch cả chapter"
thì hiểu nhầm đó nhân lên theo số trang. Đọc không được thì **ẩn dòng đó**, không đoán bừa "miễn phí".

⇒ Đã **bỏ con số "~45 giây"** khỏi popup và khỏi thông báo tiến độ. Giữ lại một số tôi không đo lại
được trên bản đang chạy là đúng loại lỗi cả lượt này đi sửa.

---

## 6. Changed Files

| Tệp | Sửa gì |
|---|---|
| `backend/app/api/v1/routes.py` | E58 — lưu thẳng `engine`, kể cả `google_fast` |
| `backend/app/main.py` | `/healthz` thêm `detect_engine` |
| `backend/tests/test_e58_…py` | MỚI — 7 bài, đo vào engine THẬT SỰ chạy |
| `backend/tests/test_e19_che_do_chi_chu.py` | Đảo một bài canh khẳng định sai (§3.4) |
| `extension-doc-truyen/src/lib/chon-anh.js` | `chonMoiTrang` |
| `extension-doc-truyen/src/lib/api.js` | `LoiApi.chiTiet` giữ `detail` dạng object |
| `extension-doc-truyen/src/service-worker.js` | Chuyển tiếp `chi_tiet` |
| `extension-doc-truyen/src/content/index.js` | Nhiều lớp phủ + chốt hiệu năng + `dichCaChapter` |
| `extension-doc-truyen/src/popup/*` | Nút *Dịch cả chapter* + câu nói thẳng về thời gian |
| `extension-doc-truyen/tests/chon-anh.test.js` | +5 bài |

Phiên bản tiện ích **0.1.12 → 0.1.15**. README của tiện ích chốt rằng mọi thông báo mang số phiên
bản, nên mỗi lượt sửa phải tăng số — không có nó thì không phân biệt được *"bản sửa không ăn thua"*
với *"bản sửa chưa tới máy"*.

---

## 7. Remaining Limits

* ~~E58 chưa kiểm trên production.~~ **ĐÃ kiểm** (28-09, sau khi nâng hạn mức lên 60 nên có lượt để
  chạy): gửi `engine=google_fast` ⇒ `/pages/{id}/translation` trả **`ENGINE = ['google_fast']`**, bản
  dịch đúng nghĩa (*"Chào buổi sáng, tên tôi là Tan…"* từ おはようございます / 俺の名前は田中だ). Cùng một
  yêu cầu, TRƯỚC bản vá cho ra `llm_context`.
* **Bước nhận diện vẫn tốn tiền**: `detect_engine = ai_gemini` (đã xác nhận), và chủ dự án chốt giữ
  nguyên. E58 chỉ vá nửa **dịch**. Muốn miễn phí hoàn toàn thì `DETECT_ENGINE=ctd`, đổi lại ~45s/trang.
  Popup của tiện ích nay nói ra điều này thay vì để người dùng tự đoán.
* ~~Hạn mức 10/ngày làm bulk gần như vô dụng.~~ Chủ dự án chốt **60** (28-09), đã đặt
  `HAN_MUC_CO_TAI_KHOAN=60`. ⚠️ Biến này **chưa từng có** trên production (đang chạy mặc định 10), nên
  đây là **cấp biến mới** — trên Vibe Host `set_env` không có lệnh xoá, sau này đổi giá trị được
  nhưng không gỡ được biến.
* **Chưa thử trên trang có DRM** (MangaPlus: ảnh `blob:`, chặn chuột phải). `docByteAnh` đọc bằng
  canvas ngay trong tab nên *có thể* chạy, nhưng chưa có số đo.
* **Chưa thử trên trang "bấm Tiếp"**: bulk chỉ thấy ảnh đã có trong DOM và chỉ cuộn được trong một
  trang. Trang phân trang thật sự thì mỗi lần bấm là một lượt bulk riêng.
* Trần 200 trang/lượt và 60 nhịp cuộn là **số đặt ra**, chưa hiệu chỉnh.
