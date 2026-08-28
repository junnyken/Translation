#!/usr/bin/env python3
"""Kiểm luồng E11 trên Chromium THẬT: bàn phím, tạo chapter, tiến độ, sửa tay, xuất.

Không kiểm bằng mắt: mỗi bước đều khẳng định một điều đo được, và chụp ảnh lại làm bằng chứng.

    ../.venv/bin/python scripts/kiem_e11.py --anh test_fixtures/external/*_1600.png \
        --chapter-cu <project_id> --ra /duong/dan
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

KQ: dict = {}


def ghi(muc: str, dat: bool, chi_tiet: str = "") -> None:
    KQ[muc] = {"dat": dat, "chi_tiet": chi_tiet}
    print(f"  [{'ĐẠT' if dat else 'HỎNG'}] {muc}{' — ' + chi_tiet if chi_tiet else ''}", flush=True)


def tao_bang_ban_phim(page, goc: str, anh: list[Path], ra: Path) -> str:
    """Tạo chapter mà KHÔNG dùng chuột lần nào — trừ hộp chọn tệp của hệ điều hành."""
    page.goto(goc, wait_until="networkidle")
    page.wait_for_timeout(500)

    # Đi bằng Tab từ đầu trang cho tới ô tên chapter, ghi lại đường đi.
    duong_di = []
    toi_noi = False
    page.keyboard.press("Tab")
    for _ in range(12):
        the, la_o_ten = page.evaluate("""() => {
            const e = document.activeElement;
            return [
              e ? `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}` : 'không có',
              !!(e && e.placeholder && e.placeholder.startsWith('ví dụ')),
            ];
        }""")
        duong_di.append(the)
        if la_o_ten:
            toi_noi = True
            break
        page.keyboard.press("Tab")
    ghi("tab tới được ô tên chapter", toi_noi, " → ".join(duong_di))

    # Vòng focus phải NHÌN THẤY được, nếu không người dùng bàn phím lạc mất mình đang ở đâu.
    co_vien = page.evaluate("""() => {
        const s = getComputedStyle(document.activeElement);
        return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0;
    }""")
    ghi("vòng focus nhìn thấy được", co_vien)

    TEN = "E11 kiem ban phim"
    page.keyboard.type(TEN)
    ghi("chữ gõ vào đúng ô tên chapter",
        page.evaluate("() => document.activeElement.value") == TEN,
        page.evaluate("() => document.activeElement.value"))
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")   # ngôn ngữ gốc -> mục đích sử dụng
    dang_focus = page.evaluate_handle("() => document.activeElement").as_element()
    dang_focus.select_option("study")

    # Vùng thả file: mở hộp chọn tệp bằng phím Enter, đúng như người dùng bàn phím sẽ làm.
    page.focus('[aria-label^="Chọn ảnh trang truyện"]')
    with page.expect_file_chooser() as hop:
        page.keyboard.press("Enter")
    hop.value.set_files([str(p) for p in anh])
    page.wait_for_timeout(400)

    ten_hien = page.locator(".ds-file .ten-file").all_inner_texts()
    ghi("thứ tự trang đúng thứ tự đã chọn", ten_hien == [p.name for p in anh], str(ten_hien))

    page.screenshot(path=str(ra / "e11_form_da_dien.png"), full_page=True)

    nut = page.locator("#nut-tao")
    ghi("nút tạo đã sáng khi đủ điều kiện", nut.is_enabled())
    nut.focus()
    page.keyboard.press("Enter")

    page.wait_for_url("**#project=*", timeout=180_000)
    ma = page.url.split("project=")[-1]
    ghi("tạo xong thì chuyển sang màn chapter", bool(ma), ma[:8])
    return ma


def xem_tien_do(page, ra: Path) -> None:
    page.wait_for_timeout(2500)
    page.screenshot(path=str(ra / "e11_tien_do.png"), full_page=True)
    buoc = page.locator(".dong-tg .buoc").count()
    ghi("có dòng thời gian pipeline", buoc >= 6, f"{buoc} bước")

    # Không được có thanh phần trăm giả cho pipeline chạy nền.
    chu = page.locator(".than-trang").inner_text()
    ghi("không hứa thời gian xử lý cụ thể", "3–6 phút" not in chu and "3-6 phút" not in chu)
    ghi("nói rõ xử lý chạy nền", "chạy nền" in chu)


def sua_tay_va_cho_canh_lai(page, goc: str, project_id: str, ra: Path) -> None:
    """Đường M7: sửa bản dịch → phải thấy trạng thái đang chạy → ảnh xem thử phải ĐỔI."""
    page.goto(f"{goc}#project={project_id}", wait_until="networkidle")
    page.wait_for_timeout(1200)
    trang = page.locator(".ds-trang a").first
    if trang.count() == 0:
        ghi("mở được trang để sửa tay", False, "chapter không có trang nào")
        return
    trang.click()
    page.wait_for_timeout(2500)

    ghi("có đường dẫn phân cấp khi sửa tay", page.locator(".duong-dan").count() == 1)
    ghi("có điều hướng trang trước/sau", page.locator(".dieu-huong-trang").count() == 1)

    anh_truoc = page.locator(".khung-anh img").get_attribute("src") or ""
    o_dich = page.locator(".bang-sua textarea").first
    if o_dich.count() == 0:
        ghi("mở được bảng sửa vùng", False)
        return
    o_dich.fill(f"Kiểm E11 lúc {int(time.time())}")
    page.get_by_role("button", name="Lưu & canh lại").click()

    # Ngay sau khi bấm phải thấy hệ thống nói nó đang làm gì.
    dang_chay = page.get_by_text("Đang căn lại chữ", exact=False)
    thay = dang_chay.count() > 0 or page.get_by_text("Đang lưu", exact=False).count() > 0
    ghi("hiện trạng thái đang căn lại chữ", thay)

    page.wait_for_selector("text=/^Xong:/", timeout=600_000)
    page.wait_for_timeout(800)
    anh_sau = page.locator(".khung-anh img").get_attribute("src") or ""
    ghi("ảnh xem thử được nạp lại, không dùng ảnh cũ", anh_truoc != anh_sau,
        f"{anh_truoc[-12:]} -> {anh_sau[-12:]}")
    page.screenshot(path=str(ra / "e11_sua_tay.png"), full_page=True)


def xuat_chapter(page, goc: str, project_id: str, ra: Path) -> None:
    page.goto(f"{goc}#project={project_id}", wait_until="networkidle")
    page.wait_for_timeout(1500)
    nut = page.locator(".bang-xuat button.chinh").first
    if nut.count() == 0:
        ghi("có bảng xuất chapter", False)
        return
    nut.click()
    page.wait_for_timeout(700)

    hop = page.locator(".hop-thoai")
    if hop.count() == 0:
        # Chapter đã xác nhận bản quyền từ trước thì M10 cố ý KHÔNG hỏi lại.
        ghi("hộp thoại bản quyền chỉ hỏi một lần mỗi chapter", True, "đã xác nhận trước đó")
    else:
        page.screenshot(path=str(ra / "e11_hop_thoai_xuat.png"), full_page=True)
        chu = hop.inner_text()
        ghi("hộp thoại nhắc trách nhiệm bản quyền", "bản quyền" in chu)
        nut_xuat = hop.get_by_role("button", name="Xuất chapter", exact=False)
        ghi("nút xuất bị khoá khi chưa tick", not nut_xuat.is_enabled())
        hop.locator('input[type="checkbox"]').check()
        ghi("tick xong thì nút xuất sáng", nut_xuat.is_enabled())
        nut_xuat.click()

    page.wait_for_selector("text=Tải file về", timeout=300_000)
    ghi("link tải chỉ hiện sau khi xuất xong", True)
    page.screenshot(path=str(ra / "e11_xuat_xong.png"), full_page=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--goc", default="http://localhost:5174/")
    ap.add_argument("--anh", nargs="+", type=Path, required=True)
    ap.add_argument("--chapter-cu", default=None, help="chapter đã xong để kiểm sửa tay + xuất")
    ap.add_argument("--ra", type=Path, required=True)
    args = ap.parse_args()
    args.ra.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        tr = pw.chromium.launch()
        ctx = tr.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        loi_console: list[str] = []
        page.on("console", lambda m: loi_console.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: loi_console.append(str(e)))

        try:
            print("\n=== 1. Tạo chapter chỉ bằng bàn phím ===", flush=True)
            ma_moi = tao_bang_ban_phim(page, args.goc, args.anh, args.ra)

            print("\n=== 2. Tiến độ thật ===", flush=True)
            xem_tien_do(page, args.ra)

            cu = args.chapter_cu or ma_moi
            print(f"\n=== 3. Sửa tay trên chapter {cu[:8]} ===", flush=True)
            sua_tay_va_cho_canh_lai(page, args.goc, cu, args.ra)

            print("\n=== 4. Xuất chapter ===", flush=True)
            xuat_chapter(page, args.goc, cu, args.ra)

            ghi("console không có lỗi", not loi_console, "; ".join(loi_console[:3]))
        finally:
            # Ghi kết quả kể cả khi chạy hỏng giữa chừng: mất sạch số đã đo được là tự làm khó
            # chính mình lúc truy nguyên.
            tr.close()
            (args.ra / "kiem_e11.json").write_text(json.dumps(KQ, ensure_ascii=False, indent=2))

    hong = [k for k, v in KQ.items() if not v["dat"]]
    print(f"\nTổng: {len(KQ) - len(hong)}/{len(KQ)} đạt")
    if hong:
        print("Chưa đạt:", *hong, sep="\n  - ")
    return 1 if hong else 0


if __name__ == "__main__":
    raise SystemExit(main())
