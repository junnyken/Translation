"""ĐX-2 + ĐX-3 — round-trip THẬT qua HTTP + Postgres.

ĐX-2: nhận cả chapter trong một gói ZIP/CBZ.
ĐX-3: engine dịch người dùng chọn phải đi được tới tận cột trong CSDL.

Phần chặn gói độc đã có test thuần ở `test_dx2_goi_nen_unit.py`; file này chỉ kiểm những gì
CHỈ round-trip thật mới thấy: đúng thứ tự `order` trong CSDL, job detect có được tạo không,
và **gói hỏng có để lại rác trong CSDL không**.
"""

from __future__ import annotations

import io
import zipfile

import sqlalchemy as sa
from PIL import Image

from app.models.enums import JobType, PageStatus


async def _create_project(client, **over):
    payload = {"name": "Chapter gói", "source_lang": "ja", "intended_use": "personal"} | over
    return await client.post("/api/v1/projects", json=payload)


def _anh(mau: str = "white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), mau).save(buf, format="PNG")
    return buf.getvalue()


def _goi(muc: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ten, data in muc.items():
            zf.writestr(ten, data)
    return buf.getvalue()


async def _gui_goi(client, project_id, goi: bytes, ten="chapter.cbz", **data):
    return await client.post(
        f"/api/v1/projects/{project_id}/pages/archive",
        files={"file": (ten, goi, "application/zip")},
        data=data,
    )


class TestNhanGoi:
    async def test_gói_cbz_vao_du_trang_dung_thu_tu_trong_csdl(
        self, client, session, storage_root
    ):
        """Thứ tự phải là thứ tự TỰ NHIÊN, và phải đúng trong CSDL chứ không chỉ trong phản hồi."""
        project_id = (await _create_project(client)).json()["id"]
        goi = _goi({f"p{i}.png": _anh() for i in (1, 2, 10, 3)})

        r = await _gui_goi(client, project_id, goi)
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["so_trang"] == 4
        assert body["bo_qua"] == 0
        assert [t["ten_trong_goi"] for t in body["trang"]] == [
            "p1.png", "p2.png", "p3.png", "p10.png",
        ]
        assert [t["order"] for t in body["trang"]] == [1, 2, 3, 4]

        thu_tu = (await session.execute(
            sa.text("SELECT \"order\" FROM page WHERE project_id = :p ORDER BY \"order\""),
            {"p": project_id},
        )).scalars().all()
        assert thu_tu == [1, 2, 3, 4]

    async def test_moi_trang_co_mot_job_detect(self, client, session, storage_root):
        project_id = (await _create_project(client)).json()["id"]
        r = await _gui_goi(client, project_id, _goi({f"{i}.png": _anh() for i in (1, 2)}))
        assert r.status_code == 202

        for trang in r.json()["trang"]:
            jobs = await client.get(f"/api/v1/pages/{trang['page_id']}/jobs")
            assert [j["type"] for j in jobs.json()] == [JobType.detect.value]
            assert (await client.get(f"/api/v1/pages/{trang['page_id']}")).json()["status"] == (
                PageStatus.queued.value
            )

    async def test_dem_dung_so_muc_bo_qua(self, client, storage_root):
        """Gói 3 mục mà chỉ vào 2 trang thì phải NÓI ra, không im lặng."""
        project_id = (await _create_project(client)).json()["id"]
        goi = _goi({"01.png": _anh(), "ComicInfo.xml": b"<ComicInfo/>", "02.png": _anh()})

        body = (await _gui_goi(client, project_id, goi)).json()
        assert body["so_trang"] == 2
        assert body["bo_qua"] == 1

    async def test_gui_goi_hai_lan_thi_order_chay_tiep_khong_dam_len_nhau(
        self, client, storage_root
    ):
        project_id = (await _create_project(client)).json()["id"]
        await _gui_goi(client, project_id, _goi({"a1.png": _anh(), "a2.png": _anh()}))
        r2 = await _gui_goi(client, project_id, _goi({"b1.png": _anh()}))
        assert [t["order"] for t in r2.json()["trang"]] == [3]


class TestGoiXauKhongDeLaiRac:
    async def test_goi_rong_tra_422_va_KHONG_tao_trang_nao(self, client, session, storage_root):
        """Thất bại phải lùi sạch — để lại chapter rỗng trông như đã nhận việc là hỏng im lặng."""
        project_id = (await _create_project(client)).json()["id"]

        r = await _gui_goi(client, project_id, _goi({"ComicInfo.xml": b"<x/>"}))
        assert r.status_code == 422

        con_lai = await session.scalar(
            sa.text("SELECT count(*) FROM page WHERE project_id = :p"), {"p": project_id}
        )
        assert con_lai == 0

    async def test_duong_dan_thoat_thu_muc_tra_422(self, client, storage_root):
        project_id = (await _create_project(client)).json()["id"]
        goi = _goi({"../thoat.png": _anh(), "01.png": _anh()})
        assert (await _gui_goi(client, project_id, goi)).status_code == 422

    async def test_khong_phai_zip_tra_422(self, client, storage_root):
        project_id = (await _create_project(client)).json()["id"]
        assert (await _gui_goi(client, project_id, _anh())).status_code == 422

    async def test_pdf_tra_422_noi_dung_ly_do_that(self, client, storage_root):
        """PDF chưa hỗ trợ — phải nói thẳng lý do, không để người dùng nhận lỗi khó hiểu."""
        project_id = (await _create_project(client)).json()["id"]
        r = await _gui_goi(client, project_id, b"%PDF-1.7\n%rest", ten="chapter.pdf")
        assert r.status_code == 422
        assert "pdf_chua_ho_tro" in r.json()["detail"]

    async def test_file_rong_tra_422(self, client, storage_root):
        project_id = (await _create_project(client)).json()["id"]
        assert (await _gui_goi(client, project_id, b"")).status_code == 422

    async def test_project_khong_ton_tai_tra_404(self, client, storage_root):
        import uuid as _u

        r = await _gui_goi(client, str(_u.uuid4()), _goi({"01.png": _anh()}))
        assert r.status_code == 404

    async def test_chapter_nguoi_khac_khong_gui_goi_vao_duoc(
        self, client, client_b, storage_root
    ):
        project_id = (await _create_project(client)).json()["id"]
        r = await _gui_goi(client_b, project_id, _goi({"01.png": _anh()}))
        assert r.status_code == 404


class TestDX3EngineDiTuUITolCSDL:
    """ĐX-3 — lựa chọn engine phải tới được CỘT trong CSDL.

    Đây là nửa GHI. Nửa ĐỌC (pipeline đầy đủ có thật sự dùng cột đó không) nằm ở
    `test_dx3_engine_pipeline_day_du.py` — thiếu một trong hai nửa thì tính năng chết im lặng.
    """

    async def test_khong_chon_engine_thi_cot_de_NULL(self, client, session, storage_root):
        project_id = (await _create_project(client)).json()["id"]
        r = await client.post(
            f"/api/v1/projects/{project_id}/pages",
            files={"file": ("p.png", _anh(), "image/png")},
        )
        assert r.status_code == 202
        cot = await session.scalar(
            sa.text("SELECT translate_engine_override FROM page WHERE id = :i"),
            {"i": r.json()["page_id"]},
        )
        assert cot is None

    async def test_chon_google_fast_thi_LUU_dung_google_fast_khong_de_NULL(
        self, client, session, storage_root
    ):
        """Lưu đúng lựa chọn, KHÔNG quy về NULL.

        Để NULL thì trang này sẽ đi theo `translate_default_engine` của hệ thống — đổi mặc định
        đó một ngày nào đó sẽ âm thầm biến lựa chọn "miễn phí" của người dùng thành engine tốn
        token. Lựa chọn của người dùng phải được ghi đúng như họ chọn.
        """
        project_id = (await _create_project(client)).json()["id"]
        r = await client.post(
            f"/api/v1/projects/{project_id}/pages",
            files={"file": ("p.png", _anh(), "image/png")},
            data={"engine": "google_fast"},
        )
        assert r.status_code == 202
        cot = await session.scalar(
            sa.text("SELECT translate_engine_override FROM page WHERE id = :i"),
            {"i": r.json()["page_id"]},
        )
        assert cot == "google_fast"

    async def test_engine_ap_cho_MOI_trang_trong_goi(self, client, session, storage_root):
        project_id = (await _create_project(client)).json()["id"]
        goi = _goi({f"{i}.png": _anh() for i in (1, 2, 3)})

        r = await _gui_goi(client, project_id, goi, engine="google_fast")
        assert r.status_code == 202, r.text

        cot = (await session.execute(
            sa.text("SELECT translate_engine_override FROM page WHERE project_id = :p"),
            {"p": project_id},
        )).scalars().all()
        assert cot == ["google_fast"] * 3

    async def test_llm_context_chua_cau_hinh_khoa_thi_tra_422_khong_nhan_trang_nao(
        self, client, session, storage_root
    ):
        """Chưa có khoá Gemini mà chọn llm_context ⇒ chặn NGAY, đừng nhận trang rồi hỏng sau."""
        project_id = (await _create_project(client)).json()["id"]

        r = await _gui_goi(client, project_id, _goi({"01.png": _anh()}), engine="llm_context")
        assert r.status_code == 422
        assert "llm_not_configured" in r.json()["detail"]

        con_lai = await session.scalar(
            sa.text("SELECT count(*) FROM page WHERE project_id = :p"), {"p": project_id}
        )
        assert con_lai == 0
