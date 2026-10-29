"""E23 — ngưỡng của phép kiểm chứng "đã xoá sạch chữ chưa", và bằng chứng đi kèm.

## Số đo dẫn tới bản sửa này

Quét lại **cả 24 trang** của lượt chạy thật E23 (168 vùng chữ) bằng đúng phép kiểm chứng đang chạy:

    24 trang · 168 vùng · 11 vùng bị gắn cờ · 7 trang (29%) -> inpaint_needs_review

Nhưng **cả 11 vùng đều chỉ đọc ra ĐÚNG MỘT ký tự**:

    'O' x4 · 'X' x2 · 'G' · '1' · 'C' · 'è' · và một '中' trên trang TIẾNG ANH

Đó là hình OCR bịa ra từ nét cong/góc còn lại trên nền đã xoá (viền bong bóng, khung panel), không
phải chữ chưa xoá. Chữ thật còn sót trong bong bóng là một từ hoặc mảnh từ.

⇒ Ngưỡng cũ (`has_meaningful_text`, tức >=1 ký tự) gắn cờ 29% số trang mà gần như toàn báo động
giả. Cờ báo sai nhiều thì người dùng học cách phớt lờ, và lần thật sự cần thì cũng bỏ qua.
"""
from __future__ import annotations

import pytest

from app.services.ocr.engines import dem_ky_tu_co_nghia, has_meaningful_text


class TestDemKyTuCoNghia:
    def test_dem_dung_so_ky_tu_chu_so(self):
        assert dem_ky_tu_co_nghia("ab1") == 3
        assert dem_ky_tu_co_nghia("a b") == 2

    def test_bo_qua_khoang_trang_va_dau_cau(self):
        assert dem_ky_tu_co_nghia("  ...!?  ") == 0
        assert dem_ky_tu_co_nghia("") == 0
        assert dem_ky_tu_co_nghia(None) == 0

    @pytest.mark.parametrize("nhieu", ["O", "X", "G", "1", "C", "è", "中"])
    def test_dung_cac_ky_tu_NHIEU_da_gap_that(self, nhieu):
        """Bảy ký tự này lấy nguyên từ 11 vùng bị gắn cờ oan trong lượt 24 trang."""
        assert dem_ky_tu_co_nghia(nhieu) == 1, "phải đếm được 1 để ngưỡng 2 lọc chúng ra"

    def test_KHONG_dung_has_meaningful_text_de_thay_the(self):
        """Hai hàm trả lời hai câu hỏi khác nhau — không được gộp.

        `has_meaningful_text` còn dùng cho `needs_manual` của bước OCR, nơi MỘT ký tự đọc được
        VẪN là chữ thật. Siết nó toàn cục sẽ đổi cả hành vi OCR.
        """
        assert has_meaningful_text("O") is True, "OCR vẫn phải coi 1 ký tự là có chữ"
        assert dem_ky_tu_co_nghia("O") < 2, "nhưng kiểm chứng xoá chữ thì không đủ để gắn cờ"


class TestNguongKiemChung:
    """Ngưỡng phải lọc được nhiễu MÀ VẪN bắt được chữ thật — siết quá tay là hỏng cả phép kiểm."""

    NGUONG = 2

    @pytest.mark.parametrize("nhieu", ["O", "X", "1", "中", " C ", "\ng\n"])
    def test_mot_ky_tu_KHONG_gan_co(self, nhieu):
        assert dem_ky_tu_co_nghia(nhieu) < self.NGUONG

    @pytest.mark.parametrize("that", [
        "GO", "OK", "help", "AAARGH", "HELLO THERE", "b2", "không sao",
    ])
    def test_chu_THAT_van_bi_gan_co(self, that):
        """Nếu ngưỡng làm rơi cả những chuỗi này thì phép kiểm chứng thành vô dụng."""
        assert dem_ky_tu_co_nghia(that) >= self.NGUONG, f"{that!r} là chữ thật, phải bắt được"

    @pytest.mark.parametrize("bo_sot", ["Ừ", "A", "?A"])
    def test_DIEM_MU_da_biet_chu_that_MOT_ky_tu_bi_bo_sot(self, bo_sot):
        """Ngưỡng 2 BỎ SÓT chữ thật dài một ký tự. Ghi ra đây thay vì giấu đi.

        Có thật: "Ừ" là một từ tiếng Việt hoàn chỉnh; truyện tranh cũng hay có tiếng thốt một chữ.

        Vì sao vẫn chấp nhận: hậu quả của bỏ sót là trang không được gắn cờ, nên một nét chữ đơn
        có thể còn lại — mà bước căn chữ sẽ vẽ chữ dịch đè lên CHÍNH vùng đó, nên gần như luôn bị
        che. Còn hậu quả của ngưỡng 1 là gắn cờ oan 29% số trang, và một cờ báo sai nhiều lần thì
        người dùng phớt lờ luôn cả những lần đúng. Đổi `inpaint_verify_min_chars=1` để lấy lại
        hành vi cũ nếu cảnh dùng khác đi.
        """
        assert dem_ky_tu_co_nghia(bo_sot) < self.NGUONG, (
            "test này mô tả điểm mù ĐANG CHẤP NHẬN — nếu nó đỏ thì ngưỡng đã đổi, đọc lại đánh đổi"
        )

    def test_ngung_2_la_ranh_gioi_hep_nhat_loc_duoc_11_vung_da_do(self):
        """Chốt lại bằng chính dữ liệu đo được: 11 vùng oan đều 1 ký tự, nên 2 là đủ và tối thiểu.

        Đặt 3 sẽ bỏ sót chữ thật hai ký tự ("GO", "OK") — thường gặp trong truyện tranh.
        """
        oan = ["O", "O", "O", "O", "X", "X", "G", "1", "C", "è", "中"]
        assert all(dem_ky_tu_co_nghia(t) < 2 for t in oan), "ngưỡng 2 phải lọc hết 11 vùng oan"
        assert dem_ky_tu_co_nghia("GO") >= 2, "ngưỡng 2 vẫn giữ được chữ thật ngắn nhất"


def test_cau_hinh_mac_dinh_la_2():
    """Mặc định phải là giá trị đã đo, không phải giá trị ai đó chỉnh tạm rồi quên."""
    from app.core.config import get_settings

    assert get_settings().inpaint_verify_min_chars == 2
