"""E39 — trang bạt/danh sách tên không được đẻ ra ứng viên thuật ngữ, và trích dẫn phải ngắn.

Bối cảnh: chạy thật ep39 bản tiếng Anh (14-09), trang 12 là trang bạt liệt kê hàng nghìn tên
người tài trợ. Màn "Tìm danh xưng trong chapter" trả về `David` 8 lần, `Alex` 7, `Christian` 7,
`Michael` 7, `Paul` 6 — **toàn bộ đều ở trang 12**, không một lần nào trong truyện.

## Vì sao ngưỡng ở đây đo được chứ không phải chọn

Bản đầu chốt trần 20 từ dựa trên **n = 3 lời thoại** của một chapter. Đó là cỡ mẫu quá nhỏ để đổi
logic production, nên đã đo lại trên **211 vùng `OCRStatus.ok` tiếng Anh thật** (3 chapter, DB
dev):

    vùng >= 20 từ:            10 / 211  (4,8%)
    số từ nhóm được GIỮ:      22, 23, 24, 26
    số từ nhóm bị BỎ:         146, 194, 402, 498, 503, 723   <- khoảng trống 26->146 RỖNG

Mọi trần trong khoảng 20..146 cho ra **cùng 6 vùng** bị bỏ. Nên trần nâng lên **100**: cùng kết
quả trên dữ liệu đã đo, nhưng có lề 3,8 lần so với lời thoại dài nhất từng thấy. Lề đó là thứ bảo
vệ chapter CHƯA đo — và chính nó biến ca `test_loi_thoai_cut_lun_dai_KHONG_bi_loai_oan` dưới đây
từ đỏ thành xanh.

## Về dữ liệu mẫu

Dòng ghi công của bộ truyện là **thật** (attribution mà CC-BY yêu cầu công bố). Khối danh sách lớn
thì dựng tổng hợp: giữ nguyên tính chất cấu trúc đã đo nhưng KHÔNG chép hàng trăm tên người thật
vào repo.
"""
from __future__ import annotations

import pytest
from app.services.consistency.ungvien import (
    DO_DAI_TRICH_DAN,
    SO_TU_TOI_THIEU_XET_LIET_KE,
    TI_LE_TU_NOI_TOI_THIEU,
    DongChu,
    UngVien,
    _cat_trich_dan,
    _CHAN_EN,
    _rut_en,
    _TU_EN,
    la_khoi_liet_ke,
)

# ---------------------------------------------------------------- số đo trên 211 vùng thật

#: Lời thoại dài nhất trong 211 vùng tiếng Anh thật: 26 từ. Trần phải cách nó một lề rõ ràng.
LOI_THOAI_DAI_NHAT_DO_DUOC = 26
#: Khối trang bạt NHỎ nhất trong cùng mẫu: 146 từ. Trần phải nằm dưới nó, nếu không thì vô dụng.
KHOI_LIET_KE_NHO_NHAT_DO_DUOC = 146
#: Tỉ lệ từ nối CAO nhất trong 6 khối bị bỏ — mốc dưới của lề ngưỡng.
TI_LE_CAO_NHAT_CUA_KHOI_BI_BO = 0.057
#: Tỉ lệ từ nối THẤP nhất trong các vùng >= 20 từ được giữ — mốc trên của lề ngưỡng.
TI_LE_THAP_NHAT_CUA_VUNG_DUOC_GIU = 0.192

#: Dòng ghi công THẬT của bộ truyện (attribution công khai theo CC-BY): 30 từ, 3,3% từ nối.
GHI_CONG_THAT = (
    "Creator: David Revoy. Writers: Craig Maloney, Nicolas Artance, Scribblemaniac, Valvin. "
    "Correctors: Willem Sonke, Moini, Hali, CGand, Alex Gryson. Software: Krita 5.2.9, "
    "Inkscape 1.2 on Debian 12 KDE License: Creative Commons Attribution 4.0. ww penpercarrot-com"
)

#: Lời thoại THẬT của cùng chapter: 10–14 từ, 38,5–57,1% từ nối.
THOAI_THAT = [
    '.. AND YOU SEE, WHEN YOU SCREAMED "AHHHHHH!!!!", WELL, THAT\'S WHEN I THREW MY AXE!',
    "THE AXE RICOCHETED, MUHAHAHA!!! AND THE NOISE TRUE THAT! DISTRACTED THOSE CURSED CREATURES!",
    "THE AXE RICOCHETED, AND THE NOISE DISTRACTED THOSE CURSED CREATURES!",
]

#: Ca NGUY HIỂM NHẤT của luật này: nhân vật đọc một danh sách trong truyện. Dài hơn 20 từ, gần
#: như không có từ nối — nếu trần còn ở 20 thì đây là lời thoại thật bị loại oan.
THOAI_CUT_LUN_DAI = (
    "POTIONS, HERBS, CAULDRON, MANDRAKE ROOT, DRAGON SCALE, PHOENIX FEATHER, MOONSTONE, "
    "NIGHTSHADE, WOLFSBANE, SILVER DUST, RAVEN QUILL, TOADSTOOL, AMBER RESIN, IRON FILINGS!"
)

