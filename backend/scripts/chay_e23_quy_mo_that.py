"""E23 — chạy một chapter 24 trang THẬT qua pipeline, đo thời gian và bộ nhớ.

## Ba câu cần trả lời

1. **"24 trang ≈ 54 phút" là ngoại suy tuyến tính từ 6 trang** (`REPORT_E25.md §6`), chưa ai chạy
   thật. Đúng hay lệch?
2. RSS đứng phẳng ~1219MB qua 6 trang, nhả model 1 lần. Qua 24 trang (dài gấp 4) còn phẳng không?
3. E22 (heartbeat + quét job mồ côi) chưa từng chạy dưới một lượt dài thật.

## Giới hạn của bàn thử — đọc trước khi tin số

Môi trường DinD này **KHÔNG bó được bộ nhớ container**: `mem_limit` làm container không start nổi
(`cannot enter cgroupv2 ... it is in threaded mode`, xem `docker-compose.e23-mem.yml`). Nên đây
**không** phải phép kiểm hành vi hồi phục sau OOM — nó chỉ **dự đoán**: đo RSS đỉnh rồi so với
ngân sách thật của production (~3950MB = 4096MB trừ ~104MB uvicorn chiếm lúc rảnh). Đỉnh nằm xa
dưới mức đó ⇒ production an toàn theo dự đoán. Sát mức đó ⇒ đã tìm ra rủi ro. **Không** kết luận
"E22 hồi phục tốt" từ lượt chạy này, vì không có cú OOM nào xảy ra để mà hồi phục.

Thời gian thì đại diện được: E25 §2.7 cho thấy pipeline gần như không scale theo số core, nên máy
local 12 core không nhanh hơn production 2,6 CPU đáng kể.

## Nguồn trang

Pepper&Carrot, David Revoy, **CC BY-SA 4.0**, https://www.peppercarrot.com — 24 trang nội dung
(bỏ trang bìa P00) từ ep11/12/13/14. Ảnh nằm ở `test_fixtures/external/` (đã .gitignore), KHÔNG
commit vào repo.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

API = "http://localhost:8010/api/v1"
TAI_KHOAN = {"email": "test-e2e@local.test", "mat_khau": "e21b-local-test"}
NGAN_SACH_PRODUCTION_MB = 3950
NHIP_GIAY = 20


def goi(duong: str, *, tok: str | None = None, body: dict | None = None) -> dict:
    du_lieu = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{duong}", data=du_lieu, method="POST" if du_lieu else "GET")
    req.add_header("Content-Type", "application/json")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def tai_trang(duong: str, tok: str, tep: Path) -> dict:
    """Upload multipart bằng tay — không kéo thêm thư viện chỉ để gửi một tệp."""
    ranh = "----e23boundary"
    than = (
        f"--{ranh}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{tep.name}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + tep.read_bytes() + f"\r\n--{ranh}--\r\n".encode()
    req = urllib.request.Request(f"{API}{duong}", data=than, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={ranh}")
    req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def rss_worker_mb() -> float:
    """Tổng RSS mọi tiến trình trong container worker."""
    kq = run(
        ["docker", "compose", "-f", "deploy/docker-compose.yml", "exec", "-T", "worker",
         "sh", "-c", r"awk '/VmRSS/{s+=$2} END{print s/1024}' /proc/[0-9]*/status"],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return float(kq.stdout.strip())
    except ValueError:
        return -1.0


def main() -> None:
    thu_muc = Path(sys.argv[1])
    anh = sorted(thu_muc.glob("E*P*.jpg"))
    if len(anh) != 24:
        raise SystemExit(f"cần đúng 24 trang, thấy {len(anh)} ở {thu_muc}")

    tok = goi("/auth/login", body=TAI_KHOAN)["ma_phien"]
    print(f"đăng nhập xong · token {tok[:8]}…", flush=True)

    du_an = goi("/projects", tok=tok, body={
        "name": f"E23 quy mô thật 24 trang {datetime.now():%m-%d %H:%M}",
        "source_lang": "en", "target_lang": "vi", "intended_use": "study",
    })["id"]
    print(f"project {du_an}", flush=True)

    for i, tep in enumerate(anh, 1):
        kq = tai_trang(f"/projects/{du_an}/pages", tok, tep)
        print(f"  tải {i:2}/24 {tep.name} -> trang {str(kq['page_id'])[:8]} ({kq['status']})",
              flush=True)

    me = goi(f"/projects/{du_an}/batch-runs", tok=tok, body={"requested_pipeline": "full_pipeline"})
    me_id = me["batch_run_id"]
    print(f"\nmẻ {me_id} · {me['total_pages']} trang · bắt đầu theo dõi\n", flush=True)

    bat_dau = time.time()
    dinh_rss, truoc = 0.0, None
    # Lần chạy 09-10 mất dấu RSS 9,5 phút vì điều kiện in cũ (`rss > dinh_rss - 1`) im lặng ĐÚNG
    # LÚC RSS tụt xuống — tức che mất chính cái vết lõm đáng xem. Nay: in khi có thay đổi thật,
    # hoặc cứ 2 phút một dòng, kèm cả đáy để thấy dao động.
    day_rss = float("inf")
    lan_in_cuoi = 0.0
    while True:
        try:
            tt = goi(f"/batch-runs/{me_id}", tok=tok)
        except urllib.error.HTTPError as e:
            if e.code == 401:  # phiên hết hạn giữa lượt chạy dài
                tok = goi("/auth/login", body=TAI_KHOAN)["ma_phien"]
                continue
            raise
        rss = rss_worker_mb()
        dinh_rss = max(dinh_rss, rss)
        if rss >= 0:
            day_rss = min(day_rss, rss)
        moc = (tt["completed_pages"], tt["failed_pages"], tt["blocked_pages"], tt["status"])
        phut = (time.time() - bat_dau) / 60
        if moc != truoc or (time.time() - lan_in_cuoi) >= 120:
            day = 0.0 if day_rss == float("inf") else day_rss
            print(f"[{phut:5.1f}p] xong={tt['completed_pages']:2}/{tt['total_pages']} "
                  f"hỏng={tt['failed_pages']} chặn={tt['blocked_pages']} "
                  f"{tt['status']:10} RSS={rss:7.1f}MB đỉnh={dinh_rss:7.1f}MB "
                  f"đáy={day:7.1f}MB", flush=True)
            truoc = moc
            lan_in_cuoi = time.time()
            day_rss = float("inf")  # đáy tính lại theo từng khoảng, không phải toàn lượt
        if tt["status"] in ("completed", "failed", "cancelled"):
            print(f"\n=== KẾT THÚC: {tt['status']} ===", flush=True)
            print(f"trang xong   : {tt['completed_pages']}/{tt['total_pages']}", flush=True)
            print(f"trang hỏng   : {tt['failed_pages']}", flush=True)
            print(f"trang chặn   : {tt['blocked_pages']}", flush=True)
            print(f"bắt đầu      : {tt['started_at']}", flush=True)
            print(f"kết thúc     : {tt['finished_at']}", flush=True)
            print(f"tường (theo dõi): {phut:.1f} phút", flush=True)
            print(f"RSS đỉnh     : {dinh_rss:.1f}MB "
                  f"({dinh_rss / NGAN_SACH_PRODUCTION_MB * 100:.0f}% ngân sách production "
                  f"{NGAN_SACH_PRODUCTION_MB}MB)", flush=True)
            if tt["error_summary"]:
                print(f"lỗi          : {tt['error_summary']}", flush=True)
            print(f"project      : {du_an}", flush=True)
            print(f"mẻ           : {me_id}", flush=True)
            break
        time.sleep(NHIP_GIAY)

    print(f"\nkết thúc lúc {datetime.now(timezone.utc):%H:%M:%S}Z", flush=True)


if __name__ == "__main__":
    main()
