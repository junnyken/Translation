#!/usr/bin/env python3
"""Đo E1a trên Chromium THẬT — trình duyệt mới là thứ thi hành CORS, không phải curl.

    ../.venv/bin/python scripts/do_run_e1a.py

Dựng một máy chủ tĩnh ở cổng 9999 để đóng vai **website lạ**, rồi từ đó gọi API Translation
local. `http://127.0.0.1:9999` là origin KHÁC với `http://127.0.0.1:5174` (khác cổng ⇒ khác
origin), nên đây là phép thử chéo nguồn thật, không phải mô phỏng.

Tên miền giống-localhost được ánh xạ về loopback bằng `--host-resolver-rules`, nên
`http://localhost.evil.example:9999` là một origin THẬT trong trình duyệt.
"""
from __future__ import annotations

import http.server
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

GOC = Path(__file__).resolve().parents[1]
CHROME = Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
UI = "http://127.0.0.1:5174"
API_TRUC_TIEP = "http://127.0.0.1:8010"
CONG_LA = 9999

KQ: list[tuple[str, bool, str]] = []

TRANG_LA = """<!doctype html><meta charset="utf-8"><title>website lạ</title>
<h1>Website lạ — thử đọc API Translation local</h1><pre id="kq">chưa chạy</pre>
<script>
window.thu = async (url) => {
  try {
    const r = await fetch(url, { method: 'GET' })
    const t = await r.text()
    return { doc_duoc: true, status: r.status, dai: t.length, mau: t.slice(0, 80) }
  } catch (e) {
    return { doc_duoc: false, loi: String(e) }
  }
}
</script>"""


def ghi(muc: str, dat: bool, chi_tiet: str = "") -> None:
    KQ.append((muc, dat, chi_tiet))
    print(f"  [{'ĐẠT ' if dat else 'HỎNG'}] {muc}" + (f" — {chi_tiet}" if chi_tiet else ""),
          flush=True)


def sql(cau: str) -> str:
    return subprocess.run(
        ["docker", "exec", "translation-db-1", "psql", "-U", "translation",
         "-d", "translation", "-tAc", cau],
        capture_output=True, text=True, timeout=60).stdout.strip()


class Phuc(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        than = TRANG_LA.encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(than)))
            self.end_headers()
            self.wfile.write(than)
        except (BrokenPipeError, ConnectionResetError):
            # Trình duyệt đóng sớm là chuyện thường; đừng để nó thành tiếng ồn.
            pass

    def log_message(self, *a):  # im lặng
        pass