_TEN_DUNG = ["Zarniwoop", "Slartibartfast", "Prosser", "Kwaltz", "Hurtenflurst", "Poodoo",
             "Vroomfondel", "Majikthise", "Garkbit", "Hotblack"]


def danh_sach_ten(so_luong: int = 80) -> str:
    """Khối liệt kê tổng hợp: tên nối bằng ★, đúng hình dạng một trang bạt tài trợ.

    Mỗi mục là 2 từ nên `so_luong=80` cho 160 từ — cùng cỡ với khối thật nhỏ nhất (146 từ).
    """
    return " ★ ".join(_TEN_DUNG[i % len(_TEN_DUNG)] + f" {chr(65 + i % 26)}."
                      for i in range(so_luong))


def so_tu(text: str) -> int:
    return len([m for m in _TU_EN.finditer(text)])


def ti_le_tu_noi(text: str) -> float:
    tu = [m.group(0) for m in _TU_EN.finditer(text)]
    return sum(1 for w in tu if w.lower() in _CHAN_EN) / len(tu) if tu else 0.0


# ---------------------------------------------------------------- nhận biết khối liệt kê


class TestNhanBietKhoiLietKe:
    def test_khoi_trang_bat_bi_bo(self):
        khoi = danh_sach_ten()
        assert so_tu(khoi) >= KHOI_LIET_KE_NHO_NHAT_DO_DUOC - 20, (
            "mẫu phải cùng cỡ với khối trang bạt thật, không thì test không nói gì"
        )
        assert la_khoi_liet_ke(khoi)

    @pytest.mark.parametrize("cau", THOAI_THAT)
    def test_loi_thoai_that_duoc_giu(self, cau):
        assert not la_khoi_liet_ke(cau), "bỏ oan lời thoại = người dùng mất đúng thứ họ cần"

    def test_loi_thoai_cut_lun_dai_KHONG_bi_loai_oan(self):
        """Ca false negative mà người dùng chỉ ra — và nó CÓ THẬT là nguy hiểm.

        Nhân vật đọc một danh sách trong truyện: dài hơn 20 từ, gần như không có từ nối. Đây
        đúng là hình dạng mà luật này dễ bắn oan nhất.

        Test này **sẽ ĐỎ nếu trần trở về 20**, nên nó canh đúng lý do trần được nâng lên 100 —
        không phải chỉ viết lại ngưỡng dưới dạng test.
        """
        n = so_tu(THOAI_CUT_LUN_DAI)
        r = ti_le_tu_noi(THOAI_CUT_LUN_DAI)
        assert n > 20, f"mẫu chỉ {n} từ — không chạm được trần cũ thì test rỗng nghĩa"
        assert r < TI_LE_TU_NOI_TOI_THIEU, (
            f"mẫu có {r:.1%} từ nối — trên ngưỡng thì nó vô hại và test rỗng nghĩa"
        )
        assert not la_khoi_liet_ke(THOAI_CUT_LUN_DAI), (
            "lời thoại thật bị loại oan — đây là thiệt hại trực tiếp cho người dùng"
        )

    def test_dong_ghi_cong_ngan_khong_bi_bo__gioi_han_da_biet(self):
        """Giới hạn ĐÃ BIẾT, ghi ra chứ không giấu.

        Dòng ghi công 30 từ (3,3% từ nối) **không** bị bỏ vì dưới trần 100. Chấp nhận được vì:
        trên 211 vùng thật, các khối cỡ đó (22–26 từ) có 19,2–54,2% từ nối và là chữ thật cần
        giữ; còn thiệt hại đo được trong lượt chạy ep39 đến từ khối 146–723 từ, không phải từ
        dòng này. Nó góp đúng 1 lần cho mỗi tên, mà ngưỡng lặp của `en` là 2 lần.
        """
        assert so_tu(GHI_CONG_THAT) < SO_TU_TOI_THIEU_XET_LIET_KE
        assert not la_khoi_liet_ke(GHI_CONG_THAT)

    def test_tran_co_le_so_voi_loi_thoai_dai_nhat_do_duoc(self):
        """Trần phải nằm GIỮA lời thoại dài nhất và khối liệt kê nhỏ nhất đã đo."""
        assert LOI_THOAI_DAI_NHAT_DO_DUOC * 3 <= SO_TU_TOI_THIEU_XET_LIET_KE, (
            f"trần {SO_TU_TOI_THIEU_XET_LIET_KE} không có lề 3x so với "
            f"{LOI_THOAI_DAI_NHAT_DO_DUOC} từ"
        )
        assert SO_TU_TOI_THIEU_XET_LIET_KE < KHOI_LIET_KE_NHO_NHAT_DO_DUOC, (
            "trần vượt khối liệt kê nhỏ nhất ⇒ luật không bỏ được gì nữa"
        )

    def test_nguong_co_le_ve_ca_hai_phia_theo_so_do_that(self):
        """Ngưỡng nằm giữa hai đám ĐO ĐƯỢC, không chỉ đúng tình cờ với mẫu trong tệp này."""
        assert TI_LE_CAO_NHAT_CUA_KHOI_BI_BO < TI_LE_TU_NOI_TOI_THIEU \
            < TI_LE_THAP_NHAT_CUA_VUNG_DUOC_GIU, (
                f"khối bị bỏ cao nhất {TI_LE_CAO_NHAT_CUA_KHOI_BI_BO:.1%}, ngưỡng "
                f"{TI_LE_TU_NOI_TOI_THIEU:.0%}, vùng được giữ thấp nhất "
                f"{TI_LE_THAP_NHAT_CUA_VUNG_DUOC_GIU:.1%}"
            )

    def test_chi_ap_cho_tieng_anh(self):
        """Chữ Nhật không có `_CHAN_EN` nào nên tỉ lệ từ nối luôn 0 — gọi hàm này với `ja` sẽ
        bỏ sạch mọi vùng đủ dài. Đó là lý do `rut_ung_vien` chỉ gọi nó khi `lang == "en"`."""
        assert ti_le_tu_noi("ペッパーさん、こんにちは。魔法を使う") == 0.0

    def test_chay_hai_lan_ra_y_het(self):
        khoi = danh_sach_ten()
        assert la_khoi_liet_ke(khoi) == la_khoi_liet_ke(khoi)


