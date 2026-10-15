"""Xuất chapter đã chèn chữ ra PNG / CBZ / ZIP (M8).

Ảnh xuất ra được vẽ bằng **đúng** `PagePreviewRenderer` của M6 — không viết lại logic vẽ,
vì hai đường vẽ khác nhau là mầm mống lệch giữa ảnh xem thử và ảnh giao cho người đọc.
"""
from __future__ import annotations

import io
import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.services.storage import IObjectStorage, workspace

logger = logging.getLogger(__name__)

#: CBZ chỉ là ZIP đổi đuôi — không cần thư viện ngoài, `zipfile` là builtin.
_DUOI_THEO_FORMAT = {"cbz": "cbz", "zip": "zip"}


class ExportFailed(RuntimeError):
    pass


#: E78 — độ dài tối đa phần bản dịch trong tên lớp PSD.
DAI_TEN_LOP = 40


def ten_lop_vung(so: int, ban_dich: str | None) -> str:
    """`Vùng 3: Cậu đi đâu thế?` — bản dịch gộp về một dòng, rút gọn 40 ký tự (thêm `…`)."""
    gon = " ".join((ban_dich or "").split())
    if len(gon) > DAI_TEN_LOP:
        gon = gon[:DAI_TEN_LOP].rstrip() + "…"
    return f"Vùng {so}: {gon}"


@dataclass(frozen=True)
class TrangCanXuat:
    """1 trang sẵn sàng xuất: ảnh clean + danh sách vùng đã canh chữ."""

    page_id: str
    order: int
    clean_image_rel: str
    regions: list  # list[RegionDraw] — kiểu của M6, không import ở đây để khỏi vòng lặp import
    #: E33 — thư mục chapter khi GỘP nhiều chapter (`01_chuong_mot`). Rỗng ⇒ tên phẳng như trước.
    #:
    #: Bắt buộc phải có: `ten_trang` đặt tên theo `order`, mà mỗi chapter đều có `order=1`. Gộp mà
    #: không có tiền tố thì trang 1 của chapter sau **ghi đè** trang 1 của chapter trước, và
    #: `zipfile` KHÔNG báo lỗi — mất trang mà không ai biết.
    tien_to: str = ""
    #: E65 — hệ số phóng ảnh RA của CHÍNH trang này. Không phải hằng số của chapter: mỗi
    #: trang có bong bóng chật hẹp khác nhau nên mỗi trang đo ra một hệ số riêng.
    he_so_ve: float = 1.0
    #: E78 — ảnh GỐC (còn chữ nguồn) của trang, cho lớp ẩn "Ảnh gốc" trong PSD. None ⇒ dùng
    #: `clean_image_rel` (trang không có chữ: ảnh gốc chính là ảnh hoàn thiện).
    anh_goc_rel: str | None = None


