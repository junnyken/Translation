# Báo cáo Mini-Spec P3h — Chặn OOM worker: tắt arena ONNX cho LaMa, trộn theo dải, đo được RAM

**Ngày:** 2026-08-31 · **Trạng thái:** ⚠️ **XONG Ở MÁY DEV — CHƯA PUSH, CHƯA DEPLOY, CHƯA VERIFY TRÊN HOST**
**Commit:** `64c006a` (31/08 16:10) · **Phụ thuộc:** P3g `ĐÃ DEPLOY` · P3e · P3a
**Sinh ra từ:** sự cố thật trong Pilot 6 trang (Phase 3D)

> ⚠️ Đọc kỹ dòng trạng thái. Mọi con số trong báo cáo này đo **trên máy dev**. Phần
> `Live Verification` **trống có lý do** — host không phản hồi tại thời điểm viết (xem §6).
> Không được đọc báo cáo này thành "đã chữa xong OOM trên máy chủ".

## 1. Summary

Pilot 6 trang trên host làm **worker bị OOM killer giết** (`exit 137`). Triệu chứng nhìn từ ngoài:
API tụt từ 3,4 ms xuống 10–42 s rồi tắt tiếng hẳn; 8 lượt thăm dò chỉ 3 lượt thành công; log
runtime phía nền tảng cũng mất (`wings_error`).

P3h làm ba việc, theo đúng thứ tự quan trọng:

| | Việc | Vì sao nó là việc đó chứ không phải "tăng RAM" |
|---|---|---|
| 1 | **Tắt CPU memory arena của ONNX Runtime cho LaMa** | Đây là nguyên nhân gốc, không phải triệu chứng |
| 2 | **Trộn ảnh theo dải 256 dòng** | Bỏ 5–6 mảng `float32` cỡ nguyên trang cùng tồn tại một lúc |
| 3 | **Đo được RAM** (`bo_nho.py` + `rss_mb` trong `/healthz`) | Trước P3h hệ thống **không có một chỉ số bộ nhớ nào** — đó là lý do không ai thấy gì cho tới lúc tiến trình chết |

## 2. Audit Before Build — nguyên nhân gốc

**LaMa là model *dynamic shape*, và ta chạy nó theo từng cụm bong bóng** — mỗi cụm một kích thước
khác nhau (`gom_cum()` trong `lama.py`). Session lại được dựng bằng `ort.SessionOptions()` mặc
định, tức **CPU memory arena BẬT**. Arena cấp một khối cho **mỗi shape mới** và **không bao giờ
trả lại**. Càng nhiều cụm, càng nhiều trang → càng phình, tới khi OOM killer ra tay.

Điều này giải thích đúng hình dạng của sự cố mà "thiếu RAM" không giải thích được: **một** trang
smoke ở P3a chạy trọn trong 157 giây không sao (P3a §1), còn **sáu** trang liên tiếp thì chết.

### Vì sao CTD **không** tắt arena

CTD letterbox mọi ảnh về **một** kích thước cố định (`ctd_input_size`) ⇒ chỉ có một shape ⇒ arena
không phình, và còn nhanh hơn vì tái dùng khối. Đây là phân biệt **có lý do**, không phải tắt bừa
cho an toàn: `ctd_cpu_mem_arena: bool = True` vs `inpaint_cpu_mem_arena: bool = False`.

## 3. Design Choice

### 3.1 Trộn theo dải — vì một dòng numpy đẹp đẽ tốn 5–6 mảng nguyên trang

```python
# Trước: numpy dựng rgb*(1-m3), pred*m3, tổng, *255, .round(), .astype() — mỗi cái một mảng
#        float32 cỡ nguyên trang, cùng tồn tại một lúc.
blended = rgb * (1.0 - mask3) + pred_hwc * mask3
out = Image.fromarray((blended * 255.0).round().astype(np.uint8), mode="RGB")
```

Nay lặp theo dải `_DAI_TRON = 256` dòng, dùng `out=` để ghi tại chỗ. Đỉnh bộ nhớ **thôi phụ thuộc
chiều cao trang**. 256 dòng là chỗ đứng giữa: đủ lớn để numpy còn vector hoá tốt, đủ nhỏ để đỉnh
không leo theo cỡ trang.

**Ràng buộc tự đặt: không được đổi một pixel nào.** Xem §5.2.

