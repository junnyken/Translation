"""E57 — bộ phân loại ngôn ngữ. Hàm THUẦN, không cần model, không cần CSDL.

## Bài canh nặng nhất

`test_manga_co_kanji_van_la_TIENG_NHAT_khong_phai_tieng_Trung` — trang tiếng Nhật có **rất nhiều**
chữ Hán (kanji). Nếu xét "có chữ Hán ⇒ tiếng Trung" trước khi xét kana thì **mọi manga** bị gán
thành tiếng Trung, và hậu quả là engine `zh` (PaddleOCR) thay cho `ja` (manga-ocr) — chữ vẫn đọc
ra, vẫn dịch ra, chỉ là kém hơn hẳn và **không có lỗi nào hiện**.

`test_mot_kana_le_KHONG_du_de_thanh_tieng_Nhat` — đối chứng ngược: rác OCR một ký tự không được
lật kết luận.

`test_qua_it_chu_thi_KHONG_ket_luan` — đoán từ 3 ký tự rồi trình bày như một phép đo là thứ tệ hơn
không đoán.
"""
from __future__ import annotations

import pytest

from app.models.enums import SourceLang
from app.services.nhan_dang_ngon_ngu import (
    SO_KANA_TOI_THIEU,
    SO_KY_TU_TOI_THIEU,
    dem_ky_tu,
    phan_loai,
)


# ── Ba ngôn ngữ được hỗ trợ ───────────────────────────────────────────────────────────────


def test_tieng_nhat_co_kana():
    kq = phan_loai(["おはようございます", "なにをしているの"])
    assert kq.ngon_ngu is SourceLang.ja
    assert kq.bang_chung.kana > 0


def test_manga_co_kanji_van_la_TIENG_NHAT_khong_phai_tieng_Trung():
    """BÀI CANH NẶNG NHẤT — thứ tự xét: kana TRƯỚC, Hán SAU.

    Câu này có 6 chữ Hán và chỉ vài kana, giống một bong bóng manga thật. Đảo thứ tự xét là gán
    thành `zh`.
    """
    kq = phan_loai(["俺の名前は田中だ", "学校に行こう"])
    assert kq.bang_chung.han >= 6, "câu mẫu phải thật sự nhiều chữ Hán, không thì bài này vô nghĩa"
    assert kq.bang_chung.kana >= SO_KANA_TOI_THIEU
    assert kq.ngon_ngu is SourceLang.ja


def test_tieng_trung_khong_co_kana():
    kq = phan_loai(["你今天吃饭了吗", "我们一起去学校"])
    assert kq.ngon_ngu is SourceLang.zh
    assert kq.bang_chung.kana == 0


def test_tieng_anh():
    kq = phan_loai(["WHAT ARE YOU DOING", "I can't believe it"])
    assert kq.ngon_ngu is SourceLang.en
    assert kq.bang_chung.han == 0


# ── Đối chứng ngược: KHÔNG được lật kết luận vì rác ───────────────────────────────────────


def test_mot_kana_le_KHONG_du_de_thanh_tieng_Nhat():
    """Một ký tự kana có thể là nét bị đọc nhầm trên trang tiếng Trung."""
    kq = phan_loai(["你今天吃饭了吗我们一起去", "ン"])
    assert kq.bang_chung.kana == 1
    assert kq.ngon_ngu is SourceLang.zh


def test_vai_chu_han_le_KHONG_lam_trang_tieng_Anh_thanh_tieng_Trung():
    kq = phan_loai(["WHAT ARE YOU DOING HERE RIGHT NOW", "口"])
    assert kq.bang_chung.han == 1
    assert kq.ngon_ngu is SourceLang.en


# ── Không kết luận: hai trạng thái KHÁC NHAU ──────────────────────────────────────────────


def test_khong_co_chu_nao():
    """"Trang không có chữ" là bình thường (bìa chương) — phải khác với "đọc được mà không chắc"."""
    kq = phan_loai(["", "   ", ""])
    assert kq.ngon_ngu is None
    assert kq.ly_do == "khong_doc_duoc_chu_nao"
    assert kq.bang_chung.so_vung_doc_duoc == 0
    assert kq.bang_chung.so_vung_da_thu == 3


def test_qua_it_chu_thi_KHONG_ket_luan():
    kq = phan_loai(["あい"])
    assert kq.ngon_ngu is None
    assert "qua_it_chu" in kq.ly_do
    assert kq.bang_chung.tong_co_nghia < SO_KY_TU_TOI_THIEU


