#!/usr/bin/env python3
"""Đo giao diện hướng chữ của E15 trên Chromium THẬT, với dữ liệu THẬT từ API.

Test thành phần dựng bằng dữ liệu tự bịa nên nó chỉ chứng minh code phản ứng đúng với khuôn
mình tưởng tượng. Tệp này bấm trên giao diện thật, đọc số thật từ backend.

    ../.venv/bin/python scripts/do_run_e15_ui.py <project_id>
"""
from __future__ import annotations

import subprocess
import sys

from playwright.sync_api import sync_playwright

GOC = "http://localhost:5174"
CHROME = "/home/coder/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
KQ: list[tuple[str, bool, str]] = []


def ghi(muc: str, dat: bool, chi_tiet: str = "") -> None:
    KQ.append((muc, dat, chi_tiet))
    print(f"  [{'ĐẠT ' if dat else 'HỎNG'}] {muc}" + (f" — {chi_tiet}" if chi_tiet else ""),
          flush=True)


def sql(cau: str) -> str:
    return subprocess.run(
        ["docker", "exec", "translation-db-1", "psql", "-U", "translation",
         "-d", "translation", "-tAc", cau],
        capture_output=True, text=True, timeout=60).stdout.strip()


def main() -> int:
    pid = sys.argv[1]
    # Ưu tiên trang CÓ vùng chưa xác định — trang toàn chữ ngang làm bộ lọc "cần kiểm tra"
    # được kiểm bằng phép so 0 == 0, tức là không kiểm gì cả.
    trang = sql(
        "select r.page_id::text from region_text_orientation ro "
        "join text_region r on r.id=ro.region_id join page pg on pg.id=r.page_id "
        f"where pg.project_id='{pid}' group by r.page_id "
        "order by count(*) filter (where ro.orientation<>'horizontal_ltr') desc, "
        "count(*) desc limit 1")
    if not trang:
        trang = sql(f"select pg.id from page pg where pg.project_id='{pid}' "
                    "order by pg.\"order\" limit 1")
    if not trang:
        print("không tìm thấy trang nào của chapter này")
        return 1

    # Số THẬT trong CSDL — giao diện phải khớp đúng những con số này.
    ngang = int(sql("select count(*) from region_text_orientation ro join text_region r "
                    f"on r.id=ro.region_id where r.page_id='{trang}' "
                    "and ro.orientation='horizontal_ltr'") or 0)
    chua_ro = int(sql("select count(*) from region_text_orientation ro join text_region r "
                      f"on r.id=ro.region_id where r.page_id='{trang}' "
                      "and ro.orientation='unknown'") or 0)
    tong_vung = int(sql(f"select count(*) from text_region where page_id='{trang}'") or 0)
    print(f"trang {trang[:8]} — CSDL: {tong_vung} vùng, {ngang} ngang, {chua_ro} chưa rõ\n")

    loi_console: list[str] = []
    with sync_playwright() as p:
        tr_duyet = p.chromium.launch(executable_path=CHROME, headless=True,
                                     args=["--no-sandbox"])
        trang_web = tr_duyet.new_page()
        trang_web.on("console", lambda m: loi_console.append(m.text)
                     if m.type == "error" else None)
        trang_web.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
        try:
            trang_web.goto(f"{GOC}/#page={trang}", wait_until="networkidle")
            trang_web.wait_for_selector(".danh-sach-vung", timeout=30000)
            trang_web.wait_for_selector(".the-tom-tat-huong", timeout=30000)

            # --- Thẻ tổng hợp phải khớp số CSDL ---
            the = trang_web.inner_text(".the-tom-tat-huong")
            ghi("U1 thẻ tổng hợp hướng chữ hiện ra", "Hướng chữ" in the)
            so_ngang = trang_web.inner_text(
                ".the-tom-tat-huong li.so-lieu:has-text('Chữ ngang') b")
            ghi("U2 số 'Chữ ngang' trên giao diện KHỚP CSDL", int(so_ngang) == ngang,
                f"giao diện={so_ngang}, CSDL={ngang}")
            so_chua_ro = trang_web.inner_text(
                ".the-tom-tat-huong li.so-lieu:has-text('Chưa xác định hướng') b")
            ghi("U3 số 'Chưa xác định hướng' KHỚP CSDL", int(so_chua_ro) == chua_ro,
                f"giao diện={so_chua_ro}, CSDL={chua_ro}")

            # --- Huy hiệu hướng chữ đứng RIÊNG, không gộp vào huy hiệu căn chữ ---
            hh = trang_web.locator(".danh-sach-vung .the-vung").first
            so_huy_hieu = hh.locator(".the-tt").count()
            ghi("U4 mỗi vùng có ÍT NHẤT 2 huy hiệu tách biệt (căn chữ + hướng chữ)",
                so_huy_hieu >= 2, f"{so_huy_hieu} huy hiệu")

            chu_ds = trang_web.inner_text(".danh-sach-vung")
            ghi("U5 nhãn hướng chữ hiện đúng tiếng Việt trên danh sách",
                "Chữ ngang" in chu_ds or "Chưa xác định hướng chữ" in chu_ds,
                chu_ds.replace("\n", " | ")[:120])

            # --- Không có nhãn hỏng nào lọt ra ---
            than = trang_web.inner_text("body")
            xau = [t for t in ("undefined", "[object Object]", "NaN",
                               "chưa được hỗ trợ") if t in than]
            ghi("U6 KHÔNG có nhãn hỏng / 'chưa được hỗ trợ' nào lọt ra giao diện",
                not xau, str(xau))

            # --- Bộ lọc ---
            ghi("U7 bộ lọc hướng chữ có đủ 5 mục",
                trang_web.locator(".loc-huong-chu .the-loc").count() == 5,
                str(trang_web.locator(".loc-huong-chu .the-loc").count()))

            truoc = trang_web.locator(".danh-sach-vung .the-vung").count()
            trang_web.click(".loc-huong-chu .the-loc:has-text('Chữ dọc')")
            trang_web.wait_for_timeout(300)
            sau = trang_web.locator(".danh-sach-vung .the-vung").count()
            ghi("U8 lọc 'Chữ dọc' lọc THẬT (dữ liệu này không có vùng dọc nên còn 0)",
                sau == 0 and truoc > 0, f"trước={truoc}, sau={sau}")
            ghi("U9 lọc rỗng thì nói rõ, không để bảng trắng im lặng",
                "Không có vùng nào khớp bộ lọc" in trang_web.inner_text(".danh-sach-vung"))

            trang_web.click(".loc-huong-chu .the-loc:has-text('Cần kiểm tra hướng chữ')")
            trang_web.wait_for_timeout(300)
            can_kiem = trang_web.locator(".danh-sach-vung .the-vung").count()
            ghi("U10 lọc 'Cần kiểm tra' bắt đúng số vùng chưa ready",
                can_kiem == tong_vung - ngang, f"giao diện={can_kiem}, kỳ vọng={tong_vung-ngang}")

            trang_web.click(".loc-huong-chu .the-loc:has-text('Tất cả')")
            trang_web.wait_for_timeout(300)

            # --- Khối giải thích của vùng đang chọn ---
            trang_web.locator(".danh-sach-vung .the-vung").first.click()
            trang_web.wait_for_selector(".the-huong-chu", timeout=10000)
            khoi = trang_web.inner_text(".the-huong-chu")
            ghi("U11 khối giải thích hướng chữ hiện ra kèm căn cứ", "Căn cứ" in khoi)
            ghi("U12 lý do hiện bằng tiếng Việt, KHÔNG hiện mã máy",
                "ocr_line_geometry" not in khoi and "ctd_geometry" not in khoi,
                khoi.replace("\n", " | ")[:160])

            # --- Lưới cột chữ: dữ liệu này không có vùng dọc ready nên PHẢI vắng mặt ---
            ghi("U13 không có vùng chữ dọc 'ready' ⇒ KHÔNG hiện công tắc lưới cột chữ",
                trang_web.locator("text=Hiện lưới cột chữ").count() == 0)

            ghi("Z1 không có lỗi JS nào trong console", not loi_console,
                "; ".join(loi_console[:3]))
        finally:
            tr_duyet.close()

    print("\n" + "=" * 70)
    dat = sum(1 for _, d, _ in KQ if d)
    print(f"KẾT QUẢ: {dat}/{len(KQ)} đạt")
    for ten, d, chi in KQ:
        if not d:
            print(f"  HỎNG: {ten} — {chi}")
    return 0 if dat == len(KQ) else 1


if __name__ == "__main__":
    sys.exit(main())