### 3.2 Van xả, không phải chế độ thường trực

`ep_giai_phong_neu_cang(giu, nguong_mb)` chỉ nhả model **khi RSS đã vượt ngưỡng**
(`worker_rss_soft_limit_mb = 2200`, `0` = tắt). Đường chạy bình thường **giữ nguyên cache** —
nhả rồi nạp lại là LaMa ~197 MB + CTD ~91 MB mỗi lượt, tức trả giá tốc độ để mua một thứ mình
chưa cần.

Mỗi bước khai đúng thứ nó cần:

| Bước | `giu` | Vì sao |
|---|---|---|
| detect | `{"detector"}` | không cần LaMa/OCR |
| ocr | `{"ocr"}` | — |
| inpaint | `{"inpainter", "ocr"}` | **giữ OCR** vì `inpaint_verify_by_ocr` cần nó **ngay sau đó**; nhả rồi nạp lại trong cùng một job là tự chuốc lấy cái giá vô ích |

### 3.3 `rss_mb()` đọc `/proc/self/statm`, không thêm `psutil`

Thêm một phụ thuộc chỉ để đọc một con số là cái giá không đáng; bản chạy thật là Linux.
Không đọc được thì trả **`None`**, **không** trả `0`: *"đo được và bằng không"* khác *"không đo
được"*, và gộp hai thứ đó là cách nhanh nhất để có một biểu đồ nói dối.

## 4. Changed Files

| Tệp | Việc |
|---|---|
| `app/workers/bo_nho.py` | **Mới** — `rss_mb()`, `ghi_moc()`, `giai_phong_model()`, `ep_giai_phong_neu_cang()` |
| `app/services/inpaint/lama.py` | `cpu_mem_arena` (mặc định **False**) + vòng trộn theo dải `_DAI_TRON` |
| `app/services/detect/ctd.py` | `cpu_mem_arena` (mặc định **True**) + ghi `arena=` vào log nạp model |
| `app/core/config.py` | `inpaint_cpu_mem_arena=False`, `ctd_cpu_mem_arena=True`, `worker_rss_soft_limit_mb=2200` |
| `app/workers/tasks.py` | Truyền cờ arena vào 2 engine; gọi van xả + `ghi_moc` ở ranh giới detect/ocr/inpaint |
| `app/main.py` | `/healthz` trả thêm `rss_mb` |
| `tests/test_bo_nho_unit.py` | **Mới** — 11 test (xem §5.3 về giới hạn của 2 trong số đó) |

## 5. New API/DB/State · Tests

### 5.1 API

`GET /healthz` thêm **một** trường; không endpoint mới, không đổi schema nào đã chốt, **không**
đụng `/api/v1/*`.

```json
{ "status": "ok",
  "worker": { "trang_thai": "starting", "so_lan_chet": 0, "ma_thoat_gan_nhat": null, "luc": "…" },
  "rss_mb": 412.7 }
```

`rss_mb: null` = **không đo được** (khác `0`). **DB: không đổi. Migration: không có.**

### 5.2 Đo lại đỉnh bộ nhớ khi trộn (chạy lại hôm nay, tái lập được)

`tracemalloc`, cùng seed, so **cách cũ** với **cách mới**:

| Cỡ trang | Một biểu thức | Theo dải | Giảm | Giống từng byte |
|---|---|---|---|---|
| 1200×1660 (đúng cỡ trang pilot) | **71,7 MB** | **14,6 MB** | **80 %** | ✅ |
| 1400×2000 (cỡ trang M4 đã đo) | **100,8 MB** | **18,5 MB** | **82 %** | ✅ |

Con số 1200×1660 **tái lập đúng** số đã ghi trong commit. Dòng 1400×2000 là điểm đo thêm của lần
viết báo cáo này, và nó nói một điều mà một dòng không nói được: **cách cũ leo theo diện tích
trang, cách mới gần như đứng yên.**

### 5.3 Bộ test — và hai chỗ nó **chưa** chứng minh được điều nó có vẻ chứng minh

```
867 passed, 6 skipped      (nền trước P3h: 856)      exit 0
```
**Chạy lại trong lúc viết báo cáo này** (`../.venv/bin/python -m pytest -q`, 31/08 ~19:0x) —
đúng **867 passed / 6 skipped**, khớp con số ghi trong commit. Ruff trên các tệp đã sửa:
**20 → 19** (kiểm lại hôm nay: `Found 19 errors`).