def test_chi_co_dau_cau_va_chu_so_thi_KHONG_ket_luan():
    """`"!!!"` hay `"123"` không nói gì về ngôn ngữ. Đếm chúng vào tổng sẽ làm loãng ngưỡng tỉ lệ
    và đẩy kết luận sang hướng sai."""
    kq = phan_loai(["!!!", "...", "123456789", "?!?!"])
    assert kq.bang_chung.tong_co_nghia == 0
    assert kq.ngon_ngu is None
    assert kq.ly_do == "khong_doc_duoc_chu_nao"


def test_khong_nhom_nao_du_nguong_thi_KHONG_doan():
    """Hán 10%, Latin 40%, chữ cái khác 50%: không nhóm nào đủ ngưỡng ⇒ trả None để giao diện hỏi
    lại, chứ không chọn nhóm cao nhất rồi im lặng."""
    kq = phan_loai(["abcd", "口", "12345", "!!!!!", "ффффф"])
    assert (kq.bang_chung.latin, kq.bang_chung.han, kq.bang_chung.chu_cai_khac) == (4, 1, 5)
    assert kq.ngon_ngu is None
    assert "khong_nhom_nao_du_nguong" in kq.ly_do


def test_tieng_NGA_KHONG_bi_ket_luan_thanh_tieng_Anh():
    """Bản đầu của tôi gom mọi chữ cái (`unicodedata.category` bắt đầu bằng `L`) vào ô `latin`, nên
    một trang tiếng Nga ra `en` — **tự tin và sai**. Bài này canh chỗ đó.

    Hệ thống chỉ hỗ trợ ja/zh/en, nên câu trả lời đúng cho tiếng Nga là "không kết luận", để giao
    diện hỏi lại người dùng — chứ không phải chọn bừa một trong ba.
    """
    kq = phan_loai(["Привет как дела", "Что ты делаешь"])
    assert kq.bang_chung.latin == 0
    assert kq.bang_chung.chu_cai_khac > 0
    assert kq.ngon_ngu is None


def test_chu_Latin_co_dau_van_tinh_la_Latin():
    """`café`, `naïve`, `Đường` — chữ Latin có dấu phải vào ô `latin`, không rơi sang `chu_cai_khac`,
    không thì một trang tiếng Anh có vài từ mượn bị đẩy về "không chắc"."""
    bc = dem_ky_tu(["café naïve Ápple"])
    assert bc.chu_cai_khac == 0
    assert bc.latin == 14  # café(4) + naïve(5) + Ápple(5)


# ── Giới hạn ĐÃ BIẾT, ghi lại thành bài chứ không giấu ─────────────────────────────────────


def test_tieng_han_bi_nhan_SAI_va_day_la_gioi_han_da_biet():
    """Từ điển của model có **0/11.172** ký tự Hangul (đo 27-09-2026), nên trang tiếng Hàn không
    bao giờ đọc ra Hangul — nó ra chuỗi rác Hán/Latin.

    Bài này KHÔNG khẳng định hành vi đúng; nó ghim lại hành vi SAI đã biết để ai đó thêm tiếng Hàn
    vào `SourceLang` sẽ thấy bài này đỏ và phải đọc giải thích. Giấu giới hạn trong tài liệu thì
    không ai đọc; ghim vào bộ test thì không bỏ qua được.
    """
    kq = phan_loai(["안녕하세요 반갑습니다"])
    assert kq.bang_chung.hangul > 0
    # Hangul được đếm vào `tong_co_nghia` nhưng KHÔNG có nhánh nào nhận nó ⇒ không kết luận.
    assert kq.ngon_ngu is None, (
        "nếu bài này đỏ nghĩa là có người thêm nhánh cho Hangul — đọc docstring module trước khi sửa"
    )


# ── Bằng chứng phải ĐÚNG SỐ, vì giao diện sẽ hiện nó ra ───────────────────────────────────


def test_bang_chung_dem_dung_tung_khoi():
    bc = dem_ky_tu(["あア亜a", "!!"])
    assert (bc.kana, bc.han, bc.latin) == (2, 1, 1)
    assert bc.tong_co_nghia == 4
    assert bc.so_vung_doc_duoc == 2
    assert bc.so_vung_da_thu == 2


@pytest.mark.parametrize("chuoi", [None, ""])
def test_chuoi_rong_hay_None_khong_lam_no(chuoi):
    """OCR trả `None` cho vùng đọc không ra. Ném lỗi ở đây sẽ biến một vùng mờ thành job failed."""
    bc = dem_ky_tu([chuoi])
    assert bc.tong_co_nghia == 0
