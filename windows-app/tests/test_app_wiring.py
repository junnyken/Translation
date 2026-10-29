"""Exercise the real desktop controller headlessly; NOT a Windows/Tk UAT."""
import importlib.util
import io
import sys
import types
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def desktop(monkeypatch):
    # Linux runner has no Tk. Replace widgets only, keep application functions real.
    tkinter = types.ModuleType("tkinter")
    tkinter.Tk = object
    for name in ("filedialog", "messagebox", "scrolledtext", "simpledialog", "ttk"):
        setattr(tkinter, name, types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    spec = importlib.util.spec_from_file_location("desktop_under_test", Path(__file__).parents[1] / "app_dich_truyen_windows.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Widget:
    def __init__(self):
        self.values = {}

    def config(self, **values):
        self.values.update(values)


def make_image(path):
    Image.new("RGB", (32, 48), "white").save(path)


def app_fixture(desktop, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    make_image(source / "1.jpg")
    app = desktop.AppDichTruyenWindows.__new__(desktop.AppDichTruyenWindows)
    app.yeu_cau_dung = False
    app.dang_chay = True
    app.btn_start, app.btn_stop, app.lbl_tien_do = Widget(), Widget(), Widget()
    app.after = lambda _, callback: callback()
    app.logs = []
    app.ghi_log = app.logs.append
    app._cap_nhat_han_muc = lambda: None
    app.run_options = dict(server="https://api.invalid", token="not-written-to-disk", account="test-account",
                           name="book", output=str(tmp_path / "output"), url="",
                           source_lang="en", target_lang="vi", font="comic", engine="local_gguf",
                           glossary="", cbz=True, pdf=False, longstrip=False,
                           chapters=[dict(ten="Chapter-001", url=f"local_dir::{source}")])
    app.run_options.update({"from": 1, "to": 1})
    return app


def test_controller_does_not_report_success_or_export_on_translation_failure(desktop, monkeypatch, tmp_path):
    app = app_fixture(desktop, tmp_path)
    monkeypatch.setattr(desktop, "dich_anh_local_gguf_tren_may_khach", lambda *a, **k: [])
    app._luong_dich_hang_loat()
    assert "cần xử lý" in app.lbl_tien_do.values["text"]
    assert not list((tmp_path / "output").rglob("*.cbz"))
    assert app.dang_chay is False


def test_controller_success_packs_and_resume_does_not_call_model(desktop, monkeypatch, tmp_path):
    app = app_fixture(desktop, tmp_path)
    monkeypatch.setattr(desktop, "dich_anh_local_gguf_tren_may_khach", lambda *a, **k: [
        dict(chu_goc="Hello", ban_dich="Chào", x=1, y=1, w=20, h=20)])
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, *a: data)
    app._luong_dich_hang_loat()
    assert "xử lý đủ 1" in app.lbl_tien_do.values["text"]
    assert len(list((tmp_path / "output").rglob("*.cbz"))) == 1
    manifest = next((tmp_path / "output").rglob("trang-thai.json"))
    assert "not-written-to-disk" not in manifest.read_text()
    monkeypatch.setattr(desktop, "dich_anh_local_gguf_tren_may_khach", lambda *a, **k: pytest.fail("already completed"))
    app._luong_dich_hang_loat()
    assert "xử lý đủ 1" in app.lbl_tien_do.values["text"]


def test_source_download_does_not_send_machine_cookie(desktop, monkeypatch):
    seen = []
    def fake_open(request, timeout):
        seen.append(dict(request.header_items()))
        return io.BytesIO(b"image")
    monkeypatch.setattr(desktop.urllib.request, "urlopen", fake_open)
    desktop.goi_http("https://source.invalid/page.jpg", nguon_ngoai=True)
    assert "Cookie" not in seen[0]
    assert "X-ma-may-tinh" not in seen[0]
    desktop.goi_http("https://api.invalid/healthz")
    assert "Cookie" in seen[1]


def test_link_count_mismatch_stops_before_upload(desktop, monkeypatch, tmp_path):
    app = app_fixture(desktop, tmp_path)
    monkeypatch.setattr(desktop.simpledialog, "askinteger", lambda *a, **k: 2, raising=False)
    with pytest.raises(desktop.NeedsAttention, match="Chưa xác nhận đủ"):
        app._xac_nhan_so_trang("chapter", 1)


def test_controller_automatic_exports_are_named_as_drafts(desktop, monkeypatch, tmp_path):
    app = app_fixture(desktop, tmp_path)
    app.run_options.update(pdf=True, longstrip=True)
    monkeypatch.setattr(desktop, "dich_anh_local_gguf_tren_may_khach", lambda *a, **k: [
        dict(chu_goc="Hello", ban_dich="Chào", x=1, y=1, w=20, h=20)])
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, *a: data)
    exported = []
    monkeypatch.setattr(desktop, "xuat_pdf_va_longstrip_chapter",
                        lambda folder, name, root, **options: exported.append((name, options)))
    app._luong_dich_hang_loat()
    assert [path.name for path in (tmp_path / "output").rglob("*.cbz")] == ["Chapter-001-ban-nhap.cbz"]
    assert exported[0][0] == "Chapter-001-ban-nhap"
    assert exported[0][1]["xuat_pdf"] is True
    assert exported[0][1]["xuat_longstrip"] is True
    assert not list((tmp_path / "output").rglob("*v1.zip"))


def test_cloud_controller_reconciles_lost_upload_by_persisted_key(desktop, monkeypatch, tmp_path):
    import json
    app = app_fixture(desktop, tmp_path)
    app.run_options["engine"] = "google_fast"
    attempts = []
    accepted = {}
    def submit(url, data, **options):
        key = options["fields"]["request_key"]
        attempts.append(key)
        accepted.update(page_id="server-page", request_key=key, cau_hinh_rieng=True,
                        xong=True, image_width=32, image_height=48,
                        vung=[dict(chu_goc="Hello", ban_dich="Chào", x=1, y=1, w=20, h=20)])
        raise OSError("response lost after server accepted")
    lookups = []
    def http(url, **options):
        if url.endswith("/healthz"):
            return json.dumps({"translation_capabilities": {
                "private_context_v1": True, "idempotent_upload_v1": True}}).encode()
        if "/doc-truyen/yeu-cau/" in url:
            lookups.append(url.rsplit("/", 1)[-1])
            return json.dumps(accepted).encode()
        pytest.fail(f"unexpected HTTP call: {url}")
    monkeypatch.setattr(desktop, "gui_multipart_trang", submit)
    monkeypatch.setattr(desktop, "goi_http", http)
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, *a: data)
    app._luong_dich_hang_loat()
    assert "cần xử lý" in app.lbl_tien_do.values["text"]
    assert not list((tmp_path / "output").rglob("*.cbz"))
    app._luong_dich_hang_loat()
    assert "xử lý đủ 1" in app.lbl_tien_do.values["text"]
    assert attempts == lookups
    assert len(attempts) == 1
    assert len(list((tmp_path / "output").rglob("*-ban-nhap.cbz"))) == 1