class TestDuLieuThatCoDoc:
    """Chống rỗng nghĩa: chứng minh mẫu THẬT đẻ ra rác TRƯỚC, rồi mới nói bộ lọc có ích."""

    def test_khong_loc_thi_ten_e_kip_thanh_ung_vien(self):
        kho: dict[str, UngVien] = {}
        _rut_en([DongChu(page_order=12, region_id="r1", text=GHI_CONG_THAT)], kho, False)
        assert "david" in kho and "alex" in kho, (
            "nếu mẫu này KHÔNG đẻ ra rác thì mọi test lọc bên trên đều rỗng nghĩa"
        )

    def test_khoi_liet_ke_khong_loc_thi_de_ra_rat_nhieu(self):
        kho: dict[str, UngVien] = {}
        _rut_en([DongChu(page_order=12, region_id="r1", text=danh_sach_ten())], kho, False)
        assert len(kho) >= 10, f"chỉ {len(kho)} ứng viên — mẫu chưa đủ độc để test có nghĩa"


# ---------------------------------------------------------------- cắt trích dẫn


class TestCatTrichDan:
    def test_da_ngan_thi_khong_doi(self):
        for cau in THOAI_THAT:
            assert _cat_trich_dan(cau, (0, 3)) == cau

    def test_cat_ngan_lai_va_danh_dau(self):
        dai = danh_sach_ten(200)
        vt = dai.find("Garkbit")
        ra = _cat_trich_dan(dai, (vt, vt + 7))
        assert len(ra) <= DO_DAI_TRICH_DAN + 2, f"vẫn dài {len(ra)}"
        assert "…" in ra, "cắt mà không đánh dấu thì người đọc tưởng đó là cả vùng chữ"
        assert len(dai) > 1000

    def test_khong_bao_gio_cat_mat_cho_khop(self):
        """Tính chất quan trọng nhất: chỗ khớp là thứ người dùng cần thấy để tin con số."""
        dai = danh_sach_ten(200)
        vt = 0
        so_lan = 0
        while True:
            vt = dai.find("Poodoo", vt)
            if vt < 0:
                break
            ra = _cat_trich_dan(dai, (vt, vt + 6))
            assert "Poodoo" in ra, f"mất chỗ khớp ở vị trí {vt}"
            assert len(ra) <= DO_DAI_TRICH_DAN + 2
            so_lan += 1
            vt += 6
        assert so_lan >= 10, f"chỉ thử được {so_lan} vị trí — chưa đủ để gọi là tính chất"

    def test_khong_co_span_van_cat_duoc(self):
        ra = _cat_trich_dan(danh_sach_ten(200), None)
        assert len(ra) <= DO_DAI_TRICH_DAN + 2

    def test_trich_dan_cua_ung_vien_da_ngan_lai(self):
        """Nối vào đường chạy thật: `_rut_en` chứ không phải bản chép lại của thuật toán."""
        kho: dict[str, UngVien] = {}
        _rut_en([DongChu(page_order=12, region_id="r1", text=danh_sach_ten(200))], kho, False)
        assert kho, "mẫu không đẻ ra ứng viên nào ⇒ test này rỗng nghĩa"
        for uv in kho.values():
            for q in uv.quotes:
                assert len(q.text) <= DO_DAI_TRICH_DAN + 2, (
                    f"trích dẫn của {uv.term!r} dài {len(q.text)} ký tự"
                )
