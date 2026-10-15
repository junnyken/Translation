"""E78 — xuất PSD nhiều lớp.

Hai bộ đọc ĐỘC LẬP kiểm cùng một tệp:
- `doc_psd` dưới đây: bộ đọc tối giản viết theo đặc tả, đọc LẠI từng byte (cờ ẩn, `luni`, kênh).
- Pillow (`PsdImagePlugin`): không do dự án viết — mở được ảnh ghép + danh sách lớp + điểm ảnh lớp
  là bằng chứng tệp hợp lệ với một bộ đọc bên ngoài, không chỉ với chính bộ ghi của mình.

Phần tích hợp chạy export thật trên Postgres với chapter dựng qua pipeline M2→M6 (fixture của
`test_export_integration.py`).
"""
from __future__ import annotations

import io
import struct
import uuid
import zipfile
from pathlib import Path

import numpy as np
import pytest
import sqlalchemy as sa
from PIL import Image, ImageDraw

from app.core.db_sync import sync_session
from app.models import Page, TextRegion, TypesetResult
from app.services.export.chapter import ChapterExporter, TrangCanXuat, ten_lop_vung
from app.services.export.psd import CO_AN, LopPsd, PsdQuaLon, ghi_psd
from app.services.interfaces import BBox
from app.services.storage import LocalObjectStorage
from app.services.typeset.preview import PagePreviewRenderer, RegionDraw
from tests.test_export_integration import _xuat, chapter  # noqa: F401 — fixture dùng lại


# ======================= bộ đọc PSD tối giản (chỉ cho test) =======================


def doc_psd(data: bytes) -> dict:
    """Đọc đúng tập con mà bộ ghi E78 sinh ra. Sai một byte độ dài là assert/struct nổ ngay."""
    p = 0

    def lay(n):
        nonlocal p
        b = data[p:p + n]
        assert len(b) == n, f"thiếu dữ liệu ở byte {p}"
        p += n
        return b

    def u(fmt):
        return struct.unpack(fmt, lay(struct.calcsize(fmt)))

    assert lay(4) == b"8BPS"
    (version,) = u(">H")
    assert version == 1
    assert lay(6) == b"\x00" * 6
    so_kenh, cao, rong, do_sau, che_do = u(">HIIHH")
    (n,) = u(">I"); lay(n)  # color mode data
    (n,) = u(">I"); lay(n)  # image resources
    (do_dai_lm,) = u(">I")
    ket_lm = p + do_dai_lm
    (do_dai_li,) = u(">I")
    ket_li = p + do_dai_li
    (so_lop,) = u(">h")
    lop = []
    for _ in range(abs(so_lop)):
        top, left, bottom, right = u(">iiii")
        (nk,) = u(">H")
        kenh = [u(">hI") for _ in range(nk)]
        assert lay(4) == b"8BIM"
        blend = lay(4)
        opacity, clipping, co, _filler = u(">BBBB")
        (do_dai_phu,) = u(">I")
        ket_phu = p + do_dai_phu
        (n,) = u(">I"); lay(n)  # mask
        (n,) = u(">I"); lay(n)  # blending ranges
        (n_ten,) = u(">B")
        ten_ascii = lay(n_ten).decode("latin-1")
        lay((-(1 + n_ten)) % 4)
        ten_luni = None
        while p < ket_phu:
            assert lay(4) in (b"8BIM", b"8B64")
            khoa = lay(4)
            (n,) = u(">I")
            khoi = lay(n)
            if khoa == b"luni":
                (so_ky_tu,) = struct.unpack(">I", khoi[:4])
                ten_luni = khoi[4:4 + 2 * so_ky_tu].decode("utf-16-be")
        assert p == ket_phu, "độ dài extra data sai"
        lop.append(dict(top=top, left=left, bottom=bottom, right=right, kenh=kenh,
                        blend=blend, opacity=opacity, an=bool(co & CO_AN),
                        ten_ascii=ten_ascii, ten=ten_luni))
    for l_ in lop:
        h, w = l_["bottom"] - l_["top"], l_["right"] - l_["left"]
        l_["mang"] = {}
        for id_kenh, dai in l_["kenh"]:
            (nen,) = u(">H")
            assert nen == 0, "bộ ghi E78 chỉ ghi RAW"
            assert dai == 2 + h * w, "độ dài kênh khai trong record khác dữ liệu thật"
            l_["mang"][id_kenh] = np.frombuffer(lay(h * w), dtype=np.uint8).reshape(h, w)
    assert p <= ket_li
    p = ket_li
    (n,) = u(">I"); lay(n)  # global layer mask
    assert p == ket_lm, "độ dài phần layer & mask sai"
    (nen,) = u(">H")
    assert nen == 0
    mat = [np.frombuffer(lay(rong * cao), dtype=np.uint8).reshape(cao, rong) for _ in range(so_kenh)]
    assert p == len(data), "còn byte thừa cuối tệp"
    return dict(rong=rong, cao=cao, so_kenh=so_kenh, do_sau=do_sau, che_do=che_do,
                so_lop=so_lop, lop=lop, ghep=np.stack(mat, axis=-1))