def test_multi_file_and_multi_comic_classification_and_batch_separation(desktop, monkeypatch, tmp_path):
    import zipfile

    # 1. Tạo nhiều file gói của nhiều truyện khác nhau + 1 gói chứa nhiều chapter + các ảnh rời theo tập
    z1 = tmp_path / "One_Piece_Chap_02.cbz"
    with zipfile.ZipFile(z1, "w") as zf:
        buf = io.BytesIO()
        Image.new("RGB", (32, 48), "white").save(buf, "JPEG")
        zf.writestr("001.jpg", buf.getvalue())

    z2 = tmp_path / "One_Piece_Chap_01.cbz"
    with zipfile.ZipFile(z2, "w") as zf:
        buf = io.BytesIO()
        Image.new("RGB", (32, 48), "white").save(buf, "JPEG")
        zf.writestr("001.jpg", buf.getvalue())

    z_multi = tmp_path / "Naruto_Pack.zip"
    with zipfile.ZipFile(z_multi, "w") as zf:
        buf = io.BytesIO()
        Image.new("RGB", (32, 48), "white").save(buf, "JPEG")
        zf.writestr("Naruto/Chap 01/01.jpg", buf.getvalue())
        zf.writestr("Naruto/Chap 02/01.jpg", buf.getvalue())

    img_dir = tmp_path / "PepperCarrot"
    img_dir.mkdir()
    p39 = img_dir / "E39P01.jpg"
    p35 = img_dir / "E35P01.jpg"
    make_image(p39)
    make_image(p35)

    ds_chap = desktop.phan_loai_nhieu_file_truyen([z1, z2, z_multi, p39, p35])
    pairs = [(c["ten_truyen"], c["ten"]) for c in ds_chap]
    assert pairs == [
        ("Naruto", "Chapter-001"),
        ("Naruto", "Chapter-002"),
        ("One_Piece", "Chapter-001"),
        ("One_Piece", "Chapter-002"),
        ("PepperCarrot", "Chapter-035"),
        ("PepperCarrot", "Chapter-039"),
    ]

    # 2. Chạy _luong_dich_hang_loat cho toàn bộ 6 chapter của 3 bộ truyện cùng lúc
    app = app_fixture(desktop, tmp_path)
    app.run_options.update(
        chapters=ds_chap,
        to=len(ds_chap),
        cbz=True,
    )
    monkeypatch.setattr(
        desktop,
        "dich_anh_local_gguf_tren_may_khach",
        lambda *a, **k: [dict(chu_goc="Hello", ban_dich="Chào", x=1, y=1, w=20, h=20)],
    )
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, *a: data)
    app._luong_dich_hang_loat()

    out_dir = tmp_path / "output"
    assert (out_dir / "Naruto" / "Chapter-001" / "001.jpg").is_file()
    assert (out_dir / "Naruto" / "Chapter-002" / "001.jpg").is_file()
    assert (out_dir / "One_Piece" / "Chapter-001" / "001.jpg").is_file()
    assert (out_dir / "One_Piece" / "Chapter-002" / "001.jpg").is_file()
    assert (out_dir / "PepperCarrot" / "Chapter-035" / "001.jpg").is_file()
    assert (out_dir / "PepperCarrot" / "Chapter-039" / "001.jpg").is_file()
    summary_file = out_dir / "DANH-SACH-TRUYEN-CHAPTER.txt"
    assert summary_file.is_file()
    summary_text = summary_file.read_text(encoding="utf-8")
    assert "Truyện: Naruto  |  Chapter: Chapter-001" in summary_text
    assert "Truyện: One_Piece  |  Chapter: Chapter-002" in summary_text
    assert "Truyện: PepperCarrot  |  Chapter: Chapter-039" in summary_text


