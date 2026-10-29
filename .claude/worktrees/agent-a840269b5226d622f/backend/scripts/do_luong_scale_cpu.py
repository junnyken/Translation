"""Đo bước nhận diện khung chữ scale theo số core tới đâu.

## Vì sao đo cái này

Người dùng hỏi: 24 trang mất ~54 phút, tối ưu được không? Đo chi phí từng bước cho thấy nhận diện
(46%) + xoá chữ (38%) = 84% thời gian, đều là compute ONNX trên CPU. Cần gạt trực giác nhất là
"thêm CPU". Nhưng `get_resources` cho thấy CPU **đã ở trần gói** (`maxCpu == currentCpu == 2.6`),
nên câu hỏi thật là: **đổi sang gói/hạ tầng lớn hơn có đáng không?**

Script này trả lời bằng số: ghim tiến trình vào N core rồi đo. Nếu 8-12 core cho nhanh gấp 3 thì
đổi hạ tầng là lý lẽ mạnh; nếu chỉ 1,2× thì đổi là vô nghĩa.

## Vì sao phải dùng taskset, và confound phải loại trước

Container local KHÔNG giới hạn CPU nên đo trực tiếp sẽ luôn dùng cả 12 core và không so được gì.
`taskset` ghim vào đúng N core.

**Confound chết người:** nếu container CÓ cgroup quota thì nới `taskset` sẽ vô tác dụng, và bảng
kết quả phẳng chỉ là tạo tác của quota chứ không phải tính chất của model — mà nhìn vào bảng thì
hai thứ đó *giống nhau hoàn toàn*. Phải kiểm trước khi tin bất kỳ số nào:

    docker inspect <ct> --format '{{.HostConfig.NanoCpus}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpusetCpus}}'
    docker exec <ct> cat /sys/fs/cgroup/cpu.max      # phải là "max <period>"

## Kỷ luật

Lượt 1 gồm thời gian nạp model nên bị bỏ, chỉ so lượt ấm. Mỗi mức đo 2 lượt để thấy dao động —
FP32 trên bàn thử này có dải nhiễu ~30%, nên **mọi "cải thiện" dưới mức đó là nhiễu**. Máy chủ
dùng chung: tải của việc khác có thể làm lệch một điểm (lần chạy 09-10, mức 8 core ra chậm nhất
bảng, gần như chắc là vì lý do này).

## Cách chạy

    for c in 0-1 0-2 0-3 0-5 0-7 0-11; do
      docker compose -f deploy/docker-compose.yml run --rm -e PYTHONPATH=/app \
        -v $PWD/backend/scripts/do_luong_scale_cpu.py:/app/dc.py worker \
        taskset -c $c python /app/dc.py /app/test_fixtures/many_bubbles.png 2>&1 | grep -E "^cores="
    done

Kết quả 2026-09-10 (xem `docs/REPORT_E25.md` §2.7): 2→12 core chỉ đổi 53,0s → 44,4s = **1,19×**.
Thêm CPU không mua được tốc độ.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

WEIGHTS = "/models/comic-text-detector.onnx"
SO_LUOT = 2


def main() -> None:
    trang = sys.argv[1] if len(sys.argv) > 1 else None
    if not trang or not Path(trang).exists():
        raise SystemExit("Cần đường dẫn tới một trang truyện thật")

    from app.services.detect.ctd import CTDDetector

    so_core = len(os.sched_getaffinity(0))
    det = CTDDetector(weights_path=WEIGHTS, device="cpu")
    det.detect(trang)  # nạp model + làm ấm, KHÔNG tính giờ

    giay = []
    for _ in range(SO_LUOT):
        t0 = time.perf_counter()
        vung = det.detect(trang)
        giay.append(time.perf_counter() - t0)

    print(
        f"cores={so_core:<3} detect_ấm= {min(giay):6.2f}s / {max(giay):6.2f}s "
        f"· {len(vung)} vùng",
        flush=True,
    )


if __name__ == "__main__":
    main()
