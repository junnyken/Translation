# Báo cáo Mini-Spec E20a — OCR Benchmark Dataset & Ground Truth Harness

**Project:** Translation · **Phase:** E20 — Stylized Comic Lettering OCR Hardening
**Ngày:** 2026-09-08 · **Nền:** `0570aac` (v0.1.12, sau các bản sửa E19)

## 1. Summary

Dựng bộ benchmark 45 crop (6 thật từ Pepper&Carrot CC BY-SA + 39 tự tạo bằng font OFL có sẵn
trong `backend/fonts/`, câu tự viết), harness đo CER/WER/exact-match/missing-character/
missing-line/empty-output/runtime, chạy PaddleOCR baseline thật (đúng adapter M3, qua
`docker compose run worker`) trên toàn bộ 45 mẫu.

**Kết quả buộc phải sửa lại chính giả thuyết đã đặt ra `PHASE E20`:** nhóm "chữ HOA sát nét"
(font Bangers — mô phỏng đúng kiểu lettering đã gây lỗi thật trên MangaPlus) đạt **100% exact
match, CER = 0**. PaddleOCR baseline **không hề yếu** với chữ hoa/cách điệu/nghiêng khi ảnh đầu
vào sạch. Nhóm DUY NHẤT có sai số đáng kể là ảnh bị làm nhiễu/mờ/cắt cạnh (`noisy_partial`,
40% exact match) — tức đầu mối thật nhiều khả năng nằm ở **chất lượng ảnh/độ phân giải crop
thật** (hoặc lỗi cắt vùng ở bước nhận diện M2), không phải "PaddleOCR không đọc được font
truyện tranh". Xem §7.

**36/36 test tự động qua** (`test_ocr_benchmark_unit.py`, không phụ thuộc dataset gitignore).
Không đụng DB, không đụng `OCRResult` production, không nối vào Celery.

**Cập nhật 08/09 (§10):** đo thêm 2 thí nghiệm không cần ảnh MangaPlus thật. Độ phân giải thấp
(tới 20px) cũng KHÔNG đủ giải thích lỗi thật. Nhưng **chữ mảnh (nghiêng) đặt trên nền tranh phức
tạp thì hỏng 0/10**, đúng một mẫu hình: mất ký tự ở HAI ĐẦU, giữa luôn đúng — dấu hiệu bước dò
vùng chữ NỘI BỘ của PaddleOCR (không phải M2) vẽ hụt biên trên nền bận. Đây là giả thuyết đáng
tin nhất hiện có, và gợi ý hướng sửa rẻ hơn nhiều so với đổi engine: nới lề quanh bbox trước khi
OCR. Xem §10 để biết chi tiết đầy đủ.

## 2. Audit Before Build

| Mục | Kết quả audit |
|---|---|
| M3 `PaddleOCREngine` adapter | Đọc `app/services/ocr/engines.py`: `recognize(image_path, bbox)` nhận bbox rồi tự `crop_region` — benchmark tái dùng ĐÚNG hàm này (truyền bbox = nguyên cả ảnh crop `(0,0,w,h)`), không viết lại lời gọi PaddleOCR riêng |
| M2 `crop_region`/`bbox_to_pixel_box` | `app/services/ocr/crop.py`: crop KHÔNG nới lề. Benchmark dùng cùng chính sách — 6 crop thật cũng cắt sát, không nới lề tay |
| License test fixture | `test_fixtures/external/NGUON.md` xác nhận Pepper&Carrot CC BY-SA 4.0, đã dùng cho E14/Run C trước đây |
| Nơi lưu mẫu private | `test_fixtures/external/` đã bị `.gitignore` từ trước (dòng 14, không có `/` đầu nên áp cả `backend/test_fixtures/external/`) — không cần sửa `.gitignore` |
| Unicode NFC | `metrics.py` chuẩn hoá NFC CHỈ lúc so sánh (`_nfc()`), không sửa `ground_truth`/`predicted_text` gốc trong `KetQuaMotMau` |
| Benchmark harness đã tồn tại? | Không — `grep` không thấy `ocr_benchmark` nào trước E20a |