class ChapterExporter:
    """Ghi kết quả xuất vào một thư mục CỤC BỘ do bên gọi cấp (thường là `workspace()`).

    P3c: trước đây bộ xuất nhận gốc kho rồi ghi thẳng vào lòng kho qua đường dẫn tuyệt đối. Nay
    nó không biết kho nằm ở đâu — chỉ vẽ ra thư mục được đưa cho, và bên gọi `save_file()` kết
    quả vào kho. Dọn bản xuất cũ cũng chuyển về kho (`delete_prefix`).
    """

    def __init__(self, storage: IObjectStorage, renderer) -> None:
        self.storage = storage
        self.renderer = renderer

    # ---------- vẽ ----------
    def render_page_bytes(self, trang: TrangCanXuat) -> bytes:
        """Trả PNG binary **trong RAM**, không ghi file trung gian.

        Ảnh clean được vật chất hoá ra thư mục tạm vì bộ vẽ của M6 nhận đường dẫn thật.
        """
        with workspace() as ws:
            clean = self.storage.fetch_to(
                trang.clean_image_rel, ws / PurePosixPath(trang.clean_image_rel).name
            )
            canvas = self.renderer.draw(str(clean), trang.regions, he_so_ve=trang.he_so_ve)
        bo_dem = io.BytesIO()
        canvas.save(bo_dem, format="PNG")
        return bo_dem.getvalue()

    def render_page_psd(self, trang: TrangCanXuat, fp) -> int:
        """E78 — ghi PSD nhiều lớp của một trang vào `fp`. Trả số lớp đã ghi.

        Lớp (dưới → trên): "Ảnh gốc" (ẨN), "Đã xoá chữ", rồi mỗi vùng có chữ một lớp RGBA trong
        suốt. Cả ba loại cùng cỡ canvas ĐÃ PHÓNG `he_so_ve` (LANCZOS, cùng hàm `mo_nen` của bộ
        vẽ). Chữ từng vùng vẽ bằng `draw_lop_vung` — chung `_ve_vung` với `draw()` — và ảnh ghép
        cuối tệp chính là `draw()`, tức ảnh xem thử.
        """
        from app.services.export.psd import LopPsd, ghi_psd

        k = float(trang.he_so_ve or 1.0)
        with workspace() as ws:
            clean = self.storage.fetch_to(
                trang.clean_image_rel, ws / ("clean_" + PurePosixPath(trang.clean_image_rel).name)
            )
            goc_rel = trang.anh_goc_rel or trang.clean_image_rel
            goc = (
                clean if goc_rel == trang.clean_image_rel
                else self.storage.fetch_to(goc_rel, ws / ("goc_" + PurePosixPath(goc_rel).name))
            )
            ghep = self.renderer.draw(str(clean), trang.regions, he_so_ve=k)
            kich_thuoc = ghep.size
            nen_sach = self.renderer.mo_nen(str(clean), k, kich_thuoc)
            nen_goc = self.renderer.mo_nen(str(goc), k, kich_thuoc)
            dem = {"so": 2}

            def cac_lop():
                yield LopPsd("Ảnh gốc", nen_goc, an=True)
                yield LopPsd("Đã xoá chữ", nen_sach)
                for so, region, lop in self.renderer.draw_lop_vung(
                    kich_thuoc, trang.regions, he_so_ve=k
                ):
                    dem["so"] += 1
                    yield LopPsd(ten_lop_vung(so, region.wrapped_text), lop)

            ghi_psd(fp, kich_thuoc, cac_lop(), ghep)
        return dem["so"]

    def export_psd(self, thu_muc_dich: Path, trang_list: list[TrangCanXuat], ten_file: str) -> str:
        """E78 — một ZIP chứa `<thứ tự>.psd` mỗi trang. Ghi tệp tạm rồi đổi chỗ nguyên tử."""
        thu_muc_dich.mkdir(parents=True, exist_ok=True)
        dich = thu_muc_dich / ten_file
        tam = dich.with_suffix(dich.suffix + ".tmp")
        with zipfile.ZipFile(tam, "w", compression=zipfile.ZIP_DEFLATED) as goi:
            for trang in trang_list:
                ten = self.ten_trang(trang, len(trang_list), duoi="psd")
                # Ghi THẲNG vào mục ZIP — PSD RAW của trang phóng to có thể vài trăm MB.
                with goi.open(ten, "w", force_zip64=True) as muc:
                    self.render_page_psd(trang, muc)
        os.replace(tam, dich)
        return str(dich)

    @staticmethod
    def ten_trang(trang: TrangCanXuat, so_trang: int, duoi: str = "png") -> str:
        """`001.png`, `002.png`… — đánh số 0 ở đầu để ứng dụng đọc truyện sắp đúng thứ tự.

        Sắp theo tên là cách mọi ứng dụng đọc CBZ dùng; đánh số không đủ chữ số thì
        `10.png` sẽ đứng trước `2.png`.
        """
        do_rong = max(len(str(so_trang)), 3)
        ten = f"{trang.order:0{do_rong}d}.{duoi}"
        # E33 — có tiền tố thì trang nằm trong thư mục chapter. Ứng dụng đọc CBZ sắp theo đường
        # dẫn đầy đủ, nên thứ tự chapter cũng nằm trong tên.
        return f"{trang.tien_to}/{ten}" if trang.tien_to else ten

    # ---------- 3 định dạng ----------
    def export_png_single(self, thu_muc_dich: Path, trang_list: list[TrangCanXuat]) -> str:
        """Mỗi trang 1 file PNG trong `<thư mục>/png/`. Trả đường dẫn thư mục vừa ghi."""
        dich = thu_muc_dich / "png"
        dich.mkdir(parents=True, exist_ok=True)
        for trang in trang_list:
            ra = dich / self.ten_trang(trang, len(trang_list))
            # E33 — tên có thể mang thư mục chapter (`01_chuong_mot/001.png`), nên phải tạo
            # thư mục cha. Thiếu dòng này thì xuất PNG khi gộp sẽ nổ `FileNotFoundError`.
            ra.parent.mkdir(parents=True, exist_ok=True)
            ra.write_bytes(self.render_page_bytes(trang))
        return str(dich)

    def _export_goi(
        self, thu_muc_dich: Path, trang_list: list[TrangCanXuat], ten_file: str
    ) -> str:
        thu_muc_dich.mkdir(parents=True, exist_ok=True)
        dich = thu_muc_dich / ten_file
        tam = dich.with_suffix(dich.suffix + ".tmp")
        with zipfile.ZipFile(tam, "w", compression=zipfile.ZIP_DEFLATED) as goi:
            for trang in trang_list:
                goi.writestr(self.ten_trang(trang, len(trang_list)), self.render_page_bytes(trang))
        # Đổi chỗ nguyên tử: file chỉ xuất hiện khi đã ghi xong, không bao giờ lộ gói dở dang.
        os.replace(tam, dich)
        return str(dich)

    def export_cbz(self, thu_muc_dich: Path, trang_list: list[TrangCanXuat], ten_file: str):
        return self._export_goi(thu_muc_dich, trang_list, ten_file)

    def export_zip(self, thu_muc_dich: Path, trang_list: list[TrangCanXuat], ten_file: str):
        return self._export_goi(thu_muc_dich, trang_list, ten_file)
