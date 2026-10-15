"""Test MCP server Translation bằng một máy chủ HTTP GIẢ chạy trong thread."""
from __future__ import annotations

import asyncio
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

PID = "11111111-1111-4111-8111-111111111111"
PAGE = "22222222-2222-4222-8222-222222222222"
REG = "33333333-3333-4333-8333-333333333333"
JOB = "44444444-4444-4444-8444-444444444444"
EXP = "55555555-5555-4555-8555-555555555555"
BATCH = "66666666-6666-4666-8666-666666666666"
MA_PHIEN = "tok-SECRET-123456"
MAT_KHAU = "mat-khau-bi-mat-9"


def png(size=(10, 10)) -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", size, "white").save(b, "PNG")
    return b.getvalue()


class Fake:
    def __init__(self):
        self.reqs: list[dict] = []
        self.dang_nhap_so_lan = 0
        self.job_polls = 0
        self.het_han_lan_dau = False
        self.anh = png((3000, 1000))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # im lặng
        pass

    def _lam(self, method):
        f: Fake = self.server.fake
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        f.reqs.append({"method": method, "path": self.path, "headers": dict(self.headers),
                       "body": body})
        path = self.path.split("?")[0]

        def js(code, obj):
            d = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(d)))
            self.end_headers()
            self.wfile.write(d)

        def raw(code, d, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(d)))
            self.end_headers()
            self.wfile.write(d)

        if path == "/api/v1/auth/login":
            f.dang_nhap_so_lan += 1
            j = json.loads(body)
            if j["mat_khau"] != MAT_KHAU:
                return js(401, {"detail": "Sai email hoặc mật khẩu."})
            return js(200, {"ma_phien": MA_PHIEN, "het_han": "2030-01-01T00:00:00Z",
                            "nguoi_dung": {}})
        if path != "/api/v1/health":
            if self.headers.get("Authorization") != f"Bearer {MA_PHIEN}":
                return js(401, {"detail": "Chưa đăng nhập"})
            if f.het_han_lan_dau:
                f.het_han_lan_dau = False
                return js(401, {"detail": "Phiên hết hạn"})
        if (method, path) == ("GET", "/api/v1/projects"):
            return js(200, [{"id": PID, "name": "Ch1"}])
        if (method, path) == ("POST", "/api/v1/projects"):
            return js(201, {"id": PID, **json.loads(body)})
        if (method, path) == ("GET", f"/api/v1/projects/{PID}"):
            return js(200, {"id": PID, "pages": [{"id": PAGE, "order": 1, "status": "queued"}]})
        if (method, path) == ("POST", f"/api/v1/projects/{PID}/pages"):
            return js(202, {"page_id": PAGE, "status": "queued", "job_id": JOB})
        if (method, path) == ("POST", f"/api/v1/projects/{PID}/pages/archive"):
            return js(202, {"project_id": PID, "trang": [], "bo_qua": 0})
        if (method, path) == ("GET", f"/api/v1/pages/{PAGE}/detail"):
            return js(200, {"page": {"id": PAGE}, "regions": [
                {"id": REG, "raw_text": "こんにちは", "translated_text": "Xin chào",
                 "fit_status": "fit"}]})
        if (method, path) == ("GET", f"/api/v1/pages/{PAGE}/typeset-preview"):
            return raw(200, f.anh, "image/png")
        if (method, path) == ("GET", f"/api/v1/pages/{PAGE}/clean-image"):
            return js(404, {"detail": "Page chưa có ảnh clean"})
        if (method, path) == ("PATCH", f"/api/v1/regions/{REG}"):
            return js(200, {"region_id": REG, "fit_status": "pending", "refit_job_id": JOB,
                            "edited_fields": list(json.loads(body))})
        if (method, path) == ("GET", f"/api/v1/jobs/{JOB}"):
            f.job_polls += 1
            return js(200, {"id": JOB, "status": "running" if f.job_polls < 2 else "done"})
        if (method, path) == ("POST", f"/api/v1/regions/{REG}/re-translate"):
            return js(202, {"job_id": JOB, "page_id": PAGE, "status": "queued"})
        if (method, path) == ("POST", f"/api/v1/pages/{PAGE}/retry-ocr"):
            return js(202, {"page_id": PAGE, "job_id": JOB, "status": "ocr_running"})
        if (method, path) == ("POST", f"/api/v1/projects/{PID}/batch-runs"):
            return js(202, {"batch_run_id": BATCH, "status": "queued", "total_pages": 1})
        if (method, path) == ("GET", f"/api/v1/batch-runs/{BATCH}"):
            return js(200, {"id": BATCH, "status": "completed", "total_pages": 1,
                            "completed_pages": 1})
        if (method, path) == ("POST", f"/api/v1/projects/{PID}/export"):
            return js(202, {"job_id": EXP, "project_id": PID, "status": "queued"})
        if (method, path) == ("GET", f"/api/v1/jobs/{EXP}"):
            return js(404, {"detail": "Job không tồn tại"})
        if (method, path) == ("GET", f"/api/v1/export-jobs/{EXP}"):
            return js(200, {"id": EXP, "status": "done", "format": "cbz",
                            "output_path": "exports/x/ch1.cbz"})
        if (method, path) == ("GET", f"/api/v1/export-jobs/{EXP}/download"):
            return raw(200, b"PK-fake-zip", "application/octet-stream")
        return js(422, {"detail": [{"loc": ["body", "source_lang"], "msg": "không hợp lệ"}]})

    do_GET = lambda self: self._lam("GET")  # noqa: E731
    do_POST = lambda self: self._lam("POST")  # noqa: E731
    do_PATCH = lambda self: self._lam("PATCH")  # noqa: E731


