#!/usr/bin/env python3
"""Đo Run của M10 — cổng khai báo mục đích & cảnh báo trước khi mang file đi, trên hệ thống THẬT.

Không dựng dữ liệu giả: vùng tràn khung được tạo bằng đúng thao tác người dùng làm ở màn sửa tay
(sửa bản dịch thành câu dài rồi để hệ thống canh lại), chứ không ghi thẳng `overflow_warning`
vào DB.

    ../.venv/bin/python scripts/do_run_m10.py <project_id> [--ra run_m10.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

GOC = "http://localhost:8010/api/v1"

#: Câu dài cố ý — chắc chắn không nhét vừa bong bóng, để hệ thống tự báo tràn khung.
CAU_DAI = (
    "Đây là một câu dịch cố ý viết thật dài để kiểm tra cảnh báo tràn khung của hệ thống, "
    "dài tới mức không bong bóng thoại nào chứa nổi dù đã thu nhỏ cỡ chữ hết mức cho phép."
)


def goi(duong_dan: str, method: str = "GET", data: dict | None = None, timeout: int = 180):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(f"{GOC}{duong_dan}", data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), r.status
    except urllib.error.HTTPError as exc:
        return {"chi_tiet": exc.read().decode()[:300]}, exc.code


def cho_job(job_id: str, tran_giay: int = 600, loai: str = "jobs") -> str:
    """Chờ một việc chạy xong.

    `loai` phải khớp: việc xuất chapter nằm ở bảng RIÊNG (`/export-jobs/{id}`), hỏi nhầm sang
    `/jobs/{id}` thì luôn nhận 404 và ngồi chờ tới hết giờ mà không hiểu vì sao.
    """
    bat_dau = time.time()
    while time.time() - bat_dau < tran_giay:
        job, ma = goi(f"/{loai}/{job_id}")
        if ma == 404:
            return f"không thấy việc ở /{loai}/"
        if job.get("status") in ("done", "failed"):
            return job["status"]
        time.sleep(2)
    return "hết giờ"


def psql(sql: str) -> str:
    return subprocess.run(
        ["docker", "exec", "translation-db-1", "psql", "-U", "translation", "-d", "translation",
         "-c", sql],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project_id")
    ap.add_argument("--ra", type=Path, default=Path("run_m10.json"))
    args = ap.parse_args()
    kq: dict = {"project_id": args.project_id}

    print("=== 1. Khai báo mục đích là BẮT BUỘC ===")
    kq["tao_thieu_khai_bao"] = {}
    for ten, than in (
        ("thiếu hẳn", {"name": "M10 thiếu", "source_lang": "en"}),
        ("giá trị lạ", {"name": "M10 lạ", "source_lang": "en", "intended_use": "commercial"}),
        ("để rỗng", {"name": "M10 rỗng", "source_lang": "en", "intended_use": ""}),
        ("hợp lệ", {"name": "M10 hợp lệ", "source_lang": "en", "intended_use": "study"}),
    ):
        body, ma = goi("/projects", "POST", than)
        kq["tao_thieu_khai_bao"][ten] = ma
        print(f"  {ten:<12} -> HTTP {ma}")
        if ma == 201:
            kq["project_sach_id"] = body["id"]

    print("\n=== 2. Tạo vùng TRÀN KHUNG thật bằng thao tác sửa tay (M7) ===")
    trang, _ = goi(f"/projects/{args.project_id}")
    page_id = trang["pages"][0]["id"]
    ct, _ = goi(f"/pages/{page_id}/detail")
    vung = next((v for v in ct["regions"] if v.get("translated_text")), None)
    if vung is None:
        print("  không có vùng nào đã dịch — bỏ qua bước này")
    else:
        sua, ma = goi(f"/regions/{vung['id']}", "PATCH", {"translated_text": CAU_DAI})
        print(f"  sửa vùng {vung['id'][:8]} thành câu {len(CAU_DAI)} ký tự -> HTTP {ma}")
        if sua.get("refit_job_id"):
            print(f"  canh lại: {cho_job(sua['refit_job_id'])}")
        ct2, _ = goi(f"/pages/{page_id}/detail")
        moi = next(v for v in ct2["regions"] if v["id"] == vung["id"])
        kq["vung_sau_khi_sua"] = {"vua_khung": moi.get("fit_status"), "co_chu": moi.get("font_size")}
        print(f"  vùng đó nay: {moi.get('fit_status')} (cỡ chữ {moi.get('font_size')})")

    print("\n=== 3. Cảnh báo hiện ra trước khi xuất ===")
    canh_bao, _ = goi(f"/projects/{args.project_id}/export-warnings")
    kq["canh_bao_truoc_khi_xuat"] = canh_bao
    print(f"  {canh_bao}")

    print("\n=== 4. Xuất + ghi nhận đã đọc cảnh báo ===")
    viec, ma = goi(f"/projects/{args.project_id}/export", "POST", {"format": "cbz"})
    print(f"  tạo việc xuất -> HTTP {ma}, job {viec.get('job_id', '')[:8]}")
    job_id = viec["job_id"]
    xac_nhan, ma_xn = goi(f"/export-jobs/{job_id}/acknowledge", "POST", {"user_acknowledged": True})
    kq["xac_nhan"] = xac_nhan
    print(f"  ghi nhận -> HTTP {ma_xn}: {xac_nhan}")
    print(f"  việc xuất chạy: {cho_job(job_id, 900, loai='export-jobs')}")

    print("\n=== 5. Đã xác nhận thì lần sau không hỏi lại ===")
    lai, _ = goi(f"/projects/{args.project_id}/export-warnings")
    kq["canh_bao_lan_sau"] = lai
    print(f"  {lai}")

    print("\n=== 6. Nhật ký tuân thủ trong DB — chỉ số liệu ===")
    kq["cot_bang_nhat_ky"] = psql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='export_compliance_log' ORDER BY ordinal_position;"
    )
    print(kq["cot_bang_nhat_ky"])
    kq["ban_ghi"] = psql(
        "SELECT intended_use, overflow_warning_count, needs_manual_count, user_acknowledged, "
        "acknowledged_at IS NOT NULL AS co_moc FROM export_compliance_log "
        f"WHERE project_id='{args.project_id}';"
    )
    print(kq["ban_ghi"])

    print("\n=== 7. KHÔNG chặn xuất khi chưa xác nhận (chapter khác) ===")
    if kq.get("project_sach_id"):
        _, ma_rong = goi(f"/projects/{kq['project_sach_id']}/export", "POST", {"format": "cbz"})
        kq["xuat_chapter_rong"] = ma_rong
        # M8 cố ý nhận việc (202) rồi để job báo `no_page_ready` — xuất là việc chạy nền,
        # không phán ngay ở tầng HTTP. Ghi lại đúng như vậy, không sửa kỳ vọng cho khớp.
        print(f"  chapter chưa có trang -> HTTP {ma_rong} (M8: nhận việc rồi job báo no_page_ready)")
    try:
        with urllib.request.urlopen(f"{GOC}/export-jobs/{job_id}/download", timeout=180) as r:
            ma_tai, so_byte = r.status, len(r.read())
    except urllib.error.HTTPError as exc:
        ma_tai, so_byte = exc.code, 0
    kq["tai_ve_sau_khi_xac_nhan"] = {"http": ma_tai, "so_byte": so_byte}
    print(f"  tải file đã xuất -> HTTP {ma_tai}, {so_byte} byte")

    args.ra.write_text(json.dumps(kq, ensure_ascii=False, indent=2))
    print(f"\nĐã ghi {args.ra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