Ba test đáng giá nhất là ba test của van xả, vì chúng khẳng định thứ dễ làm sai nhất — **nhả đúng
thứ không cần, giữ đúng thứ đang dùng**:

| Test | Khẳng định |
|---|---|
| `test_vuot_nguong_thi_nha_dung_thu_khong_can` | nhả `detector`, **giữ** `inpainter` và `ocr` — "đã nhả model của chính bước đang chạy" là cách hỏng tệ nhất |
| `test_duoi_nguong_thi_giu_nguyen_cache` | chưa căng thì **không** được nhả — mất tốc độ vô ích |
| `test_khong_doc_duoc_thi_tra_None_chu_khong_phai_0` | `None` ≠ `0` |

⚠️ **Nhưng hai test của phần trộn theo dải là loại yếu hơn vẻ ngoài của chúng** — phải nói ra:

1. `test_ket_qua_giong_het_cach_lam_mot_biểu_thuc` **chép lại vòng lặp trộn vào trong test** rồi
   so với công thức một-biểu-thức. Vòng lặp thật nằm **inline trong `LamaInpainter.inpaint()`**
   (`lama.py:238`) và **không được test gọi tới**. Nên nó chứng minh *thuật toán* tương đương,
   **không** chứng minh *mã đang chạy* làm đúng thuật toán đó. Sửa bản sao mà quên sửa bản thật
   thì test này vẫn xanh.
2. `test_ngoai_mask_giu_nguyen_anh_goc` **không đụng tới đường theo dải một chút nào** — nó tính
   bản một-biểu-thức rồi assert trên chính nó. Với P3h đây là một **pass rỗng**, đúng nghĩa đã
   dùng cho Run C của E15.

**Cách đóng:** tách vòng trộn thành `_tron_theo_dai(rgb, pred, mask) -> np.ndarray` trong
`lama.py`, cho **cả** mã sản xuất **và** test gọi cùng một hàm. Việc nhỏ, nhưng chưa làm thì
không được ghi "đã test xong phần trộn". Đã ghi vào §7.

### 5.4 Một lỗi của chính tôi trong lúc sửa

Phép thay chuỗi để thêm dòng `import` **không đặt assert**, nên nó âm thầm không khớp → 20 test đỏ
với thông báo **lạc đề** (`ValueError` về UUID, chẳng liên quan gì tới import). Mất thời gian đi
tìm sai chỗ.

*Bài học: mọi phép thay chuỗi trong tệp phải có assert "đã thay được", nếu không thì lần hỏng đầu
tiên sẽ hiện ra ở một nơi rất xa chỗ gây lỗi.*

## 6. Live Verification — ⛔ **CHƯA CHẠY ĐƯỢC**

**Host không phản hồi tại thời điểm viết báo cáo (31/08 ~19:00–19:10).** Đo được:

| Kiểm | Kết quả |
|---|---|
| `GET translation-api…/healthz` | không phản hồi trong **45 s** |
| `GET translation…/` (web tĩnh) | không phản hồi trong **45 s** |
| TCP tới `203.171.31.200:443` | **kết nối được** |
| Bắt tay TLS | **không hoàn tất** — treo sau `Client hello` |
| Dashboard VibeHost | cả hai website báo **`online`** |
| `get_runtime_logs` (cả api lẫn web) | `available: false — wings_error` |
| Đối chứng mạng workspace | `google.com` **200**, `factory.matbao.ai` **307** ⇒ lối ra internet bình thường |

**Web tĩnh cũng chết cùng lúc** — nó chỉ phục vụ file build, 0,6 CPU, không dính pipeline AI.
Hai website khác nhau, cùng một node `cmc-1`, chết cùng lúc, kèm `wings_error` ⇒ **tầng nền tảng**,
không phải container của mình OOM thêm lần nữa. Đây cũng đúng triệu chứng đã ghi trong sự cố pilot.

Vì vậy **không** có: đo RSS thật trên host, chạy lại pilot 6 trang, xác nhận `exit 137` đã hết.
Chừng nào chưa có ba thứ đó thì P3h **chưa được coi là đóng**.

### Khi host sống lại — deploy đúng 3 bước

