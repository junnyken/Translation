"""E32 — gửi kèm ảnh trang cho mô hình dịch.

Rủi ro của tính năng này KHÔNG phải chất lượng, mà là **chi phí** và **hồi quy im lặng**:

- một ảnh tốn nhiều token hơn chữ rất nhiều, và `llm_context` chỉ-chữ đo được ~300 token/trang;
- nếu bật/tắt không sạch thì lượt dịch không-ảnh cũng đổi hành vi mà không ai biết.

Nên phần lớn test dưới đây canh **bất biến khi TẮT** và **chặn chi phí khi BẬT**.
"""
from __future__ import annotations

import io
import json

import pytest

from app.services.translate.anh_kem import MIME_GUI, chuan_bi_anh
from app.services.translate.engines import LLMContextTranslator


def _anh(w: int, h: int) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 210, 220)).save(buf, format="PNG")
    return buf.getvalue()


def _kich_thuoc(du_lieu: bytes) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(du_lieu)) as im:
        return im.size


class TestChanChiPhi:
    def test_thu_nho_ve_dung_canh_toi_da(self):
        """Trang truyện thật 1200x1660 — phải co lại, vì Gemini tính tiền theo ô ảnh."""
        ra = chuan_bi_anh(_anh(1200, 1660), 1024)
        assert ra is not None
        assert max(_kich_thuoc(ra[0])) == 1024
        assert ra[1] == MIME_GUI

    def test_giu_dung_ti_le_khung(self):
        ra = chuan_bi_anh(_anh(1200, 1660), 1024)
        w, h = _kich_thuoc(ra[0])
        assert abs((w / h) - (1200 / 1660)) < 0.01

    def test_KHONG_phong_to_anh_nho(self):
        """Phóng to chỉ làm tệp nặng thêm mà không thêm một chút thông tin nào."""
        ra = chuan_bi_anh(_anh(400, 500), 1024)
        assert _kich_thuoc(ra[0]) == (400, 500)

    def test_ra_JPEG_nho_hon_PNG_vao(self):
        goc = _anh(1200, 1660)
        ra = chuan_bi_anh(goc, 1024)
        assert len(ra[0]) < len(goc)


class TestHongThiKHONG_NO:
    """Gửi ảnh là phần THÊM. Ảnh hỏng không được làm mất cả lượt dịch."""

    @pytest.mark.parametrize("xau", [b"", b"khong-phai-anh", b"\xff\xd8\xff" + b"\x00" * 20])
    def test_du_lieu_xau_tra_None(self, xau):
        assert chuan_bi_anh(xau, 1024) is None

    @pytest.mark.parametrize("canh", [0, -1])
    def test_canh_vo_ly_tra_None(self, canh):
        assert chuan_bi_anh(_anh(100, 100), canh) is None


class TestTatCoThiKHONG_DOI_GI:
    """Bất biến quan trọng nhất: không có ảnh ⇒ request giống HỆT trước E32."""

    def _than(self, tr) -> dict:
        """Lấy thân request mà `_call_api` sẽ gửi, không gọi mạng."""
        goi = {}

        def _bat(request, timeout):
            goi["body"] = json.loads(request.data.decode("utf-8"))
            raise RuntimeError("chan lai, khong goi mang")

        import app.services.translate.engines as E

        goc = E._http_json
        E._http_json = _bat
        try:
            with pytest.raises(Exception):
                tr.translate(["Hello."], "en", "vi")
        finally:
            E._http_json = goc
        return goi["body"]

    def test_khong_anh_thi_parts_chi_co_CHU(self):
        than = self._than(LLMContextTranslator(api_keys=["x"]))
        parts = than["contents"][0]["parts"]
        assert len(parts) == 1
        assert "text" in parts[0] and "inlineData" not in parts[0]

    def test_khong_anh_thi_prompt_KHONG_noi_ve_anh(self):
        p = LLMContextTranslator(api_keys=["x"]).build_prompt(["Hi"], "en", "vi")
        assert "ẢNH" not in p, "không có ảnh mà vẫn bảo mô hình xem trang = mời nó bịa"

    def test_anh_None_giong_het_khong_truyen(self):
        a = LLMContextTranslator(api_keys=["x"]).build_prompt(["Hi"], "en", "vi")
        b = LLMContextTranslator(api_keys=["x"], anh_trang=None).build_prompt(["Hi"], "en", "vi")
        c = LLMContextTranslator(api_keys=["x"], anh_trang=b"").build_prompt(["Hi"], "en", "vi")
        assert a == b == c


class TestBatCoThiGuiDungCach:
    def _than(self, tr) -> dict:
        return TestTatCoThiKHONG_DOI_GI._than(self, tr)

    def test_ANH_dung_TRUOC_chu_trong_parts(self):
        """Gemini neo câu trả lời vào phần đầu; đảo lại thì ảnh dễ bị coi là phụ."""
        tr = LLMContextTranslator(api_keys=["x"], anh_trang=b"gia-lap-anh", anh_mime="image/jpeg")
        parts = self._than(tr)["contents"][0]["parts"]
        assert len(parts) == 2
        assert "inlineData" in parts[0], "ảnh phải đứng trước chữ"
        assert "text" in parts[1]

    def test_anh_ma_hoa_base64_dung(self):
        import base64

        tr = LLMContextTranslator(api_keys=["x"], anh_trang=b"abc123")
        d = self._than(tr)["contents"][0]["parts"][0]["inlineData"]
        assert base64.b64decode(d["data"]) == b"abc123"
        assert d["mimeType"] == "image/jpeg"

    def test_co_anh_thi_prompt_NOI_cach_dung_anh(self):
        p = LLMContextTranslator(api_keys=["x"], anh_trang=b"x").build_prompt(["Hi"], "en", "vi")
        assert "ẢNH" in p
        assert "không phải để thêm nội dung" in p, "phải chặn mô hình tự thêm thoại từ ảnh"

    def test_van_giu_giao_thuc_mot_dong_mot_muc(self):
        """Có ảnh KHÔNG được làm lệch số thứ tự — đó là lỗi E30 đã sửa."""
        p = LLMContextTranslator(api_keys=["x"], anh_trang=b"x").build_prompt(
            ["một", "hai", "ba"], "en", "vi"
        )
        assert [d[:2] for d in p.splitlines() if d[:2] in ("1.", "2.", "3.")] == ["1.", "2.", "3."]
