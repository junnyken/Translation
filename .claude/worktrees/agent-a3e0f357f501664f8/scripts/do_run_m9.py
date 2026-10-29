#!/usr/bin/env python3
"""Đo các Run bắt buộc của M9 — mẻ chạy cả chapter, trên hệ thống THẬT.

Vì sao là script chứ không phải gõ tay: số liệu chạy tay rồi chép vào tài liệu là cách chắc chắn
để số sai mà không ai phát hiện. Mọi con số trong `docs/TEST_LOG.md` §M9 đều do file này in ra.

    ../.venv/bin/python scripts/do_run_m9.py A test_fixtures/external/*_1600.png
    ../.venv/bin/python scripts/do_run_m9.py B test_fixtures/external/pc_E01P01_1600.png
    ../.venv/bin/python scripts/do_run_m9.py C test_fixtures/external/pc_E01P01_1600.png
    ../.venv/bin/python scripts/do_run_m9.py E test_fixtures/external/*_1600.png
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

GOC = "http://localhost:8010/api/v1"
XONG_ME = {"completed", "partial_failed", "blocked_quota", "failed", "cancelled"}
TRANG_XONG = {"typeset_done", "ready_for_export"}


def goi(duong_dan: str, method: str = "GET", data: dict | None = None, timeout: int = 120):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(f"{GOC}{duong_dan}", data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return {"_http": exc.code, "_body": exc.read().decode()[:500]}


def tai_len(project_id: str, duong_dan: Path, timeout: int = 300) -> dict:
    ranh = "----runm9"
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


def dung_project(ten: str, anh: list[Path], nguon: str = "en") -> tuple[str, list[str]]:
    du_an = goi("/projects", "POST", {"name": ten, "source_lang": nguon, "intended_use": "study"})
    pid = du_an["id"]
    trang = []
    for p in anh:
        kq = tai_len(pid, p)
        trang.append(kq["page_id"])
        print(f"  tải lên {p.name} -> trang {kq['page_id'][:8]}", flush=True)
    return pid, trang


def cho_trang_toi(page_ids: list[str], moc: set[str], tran_giay: int) -> None:
    """Chờ các trang tới một trong các trạng thái `moc` (dùng để mẻ là thứ DUY NHẤT điều phối)."""
    bat_dau = time.time()
    while time.time() - bat_dau < tran_giay:
        tt = [goi(f"/pages/{p}")["status"] for p in page_ids]
        if all(t in moc for t in tt):
            print(f"  các trang đã ở {sorted(set(tt))} sau {int(time.time()-bat_dau)}s", flush=True)
            return
        time.sleep(3)
    raise SystemExit(f"Hết giờ chờ trang tới {moc}; đang ở {tt}")


def anh_chup_muc(me_id: str) -> list[dict]:
    return goi(f"/batch-runs/{me_id}/items?limit=500")["items"]


def theo_doi_me(me_id: str, tran_giay: int, nhip: float = 2.0, khi_doi=None) -> dict:
    """Theo dõi tới khi mẻ kết thúc. In MỌI lần một mục đổi trạng thái — đây là dòng thời gian thật."""
    bat_dau = time.time()
    truoc: dict[str, str] = {}
    dong_thoi_gian: list[dict] = []
    while time.time() - bat_dau < tran_giay:
        me = goi(f"/batch-runs/{me_id}")
        for m in anh_chup_muc(me_id):
            khoa = str(m["page_order"])
            gia = f"{m['status']}/{m['retry_count']}"
            if truoc.get(khoa) != gia:
                giay = round(time.time() - bat_dau, 1)
                ghi = {"giay": giay, "trang": m["page_order"], "trang_thai": m["status"],
                       "so_lan_thu": m["retry_count"], "ma_loi": m["error_code"]}
                dong_thoi_gian.append(ghi)
                print(f"    {giay:>7}s  trang {m['page_order']}: {m['status']}"
                      f"{'  thử lại ' + str(m['retry_count']) if m['retry_count'] else ''}"
                      f"{'  ' + m['error_code'] if m['error_code'] else ''}", flush=True)
                truoc[khoa] = gia
        if khi_doi:
            khi_doi(me, anh_chup_muc(me_id), time.time() - bat_dau)
        if me["status"] in XONG_ME:
            return {"me": me, "dong_thoi_gian": dong_thoi_gian,
                    "giay": round(time.time() - bat_dau, 1)}
        time.sleep(nhip)
    return {"me": goi(f"/batch-runs/{me_id}"), "dong_thoi_gian": dong_thoi_gian,
            "giay": round(time.time() - bat_dau, 1), "het_gio": True}


def dau_van_tay_trang(page_id: str) -> dict:
    """Bằng chứng KHÔNG tạo kết quả trùng: đếm bản ghi + băm ảnh xem thử."""
    ct = goi(f"/pages/{page_id}/detail")
    bam = None
    if ct.get("preview_url"):
        try:
            with urllib.request.urlopen(
                f"http://localhost:8010{ct['preview_url']}", timeout=120
            ) as r:
                bam = hashlib.md5(r.read()).hexdigest()
        except urllib.error.URLError as exc:
            bam = f"không tải được: {exc}"
    return {
        "trang_thai": ct["page"]["status"],
        "so_vung": len(ct["regions"]),
        "so_ban_dich": sum(1 for v in ct["regions"] if v.get("translated_text")),
        "so_da_canh_chu": sum(1 for v in ct["regions"] if v.get("fit_status") != "pending"),
        "bam_anh_xem_thu": bam,
    }


def trong_worker(*lenh: str) -> str:
    return subprocess.run(
        ["docker", "compose", "-f", "deploy/docker-compose.yml", "exec", "-T", "worker", *lenh],
        capture_output=True, text=True, timeout=120,
    ).stdout.strip()


def chan_mang_dich(bat: bool) -> None:
    """Bật/tắt lỗi MẠNG tạm thời tới máy chủ dịch — dùng cho Run B.

    Chặn bằng /etc/hosts trong container worker: lỗi thật ở tầng mạng, không phải mock hàm dịch.
    """
    if bat:
        trong_worker("sh", "-c",
                     "printf '127.0.0.1 clients5.google.com\\n127.0.0.1 translate.googleapis.com\\n'"
                     " >> /etc/hosts")
    else:
        # KHÔNG dùng `sed -i`: /etc/hosts trong container là bind mount của Docker, đổi tên tệp
        # tạm đè lên nó sẽ báo "Device or resource busy" và **âm thầm không gỡ được chặn**.
        trong_worker("sh", "-c",
                     "grep -v 'clients5.google.com\\|translate.googleapis.com' /etc/hosts"
                     " > /tmp/hosts.moi && cat /tmp/hosts.moi > /etc/hosts")


# ============================== các Run ==============================


def run_a(args) -> dict:
    """Run A — mẻ không LLM, bắt buộc. Cả chapter chạy bằng MỘT mẻ."""
    print("\n=== Run A — chạy cả chapter bằng google_fast ===")
    pid, trang = dung_project("M9 Run A — cả chapter", args.anh)
    # Chờ dò khung xong để mẻ là thứ DUY NHẤT điều phối các bước còn lại.
    cho_trang_toi(trang, {"detected", "detection_failed"}, 900)

    t0 = time.time()
    me = goi(f"/projects/{pid}/batch-runs", "POST",
             {"requested_pipeline": "full_pipeline", "translation_engine": "google_fast"})
    print(f"  mẻ {me['batch_run_id']}: {me['total_pages']} trang, trạng thái {me['status']}")
    chup = anh_chup_muc(me["batch_run_id"])
    thu_tu = [m["page_order"] for m in chup]

    # Bằng chứng ảnh chụp: tải thêm 1 trang SAU khi tạo mẻ, nó không được lẫn vào.
    them = tai_len(pid, args.anh[0])
    print(f"  tải thêm trang {them['page_id'][:8]} SAU khi tạo mẻ")

    kq = theo_doi_me(me["batch_run_id"], args.tran_giay)
    sau = anh_chup_muc(me["batch_run_id"])
    return {
        "project_id": pid, "batch_run_id": me["batch_run_id"],
        "tong_trang_luc_tao": me["total_pages"],
        "thu_tu_trang_trong_me": thu_tu,
        "trang_tai_sau_co_lot_vao_me": any(m["page_id"] == them["page_id"] for m in sau),
        "giay": kq["giay"], "dong_thoi_gian": kq["dong_thoi_gian"], "me": kq["me"],
        "muc": [{"trang": m["page_order"], "trang_thai": m["status"],
                 "so_lan_thu": m["retry_count"], "ma_loi": m["error_code"]} for m in sau],
        "dau_van_tay": {m["page_order"]: dau_van_tay_trang(m["page_id"]) for m in sau},
    }


def run_b(args) -> dict:
    """Run B — lỗi mạng TẠM THỜI, bắt buộc: thử lại có giới hạn rồi xong."""
    print("\n=== Run B — lỗi tạm thời rồi thành công ===")
    pid, trang = dung_project("M9 Run B — thử lại", args.anh[:1])
    cho_trang_toi(trang, {"detected", "detection_failed"}, 900)

    print("  chặn máy chủ dịch trong worker (lỗi mạng thật, không mock hàm dịch)")
    chan_mang_dich(True)
    da_mo = {"xong": False}

    def mo_lai_khi_thay_thu_lai(me, muc, giay):
        if not da_mo["xong"] and any(m["retry_count"] >= 1 for m in muc):
            chan_mang_dich(False)
            da_mo["xong"] = True
            print(f"    {giay:.1f}s  đã BỎ chặn mạng — lần thử lại phải chạy được")

    try:
        me = goi(f"/projects/{pid}/batch-runs", "POST",
                 {"requested_pipeline": "full_pipeline", "translation_engine": "google_fast"})
        kq = theo_doi_me(me["batch_run_id"], args.tran_giay, nhip=0.5,
                         khi_doi=mo_lai_khi_thay_thu_lai)
    finally:
        chan_mang_dich(False)

    muc = anh_chup_muc(me["batch_run_id"])
    viec = goi(f"/pages/{trang[0]}/detail")
    return {
        "project_id": pid, "batch_run_id": me["batch_run_id"],
        "da_bo_chan_giua_chung": da_mo["xong"],
        "giay": kq["giay"], "dong_thoi_gian": kq["dong_thoi_gian"], "me": kq["me"],
        "so_lan_thu_cuoi": [m["retry_count"] for m in muc],
        "trang_thai_muc": [m["status"] for m in muc],
        "trang_thai_trang": viec["page"]["status"],
        "dau_van_tay": dau_van_tay_trang(trang[0]),
    }


def run_c(args) -> dict:
    """Run C — cổng nhịp CHẶN: không có lời gọi nào ra nhà cung cấp."""
    print("\n=== Run C — cổng nhịp chặn trước khi gọi provider ===")
    cau_hinh = goi("/batch-config")
    print(f"  cấu hình: {cau_hinh}")
    pid, trang = dung_project("M9 Run C — cổng quota", args.anh[:1])
    cho_trang_toi(trang, {"detected", "detection_failed"}, 900)

    # Làm ĐẦY cửa sổ nhịp và GIỮ đầy suốt mẻ. Chỉ làm đầy một lần là không đủ: cửa sổ trượt
    # 60s sẽ tự nhả lượt, và lần thử lại thứ tư lọt qua — đã đo thật (xem TEST_LOG §M9 Run C).
    thong_tin = json.loads(trong_worker("python", "-c", """