def test_multi_link_scanning_orders_chapters_and_infers_series_name(desktop, monkeypatch):
    def fake_http(url, **kwargs):
        if "naruto" in url:
            return (
                b'<html><h1>Naruto</h1>'
                b'<a href="/manga/naruto/chapter-2">Chap 2</a>'
                b'<a href="/manga/naruto/chapter-1">Chap 1</a></html>'
            )
        return (
            b'<html><h1>Bleach</h1>'
            b'<a href="/manga/bleach/chapter-5">Chap 5</a></html>'
        )

    monkeypatch.setattr(desktop, "goi_http", fake_http)
    ds = desktop.quet_danh_sach_chapter_tu_url(
        "https://example.org/manga/naruto ; https://example.org/manga/bleach"
    )
    assert [(c["ten_truyen"], c["ten"]) for c in ds] == [
        ("bleach", "Chapter-005"),
        ("naruto", "Chapter-001"),
        ("naruto", "Chapter-002"),
    ]


def test_step1_url_adapters_series_slug_mangadex_and_mangaplus(desktop, monkeypatch):
    import json

    # 1. Suy đoán tên bộ truyện từ URL chapter có gắn hậu tố -chapter-25 (như steel-ball-run.com)
    ten_sbr = desktop.suy_doan_ten_truyen_tu_url(
        "https://steel-ball-run.com/manga/jojos-bizarre-adventure-steel-ball-run-chapter-25/"
    )
    assert ten_sbr == "jojos-bizarre-adventure-steel-ball-run"

    # 2. Mở rộng toàn bộ danh sách chapter từ 1 link chapter lẻ
    def fake_sbr_http(url, **kwargs):
        return (
            b'<html><a href="https://steel-ball-run.com/manga/jojos-bizarre-adventure-steel-ball-run-chapter-24/">Chap 24</a>'
            b'<a href="https://steel-ball-run.com/manga/jojos-bizarre-adventure-steel-ball-run-chapter-25/">Chap 25</a>'
            b'<a href="https://steel-ball-run.com/manga/jojos-bizarre-adventure-steel-ball-run-chapter-26/">Chap 26</a></html>'
        )

    monkeypatch.setattr(desktop, "goi_http", fake_sbr_http)
    ds_sbr = desktop.quet_danh_sach_chapter_tu_url(
        "https://steel-ball-run.com/manga/jojos-bizarre-adventure-steel-ball-run-chapter-25/",
        mo_rong_ca_bo=True,
    )
    assert [c["ten"] for c in ds_sbr] == ["Chapter-024", "Chapter-025", "Chapter-026"]
    assert all(c["ten_truyen"] == "jojos-bizarre-adventure-steel-ball-run" for c in ds_sbr)

    # 3. MANGA Plus (Shueisha Protobuf API v3 + Plus-Vw-Token + 128-hex XOR decryption)
    fake_mp_key = "ab" * 64
    fake_mp_vw = "cd" * 16
    fake_mp_proto = (
        b"https://jumpg-assets3.tokyo-cdn.com/secure/title/100171/chapter/1009923/manga_page/high/1.jpg?hash=abc&expires=1793210400"
        b"\x10\x90\x06\x18\xf9\x08*\x80\x01" + fake_mp_key.encode("ascii")
        + b"#001\nhttps://jumpg-assets.tokyo-cdn.com/secure/title/100171/chapter/1009921/chapter_thumbnail/1.jpg"
        + b"#003\nhttps://jumpg-assets.tokyo-cdn.com/secure/title/100171/chapter/1009923/chapter_thumbnail/3.jpg"
        + b"https://jumpg-webapi.tokyo-cdn.com/www/sns_share?title_id=100171&chapter_id=1009923*\x08Dandadan2\x04#003"
        + b"\x9a\x01\x20" + fake_mp_vw.encode("ascii")
    )
    monkeypatch.setattr(desktop, "goi_http", lambda url, **kwargs: fake_mp_proto)
    ds_mp = desktop.quet_danh_sach_chapter_tu_url("https://mangaplus.shueisha.co.jp/viewer/1009923", mo_rong_ca_bo=False)
    assert ds_mp == [
        {
            "ten_truyen": "Dandadan",
            "so": 3.0,
            "ten": "Chapter-003",
            "url": "https://mangaplus.shueisha.co.jp/viewer/1009923",
            "nhan": "Dandadan / Chapter-003",
        }
    ]
    ds_mp_all = desktop.quet_danh_sach_chapter_tu_url("https://mangaplus.shueisha.co.jp/viewer/1009923", mo_rong_ca_bo=True)
    assert [c["ten"] for c in ds_mp_all] == ["Chapter-001", "Chapter-003"]
    imgs_mp = desktop.quet_anh_trang_truyen_trong_chapter("https://mangaplus.shueisha.co.jp/viewer/1009923")
    assert len(imgs_mp) == 1
    assert f"#mp_key={fake_mp_key}&mp_vw={fake_mp_vw}" in imgs_mp[0]

    # 4. MangaDex API Adapter hoạt động khi kết nối thông suốt & báo rõ khi bị ISP reset (WinError 10054)
    md_url = "https://mangadex.org/chapter/ed85458b-d5de-4fe8-8a1c-f43b2a466198/6"

    def fake_md_ok(url, **kwargs):
        if "/chapter/" in url:
            return json.dumps({
                "data": {
                    "id": "ed85458b-d5de-4fe8-8a1c-f43b2a466198",
                    "attributes": {"chapter": "12", "translatedLanguage": "en"},
                    "relationships": [{"type": "manga", "id": "m-1", "attributes": {"title": {"en": "JoJo Part 7"}}}],
                }
            }).encode("utf-8")
        if "/at-home/server/" in url:
            return json.dumps({
                "baseUrl": "https://uploads.mangadex.org",
                "chapter": {"hash": "abc123hash", "data": ["p1.jpg", "p2.jpg"]},
            }).encode("utf-8")
        raise AssertionError(url)

    monkeypatch.setattr(desktop, "goi_http", fake_md_ok)
    ds_md = desktop.quet_danh_sach_chapter_tu_url(md_url)
    assert ds_md[0]["ten_truyen"] == "JoJo-Part-7"
    assert ds_md[0]["ten"] == "Chapter-012"
    imgs_md = desktop.quet_anh_trang_truyen_trong_chapter(md_url)
    assert imgs_md == [
        "https://uploads.mangadex.org/data/abc123hash/p1.jpg",
        "https://uploads.mangadex.org/data/abc123hash/p2.jpg",
    ]

    def fake_md_reset(url, **kwargs):
        raise ConnectionResetError("[WinError 10054] An existing connection was forcibly closed by the remote host")

    monkeypatch.setattr(desktop, "goi_http", fake_md_reset)
    with pytest.raises(desktop.NeedsAttention, match="10054"):
        desktop.quet_danh_sach_chapter_tu_url(md_url)


