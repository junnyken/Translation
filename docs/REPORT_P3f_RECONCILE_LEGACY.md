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

## Live Verification

Công cụ **đã lên host** cùng lần deploy này, nhưng **chưa chạy chế độ `apply`** — còn phải chạy
`report` trước để nhìn thiệt hại, rồi mới quyết.

## Remaining Limits

- **Chưa chạy `apply` trên host.** Số liệu thiệt hại thật chưa có.
- Không hồi sinh được ảnh đã mất — P3f chỉ làm bản ghi thôi nói dối, không tạo lại dữ liệu.
- Quét toàn bảng, không phân trang. Ở quy mô hiện tại (vài chục trang) không đáng bận; vài chục
  nghìn trang thì phải làm theo lô.
- Không tự chạy định kỳ — phải bật bằng biến môi trường rồi triển khai lại.