## 3. Design Choice

**Manifest JSONL local, không đụng DB.** Đúng theo mini-spec — tách hẳn dữ liệu benchmark khỏi
dữ liệu chapter thật, không cần migration, không rủi ro lẫn dữ liệu test vào production.

**Vừa ảnh thật vừa ảnh tự tạo, có ghi rõ nguồn từng mẫu.** 3 trang Pepper&Carrot có sẵn trong
repo chỉ cho ra 5 bong bóng thoại + 1 SFX thật — không đủ phủ các nhóm khó (chữ HOA sát nét,
nghiêng, SFX thêm, khung tường thuật, ảnh nhiễu). Dùng font OFL sẵn có (`Bangers`, `ShantellSans`,
`SigmarOne`, `Mansalva` — đã là whitelist font M6, không phải thêm dependency mới) + câu tự viết
để tự tạo 39 mẫu còn lại. Ground truth vì vậy **chắc chắn đúng 100%** cho phần tự tạo (là chính
text đã chọn render, không phải chép tay từ ảnh) — mạnh hơn yêu cầu tối thiểu "ground truth nhập
thủ công" của mini-spec.

**Suy biến có tham số, ghi lại trong `notes`.** Nhóm `noisy_partial` lấy lại 5 mẫu cách điệu ở
trên rồi áp `GaussianBlur`/nhiễu Gaussian trên kênh màu/cắt cạnh — tham số cụ thể ghi trong
`notes` từng mẫu để tái lập được, không phải "làm cho xấu đi" mơ hồ.

**Chạy suy luận THẬT trong container worker, không cài lại PaddleOCR ở `.venv` cục bộ.** `.venv`
API không có `paddleocr` (import trễ có chủ đích ở M3). Thay vì cài thêm một bản có thể lệch
version, script `ocr_benchmark_run.py` chạy bằng `docker compose run --rm worker` — dùng ĐÚNG
image/version production, mount `../backend:/app` sẵn nên không cần rebuild.

## 4. Changed Files

- `backend/app/services/ocr_benchmark/__init__.py`, `dataset.py`, `metrics.py`, `runner.py` — mới
- `backend/scripts/ocr_benchmark_generate_dataset.py` — mới, dựng 45 mẫu + manifest
- `backend/scripts/ocr_benchmark_run.py` — mới, chạy PaddleOCR baseline + ghi kết quả JSON
- `backend/tests/test_ocr_benchmark_unit.py` — mới, 33 test
- `backend/test_fixtures/external/ocr_benchmark/` — **KHÔNG commit** (gitignore theo quy ước có
  sẵn của `test_fixtures/external/`), dựng lại bằng script

## 5. New API / DB / State

**Không có.** Không route API, không bảng/cột CSDL mới, không thay đổi state production nào.
Toàn bộ nằm ở tầng script/service offline.

## 6. Tests

```
$ cd backend && ../.venv/bin/python -m pytest tests/test_ocr_benchmark_unit.py -q
....................................                                     [100%]
36 passed
```

Phủ đủ 6 mục Scope E của mini-spec:
- Manifest schema validation (thiếu từng trường trong 11 trường bắt buộc, JSON hỏng, thiếu file).
- Ground truth không rỗng trừ case đánh dấu `intentionally-empty`.
- Không trùng `sample_id`.
- Crop file tồn tại trên đĩa.
- `license_scope`/`include_in_public_report` có mặt và đúng kiểu.
- Metrics với corpus giả có đáp số biết trước (`kitten`→`sitting` = khoảng cách 3, WER đếm theo
  từ chứ không theo ký tự, runtime percentile trên dãy số biết trước).

**Cố ý không phụ thuộc dataset 45 mẫu thật** (bị gitignore) — test tự dựng manifest/crop tối
giản trong `tmp_path`, chạy được trên máy chưa từng chạy `ocr_benchmark_generate_dataset.py`.

## 7. Live Verification — chạy PaddleOCR baseline thật trên 45 mẫu

```
$ docker compose -f deploy/docker-compose.yml run --rm -e PYTHONPATH=/app worker \
    python scripts/ocr_benchmark_run.py
```