def _lop_rgba(l_: dict, kich_thuoc) -> Image.Image:
    """Dựng lại lớp cỡ canvas từ dữ liệu đã đọc."""
    rong, cao = kich_thuoc
    ra = np.zeros((cao, rong, 4), dtype=np.uint8)
    m = l_["mang"]
    if l_["bottom"] > l_["top"]:
        ra[l_["top"]:l_["bottom"], l_["left"]:l_["right"]] = np.stack(
            [m[0], m[1], m[2], m[-1]], axis=-1)
    return Image.fromarray(ra, "RGBA")


# ======================= (a) đơn vị: bộ ghi PSD =======================


def _psd_mau(rong=60, cao=41) -> tuple[bytes, Image.Image]:
    goc = Image.new("RGB", (rong, cao), (200, 10, 10))
    sach = Image.new("RGB", (rong, cao), (255, 255, 255))
    chu = Image.new("RGBA", (rong, cao), (0, 0, 0, 0))
    ImageDraw.Draw(chu).rectangle([10, 5, 30, 20], fill=(0, 0, 255, 255))
    ghep = sach.copy()
    ghep.paste(chu, (0, 0), chu)
    bo = io.BytesIO()
    ghi_psd(bo, (rong, cao), [
        LopPsd("Ảnh gốc", goc, an=True),
        LopPsd("Đã xoá chữ", sach),
        LopPsd("Vùng 1: Xin chào bạn", chu),
    ], ghep)
    return bo.getvalue(), ghep


class TestBoGhiPsd:
    def test_cau_truc_byte_doc_lai_duoc(self):
        data, ghep = _psd_mau()
        kq = doc_psd(data)
        assert (kq["rong"], kq["cao"], kq["so_kenh"], kq["do_sau"], kq["che_do"]) == (60, 41, 3, 8, 3)
        assert kq["so_lop"] == 3
        ten = [l_["ten"] for l_ in kq["lop"]]
        assert ten == ["Ảnh gốc", "Đã xoá chữ", "Vùng 1: Xin chào bạn"], "tên Unicode qua luni"
        assert kq["lop"][0]["ten_ascii"] == "Anh goc", "Pascal name ASCII dự phòng, bỏ dấu"
        assert [l_["an"] for l_ in kq["lop"]] == [True, False, False], "chỉ ảnh gốc bị ẩn"
        assert all(l_["blend"] == b"norm" and l_["opacity"] == 255 for l_ in kq["lop"])
        assert sorted(i for i, _ in kq["lop"][0]["kenh"]) == [-1, 0, 1, 2], "RGBA có kênh -1"
        assert np.array_equal(kq["ghep"], np.asarray(ghep)), "ảnh ghép = ảnh truyền vào"

    def test_lop_chu_cat_gon_ve_hop_bao_va_dung_diem_anh(self):
        data, _ = _psd_mau()
        lop_chu = doc_psd(data)["lop"][2]
        # Hình chữ nhật 10..30 × 5..20 ⇒ rộng 21 (lẻ) được nới thành 22 (chẵn).
        assert (lop_chu["left"], lop_chu["top"], lop_chu["bottom"]) == (10, 5, 21)
        assert lop_chu["right"] - lop_chu["left"] == 22
        anh = _lop_rgba(lop_chu, (60, 41))
        assert anh.getpixel((15, 10)) == (0, 0, 255, 255)
        assert anh.getpixel((31, 10))[3] == 0, "cột nới thêm phải trong suốt"

    def test_lop_trong_hoan_toan_van_la_mot_lop(self):
        """Vùng có chữ mà vẽ ra rỗng vẫn phải thành lớp — số lớp không được lặng lẽ thiếu."""
        trong = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
        bo = io.BytesIO()
        ghi_psd(bo, (20, 20), [LopPsd("Đã xoá chữ", Image.new("RGB", (20, 20))),
                               LopPsd("Vùng 1: ", trong)], Image.new("RGB", (20, 20)))
        kq = doc_psd(bo.getvalue())
        assert kq["so_lop"] == 2
        assert (kq["lop"][1]["right"] - kq["lop"][1]["left"]) == 0

    def test_pillow_mo_duoc_psd(self):
        """Bộ đọc ĐỘC LẬP: Pillow nhận ra PSD, đọc ảnh ghép, liệt kê lớp, giải mã điểm ảnh lớp."""
        data, ghep = _psd_mau()
        with Image.open(io.BytesIO(data)) as im:
            assert im.format == "PSD" and im.size == (60, 41) and im.mode == "RGB"
            assert np.array_equal(np.asarray(im.convert("RGB")), np.asarray(ghep))
            lop = im.layers
            assert [x[0] for x in lop] == ["Anh goc", "Da xoa chu", "Vung 1: Xin chao ban"]
            assert all(x[1] == "RGBA" for x in lop)
            assert lop[2][2] == (10, 5, 32, 21)
        # Pillow coi frame 1 là ảnh ghép ban đầu nên chỉ seek được tới lớp 2, 3.
        with Image.open(io.BytesIO(data)) as im:
            im.seek(2)
            im.load()
            assert im.getpixel((5, 5)) == (255, 255, 255, 255)
        with Image.open(io.BytesIO(data)) as im:
            im.seek(3)
            im.load()
            assert im.getpixel((15, 10)) == (0, 0, 255, 255)
            assert im.getpixel((0, 0))[3] == 0

    def test_lop_sai_co_hoac_qua_lon_bi_tu_choi(self):
        with pytest.raises(ValueError):
            ghi_psd(io.BytesIO(), (10, 10), [LopPsd("x", Image.new("RGB", (9, 10)))],
                    Image.new("RGB", (10, 10)))
        with pytest.raises(PsdQuaLon):
            ghi_psd(io.BytesIO(), (30001, 1), [], Image.new("RGB", (1, 1)))


