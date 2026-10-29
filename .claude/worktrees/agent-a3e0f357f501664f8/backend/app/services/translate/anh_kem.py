"""E32 — chuẩn bị ảnh trang để gửi kèm cho mô hình dịch.

## Vì sao gửi ảnh

Mô hình hiện **chỉ nhận chữ do OCR đọc**. Nên nó phải đoán khi chữ bị đọc sai, và không biết câu
nào là của nhân vật nào. Lỗi đọc là thật, đo được:

    Laughing Potions  ->  Luughing Fotlons     (tiếng Anh)
    どなどは                                    (rác hoàn toàn)
    足りなかったかかも                           (nhân đôi ký tự か)

## Vì sao PHẢI thu nhỏ

Gemini tính tiền ảnh theo ô 768×768. Trang truyện gốc 1200×1660 chiếm nhiều ô, và chi phí đó nhân
lên theo **từng trang**. `llm_context` chỉ-chữ đo được ~300 token/trang; gửi ảnh nguyên cỡ có thể
đẩy con số đó lên nhiều lần.

Thu nhỏ là cách trực tiếp nhất để chặn, nhưng **không được thu quá**: nhỏ tới mức mô hình không đọc
nổi chữ trong bong bóng thì mất đúng cái lợi mà việc gửi ảnh mang lại. 1024 px cạnh dài là điểm
giữ được chữ còn đọc được.

## Luật

**Thất bại thì trả `None`, KHÔNG nổ.** Gửi ảnh là phần *thêm*; ảnh hỏng không được làm mất cả lượt
dịch. Không có ảnh thì `llm_context` vẫn dịch bằng chữ như trước E32.
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

#: Chỉ dùng JPEG khi gửi đi: nhỏ hơn PNG nhiều lần ở ảnh truyện, mà chữ vẫn đọc được.
MIME_GUI = "image/jpeg"

#: Chất lượng JPEG. 82 là mức chữ trong bong bóng còn nét mà tệp không phình.
CHAT_LUONG = 82


def chuan_bi_anh(du_lieu: bytes, canh_toi_da: int) -> tuple[bytes, str] | None:
    """Thu nhỏ `du_lieu` về cạnh dài <= `canh_toi_da`, trả `(bytes, mime)`. Hỏng thì `None`.

    KHÔNG phóng to ảnh nhỏ hơn ngưỡng — phóng to chỉ làm tệp nặng thêm mà không thêm thông tin.
    """
    if not du_lieu or canh_toi_da < 1:
        return None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(du_lieu)) as im:
            anh = im.convert("RGB")
            canh_dai = max(anh.size)
            if canh_dai > canh_toi_da:
                ti_le = canh_toi_da / canh_dai
                anh = anh.resize(
                    (max(1, round(anh.width * ti_le)), max(1, round(anh.height * ti_le))),
                    Image.Resampling.LANCZOS,
                )
            ra = io.BytesIO()
            anh.save(ra, format="JPEG", quality=CHAT_LUONG, optimize=True)
            return ra.getvalue(), MIME_GUI
    except Exception as exc:  # noqa: BLE001
        # Gửi ảnh là phần THÊM. Ảnh hỏng không được làm mất cả lượt dịch.
        logger.warning("E32: không chuẩn bị được ảnh trang (%s) — dịch bằng chữ như cũ", exc)
        return None
