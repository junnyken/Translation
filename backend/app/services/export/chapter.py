"""Xuất chapter đã chèn chữ ra PNG / CBZ / ZIP (M8).

Ảnh xuất ra được vẽ bằng **đúng** `PagePreviewRenderer` của M6 — không viết lại logic vẽ,
vì hai đường vẽ khác nhau là mầm mống lệch giữa ảnh xem thử và ảnh giao cho người đọc.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: CBZ chỉ là ZIP đổi đuôi — không cần thư viện ngoài, `zipfile` là builtin.
_DUOI_THEO_FORMAT = {"cbz": "cbz", "zip": "zip"}


class ExportFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class TrangCanXuat:
    """1 trang sẵn sàng xuất: ảnh clean + danh sách vùng đã canh chữ."""

    page_id: str
    order: int
    clean_image_abs: str
    regions: list  # list[RegionDraw] — kiểu của M6, không import ở đây để khỏi vòng lặp import


class ChapterExporter:
    def __init__(self, storage_root: str, renderer) -> None:
        self.storage_root = Path(storage_root)
        self.renderer = renderer

    # ---------- vẽ ----------
    def render_page_bytes(self, trang: TrangCanXuat) -> bytes:
        """Trả PNG binary **trong RAM**, không ghi file trung gian."""
        canvas = self.renderer.draw(trang.clean_image_abs, trang.regions)
        bo_dem = io.BytesIO()
        canvas.save(bo_dem, format="PNG")
        return bo_dem.getvalue()

    @staticmethod
    def ten_trang(trang: TrangCanXuat, so_trang: int) -> str:
        """`001.png`, `002.png`… — đánh số 0 ở đầu để ứng dụng đọc truyện sắp đúng thứ tự.

        Sắp theo tên là cách mọi ứng dụng đọc CBZ dùng; đánh số không đủ chữ số thì
        `10.png` sẽ đứng trước `2.png`.
        """
        do_rong = max(len(str(so_trang)), 3)
        return f"{trang.order:0{do_rong}d}.png"

    # ---------- dọn trước khi ghi ----------
    def _don_ket_qua_cu(self, thu_muc: Path) -> list[str]:
        """Xoá sạch kết quả xuất cũ. Trả danh sách thứ đã xoá (để ghi log, không đoán)."""
        da_xoa: list[str] = []
        if not thu_muc.is_dir():
            return da_xoa
        for muc in sorted(thu_muc.iterdir()):
            if muc.is_dir():
                shutil.rmtree(muc)
            else:
                muc.unlink()
            da_xoa.append(muc.name)
        return da_xoa

    # ---------- 3 định dạng ----------
    def export_png_single(self, thu_muc_dich: Path, trang_list: list[TrangCanXuat]) -> tuple[str, list[str]]:
        """Mỗi trang 1 file PNG trong `<thư mục>/png/`. Trả (đường dẫn thư mục, đã xoá gì)."""
        da_xoa = self._don_ket_qua_cu(thu_muc_dich)
        dich = thu_muc_dich / "png"
        dich.mkdir(parents=True, exist_ok=True)
        for trang in trang_list:
            (dich / self.ten_trang(trang, len(trang_list))).write_bytes(self.render_page_bytes(trang))
        return str(dich), da_xoa

    def _export_goi(
        self, thu_muc_dich: Path, trang_list: list[TrangCanXuat], ten_file: str
    ) -> tuple[str, list[str]]:
        da_xoa = self._don_ket_qua_cu(thu_muc_dich)
        thu_muc_dich.mkdir(parents=True, exist_ok=True)
        dich = thu_muc_dich / ten_file
        tam = dich.with_suffix(dich.suffix + ".tmp")
        with zipfile.ZipFile(tam, "w", compression=zipfile.ZIP_DEFLATED) as goi:
            for trang in trang_list:
                goi.writestr(self.ten_trang(trang, len(trang_list)), self.render_page_bytes(trang))
        # Đổi chỗ nguyên tử: file chỉ xuất hiện khi đã ghi xong, không bao giờ lộ gói dở dang.
        os.replace(tam, dich)
        return str(dich), da_xoa

    def export_cbz(self, thu_muc_dich: Path, trang_list: list[TrangCanXuat], ten_file: str):
        return self._export_goi(thu_muc_dich, trang_list, ten_file)

    def export_zip(self, thu_muc_dich: Path, trang_list: list[TrangCanXuat], ten_file: str):
        return self._export_goi(thu_muc_dich, trang_list, ten_file)
