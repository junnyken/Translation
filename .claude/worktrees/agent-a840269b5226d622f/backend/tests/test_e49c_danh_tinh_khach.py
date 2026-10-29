"""E49c — nhận diện chủ thể hạn mức: cookie + IP, băm, và luật tin proxy.

## Ba bài canh nặng nhất

* `test_MAC_DINH_khong_tin_x_forwarded_for` — tin header do client gửi là **xoá sổ chốt IP mà
  không ai thấy**: ai cũng tự đặt "IP" khác nhau mỗi lần gọi.
* `test_chu_the_KHONG_chua_IP_tho` — sổ cái chỉ cần biết "có phải cùng một người không". Lưu IP
  thô là giữ dữ liệu cá nhân không dùng tới.
* `test_muoi_khac_nhau_cho_bam_khac_nhau` — muối phải thật sự đi vào phép băm. Muối bị bỏ quên
  thì băm vẫn chạy, hạn mức vẫn đúng, và **không bài test nào đỏ** — trừ bài này.
"""
from __future__ import annotations

import pytest
from starlette.requests import Request

from app.core.config import get_settings
from app.core.danh_tinh_khach import (
    TEN_COOKIE,
    bam,
    chot_cho_khach,
    ip_cua,
)
from app.core.danh_tinh_khach import log as log_danh_tinh
from app.models.enums import LoaiChuThe

IP_THAT = "203.0.113.9"


@pytest.fixture
def bat_canh_bao(caplog):
    """Bật lại logger rồi mới bắt log — **bắt buộc trong bộ test này**.

    `alembic/env.py` gọi `fileConfig(...)`, mà `logging.config.fileConfig` mặc định
    `disable_existing_loggers=True`: nó đặt `disabled = True` cho MỌI logger đã tồn tại lúc đó
    và không được khai trong `alembic.ini`. `conftest` chạy migration trong CÙNG tiến trình với
    bộ test ⇒ `app.core.danh_tinh_khach` bị tắt hẳn.

    `Logger.handle` kiểm `self.disabled` **trước** khi gọi handler, nên gắn handler riêng cũng
    vô ích — phải bật lại cờ.

    ⚠️ Đừng suy ra rằng production cũng mất log: `deploy/docker-compose.yml` và
    `deploy-start.sh` chạy `alembic upgrade head` ở **tiến trình riêng** rồi mới khởi động
    `uvicorn`, nên tiến trình phục vụ không hề bị `fileConfig` đụng tới. Đây là hiện tượng chỉ
    có trong bộ test.
    """
    cu = log_danh_tinh.disabled
    log_danh_tinh.disabled = False
    with caplog.at_level("WARNING", logger=log_danh_tinh.name):
        yield caplog
    log_danh_tinh.disabled = cu


@pytest.fixture
def st():
    """Cấu hình thật (`get_settings` có `lru_cache` nên đây đúng là đối tượng cả app đang dùng)."""
    return get_settings()


def _req(
    *, headers: dict[str, str] | None = None, cookies: dict[str, str] | None = None,
    client: tuple[str, int] | None = (IP_THAT, 44321),
) -> Request:
    """Request Starlette THẬT, không phải đồ giả — để bài test đi đúng đường mã sản phẩm chạy."""
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        raw.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
    return Request({
        "type": "http", "http_version": "1.1", "method": "POST", "path": "/", "raw_path": b"/",
        "root_path": "", "scheme": "http", "query_string": b"", "headers": raw,
        "client": client, "server": ("test", 80),
    })


class TestBam:
    def test_cung_gia_tri_cho_cung_bam(self, st):
        assert bam("1.2.3.4", st) == bam("1.2.3.4", st)

    def test_gia_tri_khac_cho_bam_khac(self, st):
        assert bam("1.2.3.4", st) != bam("1.2.3.5", st)

    def test_muoi_khac_nhau_cho_bam_khac_nhau(self, st, monkeypatch):
        """**Bài canh.** Muối bị bỏ quên trong phép băm thì mọi bài khác vẫn xanh."""
        monkeypatch.setattr(st, "muoi_bam_khach", "muoi-mot")
        mot = bam("1.2.3.4", st)
        monkeypatch.setattr(st, "muoi_bam_khach", "muoi-hai")
        assert bam("1.2.3.4", st) != mot, "muối không đi vào phép băm"

    def test_do_dai_on_dinh_va_vua_cot(self, st):
        assert len(bam("x" * 500, st)) == 32


