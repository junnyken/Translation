#!/usr/bin/env python3
"""Đo Run C — chạy truyện tranh THẬT qua pipeline thật rồi báo cáo số liệu.

Vì sao cần script này: toàn bộ số liệu M2–M8 mới chỉ đo trên ảnh tổng hợp nền phẳng do repo tự
sinh. Run C là phép đo trên ảnh thật, và nó phải **lặp lại được** — chạy tay rồi chép số vào
tài liệu là cách để số liệu sai mà không ai biết.

Dùng:
    ../.venv/bin/python scripts/do_run_c.py test_fixtures/external/*_1600.png
    ../.venv/bin/python scripts/do_run_c.py --engine llm_context <ảnh...>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import urllib.error
import urllib.request

GOC = "http://localhost:8010/api/v1"
#: Trạng thái coi là "đã xong hẳn" cho một trang.
XONG = {"typeset_done", "ready_for_export"}
#: Trạng thái coi là hỏng — dừng chờ, không treo mãi.
HONG = {"detection_failed"}


def goi(duong_dan: str, method: str = "GET", data: dict | None = None, timeout: int = 120):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(f"{GOC}{duong_dan}", data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def tai_len(project_id: str, duong_dan: Path, timeout: int = 300) -> dict:
    """Upload multipart thuần bằng thư viện chuẩn — không thêm phụ thuộc chỉ để chạy một script."""
    ranh = "----runc"
    than = (
        f"--{ranh}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{duong_dan.name}\"\r\nContent-Type: image/png\r\n\r\n"
    ).encode() + duong_dan.read_bytes() + f"\r\n--{ranh}--\r\n".encode()
    req = urllib.request.Request(
        f"{GOC}/projects/{project_id}/pages", data=than, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={ranh}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def cho_trang(page_id: str, tran_giay: int) -> tuple[str, float]:
    bat_dau = time.time()
    truoc = None
    while time.time() - bat_dau < tran_giay:
        tt = goi(f"/pages/{page_id}")["status"]
        if tt != truoc:
            print(f"      {int(time.time()-bat_dau):>4}s  {tt}", flush=True)
            truoc = tt
        if tt in XONG or tt in HONG:
            return tt, time.time() - bat_dau
        time.sleep(5)
    return truoc or "?", time.time() - bat_dau


def cho_job(job_id: str, tran_giay: int) -> float:
    """Chờ một Job chạy xong. Dùng khi trạng thái Page không đổi đủ để nhận ra tiến độ."""
    bat_dau = time.time()
    while time.time() - bat_dau < tran_giay:
        job = goi(f"/jobs/{job_id}")
        if job["status"] in ("done", "failed"):
            if job["status"] == "failed":
                print(f"      job {job['type']} HỎNG: {job.get('error_log')}", flush=True)
            return time.time() - bat_dau
        time.sleep(4)
    return time.time() - bat_dau


def bao_cao_trang(page_id: str) -> dict:
    ct = goi(f"/pages/{page_id}/detail")
    vung = ct["regions"]
    return {
        "so_vung": len(vung),
        "vung": [
            {
                "thu_tu": v.get("reading_order"),
                "khung": {k: round(x) for k, x in v["bbox"].items()},
                "do_tin_cay": round(v["confidence"], 3) if v.get("confidence") is not None else None,
                "chu_goc": v.get("raw_text"),
                "trang_thai_ocr": v.get("ocr_status"),
                "ban_dich": v.get("translated_text"),
                "co_chu": v.get("font_size"),
                "vua_khung": v.get("fit_status"),
            }
            for v in vung
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("anh", nargs="+", type=Path)
    ap.add_argument("--ten", default="Run C — truyện tranh thật")
    ap.add_argument("--nguon", default="en", choices=["en", "ja", "zh"])
    ap.add_argument("--engine", default=None, choices=["google_fast", "llm_context"])
    ap.add_argument("--tran-giay", type=int, default=1800)
    ap.add_argument("--ra", type=Path, default=Path("run_c_ket_qua.json"))
    args = ap.parse_args()

    thieu = [p for p in args.anh if not p.is_file()]
    if thieu:
        print("Không thấy ảnh:", *thieu, sep="\n  ")
        return 2

    du_an = goi("/projects", "POST", {
        "name": args.ten, "source_lang": args.nguon, "intended_use": "study",
    })
    print(f"Dự án: {du_an['id']}  ({args.nguon} -> vi)\n")

    ket_qua = {"project_id": du_an["id"], "nguon": args.nguon, "trang": []}
    for i, anh in enumerate(args.anh, 1):
        print(f"[{i}/{len(args.anh)}] {anh.name}")
        len_ = tai_len(du_an["id"], anh)
        page_id = len_["page_id"]
        tt, giay = cho_trang(page_id, args.tran_giay)

        if args.engine:
            print(f"      dịch lại bằng {args.engine}…", flush=True)
            xin = goi(f"/pages/{page_id}/retry-translate?engine={args.engine}", "POST")
            # Trang đang ở `typeset_done`; nếu chỉ chờ trạng thái thì hàm trả về NGAY vì
            # `typeset_done` vốn đã nằm trong tập "đã xong". Phải bám theo JOB.
            them = cho_job(xin["job_id"], args.tran_giay)
            tt, them2 = cho_trang(page_id, args.tran_giay)
            giay += them + them2

        bc = bao_cao_trang(page_id)
        bc.update({"page_id": page_id, "tep": anh.name, "trang_thai": tt, "giay": round(giay, 1)})
        ket_qua["trang"].append(bc)

        vua = sum(1 for v in bc["vung"] if v["vua_khung"] == "fit_ok")
        tran = sum(1 for v in bc["vung"] if v["vua_khung"] == "overflow_warning")
        can_xem = sum(1 for v in bc["vung"] if v["trang_thai_ocr"] == "needs_manual")
        print(f"      => {bc['so_vung']} vùng | vừa khung {vua} | tràn {tran} | "
              f"OCR cần xem lại {can_xem} | {bc['giay']}s\n", flush=True)

    args.ra.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding="utf-8")
    tong_vung = sum(t["so_vung"] for t in ket_qua["trang"])
    print(f"Xong. {len(ket_qua['trang'])} trang, {tong_vung} vùng chữ. Chi tiết: {args.ra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
