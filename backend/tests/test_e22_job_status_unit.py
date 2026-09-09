"""E22 (thu hẹp theo audit) — suy luận `processing_state` LÚC ĐỌC, đơn vị thuần (không DB)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.enums import JobStatus, JobType
from app.services.job_status import (
    TRANG_THAI_WORKER_GIAN_DOAN,
    nguong_qua_han_giay,
    suy_ra_trang_thai_hien_thi,
)


def _luc(giay_truoc: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=giay_truoc)


class TestSuyRaTrangThaiHienThi:
    def test_trang_thai_khac_running_giu_nguyen(self):
        for tt in (JobStatus.queued, JobStatus.done, JobStatus.failed):
            assert suy_ra_trang_thai_hien_thi(
                status=tt, loai=JobType.detect, heartbeat_at=None, started_at=None,
            ) == tt.value

    def test_running_nhip_tim_moi_van_la_running(self):
        moc = _luc(5)
        assert suy_ra_trang_thai_hien_thi(
            status=JobStatus.running, loai=JobType.detect,
            heartbeat_at=moc, started_at=moc,
        ) == "running"

    def test_running_qua_lau_khong_nhip_tim_moi_thanh_gian_doan(self):
        # detect_timeout_seconds=60 (mặc định) + buffer 20s = 80s ngưỡng.
        moc = _luc(200)
        assert suy_ra_trang_thai_hien_thi(
            status=JobStatus.running, loai=JobType.detect,
            heartbeat_at=moc, started_at=moc,
        ) == TRANG_THAI_WORKER_GIAN_DOAN

    def test_dung_ngay_tai_nguong_van_la_running_qua_nguong_moi_gian_doan(self):
        nguong = nguong_qua_han_giay(JobType.detect)
        vua_duoi = _luc(nguong - 1)
        vua_qua = _luc(nguong + 1)
        assert suy_ra_trang_thai_hien_thi(
            status=JobStatus.running, loai=JobType.detect,
            heartbeat_at=vua_duoi, started_at=vua_duoi,
        ) == "running"
        assert suy_ra_trang_thai_hien_thi(
            status=JobStatus.running, loai=JobType.detect,
            heartbeat_at=vua_qua, started_at=vua_qua,
        ) == TRANG_THAI_WORKER_GIAN_DOAN

    def test_job_cu_truoc_e22_chua_tung_co_heartbeat_khong_bi_bao_gian_doan(self):
        """`heartbeat_at IS NULL` (job có từ trước E22) không đủ bằng chứng để nói khác — không
        được suy diễn thành 'gián đoạn' chỉ vì thiếu dữ liệu cũ."""
        assert suy_ra_trang_thai_hien_thi(
            status=JobStatus.running, loai=JobType.inpaint,
            heartbeat_at=None, started_at=_luc(9999),
        ) == "running"

    def test_nguong_khac_nhau_theo_loai_job(self):
        # ocr_timeout_seconds (600) > detect_timeout_seconds (60) trong cấu hình mặc định.
        assert nguong_qua_han_giay(JobType.ocr) > nguong_qua_han_giay(JobType.detect)

    def test_moi_job_type_da_biet_deu_co_nguong_rieng(self):
        # Khoá lại: nếu sau này `JobType` có thêm giá trị mới mà quên cập nhật `_TIMEOUT_ATTR`,
        # bài test này đỏ thay vì âm thầm rơi vào `_TIMEOUT_MAC_DINH` (900s — quá rộng, báo trễ).
        from app.services.job_status import _TIMEOUT_ATTR

        assert set(_TIMEOUT_ATTR) == set(JobType)
