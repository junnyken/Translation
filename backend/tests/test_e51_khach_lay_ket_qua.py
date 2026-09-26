"""E51 — khách lạ nhận về ẢNH ĐÃ DỊCH, và gói nhiều trang thành một tệp.

## Vì sao phần này cần thiết, không phải tiện nghi

Trước E51, chapter của khách chạy chế độ `chi_chu`: bỏ hẳn bước xoá chữ và căn chữ, dừng ở
`translated`, chỉ trả **toạ độ + chữ dịch** cho tiện ích phủ lên ảnh gốc. Nghĩa là khách **không
có tệp nào** — và §3 đặc tả (tự động tải về) chẳng có gì để tải, còn luật 30 phút của E50 chỉ xoá
ảnh gốc với mấy dòng chữ.

## Ba bài canh nặng nhất

* `test_che_do_day_du_KHONG_bao_xong_o_translated` — bản trước E51 gộp cả ba trạng thái vào một
  danh sách cứng, nên chế độ đầy đủ **báo xong sớm một bước** (lúc đó chưa căn chữ) và client đi
  lấy một ảnh chưa tồn tại.
* `test_MAC_DINH_van_la_chi_chu` — tiện ích E19 đang chạy thật. Đổi mặc định là làm nó tốn thêm
  bước xoá chữ + căn chữ mà nó không dùng tới, và chậm gấp đôi không lý do.
* `test_khach_KHONG_xuat_duoc_chapter_cua_nguoi_khac` — chỗ này là **điểm mù** của
  `test_quyen_cheo_tai_khoan` (bài đó gửi `json={}` nên dừng ở 422 trước khi tới phép kiểm
  quyền). Gộp chapter của người khác vào tệp của mình là lỗ IDOR.
"""
from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import Page, Project
from app.models.enums import ChePipeline, ExportFormat, PageStatus, SourceLang
from app.services.storage import get_storage
from app.services.typeset.paths import preview_relative_path


def _anh() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def st():
    return get_settings()


@pytest.fixture
def cookie_chay_duoc_tren_http(st, monkeypatch):
    monkeypatch.setattr(st, "cookie_khach_secure", False)


async def _gui(client, che_do: str | None = None):
    data = {"source_lang": SourceLang.ja.value}
    if che_do is not None:
        data["che_do"] = che_do
    return await client.post(
        "/api/v1/doc-truyen/trang", files={"file": ("t.png", _anh(), "image/png")}, data=data
    )


def _dat_trang_thai(page_id, tt: PageStatus) -> None:
    with sync_session() as s:
        s.execute(sa.update(Page).where(Page.id == page_id).values(status=tt))
        s.commit()


def _ghi_anh_preview(page_id) -> str:
    rel = preview_relative_path(page_id)
    get_storage().save(rel, _anh())
    return rel


def _project_cua_trang(page_id) -> Project:
    with sync_session() as s:
        pg = s.get(Page, page_id)
        return s.get(Project, pg.project_id)


class TestCheDoPipeline:
    async def test_MAC_DINH_van_la_chi_chu(self, client_chua_dang_nhap, cookie_chay_duoc_tren_http):
        """**Bài canh.** Tiện ích E19 đang chạy thật và KHÔNG gửi `che_do`.

        Đổi mặc định là bắt nó chạy thêm xoá chữ + căn chữ — hai bước đắt nhất, hai bước duy nhất
        cần mô hình LaMa 1,5 GB — cho một thứ nó không dùng tới.
        """
        trang = (await _gui(client_chua_dang_nhap)).json()["page_id"]
        assert _project_cua_trang(trang).che_do_pipeline is ChePipeline.chi_chu

    async def test_day_du_tao_chapter_che_do_day_du(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        assert _project_cua_trang(trang).che_do_pipeline is ChePipeline.day_du

    async def test_hai_che_do_TACH_chapter_rieng(
        self, client_chua_dang_nhap, session, cookie_chay_duoc_tren_http
    ):
        """Để chung một chapter thì trang phủ-chữ và trang đã-căn-chữ lẫn vào nhau, mà hai loại
        đó có đích khác nhau — cổng xuất sẽ không biết trang nào xuất được."""
        await _gui(client_chua_dang_nhap)
        await _gui(client_chua_dang_nhap, "day_du")

        with sync_session() as s:
            che_do = sorted(
                r.che_do_pipeline.value for r in s.execute(
                    sa.select(Project).where(Project.chu_khach.isnot(None))
                ).scalars().all()
            )
        assert che_do == ["chi_chu", "day_du"], che_do

    async def test_che_do_sai_thi_422(self, client_chua_dang_nhap, cookie_chay_duoc_tren_http):
        assert (await _gui(client_chua_dang_nhap, "khong_co_che_do_nay")).status_code == 422


class TestCoXong:
    async def test_che_do_day_du_KHONG_bao_xong_o_translated(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        """**Bài canh nặng nhất.** `translated` là ĐÍCH của `chi_chu` nhưng là GIỮA ĐƯỜNG của
        `day_du` — lúc đó chưa căn chữ, chưa có ảnh nào.

        Gộp cả ba trạng thái vào một danh sách cứng (bản trước E51) làm chế độ đầy đủ báo xong
        sớm một bước, và client đi lấy một ảnh chưa tồn tại.
        """
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.translated)

        than = (await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}")).json()
        assert than["xong"] is False, "báo xong trong khi chưa căn chữ"
        assert than["anh_da_dich"] is None

    async def test_che_do_chi_chu_VE_DICH_o_translated(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        """Đối chứng: `chi_chu` không bao giờ tới `typeset_done`, chờ nó là chờ mãi."""
        trang = (await _gui(client_chua_dang_nhap)).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.translated)

        than = (await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}")).json()
        assert than["xong"] is True
        assert than["anh_da_dich"] is None, "chế độ chỉ-chữ không sinh ảnh nào"

    async def test_day_du_xong_thi_co_duong_lay_anh(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.typeset_done)

        than = (await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}")).json()
        assert than["xong"] is True
        assert than["anh_da_dich"] == f"/api/v1/doc-truyen/trang/{trang}/anh"
        assert than["che_do"] == "day_du"


class TestLayAnh:
    async def test_lay_duoc_anh_da_dich(self, client_chua_dang_nhap, cookie_chay_duoc_tren_http):
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.typeset_done)
        _ghi_anh_preview(trang)

        r = await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}/anh")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n", "không phải PNG thật"

    async def test_chua_can_chu_thi_404_kem_LY_DO_doc_duoc(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        """Thông báo mơ hồ làm người dùng tưởng hỏng. Phải nói rõ là CHƯA XONG."""
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        r = await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}/anh")

        assert r.status_code == 404
        assert "chưa chạy xong" in r.json()["detail"], r.json()

    async def test_che_do_chi_chu_thi_404_noi_RO_vi_sao(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        """'Không có ảnh' vì chế độ khác hẳn 'chưa xong' — nói gộp thì người dùng chờ vô ích."""
        trang = (await _gui(client_chua_dang_nhap)).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.translated)
        _ghi_anh_preview(trang)  # dù có tệp, chế độ này vẫn không được trả

        r = await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}/anh")
        assert r.status_code == 404
        assert "chi_chu" in r.json()["detail"], r.json()