@pytest.fixture
def fake(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.fake = Fake()
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    for k in ("TRANSLATION_MA_PHIEN", "TRANSLATION_EMAIL", "TRANSLATION_MAT_KHAU",
              "TRANSLATION_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TRANSLATION_API_URL", f"http://127.0.0.1:{srv.server_address[1]}")
    server._phien_da_dang_nhap.clear()
    yield srv.fake
    srv.shutdown()
    srv.server_close()


def chay(coro):
    return asyncio.run(coro)


def thong_diep_loi(coro) -> str:
    with pytest.raises(server.LoiApi) as e:
        chay(coro)
    return str(e.value)


def test_bearer_va_duong_dan(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    kq = chay(server.liet_ke_chapter())
    assert kq[0]["id"] == PID
    r = fake.reqs[-1]
    assert (r["method"], r["path"]) == ("GET", "/api/v1/projects")
    assert r["headers"]["Authorization"] == f"Bearer {MA_PHIEN}"


def test_api_key_header_tuy_chon(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    monkeypatch.setenv("TRANSLATION_API_KEY", "khoa-chung-xyz")
    chay(server.liet_ke_chapter())
    assert {k.lower(): v for k, v in fake.reqs[-1]["headers"].items()}["x-api-key"] == "khoa-chung-xyz"


def test_dang_nhap_email_mat_khau_lay_ma_phien_va_cache(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_EMAIL", "a@b.vn")
    monkeypatch.setenv("TRANSLATION_MAT_KHAU", MAT_KHAU)
    chay(server.liet_ke_chapter())
    chay(server.liet_ke_chapter())
    login = [r for r in fake.reqs if r["path"] == "/api/v1/auth/login"]
    assert len(login) == 1 and fake.dang_nhap_so_lan == 1
    assert json.loads(login[0]["body"]) == {"email": "a@b.vn", "mat_khau": MAT_KHAU}
    assert fake.reqs[-1]["headers"]["Authorization"] == f"Bearer {MA_PHIEN}"


def test_phien_het_han_tu_dang_nhap_lai(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_EMAIL", "a@b.vn")
    monkeypatch.setenv("TRANSLATION_MAT_KHAU", MAT_KHAU)
    chay(server.liet_ke_chapter())
    fake.het_han_lan_dau = True
    assert chay(server.liet_ke_chapter())[0]["id"] == PID
    assert fake.dang_nhap_so_lan == 2


def test_dang_nhap_sai_khong_lo_mat_khau(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_EMAIL", "a@b.vn")
    monkeypatch.setenv("TRANSLATION_MAT_KHAU", "sai-mat-khau-1")
    msg = thong_diep_loi(server.liet_ke_chapter())
    assert "Đăng nhập thất bại" in msg and "sai-mat-khau-1" not in msg


def test_thieu_xac_thuc_co_huong_dan(fake):
    msg = thong_diep_loi(server.liet_ke_chapter())
    assert "TRANSLATION_MA_PHIEN" in msg and "TRANSLATION_EMAIL" in msg


def test_ma_phien_sai_bao_401_khong_lo_ma(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", "ma-sai-khong-duoc-in")
    msg = thong_diep_loi(server.liet_ke_chapter())
    assert "401" in msg and "ma-sai-khong-duoc-in" not in msg


def test_loi_api_doc_duoc_422(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    msg = thong_diep_loi(server.chay_lai_buoc(PAGE, "detect"))
    assert "422" in msg and "body.source_lang" in msg and MA_PHIEN not in msg


def test_loi_404_co_noi_dung_detail(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    msg = thong_diep_loi(server.xem_anh_trang(PAGE, "sach"))
    assert "404" in msg and "chưa có ảnh clean" in msg


def test_api_khong_toi_duoc(monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    monkeypatch.setenv("TRANSLATION_API_URL", "http://127.0.0.1:1")
    msg = thong_diep_loi(server.liet_ke_chapter())
    assert "Không kết nối được" in msg and "TRANSLATION_API_URL" in msg
    assert MA_PHIEN not in msg


def test_tao_chapter_than_request(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    kq = chay(server.tao_chapter("Chương 1", "ja", "study"))
    r = fake.reqs[-1]
    assert (r["method"], r["path"]) == ("POST", "/api/v1/projects")
    assert json.loads(r["body"]) == {"name": "Chương 1", "source_lang": "ja",
                                     "intended_use": "study"}
    assert kq["id"] == PID


def test_tai_anh_multipart(fake, monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    f = tmp_path / "p1.png"
    f.write_bytes(png())
    kq = chay(server.tai_trang_len(PID, str(f), engine="google_fast"))
    r = fake.reqs[-1]
    assert r["path"] == f"/api/v1/projects/{PID}/pages"
    assert r["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="p1.png"' in r["body"]
    assert b'name="engine"\r\n\r\ngoogle_fast' in r["body"]
    assert kq["job_id"] == JOB


def test_tai_cbz_dung_endpoint_archive(fake, monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    f = tmp_path / "c1.cbz"
    f.write_bytes(b"PK\x03\x04")
    chay(server.tai_trang_len(PID, str(f)))
    assert fake.reqs[-1]["path"] == f"/api/v1/projects/{PID}/pages/archive"


def test_tai_tep_khong_ton_tai(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    assert "Không thấy tệp" in thong_diep_loi(server.tai_trang_len(PID, "/khong/co.png"))


def test_id_khong_hop_le():
    assert "UUID" in thong_diep_loi(server.xem_chapter("../etc/passwd"))


def test_xem_trang_detail(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    kq = chay(server.xem_trang(PAGE))
    assert fake.reqs[-1]["path"] == f"/api/v1/pages/{PAGE}/detail"
    assert kq["regions"][0]["translated_text"] == "Xin chào"


def test_xem_anh_thu_nho(fake, monkeypatch):
    from PIL import Image as P
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    img = chay(server.xem_anh_trang(PAGE, "xem_thu"))
    assert fake.reqs[-1]["path"] == f"/api/v1/pages/{PAGE}/typeset-preview"
    assert max(P.open(io.BytesIO(img.data)).size) == 1600


def test_sua_vung_patch_va_cho_canh_lai(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    kq = chay(server.sua_vung(REG, translated_text="Chào", bbox=[1, 2, 30, 40], font_size=18,
                              timeout=10))
    patch = [r for r in fake.reqs if r["method"] == "PATCH"][0]
    assert patch["path"] == f"/api/v1/regions/{REG}"
    assert json.loads(patch["body"]) == {"translated_text": "Chào",
                                         "bbox": {"x": 1, "y": 2, "w": 30, "h": 40},
                                         "font_size": 18}
    assert kq["canh_lai"]["xong"] is True and kq["canh_lai"]["status"] == "done"
    assert fake.job_polls >= 2


def test_sua_vung_khong_truong_nao(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    assert "Không có trường" in thong_diep_loi(server.sua_vung(REG))


def test_dich_lai_va_chay_lai_buoc(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    chay(server.dich_lai_vung(REG, engine="llm_context"))
    assert fake.reqs[-1]["path"] == f"/api/v1/regions/{REG}/re-translate?engine=llm_context"
    chay(server.chay_lai_buoc(PAGE, "ocr"))
    assert fake.reqs[-1]["path"] == f"/api/v1/pages/{PAGE}/retry-ocr"
    assert "buoc phải" in thong_diep_loi(server.chay_lai_buoc(PAGE, "bay"))


def test_batch_va_tien_do(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    kq = chay(server.chay_ca_chapter(PID, engine="google_fast"))
    assert json.loads(fake.reqs[-1]["body"]) == {"requested_pipeline": "full_pipeline",
                                                 "translation_engine": "google_fast"}
    assert kq["batch_run_id"] == BATCH
    assert chay(server.xem_tien_do_me(BATCH))["completed_pages"] == 1
    w = chay(server.cho_viec(BATCH, 5, "batch"))
    assert w["xong"] and w["loai"] == "batch"


def test_xuat_cho_va_tai(fake, monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    chay(server.xuat_chapter(PID, "cbz"))
    assert json.loads(fake.reqs[-1]["body"]) == {"format": "cbz"}
    w = chay(server.cho_viec(EXP, 5))  # auto: /jobs 404 -> /export-jobs
    assert w["loai"] == "export" and w["xong"] and w["tai_ve"].endswith(f"/{EXP}/download")
    assert MA_PHIEN not in json.dumps(w)
    out = chay(server.tai_file_xuat(EXP, str(tmp_path)))
    assert Path(out["duong_dan"]).read_bytes() == b"PK-fake-zip"
    assert Path(out["duong_dan"]).name == "ch1.cbz"
    assert "dinh_dang phải" in thong_diep_loi(server.xuat_chapter(PID, "pdf"))


def test_cho_viec_het_gio(fake, monkeypatch):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    fake.job_polls = -10_000  # luôn running
    w = chay(server.cho_viec(JOB, 0, "job"))
    assert w["xong"] is False and w["het_gio_cho"] is True


def test_cong_cu_dang_ky_va_annotations():
    tools = {t.name: t for t in chay(server.mcp.list_tools())}
    for ten in ("liet_ke_chapter", "tao_chapter", "xem_chapter", "tai_trang_len", "xem_trang",
                "xem_anh_trang", "sua_vung", "dich_lai_vung", "doc_lai_vung", "canh_lai_vung",
                "chay_lai_buoc", "chay_ca_chapter", "xem_tien_do_me", "xuat_chapter",
                "cho_viec", "tai_file_xuat"):
        assert ten in tools, ten
    assert tools["xem_trang"].annotations.readOnlyHint is True
    assert tools["tao_chapter"].annotations.readOnlyHint is False
    assert "không tin cậy" in server.INSTRUCTIONS.lower()


def test_khong_in_bi_mat_ra_stderr(fake, monkeypatch, capfd):
    monkeypatch.setenv("TRANSLATION_MA_PHIEN", MA_PHIEN)
    chay(server.liet_ke_chapter())
    out = capfd.readouterr()
    assert MA_PHIEN not in out.out + out.err
