# REPORT E57b — Hiệu chỉnh ngưỡng nhận dạng ngôn ngữ trên DỮ LIỆU THẬT

**Ngày:** 2026-09-27 · **Nguồn yêu cầu:** chủ dự án — *"vậy hiệu chỉnh theo hành vi thật đi"* và *"E57 bạn có thể tự test đó không"*

---

## 1. Summary

`REPORT_E57.md` §9 tự ghi hai giới hạn: ngưỡng là **số đặt ra** và **chưa chạy trên trang truyện
thật**. Lượt này đóng cả hai.

Kết quả: **37/37 trang đúng** sau khi vá **một lỗi thật mà dữ liệu bắt được**. Trước khi vá là 36/37.

---

## 2. Dữ liệu — và cách lấy được mẫu ja/zh mà repo không có

Repo đã có 65 mẫu có nhãn, nhưng **tất cả là `en`** ⇒ không đo được ngưỡng kana, cũng không đo được
chiều ja↔zh, đúng hai chỗ chọn sai gây hại nhất (manga-ocr và PaddleOCR là hai model khác hẳn).
`test_fixtures/external/mangaplus_private/` **rỗng**, và tôi không tải manga có bản quyền.

Lối ra: **Pepper&Carrot có bản dịch tiếng Nhật và tiếng Trung** của đúng những trang dự án đã dùng cho
Run C — truyện tranh vẽ tay thật, chữ đặt tay thật, **CC BY-SA 4.0** (David Revoy, peppercarrot.com),
cùng nguồn `NGUON.md` đã chọn và vì cùng lý do: giấy phép cho phép nên số đo công bố được.

| Bộ | Số | Nhãn | Là gì |
|---|---|---|---|
| `ocr_benchmark` | 45 | `en` | 6 crop manga thật + 39 crop phông cách điệu / in hoa / nghiêng / SFX / xoay / **làm nhiễu** |
| `ocr_benchmark_e20b` | 20 | `en` | Chữ mảnh & đậm trên **nền rối** |
| `pepper_carrot_cjk` (MỚI) | 28 | `ja` 17, `zh` 11 | **Trang truyện đầy đủ**, 1200×1660, chữ Nhật/Trung thật |

Tổng **93 mẫu**, gom thành **37 "trang"** — trang là đơn vị production thật sự phân loại (một lượt
`doc_toan_anh()` cho cả trang), nên đo theo crop rời sẽ cho kết luận sai lệch.

### 2.1. Ba bẫy khi lấy dữ liệu, cả ba đều bắt được việc

**Mã ngôn ngữ của tiếng Trung là `cn`, KHÔNG phải `zh`.** `https://…/zh/webcomic/ep01…` trả HTTP
**200** — nhưng ảnh trong đó mang tiền tố `en_`, tức trang **chưa dịch** và site lùi về bản tiếng Anh.
Tin "200 = có bản dịch" là tải ảnh **tiếng Anh** về rồi dán nhãn **"tiếng Trung"**: một tập dữ liệu
BỊA, và mọi số đo sau đó vô nghĩa — tệ hơn là không đo. ⇒ script chỉ nhận ảnh mang **đúng tiền tố của
ngôn ngữ đang xin**.

**Soft-404.** peppercarrot.com trả 200 kèm một trang HTML cho mọi URL sai (bẫy này `REPORT_E23` đã
ghi). ⇒ kiểm **magic byte** + **mở được bằng PIL**. Bắt được một tệp thật: `1200x24` — một dải phân
cách, không phải trang.

**"Không kiểm được" phải là lỗi DỪNG.** Lượt tải của E23 kiểm bằng `file --mime-type`, mà `file` không
có trong máy này ⇒ phép kiểm luôn thất bại ⇒ script **xoá sạch 18 ảnh thật vừa tải**. Nên ở đây chỉ
dùng thứ chắc chắn có (`PIL`), và nếu không import được thì **dừng, không tải, không xoá gì**.

---

## 3. Kết quả — hai điều dữ liệu nói mà suy luận không nói được

