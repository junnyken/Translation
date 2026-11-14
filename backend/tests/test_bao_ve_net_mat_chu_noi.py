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


def test_is_halo_on_black_bao_ve_ngon_toc_den_ngoai_seg():
    """`p1 #7`: mảng tóc đen đặc nối ra ngoài seg không bị `seg_dil`/`near_open_w` liếm mất."""
    anh = np.full((120, 120, 3), 255, dtype=np.uint8)
    anh[:95, :53] = 10
    anh[20:70, 53:72] = 10
    anh[52:88, 26:52] = 246
    anh[58:62, 32:46] = 12
    anh[58:82, 37:41] = 12

    seg = np.zeros((120, 120), dtype=np.uint8)
    seg[54:86, 28:50] = 255

    net_no = seg > 0
    ket = _bao_ve_net_ve_va_da_trang_trong_o(anh, seg, net_no)

    assert not ket[22:48, 53:70].any(), "ngọn tóc đen ngoài seg bị tẩy trắng oan"
    assert ket[58:82, 37:41].all(), "nét chữ trong halo không được xoá"


def test_panel_border_mask_bao_ve_bien_panel_ngang_doc():
    """`p4 #6`: đường viền đen khung panel có rãnh trắng bên ngoài không bị mask đè qua."""
    anh = np.full((100, 100, 3), 255, dtype=np.uint8)
    anh[11:14, :90] = 12
    anh[11:, 87:90] = 12
    anh[16:40, 54:85] = 210
    anh[20:36, 58:80] = 15

    seg = np.zeros((100, 100), dtype=np.uint8)
    seg[11:36, 58:88] = 255
    net_no = seg > 0

    ket = _bao_ve_net_ve_va_da_trang_trong_o(anh, seg, net_no)
    assert not ket[11:14, 10:55].any(), "viền đen ngang của panel bị xoá"
    assert not ket[45:90, 87:90].any(), "viền đen dọc của panel bị xoá"


def test_lama_khong_to_den_chu_sfx_vien_den_nen_trang(tmp_path: Path):
    """`p1 #3`: SFX chữ trắng viền đen mỏng trên nền giấy trắng không bị tô đen kịt trước LaMa."""
    from app.services.inpaint.lama import LamaInpainter

    anh = np.full((140, 140, 3), 255, dtype=np.uint8)
    anh[38:102, 38:102] = 10
    anh[41:99, 41:99] = 255

    seg = np.zeros((140, 140), dtype=np.uint8)
    seg[42:98, 42:98] = 255

    p_img = tmp_path / "hollow_sfx.png"
    Image.fromarray(anh).save(p_img)

    inp = LamaInpainter(weights_path="unused.onnx")
    inp._get_session = lambda: object()
    inp._chay_model = lambda rgb, mask: np.ones_like(rgb, dtype=np.float32)

    out_path = inp.inpaint(str(p_img), [BBox(x=30.0, y=30.0, w=80.0, h=80.0)], mat_na_chu=seg)
    out_arr = np.asarray(Image.open(out_path).convert("RGB"))
    assert float(out_arr[50:90, 50:90].mean()) > 200.0, "ruột chữ SFX trắng bị lấp đen kịt"


def test_loc_va_thu_hep_tach_bong_thoai_khep_kin_khoi_sfx_ben_ngoai(tmp_path: Path):
    """`p1 #11`: bóng thoại trắng khép kín có `rem` phải tách riêng khỏi SFX trôi bên trên."""
    anh = np.full((320, 320, 3), 205, dtype=np.uint8)
    anh[10:36, 10:36] = 15
    anh[177:273, 77:183] = 15
    anh[180:270, 80:180] = 255
    anh[205:245, 105:155] = 18
    anh[145:169, 95:165] = 20

    seg = np.zeros((320, 320), dtype=np.uint8)
    seg[10:36, 10:36] = 255
    seg[205:245, 105:155] = 255
    seg[145:169, 95:165] = 255

    p_img = tmp_path / "bubble_sfx_split.png"
    Image.fromarray(anh).save(p_img)

    primary = [DetectedRegion(bbox=BBox(x=10.0, y=10.0, w=26.0, h=26.0), confidence=0.90, cls=0)]
    ket = loc_va_thu_hep_khung_ctd(str(p_img), primary, seg)
    rem_boxes = [r for r in ket if r.bbox.x >= 50]
    assert len(rem_boxes) >= 2, f"Bóng thoại khép kín vẫn bị gộp chung SFX bên trên: {ket}"
    bubble_boxes = [r for r in rem_boxes if (r.bbox.y + r.bbox.h * 0.5) >= 180]
    sfx_boxes = [r for r in rem_boxes if (r.bbox.y + r.bbox.h * 0.5) < 175]
    assert bubble_boxes and sfx_boxes


