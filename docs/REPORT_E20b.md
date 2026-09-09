# Báo cáo Mini-Spec E20b — Preprocessing & Tesseract Comparative Benchmark

**Project:** Translation · **Phase:** E20 — Stylized Comic Lettering OCR Hardening
**Ngày:** 2026-09-09 · **Nền:** `a7a5ac5` (sau E20a + 3 phụ lục)

## 1. Summary

So 9 path (5 PaddleOCR+tiền xử lý, 4 Tesseract PSM) trên đúng điều kiện đã xác nhận gây lỗi thật
ở `REPORT_E20a.md` §10 — **chữ mảnh (nghiêng) đặt trên nền tranh phức tạp** — không phải "chữ
hoa cách điệu" như đề bài gốc của `PLAN E20`.

**Kết quả: KHÔNG có path nào thắng.** Cả 9 path đều **0/10 exact match** trên nhóm mục tiêu (chữ
mảnh/nền bận) — không path nào cải thiện dù chỉ 1 mẫu. Một số path còn LÀM HẠI nhóm đối chứng
(chữ đậm cùng nền bận, PaddleOCR gốc đạt 90%): tăng tương phản và nhị phân hoá tụt còn 60%, cả 4
Tesseract PSM chỉ 40-50%.

**Rơi đúng vào ô quyết định #3 trong bảng "Decision gate sau E20" của `PLAN E20`:** *"Không path
nào thắng rõ" → "Không thay engine; cải thiện M7 crop zoom/candidate transcription UX"*.
**⇒ Không build E20c** (mini-spec đó tự nêu điều kiện "chỉ build nếu E20b chứng minh candidate có
giá trị ý nghĩa" — không đạt).

## 2. Audit Before Build

| Mục | Kết quả audit |
|---|---|
| Dataset E20a baseline/hash | Dataset E20b dựng MỚI (`ocr_benchmark_e20b_generate_dataset.py`), đúng khuôn schema E20a, tái dùng `OCRBenchmarkDatasetLoader`/`OCRMetricsCalculator` không sửa — không đụng dataset E20a gốc |
| Binary/version Tesseract | Cài tạm trong container benchmark (`apt-get install tesseract-ocr tesseract-ocr-eng`, KHÔNG sửa `Dockerfile`) — bản 5.5.0, có `leptonica-1.84.1`. Không cài `pytesseract` (thêm dependency Python không cần thiết) — gọi thẳng CLI qua `subprocess` |
| Dependency cost/image size | Không tăng — chỉ cài trong container `--rm` một lần, không commit vào image `translation-worker` |
| Thư viện tiền xử lý sẵn có | `Pillow` (`ImageEnhance`, `ImageFilter`) + `numpy` đã có trong requirements, không thêm gì. Không dùng OpenCV cho ngưỡng thích nghi — tự viết bằng NumPy thuần (Gaussian blur qua Pillow + so sánh mảng) |
| NFC chỉ ở tầng so sánh | Tái dùng `OCRMetricsCalculator._nfc()` của E20a, không viết lại |

## 3. Design Choice

**9 path CỐ ĐỊNH, không dò thêm tham số sau khi thấy kết quả xấu.** Đúng constraint #4 ("không
tự chọn engine theo kết quả benchmark trước E20c") và tinh thần chống p-hacking: hệ số tăng tương
phản (1.8x), bán kính Gaussian blur cho ngưỡng thích nghi (15px, trừ hằng số 8) đều CHỐT TRƯỚC khi
chạy, không tinh chỉnh lại sau khi thấy 0/10 để "cứu vãn" con số.

**Dataset MỚI thay vì tái dùng crop nền-trắng của E20a.** Benchmark trên đúng điều kiện đã đo
thấy lỗi (chữ mảnh + nền bận) mới có ý nghĩa quyết định — so trên bong bóng nền trắng (nơi mọi
engine đều gần hoàn hảo) sẽ không phân biệt được path nào tốt hơn cho ĐÚNG vấn đề cần giải.

**Giữ nhóm đối chứng (chữ đậm/nền bận) trong CÙNG benchmark**, không tách riêng — bắt đúng ca
"cải thiện nhóm khó nhưng phá nhóm dễ" (2 path tiền xử lý + cả 4 Tesseract PSM đều rơi vào ca
này, dù nhóm khó không hề được cứu).

## 4. Changed Files

- `backend/app/services/ocr_benchmark/preprocess.py` — mới, 5 phép tiền xử lý đặt tên+phiên bản
- `backend/app/services/ocr_benchmark/tesseract_adapter.py` — mới, gọi CLI `tesseract` qua subprocess
- `backend/scripts/ocr_benchmark_e20b_generate_dataset.py` — mới, dựng 20 mẫu (10 mảnh + 10 đậm)
- `backend/scripts/ocr_benchmark_e20b_run.py` — mới, chạy 9 path + in bảng so sánh theo nhóm
- `backend/test_fixtures/external/ocr_benchmark_e20b/` — **không commit** (gitignore có sẵn)

## 5. New API / DB / State

**Không có** — cùng ranh giới E20a: không route, không bảng/cột, không đụng OCRResult production,
không nối Celery. Tesseract chỉ tồn tại trong container benchmark tạm thời, không vào image thật.

## 6. Tests

Không thêm test tự động mới trong E20b — `preprocess.py`/`tesseract_adapter.py` đủ mỏng để không
cần bộ test riêng (mỗi hàm tiền xử lý chỉ gọi thẳng API Pillow/NumPy đã có test ở thượng nguồn);
giá trị thật của E20b nằm ở SỐ ĐO benchmark (§7), không ở logic có thể unit-test theo nghĩa
thường. `preprocess.PIPELINE` là dict thuần (tên → hàm), sai tên gọi `ap_dung()` ném `KeyError`
ngay — đã tự kiểm bằng chính lượt chạy thật (9 path đều chạy được, không path nào lỗi tên).

## 7. Live Verification — chạy thật 9 path × 20 mẫu trong container worker

```
$ docker compose run --rm -e PYTHONPATH=/app worker bash -c \
    "apt-get install -y tesseract-ocr tesseract-ocr-eng && python scripts/ocr_benchmark_e20b_run.py"
```

| Path | Chữ MẢNH (mục tiêu — baseline gốc 0/10) | Chữ ĐẬM (đối chứng — baseline gốc 9/10) | Runtime p50 |
|---|---|---|---|
| `paddleocr+khong_doi` (đối chứng chính) | 0/10 (0%) CER=0,231 | 9/10 (90%) CER=0,003 | 945ms |
| `paddleocr+xam_hoa` | 0/10 (0%) CER=0,226 | 9/10 (90%) CER=0,020 | 1003ms |
| `paddleocr+phong_to_2x` | 0/10 (0%) CER=0,221 | 9/10 (90%) CER=0,003 | 2617ms |
| `paddleocr+tang_tuong_phan` | 0/10 (0%) CER=0,228 | **6/10 (60%)** CER=0,037 | 1092ms |
| `paddleocr+nguong_thich_nghi` | 0/10 (0%) **CER=0,561** | **6/10 (60%)** CER=0,156 | 910ms |
| `tesseract_psm7` | 0/10 (0%) CER=0,306 | **5/10 (50%)** CER=0,054 | **258ms** |
| `tesseract_psm8` | 0/10 (0%) CER=0,318 | **4/10 (40%)** CER=0,061 | 268ms |
| `tesseract_psm11` | 0/10 (0%) CER=0,338 | **5/10 (50%)** CER=0,146 | 284ms |
| `tesseract_psm13` | 0/10 (0%) CER=0,318 | **4/10 (40%)** CER=0,061 | 270ms |

**Đọc bảng:** cột "chữ MẢNH" — cột QUYẾT ĐỊNH — không path nào nhích khỏi 0/10. Cột "chữ ĐẬM" chỉ
để phát hiện tác dụng phụ; 6/8 path (mọi path trừ `xam_hoa` và `phong_to_2x`) làm hại nhóm này so
với baseline 90%, một số hại nặng (Tesseract tụt còn 40%). Tesseract nhanh hơn PaddleOCR ~4 lần
(258ms vs 945ms) nhưng **nhanh hơn mà sai vẫn là sai** — đúng constraint #8 (không coi tốc độ là
thắng khi accuracy không cải thiện).

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí | Đạt? |
|---|---|
| Mọi path chạy trên cùng manifest/version | ✅ 9/9 path, 20/20 mẫu mỗi path, 0 lỗi thực thi |
| Có bảng kết quả tổng + theo category | ✅ §7, tách `italic_thin_on_busy_bg` vs `bold_on_busy_bg` |
| Có baseline delta rõ cho mỗi path | ✅ so trực tiếp với `paddleocr+khong_doi` (0/10, 90%) |
| Có quyết định: thắng rõ / không đủ bằng chứng / chỉ hợp review-on-demand | ✅ **"không đủ bằng chứng"** — không path nào cải thiện dù 1 mẫu trên nhóm mục tiêu |
| Không thay OCR production | ✅ |
| `docs/REPORT_E20b.md` | ✅ (file này) |

