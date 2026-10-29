"""Nhận biết hướng chữ của từng vùng (E15 · B1).

Thuần luật và **tất định**: cùng đầu vào ⇒ cùng kết quả. Không ghi CSDL, không chạy lại OCR,
không gọi mạng, không dùng LLM.

Bốn điều đã đo được và định hình toàn bộ thiết kế (`docs/TEST_LOG.md § E15.1–2`):

1. **Bộ nhận diện không cho hình học dòng chữ** — chỉ khung chữ nhật. Nguồn mà spec trông đợi
   không tồn tại.
2. **Ảnh đã xoá chữ thì không còn chữ để đo** — thoại trong bong bóng còn 0–4 điểm ảnh tối.
   Nên không thể đoán hướng từ ảnh clean.
3. ⇒ Bằng chứng hình học **duy nhất** là **đường bao từng dòng của OCR**, lấy lúc chữ còn nguyên.
4. **Góc thô của `minAreaRect` không phân biệt được 0° với 90°** — phải chuẩn hoá bằng `w`/`h`.

Và một điều không cần đo cũng biết: **tỉ lệ khung không bao giờ được tự quyết**. Một chữ "PHEW!"
viết thưa ra theo chiều dọc vẫn là chữ ngang cách điệu.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import OrientationSource, OrientationStatus, TextOrientation
from app.services.orientation.angle import chuan_hoa_goc, la_doc, la_ngang
from app.services.orientation.decision import LyDo, OrientationDecision

VERSION = "e15-orientation-rules-v1"


@dataclass(frozen=True)
class OrientationConfig:
    #: Lệch bao nhiêu độ so với 0/90 thì vẫn coi là ngang/dọc.
    angle_tolerance_deg: float = 12.0
    #: Bao nhiêu phần các dòng phải cùng hướng thì mới được coi là nhất quán.
    min_agreement_ratio: float = 0.75
    #: Khung cao gấp ngần này lần bề rộng thì ghi TÍN HIỆU dọc — chỉ là tín hiệu.
    bbox_vertical_aspect: float = 2.0
    bbox_horizontal_aspect: float = 1.5
    #: Bật dựng chữ dọc. Mặc định TẮT: chưa có ảnh mẫu chữ dọc hợp pháp để chạy Run B, mà
    #: spec cấm tuyên bố hỗ trợ khi chưa đo được (`REPORT_E15.md` §3).
    vertical_render_enabled: bool = False


def _goc_cua_da_giac(poly) -> float | None:
    """Hướng cạnh dài của một đường bao dòng chữ, quy về [0, 180)."""
    import cv2
    import numpy as np

    if not poly or len(poly) < 3:
        return None
    pts = np.array(poly, dtype=np.float32)
    if not np.isfinite(pts).all():
        return None
    (_, _), (w, h), a = cv2.minAreaRect(pts)
    if w <= 0 or h <= 0:
        return None
    return chuan_hoa_goc(w, h, a)


class RegionOrientationAnalyzer:
    VERSION = VERSION

    def __init__(self, config: OrientationConfig | None = None) -> None:
        self.config = config or OrientationConfig()

    def analyze(
        self,
        *,
        bbox_w: float,
        bbox_h: float,
        line_polygons: list | None,
        ocr_status: str | None = None,
        region_relevance: str | None = None,
        safe_area_source: str | None = None,
    ) -> OrientationDecision:
        cfg = self.config
        ly_do: list[str] = [LyDo.CTD_GEOMETRY_UNAVAILABLE]
        bang_chung: dict = {"bbox": [round(bbox_w, 1), round(bbox_h, 1)]}

        if bbox_w <= 0 or bbox_h <= 0:
            return OrientationDecision(
                orientation=TextOrientation.unknown,
                source=OrientationSource.fallback_unknown,
                status=OrientationStatus.failed,
                reason_codes=[LyDo.ORIENTATION_UNKNOWN],
                evidence_snapshot=bang_chung,
            )

        # Tín hiệu từ tỉ lệ khung — GHI LẠI thôi, không bao giờ được tự quyết.
        ty_le = bbox_h / bbox_w
        bang_chung["ty_le_cao_tren_rong"] = round(ty_le, 2)
        if ty_le >= cfg.bbox_vertical_aspect:
            ly_do.append(LyDo.BBOX_ASPECT_VERTICAL_SIGNAL)
        elif ty_le <= 1 / cfg.bbox_horizontal_aspect:
            ly_do.append(LyDo.BBOX_ASPECT_HORIZONTAL_SIGNAL)

        if region_relevance in ("possible_sfx", "uncertain"):
            # Chỉ là ngữ cảnh. Một vùng có thể là SFX mà vẫn là chữ ngang bình thường.
            ly_do.append(LyDo.POSSIBLE_SFX_FROM_QUALITY_GATE)
        if safe_area_source == "fallback_rectangle":
            ly_do.append(LyDo.SAFE_AREA_FALLBACK_RECTANGLE)

        if line_polygons is None:
            # Engine không cung cấp bố cục dòng (manga-ocr chỉ trả chuỗi). Không có bằng chứng
            # hình học thì câu trả lời trung thực là "chưa biết" — không được suy từ tỉ lệ khung.
            ly_do.append(LyDo.OCR_LAYOUT_UNAVAILABLE)
            ly_do.append(LyDo.ORIENTATION_UNKNOWN)
            return OrientationDecision(
                orientation=TextOrientation.unknown,
                source=OrientationSource.fallback_unknown,
                status=OrientationStatus.needs_review,
                reason_codes=ly_do,
                evidence_snapshot=bang_chung,
            )

        goc = [g for g in (_goc_cua_da_giac(p) for p in line_polygons) if g is not None]
        bang_chung["goc_tung_dong"] = [round(g, 1) for g in goc]
        bang_chung["so_dong"] = len(goc)

        if not goc:
            ly_do.append(LyDo.OCR_LAYOUT_UNAVAILABLE)
            ly_do.append(LyDo.ORIENTATION_UNKNOWN)
            return OrientationDecision(
                orientation=TextOrientation.unknown,
                source=OrientationSource.fallback_unknown,
                status=OrientationStatus.needs_review,
                reason_codes=ly_do,
                line_count_estimate=0,
                evidence_snapshot=bang_chung,
            )

        so_ngang = sum(1 for g in goc if la_ngang(g, cfg.angle_tolerance_deg))
        so_doc = sum(1 for g in goc if la_doc(g, cfg.angle_tolerance_deg))
        so_nghieng = len(goc) - so_ngang - so_doc
        bang_chung["dem"] = {"ngang": so_ngang, "doc": so_doc, "nghieng": so_nghieng}

        # Có dòng nghiêng ⇒ chữ nghiêng/cách điệu. Chỉ điều hướng rà soát, KHÔNG tự xoay.
        if so_nghieng:
            nghieng = [g for g in goc
                       if not la_ngang(g, cfg.angle_tolerance_deg)
                       and not la_doc(g, cfg.angle_tolerance_deg)]
            ly_do += [LyDo.ROI_ROTATED_TEXT_EVIDENCE, LyDo.ROTATED_TEXT_MANUAL_REVIEW_ONLY]
            return OrientationDecision(
                orientation=TextOrientation.rotated_horizontal,
                source=OrientationSource.ocr_layout,
                status=OrientationStatus.needs_review,
                reason_codes=ly_do,
                rotation_degrees=round(sum(nghieng) / len(nghieng), 1),
                line_count_estimate=len(goc),
                evidence_snapshot=bang_chung,
            )

        can = cfg.min_agreement_ratio * len(goc)

        if so_doc >= can and so_doc > so_ngang:
            ly_do.append(LyDo.OCR_LINE_GEOMETRY_VERTICAL)
            if not cfg.vertical_render_enabled:
                # Nhận ra hướng KHÔNG có nghĩa là dựng được chữ theo hướng đó. Nói thẳng.
                ly_do.append(LyDo.VERTICAL_RENDERER_UNAVAILABLE)
                return OrientationDecision(
                    orientation=TextOrientation.vertical_ttb,
                    source=OrientationSource.ocr_layout,
                    status=OrientationStatus.unavailable,
                    reason_codes=ly_do,
                    line_count_estimate=len(goc),
                    evidence_snapshot=bang_chung,
                )
            return OrientationDecision(
                orientation=TextOrientation.vertical_ttb,
                source=OrientationSource.ocr_layout,
                status=OrientationStatus.ready,
                reason_codes=ly_do,
                line_count_estimate=len(goc),
                evidence_snapshot=bang_chung,
            )

        if so_ngang >= can and so_ngang > so_doc:
            ly_do.append(LyDo.OCR_LINE_GEOMETRY_HORIZONTAL)
            return OrientationDecision(
                orientation=TextOrientation.horizontal_ltr,
                source=OrientationSource.ocr_layout,
                status=OrientationStatus.ready,
                reason_codes=ly_do,
                line_count_estimate=len(goc),
                evidence_snapshot=bang_chung,
            )

        # Các dòng cãi nhau. KHÔNG bỏ phiếu đa số cho xong — nói thẳng là mâu thuẫn.
        ly_do += [LyDo.ORIENTATION_EVIDENCE_CONFLICT, LyDo.ORIENTATION_UNKNOWN]
        return OrientationDecision(
            orientation=TextOrientation.unknown,
            source=OrientationSource.ocr_layout,
            status=OrientationStatus.needs_review,
            reason_codes=ly_do,
            line_count_estimate=len(goc),
            evidence_snapshot=bang_chung,
        )