def test_step2_quick_review_rerender_updates_ledger_without_llm_call(desktop, monkeypatch, tmp_path):
    import review_delivery

    app = app_fixture(desktop, tmp_path)
    monkeypatch.setattr(
        desktop,
        "dich_anh_local_gguf_tren_may_khach",
        lambda *a, **k: [dict(chu_goc="Hello", ban_dich="Bản nháp cũ", x=2, y=2, w=24, h=20)],
    )
    app._luong_dich_hang_loat()

    chap_dir = tmp_path / "output" / "book" / "Chapter-001"
    assert (chap_dir / "trang-thai.json").is_file()

    # Cấm gọi lại model AI trong lúc vẽ lại trang
    monkeypatch.setattr(
        desktop,
        "dich_anh_local_gguf_tren_may_khach",
        lambda *a, **k: pytest.fail("Không được gọi lại model AI khi chỉ vẽ lại trang rà soát"),
    )
    regions_moi = [dict(chu_goc="Hello", ban_dich="Xin chào đã sửa!", x=2, y=2, w=24, h=20)]
    rendered = desktop.ve_lai_trang_trong_ho_so_chapter(chap_dir, 0, regions_moi, font_style="bangers")
    assert len(rendered) > 100

    # Sau khi vẽ lại, kiểm tra review_delivery duyệt và xuất gói bàn giao hợp lệ
    with review_delivery.open_chapter(chap_dir) as ledger:
        assert ledger.data["pages"][0]["regions"][0]["ban_dich"] == "Xin chào đã sửa!"
        st = review_delivery.chapter_status(ledger)
        sha = st["pages"][0]["sha256"]
        review_delivery.record_review(
            ledger, 0, decision="approved", reviewer="tester", expected_sha256=sha, confirmed=True
        )
        zip_out = tmp_path / "output" / "Chapter-001-ban-giao.zip"
        receipt = review_delivery.export_delivery(ledger, zip_out)
        assert zip_out.is_file()
        assert receipt["pages"][0]["sha256"] == sha


