"""E34 — chỉ gửi ảnh cho trang THẬT SỰ cần.

Ảnh tốn cố định **+1166 token/trang** (đo ở E32), mà lợi ích chỉ dồn vào trang bộ đọc chữ làm kém.
Trả token cho trang đã đọc sạch là trả cho thứ không đổi gì.

Rủi ro hai chiều, và test canh cả hai:

- **Gửi oan** ⇒ tiêu token vô ích. Đây là chiều dễ xảy ra: chỉ cần một cờ quá nhạy.
- **Bỏ sót** ⇒ mất đúng cái lợi của E32 trên trang cần nó nhất.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import OCRResult, Page, Project, TextRegion
from app.models.enums import (
    IntendedUse, OCREngine, OCRStatus, PageStatus, RegionStatus, SourceLang, TargetLang,
)
from app.services.translate.chon_trang_gui_anh import can_gui_anh


def _trang(s, trang_thai=PageStatus.inpainted) -> uuid.UUID:
    pr = Project(
        name=f"E34 {uuid.uuid4().hex[:8]}", source_lang=SourceLang.ja,
        target_lang=TargetLang.vi, intended_use=IntendedUse.study,
    )
    s.add(pr)
    s.flush()
    pg = Page(project_id=pr.id, image_path="x.jpg", order=1, status=trang_thai)
    s.add(pg)
    s.flush()
    return pg.id


def _vung(s, page_id, tt=RegionStatus.confirmed, ocr_tt=OCRStatus.ok, chu="Xin chào"):
    r = TextRegion(
        page_id=page_id, bbox_x=0, bbox_y=0, bbox_w=50, bbox_h=20,
        confidence=0.9, status=tt,
    )
    s.add(r)
    s.flush()
    s.add(OCRResult(
        region_id=r.id, raw_text=chu, ocr_engine=OCREngine.manga_ocr,
        confidence=0.9, status=ocr_tt,
    ))
    s.flush()
    return r.id


class TestGuiAnhKhiCoDauHieu:
    def test_inpaint_needs_review(self):
        with sync_session() as s:
            pid = _trang(s, PageStatus.inpaint_needs_review)
            _vung(s, pid)
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is True and ly_do == "inpaint_needs_review"

    def test_vung_low_confidence(self):
        with sync_session() as s:
            pid = _trang(s)
            _vung(s, pid)                                    # vùng sạch
            _vung(s, pid, tt=RegionStatus.low_confidence)    # một vùng đáng ngờ là đủ
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is True and ly_do.startswith("ti_le_dang_ngo"), ly_do

    def test_ocr_needs_manual(self):
        with sync_session() as s:
            pid = _trang(s)
            _vung(s, pid, ocr_tt=OCRStatus.needs_manual, chu="")
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is True and ly_do.startswith("ti_le_dang_ngo"), ly_do


class TestKHONG_GUI_OAN:
    """Chiều dễ xảy ra nhất: một cờ quá nhạy là tiêu token cho mọi trang."""

    def test_trang_sach_hoan_toan_thi_KHONG_gui(self):
        with sync_session() as s:
            pid = _trang(s)
            for _ in range(3):
                _vung(s, pid)
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is False, f"gửi oan cho trang sạch (lý do: {ly_do})"
        assert ly_do == "du_sach_0%", ly_do

    @pytest.mark.parametrize("tt", [
        PageStatus.inpainted, PageStatus.translated, PageStatus.typeset_done,
    ])
    def test_cac_trang_thai_BINH_THUONG_khong_kich_hoat(self, tt):
        with sync_session() as s:
            pid = _trang(s, tt)
            _vung(s, pid)
            s.commit()
            gui, _ = can_gui_anh(s, pid)
        assert gui is False, f"trạng thái {tt.value} không phải dấu hiệu OCR kém"

    def test_vung_PENDING_khong_kich_hoat(self):
        """`pending` nghĩa là chưa chấm, KHÁC hẳn `low_confidence` nghĩa là đã chấm và thấp."""
        with sync_session() as s:
            pid = _trang(s)
            _vung(s, pid, tt=RegionStatus.pending)
            s.commit()
            gui, _ = can_gui_anh(s, pid)
        assert gui is False


class TestKhongBaoHoa:
    """Luật "có MỘT vùng bị cờ" của spec đầu TỰ BÃO HOÀ — đây là ca chứng minh đã sửa.

    Đo thật: 12% vùng tiếng Anh bị cờ, ~9 vùng/trang ⇒ `1-(0.88^9) ≈ 68%` trang bật. Chọn lọc
    kiểu đó gần bằng gửi hết, tức mất sạch ý nghĩa của E34.
    """

    def test_MOT_vung_bi_co_trong_MUOI_vung_thi_KHONG_gui(self):
        with sync_session() as s:
            pid = _trang(s)
            for _ in range(9):
                _vung(s, pid)
            _vung(s, pid, tt=RegionStatus.low_confidence)
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is False, f"bão hoà: 1/10 vùng đã đủ bật (lý do: {ly_do})"
        assert ly_do == "du_sach_10%", ly_do

    def test_BA_vung_bi_co_trong_MUOI_thi_GUI(self):
        """30% là ngưỡng neo vào ca `どなどは` (33%) — ca duy nhất chứng minh ảnh có tác dụng."""
        with sync_session() as s:
            pid = _trang(s)
            for _ in range(7):
                _vung(s, pid)
            for _ in range(3):
                _vung(s, pid, tt=RegionStatus.low_confidence)
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is True and ly_do == "ti_le_dang_ngo_30%", ly_do

    def test_ca_THAT_da_chung_minh_van_duoc_giu(self):
        """Trang `どなどは`: 3 vùng, 1 bị cờ = 33%. Ngưỡng 0.5 sẽ LOẠI ca này."""
        with sync_session() as s:
            pid = _trang(s)
            _vung(s, pid, chu="．．．これで出来上がり")
            _vung(s, pid, chu="．．．うーん足りなかったかかも")
            _vung(s, pid, tt=RegionStatus.low_confidence, chu="どなどは")
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is True, f"MẤT ca duy nhất chứng minh được lợi ích của ảnh (lý do: {ly_do})"

    def test_khong_dem_DOI_vung_bi_ca_hai_co(self):
        """Vùng vừa `low_confidence` vừa `needs_manual` chỉ được đếm MỘT lần."""
        with sync_session() as s:
            pid = _trang(s)
            for _ in range(7):
                _vung(s, pid)
            for _ in range(2):
                _vung(s, pid, tt=RegionStatus.low_confidence, ocr_tt=OCRStatus.needs_manual)
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        # 2/9 = 22% < 30%. Đếm đôi thì thành 4/9 = 44% và bật oan.
        assert gui is False, f"đếm đôi vùng bị cả hai cờ (lý do: {ly_do})"


class TestThieuDuLieuThiKHONG_TIEU_TOKEN:
    def test_trang_khong_ton_tai(self):
        with sync_session() as s:
            gui, ly_do = can_gui_anh(s, uuid.uuid4())
        assert gui is False and ly_do == "khong_thay_trang"

    def test_trang_chua_co_vung_nao(self):
        with sync_session() as s:
            pid = _trang(s)
            s.commit()
            gui, ly_do = can_gui_anh(s, pid)
        assert gui is False and ly_do == "trang_khong_co_vung"


class TestKHONG_LAN_SANG_TRANG_KHAC:
    def test_co_dau_hieu_o_trang_KHAC_thi_khong_kich_hoat(self):
        """Truy vấn lọc theo `page_id`; sai chỗ này là gửi ảnh cho cả chapter."""
        with sync_session() as s:
            sach = _trang(s)
            _vung(s, sach)
            ban = _trang(s)
            _vung(s, ban, tt=RegionStatus.low_confidence)
            s.commit()
            assert can_gui_anh(s, ban)[0] is True
            assert can_gui_anh(s, sach)[0] is False, "dấu hiệu lan sang trang khác"
