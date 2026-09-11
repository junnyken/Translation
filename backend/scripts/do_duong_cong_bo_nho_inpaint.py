"""Đo ĐƯỜNG CONG bộ nhớ của bước xoá chữ theo diện tích ô cắt — một cỡ mỗi lần chạy.

## Vì sao cần

E23 hiệu chỉnh hệ số `inpaint_gb_per_mpx` từ **một** phép đo (n=1, ô 2,57 Mpx -> đỉnh 3367,8 MB
=> 1,28 GB/Mpx). Một điểm thì không phân biệt được hai mô hình rất khác nhau:

    bộ nhớ = k * Mpx            (tỉ lệ thuần)
    bộ nhớ = nền + k * Mpx      (có chi phí nền: bản thân model ONNX đã tốn ~1 GB)

Hai mô hình trùng nhau tại điểm đã đo và **lệch nhau ở mọi chỗ khác**. Mô hình tỉ lệ thuần khi hiệu
chỉnh ở đầu lớn sẽ đánh giá THẤP chi phí của ô nhỏ, và ngược lại. Phép canh ngân sách chỉ đáng tin
khi biết mình đang ở mô hình nào.

## Cách đo

`VmHWM` (high water mark trong `/proc/self/status`) — **đỉnh** thật của tiến trình. KHÔNG dùng RSS
đọc sau khi chạy xong: E23 đo được RSS-sau là 1628 MB trong khi đỉnh thật là 3367 MB (gấp 2,07
lần), tin RSS-sau thì kết luận ngược hoàn toàn.

**Một cỡ mỗi tiến trình.** Đo nhiều cỡ trong cùng tiến trình thì `VmHWM` là đỉnh CỘNG DỒN của mọi
lượt trước, không tách được từng cỡ. Và nếu một cỡ lớn bị hệ điều hành giết thì cả loạt mất trắng.

## Chạy

    for m in 0.8 1.4 2.0 2.6 3.2; do
      docker compose -f deploy/docker-compose.yml exec -T -e PYTHONPATH=/app worker \\
        python /app/scripts/do_duong_cong_bo_nho_inpaint.py <ảnh> $m
    done
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def vmhwm_mb() -> float:
    with open("/proc/self/status") as f:
        for dong in f:
            if dong.startswith("VmHWM:"):
                return int(dong.split()[1]) / 1024
    return -1.0


def main() -> None:
    goc, muc_tieu_mpx = sys.argv[1], float(sys.argv[2])

    from PIL import Image

    from app.core.config import get_settings
    from app.services.inpaint.lama import LamaInpainter, gom_cum
    from app.services.interfaces import BBox

    s = get_settings()

    # Giữ tỉ lệ 1200:2144 của trang thật, chỉ đổi diện tích.
    ti_le = 2144 / 1200
    rong = int(round(math.sqrt(muc_tieu_mpx * 1e6 / ti_le)))
    cao = int(round(rong * ti_le))
    tam = "/tmp/trang_do.png"
    with Image.open(goc) as im:
        im.convert("RGB").resize((rong, cao)).save(tam)
    mpx = rong * cao / 1e6

    # Vùng chữ trải khắp trang -> gộp thành MỘT cụm phủ cả trang, đúng cảnh xấu nhất của E23.
    n = 11
    vung = [
        BBox(x=rong * 0.08, y=cao * (0.02 + i * 0.088), w=rong * 0.84, h=cao * 0.07)
        for i in range(n)
    ]
    cum = gom_cum(vung, rong, cao, s.inpaint_tile_margin)
    o_lon = max((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in cum) / 1e6

    det = LamaInpainter(
        weights_path=s.inpaint_weights_path,
        device="cpu",
        whole_page_max_mpx=s.inpaint_whole_page_max_mpx,
        tile_margin=s.inpaint_tile_margin,
        mem_budget_gb=0,  # TẮT phép canh: đang đo nhu cầu THẬT, không phải kiểm phép canh
    )

    truoc = vmhwm_mb()
    t0 = time.perf_counter()
    det.inpaint(tam, vung)
    giay = time.perf_counter() - t0
    dinh = vmhwm_mb()

    print(
        f"KQ|{mpx:.2f}|{o_lon:.2f}|{len(cum)}|{truoc:.1f}|{dinh:.1f}|{giay:.1f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