def test_ten_lop_vung_gop_dong_va_rut_gon_40_ky_tu():
    assert ten_lop_vung(3, "Cậu đi\nđâu thế?") == "Vùng 3: Cậu đi đâu thế?"
    dai = ten_lop_vung(1, "a" * 100)
    assert dai == "Vùng 1: " + "a" * 40 + "…"
    assert ten_lop_vung(2, None) == "Vùng 2: "


# ======================= đơn vị: bộ xuất dùng ĐÚNG bộ vẽ =======================


@pytest.fixture
def renderer() -> PagePreviewRenderer:
    from app.workers.tasks import build_typesetter

    _ts, resolver = build_typesetter()
    return PagePreviewRenderer(font_resolver=resolver, line_spacing_ratio=0.2)


def _vung(x, y, chu, **kw) -> RegionDraw:
    from app.core.config import get_settings

    return RegionDraw(bbox=BBox(x=x, y=y, w=120, h=60), wrapped_text=chu,
                      font_family=get_settings().default_font_family, font_size=18,
                      padding_ratio=0.1, **kw)


@pytest.mark.parametrize("k", [1.0, 1.5])
def test_psd_mot_trang_lop_khop_anh_xem_thu(tmp_path, renderer, k):
    kho = LocalObjectStorage(str(tmp_path / "kho"))
    bo = io.BytesIO()
    Image.new("RGB", (301, 211), (240, 240, 240)).save(bo, format="PNG")
    clean_rel = kho.save("p/clean.png", bo.getvalue())
    bo = io.BytesIO()
    Image.new("RGB", (301, 211), (30, 30, 30)).save(bo, format="PNG")
    goc_rel = kho.save("p/goc.png", bo.getvalue())
    vung = [
        _vung(10, 10, "Xin chào"),
        _vung(150, 120, ""),  # không có chữ ⇒ không thành lớp
        _vung(150, 20, "Đi\nthôi", text_color="#cc0000", stroke_color="#ffffff", stroke_width=2),
        _vung(20, 120, "Theo dòng", dong=[[80, 140]]),
    ]
    trang = TrangCanXuat(page_id="p", order=1, clean_image_rel=clean_rel, regions=vung,
                         he_so_ve=k, anh_goc_rel=goc_rel)
    ra = io.BytesIO()
    so_lop = ChapterExporter(kho, renderer).render_page_psd(trang, ra)
    kq = doc_psd(ra.getvalue())

    xem_thu = renderer.draw(str(kho.fetch_to(clean_rel, tmp_path / "c.png")), vung, he_so_ve=k)
    assert (kq["rong"], kq["cao"]) == xem_thu.size == (round(301 * k), round(211 * k))
    assert so_lop == kq["so_lop"] == 2 + 3
    assert [l_["ten"] for l_ in kq["lop"]] == [
        "Ảnh gốc", "Đã xoá chữ", "Vùng 1: Xin chào", "Vùng 3: Đi thôi", "Vùng 4: Theo dòng"]
    assert kq["lop"][0]["an"] and not any(l_["an"] for l_ in kq["lop"][1:])
    assert np.array_equal(kq["ghep"], np.asarray(xem_thu)), "ảnh ghép PHẢI là ảnh xem thử"
    goc = _lop_rgba(kq["lop"][0], xem_thu.size)
    assert goc.getpixel((5, 5)) == (30, 30, 30, 255), "lớp ảnh gốc là ảnh GỐC, cỡ canvas"

    # Ghép lại các lớp như Photoshop (bỏ lớp ẩn) ⇒ phải ra ảnh xem thử (sai số làm tròn alpha).
    ghep_lai = _lop_rgba(kq["lop"][1], xem_thu.size)
    for l_ in kq["lop"][2:]:
        lop = _lop_rgba(l_, xem_thu.size)
        assert lop.getchannel("A").getbbox() is not None, f"lớp {l_['ten']} trống"
        ghep_lai = Image.alpha_composite(ghep_lai, lop)
    lech = np.abs(np.asarray(ghep_lai.convert("RGB"), dtype=int) - np.asarray(xem_thu, dtype=int))
    assert lech.max() <= 2, f"ghép lớp lệch ảnh xem thử tới {lech.max()}"
    assert (np.asarray(xem_thu) != 240).any(), "ảnh xem thử phải có chữ — không thì test rỗng"


