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
# P3m — worker tự ghi RSS của nó ra đây; /healthz đọc lên. Tệp RIÊNG với tệp trạng thái
# ở trên: tệp kia do shell này ghi, hai người ghi chung một tệp là mất dữ liệu của cả hai.
export WORKER_RSS_FILE="${WORKER_RSS_FILE:-/tmp/rss-worker.json}"

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

  # P3f — đối chiếu bản ghi với hiện vật thật. Nền tảng không cho chạy lệnh trong container,
  # nên đây là đường duy nhất để gọi nó trên bản chạy thật: bật bằng biến môi trường.
  #   off (mặc định) · report = chỉ đếm và ghi log · apply = sửa thật
  # KHÁC migration ở một điểm quan trọng: lỗi ở đây KHÔNG được chặn khởi động. Migration hỏng
  # thì schema sai, chạy tiếp là hỏng dữ liệu; còn đối chiếu hỏng thì chỉ là chưa dọn được —
  # không đáng để hạ cả website.
  case "${RECONCILE_LEGACY:-off}" in
    report)
      echo "[khoi-dong] đối chiếu hiện vật — CHỈ ĐẾM, không ghi gì…"
      python -m app.scripts.doi_chieu_hien_vat \
        || echo "[khoi-dong] đối chiếu lỗi — bỏ qua, KHÔNG chặn khởi động"
      ;;
    apply)
      echo "[khoi-dong] đối chiếu hiện vật — SỬA THẬT…"
      python -m app.scripts.doi_chieu_hien_vat --ap-dung \
        || echo "[khoi-dong] đối chiếu lỗi — bỏ qua, KHÔNG chặn khởi động"
      ;;
    off) : ;;
    *) echo "[khoi-dong] RECONCILE_LEGACY='${RECONCILE_LEGACY}' không hợp lệ (off|report|apply) — bỏ qua" ;;
  esac
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
