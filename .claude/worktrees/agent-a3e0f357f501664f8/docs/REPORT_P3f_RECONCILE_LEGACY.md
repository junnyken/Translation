# Báo cáo Mini-Spec P3f — Đối chiếu bản ghi ↔ hiện vật

**Ngày:** 2026-08-31 · **Trạng thái:** ✅ **XONG — công cụ đã lên host, CHƯA chạy chế độ sửa**
**Phụ thuộc:** P3e `ĐÃ DEPLOY` · P3d · P3c

## Summary

P3e làm hiện vật **từ nay** bền. Nó **không** hồi sinh được ảnh đã mất — ảnh gốc mất rồi thì
không dựng lại được. Nên các trang cũ vẫn mang bản ghi khai "đã canh chữ xong" trong khi bấm vào
thì 404.

Đó đúng là thứ `CLAUDE.md §3` cấm: *không tự nhận "done" khi thiếu bằng chứng*. **Bản ghi là lời
khai; hiện vật là bằng chứng.** Mất bằng chứng thì phải rút lời khai.

P3f là công cụ rút lời khai đó — có chế độ chỉ-đếm, idempotent, và không đụng tới bản dịch.

## Design Choice

### Không xoá bản dịch, chỉ rút lời khai về ảnh

Bản dịch và kết quả canh chữ nằm trong CSDL nên **không mất**, và vẫn đúng. Chạy lại bước xoá chữ
sẽ sinh ảnh clean mới rồi dùng lại chính những bản dịch đó. Xoá chúng là phá hoại.

### Lùi tới mốc gần nhất còn bằng chứng, không lùi sạch

| Tình trạng | Lùi về | Vì sao |
|---|---|---|
| Mất ảnh clean, **còn** kết quả OCR | `ocr_done` | OCR ở trong CSDL, còn nguyên — bắt chạy lại là phí |
| Mất ảnh clean, còn vùng chữ nhưng chưa OCR | `detected` | |
| Mất ảnh clean, chưa có gì | `queued` | |
| **Còn** ảnh clean, mất ảnh xem thử | `translated` | Chỉ bước canh chữ phải chạy lại |
| Lần xuất khai `done` mà file không còn | `failed` + `error_log=artifact_lost:…` | |

Cố ý **không** đi qua `assert_transition`: đây là sửa chữa, không phải một bước của pipeline. Máy
trạng thái mô tả đường **đi tới**; nó không có đường lùi vì bình thường không được lùi.

### Một cái bẫy đã tránh: `png_single` lưu output_path là THƯ MỤC

`storage.exists()` luôn trả `False` với một thư mục ở **cả hai** backend. Hỏi mỗi `exists()` thì
**mọi lần xuất PNG đều bị kết oan là đã mất file**. `_co_hien_vat()` hỏi thêm `list_prefix()`.
Có test riêng cho đúng ca này.

### Chạy nó trên host bằng cách nào

Nền tảng **không cho chạy lệnh trong container** (bộ công cụ chỉ có read/deploy/env/runtime).
Nên: gắn vào `deploy-start.sh`, bật bằng biến `RECONCILE_LEGACY`:

```
off (mặc định)  ·  report = chỉ đếm + ghi log  ·  apply = sửa thật
```

Khác migration ở một điểm quan trọng: **lỗi ở đây KHÔNG chặn khởi động**. Migration hỏng thì
schema sai, chạy tiếp là hỏng dữ liệu. Đối chiếu hỏng thì chỉ là chưa dọn được — không đáng để
hạ cả website.

Không làm thành endpoint HTTP: hệ thống **chưa có auth**, thêm một endpoint sửa dữ liệu hàng
loạt vào mặt tiền công khai là mở một cửa không ai canh.

## Changed Files

| Tệp | Việc |
|---|---|
| `app/services/reconcile.py` | **Mới** — `doi_chieu_hien_vat(session, storage, ap_dung=…)` |
| `app/scripts/doi_chieu_hien_vat.py` | **Mới** — điểm chạy CLI, mặc định chỉ đếm |
| `backend/deploy-start.sh` | Nhánh `RECONCILE_LEGACY` sau migration |
| `tests/test_reconcile_integration.py` | **Mới** — 8 test |

## Tests

```
831 passed, 6 skipped      (nền trước P3f: 823)
```

