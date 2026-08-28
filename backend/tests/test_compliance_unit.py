"""Unit — khai báo mục đích sử dụng (M10). Không cần DB."""
from __future__ import annotations

import pytest

from app.models.enums import IntendedUse
from app.services.compliance import ComplianceGate


class TestKhaiBaoMucDich:
    """Không suy đoán hộ: thiếu khai báo là LỖI, không phải là `personal`."""

    @pytest.mark.parametrize("gia_tri", ["personal", "study", "other"])
    def test_nhan_dung_ba_gia_tri_da_chot(self, gia_tri):
        assert ComplianceGate.validate_intended_use(gia_tri) is IntendedUse(gia_tri)

    @pytest.mark.parametrize("gia_tri", ["commercial", "PERSONAL", "cá nhân", "0", "none"])
    def test_tu_choi_gia_tri_ngoai_enum(self, gia_tri):
        with pytest.raises(ValueError, match="intended_use_invalid"):
            ComplianceGate.validate_intended_use(gia_tri)

    @pytest.mark.parametrize("gia_tri", [None, ""])
    def test_thieu_khai_bao_thi_bao_loi_chu_khong_tu_dien(self, gia_tri):
        """Tự điền `personal` hộ là suy đoán mục đích sử dụng thay người dùng — đúng thứ mà
        khai báo này sinh ra để tránh."""
        with pytest.raises(ValueError, match="intended_use_required"):
            ComplianceGate.validate_intended_use(gia_tri)

    def test_thong_diep_loi_noi_ro_nhung_gia_tri_hop_le(self):
        with pytest.raises(ValueError) as e:
            ComplianceGate.validate_intended_use("commercial")
        for hop_le in ("personal", "study", "other"):
            assert hop_le in str(e.value)
