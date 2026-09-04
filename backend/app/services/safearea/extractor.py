"""Tìm lòng bong bóng quanh một bbox chữ (E14 · B2).

Thuần hình học và **tất định**: cùng ảnh + cùng cấu hình ⇒ cùng kết quả. Không ghi CSDL, không
sửa ảnh, không gọi mạng, không nạp model.

Ba điều đã trả giá để học, đừng đảo lại (bằng chứng: `docs/TEST_LOG.md` §E14.2):

1. **ROI phải nới theo bội của bbox chữ.** Bong bóng lớn hơn bbox chữ rất nhiều; ROI hẹp làm
   hình bị cắt ở mép rồi bị loại oan.
2. **Ngưỡng phải CHẶT, rồi lấp lỗ theo TỪNG ứng viên.** Nới ngưỡng để cứu cái lỗ do mảng vá của
   LaMa tạo ra sẽ làm bong bóng dính vào nền sáng. Lấp lỗ trên cả ROI thì nuốt luôn vùng tối bị
   nền sáng bao quanh.
3. **Chọn đường viền KHÍT NHẤT chứa tâm bbox, không phải to nhất.** "Vùng trắng lớn nhất" là
   cách chắc chắn để có ngày chọn trúng nền trang.
"""
from __future__ import annotations

from app.models.enums import SafeAreaGeometryType, SafeAreaSource, SafeAreaStatus
from app.services.interfaces import BBox
from app.services.safearea.config import SafeAreaConfig
from app.services.safearea.decision import ReasonCode, SafeAreaDecision

VERSION = "e14-bubble-safe-area-v1"


def _le_thut_vao(bbox: BBox, cfg: SafeAreaConfig) -> int:
    canh_ngan = min(bbox.w, bbox.h)
    return int(min(max(round(canh_ngan * cfg.erosion_margin_ratio), cfg.erosion_margin_min_px),
                   cfg.erosion_margin_max_px))


def khung_du_phong(bbox: BBox, cfg: SafeAreaConfig, ly_do: list[str]) -> SafeAreaDecision:
    """Khung chữ nhật thụt vào, LƯU LẠI hẳn hoi — không để hình rỗng rồi đọc nhầm thành 'vừa'.

    Lề lấy đúng `typeset_padding_ratio` của M6 nên đường dự phòng cho ra **cùng vùng chữ** như
    trước khi có E14. Đo thật: dùng lề ăn-vào của E14 ở đây làm cỡ chữ một dòng bản quyền nhảy
    từ 14 lên 16 — đổi bố cục ở nơi E14 không nhận diện được gì cả.
    """
    pad_x = bbox.w * cfg.fallback_padding_ratio
    pad_y = bbox.h * cfg.fallback_padding_ratio
    x = bbox.x + pad_x
    y = bbox.y + pad_y
    w = max(bbox.w - 2 * pad_x, 1.0)
    h = max(bbox.h - 2 * pad_y, 1.0)
    dien_tich = int(w * h)
    thieu = (w < cfg.safe_area_min_width_px or h < cfg.safe_area_min_height_px
             or dien_tich < cfg.safe_area_min_pixels)
    ly_do = list(ly_do)
    if ReasonCode.FALLBACK_NO_RELIABLE_SHAPE not in ly_do:
        ly_do.append(ReasonCode.FALLBACK_NO_RELIABLE_SHAPE)
    if thieu:
        ly_do.append(ReasonCode.SAFE_AREA_SMALLER_THAN_MINIMUM)
    return SafeAreaDecision(
        source=SafeAreaSource.fallback_rectangle,
        # Khung quá nhỏ thì không im lặng chấp nhận: đẩy sang người xem.
        status=SafeAreaStatus.needs_review if thieu else SafeAreaStatus.fallback_rectangle,
        geometry_type=SafeAreaGeometryType.rect,
        geometry={"rect": {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}},
        roi=(int(bbox.x), int(bbox.y), int(bbox.w), int(bbox.h)),
        reason_codes=ly_do,
        safe_area_pixels=dien_tich,
        bbox_coverage_ratio=round(dien_tich / max(bbox.w * bbox.h, 1.0), 4),
    )