class TestLayIP:
    def test_mac_dinh_lay_dia_chi_ket_noi(self, st, monkeypatch):
        monkeypatch.setattr(st, "tin_header_proxy", False)
        assert ip_cua(_req(), st) == IP_THAT

    def test_MAC_DINH_khong_tin_x_forwarded_for(self, st, monkeypatch):
        """**Bài canh nặng nhất.** Header do client gửi và sửa được tuỳ ý.

        Tin nó khi chưa có proxy ghi đè nghĩa là mỗi request tự xưng một IP khác ⇒ chốt IP biến
        mất trong im lặng, mà hạn mức vẫn trông như đang hoạt động.
        """
        r = _req(headers={"x-forwarded-for": "9.9.9.9"})
        assert ip_cua(r, st) == IP_THAT, "tin X-Forwarded-For khi chưa được phép"

    def test_bat_tin_proxy_thi_lay_muc_TRAI_NHAT(self, st, monkeypatch):
        """Trái nhất là client gốc; các mục sau là chuỗi proxy."""
        monkeypatch.setattr(st, "tin_header_proxy", True)
        r = _req(headers={"x-forwarded-for": "198.51.100.7, 10.0.0.1, 10.0.0.2"})
        assert ip_cua(r, st) == "198.51.100.7"

    def test_bat_tin_proxy_ma_header_rong_thi_lui_ve_dia_chi_ket_noi(self, st, monkeypatch):
        monkeypatch.setattr(st, "tin_header_proxy", True)
        assert ip_cua(_req(headers={"x-forwarded-for": "  "}), st) == IP_THAT

    def test_khong_xac_dinh_duoc_thi_tra_None_chu_khong_doan(self, st):
        assert ip_cua(_req(client=None), st) is None


class TestChotKhachLa:
    def test_chua_co_cookie_thi_cap_moi_va_co_DU_HAI_chot(self, st, monkeypatch):
        monkeypatch.setattr(st, "tin_header_proxy", False)
        chot, cookie_moi = chot_cho_khach(_req(), st)

        assert cookie_moi, "không cấp cookie ⇒ lần sau lại là khách mới"
        assert [c.loai for c in chot] == [LoaiChuThe.khach_cookie, LoaiChuThe.khach_ip]

    def test_da_co_cookie_thi_KHONG_cap_lai(self, st):
        chot, cookie_moi = chot_cho_khach(_req(cookies={TEN_COOKIE: "ma-cu"}), st)
        assert cookie_moi is None
        assert chot[0].chu_the == bam("ma-cu", st)

    def test_cung_cookie_cung_IP_ra_cung_chu_the(self, st):
        a, _ = chot_cho_khach(_req(cookies={TEN_COOKIE: "ma-cu"}), st)
        b, _ = chot_cho_khach(_req(cookies={TEN_COOKIE: "ma-cu"}), st)
        assert [c.chu_the for c in a] == [c.chu_the for c in b]

    def test_doi_cookie_thi_chot_cookie_doi_nhung_chot_IP_GIU_NGUYEN(self, st):
        """Đây chính là cơ chế chặn xoá cookie lấy lượt mới."""
        a, _ = chot_cho_khach(_req(cookies={TEN_COOKIE: "ma-mot"}), st)
        b, _ = chot_cho_khach(_req(cookies={TEN_COOKIE: "ma-hai"}), st)

        assert a[0].chu_the != b[0].chu_the, "đổi cookie mà chốt cookie không đổi"
        assert a[1].chu_the == b[1].chu_the, "đổi cookie mà chốt IP cũng đổi ⇒ chốt IP vô dụng"

    def test_chu_the_KHONG_chua_IP_tho(self, st):
        """**Bài canh.** Sổ cái chỉ cần biết 'có phải cùng một người không'."""
        chot, _ = chot_cho_khach(_req(), st)
        assert all(IP_THAT not in c.chu_the for c in chot), "IP thô lọt vào sổ cái"

    def test_tran_IP_phai_LON_HON_tran_cookie(self, st):
        """Bằng nhau là chặn oan văn phòng/trường học/quán cà phê dùng chung IP."""
        chot, _ = chot_cho_khach(_req(), st)
        cookie, ip = chot[0], chot[1]
        assert ip.tran > cookie.tran, f"trần IP {ip.tran} không lớn hơn trần cookie {cookie.tran}"

    def test_khong_co_IP_thi_CHI_con_chot_cookie(self, st, bat_canh_bao):
        """Hạ cấp có thật — lúc đó xoá cookie là vượt được. Phải ghi lại, không im lặng."""
        chot, _ = chot_cho_khach(_req(client=None), st)

        assert [c.loai for c in chot] == [LoaiChuThe.khach_cookie]
        assert any(
            "IP người gọi" in r.getMessage() for r in bat_canh_bao.records
        ), f"hạ cấp mà không ghi cảnh báo; đã bắt được: {[r.getMessage() for r in bat_canh_bao.records]}"
