#!/usr/bin/env python3
"""Smoke sau deploy trên Chromium THẬT, đánh vào bản hosted VibeHost.

    ../.venv/bin/python scripts/do_smoke_hosted.py

CORS do trình duyệt thi hành, không phải curl. Tệp này dựng một website lạ ở cổng 9999 rồi từ
đó cố đọc API hosted — đúng thứ cần chặn.
"""
from __future__ import annotations

import http.server
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

WEB = "https://translation.cmc-1.vibenode.matbao.ai"
API = "https://translation-api.cmc-1.vibenode.matbao.ai"
CHROME = "/home/coder/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
CONG_LA = 9999

KQ: list[tuple[str, bool, str]] = []

TRANG_LA = """<!doctype html><meta charset="utf-8"><title>website la</title><h1>x</h1>
<script>
window.thu = async (url) => {
  try { const r = await fetch(url); const t = await r.text();
        return { doc_duoc: true, status: r.status, mau: t.slice(0, 60) } }
  catch (e) { return { doc_duoc: false, loi: String(e) } }
}
</script>"""


def ghi(muc, dat, chi_tiet=""):
    KQ.append((muc, dat, chi_tiet))
    print(f"  [{'ĐẠT ' if dat else 'HỎNG'}] {muc}" + (f" — {chi_tiet}" if chi_tiet else ""),
          flush=True)


class Phuc(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        b = TRANG_LA.encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *a):
        pass


def main() -> int:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    may = socketserver.ThreadingTCPServer(("127.0.0.1", CONG_LA), Phuc)
    threading.Thread(target=may.serve_forever, daemon=True).start()

    loi_console: list[str] = []
    with sync_playwright() as p:
        tr = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
        ng = tr.new_context(viewport={"width": 1280, "height": 900})
        try:
            # ---------- 1. Giao diện hosted ----------
            print("1) Giao diện hosted")
            web = ng.new_page()
            web.on("console", lambda m: loi_console.append(m.text) if m.type == "error" else None)
            web.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
            web.goto(WEB, wait_until="networkidle", timeout=60000)

            ghi("H1 tải được qua HTTPS", web.url.startswith("https://"), web.url)
            ghi("H2 __API_BASE__ trỏ đúng API hosted",
                web.evaluate("() => window.__API_BASE__") == API,
                str(web.evaluate("() => window.__API_BASE__")))

            chu = web.inner_text("body")
            ghi("H3 giao diện E11 hiện form tạo chapter",
                "Tạo chapter" in chu or "chapter" in chu.lower(),
                chu.replace("\n", " | ")[:90])

            # Giao diện gọi API chéo nguồn THẬT (web origin -> api origin)
            kq = web.evaluate(
                "async (api) => { try { const r = await fetch(api + '/api/v1/health');"
                " return { ok: true, s: r.status, t: await r.text() } }"
                " catch (e) { return { ok: false, loi: String(e) } } }", API)
            ghi("H4 giao diện ĐỌC ĐƯỢC API chéo nguồn (CORS cho đúng origin này)",
                kq.get("ok") and kq.get("s") == 200 and '"ok"' in kq.get("t", ""),
                str(kq)[:80])

            # ---------- 2. Website lạ ----------
            print("\n2) Website lạ cố đọc API hosted")
            la = ng.new_page()
            la.goto(f"http://127.0.0.1:{CONG_LA}/", wait_until="domcontentloaded")
            for ten, u in [("/api/v1/health", f"{API}/api/v1/health"),
                           ("/healthz", f"{API}/healthz")]:
                r = la.evaluate("(u) => window.thu(u)", u)
                ghi(f"H5 website lạ KHÔNG đọc được {ten}", not r["doc_duoc"],
                    r.get("loi", str(r))[:80])

            # ---------- 3. Giao diện ở nhiều cỡ màn hình ----------
            print("\n3) Giao diện ở các cỡ màn hình")
            for w, h in [(360, 800), (768, 1024), (1280, 900), (1600, 1100)]:
                web.set_viewport_size({"width": w, "height": h})
                web.wait_for_timeout(400)
                tran = web.evaluate(
                    "() => document.documentElement.scrollWidth > window.innerWidth + 1")
                ghi(f"H6 {w}x{h} không tràn ngang", not tran,
                    f"scrollW={web.evaluate('() => document.documentElement.scrollWidth')}")

            ghi("Z1 không có lỗi JS trên giao diện hosted", not loi_console,
                "; ".join(loi_console[:3]))
        finally:
            tr.close()
            may.shutdown()

    print("\n" + "=" * 70)
    d = sum(1 for _, x, _ in KQ if x)
    print(f"KẾT QUẢ: {d}/{len(KQ)} đạt")
    for t, x, c in KQ:
        if not x:
            print(f"  HỎNG: {t} — {c}")
    return 0 if d == len(KQ) else 1


if __name__ == "__main__":
    sys.exit(main())
