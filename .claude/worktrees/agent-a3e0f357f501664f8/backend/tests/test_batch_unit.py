"""Unit — phân loại lỗi, chính sách thử lại, cổng nhịp, gộp trạng thái mẻ (M9)."""
from __future__ import annotations

import threading

import pytest

from app.models.enums import BatchItemStatus as S, BatchStatus, PageStatus
from app.services.batch.errors import ErrorClass, RetryPolicy, TransientErrorClassifier
from app.services.batch.rollup import buoc_cho_trang, gop_trang_thai_me


class TestPhanLoaiLoi:
    """429 có HAI nghĩa hoàn toàn khác nhau. M5 gộp làm một rồi xoay key — M9 phải tách."""

    @pytest.fixture
    def c(self):
        return TransientErrorClassifier()

    def test_429_kem_dau_hieu_het_quota_thi_la_quota(self, c):
        assert c.classify(mo_ta='HTTP 429: {"status":"RESOURCE_EXHAUSTED"}') is ErrorClass.QUOTA_EXHAUSTED
        assert c.classify(mo_ta="HTTP 429: You exceeded your current quota") is ErrorClass.QUOTA_EXHAUSTED
        assert c.classify(mo_ta="HTTP 429: daily limit reached") is ErrorClass.QUOTA_EXHAUSTED

    def test_429_qua_nhip_tam_thoi_thi_thu_lai_duoc(self, c):
        assert c.classify(mo_ta="HTTP 429: rate limit, try again") is ErrorClass.TRANSIENT_RATE_LIMIT

    def test_429_khong_ro_thi_coi_la_tam_thoi(self, c):
        """Chặn nhầm cả mẻ vì tưởng hết quota đắt hơn là thử lại vài lần rồi dừng."""
        assert c.classify(mo_ta="HTTP 429") is ErrorClass.TRANSIENT_RATE_LIMIT

    @pytest.mark.parametrize("mo_ta,mong", [
        ("HTTP 503: unavailable", ErrorClass.TRANSIENT_PROVIDER),
        ("HTTP 500: internal", ErrorClass.TRANSIENT_PROVIDER),
        ("HTTP 408: request timeout", ErrorClass.TRANSIENT_NETWORK),
        ("TimeoutError: read timed out", ErrorClass.TRANSIENT_NETWORK),
        ("ConnectionResetError: connection reset", ErrorClass.TRANSIENT_NETWORK),
        ("HTTP 401: invalid key", ErrorClass.PERMANENT_CONFIG),
        ("HTTP 403: forbidden", ErrorClass.PERMANENT_CONFIG),
        ("HTTP 400: bad request", ErrorClass.PERMANENT_INPUT),
        ("FontNotFound: font_not_found", ErrorClass.PERMANENT_MODEL),
        ("InpaintWeightsMissing: weights", ErrorClass.PERMANENT_MODEL),
        ("no_region: page chưa có TextRegion", ErrorClass.PERMANENT_INPUT),
        ("missing_translation: vùng chưa dịch", ErrorClass.PERMANENT_INPUT),
    ])
    def test_cac_loai_con_lai(self, c, mo_ta, mong):
        assert c.classify(mo_ta=mo_ta) is mong

    def test_khong_nhan_ra_thi_khong_thu_lai(self, c):
        """Không đoán mò: lỗi lạ mà cứ thử lại là che mất lỗi thật."""
        loai = c.classify(mo_ta="chuyện gì đó rất lạ")
        assert loai is ErrorClass.UNKNOWN
        assert RetryPolicy().should_retry(loai, 0) is False


