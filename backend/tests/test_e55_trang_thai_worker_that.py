"""E55 — worker báo `starting` vĩnh viễn, và cách đọc ra trạng thái THẬT.

## Lỗi đang vá — đo được trên bản chạy thật

`deploy-start.sh` nhánh `ROLE=all` ghi `ghi_trang_thai starting` **một lần**, rồi chỉ ghi
`restarting` khi worker chết. Không có chỗ nào ghi `running`.

Đo 26-09 trên production: `trang_thai: "starting"` suốt **42 giờ**, trong khi cùng lúc
`rss_moc: "inpaint: sau"` chứng minh worker ĐÃ chạy xong một bước xoá chữ.

Một trạng thái đứng im như vậy **tệ hơn không có trạng thái**: người vận hành không phân biệt được
"đang nạp model" (mất tới cả phút, bình thường) với "chạy tốt hai ngày rồi".

## Vì sao dấu sẵn sàng phải do WORKER ghi

Shell không có cách nào biết worker đã nạp xong model — nó chỉ biết mình đã gọi lệnh. Và nó **không
được** để worker ghi chung tệp của mình: hai người ghi một tệp là mất dữ liệu của cả hai (lý do
ghi ở `config.worker_rss_file`). Nên đây là tệp THỨ BA, một người ghi.

## Bài canh nặng nhất

`test_shell_noi_restarting_thi_TIN_SHELL` — shell vừa **quan sát** một lần thoát, đó là bằng chứng
mạnh hơn một dấu sẵn sàng còn sót từ lần chạy trước. Đảo thứ tự hai nhánh này là báo "running" cho
một worker vừa chết.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.workers.trang_thai_worker import ghi_dau_san_sang


@pytest.fixture
def tep_tam(tmp_path, monkeypatch):
    """Trả (tệp trạng thái shell, tệp dấu sẵn sàng) và trỏ cả `/healthz` lẫn worker vào đó."""
    shell = tmp_path / "trang-thai-worker.json"
    ready = tmp_path / "worker-ready.json"
    monkeypatch.setenv("WORKER_STATE_FILE", str(shell))
    monkeypatch.setenv("WORKER_READY_FILE", str(ready))
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "worker_ready_file", str(ready))
    return shell, ready


def _dat_trang_thai_shell(tep: Path, trang_thai: str) -> None:
    tep.write_text(json.dumps({
        "trang_thai": trang_thai, "so_lan_chet": 0, "ma_thoat_gan_nhat": None,
        "luc": "2026-09-26T04:35:45Z",
    }))


class TestGhiDauSanSang:
    async def test_worker_ghi_duoc_dau_san_sang(self, client, tep_tam):
        _shell, ready = tep_tam
        luc = ghi_dau_san_sang()

        assert luc, "không trả về mốc thời gian"
        assert json.loads(ready.read_text())["san_sang_luc"] == luc

    async def test_ghi_khong_duoc_thi_tra_None_chu_KHONG_no(self, client, monkeypatch):
        """Một dấu hiệu quan sát không được phép ngăn worker nhận việc."""
        from app.core.config import get_settings

        monkeypatch.setattr(
            get_settings(), "worker_ready_file", "/khong-co-thu-muc-nay/ready.json"
        )
        assert ghi_dau_san_sang() is None


class TestHealthzSuyRaTrangThaiThuc:
    async def test_shell_noi_starting_ma_worker_DA_san_sang_thi_bao_running(
        self, client_chua_dang_nhap, tep_tam
    ):
        """**Chính lỗi đang vá.** Shell kẹt ở `starting`, worker đã nhận được việc."""
        shell, _ready = tep_tam
        _dat_trang_thai_shell(shell, "starting")
        ghi_dau_san_sang()

        w = (await client_chua_dang_nhap.get("/healthz")).json()["worker"]
        assert w["trang_thai"] == "starting", "trường cũ phải nói đúng thứ SHELL nghĩ"
        assert w["trang_thai_thuc"] == "running", w
        assert w["san_sang_luc"]

    async def test_chua_co_dau_san_sang_thi_GIU_NGUYEN_starting(
        self, client_chua_dang_nhap, tep_tam
    ):
        """Worker đang nạp model thật — KHÔNG được đoán là đã sẵn sàng."""
        shell, ready = tep_tam
        _dat_trang_thai_shell(shell, "starting")
        if ready.exists():
            ready.unlink()

        w = (await client_chua_dang_nhap.get("/healthz")).json()["worker"]
        assert w["trang_thai_thuc"] == "starting", w
        assert w["san_sang_luc"] is None

    async def test_shell_noi_restarting_thi_TIN_SHELL(self, client_chua_dang_nhap, tep_tam):
        """**Bài canh nặng nhất.** Shell vừa QUAN SÁT một lần thoát — bằng chứng mạnh hơn một dấu
        sẵn sàng còn sót từ lần chạy TRƯỚC.

        Đảo thứ tự hai nhánh là báo "running" cho một worker vừa chết.
        """
        shell, _ready = tep_tam
        ghi_dau_san_sang()                      # dấu của lần chạy trước, vẫn còn trên đĩa
        _dat_trang_thai_shell(shell, "restarting")

        w = (await client_chua_dang_nhap.get("/healthz")).json()["worker"]
        assert w["trang_thai_thuc"] == "restarting", (
            f"báo 'running' cho worker vừa chết vì tin dấu sẵn sàng cũ: {w}"
        )

    async def test_khong_co_tep_shell_thi_khong_bia(self, client_chua_dang_nhap, tep_tam):
        """Máy nhà chạy worker ở container riêng nên không có tệp này — không phải lỗi."""
        shell, ready = tep_tam
        if shell.exists():
            shell.unlink()
        if ready.exists():
            ready.unlink()

        w = (await client_chua_dang_nhap.get("/healthz")).json()["worker"]
        assert w["trang_thai"] == "khong_ro"
        assert w["trang_thai_thuc"] == "khong_ro", w

    async def test_khong_co_tep_shell_nhung_CO_dau_san_sang(self, client_chua_dang_nhap, tep_tam):
        """Worker chạy container riêng (compose ở máy nhà) vẫn ghi được dấu — và nó vẫn đáng tin."""
        shell, _ready = tep_tam
        if shell.exists():
            shell.unlink()
        ghi_dau_san_sang()

        w = (await client_chua_dang_nhap.get("/healthz")).json()["worker"]
        assert w["trang_thai_thuc"] == "running", w


class TestDuongDanMacDinhKhopNhau:
    async def test_mac_dinh_cua_config_khop_voi_healthz(self):
        """Lệch một chữ là `/healthz` đọc một tệp, worker ghi một tệp khác — và không ai thấy."""
        from pathlib import Path as P

        from app.core.config import get_settings

        goc = P(__file__).resolve().parents[1] / "app" / "main.py"
        assert 'WORKER_READY_FILE", "/tmp/worker-ready.json"' in goc.read_text(encoding="utf-8")
        assert get_settings().worker_ready_file == "/tmp/worker-ready.json"