def main() -> int:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    may = socketserver.ThreadingTCPServer(("127.0.0.1", CONG_LA), Phuc)
    threading.Thread(target=may.serve_forever, daemon=True).start()
    print(f"máy chủ 'website lạ' chạy ở http://127.0.0.1:{CONG_LA}\n")

    du_an = sql("select id from project where name like 'E15%' order by created_at desc limit 1")
    trang = sql(f"select id from page where project_id='{du_an}' limit 1") if du_an else ""

    loi_console: list[str] = []
    tien_ich = GOC / "extension"

    with sync_playwright() as p:
        ngu_canh = p.chromium.launch_persistent_context(
            user_data_dir="",
            executable_path=str(CHROME),
            headless=True,
            args=[
                "--headless=new",
                f"--disable-extensions-except={tien_ich}",
                f"--load-extension={tien_ich}",
                "--no-sandbox",
                # Cho tên miền giống-localhost trỏ về loopback => origin THẬT trong trình duyệt.
                "--host-resolver-rules=MAP localhost.evil.example 127.0.0.1,"
                "MAP evil.example 127.0.0.1,MAP 127.0.0.1.nip.io 127.0.0.1",
            ],
        )
        try:
            sw = ngu_canh.service_workers[0] if ngu_canh.service_workers else \
                ngu_canh.wait_for_event("serviceworker", timeout=15000)
            ext_id = sw.url.split("/")[2]
            print(f"ID tiện ích: {ext_id}\n")

            # ---------- 1. Origin ĐƯỢC PHÉP: giao diện web local ----------
            print("1) Origin được phép — giao diện Translation local")
            ui = ngu_canh.new_page()
            ui.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
            ui.goto(UI, wait_until="networkidle")
            kq = ui.evaluate(
                "async () => { const r = await fetch('/api/v1/health');"
                " return { s: r.status, t: await r.text() } }")
            ghi("L1 giao diện gọi API CÙNG NGUỒN thành công (CORS không can thiệp)",
                kq["s"] == 200 and '"ok"' in kq["t"], f"HTTP {kq['s']} {kq['t'][:40]}")

            if du_an:
                kq2 = ui.evaluate(
                    "async (id) => { const r = await fetch('/api/v1/projects/'+id);"
                    " return { s: r.status, dai: (await r.text()).length } }", du_an)
                ghi("L2 giao diện đọc được dữ liệu chapter thật", kq2["s"] == 200 and kq2["dai"] > 50,
                    f"HTTP {kq2['s']}, {kq2['dai']} byte")

            # ---------- 2. Website LẠ cố đọc API ----------
            print("\n2) Website lạ (origin khác) cố đọc API Translation local")
            la = ngu_canh.new_page()
            la.goto(f"http://127.0.0.1:{CONG_LA}/", wait_until="domcontentloaded")
            ghi("L3 trang lạ đúng là origin KHÁC",
                la.evaluate("() => location.origin") != UI,
                la.evaluate("() => location.origin"))

            r = la.evaluate("() => window.thu('http://127.0.0.1:5174/api/v1/health')")
            ghi("L4 website lạ KHÔNG đọc được /api/v1/health", not r["doc_duoc"],
                r.get("loi", str(r))[:90])

            if du_an:
                r2 = la.evaluate(
                    "(id) => window.thu('http://127.0.0.1:5174/api/v1/projects/'+id)", du_an)
                ghi("L5 website lạ KHÔNG đọc được dữ liệu chapter", not r2["doc_duoc"],
                    r2.get("loi", str(r2))[:90])

            r3 = la.evaluate("() => window.thu('http://127.0.0.1:8010/api/v1/health')")
            ghi("L6 website lạ KHÔNG đọc được API trực tiếp (cổng 8010)", not r3["doc_duoc"],
                r3.get("loi", str(r3))[:90])

            # ---------- 3. Origin giống localhost ----------
            print("\n3) Origin trông giống localhost")
            gia = ngu_canh.new_page()
            gia.goto(f"http://localhost.evil.example:{CONG_LA}/", wait_until="domcontentloaded")
            ghi("L7 origin giống-localhost là origin THẬT trong trình duyệt",
                "localhost.evil.example" in gia.evaluate("() => location.origin"),
                gia.evaluate("() => location.origin"))
            r4 = gia.evaluate("() => window.thu('http://127.0.0.1:5174/api/v1/health')")
            ghi("L8 localhost.evil.example KHÔNG đọc được API", not r4["doc_duoc"],
                r4.get("loi", str(r4))[:90])
            gia.close()
            la.close()

            # ---------- 4. Tiện ích E1 ----------
            print("\n4) Tiện ích E1")
            hanh_vi = sw.evaluate("() => chrome.sidePanel.getPanelBehavior()")
            ghi("L9 bấm biểu tượng thanh công cụ ĐƯỢC nối để mở Side Panel",
                hanh_vi.get("openPanelOnActionClick") is True, str(hanh_vi))

            mf = sw.evaluate("() => chrome.runtime.getManifest()")
            ghi("L10 manifest giữ quyền tối thiểu — không content script, host_permissions rỗng",
                "content_scripts" not in mf and mf.get("host_permissions") == []
                and sorted(mf["permissions"]) == ["sidePanel", "storage"],
                str(mf.get("permissions")))

            panel = ngu_canh.new_page()
            panel.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
            panel.goto(f"chrome-extension://{ext_id}/src/sidepanel/index.html")
            panel.wait_for_selector("#o-dia-chi", timeout=10000)
            panel.fill("#o-dia-chi", UI)
            panel.click("button[data-vai='chinh']")
            panel.wait_for_selector("text=Tạo chapter mới", timeout=20000)
            panel.wait_for_function(
                "() => !document.body.innerText.includes('Đang kiểm tra kết nối')", timeout=20000)
            noi_duoc = "Đã kết nối local" in panel.inner_text("body")
            print(f"    (tiện ích {'ĐỌC ĐƯỢC' if noi_duoc else 'KHÔNG đọc được'} trạng thái)")

            with ngu_canh.expect_page() as tab:
                panel.click("text=Tạo chapter mới")
            t = tab.value
            t.wait_for_load_state("domcontentloaded", timeout=15000)
            ghi("L11 'Tạo chapter mới' mở ĐÚNG route web app dù CORS chặt",
                t.url.rstrip("/") == UI, t.url)
            t.close()

            if noi_duoc:
                ghi("L12 origin tiện ích được khai ⇒ đọc metadata thật hoạt động", True,
                    "chế độ đọc dữ liệu")
            else:
                ghi("L12 không đọc được ⇒ lùi về chỉ-mở-link và NÓI THẲNG lý do",
                    "Không kết nối được Translation local" in panel.inner_text("body")
                    and "CORS" in panel.inner_text("body"),
                    "chế độ chỉ-mở-link")

            # ---------- 5. Máy chủ tắt: nói thật, không giả vờ rỗng ----------
            print("\n5) Tắt máy chủ giao diện — trạng thái phải trung thực")
            subprocess.run(["docker", "compose", "-f", str(GOC / "deploy/docker-compose.yml"),
                            "stop", "frontend"], capture_output=True, timeout=120, cwd=GOC)
            panel2 = ngu_canh.new_page()
            panel2.goto(f"chrome-extension://{ext_id}/src/sidepanel/index.html")
            panel2.wait_for_selector("text=Tạo chapter mới", timeout=20000)
            panel2.wait_for_function(
                "() => !document.body.innerText.includes('Đang kiểm tra kết nối')", timeout=30000)
            chu = panel2.inner_text("body")
            print("    --- panel lúc máy chủ tắt ---")
            for d in chu.splitlines():
                if d.strip():
                    print(f"      | {d.strip()}")
            # Tiêu đề render HOA do CSS `text-transform`, nên không cắt chuỗi theo tên tiêu đề.
            # Ý định thật cần kiểm: (a) nói rõ chưa kết nối kèm lý do, (b) câu về danh sách rỗng
            # KHÔNG được trình bày như một khẳng định "máy chủ không có chapter nào".
            ghi("L13 máy chủ tắt ⇒ báo chưa kết nối kèm đủ lý do",
                "Không kết nối được Translation local" in chu
                and "chưa chạy" in chu and "CORS" in chu)
            ghi("L13b câu danh sách rỗng chỉ về ứng dụng, KHÔNG khẳng định 'không có chapter'",
                "cần được mở từ ứng dụng Translation" in chu
                and "không có chapter" not in chu.lower())
            panel2.close()

            print("    bật lại máy chủ giao diện…")
            subprocess.run(["docker", "compose", "-f", str(GOC / "deploy/docker-compose.yml"),
                            "start", "frontend"], capture_output=True, timeout=180, cwd=GOC)
            ngu_canh.new_page().goto("about:blank")
            for _ in range(30):
                try:
                    kt = ngu_canh.request.get(f"{UI}/api/v1/health", timeout=3000)
                    if kt.status == 200:
                        break
                except Exception:
                    pass
                ngu_canh.pages[0].wait_for_timeout(2000)

            # ---------- 6. Sau khi khởi động lại: kiểm lại cho/chặn ----------
            print("\n6) Sau khi khởi động lại — cấu hình không phải chỉ đúng nhờ hot-reload")
            ui2 = ngu_canh.new_page()
            ui2.goto(UI, wait_until="networkidle")
            k = ui2.evaluate("async () => (await fetch('/api/v1/health')).status")
            ghi("L14 giao diện vẫn chạy sau khi khởi động lại", k == 200, f"HTTP {k}")

            la2 = ngu_canh.new_page()
            la2.goto(f"http://127.0.0.1:{CONG_LA}/", wait_until="domcontentloaded")
            r5 = la2.evaluate("() => window.thu('http://127.0.0.1:5174/api/v1/health')")
            ghi("L15 website lạ VẪN bị chặn sau khi khởi động lại", not r5["doc_duoc"],
                r5.get("loi", str(r5))[:90])

            ghi("Z1 không có ngoại lệ JS nào ở giao diện/panel", not loi_console,
                "; ".join(loi_console[:2]))
        finally:
            ngu_canh.close()
            may.shutdown()

    print("\n" + "=" * 70)
    dat = sum(1 for _, d, _ in KQ if d)
    print(f"KẾT QUẢ: {dat}/{len(KQ)} đạt")
    for ten, d, chi in KQ:
        if not d:
            print(f"  HỎNG: {ten} — {chi}")
    return 0 if dat == len(KQ) else 1


if __name__ == "__main__":
    sys.exit(main())