class TestChinhSachThuLai:
    def test_chi_thu_lai_loi_tam_thoi(self):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(ErrorClass.TRANSIENT_PROVIDER, 0) is True
        assert p.should_retry(ErrorClass.PERMANENT_MODEL, 0) is False
        assert p.should_retry(ErrorClass.PERMANENT_INPUT, 0) is False

    def test_khong_thu_lai_khi_het_quota(self):
        """Quota chưa hồi thì thử lại vẫn hỏng — mà mỗi lần thử là một lời gọi tính tiền."""
        assert RetryPolicy().should_retry(ErrorClass.QUOTA_EXHAUSTED, 0) is False

    def test_dung_dung_so_lan(self):
        p = RetryPolicy(max_retries=3)
        assert [p.should_retry(ErrorClass.TRANSIENT_PROVIDER, i) for i in range(5)] == [
            True, True, True, False, False
        ]

    def test_cho_lau_dan_va_co_tran(self):
        p = RetryPolicy(backoff_base_seconds=2, backoff_max_seconds=30, jitter=False)
        cho = [p.next_delay_seconds(i) for i in range(6)]
        assert cho == [2, 4, 8, 16, 30, 30], cho
        assert max(cho) <= 30

    def test_nhieu_ngau_nhien_tat_dinh_theo_khoa(self):
        """Nhiễu phải CÓ THẬT mà vẫn lặp lại được, nếu không thì không test nổi."""
        p = RetryPolicy(jitter=True)
        a = [p.next_delay_seconds(i, "trang-1") for i in range(4)]
        b = [p.next_delay_seconds(i, "trang-1") for i in range(4)]
        c = [p.next_delay_seconds(i, "trang-2") for i in range(4)]
        assert a == b, "cùng khoá phải ra cùng kết quả"
        assert a != c, "khác khoá phải ra khác — nếu không thì mọi trang gọi lại cùng lúc"

    def test_nhieu_khong_bao_gio_vuot_tran(self):
        p = RetryPolicy(backoff_base_seconds=2, backoff_max_seconds=10, jitter=True)
        assert all(0 <= p.next_delay_seconds(i, f"k{i}") <= 10 for i in range(20))


class TestGopTrangThaiMe:
    @pytest.mark.parametrize("items,mong", [
        ([S.completed, S.completed], BatchStatus.completed),
        ([S.completed, S.skipped], BatchStatus.completed),
        ([S.completed, S.failed], BatchStatus.partial_failed),
        ([S.failed, S.failed], BatchStatus.failed),
        ([S.blocked_quota, S.blocked_quota], BatchStatus.blocked_quota),
        ([S.completed, S.blocked_quota], BatchStatus.blocked_quota),
        ([S.completed, S.failed, S.blocked_quota], BatchStatus.partial_failed),
        ([], BatchStatus.completed),
    ])
    def test_suy_dung_trang_thai(self, items, mong):
        assert gop_trang_thai_me(items) is mong

    @pytest.mark.parametrize("items", [
        [S.completed, S.pending],
        [S.failed, S.pending],
        [S.blocked_quota, S.running],
        [S.pending],
    ])
    def test_con_viec_thi_van_la_dang_chay(self, items):
        """Báo partial_failed sớm khiến người vận hành tưởng mẻ đã dừng — chưa dừng thì phải nói chưa dừng."""
        assert gop_trang_thai_me(items) is BatchStatus.running

    def test_huy_thi_luon_la_da_huy(self):
        assert gop_trang_thai_me([S.completed, S.pending], da_huy=True) is BatchStatus.cancelled

    def test_khong_bao_gio_completed_khi_con_viec(self):
        """Đây là điều kiện quan trọng nhất của cả M9."""
        for chua_xong in (S.pending, S.running):
            for kem in (S.completed, S.failed, S.blocked_quota, S.skipped):
                assert gop_trang_thai_me([kem, chua_xong]) is not BatchStatus.completed


class TestBuocKeTiep:
    @pytest.mark.parametrize("trang_thai,mong", [
        (PageStatus.queued, "detect"),
        (PageStatus.detection_failed, "detect"),
        (PageStatus.detected, "ocr"),
        (PageStatus.ocr_done, "inpaint"),
        (PageStatus.inpainted, "translate"),
        (PageStatus.inpaint_needs_review, "translate"),
        (PageStatus.translated, "typeset"),
    ])
    def test_moi_trang_thai_ra_dung_buoc(self, trang_thai, mong):
        assert buoc_cho_trang(trang_thai) == mong

    def test_trang_da_xong_thi_khong_dung_vao(self):
        """Chạy lại trang đã xong là xoá mất kết quả đã có — kể cả phần vừa sửa tay ở M7."""
        assert buoc_cho_trang(PageStatus.typeset_done) is None
        assert buoc_cho_trang(PageStatus.ready_for_export) is None

    def test_trang_dang_chay_thi_khong_day_them(self):
        """Đẩy thêm việc lên trang đang chạy = hai job cùng ghi lên một trang."""
        assert buoc_cho_trang(PageStatus.detecting) is None