### 3.1. Thứ tự kana-trước-Hán: từ suy luận thành SỐ ĐO

`REPORT_E57.md` §3.1 lập luận rằng phải xét kana trước, vì trang Nhật đầy kanji. Nay có số:

| Trang tiếng Nhật THẬT | Hán / tổng | Tỉ lệ |
|---|---|---|
| E03P05 | 13/37 | **35,1%** |
| E03P06 | 12/42 | **28,6%** |
| E03P07 | 23/89 | **25,8%** |
| E03P04 | 10/41 | **24,4%** |
| E03P02 | 36/160 | **22,5%** |
| E03P01 | 13/64 | **20,3%** |

**Sáu trong mười bảy** trang tiếng Nhật thật vượt ngưỡng tiếng Trung (20%). Đảo thứ tự xét là gán cả
sáu thành `zh` ⇒ dùng PaddleOCR thay manga-ocr: chữ vẫn ra, vẫn dịch, **không lỗi nào hiện**, chỉ là
kém hơn hẳn.

Sáu trang này đã thành bài test có tham số, kèm số đo trong chú thích.

### 3.2. Lỗi THẬT: tỉ lệ một mình không đủ

Lượt sai duy nhất: `cn_…E03P08` → kết luận **`en`**.

```
cn_…E03P08 (trang ghi công cuối chương)   han=121  latin=1097  tong=1218  →  Hán 9,9%  ⇒ en  ✗
ja_…E03P08 (cùng trang, bản tiếng Nhật)   kana=109 latin=1099  tong=1248  →            ⇒ ja  ✓
```

Hai trang **cùng một trang**, cùng bị chữ Latin áp đảo (tên người, URL, giấy phép). Bản Nhật đúng
**chỉ vì ngưỡng kana đếm số TUYỆT ĐỐI** (`kana >= 2`), còn Hán thì chỉ có ngưỡng **tỉ lệ**.

**Bài học thành luật:** một hệ chữ có mặt **hàng trăm** ký tự thì nó *có* mặt, bất kể bị bao nhiêu chữ
Latin làm loãng. Tỉ lệ một mình không diễn tả được điều đó.

### 3.3. Bản vá: thêm ngưỡng TUYỆT ĐỐI cho chữ Hán

```python
if ti_le_han >= TI_LE_HAN_TOI_THIEU or bc.han >= SO_HAN_TOI_THIEU:   # hoặc-thì
```

`SO_HAN_TOI_THIEU = 8`, và con số đó nằm giữa hai phép đo:

* trang tiếng Trung thật **ít Hán nhất** có **10** chữ Hán;
* **mọi** trang tiếng Anh đo được có **0** chữ Hán — cả 9 nhóm, gồm nhóm làm nhiễu, nền rối, chữ mảnh
  nghiêng.

Lệch về phía an toàn cho tiếng Anh: cần **8 chữ Hán rác** trên một trang Latin mới misfire, mà số đo
được là 0.

---

## 4. Ngưỡng nào KHÔNG cần đổi — và số đo nói vì sao

| Ngưỡng | Giữ | Biên thật đo được |
|---|---|---|
| `SO_KY_TU_TOI_THIEU = 8` | ✔ | Trang thật **ít chữ nhất**: `zh` 10 ký tự, `ja` 12. Nâng lên 15 là làm hai trang thật này thành "không kết luận" |
| `SO_KANA_TOI_THIEU = 2` | ✔ | **11/11** trang tiếng Trung thật có **0 kana**; trang Nhật thật ít kana nhất có **3**. Ngưỡng 2 nằm đúng giữa — tín hiệu kana **sạch tuyệt đối** trên dữ liệu thật |
| `TI_LE_HAN_TOI_THIEU = 0.20` | ✔ | Tiếng Anh đo được **0,0% ở tất cả 9 nhóm** ⇒ 20% thừa rất xa so với biên thật. Không phải chỗ cần siết |
| `TI_LE_LATIN_TOI_THIEU = 0.60` | ✔ | Không có lượt sai nào ở nhánh này sau khi vá §3.3 |