def test_loc_va_thu_hep_chan_k_gom_qua_ranh_panel_va_bo_khuy_ao(tmp_path: Path):
    """`p1 #3` & `p5`: không bắc cầu `k_gom` qua rãnh panel và loại vòng khuy áo đơn hình học."""
    import cv2

    anh = np.full((360, 360, 3), 255, dtype=np.uint8)
    anh[10:36, 10:36] = 15
    # Panel trái & phải ngăn bởi 2 viền đen + rãnh trắng 6px (chữ 2 bên cách 10px <= k_gom 13px)
    anh[40:300, 148:150] = 12
    anh[40:300, 156:158] = 12
    anh[120:170, 120:148] = 15
    anh[120:170, 158:190] = 15

    seg = np.zeros((360, 360), dtype=np.uint8)
    seg[10:36, 10:36] = 255
    seg[120:170, 120:148] = 255
    seg[120:170, 158:190] = 255

    # Khuy áo tròn đơn giản trên áo choàng tối ở góc dưới (lọt `scov` nhưng là 1 vòng rỗng đơn giản)
    anh[240:284, 240:284] = 85
    cv2.circle(anh, (262, 262), 9, (15, 15, 15), 2)
    cv2.circle(seg, (262, 262), 9, 255, 2)

    p_img = tmp_path / "gutter_and_button.png"
    Image.fromarray(anh).save(p_img)

    primary = [DetectedRegion(bbox=BBox(x=10.0, y=10.0, w=26.0, h=26.0), confidence=0.90, cls=0)]
    ket = loc_va_thu_hep_khung_ctd(str(p_img), primary, seg)
    spanning = [r for r in ket if r.bbox.x < 145 and (r.bbox.x + r.bbox.w) > 165]
    assert not spanning, f"k_gom vẫn bắc cầu qua rãnh panel: {spanning}"
    btn = [r for r in ket if r.bbox.x >= 235 and r.bbox.y >= 235]
    assert not btn, f"Vòng khuy áo hình học vẫn lọt hậu kiểm: {btn}"


def test_vung_dang_xoa_chu_chan_ky_tu_hinh_hoc_1_chu_nhung_giu_chu_that():
    from app.services.ocr.engines import vung_dang_xoa_chu

    assert vung_dang_xoa_chu("O", 0.57, 0.42, 2) is False
    assert vung_dang_xoa_chu("OO", 0.65, 0.42, 2) is False
    assert vung_dang_xoa_chu("0", 0.60, 0.42, 2) is False
    assert vung_dang_xoa_chu("中", 0.55, 0.42, 2) is False
    assert vung_dang_xoa_chu("GO", 0.55, 0.42, 2) is True
    assert vung_dang_xoa_chu("But...", 0.55, 0.42, 2) is True
    assert vung_dang_xoa_chu("はい", 0.55, 0.42, 2) is True
    assert vung_dang_xoa_chu("O", 0.57, 0.0, 2) is True


def test_ha_tang_nginx_bo_nho_tasks_va_deploy_start_lf():
    import re
    goc = Path(__file__).resolve().parents[2]

    nginx_conf = re.sub(r"#.*", "", (goc / "frontend" / "default.conf.template").read_text(encoding="utf-8"))
    assert "resolver " in nginx_conf and "$upstream_api_backend" in nginx_conf
    assert re.search(r"location\s*=\s*/healthz\s*\{[^}]*return\s+200\b", nginx_conf, re.S)
    locs = re.findall(r"^\s*location\b[^{]*\{[^}]*\}", nginx_conf, re.M | re.S)
    assert locs and all("add_header" not in blk for blk in locs)

    from app.workers import bo_nho
    assert isinstance(bo_nho.ep_nha_heap_he_dieu_hanh(), bool)

    tasks_src = (goc / "backend" / "app" / "workers" / "tasks.py").read_text(encoding="utf-8")
    assert "_KHOA_MO_HINH_CUC_BO = threading.RLock()" in tasks_src
    assert "def _run_xoa_vung_to(" in tasks_src and tasks_src.count("with _KHOA_MO_HINH_CUC_BO:") >= 8

    sh_bytes = (goc / "backend" / "deploy-start.sh").read_bytes()
    assert b"\r" not in sh_bytes, "deploy-start.sh vẫn còn CRLF"
    sh_text = sh_bytes.decode("utf-8")
    assert "WORKER_READY_FILE=" in sh_text
    assert 'rm -f "$WORKER_READY_FILE"' in sh_text
    assert 'ghi_trang_thai starting "$SO_LAN_CHET" "$MA_CU"' in sh_text


