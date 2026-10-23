#!/bin/sh
# Sinh config lúc CHẠY, không phải lúc build.
#
# Vite thay biến `import.meta.env.*` ngay lúc dựng file tĩnh, mà nền tảng hosting chỉ cho đặt
# biến môi trường lúc chạy — nên nếu chỉ dựa vào VITE_API_BASE thì giao diện sẽ không biết gọi
# API ở đâu. Ghi ra một file config nhỏ để trang đọc khi mở.
#
# Script này nằm trong /docker-entrypoint.d/ nên entrypoint chuẩn của image nginx tự chạy nó
# rồi mới khởi động nginx — KHÔNG tự gọi `exec nginx` ở đây.
set -e
: "${API_BASE:=}"
printf 'window.__API_BASE__ = "%s";\n' "$API_BASE" > /usr/share/nginx/html/config.js
echo "[cau-hinh] API_BASE = '${API_BASE:-(rỗng — gọi đường dẫn tương đối)}'"