import json
from app.core.config import get_settings
from app.services.batch.gate import GeminiProjectRateGate
s = get_settings()
print(json.dumps({
    "khoa": GeminiProjectRateGate.khoa_project(s.llm_model_name, "gemini"),
    "rpm": s.llm_project_rpm,
}))
"""))
    print(f"  cổng: khoá {thong_tin['khoa']}, hạn mức {thong_tin['rpm']} lượt/phút")

    from app.services.batch.gate import GeminiProjectRateGate  # noqa: PLC0415

    cong = GeminiProjectRateGate("redis://localhost:6380/0", rpm=thong_tin["rpm"])
    dung_lai = threading.Event()

    def giu_cong_day():
        while not dung_lai.is_set():
            for _ in range(thong_tin["rpm"]):
                cong.acquire(thong_tin["khoa"])
            dung_lai.wait(3)

    luong = threading.Thread(target=giu_cong_day, daemon=True)
    luong.start()
    time.sleep(1)
    day_cong = {"lan_ke_tiep_cho_phep": cong.acquire(thong_tin["khoa"]).cho_phep}
    print(f"  giữ cổng đầy: {day_cong}")

    me = goi(f"/projects/{pid}/batch-runs", "POST",
             {"requested_pipeline": "full_pipeline", "translation_engine": "llm_context"})
    if "_http" in me:
        return {"bi_tu_choi_ngay": me, "ghi_chu": "chưa cấu hình khoá dịch nên 422 — đúng hợp đồng"}
    kq = theo_doi_me(me["batch_run_id"], args.tran_giay, nhip=1.0)

    # Hạn mức hồi ⇒ bấm chạy lại phải chạy được, và CHỈ chạy lại trang bị chặn.
    dung_lai.set()
    luong.join(timeout=10)
    print("  đã thả cổng; chờ cửa sổ nhịp trôi qua rồi bấm chạy lại")
    time.sleep(62)
    tiep = goi(f"/batch-runs/{me['batch_run_id']}/resume", "POST", {})
    print(f"  chạy lại: {tiep}")
    kq2 = theo_doi_me(me["batch_run_id"], args.tran_giay, nhip=1.0)

    nhat_ky = subprocess.run(
        ["docker", "compose", "-f", "deploy/docker-compose.yml", "logs", "--tail", "400", "worker"],
        capture_output=True, text=True, timeout=120).stdout
    dong_cong = [d for d in nhat_ky.splitlines() if "cổng nhịp" in d or "gate" in d.lower()]
    goi_that = [d for d in nhat_ky.splitlines() if "generativelanguage.googleapis.com" in d]
    viec = goi(f"/pages/{trang[0]}/detail")
    return {
        "project_id": pid, "batch_run_id": me["batch_run_id"], "cau_hinh": cau_hinh,
        "lam_day_cong": day_cong, "giay": kq["giay"], "me_khi_bi_chan": kq["me"],
        "ket_qua_resume": tiep, "me": kq2["me"], "giay_sau_resume": kq2["giay"],
        "dong_thoi_gian": kq["dong_thoi_gian"] + kq2["dong_thoi_gian"],
        "muc": [{"trang": m["page_order"], "trang_thai": m["status"], "ma_loi": m["error_code"],
                 "loi": m["error_message"]} for m in anh_chup_muc(me["batch_run_id"])],
        "dong_nhat_ky_ve_cong": dong_cong[-5:],
        "co_dau_vet_goi_that_ra_gemini": goi_that[-3:],
        "ban_dich_cua_trang": [
            {"vung": v.get("reading_order"), "ban_dich": v.get("translated_text"),
             "trang_thai": v.get("translation_status")}
            for v in viec["regions"]
        ],
    }


def run_e(args) -> dict:
    """Run E — worker chết giữa chừng rồi chạy lại, bắt buộc."""
    print("\n=== Run E — khởi động lại worker giữa mẻ rồi chạy tiếp ===")
    pid, trang = dung_project("M9 Run E — khởi động lại", args.anh)
    cho_trang_toi(trang, {"detected", "detection_failed"}, 900)

    me = goi(f"/projects/{pid}/batch-runs", "POST",
             {"requested_pipeline": "full_pipeline", "translation_engine": "google_fast"})
    me_id = me["batch_run_id"]
    chup_truoc = [(m["page_id"], m["page_order"]) for m in anh_chup_muc(me_id)]

    print("  chờ mẻ chạy được một lúc rồi giết worker…")
    time.sleep(args.giay_truoc_khi_giet)
    truoc_khi_giet = goi(f"/batch-runs/{me_id}")
    muc_truoc = anh_chup_muc(me_id)
    subprocess.run(["docker", "compose", "-f", "deploy/docker-compose.yml", "kill", "worker"],
                   capture_output=True, text=True, timeout=120)
    print(f"    đã giết worker; mẻ đang: {truoc_khi_giet['status']} "
          f"({truoc_khi_giet['completed_pages']}/{truoc_khi_giet['total_pages']})")
    time.sleep(5)
    subprocess.run(["docker", "compose", "-f", "deploy/docker-compose.yml", "up", "-d", "worker"],
                   capture_output=True, text=True, timeout=600)
    print("    worker đã chạy lại")
    time.sleep(20)

    sau_khi_song = goi(f"/batch-runs/{me_id}")
    tiep = goi(f"/batch-runs/{me_id}/resume", "POST", {})
    print(f"    chạy lại: {tiep}")
    kq = theo_doi_me(me_id, args.tran_giay)
    chup_sau = [(m["page_id"], m["page_order"]) for m in anh_chup_muc(me_id)]
    return {
        "project_id": pid, "batch_run_id": me_id,
        "truoc_khi_giet": truoc_khi_giet, "sau_khi_worker_song_lai": sau_khi_song,
        "ket_qua_resume": tiep,
        "anh_chup_khong_doi": chup_truoc == chup_sau,
        "muc_truoc_khi_giet": [{"trang": m["page_order"], "trang_thai": m["status"]}
                               for m in muc_truoc],
        "giay": kq["giay"], "me": kq["me"], "dong_thoi_gian": kq["dong_thoi_gian"],
        "dau_van_tay": {m["page_order"]: dau_van_tay_trang(m["page_id"])
                        for m in anh_chup_muc(me_id)},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", choices=["A", "B", "C", "E"])
    ap.add_argument("anh", nargs="+", type=Path)
    ap.add_argument("--tran-giay", type=int, default=3600)
    ap.add_argument("--giay-truoc-khi-giet", type=int, default=45)
    ap.add_argument("--ra", type=Path, default=None)
    args = ap.parse_args()

    thieu = [p for p in args.anh if not p.is_file()]
    if thieu:
        print("Không thấy ảnh:", *thieu, sep="\n  ")
        return 2

    kq = {"A": run_a, "B": run_b, "C": run_c, "E": run_e}[args.run](args)
    ra = args.ra or Path(f"run_m9_{args.run.lower()}.json")
    ra.write_text(json.dumps(kq, ensure_ascii=False, indent=2))
    print(f"\nĐã ghi {ra}")
    print(json.dumps(kq.get("me", {}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