### Tổng thể (45 mẫu)

| Chỉ số | Giá trị |
|---|---|
| Exact match | **40/45 (88,9%)** |
| CER | 1,25% (16/1281 ký tự) |
| WER | 2,5% (6/240 từ) |
| Missing character rate | 1,38% (15/1086) |
| Missing line rate | 1/10 (chỉ tính trên 10 mẫu nhiều dòng) |
| Empty output | 0/45 |
| Runtime | trung bình 3619ms · p50 2154ms · p95 5225ms |

### Theo `lettering_style` — đúng yêu cầu "phân tách normal vs stylized"

| Nhóm | n | Exact match | CER |
|---|---|---|---|
| `uppercase_tight` (Bangers — mô phỏng đúng kiểu MangaPlus) | 10 | **10/10 (100%)** | 0% |
| `outlined` (SFX, viền, xoay mạnh) | 5 | **5/5 (100%)** | 0% |
| `italic_stylized` (nghiêng) | 10 | 9/10 (90%) | 0,25% |
| `normal_handlettered` | 15 | 14/15 (93,3%) | 0,47% |
| `noisy_partial` (mờ/nhiễu/cắt cạnh) | 5 | **2/5 (40%)** | **9,77%** |

### Soi từng ca "hỏng" — không ca nào là PaddleOCR đọc bậy chữ hoa/nghiêng

| Mẫu | Thật | Đọc được | Nguyên nhân |
|---|---|---|---|
| `pc_p1_b1` | `...and the last touch.` | `….and the last touch.` | PaddleOCR trả ký tự dấu-ba-chấm Unicode (`…`) thay vì 3 dấu chấm rời — lệch QUY ƯỚC GHI ground truth, không phải đọc sai chữ |
| `syn_it_01` | `...good idea...` | `...good idea..` | thiếu đúng 1 dấu chấm cuối cùng |
| `syn_noisy_03` | `TARGET CONFIRMED, MOVING IN.` | `TARGET CONFIRMED, MOU` | ảnh bị CẮT CẠNH (tham số suy biến cố ý) — phần "đọc sai" thực ra là phần **không còn tồn tại trong ảnh** |
| `syn_noisy_04` | `...WE'RE NOT DONE YET.` | `...WE'RE NOT DONE VET.` | 1 ký tự sai thật (Y→V) dưới nhiễu Gaussian — ca lỗi thật duy nhất trong cả 45 mẫu |
| `syn_noisy_05` | `...NO MORE GAMES.` | `...NO MORE GAI` | cũng bị cắt cạnh, tương tự `syn_noisy_03` |

**Kết luận:** trong 5 ca không khớp tuyệt đối, 2 ca là quy ước ghi chép (không phải lỗi đọc), 2 ca
là hệ quả TẤT YẾU của việc tôi cố ý cắt mất một phần ảnh (không phải lỗi model), và **đúng 1 ca**
là lỗi đọc ký tự thật, xảy ra dưới nhiễu ảnh nặng — không phải trên chữ hoa/nghiêng/cách điệu.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí (từ mini-spec) | Đạt? |
|---|---|
| Manifest hợp lệ tối thiểu 40 crop hoặc lý do nếu chỉ pilot | ✅ 45 crop, không phải pilot |
| Mỗi sample có ground truth thủ công/tự tạo + category | ✅ |
| PaddleOCR baseline chạy được trên toàn bộ sample | ✅ 45/45, 0 lỗi thực thi |
| Metrics có tử số/mẫu số, CER/WER/exact match/runtime | ✅ (`TiLe` mọi tỉ lệ đều kèm tử/mẫu) |
| Phân tách normal vs stylized uppercase/angled | ✅ §7 |
| Không raw copyrighted asset lọt vào Git | ✅ `test_fixtures/external/` gitignore sẵn có |
| `docs/REPORT_E20a.md` + kết quả benchmark local | ✅ (file này + `ket_qua_paddleocr_baseline.json` cục bộ, không commit) |

## 9. Remaining Limits / Follow-ups — QUAN TRỌNG cho quyết định E20b

