#!/usr/bin/env python3
"""P3a — smoke MỘT trang qua giao diện hosted, để chứng minh worker thật sự chạy pipeline.

    ../.venv/bin/python scripts/do_run_p3a.py <đường-dẫn-ảnh-smoke>

Bắt buộc đi qua giao diện E11 hosted: KHÔNG dùng curl/Postman/DB/Celery để thay thế. Đây là
điểm mấu chốt của P3a — nó chứng minh đúng con đường mà người dùng thật sẽ đi.

Bằng chứng worker sống là **việc được tiêu thụ và trạng thái cuối trung thực**, KHÔNG phải
`worker.trang_thai` (trường đó kẹt ở `starting` vĩnh viễn ở `ROLE=all`).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

WEB = "https://translation.cmc-1.vibenode.matbao.ai"
API = "https://translation-api.cmc-1.vibenode.matbao.ai"
CHROME = "/home/coder/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
TEN = "P3a hosted smoke — DO NOT TREAT AS PILOT"

KQ: list[tuple[str, bool, str]] = []


def ghi(muc, dat, chi_tiet=""):
    KQ.append((muc, dat, chi_tiet))
    print(f"  [{'ĐẠT ' if dat else 'HỎNG'}] {muc}" + (f" — {chi_tiet}" if chi_tiet else ""),
          flush=True)


def do(muc, chi_tiet):
    print(f"  [ĐO  ] {muc} — {chi_tiet}", flush=True)


def api(dd):
    with urllib.request.urlopen(f"{API}{dd}", timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> int:
    anh = Path(sys.argv[1])
    if not anh.exists():
        print(f"không thấy ảnh: {anh}")
        return 1
    print(f"ảnh smoke: {anh} ({anh.stat().st_size} byte)\n")

    loi_console: list[str] = []
    t0 = time.time()

    with sync_playwright() as p:
        tr = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
        ng = tr.new_context(viewport={"width": 1400, "height": 1000})
        trang = ng.new_page()
        trang.on("console", lambda m: loi_console.append(m.text) if m.type == "error" else None)
        trang.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))

        try:
            # ---------- Step C: tạo chapter + tải trang qua GIAO DIỆN ----------
            print("Step C — tạo chapter + tải trang qua giao diện hosted")
            trang.goto(WEB, wait_until="networkidle", timeout=60000)
            trang.wait_for_selector("#tieu-de-tao", timeout=30000)
            ghi("C1 giao diện tạo chapter hiện ra", True)

            # `Input` của E11 render `<input className="o">` KHÔNG kèm thuộc tính `type`,
            # nên bộ chọn theo thuộc tính `input[type='text']` không khớp — phải dùng lớp.
            trang.fill("section.the-lon input.o", TEN)
            # Ngôn ngữ gốc: tiếng Anh (PaddleOCR — engine có trả đường bao dòng)
            trang.select_option("section.the-lon select.o >> nth=0", "en")
            trang.select_option("section.the-lon select.o >> nth=1", "personal")
            trang.set_input_files("input[type='file']", str(anh))
            trang.wait_for_timeout(600)
            ghi("C2 điền thông tin + chọn ảnh qua dropzone thật", True)

            trang.click("#nut-tao")
            # Sau khi tạo xong, địa chỉ đổi sang #project=<id>
            trang.wait_for_function(
                "() => location.hash.includes('project=')", timeout=180000)
            pid = trang.evaluate("() => new URLSearchParams(location.hash.slice(1)).get('project')")
            ghi("C3 chapter được tạo qua giao diện, KHÔNG dùng curl", bool(pid), f"project={pid}")

            # ---------- Step D: theo dõi pipeline THẬT ----------
            print("\nStep D — theo dõi worker tiêu thụ việc")
            moc: list[tuple[float, str]] = []
            tt = ""
            het = time.time() + 1500
            pg = None
            while time.time() < het:
                try:
                    d = api(f"/api/v1/projects/{pid}")
                except Exception as e:
                    time.sleep(5)
                    continue
                if not d.get("pages"):
                    time.sleep(4)
                    continue
                pg = d["pages"][0]
                if pg["status"] != tt:
                    tt = pg["status"]
                    moc.append((time.time() - t0, tt))
                    print(f"      {time.time()-t0:7.1f}s  ->  {tt}", flush=True)
                if tt in {"typeset_done", "ready_for_export", "detection_failed"}:
                    break
                time.sleep(5)

            do("các mốc trạng thái", " · ".join(f"{s:.0f}s:{n}" for s, n in moc) or "(không có)")
            ghi("D1 worker TIÊU THỤ việc — trạng thái đổi khỏi 'queued'",
                len(moc) > 1, f"{len(moc)} lần chuyển")
            ghi("D2 trang đi tới trạng thái cuối trung thực (không kẹt mãi)",
                tt in {"typeset_done", "ready_for_export", "detection_failed"}, tt)

            if pg:
                pgid = pg["id"]
                ct = api(f"/api/v1/pages/{pgid}/detail")
                vung = ct.get("regions", [])
                do("số vùng nhận diện được", str(len(vung)))
                ghi("D3 bước nhận diện tạo ra vùng chữ THẬT", len(vung) >= 2,
                    f"{len(vung)} vùng (ảnh có 2 bong bóng)")

                doc_duoc = [r for r in vung if (r.get("raw_text") or "").strip()]
                do("vùng đọc được chữ", f"{len(doc_duoc)}/{len(vung)}")
                for r in vung[:4]:
                    do("  OCR", f"{(r.get('raw_text') or '')[:46]!r} -> "
                                f"{(r.get('translated_text') or '')[:46]!r}")

                pdt = api(f"/api/v1/pages/{pgid}")
                ghi("D4 ảnh xoá chữ (clean image) được tạo — LaMa chạy xong",
                    bool(pdt.get("clean_image_path")), str(pdt.get("clean_image_path"))[:60])

                dich = [r for r in vung if (r.get("translated_text") or "").strip()]
                ghi("D5 có bản dịch thật (hoặc nêu rõ giới hạn)", len(dich) > 0,
                    f"{len(dich)}/{len(vung)} vùng có bản dịch")

                # ---------- Step E: hiện vật ----------
                print("\nStep E — hiện vật trước khi restart")
                for ten_r, r in [("clean-image", "clean-image"),
                                 ("typeset-preview", "typeset-preview")]:
                    res = ng.request.get(f"{API}/api/v1/pages/{pgid}/{r}", timeout=60000)
                    ok = res.status == 200
                    ghi(f"E1 {ten_r} mở được", ok,
                        f"HTTP {res.status} · {res.headers.get('content-type')} · "
                        f"{len(res.body()) if ok else 0} byte")

                print(f"\n  >>> project_id = {pid}")
                print(f"  >>> page_id    = {pgid}")

            ghi("Z1 không có lỗi JS trên giao diện hosted", not loi_console,
                "; ".join(loi_console[:3]))
        finally:
            tr.close()

    print("\n" + "=" * 70)
    d = sum(1 for _, x, _ in KQ if x)
    print(f"KẾT QUẢ: {d}/{len(KQ)} đạt   (tổng {time.time()-t0:.0f}s)")
    for t, x, c in KQ:
        if not x:
            print(f"  HỎNG: {t} — {c}")
    return 0 if d == len(KQ) else 1


if __name__ == "__main__":
    sys.exit(main())
