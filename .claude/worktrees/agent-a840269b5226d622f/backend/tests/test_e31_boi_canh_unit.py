"""E31 — nối thuật ngữ + giọng nhân vật ĐÃ CHỐT vào prompt của `llm_context`.

`llm_context` nhất quán trong MỘT trang nhưng không thấy trang khác — giới hạn đã ghi ở
`REPORT_E26 §9`. Đo thật: `Air Dragon` ra `Rồng Gió` ở trang này, không gì bảo đảm trang sau không
ra `Rồng Không Khí`. Bảng thuật ngữ là chỗ duy nhất giữ được quyết định đó xuyên trang.

Rủi ro của module này là **đưa phỏng đoán chưa ai duyệt vào prompt** rồi biến một gợi ý sai thành
cái sai lặp trên cả chapter. Phần lớn test dưới đây canh chiều đó.
"""
from __future__ import annotations

from app.services.translate.boi_canh import _dong_nhan_vat, _dong_thuat_ngu
from app.services.translate.engines import LLMContextTranslator


class _TN:
    """Bản ghi thuật ngữ tối giản — chỉ các trường module này đọc."""

    def __init__(self, goc, dich, loai=None, cam=None):
        self.source_term, self.target_term = goc, dich
        self.term_type = type("E", (), {"value": loai})() if loai else None
        self.prohibited_variants = cam or []


class _NV:
    def __init__(self, ten, aliases=None, giong=None, xung_ho=None, tone=None):
        self.character_name, self.aliases = ten, aliases or []
        self.speech_register = type("E", (), {"value": giong})() if giong else None
        self.vietnamese_pronoun_guidance, self.tone_note = xung_ho, tone


class TestDinhDangDongThuatNgu:
    def test_co_mui_va_loai(self):
        d = _dong_thuat_ngu(_TN("Air Dragon", "Rồng Gió", "item"))
        assert "Air Dragon → Rồng Gió" in d and "(item)" in d

    def test_neu_ro_bien_the_BI_CAM(self):
        """Nói ra cái KHÔNG được dùng mạnh hơn chỉ nói cái được dùng."""
        d = _dong_thuat_ngu(_TN("Air Dragon", "Rồng Gió", cam=["Rồng Không Khí", "Air Dragon"]))
        assert "KHÔNG dùng" in d and "Rồng Không Khí" in d

    def test_khong_co_loai_thi_khong_in_ngoac_rong(self):
        assert "()" not in _dong_thuat_ngu(_TN("Chaosah", "Chaosah"))


class TestDinhDangDongNhanVat:
    def test_gom_du_giong_xung_ho_va_ghi_chu(self):
        d = _dong_nhan_vat(_NV("Pepper", ["ペッパー"], "casual", "gọi Carrot là 'mày'", "hay bốc đồng"))
        for phan in ("Pepper", "ペッパー", "casual", "mày", "bốc đồng"):
            assert phan in d

    def test_thieu_truong_thi_bo_qua_chu_khong_in_rong(self):
        d = _dong_nhan_vat(_NV("Pepper"))
        assert d.strip() == "- Pepper"


class TestPromptKhongDoiKhiKHONG_CO_BOI_CANH:
    """Bất biến: chưa chốt gì thì prompt phải giống HỆT trước E31."""

    def test_boi_canh_rong_thi_prompt_khong_them_ky_tu_nao(self):
        a = LLMContextTranslator(api_keys=["x"]).build_prompt(["Hi"], "en", "vi")
        b = LLMContextTranslator(api_keys=["x"], boi_canh="").build_prompt(["Hi"], "en", "vi")
        c = LLMContextTranslator(api_keys=["x"], boi_canh="   \n  ").build_prompt(["Hi"], "en", "vi")
        assert a == b == c

    def test_boi_canh_None_khong_no(self):
        assert LLMContextTranslator(api_keys=["x"], boi_canh=None).build_prompt(["Hi"], "en", "vi")


class TestBoiCanhVaoDungCHO:
    def test_boi_canh_dung_TRUOC_danh_sach_chu(self):
        """Đặt sau danh sách thì mô hình đọc xong chữ mới thấy thuật ngữ, và không quay lại sửa."""
        p = LLMContextTranslator(
            api_keys=["x"], boi_canh="### Thuật ngữ\n- Air Dragon → Rồng Gió"
        ).build_prompt(["Air Dragon!"], "en", "vi")
        assert p.index("Rồng Gió") < p.index("1. Air Dragon!")

    def test_van_giu_dung_giao_thuc_mot_dong_mot_muc(self):
        """Bối cảnh nhiều dòng KHÔNG được làm lệch số thứ tự — đó là lỗi E30 đã sửa."""
        p = LLMContextTranslator(
            api_keys=["x"], boi_canh="### A\n- x → y\n\n### B\n- z"
        ).build_prompt(["một", "hai"], "en", "vi")
        assert [d[:2] for d in p.splitlines() if d[:2] in ("1.", "2.")] == ["1.", "2."]