def test_step3_multilang_ocr_pack_checker_returns_4_languages(desktop):
    kq = desktop.kiem_tra_goi_ocr_windows()
    assert set(kq.keys()) == {"en", "ja", "ko", "zh"}
    for lang, info in kq.items():
        assert "ten" in info and "lenh_cai" in info and isinstance(info["ho_tro"], bool)


def test_step4_local_ocr_gpu_fallback_and_chrome_extension_bridge(desktop, monkeypatch):
    import base64
    import json

    buf = io.BytesIO()
    Image.new("RGB", (120, 120), "white").save(buf, "JPEG")
    img_bytes = buf.getvalue()

    # Giả lập máy chưa bật Ollama -> local_ocr_gpu tự động chuyển sang OCR cục bộ + dịch văn bản nhanh 0đ
    def fake_gguf_down(*a, **k):
        raise desktop.LocalServerUnavailableError("Ollama chưa bật")

    monkeypatch.setattr(desktop, "_ket_noi_qwen3_vl_cuc_bo", fake_gguf_down)
    monkeypatch.setattr(
        desktop,
        "nhan_dien_bong_thoai_ocr_cuc_bo",
        lambda data, ngon_ngu_nguon="ja": [
            {"x": 10, "y": 15, "w": 80, "h": 40, "chu_goc": "You heard them!"}
        ],
    )
    monkeypatch.setattr(
        desktop,
        "goi_http",
        lambda url, **kw: json.dumps([[["Bạn đã nghe thấy họ!", "You heard them!"]]]).encode("utf-8"),
    )
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, regions, font: b"rendered-jpeg")

    kq_bridge = desktop.xu_ly_yeu_cau_local_bridge(
        {
            "image_base64": base64.b64encode(img_bytes).decode("ascii"),
            "source_lang": "en",
            "target_lang": "vi",
            "che_do": "ve_anh",
        }
    )
    assert kq_bridge["xong"] is True
    assert kq_bridge["engine"] == "local_bridge_windows_app"
    # Hậu kiểm tự động đổi 'Bạn' -> 'Cậu'
    assert kq_bridge["vung"][0]["ban_dich"] == "Cậu đã nghe thấy họ!"
    assert kq_bridge["anh_da_dich_data_url"].startswith("data:image/jpeg;base64,")


