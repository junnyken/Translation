"""E46 — engine nhận diện bằng Gemini.

Bài canh quan trọng nhất ở đây là `test_confidence_None_KHONG_bi_gan_co_thap`: Gemini không trả
điểm tin cậy, và cả hai cách xử lý "cho tiện" đều sai —

* điền 1.0 cho gọn ⇒ **bịa ra một con số không hề tồn tại**;
* coi `None` là thấp ⇒ **gắn cờ rà soát oan cho MỌI vùng**, và E23 đã đo được rằng cờ báo sai
  nhiều thì người dùng học cách phớt lờ nó, hỏng luôn cả cơ chế.

Và `test_mac_dinh_van_la_ctd`: engine mới bỏ sót 2/27 vùng trong khi model cũ sót 0/27, nên đổi
mặc định là âm thầm hạ chất lượng của mọi người dùng.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from app.services.detect.ai_gemini import (
    LOI_NHAC,
    SCHEMA,
    AIDetectError,
    AIGeminiDetector,
)


def _tra_loi(khung: list[list[int]], finish: str = "STOP") -> dict:
    return {"candidates": [{"finishReason": finish, "content": {"parts": [
        {"text": json.dumps([{"box": k} for k in khung])}]}}],
        "usageMetadata": {"totalTokenCount": 1280}}


@pytest.fixture
def gia_lap_api(monkeypatch):
    """Thay tầng HTTP. Trả về list để bài test soi được thân request đã gửi."""
    da_gui: list[dict] = []

    def dat(tra_loi=None, loi: Exception | None = None):
        def _urlopen(req, timeout=None):
            da_gui.append({"url": req.full_url, "than": json.loads(req.data)})
            if loi is not None:
                raise loi
            return io.BytesIO(json.dumps(tra_loi).encode())
        monkeypatch.setattr("urllib.request.urlopen", _urlopen)
        return da_gui

    return dat


@pytest.fixture
def anh(tmp_path):
    from PIL import Image

    p = tmp_path / "trang.png"
    Image.new("RGB", (1200, 1660), (255, 255, 255)).save(p)
    return str(p)


class TestToaDo:
    def test_doi_dung_thang_va_thu_tu(self, anh, gia_lap_api):
        """Toạ độ là `[ymin, xmin, ymax, xmax]` thang 0-1000 — ĐÃ xác minh bằng cách vẽ lên ảnh.

        Đảo nhầm thứ tự sẽ cho khung **trông hợp lý mà sai hoàn toàn**, và không một chỉ số nào
        phía sau bắt được.
        """
        gia_lap_api(_tra_loi([[100, 200, 300, 600]]))
        d = AIGeminiDetector(api_keys=["k"])
        r = d.detect_regions(anh)

        assert len(r) == 1
        b = r[0].bbox
        assert b.x == pytest.approx(200 / 1000 * 1200)   # xmin
        assert b.y == pytest.approx(100 / 1000 * 1660)   # ymin
        assert b.w == pytest.approx((600 - 200) / 1000 * 1200)
        assert b.h == pytest.approx((300 - 100) / 1000 * 1660)

    def test_khung_rong_hoac_dao_chieu_bi_BO(self, anh, gia_lap_api):
        """Bỏ hẳn, KHÔNG tự hoán vị cho thành khung hợp lệ — đó là đoán, không phải dữ liệu."""
        gia_lap_api(_tra_loi([[500, 500, 100, 100], [0, 0, 0, 0], [10, 10, 50, 50]]))
        r = AIGeminiDetector(api_keys=["k"]).detect_regions(anh)
        assert len(r) == 1

    def test_kep_ve_trong_bien_anh(self, anh, gia_lap_api):
        gia_lap_api(_tra_loi([[0, 0, 1200, 1200]]))     # vượt thang 1000
        b = AIGeminiDetector(api_keys=["k"]).detect_regions(anh)[0].bbox
        assert b.x + b.w <= 1200
        assert b.y + b.h <= 1660


class TestKhongBiaBangChung:
    def test_confidence_luon_None(self, anh, gia_lap_api):
        gia_lap_api(_tra_loi([[10, 10, 50, 50]]))
        assert AIGeminiDetector(api_keys=["k"]).detect_regions(anh)[0].confidence is None

    @pytest.mark.anyio
    async def test_confidence_None_di_het_duong_GHI_ma_khong_gan_co_thap(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
    ):
        """Chạy THẬT qua `run_detect_job`, không lặp lại logic ở đây.

        Đây là đối chứng cho đúng dòng đã vá trong `tasks.py`. Gỡ bản vá ra thì `None < 0.5`
        ném TypeError và bài này ĐỎ — đó là chủ ý. Một bài chỉ tính lại công thức trong chính
        nó thì xanh cả khi sản phẩm hỏng.
        """
        import uuid

        import sqlalchemy as sa

        from app.core.db_sync import sync_session
        from app.models import TextRegion
        from app.models.enums import RegionStatus
        from app.services.detect.ctd import DetectedRegion
        from app.services.interfaces import BBox
        from app.workers.tasks import run_detect_job

        proj = await client.post("/api/v1/projects", json={
            "name": "E46", "source_lang": "en", "intended_use": "study"})
        pid = proj.json()["id"]
        up = await client.post(f"/api/v1/projects/{pid}/pages",
                               files={"file": ("p.png", sample_page_image, "image/png")})
        page_id, job_id = up.json()["page_id"], up.json()["job_id"]

        fake_detector(regions=[
            DetectedRegion(bbox=BBox(x=10, y=10, w=50, h=20), confidence=None, cls=0),
            DetectedRegion(bbox=BBox(x=200, y=10, w=50, h=20), confidence=0.2, cls=0),
        ])
        run_detect_job(job_id)

        with sync_session() as s:
            rs = sorted(
                s.execute(sa.select(TextRegion).where(
                    TextRegion.page_id == uuid.UUID(page_id))).scalars(),
                key=lambda r: r.bbox_x,
            )
        assert len(rs) == 2
        assert rs[0].confidence is None, "không được bịa điểm cho engine không trả điểm"
        assert rs[0].status is RegionStatus.pending, (
            "confidence=None bị gắn cờ low_confidence — gắn oan MỌI vùng của engine AI"
        )
        assert rs[1].status is RegionStatus.low_confidence, (
            "điểm THẤP thật vẫn phải bị gắn cờ — bản vá không được nuốt luôn trường hợp này"
        )


class TestHongThiBao:
    def test_thieu_khoa_API_bao_ro_cach_sua(self, anh):
        with pytest.raises(AIDetectError) as e:
            AIGeminiDetector(api_keys=[]).detect_regions(anh)
        assert "GEMINI_API_KEYS" in str(e.value)
        assert "ctd" in str(e.value), "thông điệp phải chỉ được đường lùi"

    def test_doc_THAN_loi_HTTP_chu_khong_doan_theo_ma(self, anh, gia_lap_api):
        """400 của bậc pro hoá ra là 'model only works in thinking mode' — đoán theo mã HTTP là
        cách chắc chắn chẩn sai."""
        than = json.dumps({"error": {"message": "Budget 0 is invalid. This model only works in thinking mode."}})
        gia_lap_api(loi=urllib.error.HTTPError(
            "u", 400, "Bad Request", {}, io.BytesIO(than.encode())))
        with pytest.raises(AIDetectError) as e:
            AIGeminiDetector(api_keys=["k"]).detect_regions(anh)
        assert "thinking mode" in str(e.value)

    def test_JSON_hong_van_BAO_chu_khong_tra_rong(self, anh, gia_lap_api):
        """Kiểu hỏng nguy hiểm nhất đã đo được: model dừng giữa mảng mà vẫn báo STOP.

        Trả `[]` ở đây thì trang im lặng mất hết vùng chữ và không ai biết.
        """
        gia_lap_api({"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": '[{"box": [1,2,3,4]}, {"box": [5,6'}]}}]})
        with pytest.raises(AIDetectError) as e:
            AIGeminiDetector(api_keys=["k"]).detect_regions(anh)
        assert "STOP" in str(e.value), "thông điệp phải nêu finishReason để chẩn được"

    def test_KHONG_tu_lui_ve_model_cu(self, anh, gia_lap_api):
        """Tự lùi về `ctd` nghe an toàn nhưng người dùng sẽ tưởng đang chạy engine mình chọn,
        và một sự cố kéo dài sẽ không ai thấy."""
        gia_lap_api(loi=OSError("mạng chết"))
        with pytest.raises(AIDetectError):
            AIGeminiDetector(api_keys=["k"]).detect_regions(anh)


class TestThanRequest:
    def test_LUON_ep_schema(self, anh, gia_lap_api):
        """Bỏ `responseSchema` là mở lại đường hỏng âm thầm — đo được 24/30 so với 45/45."""
        gui = gia_lap_api(_tra_loi([[10, 10, 50, 50]]))
        AIGeminiDetector(api_keys=["k"]).detect_regions(anh)
        gc = gui[0]["than"]["generationConfig"]
        assert gc["responseSchema"] == SCHEMA
        assert gc["responseMimeType"] == "application/json"
        assert gc["temperature"] == 0.0, "nhiệt độ > 0 làm kết quả hết tất định"

    def test_loi_nhac_doi_khung_CHU_chu_khong_phai_BONG_BONG(self):
        """Nới lời nhắc này ra là quay lại đúng lỗi cũ: khung bong bóng ăn nét vẽ gấp 2,7 lần."""
        assert "TIGHT bounding box" in LOI_NHAC
        assert "Do NOT include the speech balloon" in LOI_NHAC
        assert "balloon and text area" not in LOI_NHAC

    def test_gui_anh_DA_THU_NHO(self, anh, gia_lap_api):
        """Gửi nguyên cỡ là đốt token vô ích — Gemini tính tiền theo ô 768×768."""
        gui = gia_lap_api(_tra_loi([]))
        AIGeminiDetector(api_keys=["k"], canh_toi_da=1024).detect_regions(anh)
        import base64

        from PIL import Image

        phan = gui[0]["than"]["contents"][0]["parts"][0]["inline_data"]
        with Image.open(io.BytesIO(base64.b64decode(phan["data"]))) as im:
            assert max(im.size) <= 1024

    def test_xoay_key_khi_loi_KHONG_phai_loi_cau_hinh(self, anh, gia_lap_api, monkeypatch):
        """401 thì thử key sau; 400 là lỗi cấu hình nên xoay key vô ích, phải ném ngay."""
        goi: list[str] = []

        def _urlopen(req, timeout=None):
            goi.append(req.full_url)
            if len(goi) == 1:
                raise urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b"{}"))
            return io.BytesIO(json.dumps(_tra_loi([[10, 10, 50, 50]])).encode())

        monkeypatch.setattr("urllib.request.urlopen", _urlopen)
        r = AIGeminiDetector(api_keys=["k1", "k2"]).detect_regions(anh)
        assert len(r) == 1
        assert len(goi) == 2, "phải thử sang key thứ hai"


class TestCongTac:
    def test_mac_dinh_van_la_ctd(self):
        """Engine AI sót 2/27 vùng, `ctd` sót 0/27. Đổi mặc định = âm thầm hạ chất lượng."""
        from app.core.config import Settings

        assert Settings(_env_file=None).detect_engine == "ctd"

    def test_get_detector_doi_theo_cong_tac(self, monkeypatch):
        from app.workers import tasks

        # Vá vào CHÍNH đối tượng `tasks.py` đang dùng, không phải `get_settings()` hiện thời:
        # `tasks.py` gán `settings = get_settings()` lúc IMPORT nên giữ tham chiếu riêng. Vá
        # nhầm chỗ thì bài xanh khi chạy một mình và ĐỎ khi chạy cả bộ — đúng cách nó đã hỏng.
        monkeypatch.setattr(tasks.settings, "detect_engine", "ai_gemini")
        monkeypatch.setattr(tasks.settings, "gemini_api_keys", "k1,k2")
        tasks.reset_detector()
        try:
            d = tasks.get_detector()
            assert isinstance(d, AIGeminiDetector)
            assert d.api_keys == ["k1", "k2"]
        finally:
            tasks.reset_detector()
