"""Unit tests cho can chinh toa do Model 2 (`ai_gemini`) va co lap cache `_pro2v2` (`bo_nho_anh_dich`)."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path

import cv2
import numpy as np

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _ensure_optional_test_stubs() -> None:
    """Cai stub nhe cho `sqlalchemy`/`starlette`/`app.models` chi khi moi truong thieu container deps."""
    try:
        import sqlalchemy  # noqa: F401
        return
    except ImportError:
        pass

    if "sqlalchemy" not in sys.modules:
        sa = types.ModuleType("sqlalchemy")
        sa.select = lambda *args, **kwargs: None  # type: ignore[assignment]
        sa_ext = types.ModuleType("sqlalchemy.ext")
        sa_async = types.ModuleType("sqlalchemy.ext.asyncio")
        sa_async.AsyncSession = object  # type: ignore[attr-defined]
        sys.modules["sqlalchemy"] = sa
        sys.modules["sqlalchemy.ext"] = sa_ext
        sys.modules["sqlalchemy.ext.asyncio"] = sa_async

    if "starlette.concurrency" not in sys.modules:
        st = types.ModuleType("starlette")
        st_conc = types.ModuleType("starlette.concurrency")

        async def _run_in_threadpool(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        st_conc.run_in_threadpool = _run_in_threadpool  # type: ignore[attr-defined]
        sys.modules["starlette"] = st
        sys.modules["starlette.concurrency"] = st_conc

    if "app.models" not in sys.modules:
        pkg_models = types.ModuleType("app.models")
        pkg_models.__path__ = [str(_BACKEND_ROOT / "app" / "models")]  # type: ignore[attr-defined]
        for cls_name in ("OCRResult", "Page", "Project", "TextRegion", "TranslationResult", "TypesetResult"):
            setattr(pkg_models, cls_name, type(cls_name, (), {}))
        sys.modules["app.models"] = pkg_models

    if "app.models.enums" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "app.models.enums", _BACKEND_ROOT / "app" / "models" / "enums.py"
        )
        assert spec and spec.loader
        mod_enums = importlib.util.module_from_spec(spec)
        sys.modules["app.models.enums"] = mod_enums
        spec.loader.exec_module(mod_enums)

    if "app.services.typeset.paths" not in sys.modules:
        pkg_ts = types.ModuleType("app.services.typeset")
        mod_paths = types.ModuleType("app.services.typeset.paths")
        mod_paths.preview_relative_path = lambda pid, page_id: f"previews/{pid}/{page_id}.png"  # type: ignore[attr-defined]
        sys.modules["app.services.typeset"] = pkg_ts
        sys.modules["app.services.typeset.paths"] = mod_paths


_ensure_optional_test_stubs()

from app.models.enums import ChePipeline, SourceLang, TargetLang, TranslationEngine  # noqa: E402
from app.services.bo_nho_anh_dich import (  # noqa: E402
    _BO_NHO_BAM,
    _duong_dan_cache_cong_dong,
    ghi_nhan_trang_anh,
    tinh_bam_anh,
    thu_sao_chep_tu_cache,
    xoa_bo_nho_bam,
)
from app.services.detect.ai_gemini import (  # noqa: E402
    can_chinh_khung_theo_bong_bong,
    neo_khung_gemini_theo_ctd,
)
from app.services.detect.ctd import DetectedRegion  # noqa: E402
from app.services.interfaces import BBox  # noqa: E402


class TestModel2BBoxAlignment(unittest.TestCase):
    def test_can_chinh_khung_expands_clipped_bubble_bbox(self) -> None:
        img = np.full((800, 600), 220, dtype=np.uint8)
        # Ve bong bong thoai trang khep kin co vien den tai (80..280, 120..360)
        cv2.ellipse(img, (180, 240), (95, 115), 0, 0, 360, 255, -1)
        cv2.ellipse(img, (180, 240), (95, 115), 0, 0, 360, 0, 3)
        for y in (175, 225, 275):
            for x in range(130, 230, 16):
                cv2.rectangle(img, (x, y), (x + 9, y + 18), 10, -1)

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bubble.png"
            cv2.imwrite(str(p), img)
            # Gemini bi khoanh thieu dong cuoi (chi den y=245 thay vi ~293)
            clipped = DetectedRegion(
                bbox=BBox(x=124.0, y=170.0, w=112.0, h=75.0),
                confidence=0.95,
                cls=0,
                chu="Line one Line two Line three",
                ban_dich="Dong 1 Dong 2 Dong 3",
            )
            out = can_chinh_khung_theo_bong_bong(p, [clipped])
            self.assertEqual(len(out), 1)
            self.assertLessEqual(out[0].bbox.y, 178.0)
            self.assertGreaterEqual(out[0].bbox.y + out[0].bbox.h, 285.0)
            self.assertEqual(out[0].chu, clipped.chu)
            self.assertEqual(out[0].ban_dich, clipped.ban_dich)

    def test_can_chinh_khung_trims_hair_off_open_corner_text(self) -> None:
        img = np.full((800, 600), 255, dtype=np.uint8)
        # Mang toc den o goc tren trai trong khi cum chu nam lech phai
        cv2.rectangle(img, (320, 70), (410, 220), 8, -1)
        for y in (100, 130, 160):
            for x in range(425, 495, 14):
                cv2.rectangle(img, (x, y), (x + 8, y + 14), 12, -1)

        # Bong bong khac nam xa ben trai de kiem tra Pass B khong keo nham
        cv2.ellipse(img, (130, 140), (70, 80), 0, 0, 360, 255, -1)
        cv2.ellipse(img, (130, 140), (70, 80), 0, 0, 360, 0, 3)
        for y in (110, 145):
            for x in range(95, 165, 14):
                cv2.rectangle(img, (x, y), (x + 8, y + 14), 10, -1)

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "hair_open.png"
            cv2.imwrite(str(p), img)
            reg_other = DetectedRegion(
                bbox=BBox(x=90.0, y=105.0, w=80.0, h=60.0),
                confidence=0.9,
                cls=0,
                chu="Left bubble",
                ban_dich="Bong trai",
            )
            # Hop bao trum ca mang toc den (x=370..505) quanh cum chu (x=425..501)
            reg_hair = DetectedRegion(
                bbox=BBox(x=370.0, y=90.0, w=135.0, h=95.0),
                confidence=0.9,
                cls=0,
                chu="That unease",
                ban_dich="Cam giac bat an",
            )
            out = can_chinh_khung_theo_bong_bong(p, [reg_other, reg_hair])
            self.assertEqual(len(out), 2)
            # Hop ben phai phai cat bo mang toc den x=320..410 va khong nhay sang bong trai
            self.assertGreaterEqual(out[1].bbox.x, 415.0)
            self.assertGreater(out[1].bbox.w, 40.0)

    def test_neo_khung_gemini_theo_ctd_1_to_1_and_guards(self) -> None:
        g_ok = DetectedRegion(
            bbox=BBox(x=100.0, y=100.0, w=90.0, h=120.0),
            confidence=0.9,
            cls=0,
            chu="Original A",
            ban_dich="Dich A",
        )
        ctd_ok = DetectedRegion(bbox=BBox(x=104.0, y=102.0, w=82.0, h=114.0), confidence=0.9, cls=0)

        g_frag = DetectedRegion(
            bbox=BBox(x=300.0, y=300.0, w=100.0, h=160.0),
            confidence=0.9,
            cls=0,
            chu="Original B",
            ban_dich="Dich B",
        )
        # CTD bi cut thieu chieu cao (< 72% chieu cao Gemini) -> phai giu khung Gemini
        ctd_frag = DetectedRegion(bbox=BBox(x=305.0, y=305.0, w=90.0, h=80.0), confidence=0.9, cls=0)

        g_multi = DetectedRegion(
            bbox=BBox(x=500.0, y=100.0, w=120.0, h=140.0),
            confidence=0.9,
            cls=0,
            chu="Original C",
            ban_dich="Dich C",
        )
        ctd_c1 = DetectedRegion(bbox=BBox(x=505.0, y=105.0, w=110.0, h=60.0), confidence=0.8, cls=0)
        ctd_c2 = DetectedRegion(bbox=BBox(x=505.0, y=170.0, w=110.0, h=65.0), confidence=0.8, cls=0)

        snapped = neo_khung_gemini_theo_ctd(
            [g_ok, g_frag, g_multi],
            [ctd_ok, ctd_frag, ctd_c1, ctd_c2],
            image_path=None,
        )
        self.assertEqual(snapped[0].bbox, ctd_ok.bbox)
        self.assertEqual(snapped[0].chu, "Original A")
        self.assertEqual(snapped[0].ban_dich, "Dich A")
        self.assertEqual(snapped[1].bbox, g_frag.bbox)
        self.assertEqual(snapped[2].bbox, g_multi.bbox)


class _DummySession:
    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []

    async def get(self, model_cls, obj_id):
        if model_cls.__name__ == "Project":
            return types.SimpleNamespace(cau_hinh_rieng=False)
        self.calls.append(obj_id)
        return None


class _DummyStorage:
    def __init__(self) -> None:
        self.checked: list[str] = []

    def exists(self, rel_path: str) -> bool:
        self.checked.append(rel_path)
        return False


class TestModel2CacheIsolation(unittest.TestCase):
    def setUp(self) -> None:
        xoa_bo_nho_bam()

    def tearDown(self) -> None:
        xoa_bo_nho_bam()

    def test_duong_dan_cache_cong_dong_v2_separates_tiers(self) -> None:
        h = "a" * 64
        p_m1 = _duong_dan_cache_cong_dong(
            h, SourceLang.en, TranslationEngine.google_fast, ChePipeline.chi_chu, target_lang=TargetLang.vi
        )
        p_m2 = _duong_dan_cache_cong_dong(
            f"{h}_pro2v2", SourceLang.en, TranslationEngine.google_fast, ChePipeline.chi_chu, target_lang=TargetLang.vi
        )
        p_m3 = _duong_dan_cache_cong_dong(
            f"{h}_ultra3", SourceLang.en, TranslationEngine.llm_context, ChePipeline.chi_chu, target_lang=TargetLang.vi
        )
        self.assertTrue(p_m1.startswith("cache_cong_dong_v2/"))
        self.assertTrue(p_m2.startswith("cache_cong_dong_v2/"))
        self.assertIn("_pro2v2_en_vi_", p_m2)
        self.assertEqual(len({p_m1, p_m2, p_m3}), 3)

    def test_thu_sao_chep_pro2v2_never_falls_back_to_model1_or_stale(self) -> None:
        h = tinh_bam_anh(b"akagi-p17-test")
        stale_pid = uuid.uuid4()
        ghi_nhan_trang_anh(h, SourceLang.en, TranslationEngine.google_fast, ChePipeline.chi_chu, stale_pid)
        ghi_nhan_trang_anh(f"{h}_pro2", SourceLang.en, TranslationEngine.llm_context, ChePipeline.chi_chu, uuid.uuid4())
        self.assertTrue(_BO_NHO_BAM)

        session = _DummySession()
        storage = _DummyStorage()
        page_dich = types.SimpleNamespace(id=uuid.uuid4(), project_id=uuid.uuid4())

        hit = asyncio.run(
            thu_sao_chep_tu_cache(
                session,
                bam_anh=f"{h}_pro2v2",
                source_lang=SourceLang.en,
                target_lang=TargetLang.vi,
                engine=TranslationEngine.llm_context,
                che_do=ChePipeline.chi_chu,
                dich_page=page_dich,
                storage=storage,
            )
        )
        self.assertFalse(hit)
        self.assertEqual(session.calls, [])
        self.assertEqual(
            set(storage.checked),
            {f"cache_cong_dong_v2/{h}_pro2v2_en_vi_llm_context_chi_chu.json"},
        )


if __name__ == "__main__":
    unittest.main()
