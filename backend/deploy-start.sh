#!/usr/bin/env bash
# Khởi động cho môi trường chạy thật (Vibe Host).
#
# VÌ SAO API VÀ WORKER CHẠY CHUNG MỘT CONTAINER:
# 7 endpoint của API phục vụ file mà worker ghi ra (ảnh clean của M4, ảnh xem thử của M6/M7,
# file CBZ của M8). Ở máy nhà chúng dùng chung volume `storage_data`. Trên Vibe Host mỗi
# website là một container ĐĨA RIÊNG, và nền tảng chỉ nhận thư mục con `backend`/`frontend`
# làm gốc build, không tạo được cụm nhiều container dùng chung volume — tách ra là mọi ảnh và
# file xuất đều 404.
#
# VÌ SAO UVICORN CHẠY Ở TIỀN CẢNH CÒN CELERY Ở NỀN:
# Nền tảng loại bỏ bản mới nếu container khởi động lại 3 lần. Bản đầu cho hai tiến trình "chết
# cùng nhau" ⇒ celery bị hạ là kéo sập cả website, và trang không bao giờ lên được. Nay API luôn
# sống để phục vụ, còn celery được bật lại và **đếm số lần chết** — báo ra `/healthz`, KHÔNG im lặng.
set -uo pipefail

ROLE="${ROLE:-all}"
PORT="${PORT:-8000}"
TRANG_THAI_WORKER="${WORKER_STATE_FILE:-/tmp/trang-thai-worker.json}"

lenh_worker() {
  # --pool=solo: một tiến trình duy nhất, không fork. Xử lý mỗi lần một việc nên không mất gì,
  #   mà bớt được một bản sao toàn bộ thư viện AI trong bộ nhớ.
  # --without-gossip/mingle/heartbeat: chỉ có MỘT worker, không cần dò tìm worker khác.
  celery -A app.workers.celery_app.celery_app worker \
    -l info -Q celery --pool=solo \
    --without-gossip --without-mingle --without-heartbeat
}

ghi_trang_thai() {
  printf '{"trang_thai":"%s","so_lan_chet":%s,"ma_thoat_gan_nhat":%s,"luc":"%s"}\n' \
    "$1" "${2:-0}" "${3:-null}" "$(date -u +%FT%TZ)" > "$TRANG_THAI_WORKER"
}

if [ "$ROLE" = "all" ] || [ "$ROLE" = "api" ]; then
  echo "[khoi-dong] chạy migration…"
  alembic upgrade head || { echo "[khoi-dong] MIGRATION HỎNG — dừng"; exit 1; }
fi

case "$ROLE" in
  worker)
    ghi_trang_thai running 0
    exec bash -c "$(declare -f lenh_worker); lenh_worker"
    ;;
  api)
    ghi_trang_thai disabled 0
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
    ;;
  all)
    ghi_trang_thai starting 0
    (
      SO_LAN_CHET=0
      while true; do
        lenh_worker
        MA=$?
        SO_LAN_CHET=$((SO_LAN_CHET + 1))
        # 137 = bị SIGKILL, gần như luôn là hết bộ nhớ. Nói thẳng ra thay vì để người đọc đoán.
        if [ "$MA" -eq 137 ]; then
          echo "[worker] BỊ GIẾT (SIGKILL/137) — gần như chắc chắn là container hết bộ nhớ." >&2
        fi
        echo "[worker] đã thoát (mã $MA), lần chết thứ $SO_LAN_CHET — bật lại sau 10s" >&2
        ghi_trang_thai restarting "$SO_LAN_CHET" "$MA"
        sleep 10
      done
    ) &
    echo "[khoi-dong] API trên cổng ${PORT} (worker chạy nền)…"
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
    ;;
  *) echo "ROLE không hợp lệ: '$ROLE' (chỉ all|api|worker)"; exit 2 ;;
esac