class TestCongNhip:
    """Cổng phải nguyên tử: `rate_limit` của Celery chỉ giới hạn từng worker, không toàn cục."""

    @pytest.fixture
    def cong(self):
        import os

        from app.services.batch.gate import GeminiProjectRateGate

        url = os.environ.get("REDIS_URL", "redis://localhost:6380/0").rsplit("/", 1)[0] + "/9"
        return GeminiProjectRateGate(url, rpm=5, cua_so_giay=60)

    def _don(self, cong, khoa):
        import redis

        redis.Redis.from_url(cong.redis_url).delete(f"{cong.tien_to}:{khoa}")

    def test_khoa_project_khong_bao_gio_chua_api_key(self):
        from app.services.batch.gate import GeminiProjectRateGate

        # Ghép lúc chạy chứ không viết liền một chuỗi: viết liền thì bộ quét khoá bí mật
        # (test_khong_co_api_key_nao_bi_commit_vao_git) sẽ kêu vì trông y hệt khoá thật —
        # và một cảnh báo kêu sai là một cảnh báo sẽ bị tắt.
        key = "AIza" + "SyD" + "-khoa-gia-chi-de-test-khong-duoc-lo-ra"
        khoa = GeminiProjectRateGate.khoa_project(key, "gemini")
        assert key not in khoa and "AIza" not in khoa
        assert len(khoa) == 16

    def test_duoi_gioi_han_thi_cho_qua(self, cong):
        khoa = cong.khoa_project("t-duoi")
        self._don(cong, khoa)
        assert all(cong.acquire(khoa).cho_phep for _ in range(5))

    def test_cham_gioi_han_thi_chan(self, cong):
        khoa = cong.khoa_project("t-cham")
        self._don(cong, khoa)
        for _ in range(5):
            cong.acquire(khoa)
        ket = cong.acquire(khoa)
        assert ket.cho_phep is False
        assert ket.ly_do == "rate_limited"
        assert ket.cho_giay > 0

    def test_nhieu_luong_tranh_nhau_khong_vuot_gioi_han(self, cong):
        """Đây là lý do phải dùng Redis nguyên tử thay vì đếm ở phía Python."""
        khoa = cong.khoa_project("t-dua")
        self._don(cong, khoa)
        qua = []
        ts = [threading.Thread(target=lambda: qua.append(cong.acquire(khoa).cho_phep))
              for _ in range(40)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert sum(1 for x in qua if x) == 5, f"vượt giới hạn: {sum(1 for x in qua if x)}/5"

    def test_dat_rpm_bang_0_thi_tat_cong(self, cong):
        from app.services.batch.gate import GeminiProjectRateGate

        tat = GeminiProjectRateGate(cong.redis_url, rpm=0)
        assert tat.acquire("bat-ky").cho_phep is True

    def test_redis_hong_thi_chan_chu_khong_mo_toang(self):
        """Mở toang khi cổng hỏng = đập thẳng vào quota nhà cung cấp."""
        from app.services.batch.gate import GeminiProjectRateGate

        hong = GeminiProjectRateGate("redis://khong-ton-tai-dau:6379/0", rpm=5)
        ket = hong.acquire("x")
        assert ket.cho_phep is False
        assert "gate_unavailable" in (ket.ly_do or "")


class TestNhieuMotNua:
    """Nhiễu không được phép rơi về gần 0 — đo thật ở Run B: chờ 0,2s sau lỗi 429."""

    def test_luon_cho_it_nhat_mot_nua_moc(self):
        from app.services.batch.errors import RetryPolicy

        cs = RetryPolicy(backoff_base_seconds=10, backoff_max_seconds=120)
        for lan in range(4):
            moc = min(10 * 2 ** lan, 120)
            for khoa in (f"muc-{i}" for i in range(50)):
                cho = cs.next_delay_seconds(lan, khoa_nhieu=khoa)
                assert moc / 2 <= cho <= moc, f"{cho} ngoài [{moc/2}, {moc}]"

    def test_van_con_nhieu_de_cac_trang_khong_goi_lai_cung_luc(self):
        from app.services.batch.errors import RetryPolicy

        cs = RetryPolicy(backoff_base_seconds=10)
        cac_gia = {cs.next_delay_seconds(0, khoa_nhieu=f"muc-{i}") for i in range(30)}
        assert len(cac_gia) > 20, "gần như mọi mục ra cùng một thời điểm chờ"
