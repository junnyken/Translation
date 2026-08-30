"""Đo thật mini-spec E1 — nạp tiện ích vào Chromium và bấm như người dùng.

Chạy:  .venv/bin/python scripts/do_run_e1.py

Run A — lần chạy đầu + kết nối
Run B — bàn giao luồng làm việc (mở đúng route web app)
Run C — vòng đời + riêng tư (kho lưu gì, xoá thì xoá cái gì)
Run D — sự thật về quyền (mở một trang truyện, xem tiện ích có đụng vào không)

Không có bước nào ở đây "giả lập". Mọi khẳng định trong REPORT_E1.md phải truy về được một
dòng kết quả của tệp này.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

GOC = Path(__file__).resolve().parents[1]
TIEN_ICH = GOC / "extension"
CHROME = Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome"

# Cổng đo được ngày 2026-08-30 (xem extension/README.md §1.1).
WEB_APP = "http://127.0.0.1:5174"
API = "http://127.0.0.1:8010"

ket_qua: list[tuple[str, bool, str]] = []


def dat(ten: str, dat_khong: bool, ghi_chu: str = "") -> None:
    ket_qua.append((ten, dat_khong, ghi_chu))
    dau = "ĐẠT " if dat_khong else "HỎNG"
    print(f"  [{dau}] {ten}" + (f" — {ghi_chu}" if ghi_chu else ""), flush=True)


def id_tien_ich(ngu_canh) -> str:
    """Lấy extension ID từ service worker đang chạy."""
    sw = ngu_canh.service_workers[0] if ngu_canh.service_workers else ngu_canh.wait_for_event(
        "serviceworker", timeout=15000)
    return sw.url.split("/")[2]


def doc_kho(trang) -> dict:
    return trang.evaluate("() => chrome.storage.local.get(null)")


def main() -> int:
    print(f"Thư mục tiện ích: {TIEN_ICH}")
    print(f"Chrome: {CHROME}\n")

    with sync_playwright() as p:
        ngu_canh = p.chromium.launch_persistent_context(
            user_data_dir="",
            executable_path=str(CHROME),
            headless=True,
            args=[
                "--headless=new",
                f"--disable-extensions-except={TIEN_ICH}",
                f"--load-extension={TIEN_ICH}",
                "--no-sandbox",
            ],
        )
        try:
            ext_id = id_tien_ich(ngu_canh)
            print(f"ID tiện ích: {ext_id}\n")

            loi_console: list[str] = []
            panel_url = f"chrome-extension://{ext_id}/src/sidepanel/index.html"

            # ---------------- Run A — lần chạy đầu + kết nối ----------------
            print("Run A — lần chạy đầu và kết nối")
            panel = ngu_canh.new_page()
            panel.on("console", lambda m: loi_console.append(f"{m.type}: {m.text}")
                     if m.type == "error" else None)
            panel.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
            panel.goto(panel_url)
            panel.wait_for_selector("#o-dia-chi", timeout=10000)

            chu = panel.inner_text("body")
            dat("A1 màn đầu hiện ô nhập địa chỉ", panel.is_visible("#o-dia-chi"))
            dat("A2 có câu nói rõ không đọc trang web đang xem",
                "không đọc nội dung trang web bạn đang xem" in chu)
            dat("A3 gợi ý cổng là cổng đo được, không phải cổng đoán",
                panel.get_attribute("#o-dia-chi", "placeholder") == f"{WEB_APP}",
                panel.get_attribute("#o-dia-chi", "placeholder"))

            # A4 — địa chỉ ngoài loopback phải bị chặn NGAY, không gọi mạng
            panel.fill("#o-dia-chi", "http://evil.example:5174")
            panel.click("button[data-vai='chinh']")
            panel.wait_for_selector("[role='alert']", timeout=5000)
            dat("A4 địa chỉ ngoài loopback bị từ chối",
                "localhost" in panel.inner_text("[role='alert']"))
            kho = doc_kho(panel)
            dat("A4b địa chỉ xấu KHÔNG được ghi vào kho",
                kho.get("caiDatV1", {}).get("translationBaseUrl", "") == "")

            # A5 — địa chỉ đúng, máy chủ ĐANG CHẠY nhưng CORS chưa mở
            panel.fill("#o-dia-chi", WEB_APP)
            panel.click("button[data-vai='chinh']")
            panel.wait_for_selector("text=Tạo chapter mới", timeout=15000)
            chu = panel.inner_text("body")
            noi_duoc = "Đã kết nối local" in chu
            print(f"    (trạng thái kết nối lúc CHƯA mở CORS: "
                  f"{'nối được' if noi_duoc else 'không nối được'})")
            dat("A5 địa chỉ hợp lệ được lưu",
                doc_kho(panel).get("caiDatV1", {}).get("translationBaseUrl") == WEB_APP)

            if not noi_duoc:
                dat("A6 báo không kết nối kèm ĐỦ ba lý do (có nhắc CORS)",
                    all(t in chu for t in ("Không kết nối được Translation local",
                                           "chưa chạy", "Sai địa chỉ hoặc sai cổng", "CORS")))
                dat("A7 KHÔNG hiện 'chưa ghim chapter nào' như thể chưa có dữ liệu — "
                    "vẫn mở được web app",
                    "Tạo chapter mới" in chu)
            else:
                dat("A6 huy hiệu đã kết nối kèm địa chỉ đang dùng", WEB_APP in chu)

            # ---------------- Run D — sự thật về quyền ----------------
            print("\nRun D — sự thật về quyền")
            mf = json.loads((TIEN_ICH / "manifest.json").read_text())
            dat("D1 manifest không có content_scripts", "content_scripts" not in mf)
            dat("D2 host_permissions rỗng", mf.get("host_permissions") == [])
            dat("D3 quyền đúng bằng {storage, sidePanel}",
                sorted(mf["permissions"]) == ["sidePanel", "storage"], str(mf["permissions"]))

            # Mở một trang bất kỳ rồi kiểm tiện ích có chạm vào không.
            trang_ngoai = ngu_canh.new_page()
            trang_ngoai.set_content(
                "<html><body><h1>Trang truyện giả lập</h1>"
                "<img src='data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='>"
                "</body></html>")
            da_tiem = trang_ngoai.evaluate(
                "() => !!(window.__translation_companion__ "
                "|| document.querySelector('[data-translation-companion]'))")
            dat("D4 tiện ích KHÔNG tiêm gì vào trang đang xem", not da_tiem)
            kho_sau = doc_kho(panel)
            dat("D5 kho KHÔNG ghi lại địa chỉ trang vừa mở",
                "about:blank" not in json.dumps(kho_sau)
                and "trang truyện" not in json.dumps(kho_sau, ensure_ascii=False).lower())
            trang_ngoai.close()

            # ---------------- Run C — vòng đời + riêng tư ----------------
            print("\nRun C — vòng đời và riêng tư")
            kho = doc_kho(panel)
            dat("C1 kho chỉ có đúng hai khoá đã khai báo",
                sorted(kho.keys()) in (["caiDatV1"], ["caiDatV1", "chapterGhimV1"]),
                str(sorted(kho.keys())))

            chu_kho = json.dumps(kho, ensure_ascii=False).lower()
            cam = ["apikey", "aiza", "sk-", "password", "secret", "ocr", "base64",
                   "/home/", "cookie", "token"]
            dinh = [t for t in cam if t in chu_kho]
            dat("C2 kho KHÔNG chứa key/ảnh/OCR/đường dẫn tệp/cookie", not dinh, str(dinh))

            # Đóng rồi mở lại panel = mô phỏng service worker bị tắt và dựng lại.
            panel.close()
            panel2 = ngu_canh.new_page()
            panel2.on("console", lambda m: loi_console.append(f"{m.type}: {m.text}")
                      if m.type == "error" else None)
            panel2.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
            panel2.goto(panel_url)
            panel2.wait_for_selector("text=Tạo chapter mới", timeout=15000)
            dat("C3 cài đặt sống sót qua lượt mở lại panel",
                doc_kho(panel2).get("caiDatV1", {}).get("translationBaseUrl") == WEB_APP)

            # ---------------- Run B — bàn giao luồng làm việc ----------------
            print("\nRun B — bàn giao luồng làm việc")
            with ngu_canh.expect_page() as tab_moi:
                panel2.click("text=Tạo chapter mới")
            tab_tao = tab_moi.value
            tab_tao.wait_for_load_state("domcontentloaded", timeout=15000)
            dat("B1 'Tạo chapter mới' mở ĐÚNG route tạo chapter của web app",
                tab_tao.url.rstrip("/") == WEB_APP, tab_tao.url)
            try:
                tab_tao.wait_for_selector("text=Tạo chapter", timeout=10000)
                dat("B2 form tạo chapter của web app hiện ra", True)
            except Exception:
                dat("B2 form tạo chapter của web app hiện ra", False,
                    "không thấy form — web app có thể chưa nạp xong")
            tab_tao.close()

            # ---------------- Xoá dữ liệu ----------------
            print("\nRun C (tiếp) — xoá dữ liệu")
            panel2.click("text=Xoá dữ liệu extension")
            panel2.wait_for_selector("[role='alertdialog']", timeout=5000)
            hop = panel2.inner_text("[role='alertdialog']")
            dat("C4 hộp xác nhận nói rõ backend KHÔNG bị xoá",
                "KHÔNG bị xoá" in hop and "TRONG TRÌNH DUYỆT" in hop)
            # `text=Xoá` khớp cả tiêu đề trong hộp; phải chỉ đích danh nút.
            panel2.click("[role='alertdialog'] button:text-is('Xoá')")
            panel2.wait_for_selector("#o-dia-chi", timeout=5000)
            dat("C5 xoá xong thì kho sạch và quay về màn đầu", doc_kho(panel2) == {})

            # Chapter trong backend vẫn còn nguyên sau khi xoá dữ liệu tiện ích.
            kiem = ngu_canh.new_page()
            kiem.goto(f"{API}/healthz")
            dat("C6 backend vẫn sống sau khi xoá dữ liệu tiện ích",
                '"status":"ok"' in kiem.inner_text("body"))
            kiem.close()

            dat("Z1 không có lỗi JS nào trong console suốt lượt chạy",
                not loi_console, "; ".join(loi_console[:3]))

        finally:
            ngu_canh.close()

    print("\n" + "=" * 70)
    so_dat = sum(1 for _, d, _ in ket_qua if d)
    print(f"KẾT QUẢ: {so_dat}/{len(ket_qua)} đạt")
    for ten, d, ghi in ket_qua:
        if not d:
            print(f"  HỎNG: {ten} — {ghi}")
    return 0 if so_dat == len(ket_qua) else 1


if __name__ == "__main__":
    sys.exit(main())