def test_step5_resilient_retry_prefetch_and_silent_pages_in_batch_mode(desktop, monkeypatch, tmp_path):
    import urllib.error

    buf1 = io.BytesIO()
    Image.new("RGB", (40, 48), "white").save(buf1, "JPEG")
    img_page1 = buf1.getvalue()

    buf2 = io.BytesIO()
    Image.new("RGB", (40, 48), "black").save(buf2, "JPEG")
    img_page2_silent = buf2.getvalue()

    app = app_fixture(desktop, tmp_path)
    app.run_options.update(
        auto_confirm_link_pages=True,
        chapters=[
            dict(
                ten_truyen="Dandadan",
                ten="Chapter-003",
                url="https://mangaplus.shueisha.co.jp/viewer/1009923",
                sources=["https://cdn.invalid/p1.jpg", "https://cdn.invalid/p2_silent.jpg"],
            )
        ],
    )

    so_lan_goi = {"p1": 0, "p2": 0}
    monkeypatch.setattr(desktop.time, "sleep", lambda *_: None)

    def flaky_http(url, **kwargs):
        if "p1.jpg" in url:
            so_lan_goi["p1"] += 1
            if so_lan_goi["p1"] == 1:
                raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)
            return img_page1
        if "p2_silent.jpg" in url:
            so_lan_goi["p2"] += 1
            return img_page2_silent
        raise AssertionError(url)

    monkeypatch.setattr(desktop, "goi_http", flaky_http)
    monkeypatch.setattr(
        desktop,
        "dich_anh_local_gguf_tren_may_khach",
        lambda data, **kw: (
            [dict(chu_goc="Hi", ban_dich="Chào", x=2, y=2, w=20, h=20)]
            if data == img_page1
            else []
        ),
    )
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, *a: data)

    app._luong_dich_hang_loat()
    assert so_lan_goi["p1"] == 2  # Tự động retry vượt lỗi HTTP 503 ở lần đầu
    assert "xử lý đủ 1" in app.lbl_tien_do.values["text"]
    assert (tmp_path / "output" / "Dandadan" / "Chapter-003" / "001.jpg").is_file()
    assert (tmp_path / "output" / "Dandadan" / "Chapter-003" / "002.jpg").read_bytes() == img_page2_silent