# ======================= (b) tích hợp: export thật trên DB =======================


async def test_xuat_psd_zip_moi_trang_mot_psd_dung_so_lop(client, chapter, storage_root):  # noqa: F811
    project_id, page_ids = await chapter(so_trang=2)
    ket_qua = await _xuat(client, project_id, "psd")
    assert ket_qua["status"] == "done" and ket_qua["format"] == "psd"
    assert ket_qua["page_count"] == 2
    duong_dan = Path(storage_root) / ket_qua["output_path"]
    assert duong_dan.name.endswith(".zip") and zipfile.is_zipfile(duong_dan)

    # Số vùng CÓ CHỮ của từng trang, đếm từ DB theo đúng điều kiện của bộ vẽ.
    co_chu: dict[str, int] = {}
    with sync_session() as s:
        for pid in page_ids:
            rows = s.execute(
                sa.select(TypesetResult)
                .join(TextRegion, TextRegion.id == TypesetResult.region_id)
                .where(TextRegion.page_id == uuid.UUID(pid))
            ).scalars().all()
            co_chu[pid] = sum(1 for t in rows if t.wrapped_text and t.font_size is not None)
            assert co_chu[pid] > 0, "fixture phải có vùng có chữ, không thì test vô nghĩa"
        orders = {pid: s.get(Page, uuid.UUID(pid)).order for pid in page_ids}

    # Đối chiếu ảnh ghép với bản xuất PNG của CÙNG trang: PSD phải khớp ảnh xem thử.
    with zipfile.ZipFile(duong_dan) as goi:
        assert goi.namelist() == ["001.psd", "002.psd"]
        assert goi.testzip() is None
        psd_theo_ten = {ten: goi.read(ten) for ten in goi.namelist()}
    png = await _xuat(client, project_id, "png_single")
    thu_muc_png = Path(storage_root) / png["output_path"]

    for pid in page_ids:
        ten = f"{orders[pid]:03d}.psd"
        kq = doc_psd(psd_theo_ten[ten])
        assert kq["so_lop"] == 2 + co_chu[pid]
        assert kq["lop"][0]["ten"] == "Ảnh gốc" and kq["lop"][0]["an"]
        assert kq["lop"][1]["ten"] == "Đã xoá chữ" and not kq["lop"][1]["an"]
        assert all(l_["ten"].startswith("Vùng ") for l_ in kq["lop"][2:])
        with Image.open(thu_muc_png / ten.replace(".psd", ".png")) as anh_png:
            assert (kq["rong"], kq["cao"]) == anh_png.size
            assert np.array_equal(kq["ghep"], np.asarray(anh_png.convert("RGB")))
        with Image.open(io.BytesIO(psd_theo_ten[ten])) as im:  # bộ đọc độc lập
            assert im.format == "PSD" and len(im.layers) == kq["so_lop"]


async def test_xuat_psd_van_ghi_canh_bao_tran_khung(client, chapter):  # noqa: F811
    from app.models.enums import FitStatus

    project_id, page_ids = await chapter(so_trang=1)
    with sync_session() as s:
        ts = s.execute(
            sa.select(TypesetResult)
            .join(TextRegion, TextRegion.id == TypesetResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_ids[0]))
        ).scalars().first()
        ts.fit_status = FitStatus.overflow_warning
        s.commit()
    ket_qua = await _xuat(client, project_id, "psd")
    assert ket_qua["status"] == "done"
    assert ket_qua["overflow_warning_count"] == 1
    body = (await client.get(f"/api/v1/export-jobs/{ket_qua['job_id']}")).json()
    assert body["format"] == "psd"
    assert "overflow_warning" in (body["error_log"] or "")
    r = await client.get(f"/api/v1/export-jobs/{ket_qua['job_id']}/download")
    assert r.status_code == 200 and r.content[:2] == b"PK"
