"""Điểm chạy cho việc đối chiếu bản ghi ↔ hiện vật (P3f).

Chạy tay:
    python -m app.scripts.doi_chieu_hien_vat            # chỉ đếm, KHÔNG ghi
    python -m app.scripts.doi_chieu_hien_vat --ap-dung  # sửa thật

Trên host thì gọi qua biến môi trường `RECONCILE_LEGACY` trong `deploy-start.sh`, vì nền tảng
không cho chạy lệnh trong container.
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.core.db_sync import sync_session
from app.services.reconcile import doi_chieu_hien_vat
from app.services.storage import get_storage


def main(argv: list[str] | None = None) -> int:
    bo = argparse.ArgumentParser(description="Đối chiếu bản ghi với hiện vật thật.")
    bo.add_argument(
        "--ap-dung",
        action="store_true",
        help="Sửa thật. Không có cờ này thì chỉ đếm và in ra, không ghi một chữ nào.",
    )
    tuy_chon = bo.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with sync_session() as s:
        kq = doi_chieu_hien_vat(s, get_storage(), ap_dung=tuy_chon.ap_dung)

    print(
        f"\n{'ĐÃ SỬA' if kq.da_ghi else 'CHỈ ĐẾM (chưa ghi gì)'}: "
        f"{kq.trang_mat_anh_clean} trang mất ảnh clean · "
        f"{kq.trang_mat_preview} trang mất ảnh xem thử · "
        f"{kq.job_xuat_mat_file} lần xuất mất file"
    )
    if not kq.da_ghi and kq.tong:
        print("Chạy lại với --ap-dung để sửa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
