#!/usr/bin/env bash
# Khởi động cho môi trường chạy thật (Vibe Host).
#
# VÌ SAO API VÀ WORKER CHẠY CHUNG MỘT CONTAINER:
# 7 endpoint của API phục vụ file mà worker ghi ra (ảnh clean của M4, ảnh xem thử của M6/M7,
# file CBZ của M8). Ở máy nhà chúng dùng chung volume `storage_data`. Trên Vibe Host mỗi
# website là một container với đĩa RIÊNG, và nền tảng chưa cho tạo cụm nhiều container dùng
# chung volume — tách ra là mọi ảnh và file xuất đều 404.
#
# Đánh đổi đã biết: image này nặng (~4,5GB, có cả stack AI) nên tiến trình API cũng nằm trong
# đó. Ranh giới "API không NẠP model" vẫn giữ nguyên — các module AI đều import trễ, guardrail
# `test_api_khong_nap_engine_render_cua_m6` vẫn canh điều đó.
#
# ROLE=all (mặc định) chạy cả hai; ROLE=api / ROLE=worker để tách khi nào có volume dùng chung.
set -euo pipefail

ROLE="${ROLE:-all}"
PORT="${PORT:-8000}"

if [ "$ROLE" = "all" ] || [ "$ROLE" = "api" ]; then
  echo "[khoi-dong] chạy migration…"
  alembic upgrade head
fi

chay_worker() {
  echo "[khoi-dong] worker Celery…"
  exec celery -A app.workers.celery_app.celery_app worker -l info -Q celery --concurrency=1
}
chay_api() {
  echo "[khoi-dong] API trên cổng ${PORT}…"
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
}

case "$ROLE" in
  worker) chay_worker ;;
  api)    chay_api ;;
  all)
    celery -A app.workers.celery_app.celery_app worker -l info -Q celery --concurrency=1 &
    PID_WORKER=$!
    uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" &
    PID_API=$!
    # Tiến trình nào chết trước cũng phải kéo cả container xuống để nền tảng khởi động lại.
    # Không có dòng này thì worker chết âm thầm mà API vẫn 200 — pipeline đứng im không ai biết,
    # đúng loại sự cố đã gặp khi worker bị OOM (xem docs/REPORT_M8.md §7).
    wait -n "$PID_WORKER" "$PID_API"
    MA=$?
    echo "[khoi-dong] một tiến trình đã thoát (mã $MA) — dừng cả container để được khởi động lại"
    kill "$PID_WORKER" "$PID_API" 2>/dev/null || true
    exit 1
    ;;
  *) echo "ROLE không hợp lệ: '$ROLE' (chỉ all|api|worker)"; exit 2 ;;
esac
