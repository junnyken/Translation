#!/bin/sh
# Sinh config lúc CHẠY, không phải lúc build.
#
# Vite thay biến `import.meta.env.*` ngay lúc dựng file tĩnh, mà nền tảng hosting chỉ cho đặt
# biến môi trường lúc chạy — nên nếu chỉ dựa vào VITE_API_BASE thì giao diện sẽ không biết gọi
# API ở đâu. Ghi ra một file config nhỏ để trang đọc khi mở.
set -e
: "${API_BASE:=}"
cat > /usr/share/nginx/html/config.js <<EOF
window.__API_BASE__ = "${API_BASE}";
EOF
echo "[entrypoint] API_BASE = '${API_BASE:-(rỗng — gọi đường dẫn tương đối)}'"
exec nginx -g 'daemon off;'