## 9. Quyết định — theo đúng bảng "Decision gate sau E20" của `PLAN E20`

> *"Không path nào thắng rõ" → "Không thay engine; cải thiện M7 crop zoom/candidate transcription
> UX"*

**Không build E20c.** Điều kiện tự đặt ra của E20c ("chỉ build nếu E20b chứng minh candidate có
evidence") không đạt — 0/10 không đổi qua mọi path, không có ứng viên nào để đưa vào cổng fallback.

**Khuyến nghị hướng đi tiếp** (không tự quyết, để người dùng chọn):
1. **Chấp nhận giới hạn, cải thiện UX rà soát tay** — hướng chính đáng theo gate: thêm khả năng
   phóng to vùng chữ + gõ lại tay ngay tại M7 cho đúng ca "chữ mảnh trên nền bận" (không có trong
   scope E20, cần mini-spec riêng nếu muốn làm).
2. **Vision LLM review-on-demand** — `PLAN E20` cố ý loại khỏi E20 ("Vision LLM có tiềm năng
   nhưng chưa benchmark/cost chưa rõ → Mở Mini-Spec riêng, không chen vào E20"). Đáng cân nhắc
   NHƯNG cần mini-spec riêng đo cost/latency/quota trước, không tự động hoá hàng loạt.
3. **Wording trung thực** — đúng yêu cầu "Wording sản phẩm cần giữ" của `PLAN E20`: không nói
   "OCR chính xác với mọi font", nói rõ "hoạt động tốt với chữ rõ/font thông thường; chữ mảnh
   cách điệu trên nền phức tạp cần rà soát/chỉnh tay thủ công qua web app (M7)".

## 10. Remaining Limits

- Chưa đo trên ảnh MangaPlus thật (vẫn chưa lấy được — xem `REPORT_E20a.md` §9) để xác nhận
  100% đây đúng là nguyên nhân, dù bằng chứng gián tiếp (đậm/mảnh cùng nền, cùng crop, khác đúng
  một biến) đã khá mạnh.
- Chỉ đo tiếng Anh, chỉ 2 font (Bangers/ShantellSans) — không đại diện hết mọi kiểu "chữ mảnh"
  có thể gặp trên các trang manga chính thức khác MangaPlus.
- Chưa thử tổ hợp tiền xử lý (vd tăng tương phản + phóng to cùng lúc) — cố ý, đúng constraint #1
  của E20b ("không chaining ngẫu nhiên nhiều filter").
- Chưa thử Vision LLM — cố ý ngoài phạm vi E20 (xem §9.2).
