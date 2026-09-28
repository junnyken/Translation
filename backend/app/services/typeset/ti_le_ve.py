"""E65 — tách ĐỘ PHÂN GIẢI VẼ khỏi độ phân giải ĐỌC CHỮ.

## Vấn đề đo được (28-09-2026, trang thật của chủ dự án)

Trang 368×543. Bong bóng tiếng Nhật xếp chữ **dọc** nên khung chữ rất hẹp — đo được 10–34px.
Từ tiếng Việt nằm **ngang** và dài hơn nhiều:

```
bong bóng rộng 10px (còn  8px sau lề)  ·  từ "Aliator"  cần 27px
bong bóng rộng 11px (còn  9px sau lề)  ·  từ "Umi-chan?" cần 38px
=> 12/19 bong bóng KHÔNG chứa nổi MỘT từ ở cỡ chữ NHỎ NHẤT (10px)
```

Khi cả cỡ nhỏ nhất cũng không vừa, bộ căn chữ buộc phải cắt giữa từ — nhánh mà `REPORT_E60` gọi
là "lựa chọn cuối". Kết quả người dùng thấy: `ĐỘT NHIÊN` → `ĐỘ T / NHI / ẾN`.

**Đây không phải lỗi thuật toán ngắt dòng.** E60 đã vá phần đó. Đây là hình học: không có cách
xếp chữ nào nhét một từ 27px vào một ô 8px.

## Vì sao KHÔNG phóng to ảnh ĐẦU VÀO

Đã thử, đã đo: phóng trang lên 1200×1770 rồi cho chạy cả pipeline thì chữ hết vỡ (12/19 → 3/14),
nhưng **đọc chữ tệ đi rõ rệt** — `SEYAMA` thành `MUYAMA`, `AKI-CHAN` thành `LAI-CHAN`, và sinh
câu vô nghĩa. manga-ocr được huấn luyện ở độ phân giải tự nhiên; ảnh phóng nội suy làm nét chữ
nhoè theo kiểu model chưa từng thấy.

## Cách của E65

Hai độ phân giải, tách hẳn nhau:

* **ĐỌC** (dò khung, OCR, dịch, xoá chữ) — giữ nguyên ảnh gốc. Không đụng gì tới chất lượng đọc.
* **VẼ** (căn chữ + chèn chữ) — phóng ảnh *đã xoá chữ* lên `k` lần, nhân toạ độ khung lên `k`,
  rồi căn chữ trong khung đã to ra.

Cùng một cỡ chữ tối thiểu 10px, nhưng khung rộng gấp `k` lần ⇒ từ vừa.

`k` **không phải hằng số**: hàm dưới đây đo đúng chỗ chật nhất của từng trang rồi lấy vừa đủ.
Trang vốn đã đủ rộng nhận `k = 1.0` và **không bị đụng vào** — không phóng, không mờ, không
phình dung lượng.
"""
from __future__ import annotations

import logging
import math

__all__ = ["TRAN_HE_SO", "TRAN_CANH_DAI_PX", "BUOC_LAM_TRON", "tinh_he_so_ve"]

logger = logging.getLogger(__name__)

#: Trần tuyệt đối, chỉ để chặn trường hợp bệnh hoạn (một vùng nhiễu rộng 0,5px kéo cả trang
#: phình vô hạn). KHÔNG phải cái trần làm việc chính — xem `TRAN_CANH_DAI_PX`.
TRAN_HE_SO = 6.0

#: Trần LÀM VIỆC: cạnh dài của ảnh RA.
#:
#: Bản đầu của E65 chỉ chặn theo **tỉ lệ** (4,0). Sai thước đo: thứ cần chặn là **chi phí**, mà
#: chi phí đi theo số điểm ảnh của ảnh ra, không theo tỉ lệ. Cùng tỉ lệ 4× thì trang 368px ra
#: 1472px (rẻ) còn trang 2000px ra 8000px (8000×11800 ≈ 94 triệu điểm — đủ giết worker).
#:
#: Và trần tỉ lệ cắt nhầm đúng ca đang sửa: trang thật của chủ dự án cần 4,22 cho bong bóng
#: "Umi-chan?" — trần 4,0 bỏ lại đúng một bong bóng vỡ, nhìn y như chưa sửa gì.
#:
#: 2400px là cỡ cạnh dài của một trang quét chất lượng tốt. Trang 543px được phóng tới 4,42×;
#: trang 2000px chỉ được 1,2× — mà trang lớn thì vốn đã không cần phóng.
TRAN_CANH_DAI_PX = 2400

