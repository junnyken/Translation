"""E65 — tách độ phân giải VẼ khỏi độ phân giải ĐỌC.

## Vấn đề, đo trên trang thật của chủ dự án (28-09-2026)

Trang 368×543, bong bóng tiếng Nhật xếp chữ dọc nên khung chữ rộng 10–34px. Từ tiếng Việt nằm
ngang và dài hơn nhiều. Đo bằng chính phông và cỡ chữ nhỏ nhất của hệ thống:

```
12/19 bong bóng KHÔNG chứa nổi MỘT từ ở cỡ chữ nhỏ nhất (10px)
chật nhất: ô còn 8px sau lề, từ "Aliator" cần 27px
```

Người dùng thấy: `ĐỘT NHIÊN` → `ĐỘ T / NHI / ẾN`, `AKI-CHAN` → `AKI-CHA / N`.

## Vì sao KHÔNG phóng ảnh ĐẦU VÀO

Đã chạy thật cả hai đường trên production và so:

| Ảnh vào | Bong bóng không chứa nổi một từ | Chất lượng đọc chữ |
|---|---|---|
| 368×543 (gốc) | **12/19** | tên riêng đúng: `SEYAMA`, `AKI-CHAN` |
| 1200×1770 (phóng) | 3/14 | **sai**: `MUYAMA`, `LAI-CHAN`, câu vô nghĩa |

Phóng ảnh vào sửa được hình học nhưng phá chất lượng đọc. E65 phóng ở **bước vẽ**, sau khi đọc
và dịch đã xong trên ảnh gốc.
"""
from __future__ import annotations

import glob

import pytest
from PIL import Image, ImageFont

from app.services.interfaces import BBox
from app.services.typeset.fitter import FitToBoxTypesetter
from app.services.typeset.preview import PagePreviewRenderer, RegionDraw
from app.services.typeset.ti_le_ve import (
    BUOC_LAM_TRON,
    TRAN_CANH_DAI_PX,
    TRAN_HE_SO,
    tinh_he_so_ve,
)

FONT = glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)[0]
CO_NHO_NHAT = 10


class _Resolver:
    def resolve(self, _family: str, size: int):
        return ImageFont.truetype(FONT, int(size))

    def assert_can_render(self, _font, _text) -> None:
        return None


#: Cỡ trang THẬT của chủ dự án — mọi bài dưới đây đo ở đúng khổ đó trừ khi nói khác.
TRANG_THAT = (368, 543)


def _he_so(khung_chu, co_anh=TRANG_THAT) -> float:
    return tinh_he_so_ve(
        khung_chu, _Resolver(), font_family="bất kỳ", co_chu_nho_nhat=CO_NHO_NHAT,
        co_anh=co_anh,
    )


def _rong_tu(tu: str) -> float:
    return ImageFont.truetype(FONT, CO_NHO_NHAT).getlength(tu)


# ── Hệ số phóng ───────────────────────────────────────────────────────────────────────────


def test_trang_DA_DU_RONG_thi_KHONG_phong_gi_ca():
    """ĐỐI CHỨNG ÂM, và là bài quan trọng nhất của lượt này.

    Trang quét độ phân giải tốt phải đi qua E65 mà **không bị đụng vào**: không phóng, không nội
    suy, không phình dung lượng. Một bản vá "luôn phóng cho chắc" sẽ làm xấu đi mọi trang vốn đang
    đúng — đắt hơn nhiều so với lỗi đang sửa.
    """
    rong = _rong_tu("NGHIÊNG") * 3        # thừa chỗ
    assert _he_so([(rong, "NGHIÊNG NGẢ ĐÂY LÀ MỘT CÂU DÀI")]) == 1.0


def test_khong_co_chu_thi_khong_phong():
    assert _he_so([(5.0, ""), (5.0, "   "), (5.0, None)]) == 1.0


def test_CAU_dai_hon_khung_KHONG_lam_phong___chi_TU_dai_moi_lam():
    """Câu dài hơn khung là chuyện bình thường: nó xuống dòng. Chỉ TỪ dài hơn khung mới là chỗ
    không còn cách vẽ nào đúng.

    Không có bài này thì dễ viết nhầm thành đo cả câu — và mọi trang đều bị phóng kịch trần vì
    trang nào cũng có câu dài hơn một bong bóng.
    """
    rong = _rong_tu("NGHIÊNG") + 2
    assert _he_so([(rong, "NGHIÊNG NGẢ RẤT NHIỀU TỪ NỮA Ở ĐÂY")]) == 1.0


def test_tai_hien_dung_so_do_cua_trang_that():
    """Ô còn 8px, từ cần 27px ⇒ phải phóng ít nhất 27/8 = 3,375 lần."""
    tu = "Aliator"
    can = _rong_tu(tu) / 8.0
    k = _he_so([(8.0, tu)])
    assert k >= can, f"phóng {k} vẫn chưa đủ cho tỉ lệ cần {can}"
    assert k <= TRAN_HE_SO


