"""Đo ảnh hưởng của `intra_op_num_threads` lên bước nhận diện khung chữ.

## Vì sao đo cái này

Log production (2026-09-09) cho thấy bước detect mất **50,6s** cho một trang 1200x1700 —
chiếm ~55% tổng thời gian pipeline một trang. `ctd.py` mặc định `intra_op_threads=0`, tức KHÔNG
đặt `intra_op_num_threads`, để ONNX Runtime tự quyết. Trong container, ORT thường đếm số core của
MÁY CHỦ chứ không theo quota cgroup: máy này có **192 core** trong khi container production chỉ có
quota **2.6 CPU**. Nếu ORT sinh ~192 luồng cho 2.6 CPU thực thì phần lớn thời gian là tranh chấp
luồng, không phải tính toán.

## Vì sao phải dùng taskset

Container local KHÔNG giới hạn CPU (`NanoCpus=0`) nên nếu đo trực tiếp, ORT có 192 core thật và
sẽ nhanh — KHÔNG tái hiện được production. `taskset` ghim tiến trình vào đúng 3 core để mô phỏng
quota 2.6 CPU. Đây là điểm dễ tự lừa nhất của phép đo này.

## Kỷ luật

Ba cấu hình CHỐT TRƯỚC khi chạy, không thêm/bớt sau khi thấy số. Mỗi cấu hình chạy 2 lượt trên
CÙNG một trang thật để thấy độ dao động. Lượt đầu của mỗi cấu hình gồm cả thời gian nạp model nên
được ghi riêng, không trộn vào thời gian suy luận.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

WEIGHTS = "/models/comic-text-detector.onnx"

#: Chốt trước: 0 = hiện trạng (không đặt gì, ORT tự quyết theo 192 core của máy chủ).
CAC_CAU_HINH = [0, 2, 4]
SO_LUOT = 2


def main() -> None:
    trang = sys.argv[1] if len(sys.argv) > 1 else None
    if not trang or not Path(trang).exists():
        raise SystemExit("Cần đường dẫn tới một trang truyện thật")

    import os

    from app.services.detect.ctd import CTDDetector

    print(f"Trang đo: {trang}")
    print(f"CPU khả dụng cho tiến trình này: {len(os.sched_getaffinity(0))} core "
          f"(máy chủ có {os.cpu_count()} core)\n")

    for threads in CAC_CAU_HINH:
        nhan = "mặc định (không đặt)" if threads == 0 else f"{threads} luồng"
        det = CTDDetector(weights_path=WEIGHTS, device="cpu", intra_op_threads=threads)
        for luot in range(1, SO_LUOT + 1):
            t0 = time.perf_counter()
            vung = det.detect(trang)
            giay = time.perf_counter() - t0
            ghi_chu = " (gồm nạp model)" if luot == 1 else ""
            print(f"intra_op={threads:<2} [{nhan:>20}] lượt {luot}: "
                  f"{giay:6.2f}s · {len(vung)} vùng{ghi_chu}")
        print()


if __name__ == "__main__":
    main()