**Giả thuyết gốc của `PHASE E20` ("chữ HOA cách điệu, sát nhau làm PaddleOCR đọc sai/thiếu đáng
kể") KHÔNG được xác nhận bởi benchmark này.** Dữ liệu cho thấy ngược lại: PaddleOCR đọc hoàn hảo
đúng kiểu font (Bangers, chữ hoa đậm sát nét) được coi là nguyên nhân nghi ngờ. Trước khi chạy
E20b (so sánh Tesseract/tiền xử lý) — vốn giả định "cần fallback vì PaddleOCR yếu với font này"
— nên cân nhắc lại: **đổi engine OCR khó có khả năng sửa được lỗi thật trên MangaPlus nếu nguyên
nhân không nằm ở engine.**

Ba giả thuyết còn lại, CHƯA đo được trong E20a (đều cần dữ liệu KHÔNG public-safe hoặc cần audit
khác, ngoài phạm vi mini-spec này):

1. **Độ phân giải/kích thước crop thật quá nhỏ.** Ảnh trang MangaPlus đo được trong session này
   chỉ 784×1145px cho CẢ TRANG — một bong bóng trong đó có thể chỉ vài chục pixel chiều cao,
   thấp hơn nhiều so với 45px chữ trong bộ benchmark tự tạo (render ở cỡ generous). `noisy_partial`
   là nhóm DUY NHẤT tụt điểm rõ rệt trong E20a — cùng họ với "ảnh chất lượng thấp".
2. **Lỗi crop ở bước nhận diện (M2), không phải bước đọc chữ (M3).** Nếu bbox từ comic-text-
   detector cắt lệch/cắt sát mép chữ trên nền tranh vẽ phức tạp của MangaPlus, OCR nhận vào một
   crop đã hỏng ngay từ đầu — độc lập với việc engine đọc giỏi hay dở. `FEATURES.md` đã ghi nhận
   từ trước: "Nhận nhầm khoảng 2/7 vùng trên ảnh thật (cây chổi, vệt sáng bị tưởng là chữ)".
3. **Artefact riêng của luồng capture MangaPlus** (ảnh giải mã từ `blob:`, có thể qua nén/resize
   của chính trang trước khi tiện ích đọc được) — khác hẳn PNG sạch dựng trong E20a.

**Đề xuất, không tự quyết:** trước khi mở E20b, nên có một mini-spec ngắn đo TRỰC TIẾP nguyên
nhân trên ĐÚNG ảnh/crop thật đã gây lỗi (giữ private/gitignore, người dùng cần tự cấp ảnh vì
MangaPlus có bản quyền) — so sánh độ phân giải bbox thật vs benchmark tự tạo, và kiểm bbox từ M2
có cắt đúng bong bóng không. Việc này rẻ hơn nhiều so với chạy hết E20b (nhiều path Tesseract +
tiền xử lý) rồi mới phát hiện ra vấn đề nằm ở chỗ khác.

## 10. Phụ lục 08/09 — hai thí nghiệm thêm, không cần ảnh MangaPlus thật

Sau khi §9 nêu 3 giả thuyết còn lại, đo được 2/3 mà KHÔNG cần ảnh thật (script mới, không commit
dữ liệu sinh ra — cùng quy ước gitignore).

### 10.1 Độ phân giải thấp — `scripts/ocr_benchmark_resolution_test.py`

Lấy lại 20 mẫu `uppercase_tight`/`italic_stylized`, thu nhỏ còn 60%/35%/20% kích thước gốc (mô
phỏng bong bóng nhỏ trong 1 trang đầy đủ — ảnh MangaPlus đo thật trong tiện ích chỉ 784×1145px
**cả trang**).

| Tỉ lệ | Cao chữ TB | Exact match | CER TB |
|---|---|---|---|
| 100% (đối chứng) | 100px | 19/20 (95%) | 0,14% |
| 60% | 60px | 20/20 (100%) | 0% |
| 35% | 35px | 19/20 (95%) | 0,16% |
| **20%** | **20px** | **15/20 (75%)** | **1,26%** |

Ngay cả ở 20px — nhỏ hơn phần lớn bong bóng thật — 5 ca "sai" đều là lỗi vặt (thiếu dấu chấm
cuối, 1 ký tự W→M, mất khoảng trắng giữa từ). **Không có ca nào giống kiểu đọc bậy hoàn toàn** đã
thấy trên MangaPlus thật. ⇒ **Giả thuyết độ phân giải KHÔNG đủ giải thích**, kể cả ở mức cực đoan.

### 10.2 Nền tranh phức tạp — `scripts/ocr_benchmark_busy_bg_test.py`

Đặt lại đúng 20 câu đó (10 Bangers hoa/10 ShantellSans nghiêng) **trực tiếp lên nền tranh thật**
cắt từ Pepper&Carrot (gỗ, kệ chai lọ, bầu trời sao, ánh sáng, mây, sàn gỗ — 6 nền xen kẽ), có viền
đen giữ đọc được, KHÔNG còn bong bóng trắng sạch phía sau.

| Nhóm | Exact match | CER TB |
|---|---|---|
| `uppercase_tight` (Bangers, đậm) | **10/10 (100%)** | 0% |
| `italic_stylized` (ShantellSans, mảnh) | **0/10 (0%)** | 20,9% |

**Mẫu hình lỗi giống hệt nhau ở cả 10 ca chữ nghiêng** — mất vài ký tự ĐẦU và vài ký tự CUỐI,
đoạn giữa luôn đúng nguyên văn:

```
THẬT: "Maybe this wasn't such a good idea..."
ĐỌC : "ybe this wasn't such a good ide"        ← mất "Ma" đầu, mất "a..." cuối

THẬT: "Why does it always rain when I need it not to?"
ĐỌC : "es it always rain when I need i"        ← mất "Why do" đầu, mất "t not to?" cuối
```

Đây **không phải đọc sai ký tự nhìn thấy được** (đoạn giữa hoàn hảo) — mà là bước **dò vùng chữ
NỘI BỘ của chính PaddleOCR** (`PP-OCRv6_medium_det`, chạy TRONG `recognize()`, khác với M2 comic-
text-detector ở tầng trên) vẽ hụt biên khi nền phức tạp, và nét càng MẢNH (chữ nghiêng) càng dễ
lẫn vào nền ở hai đầu chữ hơn nét ĐẬM (Bangers) — cùng cách crop, cùng câu, chỉ khác nền, nên
không phải lỗi ở cách cắt ảnh của thí nghiệm.

**⇒ Giả thuyết đáng tin nhất bây giờ:** MangaPlus không chỉ có font đặc thù — nó còn có **chữ
mảnh + nền nghệ thuật phức tạp cùng lúc**, và tổ hợp đó (không phải riêng font, không phải riêng
độ phân giải) mới là thứ đánh gục bước dò nội bộ của PaddleOCR. Việc còn thiếu để xác nhận 100%
là ảnh MangaPlus thật (chưa có, xem §9), nhưng hướng sửa khả dĩ đã rõ hơn nhiều so với lúc mở
E20a: **nới thêm lề quanh bbox trước khi đưa vào OCR** (cho bước dò nội bộ nhiều "khoảng thở" hơn
ở nền phức tạp) là ứng viên rẻ, đáng thử TRƯỚC KHI đổi engine (Tesseract, E20b) — vì đây là lỗi ở
bước DÒ VÙNG, một tham số crop có thể sửa được mà không cần thay engine nào cả.

**Giới hạn khác:**
- Benchmark chỉ tiếng Anh (đúng phạm vi tái hiện lỗi MangaPlus) — chưa có bộ tương tự cho `ja`/`zh`.
- 2/45 mẫu bị lệch chỉ vì quy ước ghi ground truth (dấu ba chấm) — không sửa lại a-posteriori
  (tránh "gọt số liệu cho đẹp"), ghi rõ ở §7 để không hiểu nhầm là lỗi đọc thật.
- Chưa có Tesseract/tiền xử lý/Vision OCR — đúng phạm vi E20a, việc đó thuộc E20b.
