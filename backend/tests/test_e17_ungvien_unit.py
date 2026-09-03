"""E17 — luật rút ứng viên & cổng đối chiếu của tầng 3 (không đụng DB).

Bộ này gọi thẳng các hàm mà đường chạy thật gọi. Bài học P3h còn nóng: test so với một bản chép
lại của thuật toán thì chỉ chứng minh thuật toán, không chứng minh mã đang chạy.
"""
from __future__ import annotations

import pytest
from app.models.enums import TermType
from app.services.consistency.goi_y_ten import dung_prompt, phan_tich_va_doi_chieu
from app.services.consistency.ungvien import (
    DongChu,
    UngVien,
    _ratio_chu_hoa,
    _rut_en,
    _rut_ja,
    _rut_zh,
)


def _dong(*texts: str, trang: int = 1) -> list[DongChu]:
    # `region_id` phải DUY NHẤT kể cả giữa hai lần gọi: bộ đếm khử trùng theo (vùng, vị trí), nên
    # hai vùng khác nhau mà trùng id sẽ bị coi là một chỗ. Vùng thật là UUID nên không dính.
    return [DongChu(page_order=trang, region_id=f"r{trang}-{i}", text=t)
            for i, t in enumerate(texts)]


def _rut(fn, dong, *a) -> dict[str, UngVien]:
    kho: dict[str, UngVien] = {}
    fn(dong, kho, *a)
    return kho


class TestTatDinh:
    def test_chay_hai_lan_ra_y_het(self):
        """Cùng đầu vào ⇒ cùng đầu ra. Không có tính chất này thì không ai kiểm chứng được gì."""
        dong = _dong("ペッパーさん、こんにちは", "ペッパーは魔法を使う")
        a, b = _rut(_rut_ja, dong), _rut(_rut_ja, dong)
        assert sorted(a) == sorted(b)
        assert [a[k].count for k in sorted(a)] == [b[k].count for k in sorted(b)]


class TestTiengNhat:
    def test_cat_dung_ten_truoc_hau_to_kinh_ngu(self):
        kho = _rut(_rut_ja, _dong("ペッパーさん、待って!"))
        assert "ペッパー" in kho, "không cắt được tên đứng trước さん"
        assert kho["ペッパー"].type_guess == TermType.character_name
        assert any("さん" in r for r in kho["ペッパー"].reasons)

    def test_khong_nuot_ca_hau_to_vao_ten(self):
        kho = _rut(_rut_ja, _dong("カルロ様が来た"))
        assert "カルロ" in kho
        assert "カルロ様" not in kho, "hậu tố bị nuốt vào tên ⇒ thuật ngữ sai từ gốc"

    def test_katakana_van_duoc_neu_khong_co_hau_to(self):
        kho = _rut(_rut_ja, _dong("コーヒーを飲む"))
        assert "コーヒー" in kho
        assert kho["コーヒー"].type_guess == TermType.general_term, (
            "không có bằng chứng danh xưng thì KHÔNG được đoán là tên nhân vật"
        )

    def test_kanji_qua_pho_thong_bi_chan(self):
        kho = _rut(_rut_ja, _dong("大丈夫ですか"))
        assert "大丈夫" not in kho

    def test_dem_dung_so_lan_va_gom_trang(self):
        dong = _dong("ペッパーさん!", trang=1) + _dong("ペッパーさん、また?", trang=3)
        kho = _rut(_rut_ja, dong)
        assert kho["ペッパー"].count == 2
        assert kho["ペッパー"].pages == {1, 3}

    def test_hai_luat_cung_bat_mot_cho_thi_KHONG_dem_hai_lan(self):
        """`ペッパーさん` khớp cả luật hậu tố lẫn luật katakana — vẫn phải là MỘT lần xuất hiện.

        Đếm theo số lần khớp luật thay vì số lần xuất hiện sẽ thổi con số mà người dùng dựa vào
        để duyệt. Cùng loại bẫy với chế độ chỉ-đếm của P3f.
        """
        kho = _rut(_rut_ja, _dong("ペッパーさん"))
        assert kho["ペッパー"].count == 1
        assert len(kho["ペッパー"].reasons) >= 2, "vẫn phải giữ CẢ HAI lý do để người đọc hiểu"

    def test_cung_mot_vung_xuat_hien_hai_lan_thi_dem_hai(self):
        kho = _rut(_rut_ja, _dong("ペッパーさん、ペッパーさん!"))
        assert kho["ペッパー"].count == 2

    def test_trich_dan_la_nguyen_van(self):
        cau = "ペッパーさん、待って!"
        kho = _rut(_rut_ja, _dong(cau))
        assert kho["ペッパー"].quotes[0].text == cau, "trích dẫn phải là câu THẬT, không dựng lại"


