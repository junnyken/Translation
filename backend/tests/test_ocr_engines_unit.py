"""Unit — factory chọn engine + hành vi engine (M3 §7.1)."""
import pytest

from app.models.enums import OCREngine, SourceLang
from app.services.interfaces import BBox, IOCREngine
from app.services.ocr.engines import (
    MangaOCREngine,
    OCREngineUnavailable,
    PaddleOCREngine,
    UnsupportedSourceLang,
    get_ocr_engine,
    has_meaningful_text,
)


class TestFactory:
    def test_ja_chon_manga_ocr(self):
        engine = get_ocr_engine("ja")
        assert isinstance(engine, MangaOCREngine)
        assert engine.engine_enum is OCREngine.manga_ocr

    @pytest.mark.parametrize("lang,paddle_lang", [("zh", "ch"), ("en", "en")])
    def test_zh_en_chon_paddleocr_dung_lang(self, lang, paddle_lang):
        engine = get_ocr_engine(lang)
        assert isinstance(engine, PaddleOCREngine)
        assert engine.lang == paddle_lang
        assert engine.engine_enum is OCREngine.paddle_ocr

    def test_nhan_ca_enum_source_lang(self):
        assert isinstance(get_ocr_engine(SourceLang.ja), MangaOCREngine)

    @pytest.mark.parametrize("bad", ["vi", "ko", "JA", "", "fr"])
    def test_lang_la_bao_loi_ro_khong_fallback_am_tham(self, bad):
        with pytest.raises(UnsupportedSourceLang) as exc:
            get_ocr_engine(bad)
        assert bad in str(exc.value) or "không được hỗ trợ" in str(exc.value)

    def test_ca_hai_engine_dung_protocol_iocrengine(self):
        assert isinstance(get_ocr_engine("ja"), IOCREngine)
        assert isinstance(get_ocr_engine("en"), IOCREngine)


class TestMangaOCR:
    def test_tra_confidence_none_khong_bia_so(self, tmp_path, monkeypatch):
        from PIL import Image

        img = tmp_path / "p.png"
        Image.new("RGB", (200, 100), "white").save(img)

        engine = MangaOCREngine()
        monkeypatch.setattr(engine, "_get_model", lambda: (lambda crop: "こんにちは"))
        text, confidence = engine.recognize(str(img), BBox(0, 0, 100, 50))
        assert text == "こんにちは"
        assert confidence is None  # thư viện không cung cấp điểm tin cậy

    def test_thieu_thu_vien_bao_loi_ro(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def _fail(name, *a, **kw):
            if name == "manga_ocr":
                raise ImportError("no module named manga_ocr")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", _fail)
        with pytest.raises(OCREngineUnavailable):
            MangaOCREngine()._load()


class TestPaddleParse:
    def test_doc_duoc_format_dict_moi(self):
        result = [{"rec_texts": ["HELLO", "WORLD"], "rec_scores": [0.9, 0.8]}]
        text, conf = PaddleOCREngine._parse(result)
        assert text == "HELLO\nWORLD"
        assert conf == pytest.approx(0.85)

    def test_doc_duoc_format_list_cu(self):
        result = [[[[[0, 0], [1, 0], [1, 1], [0, 1]], ("HELLO", 0.7)]]]
        text, conf = PaddleOCREngine._parse(result)
        assert text == "HELLO"
        assert conf == pytest.approx(0.7)

    def test_ket_qua_rong(self):
        assert PaddleOCREngine._parse([]) == ("", None)
        assert PaddleOCREngine._parse(None) == ("", None)

    def test_khong_co_score_thi_confidence_none(self):
        text, conf = PaddleOCREngine._parse([{"rec_texts": ["X"], "rec_scores": []}])
        assert text == "X"
        assert conf is None


class TestMeaningfulText:
    @pytest.mark.parametrize("text", ["HELLO", "こんにちは", "你好", "Xin chào", "42"])
    def test_co_chu_that(self, text):
        assert has_meaningful_text(text)

    @pytest.mark.parametrize("text", ["", "   ", None, "...", "!!!", "|||", "。。。"])
    def test_khong_co_chu(self, text):
        assert not has_meaningful_text(text)


class TestPaddleRuntimeFlags:
    def test_mac_dinh_tat_onednn(self):
        """paddlepaddle 3.3.1 vỡ ở nhánh oneDNN trên CPU -> mặc định phải TẮT."""
        kwargs = PaddleOCREngine(lang="en").build_kwargs()
        assert kwargs["enable_mkldnn"] is False
        assert kwargs["lang"] == "en"
        assert kwargs["device"] == "cpu"

    def test_factory_truyen_co_xuong_engine(self):
        engine = get_ocr_engine("zh", paddle_enable_mkldnn=True)
        assert engine.build_kwargs()["enable_mkldnn"] is True

    def test_manga_engine_khong_dinh_dang_co_paddle(self):
        assert not hasattr(get_ocr_engine("ja"), "build_kwargs")


class TestPaddleThuTuDong:
    def test_sap_lai_dong_theo_toa_do_tren_xuong_duoi(self):
        """Đo thật: PaddleOCR trả 'OUT!' trước 'LOOK' dù LOOK nằm trên."""
        result = [{
            "rec_texts": ["OUT!", "LOOK"],
            "rec_scores": [0.99, 0.98],
            "rec_polys": [
                [[194, 126], [300, 126], [300, 170], [194, 170]],   # dòng dưới
                [[188, 85], [300, 85], [300, 125], [188, 125]],     # dòng trên
            ],
        }]
        text, conf = PaddleOCREngine._parse(result)
        assert text == "LOOK\nOUT!"
        assert conf == pytest.approx(0.985)

    def test_cung_hang_thi_sap_trai_sang_phai(self):
        result = [{
            "rec_texts": ["PHAI", "TRAI"],
            "rec_scores": [0.9, 0.9],
            "rec_polys": [
                [[500, 10], [600, 10], [600, 50], [500, 50]],
                [[100, 10], [200, 10], [200, 50], [100, 50]],
            ],
        }]
        assert PaddleOCREngine._parse(result)[0] == "TRAI\nPHAI"

    def test_khong_co_toa_do_thi_giu_nguyen_thu_tu(self):
        result = [{"rec_texts": ["MOT", "HAI"], "rec_scores": [0.9, 0.9]}]
        assert PaddleOCREngine._parse(result)[0] == "MOT\nHAI"

    def test_khong_sua_ky_tu_nao_trong_text(self):
        """Chỉ sắp thứ tự dòng — lỗi chính tả của OCR giữ nguyên cho M5 xử lý."""
        result = [{"rec_texts": ["HELLC"], "rec_scores": [0.99]}]
        assert PaddleOCREngine._parse(result)[0] == "HELLC"


def test_tat_phan_loai_huong_trang_cho_crop_bubble():
    """Bộ phân loại hướng TRANG xoay ngược crop bubble 180° -> phải tắt.

    Bằng chứng đo thật: cùng 1 crop, bật thì trả ['OUT!','LOOK'] (y sai), tắt thì trả
    ['LOOK','OUT!'] khớp ảnh. Xem docs/TEST_LOG.md § M3.
    """
    kwargs = PaddleOCREngine(lang="en").build_kwargs()
    assert kwargs["use_doc_orientation_classify"] is False
    assert kwargs["use_doc_unwarping"] is False
    # nhận diện hướng DÒNG chữ thì vẫn giữ
    assert kwargs["use_textline_orientation"] is True
