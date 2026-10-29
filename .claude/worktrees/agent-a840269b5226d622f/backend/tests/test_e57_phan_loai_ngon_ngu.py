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
    SO_HAN_TOI_THIEU,
    SO_KANA_TOI_THIEU,
    SO_KY_TU_TOI_THIEU,
    TI_LE_HAN_TOI_THIEU,
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


# ── Hiệu chỉnh trên DỮ LIỆU THẬT (E57b, 27-09-2026) ───────────────────────────────────────
#
# Số trong các bài dưới đây là **số đo thật** từ 37 trang có nhãn
# (`app/services/ocr_benchmark/hieu_chinh_nhan_dang.py`), không phải số dựng cho vừa. Đổi ngưỡng mà
# không chạy lại phép đo đó thì các bài này đỏ — đúng ý muốn.


@pytest.mark.parametrize(
    "ten_trang,han,kana,latin",
    [
        # SÁU trang tiếng Nhật THẬT có tỉ lệ Hán >= 20% — tức là vượt `TI_LE_HAN_TOI_THIEU`.
        # Ba con số là ba ô ĐO ĐƯỢC. Tổng thật của trang có thể lớn hơn tổng ba ô này một vài ký tự
        # (trang có ít ký tự rơi vào ô `chu_cai_khac`) — không nhồi thêm cho khớp, vì phần thêm đó chỉ
        # làm LOÃNG tỉ lệ Hán, tức bài canh dựng lại đã nghiêm hơn trang thật một chút.
        ("E03P01", 13, 47, 4),      # trang thật: Hán 13/64 = 20,3%
        ("E03P02", 36, 122, 0),     # trang thật: Hán 36/160 = 22,5%
        ("E03P04", 10, 31, 0),      # trang thật: Hán 10/41 = 24,4%
        ("E03P05", 13, 24, 0),      # trang thật: Hán 13/37 = 35,1% — cao nhất đo được
        ("E03P06", 12, 25, 5),      # trang thật: Hán 12/42 = 28,6%
        ("E03P07", 23, 54, 10),     # trang thật: Hán 23/89 = 25,8%
    ],
)
def test_trang_Nhat_THAT_co_ti_le_Han_vuot_nguong_van_ra_ja(ten_trang, han, kana, latin):
    """BÀI CANH NẶNG NHẤT, nay có SỐ ĐO THẬT đứng sau.

    Sáu trang này là trang tiếng Nhật thật (Pepper&Carrot bản ja, CC BY-SA 4.0) và cả sáu đều có tỉ lệ
    chữ Hán **vượt ngưỡng tiếng Trung**. Xét Hán trước kana thì cả sáu bị gán `zh` ⇒ dùng PaddleOCR
    thay manga-ocr: chữ vẫn ra, vẫn dịch, chỉ kém hơn hẳn và **không lỗi nào hiện**.

    Trước lượt hiệu chỉnh, chốt này chỉ có một ví dụ tôi tự gõ. Nay nó có sáu trang thật.
    """
    kq = phan_loai(["漢" * han + "あ" * kana + "a" * latin])
    assert kq.bang_chung.han / kq.bang_chung.tong_co_nghia >= TI_LE_HAN_TOI_THIEU, (
        f"{ten_trang}: ví dụ phải THẬT SỰ vượt ngưỡng Hán, không thì không canh được gì"
    )
    assert kq.ngon_ngu is SourceLang.ja


def test_trang_ghi_cong_tieng_Trung_KHONG_bi_ket_luan_thanh_tieng_Anh():
    """Lượt SAI DUY NHẤT trong 37 trang thật, trước khi thêm `SO_HAN_TOI_THIEU`.

    `cn_…E03P08` (trang ghi công cuối chương): **121 chữ Hán** giữa **1097 chữ Latin** (tên người,
    URL, giấy phép) ⇒ tỉ lệ Hán chỉ **9,9%**, dưới ngưỡng 20% ⇒ ra `en`.

    Trang cùng số bản tiếng Nhật (109 kana / 1099 Latin) thì ĐÚNG — vì ngưỡng kana đếm số **tuyệt
    đối**. Bài học đã thành luật: một hệ chữ có mặt hàng trăm ký tự thì nó CÓ mặt, bất kể bị bao nhiêu
    chữ Latin làm loãng.
    """
    kq = phan_loai(["中" * 121 + "a" * 1097])
    assert kq.bang_chung.han == 121
    assert kq.bang_chung.han / kq.bang_chung.tong_co_nghia < TI_LE_HAN_TOI_THIEU, (
        "ví dụ phải DƯỚI ngưỡng tỉ lệ, không thì nó không canh được nhánh số tuyệt đối"
    )
    assert kq.ngon_ngu is SourceLang.zh


def test_trang_ghi_cong_tieng_Nhat_van_ra_ja_du_bi_Latin_ap_dao():
    """Đối chứng cặp với bài trên: cùng một trang, bản tiếng Nhật, cùng bị Latin áp đảo."""
    kq = phan_loai(["あ" * 109 + "漢" * 30 + "a" * 1099])
    assert kq.bang_chung.latin > kq.bang_chung.kana * 9
    assert kq.ngon_ngu is SourceLang.ja


def test_trang_tieng_Anh_THAT_do_duoc_0_chu_Han():
    """9 nhóm ảnh tiếng Anh (gồm nhóm làm nhiễu, nền rối, chữ mảnh nghiêng) đo được Hán = **0** ở tất
    cả. Nên `SO_HAN_TOI_THIEU = 8` cách biên thật rất xa — đó là điều bài này ghim lại.

    Nếu ngày nào OCR bắt đầu sinh chữ Hán rác trên chữ Latin, ngưỡng 8 là chỗ đầu tiên phải xem lại.
    """
    kq = phan_loai(["WHAT ARE YOU DOING HERE", "I can't believe he said that"])
    assert kq.bang_chung.han == 0
    assert kq.ngon_ngu is SourceLang.en


def test_it_hon_nguong_tuyet_doi_va_duoi_ti_le_thi_KHONG_thanh_tieng_Trung():
    """Đối chứng âm cho nhánh số tuyệt đối: 7 chữ Hán (< 8) giữa nhiều chữ Latin phải ra `en`, không
    được vì có vài chữ Hán rác mà lật cả trang."""
    kq = phan_loai(["漢" * 7 + "a" * 200])
    assert kq.bang_chung.han == 7
    assert kq.ngon_ngu is SourceLang.en


def test_trang_THAT_it_chu_nhat_van_ket_luan_duoc():
    """Trang thật ít chữ nhất đo được: bản Trung 10 ký tự, bản Nhật 12 ký tự. Nên
    `SO_KY_TU_TOI_THIEU = 8` là đúng — nâng lên 15 là làm hai trang thật này thành "không kết luận"."""
    assert phan_loai(["中" * 10]).ngon_ngu is SourceLang.zh
    assert phan_loai(["あ" * 5 + "abcdefg"]).ngon_ngu is SourceLang.ja


def test_moi_trang_Trung_THAT_deu_co_0_kana():
    """11/11 trang tiếng Trung thật đo được **0 kana**, còn trang Nhật thật ít kana nhất có **3**.
    Tín hiệu kana sạch tuyệt đối trên dữ liệu thật ⇒ `SO_KANA_TOI_THIEU = 2` nằm giữa 0 và 3."""
    assert SO_KANA_TOI_THIEU == 2
    assert phan_loai(["中" * 50]).ngon_ngu is SourceLang.zh          # 0 kana
    assert phan_loai(["あいう" + "中" * 50]).ngon_ngu is SourceLang.ja  # 3 kana — trang thật ít nhất


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