def khung_du_phong_co_noi(
    bbox: BBox,
    cfg: SafeAreaConfig,
    ly_do: list[str],
    mat_na_trong,
    roi: tuple[int, int, int, int],
) -> SafeAreaDecision:
    """Khung dự phòng, nhưng **nới ra chỗ trống** trước khi chịu thua (A1).

    Chỉ đổi HÌNH HỌC, không đổi kết luận: vẫn là `fallback_rectangle` với đủ lý do vì sao không
    dựng được hình bong bóng. Nói "đã tìm được bong bóng" chỉ vì nới được một cái khung rộng hơn
    là tự phong cho mình một mức chắc chắn mình không có.

    Nới thất bại (ô ban đầu đã dính mực, hoặc không rộng thêm được bao nhiêu) ⇒ trả đúng khung
    dự phòng cũ, không có gì đổi.
    """
    goc = khung_du_phong(bbox, cfg, ly_do)
    if not cfg.grow_enabled or mat_na_trong is None:
        return goc

    from app.services.safearea.grow import gioi_han_no, no_khung_ra_cho_trong

    r = goc.geometry["rect"]
    rx, ry, _rw, _rh = roi
    # Mặt nạ nằm trong hệ toạ độ ROI; khung thì ở hệ toạ độ ảnh gốc.
    o_bat_dau = (r["x"] - rx, r["y"] - ry, r["w"], r["h"])
    gh = gioi_han_no(bbox.x - rx, bbox.y - ry, bbox.w, bbox.h,
                     (0, 0, mat_na_trong.shape[1], mat_na_trong.shape[0]),
                     cfg.grow_max_ratio, cfg.grow_max_px)
    kq = no_khung_ra_cho_trong(mat_na_trong, o_bat_dau, gioi_han=gh, buoc=cfg.grow_step_px)
    if kq is None or kq.he_so_dien_tich < 1.0 + cfg.grow_min_gain_ratio:
        return goc

    # Chừa lề bên trong khung vừa nới: nới dừng ở NÉT MỰC, nên mép khung đang chạm sát viền
    # bong bóng. Không thụt vào thì chữ dính viền.
    le = _le_thut_vao(bbox, cfg)
    x = kq.x + rx + le
    y = kq.y + ry + le
    w = kq.w - 2 * le
    h = kq.h - 2 * le
    if w < cfg.safe_area_min_width_px or h < cfg.safe_area_min_height_px:
        return goc
    if w * h <= r["w"] * r["h"]:
        return goc

    ly_do_moi = list(goc.reason_codes)
    if ReasonCode.FALLBACK_GROWN_TO_FREE_SPACE not in ly_do_moi:
        ly_do_moi.append(ReasonCode.FALLBACK_GROWN_TO_FREE_SPACE)
    # Khung đã nới thì không còn "nhỏ hơn mức tối thiểu" nữa — bỏ mã đó đi, giữ lại là nói sai
    # về khung ĐANG dùng.
    ly_do_moi = [m for m in ly_do_moi if m != ReasonCode.SAFE_AREA_SMALLER_THAN_MINIMUM]

    dien_tich = int(w * h)
    return SafeAreaDecision(
        source=SafeAreaSource.fallback_rectangle,
        status=SafeAreaStatus.fallback_rectangle,
        geometry_type=SafeAreaGeometryType.rect,
        geometry={"rect": {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}},
        roi=roi,
        reason_codes=ly_do_moi,
        safe_area_pixels=dien_tich,
        bbox_coverage_ratio=round(dien_tich / max(bbox.w * bbox.h, 1.0), 4),
    )


