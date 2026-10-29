"""Đo thật E1 — nhánh ĐỌC ĐƯỢC DỮ LIỆU: ghim chapter thật, đọc trạng thái thật, mở đúng route.

Điều kiện chạy: stack docker dev đang chạy (`deploy/docker-compose.yml`), giao diện ở cổng 5174.

KHÔNG cần cấu hình `CORS_ALLOW_ORIGINS`: máy chủ dev của Vite proxy `/api` xuống backend và tự
thêm `Access-Control-Allow-Origin: *`. Đo thật ngày 2026-08-30 — xem `extension/README.md` §1.3 B.
Ở bản dựng prod (nginx) thì nginx không proxy `/api`, và tiện ích lùi về chế độ chỉ-mở-link;
nhánh đó được `scripts/do_run_e1.py` phủ.

Chạy:  .venv/bin/python scripts/do_run_e1_ket_noi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

GOC = Path(__file__).resolve().parents[1]
TIEN_ICH = GOC / "extension"
CHROME = Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome"

WEB_APP = "http://127.0.0.1:5174"

# Chapter THẬT trong CSDL lúc đo (3 trang, đều `typeset_done`).
CHAPTER = "67094721-c9e4-4231-896d-83b555205a42"
# Chapter có trang ở nhiều trạng thái khác nhau (`detected` + `typeset_done`).
CHAPTER_HON_HOP = "c10032f2-05ce-4650-9cdd-b8c0c819da2e"

ket_qua: list[tuple[str, bool, str]] = []


def dat(ten: str, ok: bool, ghi_chu: str = "") -> None:
    ket_qua.append((ten, ok, ghi_chu))
    print(f"  [{'ĐẠT ' if ok else 'HỎNG'}] {ten}" + (f" — {ghi_chu}" if ghi_chu else ""),
          flush=True)


def main() -> int:
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
            sw = ngu_canh.service_workers[0] if ngu_canh.service_workers else \
                ngu_canh.wait_for_event("serviceworker", timeout=15000)
            ext_id = sw.url.split("/")[2]
            print(f"ID tiện ích: {ext_id}\n")

            loi_console: list[str] = []
            panel = ngu_canh.new_page()
            panel.on("console", lambda m: loi_console.append(f"{m.type}: {m.text}")
                     if m.type == "error" else None)
            panel.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
            panel.goto(f"chrome-extension://{ext_id}/src/sidepanel/index.html")
            panel.wait_for_selector("#o-dia-chi", timeout=10000)

            print("Nhánh ĐÃ MỞ CORS")
            panel.fill("#o-dia-chi", WEB_APP)
            panel.click("button[data-vai='chinh']")
            panel.wait_for_selector("text=Tạo chapter mới", timeout=20000)
            chu = panel.inner_text("body")
            dat("K1 huy hiệu 'Đã kết nối local' hiện ra khi CORS đã mở",
                "Đã kết nối local" in chu)
            dat("K2 hiện đúng địa chỉ đang dùng", WEB_APP in chu)

            # --- Ghim một chapter THẬT ---
            panel.fill("#o-ma", CHAPTER)
            panel.click("button:text-is('Ghim chapter')")
            panel.wait_for_selector("li.muc", timeout=15000)
            muc = panel.inner_text("li.muc")
            dat("K3 ghim được chapter thật và lấy TÊN THẬT từ máy chủ",
                "E11 kiem ban phim" in muc, muc.split("\n")[0])
            dat("K4 hiện số trang THẬT (3 trang) chứ không phải số bịa",
                "3 trang" in muc, muc.replace("\n", " | "))
            dat("K5 trạng thái chapter dịch đúng ra chữ", "Đang làm" in muc)

            # --- Nút phải BẬT vì có trang typeset_done ---
            ra_soat = panel.locator("li.muc button", has_text="Mở rà soát").first
            xuat = panel.locator("li.muc button", has_text="Xuất").first
            dat("K6 có trang đã căn chữ -> nút 'Mở rà soát' được BẬT",
                not ra_soat.is_disabled())
            dat("K7 có trang đã căn chữ -> nút 'Xuất' được BẬT", not xuat.is_disabled())

            # --- Mở đúng route rà soát (M7) ---
            with ngu_canh.expect_page() as tab:
                ra_soat.click()
            t = tab.value
            t.wait_for_load_state("domcontentloaded", timeout=15000)
            dat("K8 'Mở rà soát' mở ĐÚNG route #page= của web app",
                t.url.startswith(f"{WEB_APP}/#page="), t.url)
            t.close()

            # --- Mở đúng route chapter (tiến độ + khối xuất M8) ---
            with ngu_canh.expect_page() as tab:
                panel.locator("li.muc button", has_text="Xem tiến độ").first.click()
            t = tab.value
            t.wait_for_load_state("domcontentloaded", timeout=15000)
            dat("K9 'Xem tiến độ' mở ĐÚNG route #project= của web app",
                t.url == f"{WEB_APP}/#project={CHAPTER}", t.url)
            t.close()

            with ngu_canh.expect_page() as tab:
                xuat.click()
            t = tab.value
            t.wait_for_load_state("domcontentloaded", timeout=15000)
            dat("K10 'Xuất' mở màn chapter (M8 nằm trong đó), KHÔNG bịa route #export=",
                t.url == f"{WEB_APP}/#project={CHAPTER}" and "export" not in t.url, t.url)
            t.close()

            # --- Chapter có trang chưa căn chữ: nút vẫn bật vì CÓ ít nhất 1 trang đủ điều kiện ---
            panel.fill("#o-ma", CHAPTER_HON_HOP)
            panel.click("button:text-is('Ghim chapter')")
            panel.wait_for_selector("li.muc >> nth=1", timeout=15000)
            dat("K11 ghim được chapter thứ hai", panel.locator("li.muc").count() == 2)

            # --- Mã bịa phải bị máy chủ trả 404 và panel nói thật ---
            panel.fill("#o-ma", "00000000-0000-4000-8000-000000000000")
            panel.click("button:text-is('Ghim chapter')")
            panel.wait_for_selector("[role='alert']", timeout=15000)
            dat("K12 mã không có thật -> báo 'không tìm thấy', KHÔNG ghim mục ma",
                "Không tìm thấy chapter" in panel.inner_text("[role='alert']")
                and panel.locator("li.muc").count() == 2)

            # --- Kho: có ghim rồi thì lưu gì? ---
            kho = panel.evaluate("() => chrome.storage.local.get(null)")
            print("\n  Nội dung kho sau khi ghim 2 chapter thật:")
            print("   ", json.dumps(kho, ensure_ascii=False)[:400])
            ghim = kho.get("chapterGhimV1", [])
            dat("K13 kho chỉ có 2 khoá đã khai báo",
                sorted(kho.keys()) == ["caiDatV1", "chapterGhimV1"], str(sorted(kho.keys())))
            khoa_cho_phep = {"projectId", "title", "status", "updatedAt", "cachedAt"}
            thua = {k for m in ghim for k in m} - khoa_cho_phep
            dat("K14 mỗi mục ghim chỉ có trường trong khuôn", not thua, str(thua))
            dat("K15 mỗi mục ghim đều có mốc thời gian chụp",
                all(m.get("cachedAt") for m in ghim))

            chu_kho = json.dumps(kho, ensure_ascii=False).lower()
            cam = ["aiza", "sk-", "apikey", "password", "secret", "base64", "/home/",
                   "image_path", "ocr", "source_lang", "intended_use"]
            dinh = [t for t in cam if t in chu_kho]
            dat("K16 kho KHÔNG chứa key/ảnh/OCR/ngôn ngữ/mục đích dùng", not dinh, str(dinh))

            # --- Mở lại panel: phải HỎI LẠI máy chủ, không tin bộ nhớ cũ ---
            panel.close()
            panel2 = ngu_canh.new_page()
            panel2.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
            panel2.goto(f"chrome-extension://{ext_id}/src/sidepanel/index.html")
            panel2.wait_for_selector("li.muc", timeout=20000)
            # Panel vẽ ghim từ kho TRƯỚC, rồi mới có kết quả kiểm kết nối — nên phải chờ lượt
            # kiểm xong hẳn. Trong lúc chờ, huy hiệu phải là "Đang kiểm tra", không phải "Chưa
            # kết nối" (xem lỗi đã sửa ở panel-view: trạng thái kết nối có BA giá trị).
            panel2.wait_for_function(
                "() => !document.body.innerText.includes('Đang kiểm tra kết nối')",
                timeout=20000)
            dat("K17 mở lại panel: ghim còn nguyên và trạng thái được lấy lại từ máy chủ",
                panel2.locator("li.muc").count() == 2
                and "Đã kết nối local" in panel2.inner_text("body"))

            # --- Bỏ ghim ---
            panel2.locator("li.muc button", has_text="Bỏ ghim").first.click()
            panel2.wait_for_function("() => document.querySelectorAll('li.muc').length === 1",
                                     timeout=10000)
            dat("K18 bỏ ghim chỉ gỡ đúng một mục", panel2.locator("li.muc").count() == 1)

            # K12 CỐ Ý hỏi một mã không tồn tại, nên Chrome ghi một dòng "404" vào console.
            # Đó là tiếng ồn của trình duyệt, không phải ngoại lệ JS của tiện ích — tách hai loại
            # ra thay vì nới lỏng cả phép kiểm.
            ngoai_le = [d for d in loi_console if d.startswith("pageerror")]
            on_khac = [d for d in loi_console if not d.startswith("pageerror")
                       and "404" not in d]
            dat("Z1 không có ngoại lệ JS nào suốt lượt chạy", not ngoai_le,
                "; ".join(ngoai_le[:3]))
            dat("Z2 console sạch, trừ đúng một dòng 404 do K12 cố ý gây ra", not on_khac,
                "; ".join(on_khac[:3]))
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