def test_step6_host_to_client_multipart_api_gateway(desktop, monkeypatch):
    buf = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(buf, "JPEG")
    img_bytes = buf.getvalue()

    monkeypatch.setattr(
        desktop,
        "dich_anh_local_ocr_gpu_tang_toc",
        lambda data, **kw: [{"x": 5, "y": 5, "w": 40, "h": 25, "chu_goc": "Hello", "ban_dich": "Xin chào máy khách!"}],
    )
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, regions, font: b"rendered-client-jpg")

    boundary = "----TestHostBoundary123"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="source_lang"\r\n\r\nen\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="target_lang"\r\n\r\nvi\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="request_key"\r\n\r\nreq-key-001\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="001.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + img_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    fields, parsed_img = desktop._tach_multipart_form_data(f"multipart/form-data; boundary={boundary}", body)
    assert fields["source_lang"] == "en"
    assert fields["request_key"] == "req-key-001"
    assert parsed_img == img_bytes

    doc1 = desktop.xu_ly_multipart_doc_truyen_tu_may_khach(fields, parsed_img)
    assert doc1["xong"] is True
    assert doc1["cau_hinh_rieng"] is True
    assert doc1["request_key"] == "req-key-001"
    assert doc1["vung"][0]["ban_dich"] == "Xin chào máy khách!"

    # Gửi lại cùng request_key phải trả đúng page_id cũ (chống trùng idempotent_upload_v1)
    doc2 = desktop.xu_ly_multipart_doc_truyen_tu_may_khach(fields, parsed_img)
    assert doc2["page_id"] == doc1["page_id"]
    assert desktop._BRIDGE_IMAGES_STORE[doc1["page_id"]] == b"rendered-client-jpg"


def test_step7_model2_cloud_guest_and_apikey_gateway(desktop, monkeypatch, tmp_path):
    import json

    app = app_fixture(desktop, tmp_path)
    app.run_options["engine"] = "google_fast"
    app.run_options["token"] = ""  # Khách vãng lai HWID (2 trang miễn phí/ngày, chưa cần token)

    seen_fields = []

    def submit(url, data, **options):
        seen_fields.append(dict(options["fields"]))
        return json.dumps(
            {
                "page_id": "guest-page-1",
                "cau_hinh_rieng": True,
                "xong": True,
                "image_width": 32,
                "image_height": 48,
                "vung": [dict(chu_goc="Hi", ban_dich="Chào", x=1, y=1, w=20, h=20)],
            }
        ).encode("utf-8")

    def http(url, **options):
        if url.endswith("/healthz"):
            return json.dumps({"status": "ok", "llm_configured": True, "translate_default_engine": "llm_context"}).encode("utf-8")
        pytest.fail(f"unexpected HTTP call: {url}")

    monkeypatch.setattr(desktop, "gui_multipart_trang", submit)
    monkeypatch.setattr(desktop, "goi_http", http)
    monkeypatch.setattr(desktop, "xoa_chu_va_ve_ban_dich_tren_anh", lambda data, *a: data)

    app._luong_dich_hang_loat()
    assert "xử lý đủ 1" in app.lbl_tien_do.values["text"]
    assert len(seen_fields) == 1
    assert "request_key" not in seen_fields[0]






