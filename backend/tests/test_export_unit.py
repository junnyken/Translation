"""Unit — đặt tên file xuất + đóng gói CBZ/ZIP (M8). Không DB, không Celery."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from app.services.export.chapter import ChapterExporter, TrangCanXuat
from app.services.storage import LocalObjectStorage
from app.services.export.naming import slugify, ten_file_export
from app.services.export.paths import export_relative_dir


class _RendererGia:
    """Vẽ ảnh thật (Pillow) nhưng không cần font/bbox — đủ để kiểm phần đóng gói."""

    def __init__(self):
        self.so_lan_ve = 0

    def draw(self, clean_image_path, regions):
        self.so_lan_ve += 1
        with Image.open(clean_image_path) as im:
            return im.convert("RGB").copy()


@pytest.fixture
def kho(tmp_path) -> LocalObjectStorage:
    """Kho thật, gốc riêng cho từng test — bộ xuất P3c nhận kho chứ không nhận thư mục."""
    return LocalObjectStorage(str(tmp_path / "kho"))


@pytest.fixture
def anh_clean(kho) -> str:
    """Trả PATH TƯƠNG ĐỐI trong kho (P3c), không còn là đường dẫn tuyệt đối."""
    bo = io.BytesIO()
    Image.new("RGB", (120, 160), "white").save(bo, format="PNG")
    return kho.save("clean/clean.png", bo.getvalue())


def _trang(anh_clean: str, order: int) -> TrangCanXuat:
    return TrangCanXuat(page_id=f"p{order}", order=order, clean_image_rel=anh_clean, regions=[])


class TestDatTen:
    @pytest.mark.parametrize(
        "vao,ra",
        [
            ("Truyện Hay #1", "truyen_hay_1"),
            ("Đường/Xá: tập 2", "duong_xa_tap_2"),
            ("  nhiều   khoảng   trắng  ", "nhieu_khoang_trang"),
            ("ĐẦY ĐỦ DẤU ăâêôơư", "day_du_dau_aaeoou"),
        ],
    )
    def test_bo_dau_va_ky_tu_la(self, vao, ra):
        assert slugify(vao) == ra

    def test_ten_rong_van_ra_ten_dung_duoc(self):
        assert slugify("") == "chapter"
        assert slugify("###") == "chapter"

    def test_khong_con_ky_tu_gay_loi_he_tep(self):
        xau = slugify('a/b\\c:d*e?f"g<h>i|j')
        for ky_tu in '/\\:*?"<>|':
            assert ky_tu not in xau

    def test_ten_file_co_duoi_dung(self):
        assert ten_file_export("Truyện Hay", "cbz") == "truyen_hay_chapter.cbz"
        assert ten_file_export("Truyện Hay", "zip") == "truyen_hay_chapter.zip"

    def test_khong_lap_chu_chapter(self):
        assert ten_file_export("MTE Live Test Chapter", "cbz") == "mte_live_test_chapter.cbz"

    def test_ten_qua_dai_bi_cat(self):
        assert len(slugify("a" * 500)) <= 80


class TestDanhSoTrang:
    def test_danh_so_0_o_dau_de_sap_dung_thu_tu(self, anh_clean):
        """`10.png` phải đứng SAU `2.png` — thiếu số 0 đầu là ứng dụng đọc truyện sắp sai."""
        ten = [ChapterExporter.ten_trang(_trang(anh_clean, i), 12) for i in (1, 2, 10, 12)]
        assert ten == ["001.png", "002.png", "010.png", "012.png"]
        assert ten == sorted(ten), "sắp theo tên phải ra đúng thứ tự trang"

    def test_nhieu_hon_999_trang_van_sap_dung(self, anh_clean):
        ten = [ChapterExporter.ten_trang(_trang(anh_clean, i), 1200) for i in (1, 999, 1200)]
        assert ten == sorted(ten)


class TestDongGoi:
    @pytest.fixture
    def exporter(self, kho):
        return ChapterExporter(storage=kho, renderer=_RendererGia())

    def test_cbz_chua_dung_so_trang_dung_thu_tu(self, exporter, tmp_path, anh_clean):
        trang = [_trang(anh_clean, i) for i in (1, 2, 3)]
        duong_dan = exporter.export_cbz(tmp_path / "out", trang, "test_chapter.cbz")
        assert duong_dan.endswith("test_chapter.cbz")
        with zipfile.ZipFile(duong_dan) as goi:
            assert goi.namelist() == ["001.png", "002.png", "003.png"]
            assert goi.testzip() is None, "gói bị hỏng"

    def test_moi_anh_trong_goi_mo_duoc(self, exporter, tmp_path, anh_clean):
        import io

        duong_dan = exporter.export_cbz(tmp_path / "out", [_trang(anh_clean, 1)], "c.cbz")
        with zipfile.ZipFile(duong_dan) as goi:
            with Image.open(io.BytesIO(goi.read("001.png"))) as im:
                assert im.size == (120, 160)
                assert im.format == "PNG"

    def test_zip_giu_duoi_zip(self, exporter, tmp_path, anh_clean):
        duong_dan = exporter.export_zip(tmp_path / "out", [_trang(anh_clean, 1)], "c.zip")
        assert duong_dan.endswith(".zip") and zipfile.is_zipfile(duong_dan)

    def test_png_single_ra_dung_so_file(self, exporter, tmp_path, anh_clean):
        trang = [_trang(anh_clean, i) for i in (1, 2, 3)]
        thu_muc = exporter.export_png_single(tmp_path / "out", trang)
        files = sorted(p.name for p in Path(thu_muc).iterdir())
        assert files == ["001.png", "002.png", "003.png"]
        for f in Path(thu_muc).iterdir():
            with Image.open(f) as im:
                assert im.size == (120, 160)

    # P3c: việc dọn bản xuất cũ đã CHUYỂN từ bộ xuất sang kho (`delete_prefix`), vì kho mới là
    # thứ biết mình đang giữ những gì. Hai test dưới giữ nguyên bảo đảm đó, chỉ đổi chỗ kiểm.
    def test_kho_don_sach_ban_xuat_cu(self, kho):
        kho.save("exports/p1/cu.cbz", b"x")
        kho.save("exports/p1/png/001.png", b"y")
        da_xoa = kho.delete_prefix("exports/p1")
        assert da_xoa == ["exports/p1/cu.cbz", "exports/p1/png/001.png"]
        assert kho.list_prefix("exports/p1") == [], "còn sót bản xuất cũ"

    def test_don_ban_cu_khong_dung_toi_project_khac(self, kho):
        kho.save("exports/p1/cu.cbz", b"x")
        kho.save("exports/p2/giu.cbz", b"z")
        kho.delete_prefix("exports/p1")
        assert kho.list_prefix("exports/p2") == ["exports/p2/giu.cbz"]

    def test_khong_de_lai_file_tam(self, exporter, tmp_path, anh_clean):
        dich = tmp_path / "out"
        exporter.export_cbz(dich, [_trang(anh_clean, 1)], "c.cbz")
        assert not any(p.name.endswith(".tmp") for p in dich.iterdir())

    def test_render_tra_ve_png_binary(self, exporter, anh_clean):
        du_lieu = exporter.render_page_bytes(_trang(anh_clean, 1))
        assert du_lieu.startswith(b"\x89PNG\r\n\x1a\n"), "không phải PNG thật"

    def test_moi_trang_chi_ve_dung_mot_lan(self, tmp_path, kho, anh_clean):
        ve = _RendererGia()
        ChapterExporter(kho, ve).export_cbz(
            tmp_path / "out", [_trang(anh_clean, i) for i in (1, 2, 3)], "c.cbz"
        )
        assert ve.so_lan_ve == 3


def test_duong_dan_export_on_dinh_theo_project():
    import uuid

    pid = uuid.uuid4()
    assert export_relative_dir(pid) == f"exports/{pid}"
