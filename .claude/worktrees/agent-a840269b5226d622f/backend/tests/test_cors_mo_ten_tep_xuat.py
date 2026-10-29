"""Giao diện và API khác tên miền: JS chỉ đọc được `Content-Disposition` (tên tệp xuất) khi API khai
`Access-Control-Expose-Headers`. Thiếu nó, chọn xuất ZIP mà tải về thành `.cbz` (báo 16-10-2026).

Middleware CORS chỉ gắn khi `CORS_ALLOW_ORIGINS` có giá trị LÚC IMPORT `app.main` ⇒ chạy trong tiến
trình con với biến môi trường đó, gửi Origin THẬT (curl/httpx mặc định không gửi Origin).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MA = """
from starlette.testclient import TestClient
from app.main import app
r = TestClient(app).get("/", headers={"Origin": "https://web.test"})
print(r.headers.get("access-control-allow-origin"), "|", r.headers.get("access-control-expose-headers"))
"""


def test_api_mo_content_disposition_cho_giao_dien_khac_ten_mien():
    env = {**os.environ, "CORS_ALLOW_ORIGINS": "https://web.test"}
    ra = subprocess.run([sys.executable, "-c", MA], cwd=Path(__file__).resolve().parents[1],
                        env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert ra.returncode == 0, ra.stderr[-2000:]
    dong = ra.stdout.strip().splitlines()[-1]
    goc, lo = (x.strip() for x in dong.split("|"))
    assert goc == "https://web.test"
    assert "content-disposition" in lo.lower()