class TestTiengAnhBayToanChuHoa:
    """Cái bẫy quan trọng nhất của E17: chữ lồng truyện tranh hay viết hoa toàn bộ."""

    def test_do_dung_ty_le_chu_hoa(self):
        assert _ratio_chu_hoa(["WHAT ARE YOU DOING"]) == 1.0
        assert _ratio_chu_hoa(["Pepper is here"]) < 0.2
        assert _ratio_chu_hoa(["123 !!!"]) == 0.0, "không có chữ cái ⇒ 0.0, không phải 1.0"

    def test_toan_chu_hoa_KHONG_duoc_tra_ve_moi_tu(self):
        """Nếu luật ngây thơ chạy, mọi từ viết hoa đều thành ứng viên — vô dụng và gây hại."""
        dong = _dong("WHAT ARE YOU DOING HERE", "I KNOW WHAT YOU WANT")
        kho = _rut(_rut_en, dong, True)
        assert "what" not in kho and "you" not in kho and "know" not in kho
        assert len(kho) <= 3, f"nhánh toàn-hoa vẫn ra quá nhiều rác: {sorted(kho)}"

    def test_toan_chu_hoa_van_bat_duoc_ten_sau_danh_xung(self):
        # Khoá đã hạ chữ thường (`khoa_thuat_ngu` cho tiếng Anh); `term` giữ NGUYÊN VĂN.
        kho = _rut(_rut_en, _dong("YES, SIR PEPPER! WE MUST GO"), True)
        assert "pepper" in kho
        assert kho["pepper"].term == "PEPPER", "phải giữ nguyên văn để người dùng gõ lại đúng"
        assert kho["pepper"].type_guess == TermType.character_name

    def test_chu_thuong_dung_tin_hieu_viet_hoa_giua_cau(self):
        kho = _rut(_rut_en, _dong("I met Pepper today. Pepper was tired."), False)
        assert "pepper" in kho, f"không bắt được tên viết hoa giữa câu: {sorted(kho)}"
        assert kho["pepper"].count == 2, (
            "'Pepper' đầu câu tự nó không phải bằng chứng tên riêng, NHƯNG từ này đã được chứng "
            "minh ở chỗ khác nên lần đó vẫn là một lần xuất hiện THẬT — bỏ đi là đếm thấp hơn "
            "sự thật, mà đây đúng là con số người dùng dựa vào để duyệt"
        )

    def test_dau_cau_KHONG_tu_no_lam_bang_chung(self):
        """Mặt kia của cùng một luật: không có bằng chứng ở chỗ khác thì đầu câu không tính."""
        kho = _rut(_rut_en, _dong("Pepper was tired. Pepper slept."), False)
        assert "pepper" not in kho

    def test_tu_dau_cau_khong_bi_ket_oan_la_ten_rieng(self):
        kho = _rut(_rut_en, _dong("Wonderful day. Terrible night."), False)
        assert "wonderful" not in kho and "terrible" not in kho


class TestTiengTrung:
    def test_bat_ten_truoc_hau_to_xung_danh(self):
        kho = _rut(_rut_zh, _dong("李逍遥大人来了"))
        assert any("大人" in r for uv in kho.values() for r in uv.reasons)

    def test_tu_pho_thong_bi_chan(self):
        kho = _rut(_rut_zh, _dong("这个什么东西", "这个什么东西"))
        assert "这个" not in kho and "什么" not in kho


class TestCongDoiChieuTang3:
    """Lớp chặn model bịa. Không có nó thì tầng 3 chỉ là một cái máy đoán có giao diện đẹp."""

    def test_prompt_khong_hoi_truyen_co_nhan_vat_nao(self):
        p = dung_prompt("Pepper&Carrot", ["Pepper", "Carrot"], "en")
        assert "TRÍCH RA TỪ CHÍNH chapter này" in p
        assert "KHÔNG thêm mục mới" in p
        assert "`?`" in p, "phải cho model đường nói 'không biết'"

    def test_giu_dong_nhac_lai_dung_thuat_ngu(self):
        goi_y, loai = phan_tich_va_doi_chieu(
            "1. Pepper => Pepper | character_name | cô phù thuỷ nhỏ", ["Pepper"]
        )
        assert loai == 0
        assert goi_y[0].source_term == "Pepper" and goi_y[0].target_term == "Pepper"
        assert goi_y[0].term_type == "character_name"

    def test_LOAI_dong_nhac_lai_mot_ten_KHONG_co_trong_danh_sach(self):
        """Đây là ca quan trọng nhất: model dựng ra một nhân vật không có trong chapter."""
        goi_y, loai = phan_tich_va_doi_chieu(
            "1. Pepper => Pepper | character_name | ok\n"
            "2. Shichimiya Satone => Satone | character_name | nhân vật chính",
            ["Pepper"],
        )
        assert [g.source_term for g in goi_y] == ["Pepper"]
        assert loai == 1, "mục bịa phải bị loại VÀ được đếm"

    def test_LOAI_dong_nhac_sai_thuat_ngu_du_dung_so_thu_tu(self):
        goi_y, loai = phan_tich_va_doi_chieu("1. Carrot => Cà Rốt | character_name | con mèo",
                                             ["Pepper"])
        assert goi_y == [] and loai == 1

    def test_model_noi_khong_biet_thi_khong_tinh_la_bia(self):
        goi_y, loai = phan_tich_va_doi_chieu("1. Pepper => ? | | ", ["Pepper"])
        assert goi_y == []
        assert loai == 0, "'không biết' là câu trả lời TRUNG THỰC, không phải lỗi"

    def test_loai_khong_hop_le_ha_ve_general_term_chu_khong_no(self):
        goi_y, _ = phan_tich_va_doi_chieu("1. Pepper => Pepper | nhan_vat_chinh | x", ["Pepper"])
        assert goi_y[0].term_type == TermType.general_term.value

    def test_nhan_nguon_di_theo_tung_goi_y(self):
        goi_y, _ = phan_tich_va_doi_chieu("1. Pepper => Pepper | character_name | x", ["Pepper"])
        assert goi_y[0].to_json()["nguon"] == "goi_y_mo_hinh_chua_duyet", (
            "mất nhãn này thì giao diện không còn cách nào phân biệt gợi ý với thuật ngữ đã chốt"
        )

    @pytest.mark.parametrize("rac", ["", "xin chào", "Tôi không biết bộ truyện này.", "1) hỏng"])
    def test_phan_hoi_rac_khong_lam_no(self, rac):
        goi_y, loai = phan_tich_va_doi_chieu(rac, ["Pepper"])
        assert goi_y == [] and loai == 0


