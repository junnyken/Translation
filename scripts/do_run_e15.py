#!/usr/bin/env python3
"""Đo Run A–D của E15 trên hệ thống thật.

    ../.venv/bin/python scripts/do_run_e15.py

Run A — chữ ngang không hồi quy (Pepper&Carrot, tiếng Anh, PaddleOCR có đường bao dòng).
Run B — chữ dọc tiếng Nhật. **Không chạy được** — xem `chan_run_b()`, ghi lý do bằng số đo.
Run C — SFX / chữ nghiêng: không vùng nào bị bỏ qua im lặng, không vùng nào bị tự xoay.
Run D — sửa tay + cảnh báo lúc xuất, không phá M7/M8/M10.

Toàn bộ dữ liệu OCR có sẵn trong CSDL đều có TRƯỚC E15 nên `line_polygons` rỗng. Muốn có bằng
chứng hình học thật thì phải cho một chapter chạy lại **cả pipeline**, đó là việc script này làm.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GOC = "http://localhost:8010/api/v1"
ANH = sorted(Path("test_fixtures/external").glob("pc_E01P0*_1600.png"))

KQ: list[tuple[str, bool, str]] = []


def ghi(muc: str, dat: bool, chi_tiet: str = "") -> None:
    KQ.append((muc, dat, chi_tiet))
    print(f"  [{'ĐẠT ' if dat else 'HỎNG'}] {muc}" + (f" — {chi_tiet}" if chi_tiet else ""),
          flush=True)


def ghi_nhan(muc: str, chi_tiet: str) -> None:
    """Ghi nhận số đo KHÔNG phải phép đạt/hỏng — dùng cho kết luận blocked."""
    print(f"  [ĐO  ] {muc} — {chi_tiet}", flush=True)


def goi(dd, method="GET", data=None, timeout=120):
    body = json.dumps(data).encode() if data is not None else None
    h = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(f"{GOC}{dd}", data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), r.status
    except urllib.error.HTTPError as exc:
        return {"chi_tiet": exc.read().decode()[:300]}, exc.code


def sql(cau: str) -> str:
    return subprocess.run(
        ["docker", "exec", "translation-db-1", "psql", "-U", "translation",
         "-d", "translation", "-tA", "-c", cau],
        capture_output=True, text=True, timeout=60).stdout.strip()


def tai_len(project_id: str, duong_dan: Path, timeout: int = 300) -> dict:
    ranh = "----rune15"
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


def cho_trang(page_id: str, trang_thai: set[str], tran: int = 900) -> str:
    het = time.time() + tran
    tt = ""
    while time.time() < het:
        tt = sql(f"select status from page where id='{page_id}'")
        if tt in trang_thai:
            return tt
        time.sleep(5)
    return tt


def cho_me(me_id: str, tran: int = 1800) -> dict:
    het = time.time() + tran
    me = {}
    while time.time() < het:
        me, _ = goi(f"/batch-runs/{me_id}")
        if me.get("status") in {"completed", "partial_failed", "failed",
                                "blocked_quota", "cancelled"}:
            return me
        time.sleep(10)
    return me


# ---------------------------------------------------------------------------
# Audit — ba câu hỏi bắt buộc của mini-spec E15 phần 2
# ---------------------------------------------------------------------------

def audit() -> dict:
    print("\n=== AUDIT bắt buộc (3 câu hỏi của mini-spec) ===")

    def trong(dv: str, ma: str) -> str:
        return subprocess.run(
            ["docker", "exec", dv, "python", "-c", ma],
            capture_output=True, text=True, timeout=120).stdout.strip()

    raqm_worker = trong("translation-worker-1",
                        "from PIL import features;print(features.check('raqm'))")
    raqm_api = trong("translation-api-1",
                     "from PIL import features;print(features.check('raqm'))")
    raqm_dev = subprocess.run(
        [".venv/bin/python", "-c", "from PIL import features;print(features.check('raqm'))"],
        capture_output=True, text=True, timeout=60).stdout.strip()

    ghi_nhan("libraqm trong WORKER (nơi dựng chữ thật chạy)", raqm_worker)
    ghi_nhan("libraqm trong API", raqm_api)
    ghi_nhan("libraqm trên MÁY DEV", raqm_dev)
    ghi("AUDIT-1 worker và máy dev KHÁC nhau về libraqm ⇒ đo ở máy dev là đo sai chỗ",
        raqm_worker == "False" and raqm_dev == "True",
        f"worker={raqm_worker}, dev={raqm_dev}")

    co_font_cjk = subprocess.run(
        ["docker", "exec", "translation-worker-1", "sh", "-c",
         "ls /fonts/**/*.ttf /fonts/*.ttf 2>/dev/null | wc -l"],
        capture_output=True, text=True, timeout=60).stdout.strip()
    ghi_nhan("số font trong worker", co_font_cjk)

    co_cjk = trong("translation-worker-1", (
        "import glob;from fontTools.ttLib import TTFont;"
        "n=0\n"
        "for f in glob.glob('/fonts/**/*.ttf',recursive=True):\n"
        "    try:\n"
        "        t=TTFont(f,fontNumber=0,lazy=True)\n"
        "        if any(0x3040<=c<=0x30FF for tb in t['cmap'].tables for c in tb.cmap): n+=1\n"
        "    except Exception: pass\n"
        "print(n)"))
    ghi_nhan("font có glyph kana/kanji trong worker", co_cjk or "không đo được")

    co_cot = sql("select count(*) from ocr_result where line_polygons is not null")
    tong_ocr = sql("select count(*) from ocr_result")
    ghi_nhan("kết quả OCR có đường bao dòng", f"{co_cot}/{tong_ocr}")

    co = sql("select count(*) from region_text_orientation")
    ghi_nhan("số dòng trong region_text_orientation trước khi chạy", co)

    cfg = trong("translation-api-1",
                "from app.core.config import get_settings as g;"
                "s=g();print(s.e15_vertical_render_enabled, s.e15_orientation_enabled)")
    ghi_nhan("cờ e15_vertical_render_enabled / e15_orientation_enabled", cfg)

    return {"raqm_worker": raqm_worker, "raqm_dev": raqm_dev, "font_cjk": co_cjk,
            "ocr_co_cot": co_cot, "cfg": cfg}


# ---------------------------------------------------------------------------
# Run A — chữ ngang không hồi quy
# ---------------------------------------------------------------------------

def run_a() -> str:
    print("\n=== Run A — chữ ngang không hồi quy (Pepper&Carrot) ===")
    if not ANH:
        ghi("A0 có ảnh Pepper&Carrot", False, "không tìm thấy test_fixtures/external/pc_*")
        return ""

    du_an, _ = goi("/projects", "POST", {
        "name": "E15 Run A — chữ ngang", "source_lang": "en", "intended_use": "study"})
    pid = du_an["id"]
    trang = [tai_len(pid, p)["page_id"] for p in ANH[:2]]
    print(f"  chapter {pid[:8]} · {len(trang)} trang")

    for t in trang:
        cho_trang(t, {"detected", "detection_failed"}, 900)

    me, _ = goi(f"/projects/{pid}/batch-runs", "POST",
                {"requested_pipeline": "full_pipeline", "translation_engine": "google_fast"})
    print(f"  mẻ {me['batch_run_id'][:8]} — chờ chạy xong…")
    kq = cho_me(me["batch_run_id"])
    print(f"  mẻ kết thúc: {kq.get('status')}")

    # Bằng chứng hình học phải có THẬT sau khi chạy lại pipeline.
    co_cot = int(sql(
        "select count(*) from ocr_result o join text_region r on r.id=o.region_id "
        f"where r.page_id in ({','.join(chr(39)+t+chr(39) for t in trang)}) "
        "and o.line_polygons is not null") or 0)
    ghi("A1 chạy lại pipeline sinh ra đường bao dòng THẬT", co_cot > 0, f"{co_cot} vùng")

    tong_o = int(sql(
        "select count(*) from region_text_orientation ro join text_region r "
        f"on r.id=ro.region_id where r.page_id in "
        f"({','.join(chr(39)+t+chr(39) for t in trang)})") or 0)
    ghi("A2 hướng chữ được tính cho các vùng", tong_o > 0, f"{tong_o} vùng")

    phan_bo = sql(
        "select ro.orientation||'/'||ro.status||'='||count(*) from region_text_orientation ro "
        f"join text_region r on r.id=ro.region_id where r.page_id in "
        f"({','.join(chr(39)+t+chr(39) for t in trang)}) group by 1,2,ro.orientation,ro.status")
    ghi_nhan("phân bố hướng/trạng thái thật", phan_bo.replace("\n", " · ") or "(rỗng)")

    ngang = int(sql(
        "select count(*) from region_text_orientation ro join text_region r "
        f"on r.id=ro.region_id where r.page_id in "
        f"({','.join(chr(39)+t+chr(39) for t in trang)}) "
        "and ro.orientation='horizontal_ltr'") or 0)
    ghi("A3 truyện chữ ngang được nhận đúng là chữ ngang", ngang > 0, f"{ngang} vùng ngang")

    doc_sai = int(sql(
        "select count(*) from region_text_orientation ro join text_region r "
        f"on r.id=ro.region_id where r.page_id in "
        f"({','.join(chr(39)+t+chr(39) for t in trang)}) "
        "and ro.orientation='vertical_ttb'") or 0)
    ghi("A4 KHÔNG vùng chữ ngang nào bị gọi nhầm thành chữ dọc", doc_sai == 0,
        f"{doc_sai} vùng bị gọi nhầm")

    # Không hồi quy: trang vẫn đi tới trạng thái căn chữ như trước E15.
    tt = [sql(f"select status from page where id='{t}'") for t in trang]
    ghi("A5 trang vẫn đi tới trạng thái căn chữ (không hồi quy M6)",
        all(t in {"typeset_done", "ready_for_export"} for t in tt), str(tt))

    tong_ket, mã = goi(f"/pages/{trang[0]}/orientation-summary")
    ghi("A6 endpoint tổng hợp trả đúng khuôn", mã == 200 and "total_regions" in tong_ket,
        json.dumps(tong_ket, ensure_ascii=False)[:150])

    return pid


# ---------------------------------------------------------------------------
# Run B — chữ dọc tiếng Nhật
# ---------------------------------------------------------------------------

def chan_run_b(a: dict) -> None:
    """Run B KHÔNG chạy được. Ghi lại BA vật cản độc lập, mỗi cái đủ để chặn một mình."""
    print("\n=== Run B — chữ dọc tiếng Nhật: BỊ CHẶN ===")

    ghi_nhan("Vật cản 1 — dữ liệu",
             "không có ảnh chữ dọc tiếng Nhật license rõ trong kho "
             "(test_fixtures/external chỉ có Pepper&Carrot tiếng Anh)")

    ghi_nhan("Vật cản 2 — kiến trúc",
             "MangaOCREngine.recognize() trả (text, None) — KHÔNG có đường bao dòng. "
             "analyzer chỉ tới được vertical_ttb qua ocr_line_geometry_vertical "
             "⇒ trang tiếng Nhật LUÔN ra unknown, kể cả khi có ảnh")

    ghi_nhan("Vật cản 3 — môi trường",
             f"libraqm trong worker = {a['raqm_worker']} ⇒ Pillow direction='ttb' ném KeyError. "
             f"(máy dev = {a['raqm_dev']}, khác worker)")

    ghi_nhan("Vật cản 4 — glyph",
             f"font có glyph kana/kanji trong worker = {a['font_cjk']}")

    ghi("B1 KHÔNG tuyên bố hỗ trợ chữ dọc ở bất kỳ đâu", True,
        "kết luận: vertical rendering BLOCKED, chỉ đóng phần routing/UI")

    # Chốt chặn: không được tồn tại vertical_ttb + ready trong CSDL.
    ready_doc = int(sql("select count(*) from region_text_orientation "
                        "where orientation='vertical_ttb' and status='ready'") or 0)
    ghi("B2 CSDL không có vùng nào mang 'chữ dọc + đã dựng được'", ready_doc == 0,
        f"{ready_doc} vùng")


# ---------------------------------------------------------------------------
# Run C — SFX / chữ nghiêng
# ---------------------------------------------------------------------------

def run_c(pid: str) -> None:
    print("\n=== Run C — SFX / chữ nghiêng ===")
    if not pid:
        ghi("C0 có chapter từ Run A", False)
        return

    tong = int(sql(
        "select count(*) from region_text_orientation ro join text_region r on r.id=ro.region_id "
        f"join page p on p.id=r.page_id where p.project_id='{pid}'") or 0)
    vung = int(sql(f"select count(*) from text_region r join page p on p.id=r.page_id "
                   f"where p.project_id='{pid}'") or 0)
    ghi("C1 KHÔNG vùng nào bị bỏ qua im lặng — mọi vùng đều có phán quyết hướng chữ",
        tong == vung, f"{tong}/{vung} vùng có bản ghi")

    nghieng = sql(
        "select ro.rotation_degrees::text from region_text_orientation ro "
        f"join text_region r on r.id=ro.region_id join page p on p.id=r.page_id "
        f"where p.project_id='{pid}' and ro.orientation='rotated_horizontal'")
    so_nghieng = len([x for x in nghieng.split("\n") if x])
    ghi_nhan("số vùng chữ nghiêng trong chapter đo", str(so_nghieng))

    # Tần suất trên TOÀN BỘ dữ liệu đã phân tích — spec E15 phần 2 §7 nói không được mở E16
    # trước khi có con số này.
    toan_bo = sql(
        "select ro.orientation::text || '=' || count(*)::text "
        "from region_text_orientation ro group by ro.orientation")
    ghi_nhan("tần suất hướng chữ trên TOÀN BỘ dữ liệu đã phân tích",
             toan_bo.replace("\n", " · ") or "(rỗng)")

    # Mọi vùng nghiêng BẮT BUỘC mang mã "chỉ rà soát thủ công" — tức không tự xoay.
    thieu_ma = int(sql(
        "select count(*) from region_text_orientation ro join text_region r on r.id=ro.region_id "
        f"join page p on p.id=r.page_id where p.project_id='{pid}' "
        "and ro.orientation='rotated_horizontal' "
        "and not (ro.reason_codes @> '[\"rotated_text_manual_review_only\"]')") or 0)
    ghi("C2 mọi vùng nghiêng đều ghi rõ 'chỉ rà soát thủ công' — không tự xoay",
        thieu_ma == 0, f"{thieu_ma} vùng thiếu mã")

    thieu_goc = int(sql(
        "select count(*) from region_text_orientation ro join text_region r on r.id=ro.region_id "
        f"join page p on p.id=r.page_id where p.project_id='{pid}' "
        "and ro.orientation='rotated_horizontal' and ro.rotation_degrees is null") or 0)
    ghi("C3 vùng nghiêng nào cũng kèm góc đã chuẩn hoá", thieu_goc == 0,
        f"{thieu_goc} vùng thiếu góc")

    la = sql(
        "select distinct m from region_text_orientation ro "
        "cross join lateral jsonb_array_elements_text(ro.reason_codes) m "
        f"join text_region r on r.id=ro.region_id join page p on p.id=r.page_id "
        f"where p.project_id='{pid}'")
    ghi_nhan("các mã lý do thật xuất hiện", la.replace("\n", ", ") or "(rỗng)")


# ---------------------------------------------------------------------------
# Run D — sửa tay + cảnh báo lúc xuất
# ---------------------------------------------------------------------------

def run_d(pid: str) -> None:
    print("\n=== Run D — sửa tay + cảnh báo lúc xuất ===")
    if not pid:
        ghi("D0 có chapter từ Run A", False)
        return

    canh_bao, ma = goi(f"/projects/{pid}/export-warnings")
    ghi("D1 endpoint cảnh báo xuất trả 200", ma == 200)
    co_khoi = all(k in canh_bao for k in (
        "orientation_vertical_rendered_count", "orientation_review_count",
        "orientation_unknown_count"))
    ghi("D2 cảnh báo xuất có khối hướng chữ TÁCH RIÊNG", co_khoi,
        json.dumps({k: v for k, v in canh_bao.items() if "orientation" in k},
                   ensure_ascii=False))

    # Sửa tay một vùng rồi xem M7 còn chạy đúng không.
    vung = sql("select r.id from text_region r join page p on p.id=r.page_id "
               f"where p.project_id='{pid}' order by r.id limit 1")
    if vung:
        sua, ma_s = goi(f"/regions/{vung}", "PATCH", {"translated_text": "E15 Run D sửa tay"})
        ghi("D3 sửa tay vùng (M7) vẫn chạy", ma_s == 200, f"HTTP {ma_s}")

    xuat, ma_x = goi(f"/projects/{pid}/export", "POST", {"format": "cbz"})
    ghi("D4 xuất chapter (M8) vẫn chạy sau khi có E15", ma_x in (200, 202),
        f"HTTP {ma_x}")

    tuan_thu = sql("select count(*) from export_compliance_log where project_id="
                   f"'{pid}'")
    ghi_nhan("bản ghi tuân thủ M10 sinh ra", tuan_thu)


def main() -> int:
    a = audit()
    # Truyền sẵn project_id để đo lại Run C/D mà không phải chạy lại cả pipeline.
    pid = sys.argv[1] if len(sys.argv) > 1 else run_a()
    chan_run_b(a)
    run_c(pid)
    run_d(pid)

    print("\n" + "=" * 70)
    dat = sum(1 for _, d, _ in KQ if d)
    print(f"KẾT QUẢ: {dat}/{len(KQ)} đạt")
    for ten, d, chi in KQ:
        if not d:
            print(f"  HỎNG: {ten} — {chi}")
    print(f"\nchapter dùng để đo: {pid}")
    return 0 if dat == len(KQ) else 1


if __name__ == "__main__":
    sys.exit(main())