def tinh_roi(bbox: BBox, image_w: int, image_h: int, cfg: SafeAreaConfig) -> tuple[int, int, int, int]:
    ex = min(bbox.w * cfg.roi_expand_ratio, cfg.roi_expand_max_px)
    ey = min(bbox.h * cfg.roi_expand_ratio, cfg.roi_expand_max_px)
    x0 = max(int(bbox.x - ex), 0)
    y0 = max(int(bbox.y - ey), 0)
    x1 = min(int(bbox.x + bbox.w + ex), image_w)
    y1 = min(int(bbox.y + bbox.h + ey), image_h)
    return x0, y0, max(x1 - x0, 0), max(y1 - y0, 0)


class BubbleSafeAreaExtractor:
    """Chỉ chạy trong worker — `cv2` cố ý import bên trong hàm để tiến trình API không nạp."""

    VERSION = VERSION

    def extract(
        self,
        clean_image_path: str,
        region_bbox: BBox,
        image_size: tuple[int, int],
        config: SafeAreaConfig,
    ) -> SafeAreaDecision:
        import cv2
        import numpy as np

        image_w, image_h = image_size
        if (region_bbox.w <= 0 or region_bbox.h <= 0
                or region_bbox.x < 0 or region_bbox.y < 0
                or region_bbox.x + region_bbox.w > image_w
                or region_bbox.y + region_bbox.h > image_h):
            # Đầu vào hỏng thì KHÔNG dựng khung dự phòng giả — báo hỏng để người xem.
            return SafeAreaDecision(
                source=SafeAreaSource.fallback_rectangle,
                status=SafeAreaStatus.failed,
                geometry_type=SafeAreaGeometryType.rect,
                geometry={"rect": {"x": float(max(region_bbox.x, 0)),
                                   "y": float(max(region_bbox.y, 0)),
                                   "w": float(max(region_bbox.w, 1)),
                                   "h": float(max(region_bbox.h, 1))}},
                roi=(0, 0, 0, 0),
                reason_codes=[ReasonCode.SHAPE_INVALID_GEOMETRY],
            )

        rx, ry, rw, rh = tinh_roi(region_bbox, image_w, image_h, config)
        if rw <= 0 or rh <= 0:
            return khung_du_phong(region_bbox, config, [ReasonCode.SHAPE_INVALID_GEOMETRY])

        anh = cv2.imread(clean_image_path)
        if anh is None:
            return SafeAreaDecision(
                source=SafeAreaSource.fallback_rectangle,
                status=SafeAreaStatus.failed,
                geometry_type=SafeAreaGeometryType.rect,
                geometry={"rect": {"x": float(region_bbox.x), "y": float(region_bbox.y),
                                   "w": float(region_bbox.w), "h": float(region_bbox.h)}},
                roi=(rx, ry, rw, rh),
                reason_codes=[ReasonCode.SHAPE_INVALID_GEOMETRY],
            )

        roi = anh[ry:ry + rh, rx:rx + rw]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sang = ((hsv[:, :, 2] >= config.brightness_threshold)
                & (hsv[:, :, 1] <= config.saturation_threshold)).astype(np.uint8) * 255
        if not sang.any():
            # Không có điểm sáng nào thì cũng không có chỗ trống nào để nới vào.
            return khung_du_phong(region_bbox, config, [ReasonCode.SHAPE_LOW_CONTRAST])

        # Từ đây trở xuống đã có mặt nạ chỗ-trống, nên mọi đường lùi về khung dự phòng đều
        # được thử nới ra trước (A1).
        trong = sang > 0

        def du_phong(ly_do: list[str]) -> SafeAreaDecision:
            return khung_du_phong_co_noi(region_bbox, config, ly_do, trong, (rx, ry, rw, rh))

        canh_ngan = min(region_bbox.w, region_bbox.h)
        k = int(max(3, round(canh_ngan * config.morph_kernel_ratio)) // 2 * 2 + 1)
        nhan = np.ones((k, k), np.uint8)
        dong = cv2.morphologyEx(sang, cv2.MORPH_CLOSE, nhan)
        dong = cv2.morphologyEx(dong, cv2.MORPH_OPEN, nhan)

        vien, _ = cv2.findContours(dong, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cx = float(region_bbox.x + region_bbox.w / 2 - rx)
        cy = float(region_bbox.y + region_bbox.h / 2 - ry)
        chua_tam = [c for c in vien if cv2.pointPolygonTest(c, (cx, cy), False) >= 0]
        if not chua_tam:
            return du_phong([ReasonCode.SHAPE_CANDIDATE_NOT_CENTERED])

        ly_do: list[str] = []
        if len(chua_tam) > 1:
            ly_do.append(ReasonCode.SHAPE_CANDIDATE_MULTIPLE_AMBIGUOUS)

        c = min(chua_tam, key=cv2.contourArea)
        mask = np.zeros((rh, rw), np.uint8)
        cv2.drawContours(mask, [c], -1, 255, cv2.FILLED)   # tô đặc = lấp lỗ của riêng ứng viên này

        dien_tich = int((mask > 0).sum())
        dt_bbox = max(region_bbox.w * region_bbox.h, 1.0)
        if dien_tich < config.min_bbox_coverage_ratio * dt_bbox:
            ly_do.append(ReasonCode.SHAPE_CANDIDATE_TOO_SMALL)
        if dien_tich > config.max_roi_coverage_ratio * rw * rh:
            ly_do.append(ReasonCode.SHAPE_CANDIDATE_FILLS_ROI)

        cham = int((mask[0, :] > 0).sum() + (mask[-1, :] > 0).sum()
                   + (mask[:, 0] > 0).sum() + (mask[:, -1] > 0).sum())
        if cham / max(2 * (rw + rh), 1) > config.max_roi_touch_ratio:
            ly_do.append(ReasonCode.SHAPE_CANDIDATE_TOUCHES_ROI_BOUNDARY)

        le = _le_thut_vao(region_bbox, config)
        mask_an = cv2.erode(mask, np.ones((le * 2 + 1, le * 2 + 1), np.uint8))
        con_lai = int((mask_an > 0).sum())
        if con_lai == 0:
            ly_do.append(ReasonCode.SHAPE_EROSION_ELIMINATED_AREA)

        if ly_do:
            return du_phong(ly_do)

        cnt, _ = cv2.findContours(mask_an, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnt:
            return du_phong([ReasonCode.SHAPE_EROSION_ELIMINATED_AREA])
        c2 = max(cnt, key=cv2.contourArea)
        eps = 0.005 * cv2.arcLength(c2, True)
        xap_xi = cv2.approxPolyDP(c2, eps, True)
        # Nới dần sai số cho tới khi số đỉnh nằm trong trần — vẫn tất định vì bước nới cố định.
        while len(xap_xi) > config.max_polygon_vertices and eps < rw:
            eps *= 1.5
            xap_xi = cv2.approxPolyDP(c2, eps, True)
        if len(xap_xi) < 3 or len(xap_xi) > config.max_polygon_vertices:
            return du_phong([ReasonCode.SHAPE_INVALID_GEOMETRY])

        x, y, w, h = cv2.boundingRect(mask_an)
        if (w < config.safe_area_min_width_px or h < config.safe_area_min_height_px
                or con_lai < config.safe_area_min_pixels):
            return du_phong([ReasonCode.SAFE_AREA_SMALLER_THAN_MINIMUM])

        diem = [[float(p[0][0] + rx), float(p[0][1] + ry)] for p in xap_xi]
        return SafeAreaDecision(
            source=SafeAreaSource.shape_derived,
            status=SafeAreaStatus.ready,
            geometry_type=SafeAreaGeometryType.polygon,
            geometry={"polygon": diem},
            roi=(rx, ry, rw, rh),
            reason_codes=[ReasonCode.SHAPE_CANDIDATE_FOUND],
            safe_area_pixels=con_lai,
            bbox_coverage_ratio=round(con_lai / dt_bbox, 4),
        )
