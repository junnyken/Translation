"""Phong quyền quản trị cho một tài khoản ĐÃ CÓ — thay cho email "chủ hệ thống" viết cứng trong mã.

Chạy tay:
    python -m app.scripts.phong_quan_tri ten@gmail.com

Trên host thì gọi qua biến môi trường `PHONG_QUAN_TRI_EMAIL` trong `deploy-start.sh`.

Cố ý KHÔNG tạo tài khoản: chỉ phong cho tài khoản đã tồn tại. Nếu lệnh tự tạo thì đặt biến môi
trường trước khi chủ thật đăng ký là mở đúng lỗ cũ — ai đăng ký trước bằng email đó là thành
quản trị.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.db_sync import sync_session
from app.models import NguoiDung
from app.services.tai_khoan import chuan_hoa_email


def main(argv: list[str] | None = None) -> int:
    bo = argparse.ArgumentParser(description="Phong quyền quản trị cho một tài khoản đã có.")
    bo.add_argument("email")
    tuy_chon = bo.parse_args(argv)
    email = chuan_hoa_email(tuy_chon.email)

    with sync_session() as s:
        nguoi = s.execute(select(NguoiDung).where(NguoiDung.email == email)).scalars().first()
        if nguoi is None:
            print(f"Không có tài khoản {email} — đăng ký trước rồi chạy lại.")
            return 1
        if nguoi.la_quan_tri:
            print(f"{email} đã là quản trị — không đổi gì.")
            return 0
        nguoi.la_quan_tri = True
        s.commit()
    print(f"Đã phong quản trị cho {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