Test gắt nhất **không** phải "có sửa được không" mà là **chế độ chỉ-đếm tuyệt đối không ghi gì**
(`test_che_do_chi_dem_KHONG_ghi_mot_chu_nao`). Một công cụ sửa dữ liệu mà lỡ ghi trong lúc người
ta tưởng nó chỉ đang đếm thì tệ hơn hẳn việc không có công cụ nào.

Cùng hạng: `test_khong_dung_toi_trang_con_du_hien_vat` — trang lành lặn phải được để yên.

## Live Verification — chế độ `report` đã chạy thật trên host

`RECONCILE_LEGACY=report` + deploy. Log khởi động 2026-08-31 03:59:17:

```
đối chiếu hiện vật (chỉ đếm): 5 trang mất ảnh clean, 5 trang mất ảnh xem thử, 0 lần xuất mất file
```

**Thiệt hại thật: 5 trang.** Toàn bộ đều `typeset_done -> ocr_done` (còn kết quả OCR trong CSDL).
Không có lần xuất nào mất file.

### Chế độ `report` đã đếm sai — và tự nó lộ ra

Năm ID trang xuất hiện ở **cả hai** danh sách. Nguyên nhân: bước 2 bỏ qua trang đã xử ở bước 1
bằng cách nhìn `clean_image_path is None` — nhưng chế độ chỉ-đếm **không ghi gì**, nên cột đó
vẫn còn giá trị cũ và cùng một trang bị đếm hai lần. Báo cáo nói 10 trong khi thiệt hại thật là 5.

Đã sửa bằng một tập `da_xu_ly` (không dựa vào tác dụng phụ của việc ghi), kèm test hồi quy
`test_che_do_chi_dem_KHONG_dem_mot_trang_hai_lan` — khẳng định chế độ chỉ-đếm và chế độ sửa cho
ra **cùng** con số.

Bài học: **chế độ khô (dry-run) mà dựa vào tác dụng phụ của chế độ ướt thì sẽ nói dối** — và nó
nói dối đúng lúc người ta cần tin nó nhất.

### Chế độ `apply` — đã chạy, kết quả kiểm bằng DỮ LIỆU chứ không bằng log

Cả 5 trang nay ở đúng trạng thái mong muốn (đo qua API, từng trang một):

```
1e3cfe17  status=ocr_done  clean=None
a8613fe9  status=ocr_done  clean=None
891aec15  status=ocr_done  clean=None
4b955242  status=ocr_done  clean=None
460fe90a  status=ocr_done  clean=None
```

Bản dịch và kết quả OCR **còn nguyên** — chỉ lời khai về ảnh bị rút. Chạy lại bước xoá chữ là
dùng lại được ngay.

⚠️ **Một khoảng trống trong bằng chứng, nói thẳng:** tôi **không có log** của chính lượt sửa đó.
Nhật ký chạy **không sống sót qua một lần triển khai lại** — lượt `apply` tôi đọc được (04:13:22)
đã báo `0/0/0`, tức lúc nó chạy thì 5 trang **đã được sửa từ trước** bởi một lượt khởi động mà
log đã bị lần deploy sau ghi đè.

Nên bằng chứng ở đây là **trạng thái dữ liệu**, không phải nhật ký. Với việc này thì dữ liệu là
bằng chứng mạnh hơn — nhưng phải nói rõ để không ai tưởng tôi đọc được log của lượt sửa.

**Bài học vận hành:** nhật ký chạy trên nền tảng này là *phù du*. Việc gì cần dấu vết kiểm toán
thì phải ghi vào CSDL, không được trông vào log.

## Remaining Limits

- ~~Chưa chạy `apply`~~ → **đã chạy, đã kiểm bằng dữ liệu**: 5 trang về `ocr_done` + `clean=None`.
- **Không có nhật ký của chính lượt sửa** (log không sống sót qua deploy). Việc cần dấu vết kiểm
  toán về sau phải ghi vào CSDL chứ không trông vào log.
- `RECONCILE_LEGACY` đã đặt lại **`off`** — không để một thao tác ghi hàng loạt ở trạng thái đã
  lên nòng.
- Không hồi sinh được ảnh đã mất — P3f chỉ làm bản ghi thôi nói dối, không tạo lại dữ liệu.
- Quét toàn bảng, không phân trang. Ở quy mô hiện tại (vài chục trang) không đáng bận; vài chục
  nghìn trang thì phải làm theo lô.
- Không tự chạy định kỳ — phải bật bằng biến môi trường rồi triển khai lại.
