"""E38 — trang KHÔNG CÓ CHỮ phải vào file xuất, không bị loại.

## Lỗi thật, phát hiện ở E35 trên production (2026-09-14)

Trang `E39P02` của `ep39_The-Tavern` **toàn tranh, không một bong bóng thoại**. Pipeline xử lý:

    detect chạy xong, 0 vùng  ->  Page.status = detected
    ocr                       ->  no_region, job FAILED
    giao diện                 ->  trang hiện "Hỏng" (đỏ)
    cổng xuất                 ->  "3 trang sẽ bị BỎ QUA vì chưa chèn chữ xong"

⇒ **truyện xuất ra THIẾU TRANG.** Mất dữ liệu ở đầu ra, không phải chuyện thẩm mỹ.

## Điều làm bản sửa này an toàn

    detect NỔ        -> PageStatus.detection_failed
    detect CHẠY XONG -> PageStatus.detected, kể cả 0 vùng

Nên `detected` + 0 vùng nghĩa là **máy đã xem và xác nhận không có chữ**. Test dưới đây canh đúng
sự phân biệt đó: bỏ sót nó là xuất ra một trang mà chữ đã bị đọc hỏng.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.db_sync import sync_session
from app.models import Page, Project, TextRegion
from app.models.enums import IntendedUse, PageStatus, SourceLang, TargetLang
from app.workers.tasks import _thu_thap_trang, thong_ke_xuat, trang_khong_co_chu


def _du_an(s) -> uuid.UUID:
    pr = Project(
        name=f"E38 {uuid.uuid4().hex[:8]}", source_lang=SourceLang.en,
        target_lang=TargetLang.vi, intended_use=IntendedUse.study,
    )
    s.add(pr)
    s.flush()
    return pr.id


def _trang(s, pid, order, tt, co_vung=False, clean=None) -> Page:
    pg = Page(
        project_id=pid, image_path=f"goc/{order}.jpg", order=order, status=tt,
        clean_image_path=clean,
    )
    s.add(pg)
    s.flush()
    if co_vung:
        s.add(TextRegion(
            page_id=pg.id, bbox_x=0, bbox_y=0, bbox_w=50, bbox_h=20, confidence=0.9,
        ))
        s.flush()
    return pg


class TestNhanBietTrangKhongCoChu:
    def test_detected_va_0_vung_LA_trang_khong_co_chu(self):
        with sync_session() as s:
            pid = _du_an(s)
            pg = _trang(s, pid, 1, PageStatus.detected)
            s.commit()
            assert trang_khong_co_chu(s, pg) is True

    def test_detected_nhung_CO_vung_thi_KHONG(self):
        """Trang có chữ mà kẹt ở `detected` là trang chưa chạy xong, KHÔNG được xuất."""
        with sync_session() as s:
            pid = _du_an(s)
            pg = _trang(s, pid, 1, PageStatus.detected, co_vung=True)
            s.commit()
            assert trang_khong_co_chu(s, pg) is False

    def test_detection_failed_thi_KHONG_du_cung_0_vung(self):
        """Đây là phân biệt then chốt: detect HỎNG khác detect chạy xong mà không thấy chữ.

        Bỏ sót chỗ này là xuất ra một trang mà chữ đã bị đọc hỏng, và người dùng không biết.
        """
        with sync_session() as s:
            pid = _du_an(s)
            pg = _trang(s, pid, 1, PageStatus.detection_failed)
            s.commit()
            assert trang_khong_co_chu(s, pg) is False

    @pytest.mark.parametrize("tt", [
        PageStatus.queued, PageStatus.detecting, PageStatus.ocr_done,
        PageStatus.inpainted, PageStatus.translated,
    ])
    def test_cac_trang_thai_DANG_CHAY_thi_KHONG(self, tt):
        with sync_session() as s:
            pid = _du_an(s)
            pg = _trang(s, pid, 1, tt)
            s.commit()
            assert trang_khong_co_chu(s, pg) is False, f"{tt.value} không phải 'đã xem, không chữ'"


class TestVaoFileXuat:
    def test_trang_khong_co_chu_CO_trong_danh_sach_xuat(self):
        with sync_session() as s:
            pid = _du_an(s)
            _trang(s, pid, 1, PageStatus.typeset_done, co_vung=True, clean="clean/1.png")
            _trang(s, pid, 2, PageStatus.detected)          # không chữ
            s.commit()
            trang_list, bo_qua = _thu_thap_trang(s, pid)
        assert [t.order for t in trang_list] == [1, 2], f"thiếu trang; bỏ qua={bo_qua}"

    def test_dung_anh_GOC_vi_khong_co_anh_clean(self):
        """Không có chữ ⇒ bước xoá chữ chưa từng chạy ⇒ không có ảnh clean. Ảnh gốc là kết quả."""
        with sync_session() as s:
            pid = _du_an(s)
            _trang(s, pid, 1, PageStatus.detected)
            s.commit()
            trang_list, _ = _thu_thap_trang(s, pid)
        assert trang_list[0].clean_image_rel == "goc/1.jpg"
        assert trang_list[0].regions == [], "không có chữ thì không có gì để vẽ"

    def test_GIU_dung_thu_tu_trang(self):
        """Trang không chữ nằm giữa thì không được nhảy xuống cuối file."""
        with sync_session() as s:
            pid = _du_an(s)
            _trang(s, pid, 1, PageStatus.typeset_done, co_vung=True, clean="clean/1.png")
            _trang(s, pid, 2, PageStatus.detected)
            _trang(s, pid, 3, PageStatus.typeset_done, co_vung=True, clean="clean/3.png")
            s.commit()
            trang_list, _ = _thu_thap_trang(s, pid)
        assert [t.order for t in trang_list] == [1, 2, 3]

    def test_detection_failed_VAN_bi_bo_qua(self):
        with sync_session() as s:
            pid = _du_an(s)
            _trang(s, pid, 1, PageStatus.typeset_done, co_vung=True, clean="clean/1.png")
            _trang(s, pid, 2, PageStatus.detection_failed)
            s.commit()
            trang_list, bo_qua = _thu_thap_trang(s, pid)
        assert [t.order for t in trang_list] == [1]
        assert any("trang 2" in x for x in bo_qua)


class TestSoXemTruocKhopFileXuat:
    def test_thong_ke_dem_CA_trang_khong_co_chu(self):
        """Số xem trước nói một chuyện mà file xuất chứa chuyện khác là lỗi tệ hơn cả thiếu trang."""
        with sync_session() as s:
            pid = _du_an(s)
            _trang(s, pid, 1, PageStatus.typeset_done, co_vung=True, clean="clean/1.png")
            _trang(s, pid, 2, PageStatus.detected)
            _trang(s, pid, 3, PageStatus.detection_failed)
            s.commit()
            tk = thong_ke_xuat(s, pid)
            trang_list, _ = _thu_thap_trang(s, pid)
        assert tk["page_count"] == 2, tk
        assert tk["total_page_count"] == 3
        assert tk["skipped_page_count"] == 1
        assert tk["page_count"] == len(trang_list), "số xem trước LỆCH với file xuất thật"