class TestSauDanhXungKhongNhanBua:
    """P3l — luật "sau danh xưng ⇒ tên nhân vật" từng nhận BẤT KỲ từ nào theo sau.

    Kiểm chứng live E17 trên host 2026-09-03 cho ra ứng viên `"of"` gắn nhãn `character_name`,
    lý do *"đứng sau danh xưng king"* — luật bắn vào "King **of** Chaosah".
    """

    def _ten(self, kho):
        """Khoá của kho là term_key viết thường — cái cần kiểm là `source_term` nguyên văn."""
        return {v.term for v in kho.values()}

    def test_gioi_tu_sau_danh_xung_KHONG_thanh_ten_nhan_vat(self):
        kq = _rut(_rut_en, _dong("The King of Chaosah is angry. The King of Chaosah waits."), False)
        assert "of" not in self._ten(kq), "giới từ sau danh xưng bị nhận làm tên nhân vật"

    def test_van_bat_dung_ten_that_sau_danh_xung(self):
        """Sửa dương tính giả mà làm mất luôn dương tính thật thì còn tệ hơn."""
        kq = _rut(_rut_en, _dong("Sir Pepper arrived. Sir Pepper left again."), False)
        ten = self._ten(kq)
        assert "Pepper" in ten
        muc = kq["pepper"]
        assert muc.type_guess is TermType.character_name
        assert any("danh xưng" in r for r in muc.reasons)

    def test_chan_theo_CAU_TRUC_chu_khong_theo_danh_sach_tu(self):
        """Một giới từ chưa từng có trong `_CHAN_EN` vẫn phải bị loại, nhờ luật viết-thường.

        Nếu chỉ vá bằng danh sách từ thì "amongst" sẽ lọt — và lần sau là một từ khác nữa.
        """
        kq = _rut(_rut_en, _dong("The King amongst them ruled. The King amongst them ruled."), False)
        assert "amongst" not in self._ten(kq)

    def test_toan_hoa_thi_dua_vao_tu_pho_thong_chu_khong_dua_vao_viet_hoa(self):
        """Cả đoạn viết hoa thì tín hiệu viết hoa chết; không được vì thế mà nhận bừa."""
        kq = _rut(_rut_en, _dong("THE KING OF CHAOSAH IS ANGRY. THE KING OF CHAOSAH WAITS."), True)
        assert "OF" not in self._ten(kq)


class TestCoTinhKHONGBatTenODauCau:
    """Ghim một đánh đổi CÓ CHỦ Ý, để lần sau không ai "sửa" nó thành máy đẻ dương tính giả.

    Kiểm chứng live cũng cho thấy `Cayenne` (tên nhân vật, xuất hiện đúng một lần, ở ĐẦU câu)
    không được liệt kê. Đó **không phải lỗi**: một từ viết hoa ở đầu câu viết hoa vì ngữ pháp, nên
    tự nó không phải bằng chứng. Nới luật này ra sẽ biến mọi câu mở đầu thành ứng viên.

    Cái giá đã biết và chấp nhận: tên chỉ xuất hiện một lần và luôn ở đầu câu thì bị bỏ sót.
    """

    def test_tu_dau_cau_xuat_hien_MOT_lan_thi_khong_thanh_ung_vien(self):
        kq = _rut(_rut_en, _dong("Cayenne is right. Everyone agreed with that."), False)
        assert "Cayenne" not in {v.term for v in kq.values()}

    def test_nhung_cau_mo_dau_binh_thuong_cung_khong_lot_vao(self):
        """Mặt kia của cùng đánh đổi — đây mới là thứ luật này bảo vệ."""
        kq = _rut(_rut_en, _dong("Wonderful day. Terrible night. Wonderful day again."), False)
        assert not {"Wonderful", "Terrible"} & {v.term for v in kq.values()}