1. `git push` commit `64c006a` (đang **hơn `origin/main` 1 commit**).
2. `redeploy_project(translation-api)` — **push không tự deploy** (D001 đã ghi).
3. Chạy lại **đúng** kịch bản pilot 6 trang, vừa chạy vừa đọc `/healthz`.

**Không cần đặt biến môi trường nào.** Đã kiểm danh sách biến trên host: không có
`INPAINT_CPU_MEM_ARENA`, `CTD_CPU_MEM_ARENA` hay `WORKER_RSS_SOFT_LIMIT_MB` ⇒ cả ba lấy **mặc
định trong mã**, tức bản sửa có hiệu lực ngay khi deploy. Đổi lại, muốn **tắt** bản sửa để đối
chứng thì phải thêm biến, không có sẵn.

### Bằng chứng nào chứng minh được "đã hết OOM"

Đặt trước ngưỡng đạt, để lần sau khỏi tự nới:

| Phải thấy | Ở đâu |
|---|---|
| 6/6 trang tới `typeset_done` | API trạng thái trang |
| `worker.so_lan_chet` **= 0** trong suốt lượt chạy | `/healthz` |
| `ma_thoat_gan_nhat` **≠ 137** | `/healthz` |
| RSS worker không leo đơn điệu qua từng trang | log `bộ nhớ [inpaint: sau]` |
| API vẫn ~3–4 ms trong lúc worker chạy | đo lặp `/healthz` |

## 7. Remaining Limits — nói thẳng

1. ⛔ **Chưa verify trên host.** Toàn bộ §5 là bằng chứng loại "máy dev". Sự cố xảy ra ở loại thứ
   hai — trên host, với 6 trang thật.
2. ⚠️ **`rss_mb` trong `/healthz` là RSS của tiến trình API, KHÔNG phải của worker.** Trên host
   `ROLE=all` chạy uvicorn ở tiền cảnh và celery `--pool=solo` ở **tiến trình nền riêng**
   (`deploy-start.sh`). Tiến trình bị OOM giết là **celery**. RSS của worker hiện chỉ đi vào
   **log**, mà log runtime nền tảng thì **đang không lấy được** (`wings_error`) và **không sống
   sót qua deploy** (P3f đã ghi). ⇒ **Lỗ hổng quan sát chưa đóng hẳn.** Đường đóng rẻ nhất: cho
   worker ghi RSS vào chính `WORKER_STATE_FILE` mà `deploy-start.sh` đã dùng, rồi `/healthz` trả
   ra cả hai. Việc này **chưa làm**.
   Cái đang thật sự tố giác cái chết vẫn là `worker.so_lan_chet` + `ma_thoat_gan_nhat=137` —
   thứ đã có từ trước P3h, không phải do P3h thêm.
3. ⚠️ **Ngưỡng `2200 MB` chưa được kiểm chứng bằng số đo nào.** Container có 4096 MB và API cũng
   ăn một phần. Chọn 2200 là suy luận, không phải phép đo — phải chỉnh lại sau lượt pilot có RSS
   thật.
4. ⚠️ **Van xả chưa từng nổ trong một lượt chạy thật** — mọi test đều `monkeypatch` `rss_mb`.
   Nhánh nhả model thật (nhả rồi nạp lại LaMa giữa chừng) chưa chạy lần nào ngoài đời.
5. ⚠️ **Hai test phần trộn theo dải chưa gọi mã sản xuất** (§5.3). Cần tách `_tron_theo_dai()`.
6. **Chưa đo lại tốc độ inpaint sau khi tắt arena.** Arena tắt thường **chậm hơn** đôi chút — đổi
   tốc độ lấy sống sót là đổi có chủ đích, nhưng cái giá đó **chưa được đo**. Mốc M4 cũ:
   54,3 s/ảnh 1400×2000 trên CPU.
7. Tên test `test_ket_qua_giong_het_cach_lam_mot_biểu_thuc` chứa một ký tự có dấu (`ể`) — Python
   chấp nhận, nhưng lệch quy ước ASCII-không-dấu của mọi tên test khác trong repo, và làm nó khó
   gõ khi cần `pytest -k`.
8. Các khoản nợ cũ **không** thuộc P3h và vẫn còn: `GEMINI_API_KEYS` trên host đang
   `isSecret: false`; chưa có auth/RBAC/multi-user; tag `v1.5-E15-closed` + `v1.6-E1a-cors-hardening`
   chưa đẩy.