def test_lay_cho_CHAT_NHAT_cua_trang_chu_khong_lay_trung_binh():
    """Một vùng chật mà các vùng khác rộng thì vẫn phải phóng theo vùng chật — lấy trung bình là
    bỏ mặc đúng chỗ đang hỏng."""
    rong_rai = _rong_tu("Chào") * 4
    k = _he_so([(rong_rai, "Chào"), (rong_rai, "Ừm"), (4.0, "Umi-chan?")])
    assert k > 1.0
    assert k == _he_so([(4.0, "Umi-chan?")])


def test_khong_vuot_TRAN_TUYET_DOI_khi_khong_biet_co_anh():
    """Bong bóng chật vô lý không được kéo ảnh phình vô hạn."""
    k = _he_so([(0.5, "MộtTừRấtDàiKhôngCóKhoảngTrắngChútNào")], co_anh=None)
    assert k == TRAN_HE_SO


def test_TRAN_theo_CANH_DAI_anh_ra___khong_phai_theo_ti_le():
    """Thứ phải chặn là CHI PHÍ, mà chi phí đi theo số điểm ảnh của ảnh ra.

    Bản đầu của E65 chỉ chặn theo tỉ lệ (4,0) và sai ở cả hai đầu:

    * trang LỚN vẫn phình kinh hoàng — 2000px × 4 = 8000px (≈94 triệu điểm, đủ giết worker);
    * trang NHỎ bị cắt nhầm đúng ca đang sửa — trang thật cần 4,22 cho bong bóng "Umi-chan?",
      trần 4,0 bỏ lại đúng một bong bóng vỡ, nhìn y như chưa sửa gì.
    """
    chat = [(0.5, "MộtTừRấtDàiKhôngCóKhoảngTrắngChútNào")]

    nho = _he_so(chat, co_anh=(368, 543))
    lon = _he_so(chat, co_anh=(2000, 3000))

    assert 543 * nho <= TRAN_CANH_DAI_PX + 1, "trang nhỏ vượt trần cạnh dài"
    # Trang VỐN đã lớn hơn trần thì giữ nguyên — trần chặn mức PHÓNG THÊM, không phải chặn kích
    # thước sẵn có. (Khẳng định đầu tôi viết ở đây là `3000 * lon <= 2400`, và nó sai: nó đòi hệ
    # thống THU NHỎ ảnh của người dùng.)
    assert lon == 1.0, "trang đã lớn hơn trần thì không được phóng thêm chút nào"
    assert nho > lon, "trang nhỏ phải được phóng NHIỀU hơn trang lớn, không phải cùng một tỉ lệ"


def test_trang_LON_gan_nhu_khong_duoc_phong():
    """Đối chứng: trang quét tốt (2400px) đã đạt trần cạnh dài nên hệ số về 1,0 — dù có vùng
    chật. Đúng ý: trang lớn thì bong bóng vốn đã đủ rộng, phóng chỉ tốn chỗ."""
    assert _he_so([(0.5, "TừRấtDài")], co_anh=(1600, 2400)) == 1.0


def test_KHONG_bo_lai_bong_bong_Umi_chan_cua_trang_that():
    """Ca đã làm tôi phải đổi thiết kế: ô còn 9px, từ "Umi-chan?" cần 38px ở phông thật ⇒ 4,22×.

    Trần tỉ lệ 4,0 của bản đầu **loại đúng bong bóng này**. Bài canh giữ lại bài học đó: hệ số
    phải đủ cho từ dài nhất, chừng nào ảnh ra còn trong trần cạnh dài.
    """
    # Số đo THẬT, bằng phông thật (Bangers) trên trang thật — chép từ phép đo 28-09, KHÔNG đo
    # lại bằng DejaVu ở đây: phông test rộng hơn phông thật nên nó sẽ ra một con số khác và biến
    # bài này thành bài canh của DejaVu.
    CAN_THAT = 38.0 / 9.0          # từ "Umi-chan?" cần 38px trong ô còn 9px
    assert CAN_THAT > 4.0, "tiền đề: ca này vượt trần tỉ lệ 4,0 của bản đầu"
    assert TRAN_CANH_DAI_PX / 543 >= CAN_THAT, (
        "trần cạnh dài phải đủ rộng cho đúng ca đã làm tôi đổi thiết kế"
    )


def test_he_so_lam_tron_len_theo_buoc():
    """Không làm tròn thì mỗi trang trong cùng một chapter ra một kích thước ảnh khác nhau."""
    k = _he_so([(8.0, "Aliator")])
    assert abs(k / BUOC_LAM_TRON - round(k / BUOC_LAM_TRON)) < 1e-9, f"{k} không phải bội của bước"


# ── Hệ quả thật: hết cắt giữa từ ───────────────────────────────────────────────────────────


def _co_cat_giua_tu(wrapped: str, nguyen_van: str) -> bool:
    tu_that = set(nguyen_van.split())
    return any(tu not in tu_that for dong in wrapped.split("\n") for tu in dong.split())