⇒ Lượt hiệu chỉnh này **đổi đúng một ngưỡng**, và vì một lỗi đo được — không phải vặn số cho đẹp bảng.

---

## 5. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/services/nhan_dang_ngon_ngu.py` | `SO_HAN_TOI_THIEU = 8` + nhánh hoặc-thì; mọi hằng số nay có số đo trong chú thích |
| `app/services/ocr_benchmark/hieu_chinh_nhan_dang.py` | MỚI — phép đo, chạy lại được |
| `app/services/ocr_benchmark/tai_pepper_carrot_cjk.py` | MỚI — tải bộ ja/zh, kèm ba lớp chống bẫy §2.1 |
| `tests/test_e57_phan_loai_ngon_ngu.py` | +12 bài, số lấy từ phép đo thật |

Ảnh **không** vào repo (`.gitignore: backend/test_fixtures/external/`). Script tải nằm ở
`app/services/ocr_benchmark/` chứ không cạnh ảnh — để ở đó là để công thức tái lập biến mất theo.

---

## 6. Tests

`test_e57_phan_loai_ngon_ngu.py` nay **28 bài**. Bảy bài mới neo vào số đo thật:

| Bài | Neo vào |
|---|---|
| `test_trang_Nhat_THAT_co_ti_le_Han_vuot_nguong_van_ra_ja` | 6 trang thật, tham số là 3 ô đo được |
| `test_trang_ghi_cong_tieng_Trung_KHONG_bi_ket_luan_thanh_tieng_Anh` | Chính lượt sai duy nhất |
| `test_trang_ghi_cong_tieng_Nhat_van_ra_ja_du_bi_Latin_ap_dao` | Đối chứng cặp |
| `test_trang_tieng_Anh_THAT_do_duoc_0_chu_Han` | Biên 0% của 9 nhóm |
| `test_it_hon_nguong_tuyet_doi_va_duoi_ti_le_thi_KHONG_thanh_tieng_Trung` | Đối chứng âm cho nhánh mới |
| `test_trang_THAT_it_chu_nhat_van_ket_luan_duoc` | 10 và 12 ký tự |
| `test_moi_trang_Trung_THAT_deu_co_0_kana` | 0 vs 3 |

**Một lỗi của tôi, do chính bài test bắt:** hai dòng tham số không cộng khớp (23+54+10 = 87, tôi ghi
89). Trang thật có vài ký tự rơi vào ô `chu_cai_khac`. Tôi **không nhồi thêm cho khớp** — bỏ cột tổng
và ghi rõ trong chú thích rằng ví dụ dựng lại chỉ gồm ba ô đo được, nên nó **nghiêm hơn** trang thật
một chút (phần thiếu chỉ làm loãng tỉ lệ Hán). Một `assert` tự kiểm trong bài test là thứ bắt được.

---

## 7. Remaining Limits

* **Không có mẫu manga Nhật/Trung thật** (kiểu scan, phông cách điệu, **chữ dọc**, screentone).
  Pepper&Carrot là truyện tranh châu Âu dịch sang Nhật/Trung: bong bóng kiểu phương Tây, chữ **ngang**,
  phông đều. Nên §3.1 chứng minh được *thứ tự xét*, **không** chứng minh được độ bền trên manga scan.
* **Chưa đo chữ DỌC.** Nếu có trang manga chữ dọc thật thì đó cũng là dữ liệu mà E16 (nửa dọc) đang
  thiếu — một lượt tải giải quyết được hai việc.
* Bộ `zh` chỉ **11 trang** (ep02 bản `cn` tải lỗi mạng, chưa thử lại) và đều từ **2 tập**. Đủ để bắt
  một lỗi thật, **không** đủ để gọi là phân phối đại diện.
* Ngưỡng `TI_LE_LATIN_TOI_THIEU` chưa có lượt sai nào chạm tới, nên nó **chưa được kiểm thật sự** —
  đúng là "không có bằng chứng phản đối", không phải "đã chứng minh".
