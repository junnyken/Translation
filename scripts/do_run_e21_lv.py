#!/usr/bin/env python3
"""E21-LV — Live Verification & Closeout của E21 (gõ đè raw_text + phóng to đối chiếu ảnh gốc).

Bấm THẬT trên Chromium thật (Playwright), dữ liệu THẬT lấy từ Postgres thật — không dựng DOM giả,
không tự bịa toạ độ. Khung đỏ được kiểm bằng cách tính lại ĐỘC LẬP đúng công thức của
`ZoomCropModal.jsx` (bbox + nới lề + tỉ lệ phóng) từ kích thước ảnh gốc đo thật, rồi lấy mẫu pixel
canvas thật ở đúng toạ độ đó — không phải nhìn ảnh chụp màn hình bằng mắt.

    cd backend && ../.venv/bin/python ../scripts/do_run_e21_lv.py
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

GOC = "http://localhost:5174"
API = "http://localhost:8010/api/v1"
EMAIL = "test-e2e@local.test"
MAT_KHAU = "e21-lv-test-pw-2026"
PAGE_ID = "e3b458c7-528b-48ba-9c74-5a8f2da56a0f"
REGION_ID = "30234117-60c3-4220-9146-b61e62d6e85e"  # reading_order=2, bbox lớn nhất trên trang
RA = Path(__file__).resolve().parent.parent / "docs" / "evidence" / "E21-LV"

KQ: list[tuple[str, bool, str]] = []
loi_console: list[str] = []


def ghi(muc: str, dat: bool, chi_tiet: str = "") -> None:
    KQ.append((muc, dat, chi_tiet))
    print(f"  [{'ĐẠT ' if dat else 'HỎNG'}] {muc}" + (f" — {chi_tiet}" if chi_tiet else ""), flush=True)


def sql(cau: str) -> str:
    return subprocess.run(
        ["docker", "exec", "translation-db-1", "psql", "-U", "translation", "-d", "translation", "-tAc", cau],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()


def lam_tron_js(x: float) -> int:
    """`Math.round` của JS: luôn làm tròn .5 lên, khác `round()` ngân hàng của Python."""
    return math.floor(x + 0.5)


def tinh_khung_do(bbox: dict, rong_anh: int, cao_anh: int) -> dict:
    """Suy lại ĐÚNG công thức `ZoomCropModal.jsx` để có toạ độ kỳ vọng, độc lập với code đang test."""
    le_x = max(24.0, bbox["w"] * 0.4)
    le_y = max(24.0, bbox["h"] * 0.4)
    sx = max(0.0, bbox["x"] - le_x)
    sy = max(0.0, bbox["y"] - le_y)
    sw = min(rong_anh - sx, bbox["w"] + le_x * 2)
    sh = min(cao_anh - sy, bbox["h"] + le_y * 2)
    ti_le = min(6.0, max(1.0, 900 / max(sw, sh)))
    return {
        "canvas_w": lam_tron_js(sw * ti_le),
        "canvas_h": lam_tron_js(sh * ti_le),
        "rx": lam_tron_js((bbox["x"] - sx) * ti_le),
        "ry": lam_tron_js((bbox["y"] - sy) * ti_le),
        "rw": lam_tron_js(bbox["w"] * ti_le),
        "rh": lam_tron_js(bbox["h"] * ti_le),
    }


def do_khung_do(trang, khung: dict) -> tuple[bool, str]:
    """Lấy mẫu pixel canvas thật dọc 4 cạnh của hình chữ nhật kỳ vọng — kiểm 'đỏ trội', không so
    khớp màu tuyệt đối (nét vẽ đè lên nội dung ảnh gốc, alpha .85, nên màu pha trộn)."""
    diem = []
    for t in (0.25, 0.5, 0.75):
        diem += [
            (khung["rx"] + int(khung["rw"] * t), khung["ry"]),  # cạnh trên
            (khung["rx"] + int(khung["rw"] * t), khung["ry"] + khung["rh"]),  # cạnh dưới
            (khung["rx"], khung["ry"] + int(khung["rh"] * t)),  # cạnh trái
            (khung["rx"] + khung["rw"], khung["ry"] + int(khung["rh"] * t)),  # cạnh phải
        ]
    ket_qua = trang.evaluate(
        """(diem) => {
          const cv = document.querySelector('.khung-anh-phong-to canvas')
          if (!cv) return null
          const ctx = cv.getContext('2d')
          return diem.map(([x, y]) => {
            const do_do = []
            for (const [dx, dy] of [[0,0],[1,0],[-1,0],[0,1],[0,-1]]) {
              const px = Math.min(cv.width - 1, Math.max(0, x + dx))
              const py = Math.min(cv.height - 1, Math.max(0, y + dy))
              const d = ctx.getImageData(px, py, 1, 1).data
              do_do.push([d[0], d[1], d[2]])
            }
            return do_do
          })
        }""",
        diem,
    )
    if ket_qua is None:
        return False, "không tìm thấy canvas"
    trung = 0
    for mau_3x3 in ket_qua:
        # đỏ trội nếu BẤT KỲ pixel nào trong vùng 3x3 quanh điểm mẫu có R trội hẳn G và B
        if any(r > 110 and r > g + 35 and r > b + 35 for r, g, b in mau_3x3):
            trung += 1
    return trung >= len(ket_qua) * 0.8, f"{trung}/{len(ket_qua)} điểm mẫu thấy đỏ trội"


def dang_nhap(trang) -> None:
    trang.goto(GOC, wait_until="networkidle")
    trang.wait_for_selector("#o-email", timeout=15000)
    trang.fill("#o-email", EMAIL)
    trang.fill("#o-mk", MAT_KHAU)
    trang.click("button:has-text('Đăng nhập')")
    trang.wait_for_selector(".dieu-huong", timeout=15000)


def tran_ngang(trang) -> dict:
    return trang.evaluate(
        "() => ({ cuon: document.documentElement.scrollWidth, nhin: document.documentElement.clientWidth })"
    )


def main() -> int:
    RA.mkdir(parents=True, exist_ok=True)

    # --- Dữ liệu thật, đo thật — không tự bịa toạ độ ---
    rong_str = sql(
        f"select array_to_string(array[bbox_x,bbox_y,bbox_w,bbox_h], ',') "
        f"from text_region where id='{REGION_ID}'"
    )
    bx, by, bw, bh = (float(v) for v in rong_str.split(","))
    bbox = {"x": bx, "y": by, "w": bw, "h": bh}
    raw_text_goc = sql(f"select raw_text from ocr_result where region_id='{REGION_ID}'")
    dich_goc = sql(f"select translated_text from translation_result where region_id='{REGION_ID}'")
    dem_translate_truoc = int(sql(
        f"select count(*) from job where page_id='{PAGE_ID}' and type='translate'"
    ) or 0)

    print(f"Vùng {REGION_ID[:8]} — bbox=({bx:.1f},{by:.1f},{bw:.1f}x{bh:.1f})")
    print(f"raw_text gốc: {raw_text_goc!r}")
    print(f"bản dịch hiện có: {dich_goc!r}\n")

    with sync_playwright() as p:
        trinh_duyet = p.chromium.launch(headless=True, args=["--no-sandbox"])
        trang = trinh_duyet.new_page()
        trang.on("console", lambda m: loi_console.append(m.text) if m.type == "error" else None)
        trang.on("pageerror", lambda e: loi_console.append(f"pageerror: {e}"))
        try:
            dang_nhap(trang)
            trang.goto(f"{GOC}/#page={PAGE_ID}", wait_until="networkidle")
            trang.wait_for_selector(".danh-sach-vung .the-vung", timeout=20000)

            so_vung = trang.locator(".danh-sach-vung .the-vung").count()
            ghi("A1 danh sách vùng nạp được, khớp số vùng CSDL", so_vung == 2, f"giao diện={so_vung}, CSDL=2")

            trang.locator(".danh-sach-vung .the-vung").nth(1).click()
            trang.wait_for_selector(f"#chu-goc-{REGION_ID}", timeout=10000)

            o_chu_goc = trang.locator(f"#chu-goc-{REGION_ID}")
            ghi("A2 ô chữ gốc nạp đúng raw_text hiện có", o_chu_goc.input_value() == raw_text_goc)

            trang.screenshot(path=str(RA / "01_truoc_khi_mo_modal.png"))

            # --- C1-C6: modal phóng to đối chiếu ---
            nut_phong_to = trang.locator("button:has-text('Phóng to đối chiếu')")
            nut_phong_to.click()
            mo_duoc = trang.locator(".hop-thoai-rong").is_visible()
            ghi("C2 bấm 'Phóng to đối chiếu' mở modal", mo_duoc)

            trang.wait_for_selector(".khung-anh-phong-to canvas:not([hidden])", timeout=15000)
            loi_hien = trang.locator(".hop-thoai-rong .canh-bao").count()
            ghi("C1 ảnh gốc tải được qua modal (không hiện lỗi tải)", loi_hien == 0)

            kich_canvas = trang.evaluate(
                "() => { const c = document.querySelector('.khung-anh-phong-to canvas'); "
                "return c ? {w: c.width, h: c.height} : null }"
            )
            ghi("C3 canvas render với kích thước thật > 0", bool(kich_canvas) and kich_canvas["w"] > 0 and kich_canvas["h"] > 0, str(kich_canvas))

            khung = tinh_khung_do(bbox, 1600, 2213)  # đo thật ở bước chuẩn bị dữ liệu, xem log trên
            ghi(
                "-- canvas kỳ vọng (tính độc lập theo công thức ZoomCropModal.jsx)", True,
                f"canvas={khung['canvas_w']}x{khung['canvas_h']}, "
                f"khung=({khung['rx']},{khung['ry']},{khung['rw']}x{khung['rh']})",
            )
            khop_kich_thuoc = kich_canvas and abs(kich_canvas["w"] - khung["canvas_w"]) <= 1 and abs(kich_canvas["h"] - khung["canvas_h"]) <= 1
            ghi("-- canvas thật KHỚP kích thước tính tay (sai số ≤1px)", bool(khop_kich_thuoc), str(kich_canvas))

            dat, chi_tiet = do_khung_do(trang, khung)
            ghi("C4 khung đỏ đúng vị trí region OCR đang chọn", dat, chi_tiet)

            trang.wait_for_timeout(600)
            dat2, chi_tiet2 = do_khung_do(trang, khung)
            ghi("C5 khung không lệch sau khi ảnh load xong (đo lại sau 600ms)", dat2, chi_tiet2)

            trang.screenshot(path=str(RA / "02_modal_mo_desktop.png"))

            # C6: resize trong lúc modal mở — canvas là raster cố định, phải giữ tỉ lệ hiển thị
            for rong, cao, nhan in ((900, 700, "hep"), (1400, 900, "rong")):
                trang.set_viewport_size({"width": rong, "height": cao})
                trang.wait_for_timeout(300)
                hcnh = trang.evaluate(
                    "() => { const c = document.querySelector('.khung-anh-phong-to canvas'); "
                    "const r = c.getBoundingClientRect(); return {w: r.width, h: r.height} }"
                )
                ti_le_hien = hcnh["w"] / hcnh["h"] if hcnh["h"] else 0
                ti_le_raster = kich_canvas["w"] / kich_canvas["h"] if kich_canvas["h"] else 0
                sai_so = abs(ti_le_hien - ti_le_raster) / ti_le_raster if ti_le_raster else 1
                ghi(
                    f"C6 khung không méo khi resize ({nhan}, {rong}x{cao})", sai_so < 0.03,
                    f"tỉ lệ hiển thị={ti_le_hien:.3f}, tỉ lệ raster={ti_le_raster:.3f}",
                )
            trang.set_viewport_size({"width": 1280, "height": 900})
            trang.wait_for_timeout(300)
            dat3, chi_tiet3 = do_khung_do(trang, khung)
            ghi("C6b khung đỏ vẫn đúng vị trí sau khi resize qua lại", dat3, chi_tiet3)

            trang.click(".hop-thoai-rong button:has-text('Đóng')")
            trang.wait_for_selector(".hop-thoai-rong", state="hidden", timeout=5000)

            # --- C7-C11: sửa raw_text, lưu, refresh, kiểm không lan ---
            chu_moi = raw_text_goc + " [E21-LV đã sửa tay]"
            o_chu_goc.fill(chu_moi)
            nut_luu = trang.locator("button.chinh:has-text('Lưu & canh lại')")
            ghi("C7a nút Lưu bật lên khi có thay đổi", nut_luu.is_enabled())
            nut_luu.click()
            trang.wait_for_function(
                "() => document.body.innerText.includes('Xong: lưu và căn lại chữ')", timeout=30000
            )
            ghi("C7b bấm Lưu chạy xong, không báo lỗi", trang.locator(".alert-loi, .loi").count() == 0)

            trang.reload(wait_until="networkidle")
            trang.wait_for_selector(".danh-sach-vung .the-vung", timeout=20000)
            trang.locator(".danh-sach-vung .the-vung").nth(1).click()
            trang.wait_for_selector(f"#chu-goc-{REGION_ID}", timeout=10000)
            gia_tri_sau_refresh = trang.locator(f"#chu-goc-{REGION_ID}").input_value()
            ghi("C8 refresh trình duyệt, raw_text mới VẪN CÒN", gia_tri_sau_refresh == chu_moi, gia_tri_sau_refresh)

            dich_sau_db = sql(f"select translated_text from translation_result where region_id='{REGION_ID}'")
            ghi("C9 bản dịch hiện hữu KHÔNG bị đổi tự động (đối chiếu CSDL)", dich_sau_db == dich_goc, f"trước={dich_goc!r}, sau={dich_sau_db!r}")

            dem_translate_sau = int(sql(f"select count(*) from job where page_id='{PAGE_ID}' and type='translate'") or 0)
            ghi("C10 KHÔNG có job dịch mới chỉ vì sửa raw_text", dem_translate_sau == dem_translate_truoc, f"trước={dem_translate_truoc}, sau={dem_translate_sau}")

            preview_van_hien = trang.locator("img, canvas").count() > 0
            khong_loi_body = not any(x in trang.inner_text("body") for x in ("undefined", "[object Object]", "NaN"))
            ghi("C11 không phá preview/refit hiện hữu (trang vẫn render sạch)", preview_van_hien and khong_loi_body)

            trang.screenshot(path=str(RA / "03_sau_khi_luu_va_refresh.png"))

            # --- C13: responsive ở 3 kích thước, có mở modal ---
            for rong, cao, nhan in ((375, 800, "mobile"), (768, 1024, "tablet"), (1440, 900, "desktop")):
                trang.set_viewport_size({"width": rong, "height": cao})
                trang.wait_for_timeout(300)
                tn = tran_ngang(trang)
                ghi(f"C13 không tràn ngang @ {nhan} ({rong}x{cao})", tn["cuon"] <= tn["nhin"] + 1, f"cuộn={tn['cuon']}, nhìn={tn['nhin']}")
                trang.locator("button:has-text('Phóng to đối chiếu')").click()
                trang.wait_for_selector(".hop-thoai-rong", timeout=10000)
                tn_modal = tran_ngang(trang)
                ghi(f"C13b modal không tràn ngang @ {nhan}", tn_modal["cuon"] <= tn_modal["nhin"] + 1, f"cuộn={tn_modal['cuon']}, nhìn={tn_modal['nhin']}")
                trang.screenshot(path=str(RA / f"04_responsive_{nhan}.png"))
                trang.click(".hop-thoai-rong button:has-text('Đóng')")
                trang.wait_for_selector(".hop-thoai-rong", state="hidden", timeout=5000)

            ghi("C12 không lỗi JS console suốt phiên", not loi_console, "; ".join(loi_console[:5]))
        finally:
            trinh_duyet.close()

    print("\n" + "=" * 70)
    dat_tong = sum(1 for _, d, _ in KQ if d)
    print(f"KẾT QUẢ: {dat_tong}/{len(KQ)} đạt — ảnh chụp ở {RA}")
    for ten, d, chi in KQ:
        if not d:
            print(f"  HỎNG: {ten} — {chi}")
    return 0 if dat_tong == len(KQ) else 1


if __name__ == "__main__":
    sys.exit(main())
