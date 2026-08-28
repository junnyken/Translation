#!/usr/bin/env python3
"""Soi giao diện bằng Chromium thật — dùng cho audit trước/sau của E11.

Đo thứ có thể đo chứ không phán bằng mắt: tràn ngang, thứ tự tab, số lỗi console,
và chụp ảnh màn hình ở 4 kích thước bắt buộc.

    ../.venv/bin/python scripts/soi_giao_dien.py --ra /duong/dan/thu-muc --nhan truoc
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

KICH_THUOC = [("mobile", 360, 800), ("tablet", 768, 1024),
              ("desktop", 1280, 900), ("wide", 1600, 1100)]


def do_mot_man(page, ten: str, rong: int, cao: int, goc: str, ra: Path, nhan: str) -> dict:
    page.set_viewport_size({"width": rong, "height": cao})
    page.goto(goc, wait_until="networkidle")
    page.wait_for_timeout(700)

    tran_ngang = page.evaluate(
        "() => ({ cuon: document.documentElement.scrollWidth,"
        " nhin: document.documentElement.clientWidth })"
    )
    # Phần tử nào thò ra ngoài khung nhìn — chỉ ra ĐÚNG thủ phạm, không chỉ nói "có tràn".
    thu_pham = page.evaluate("""() => {
      const rong = document.documentElement.clientWidth;
      return [...document.querySelectorAll('body *')]
        .filter(e => e.getBoundingClientRect().right > rong + 1)
        .slice(0, 5)
        .map(e => `${e.tagName.toLowerCase()}.${(e.className||'').toString().split(' ')[0]}`);
    }""")
    tab = page.evaluate("""() => [...document.querySelectorAll(
        'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])')]
        .filter(e => !e.disabled && e.offsetParent !== null)
        .map(e => e.tagName.toLowerCase() + (e.type ? `[${e.type}]` : ''))""")
    anh = ra / f"{nhan}_{ten}.png"
    page.screenshot(path=str(anh), full_page=True)
    return {
        "kich_thuoc": f"{rong}x{cao}",
        "tran_ngang": tran_ngang["cuon"] > tran_ngang["nhin"] + 1,
        "rong_cuon": tran_ngang["cuon"], "rong_nhin": tran_ngang["nhin"],
        "phan_tu_tho_ra": thu_pham,
        "so_diem_dung_tab": len(tab),
        "thu_tu_tab": tab[:14],
        "anh": str(anh),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--goc", default="http://localhost:5174/")
    ap.add_argument("--ra", type=Path, required=True)
    ap.add_argument("--nhan", default="truoc")
    args = ap.parse_args()
    args.ra.mkdir(parents=True, exist_ok=True)

    kq: dict = {"goc": args.goc, "man": []}
    with sync_playwright() as pw:
        trinh_duyet = pw.chromium.launch()
        ngu_canh = trinh_duyet.new_context()
        page = ngu_canh.new_page()
        loi_console: list[str] = []
        page.on("console", lambda m: loi_console.append(f"{m.type}: {m.text}")
                if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: loi_console.append(f"requestfailed: {r.url}"))
        page.on("response", lambda r: loi_console.append(f"http {r.status}: {r.url}")
                if r.status >= 400 else None)

        for ten, rong, cao in KICH_THUOC:
            kq["man"].append(do_mot_man(page, ten, rong, cao, args.goc, args.ra, args.nhan))
            print(f"  {ten:<8} {rong}x{cao}: tràn ngang="
                  f"{kq['man'][-1]['tran_ngang']}, {kq['man'][-1]['so_diem_dung_tab']} điểm dừng tab")

        kq["console"] = loi_console
        trinh_duyet.close()

    (args.ra / f"{args.nhan}_ket_qua.json").write_text(
        json.dumps(kq, ensure_ascii=False, indent=2))
    print(f"\nconsole: {len(loi_console)} dòng lỗi/cảnh báo")
    for d in loi_console[:5]:
        print("   ", d[:160])
    print(f"Đã ghi {args.ra}/{args.nhan}_ket_qua.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