#: Làm tròn LÊN theo bước này. Không có nó thì mỗi trang ra một hệ số lẻ (1,03 · 1,07 · 1,11…)
#: và mỗi trang trong cùng một chapter lại là một kích thước ảnh khác nhau.
BUOC_LAM_TRON = 0.25


def tinh_he_so_ve(
    khung_chu,
    resolver,
    *,
    font_family: str,
    co_chu_nho_nhat: int,
    co_anh: tuple[int, int] | None = None,
    tran: float = TRAN_HE_SO,
    tran_canh_dai: int = TRAN_CANH_DAI_PX,
) -> float:
    """Trả về hệ số phóng ảnh ra, đủ để mỗi khung chứa nổi **từ dài nhất** của chính nó.

    `khung_chu`: lặp qua các bộ ba `(rong_kha_dung, chu, ...)` — bề rộng **đã trừ lề** của ô đặt
    chữ, và câu tiếng Việt sẽ đặt vào đó.

    Vì sao đo theo **TỪ DÀI NHẤT** chứ không theo cả câu: thứ đang hỏng là *cắt giữa từ*. Câu dài
    hơn khung là chuyện bình thường — nó xuống dòng. Từ dài hơn khung mới là chỗ không còn cách
    nào đúng.

    Vì sao đo ở **CỠ CHỮ NHỎ NHẤT**: đó là lằn ranh cuối. Trên nó bộ căn chữ còn thu nhỏ được;
    dưới nó thì không, và nó buộc phải cắt.
    """
    # Trần thật = nhỏ hơn giữa trần tuyệt đối và trần theo cạnh dài ảnh ra. Không biết cỡ ảnh
    # thì chỉ còn trần tuyệt đối — và nói rõ điều đó trong log, vì lúc đó chi phí không bị chặn
    # theo điểm ảnh nữa.
    if co_anh:
        canh_dai = max(int(co_anh[0]), int(co_anh[1]), 1)
        tran = min(tran, max(tran_canh_dai / canh_dai, 1.0))
    else:
        logger.info("E65: không biết cỡ ảnh, chỉ chặn theo trần tuyệt đối %.1f", tran)

    can = 1.0
    chat_nhat = None
    for rong_kha_dung, chu in khung_chu:
        tu_dai = max(str(chu or "").split(), key=len, default="")
        if not tu_dai:
            continue
        rong_o = max(float(rong_kha_dung), 1.0)
        try:
            font = resolver.resolve(font_family, int(co_chu_nho_nhat))
            rong_tu = float(font.getlength(tu_dai))
        except Exception:  # noqa: BLE001
            # Không đo được một từ KHÔNG được làm hỏng cả trang: bỏ qua từ đó, các từ khác vẫn
            # quyết định được hệ số. Im lặng ở đây là im lặng có chủ ý và có giới hạn.
            logger.warning("không đo được bề rộng của %r, bỏ qua khi tính hệ số vẽ", tu_dai)
            continue
        if rong_tu > rong_o:
            ti = rong_tu / rong_o
            if ti > can:
                can, chat_nhat = ti, (tu_dai, rong_tu, rong_o)

    if can <= 1.0:
        return 1.0

    lam_tron = math.ceil(can / BUOC_LAM_TRON) * BUOC_LAM_TRON
    # Khi trần cắn, giá trị trần là một số lẻ (2400/543 = 4,4198…) nên phải làm tròn XUỐNG theo
    # bước — làm tròn lên là vượt chính cái trần vừa đặt. Không cắn trần thì `lam_tron` vốn đã là
    # bội của bước, phép này không đổi gì.
    ket_qua = min(lam_tron, tran)
    ket_qua = max(math.floor(ket_qua / BUOC_LAM_TRON) * BUOC_LAM_TRON, 1.0)
    if chat_nhat:
        logger.info(
            "E65 hệ số vẽ %.2f (chật nhất: %r cần %.0fpx trong ô %.0fpx)%s",
            ket_qua, chat_nhat[0], chat_nhat[1], chat_nhat[2],
            " — ĐÃ CHẠM TRẦN, vẫn còn vùng phải cắt giữa từ" if lam_tron > tran else "",
        )
    return ket_qua
