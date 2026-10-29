#!/usr/bin/env python3
"""Đo Run B/C/D của E12 trên hệ thống thật.

Run B — bơm lỗi có kiểm soát rồi xem cổng chất lượng có nói đúng không.
Run C — quyết định của người dùng có sống qua khởi động lại không.
Run D — sửa tay xong thì cảnh báo có được chấm lại không.

    ../.venv/bin/python scripts/do_run_e12.py <project_id> <page_id>
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

GOC = "http://localhost:8010/api/v1"
KQ: dict = {}


def goi(dd, method="GET", data=None, timeout=120):
    body = json.dumps(data).encode() if data is not None else None
    h = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(f"{GOC}{dd}", data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), r.status
    except urllib.error.HTTPError as exc:
        return {"chi_tiet": exc.read().decode()[:200]}, exc.code


def sql(cau: str) -> str:
    return subprocess.run(
        ["docker", "exec", "translation-db-1", "psql", "-U", "translation",
         "-d", "translation", "-tA", "-c", cau],
        capture_output=True, text=True, timeout=60).stdout.strip()


def trong_worker(ma: str) -> str:
    return subprocess.run(
        ["docker", "compose", "-f", "deploy/docker-compose.yml", "exec", "-T", "worker",
         "python", "-c", ma],
        capture_output=True, text=True, timeout=300).stdout.strip()


def ghi(muc, dat, chi_tiet=""):
    KQ[muc] = {"dat": bool(dat), "chi_tiet": str(chi_tiet)}
    print(f"  [{'ĐẠT' if dat else 'HỎNG'}] {muc}{' — ' + str(chi_tiet) if chi_tiet else ''}",
          flush=True)


def cham_lai(page_id):
    return trong_worker(
        "import uuid;from app.services.quality.gate import QualityGateService;"
        f"print(QualityGateService().assess_page(uuid.UUID('{page_id}'), trigger='run'))")


def danh_gia_theo_vung(page_id) -> dict:
    d, _ = goi(f"/pages/{page_id}/quality")
    return {v["region_id"]: v for v in d["regions"]}


def main() -> int:
    project_id, page_id = sys.argv[1], sys.argv[2]

    print("\n=== Run B — bơm lỗi có kiểm soát ===")
    vung_ids = sql(f"SELECT id FROM text_region WHERE page_id='{page_id}' "
                   "ORDER BY reading_order NULLS LAST LIMIT 4;").splitlines()
    v_fallback, v_mat_dich = vung_ids[0], vung_ids[1]

    sql(f"UPDATE translation_result SET status='fallback_used' WHERE region_id='{v_fallback}';")
    sql(f"DELETE FROM translation_result WHERE region_id='{v_mat_dich}';")
    sql(f"UPDATE typeset_result SET fit_status='overflow_warning' WHERE region_id='{v_mat_dich}';")
    cham_lai(page_id)

    dg = danh_gia_theo_vung(page_id)
    ma_fb = [l["ma"] for l in dg[v_fallback]["ly_do"]]
    ma_md = [l["ma"] for l in dg[v_mat_dich]["ly_do"]]
    ghi("lùi về dịch nhanh được nêu đúng lý do", "translation_fallback_used" in ma_fb, ma_fb)
    ghi("mất bản dịch được nêu đúng lý do", "translation_missing" in ma_md, ma_md)
    ghi("chữ tràn khung được nêu đúng lý do", "layout_overflow_warning" in ma_md)
    ghi("cả hai vùng đều bị đẩy cho người xem",
        dg[v_fallback]["review_status"] == "needs_review"
        and dg[v_mat_dich]["review_status"] == "needs_review")

    tom, _ = goi(f"/projects/{project_id}/quality-summary")
    dem_sql = int(sql("SELECT count(*) FROM region_quality_assessment q "
                      "JOIN text_region r ON r.id=q.region_id JOIN page p ON p.id=r.page_id "
                      f"WHERE p.project_id='{project_id}' AND q.review_status='needs_review';"))
    ghi("số trên API khớp số đếm thẳng từ DB", tom["can_ra_soat"] == dem_sql,
        f"API={tom['can_ra_soat']} DB={dem_sql}")

    canh, _ = goi(f"/projects/{project_id}/export-warnings")
    ghi("hộp thoại xuất nhận đủ số của E12",
        canh.get("quality_needs_review_count") == tom["can_ra_soat"], canh)

    print("\n=== Run C — quyết định của người dùng ===")
    v_bo, v_giu = v_mat_dich, v_fallback
    r1, ma1 = goi(f"/regions/{v_bo}/quality-review", "POST", {"decision": "skip"})
    r2, ma2 = goi(f"/regions/{v_giu}/quality-review", "POST", {"decision": "keep"})
    ghi("ghi được quyết định bỏ qua", ma1 == 200 and r1["review_status"] == "reviewed_skip")
    ghi("ghi được quyết định giữ lại", ma2 == 200 and r2["review_status"] == "reviewed_keep")

    con = sql(f"SELECT count(*) FROM text_region WHERE id='{v_bo}';")
    con_ocr = sql(f"SELECT count(*) FROM ocr_result WHERE region_id='{v_bo}';")
    ghi("bỏ qua KHÔNG xoá dữ liệu", con == "1" and con_ocr == "1",
        f"vùng={con} ocr={con_ocr}")

    subprocess.run(["docker", "compose", "-f", "deploy/docker-compose.yml", "restart", "api"],
                   capture_output=True, timeout=180)
    time.sleep(12)
    dg = danh_gia_theo_vung(page_id)
    ghi("quyết định sống qua khởi động lại",
        dg[v_bo]["review_status"] == "reviewed_skip"
        and dg[v_giu]["review_status"] == "reviewed_keep")

    cham_lai(page_id)
    dg = danh_gia_theo_vung(page_id)
    ghi("chấm lại KHÔNG xoá quyết định của người",
        dg[v_bo]["review_status"] == "reviewed_skip", dg[v_bo]["review_status"])

    print("\n=== Run D — sửa tay xong thì chấm lại ===")
    v_sua = vung_ids[2]
    truoc = danh_gia_theo_vung(page_id)[v_sua]
    khong_lien_quan = vung_ids[3]
    truoc_khac = danh_gia_theo_vung(page_id)[khong_lien_quan]

    sua, ma = goi(f"/regions/{v_sua}", "PATCH", {"translated_text": "M" + "ộ" * 300})
    ghi("sửa được bản dịch", ma == 200, sua.get("fit_status"))
    job = sua.get("refit_job_id")
    for _ in range(60):
        j, _ = goi(f"/jobs/{job}")
        if j.get("status") in ("done", "failed"):
            break
        time.sleep(3)
    ghi("việc căn lại chạy xong", j.get("status") == "done", j.get("error_log"))

    time.sleep(2)
    sau = danh_gia_theo_vung(page_id)
    ma_sau = [l["ma"] for l in sau[v_sua]["ly_do"]]
    ghi("vùng vừa sửa được chấm lại", ma_sau != [l["ma"] for l in truoc["ly_do"]], ma_sau)
    ghi("vùng KHÔNG liên quan giữ nguyên đánh giá",
        sau[khong_lien_quan]["ly_do"] == truoc_khac["ly_do"])

    json.dump(KQ, open("run_e12.json", "w"), ensure_ascii=False, indent=2)
    hong = [k for k, v in KQ.items() if not v["dat"]]
    print(f"\nTổng: {len(KQ) - len(hong)}/{len(KQ)} đạt")
    if hong:
        print("Chưa đạt:", *hong, sep="\n  - ")
    return 1 if hong else 0


if __name__ == "__main__":
    raise SystemExit(main())