class TestKhongAiLayDuocCuaAi:
    async def test_khach_KHAC_khong_lay_duoc_anh(self, client_chua_dang_nhap, st, monkeypatch):
        monkeypatch.setattr(st, "cookie_khach_secure", False)
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.typeset_done)
        _ghi_anh_preview(trang)

        client_chua_dang_nhap.cookies.clear()
        client_chua_dang_nhap.cookies.set("ma_khach", "cookie-khach-khac")
        r = await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}/anh")
        assert r.status_code == 404, f"khách khác lấy được ảnh: {r.status_code}"

    async def test_NGUOI_DANG_NHAP_khong_lay_duoc_anh_cua_khach(
        self, client_chua_dang_nhap, client, cookie_chay_duoc_tren_http
    ):
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.typeset_done)
        _ghi_anh_preview(trang)

        r = await client.get(f"/api/v1/doc-truyen/trang/{trang}/anh")
        assert r.status_code == 404, f"người đăng nhập lấy được ảnh của khách: {r.status_code}"


class TestGoiTaiVe:
    async def test_khach_xuat_duoc_chapter_CUA_MINH(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        """§3.3 — nhiều trang phải gói thành MỘT tệp, nếu không là 24 lần bị trình duyệt hỏi."""
        trang = (await _gui(client_chua_dang_nhap, "day_du")).json()["page_id"]
        _dat_trang_thai(trang, PageStatus.typeset_done)
        pid = _project_cua_trang(trang).id

        r = await client_chua_dang_nhap.post(
            f"/api/v1/projects/{pid}/export", json={"format": ExportFormat.cbz.value}
        )
        assert r.status_code == 202, r.text
        assert r.json()["job_id"]

    async def test_khach_KHONG_xuat_duoc_chapter_cua_nguoi_khac(
        self, client, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        """**Bài canh.** Đây là ĐIỂM MÙ của `test_quyen_cheo_tai_khoan`: bài đó gửi `json={}` nên
        dừng ở 422 trước khi tới phép kiểm quyền. Ở đây thân request HỢP LỆ.

        Gộp chapter của người khác vào tệp của mình là lỗ IDOR.
        """
        cua_nguoi_dung = (await client.post(
            "/api/v1/projects",
            json={"name": "Của tài khoản", "source_lang": "ja", "intended_use": "personal"},
        )).json()["id"]

        r = await client_chua_dang_nhap.post(
            f"/api/v1/projects/{cua_nguoi_dung}/export",
            json={"format": ExportFormat.cbz.value},
        )
        assert r.status_code == 404, f"khách xuất được chapter của tài khoản: {r.status_code}"

    async def test_khach_KHONG_doc_duoc_export_job_cua_nguoi_khac(
        self, client, client_chua_dang_nhap, sample_page_image, cookie_chay_duoc_tren_http
    ):
        pid = (await client.post(
            "/api/v1/projects",
            json={"name": "X", "source_lang": "ja", "intended_use": "personal"},
        )).json()["id"]
        await client.post(
            f"/api/v1/projects/{pid}/pages",
            files={"file": ("p.png", sample_page_image, "image/png")},
        )
        job = (await client.post(
            f"/api/v1/projects/{pid}/export", json={"format": ExportFormat.cbz.value}
        )).json()["job_id"]

        for duong in (f"/api/v1/export-jobs/{job}", f"/api/v1/export-jobs/{job}/download"):
            r = await client_chua_dang_nhap.get(duong)
            assert r.status_code == 404, f"{duong} → {r.status_code}"