def test_KHUNG_PHONG_LEN_thi_het_cat_giua_tu___doi_chung_cap():
    """Bài canh nặng nhất: **cùng một câu, cùng một bong bóng**, chỉ khác là có nhân hệ số hay không.

    Trước: khung 12×42 (đúng cỡ đo được trên trang thật) ⇒ buộc cắt giữa từ.
    Sau: nhân hệ số ⇒ từ nguyên vẹn.
    """
    cau = "Đột nhiên!"
    bo_can = FitToBoxTypesetter(
        font_resolver=_Resolver(), min_font_size=CO_NHO_NHAT, max_font_size=40,
        padding_ratio=0.09, line_spacing_ratio=0.2, stroke_width=0,
    )

    truoc = bo_can.fit(cau, BBox(x=0, y=0, w=12, h=42), "bất kỳ")
    assert _co_cat_giua_tu(truoc["wrapped_text"], cau), (
        "khung 12px mà KHÔNG cắt giữa từ thì tiền đề của E65 sai — đọc lại phép đo"
    )

    k = _he_so([(12 * (1 - 2 * 0.09), cau)])
    sau = bo_can.fit(cau, BBox(x=0, y=0, w=12 * k, h=42 * k), "bất kỳ")
    assert not _co_cat_giua_tu(sau["wrapped_text"], cau), (
        f"phóng {k}× rồi mà vẫn cắt: {sau['wrapped_text']!r}"
    )


# ── Bộ vẽ ──────────────────────────────────────────────────────────────────────────────────


def _anh_tam(tmp_path, co=(100, 60)) -> str:
    duong = tmp_path / "clean.png"
    Image.new("RGB", co, "white").save(duong)
    return str(duong)


def _vung() -> RegionDraw:
    return RegionDraw(
        bbox=BBox(x=10, y=10, w=40, h=20), wrapped_text="Chào", font_family="bất kỳ",
        font_size=12, padding_ratio=0.09,
    )


def _bo_ve(**kw) -> PagePreviewRenderer:
    tham = dict(font_resolver=_Resolver(), line_spacing_ratio=0.2)
    tham.update(kw)
    return PagePreviewRenderer(**tham)


def test_he_so_1_thi_anh_ra_GIU_NGUYEN_kich_thuoc():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        anh = _anh_tam(Path(d))
        ra = _bo_ve().draw(anh, [_vung()])
        assert ra.size == (100, 60)


def test_he_so_2_thi_anh_ra_GAP_DOI():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        anh = _anh_tam(Path(d))
        ra = _bo_ve(he_so_ve=2.0).draw(anh, [_vung()])
        assert ra.size == (200, 120)


def test_he_so_truyen_theo_TUNG_LUOT_ve_de_xuat_chapter_dung():
    """Xuất cả chapter dùng CHUNG một renderer cho mọi trang, mà hệ số là của từng trang. Ghim hệ
    số vào renderer thì mọi trang bị phóng theo trang đầu tiên."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        anh = _anh_tam(Path(d))
        bo = _bo_ve(he_so_ve=3.0)
        assert bo.draw(anh, [_vung()], he_so_ve=1.0).size == (100, 60)
        assert bo.draw(anh, [_vung()], he_so_ve=2.0).size == (200, 120)


def test_CHU_di_theo_khung_khi_phong___khong_nam_lai_goc_cu():
    """Phóng ảnh mà quên nhân toạ độ thì chữ dồn hết về góc trên-trái. Bài này đo CHỖ CÓ MỰC."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        anh = _anh_tam(Path(d))
        vung = RegionDraw(
            bbox=BBox(x=60, y=30, w=35, h=25), wrapped_text="Ừ", font_family="bất kỳ",
            font_size=12, padding_ratio=0.09,
        )
        ra = _bo_ve(he_so_ve=2.0).draw(anh, [vung])
        muc = ra.convert("L").point(lambda v: 255 if v < 128 else 0)
        hop = muc.getbbox()
        assert hop is not None, "không thấy chữ nào được vẽ"
        # Khung đã nhân 2 ⇒ chữ phải nằm quanh (120..190, 60..110), không phải quanh (60,30).
        assert hop[0] >= 110, f"chữ nằm ở {hop} — có vẻ toạ độ chưa được nhân hệ số"
        assert hop[1] >= 55, f"chữ nằm ở {hop} — có vẻ toạ độ chưa được nhân hệ số"


@pytest.mark.parametrize("k", [1.0, 1.5, 3.0])
def test_o_dat_chu_cung_duoc_nhan(k):
    """`place_rect` (ô trong lòng bong bóng của E14) cũng là toạ độ ảnh gốc — bỏ sót nó thì chữ
    của những vùng CÓ ô an toàn bị vẽ sai, còn vùng không có thì đúng: một lỗi nửa vời rất khó
    nhìn ra."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        anh = _anh_tam(Path(d), co=(200, 120))
        vung = RegionDraw(
            bbox=BBox(x=0, y=0, w=200, h=120), wrapped_text="Ừ", font_family="bất kỳ",
            font_size=10, padding_ratio=0.0, place_rect=(120.0, 70.0, 30.0, 20.0),
        )
        ra = _bo_ve(he_so_ve=k).draw(anh, [vung])
        hop = ra.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()
        assert hop is not None
        assert hop[0] >= 118 * k, f"k={k}: chữ ở {hop}, ô đặt chữ chưa được nhân"