def test_loc_va_thu_hep_khong_xe_nho_halo_chu_tren_toc_den_va_bo_vien_tam_giac(tmp_path: Path):
    """`p1` halo trắng trên tóc đen không tách hộp lồng nhau & `p4` viền tam giác bị loại."""
    import cv2

    anh = np.full((340, 340, 3), 255, dtype=np.uint8)
    anh[10:36, 10:36] = 15

    # Khối thoại nền tóc đen có sớ sáng tóc (không phải viền panel) và halo trắng ôm sát 2 dòng (`px_in / wb_area > 0.58`)
    anh[100:220, 40:140] = 15
    anh[100:220, 64:66] = 200
    anh[100:220, 114:116] = 200
    anh[112:142, 62:118] = 255
    anh[117:137, 67:113] = 15
    anh[148:188, 52:128] = 255
    anh[153:183, 57:123] = 15

    seg = np.zeros((340, 340), dtype=np.uint8)
    seg[10:36, 10:36] = 255
    seg[112:142, 62:118] = 255
    seg[148:188, 52:128] = 255

    # Cột tam giác trang trí nhỏ trên nền trắng ở bên phải (`min <= 56`, `scov < 0.26`, `area < 180`)
    for ty in (100, 124, 148, 172):
        tri = np.array([[260, ty], [272, ty + 6], [260, ty + 12]], dtype=np.int32)
        cv2.polylines(anh, [tri], True, (20, 20, 20), 2)
        cv2.polylines(seg, [tri], True, 255, 2)

    p_img = tmp_path / "halo_and_tri.png"
    Image.fromarray(anh).save(p_img)

    primary = [DetectedRegion(bbox=BBox(x=10.0, y=10.0, w=26.0, h=26.0), confidence=0.90, cls=0)]
    ket = loc_va_thu_hep_khung_ctd(str(p_img), primary, seg)

    hair_boxes = [r for r in ket if 35 <= r.bbox.x <= 140 and r.bbox.y >= 95]
    assert len(hair_boxes) == 1, f"Halo chữ trên tóc đen bị xé nhiều hộp đè nhau: {hair_boxes}"
    tri_boxes = [r for r in ket if r.bbox.x >= 245 and r.bbox.y >= 90]
    assert not tri_boxes, f"Viền tam giác nhỏ vẫn lọt hậu kiểm: {tri_boxes}"


