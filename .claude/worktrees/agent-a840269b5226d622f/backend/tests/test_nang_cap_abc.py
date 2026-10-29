"""Unit tests cho các nâng cấp Nhóm B & Nhóm C (E92, E93, E94)."""
from __future__ import annotations

import uuid

from app.models.enums import ChePipeline, SourceLang, TranslationEngine
from app.services.bo_nho_anh_dich import (
    _BO_NHO_BAM,
    ghi_nhan_trang_anh,
    tinh_bam_anh,
    xoa_bo_nho_bam,
)
from app.services.interfaces import BBox
from app.services.ocr.engines import PaddleOCREngine, get_ocr_engine, has_meaningful_text
from app.services.translate.khung_tranh import vung_cham_mep_cat_doc
from app.services.translate.reading_order import direction_for


def test_source_lang_ko_chon_paddle_korean_va_doc_ltr():
    assert SourceLang.ko.value == "ko"
    eng = get_ocr_engine(SourceLang.ko)
    assert isinstance(eng, PaddleOCREngine)
    assert eng.lang == "korean"
    assert direction_for("ko") == "ltr"
    assert has_meaningful_text("안녕하세요")


def test_vung_cham_mep_cat_doc_webtoon():
    boxes = {
        "tren": BBox(x=100, y=2, w=120, h=60),
        "giua": BBox(x=100, y=400, w=120, h=80),
        "duoi": BBox(x=100, y=1950, w=120, h=48),
    }
    kq = vung_cham_mep_cat_doc(boxes, cao_trang=2000, le_px=6)
    assert kq["mep_tren"] == {"tren"}
    assert kq["mep_duoi"] == {"duoi"}


def test_bo_nho_bam_ghi_nhan_va_gioi_han():
    xoa_bo_nho_bam()
    bam = tinh_bam_anh(b"anh-thu-nghiem")
    assert len(bam) == 64
    pid = uuid.uuid4()
    ghi_nhan_trang_anh(bam, SourceLang.ko, TranslationEngine.google_fast, ChePipeline.chi_chu, pid)
    assert pid in _BO_NHO_BAM[(bam, "ko", "google_fast", "chi_chu")]
    xoa_bo_nho_bam()


def test_schema_gop_dich_va_loi_nhac_kem_boi_canh(tmp_path, monkeypatch):
    import io
    import json
    from PIL import Image
    from app.services.detect.ai_gemini import (
        SCHEMA_GOP_DICH,
        AIGeminiDetector,
        xay_loi_nhac_gop_dich,
    )

    assert SCHEMA_GOP_DICH["items"]["required"] == ["box", "text", "ban_dich", "doan"]
    loi_nhac = xay_loi_nhac_gop_dich("ja", "vi", "### Thoại trang trước:\n- 婆婆 → Bà")
    assert "婆婆 → Bà" in loi_nhac
    assert "ban_dich" in loi_nhac

    anh = tmp_path / "p.png"
    Image.new("RGB", (1000, 1000), (255, 255, 255)).save(anh)
    phan_hoi = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                [
                                    {
                                        "box": [100, 200, 200, 400],
                                        "text": "婆婆こそ気をつけてな",
                                        "ban_dich": "Bà cũng nhớ cẩn thận đấy nhé.",
                                        "doan": False,
                                    }
                                ]
                            )
                        }
                    ]
                },
            }
        ],
        "usageMetadata": {"totalTokenCount": 512},
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: io.BytesIO(json.dumps(phan_hoi).encode("utf-8")),
    )
    det = AIGeminiDetector(api_keys=["k"])
    kq = det.detect_va_dich_regions(str(anh), "ja", "vi", boi_canh=loi_nhac)
    assert len(kq) == 1
    assert kq[0].chu == "婆婆こそ気をつけてな"
    assert kq[0].ban_dich == "Bà cũng nhớ cẩn thận đấy nhé."
    assert kq[0].doan is False
    assert det.last_usage["totalTokenCount"] == 512


def test_google_fast_song_song_va_khu_trung_lap(monkeypatch):
    from app.services.translate import engines as mod
    from app.services.translate.engines import GoogleTranslateEngine

    eng = GoogleTranslateEngine(max_workers=4)
    dem_goi: list[str] = []

    def fake_translate_one(text: str, sl: str, tl: str) -> str:
        dem_goi.append(text)
        return f"VI:{text}"

    monkeypatch.setattr(eng, "_translate_one", fake_translate_one)
    # Giữ `_http_json is _http_json_mac_dinh` để kích hoạt nhánh song song + khử trùng lặp
    assert mod._http_json is mod._http_json_mac_dinh
    ra = eng.translate(["カラン", "こんにちは", "カラン", "  "], "ja", "vi")
    assert ra == ["VI:カラン", "VI:こんにちは", "VI:カラン", ""]
    assert len(dem_goi) == 2, "câu trùng lặp 'カラン' chỉ được gọi mạng 1 lần"
