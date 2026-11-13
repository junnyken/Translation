"""Kiểm thử hồi quy bảo vệ nét khuôn mặt, mắt, viền sọ và viền halo trắng của chữ nổi."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.detect.ctd import DetectedRegion, loc_va_thu_hep_khung_ctd
from app.services.inpaint.mat_na_net import (
    _bao_ve_net_ve_va_da_trang_trong_o,
    loc_nhieu_net_ve_khoi_seg_crop,
)
from app.services.inpaint.to_phang import to_phang
from app.services.interfaces import BBox
from app.services.typeset.mau_chu import do_mau_chu

FONT = Path(__file__).resolve().parents[1] / "fonts" / "Bangers" / "Bangers-Regular.ttf"


def test_loc_nhieu_net_ve_khoi_seg_crop_loai_mat_nhieu_va_vien_dai():
    gray = np.full((120, 120), 255, dtype=np.uint8)
    seg = np.zeros((120, 120), dtype=np.uint8)

    # 1. Các nét chữ thật (có viền trắng quanh, seg phủ kín 100%)
    gray[18:38, 18:24] = 10
    gray[18:23, 18:36] = 10
    seg[18:38, 18:24] = 255
    seg[18:23, 18:36] = 255

    gray[18:38, 42:48] = 10
    gray[18:23, 42:60] = 10
    seg[18:38, 42:48] = 255
    seg[18:23, 42:60] = 255

    gray[18:38, 66:72] = 10
    gray[18:23, 66:84] = 10
    seg[18:38, 66:72] = 255
    seg[18:23, 66:84] = 255

    # 2. Nét mắt nheo nằm lệch một phần ngoài seg (`out_px >= 10`, `seg_cov < 0.80`)
    gray[60:66, 20:50] = 15
    seg[60:66, 36:50] = 255

    # 3. Nét mắt cô lập trên vùng da xám sáng (`no_halo_eye`: không có halo trắng 245+)
    gray[78:94, 58:92] = 225
    gray[83:87, 65:84] = 20
    seg[83:87, 65:84] = 255

    # 4. Nét viền sọ dựng đứng kéo dài (`tall_contour`)
    gray[25:80, 100:103] = 20
    seg[25:80, 100:103] = 255

    sach = loc_nhieu_net_ve_khoi_seg_crop(gray, seg, img_hw=(120, 120))
    assert sach[18:38, 18:24].any(), "nét chữ thật bị xoá oan khỏi seg"
    assert not sach[60:66, 36:50].any(), "mắt lệch biên seg vẫn sót trong seg"
    assert not sach[83:87, 65:84].any(), "mắt không halo vẫn sót trong seg"
    assert not sach[25:80, 100:103].any(), "viền sọ dài vẫn sót trong seg"


def test_bao_ve_net_ve_va_da_trang_trong_o_giu_net_noi_bo_va_da():
    anh = np.full((120, 120, 3), 255, dtype=np.uint8)
    # Vùng bóng xám trên mặt cạnh chữ
    anh[20:95, 15:95] = 195
    # Nét chữ thật (có halo trắng bao quanh)
    anh[26:48, 36:60] = 250
    anh[30:44, 40:44] = 15
    anh[30:44, 50:54] = 15
    # Mắt / lông mày nội bộ (không chạm biên ô cắt) nằm gần chữ
    anh[62:66, 28:46] = 20

    seg = np.zeros((120, 120), dtype=np.uint8)
    seg[30:44, 40:44] = 255
    seg[30:44, 50:54] = 255

    # Giả lập `no_va_bit` nở phủ rộng qua cả lông mày nội bộ lẫn da trắng
    net_no = np.zeros((120, 120), dtype=bool)
    net_no[20:76, 20:65] = True

    ket = _bao_ve_net_ve_va_da_trang_trong_o(anh, seg, net_no)
    assert ket[30:44, 40:44].all(), "ruột chữ thật phải được xoá"
    assert not ket[62:66, 28:46].any(), "nét mắt/lông mày nội bộ bị xoá oan"
    assert not ket[80:95, 70:90].any(), "vùng da sáng ngoài chữ bị đục lỗ oan"


def test_to_phang_bo_qua_khi_co_net_tranh_ngoai_seg():
    anh = np.full((200, 200, 3), 255, dtype=np.uint8)
    # Chữ thuộc seg bên trái
    anh[60:80, 50:56] = 15
    # Nét vẽ nhân vật không thuộc seg (cũng nằm trong khung)
    anh[95:98, 70:95] = 10
    goc_net = anh[95:98, 70:95].copy()

    seg = np.zeros((200, 200), dtype=np.uint8)
    seg[60:80, 50:56] = 255

    kq = to_phang(anh, [BBox(40, 40, 90, 90)], mat_na_chu=seg)
    assert kq.da_to == ()
    assert kq.con_lai == (0,)
    assert np.array_equal(anh[95:98, 70:95], goc_net)


def test_do_mau_chu_bat_vien_halo_trang_tren_nen_hon_hop():
    font = ImageFont.truetype(str(FONT), 36)

    # 1. Chữ đen có viền halo trắng đặt trên nền viền tối/vằn hỗn hợp
    im_halo = Image.new("RGB", (260, 110), (30, 30, 30))
    d1 = ImageDraw.Draw(im_halo)
    d1.rectangle((0, 0, 259, 45), fill=(35, 35, 35))
    d1.rectangle((0, 46, 259, 109), fill=(215, 215, 215))
    d1.text((30, 26), "AKAGI", font=font, fill=(0, 0, 0), stroke_width=3, stroke_fill=(255, 255, 255))
    b1 = d1.textbbox((30, 26), "AKAGI", font=font, stroke_width=3)
    m_halo = do_mau_chu(np.asarray(im_halo), BBox(b1[0] - 2, b1[1] - 2, b1[2] - b1[0] + 4, b1[3] - b1[1] + 4))
    assert m_halo is not None
    assert m_halo.mau == (0, 0, 0)
    assert m_halo.mau_vien == (255, 255, 255)
    assert (m_halo.vien or 0.0) >= 2.0

    # 2. Chữ đen trên bong bóng trắng sạch giữ nguyên không thêm viền trắng
    im_sach = Image.new("RGB", (260, 110), (255, 255, 255))
    d2 = ImageDraw.Draw(im_sach)
    d2.text((30, 26), "AKAGI", font=font, fill=(0, 0, 0))
    b2 = d2.textbbox((30, 26), "AKAGI", font=font)
    m_sach = do_mau_chu(np.asarray(im_sach), BBox(b2[0] - 3, b2[1] - 3, b2[2] - b2[0] + 6, b2[3] - b2[1] + 6))
    assert m_sach is not None
    assert m_sach.mau == (0, 0, 0)
    assert m_sach.mau_vien is None


def test_loc_va_thu_hep_khung_ctd_mo_rong_net_chu_tho_ra_khong_tach_hop_moi(tmp_path: Path):
    anh = np.full((140, 180, 3), 255, dtype=np.uint8)
    seg = np.zeros((140, 180), dtype=np.uint8)

    # Hai cột chữ tách biệt + một chữ cái lớn ở mép phải có thân nằm từ x=122..140, cao 36px
    for bx in (40, 68, 96):
        anh[40:76, bx : bx + 8] = 10
        seg[40:76, bx : bx + 8] = 255
    anh[40:76, 122:140] = 10
    seg[40:76, 122:140] = 255

    p_img = tmp_path / "protrude.png"
    Image.fromarray(anh).save(p_img)

    # Khung ban đầu bị cắt mất 8px bên phải của chữ cuối (x=132..140, 288px > ngưỡng 80px của `rem`)
    vung = [DetectedRegion(bbox=BBox(x=36.0, y=36.0, w=96.0, h=44.0), confidence=0.85, cls=0)]
    ket = loc_va_thu_hep_khung_ctd(str(p_img), vung, seg)

    assert len(ket) == 1, f"Không được tách phần chữ thò <=12px thành hộp mồ côi: {ket}"
    assert ket[0].bbox.x + ket[0].bbox.w >= 140.0