def test_loc_sfx_tranh_giu_bong_kin_va_chan_sfx_ngoai_bong():
    import cv2
    from app.services.ocr.loc_sfx_tranh import (
        la_chu_tuong_thanh_sfx,
        tao_ban_do_bong_thoai_tu_anh,
        vung_can_thiet_dich,
    )

    # Tạo ảnh 520x520 trắng ở trên (bong bóng khép kín viền đen dày) và nền gạch chéo phức tạp ở dưới
    anh = np.full((520, 520, 3), 245, dtype=np.uint8)
    # 1. Bong bóng thoại khép kín bên trái trên: (30, 30, 150, 140)
    cv2.ellipse(anh, (105, 100), (65, 62), 0, 0, 360, (255, 255, 255), -1)
    cv2.ellipse(anh, (105, 100), (65, 62), 0, 0, 360, (15, 15, 15), 3)
    # 2. Nửa dưới là nền tranh gạch sọc + nhiễu (phức tạp)
    anh[220:500, :] = 190
    for xx in range(10, 510, 7):
        cv2.line(anh, (xx, 220), (xx - 30, 500), (45, 45, 45), 2)
    # Tóc đen đặc cho thoại nội tâm dạng Akagi ở góc phải dưới: (310, 360, 180, 90)
    anh[350:465, 300:505] = 12
    # Halo trắng mảnh mô phỏng nét chữ nội tâm trên tóc đen (nằm NGOÀI bóng trắng khép kín)
    cv2.putText(anh, "No matter", (315, 405), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (250, 250, 250), 3)

    ban_do = tao_ban_do_bong_thoai_tu_anh(anh)
    assert ban_do is not None

    bbox_bong = BBox(x=68, y=72, w=74, h=56)
    bbox_nen_phuc_tap = BBox(x=45, y=280, w=88, h=46)
    bbox_toc_akagi = BBox(x=312, y=365, w=175, h=85)

    assert ban_do.kiem_tra_vung(bbox_bong).trong_bong_kin is True
    assert ban_do.kiem_tra_vung(bbox_nen_phuc_tap).trong_bong_kin is False
    assert ban_do.kiem_tra_vung(bbox_nen_phuc_tap).nen_tranh_phuc_tap is True

    # Thoại ngắn trong bong bóng khép kín (kể cả conf vừa) PHẢI luôn được giữ & dịch
    assert vung_can_thiet_dich("응응", 0.56, 0.50, 2, source_lang="ko", bbox=bbox_bong, ban_do_bong=ban_do) is True
    assert vung_can_thiet_dich("Uma...?", 0.62, 0.50, 2, source_lang="en", bbox=bbox_bong, ban_do_bong=ban_do) is True
    assert vung_can_thiet_dich("WHOOOM!", 0.90, 0.50, 2, source_lang="en", bbox=bbox_bong, ban_do_bong=ban_do) is True

    # SFX trôi nổi ngoài bóng thoại PHẢI bị loại sạch (kể cả conf 0.99)
    for txt_sfx, lang in [
        ("GULP", "en"),
        ("주절 - -", "ko"),
        ("주절 ~", "ko"),
        ("~~~꼬르르", "ko"),
        ("픽", "ko"),
        ("ビュウ ガタガタ", "en"),
        ("グキ", "ja"),
        ("ピキ", "ja"),
        ("ボワアア", "ja"),
    ]:
        assert la_chu_tuong_thanh_sfx(txt_sfx, lang) is True, f"Bỏ sót SFX: {txt_sfx}"
        assert vung_can_thiet_dich(
            txt_sfx, 0.98, 0.50, 2, source_lang=lang, bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do
        ) is False, f"Vẫn xoá/dịch SFX ngoài bóng: {txt_sfx}"

    # Chữ OCR đọc bậy trên nền tranh phức tạp ngoài bóng thoại PHẢI bị chặn
    assert vung_can_thiet_dich("LA UMa Z", 0.66, 0.50, 2, source_lang="en", bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do) is False
    assert vung_can_thiet_dich("Mi P", 0.65, 0.50, 2, source_lang="en", bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do) is False
    assert vung_can_thiet_dich("#? -- - 로 나 까", 0.77, 0.50, 2, source_lang="ko", bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do) is False
    assert vung_can_thiet_dich("1 피", 0.52, 0.50, 2, source_lang="ko", bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do) is False

    # Thoại nội tâm mạch lạc trên tóc đen (Akagi) PHẢI giữ nguyên 100% để dịch
    assert vung_can_thiet_dich(
        "No matter how I play...", 0.88, 0.50, 2, source_lang="en", bbox=bbox_toc_akagi, ban_do_bong=ban_do
    ) is True
    assert vung_can_thiet_dich(
        "...There's something really strange", 0.91, 0.50, 2, source_lang="en", bbox=bbox_toc_akagi, ban_do_bong=ban_do
    ) is True
    assert vung_can_thiet_dich(
        "Giants' fans are really loud...", 0.92, 0.50, 2, source_lang="en", bbox=bbox_toc_akagi, ban_do_bong=ban_do
    ) is True
    assert vung_can_thiet_dich("응응", 0.92, 0.50, 2, source_lang="ko", bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do) is True
    assert vung_can_thiet_dich("선배...", 0.88, 0.50, 2, source_lang="ko", bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do) is True
    assert vung_can_thiet_dich("なに…？", 0.88, 0.50, 2, source_lang="ja", bbox=bbox_nen_phuc_tap, ban_do_bong=ban_do) is True

    # Nền góc nhọn trắng trong khung tranh (fill_ratio < 0.42) KHÔNG được nhận nhầm là bóng kín,
    # và từ tượng thanh chắc chắn ("주절 - -") kể cả đặt trên nền sáng vẫn phải bị bỏ qua.
    anh_goc = np.full((300, 420, 3), 60, dtype=np.uint8)
    tam_giac = np.array([[20, 20], [340, 20], [20, 160]], dtype=np.int32)
    cv2.fillPoly(anh_goc, [tam_giac], (255, 255, 255))
    cv2.polylines(anh_goc, [tam_giac], True, (15, 15, 15), 3)
    ban_do_goc = tao_ban_do_bong_thoai_tu_anh(anh_goc)
    assert ban_do_goc is not None
    bbox_goc_nhon = BBox(x=50, y=35, w=55, h=40)
    assert ban_do_goc.kiem_tra_vung(bbox_goc_nhon).trong_bong_kin is False
    assert vung_can_thiet_dich(
        "주절 - -", 0.62, 0.50, 2, source_lang="ko", bbox=bbox_bong, ban_do_bong=ban_do
    ) is False




