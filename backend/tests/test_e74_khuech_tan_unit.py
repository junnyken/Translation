"""E74 — xoá chữ bằng mô hình khuếch tán (SDXL/FLUX qua diffusers) — cần GPU.

Workspace dev KHÔNG có GPU, nên `torch`/`diffusers` ở đây là bản GIẢ gắn vào `sys.modules`. Bài này
kiểm phần MÃ CỦA DỰ ÁN (cỡ đưa vào model, chỉ thay điểm ảnh trong mặt nạ, chia cụm, tô phẳng trước,
lỗi rõ khi thiếu GPU/thư viện, chọn engine) — KHÔNG chứng minh chất lượng vẽ của SDXL. Chạy thật
trên GPU là việc còn nợ (REPORT_E74).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.services.inpaint.khuech_tan import KhuechTanInpainter, co_dua_vao_model
from app.services.inpaint.lama import InpaintFailed
from app.services.interfaces import BBox


# ---------- bản giả torch + diffusers ----------

class _PipeGia:
    def __init__(self):
        self.goi = []
        self.loi = None

    def to(self, _thiet_bi):
        return self

    def set_progress_bar_config(self, **_kw):
        pass

    def __call__(self, **kw):
        if self.loi:
            raise self.loi
        self.goi.append(kw)
        w, h = kw["width"], kw["height"]
        assert kw["image"].size == (w, h) and kw["mask_image"].size == (w, h)
        return types.SimpleNamespace(images=[Image.new("RGB", (w, h), (128, 128, 128))])


@pytest.fixture
def gia(monkeypatch):
    pipe = _PipeGia()
    trang_thai = {"cuda": True, "nap": 0}

    torch = types.ModuleType("torch")
    torch.float16, torch.float32 = "f16", "f32"
    torch.cuda = types.SimpleNamespace(is_available=lambda: trang_thai["cuda"])

    class _Gen:
        def __init__(self, device="cpu"):
            pass

        def manual_seed(self, _s):
            return self
    torch.Generator = _Gen

    diffusers = types.ModuleType("diffusers")

    class _Auto:
        @staticmethod
        def from_pretrained(model_id, **_kw):
            trang_thai["nap"] += 1
            trang_thai["model"] = model_id
            return pipe
    diffusers.AutoPipelineForInpainting = _Auto
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "diffusers", diffusers)
    return pipe, trang_thai


def _trang(tmp_path: Path, nen_tranh: bool = True, cao: int = 600, rong: int = 800) -> Path:
    rng = np.random.default_rng(3)
    anh = (rng.integers(0, 256, (cao, rong, 3), dtype=np.uint8) if nen_tranh
           else np.full((cao, rong, 3), 255, np.uint8))
    p = tmp_path / "trang.png"
    Image.fromarray(anh).save(p)
    return p


def _may(**kw):
    kw.setdefault("model_id", "diffusers/stable-diffusion-xl-1.0-inpainting-0.1")
    return KhuechTanInpainter(**kw)


# ---------- cỡ đưa vào model ----------

@pytest.mark.parametrize("rong, cao", [(3000, 2000), (1024, 1024), (800, 600), (100, 60),
                                       (2000, 100), (37, 41)])
def test_co_dua_vao_model(rong, cao):
    w, h = co_dua_vao_model(rong, cao, 1024)
    assert w % 16 == 0 and h % 16 == 0
    assert max(w, h) <= 1024 + 8, "cạnh dài không vượt trần (sai số làm tròn bội 16)"
    if 1024 * min(rong, cao) / max(rong, cao) >= 256:
        assert min(w, h) >= 240, "ô thường: cạnh ngắn được nâng lên ~256"


# ---------- đường chạy ----------

def test_chi_thay_diem_anh_trong_mat_na_va_khong_ghi_de_goc(gia, tmp_path):
    pipe, tt = gia
    src = _trang(tmp_path)
    goc = np.asarray(Image.open(src)).copy()
    sach = _may(dilate_ratio=0.0).inpaint(str(src), [BBox(300, 200, 120, 60)])
    out = np.asarray(Image.open(sach))
    assert np.array_equal(np.asarray(Image.open(src)), goc), "ảnh gốc bị ghi đè"
    assert (out[200:260, 300:420] == 128).all(), "trong mặt nạ phải là ảnh model vẽ"
    ngoai = np.ones(out.shape[:2], bool)
    ngoai[200:260, 300:420] = False
    assert np.array_equal(out[ngoai], goc[ngoai]), "ngoài mặt nạ phải giữ từng điểm ảnh"
    assert len(pipe.goi) == 1 and tt["nap"] == 1
    k = pipe.goi[0]
    assert k["width"] % 16 == 0 and k["height"] % 16 == 0 and k["strength"] == 0.99
    assert "no text" in k["prompt"] and "watermark" in k["negative_prompt"]


def test_luon_chay_theo_cum_ke_ca_trang_nho(gia, tmp_path):
    pipe, _ = gia
    src = _trang(tmp_path, cao=900, rong=900)
    _may(dilate_ratio=0.0, tile_margin=32).inpaint(
        str(src), [BBox(40, 40, 80, 40), BBox(700, 780, 80, 40)])
    assert len(pipe.goi) == 2, "hai vùng xa nhau ⇒ hai cụm, không đưa cả trang vào model"


def test_vung_nen_phang_thi_khong_nap_model(gia, tmp_path):
    pipe, tt = gia
    src = _trang(tmp_path, nen_tranh=False)
    anh = np.asarray(Image.open(src)).copy()
    anh[210:250, 310:410:4] = 0  # "chữ" trên nền trắng
    Image.fromarray(anh).save(src)
    _may().inpaint(str(src), [BBox(300, 200, 120, 60)])
    assert tt["nap"] == 0 and pipe.goi == [], "E69 tô phẳng trước — không cần GPU cho vùng này"


def test_khong_co_gpu_thi_bao_ro(gia, tmp_path):
    _pipe, tt = gia
    tt["cuda"] = False
    with pytest.raises(InpaintFailed, match="khuech_tan_khong_co_gpu"):
        _may().inpaint(str(_trang(tmp_path)), [BBox(300, 200, 120, 60)])


def test_thieu_thu_vien_thi_bao_ro_khong_lui_ve_lama(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "diffusers", None)
    with pytest.raises(InpaintFailed, match="khuech_tan_thieu_thu_vien"):
        _may().inpaint(str(_trang(tmp_path)), [BBox(300, 200, 120, 60)])


def test_loi_cuda_thanh_loi_doc_duoc(gia, tmp_path):
    pipe, _ = gia
    pipe.loi = RuntimeError("CUDA out of memory")
    with pytest.raises(InpaintFailed, match="khuech_tan_loi_suy_dien.*out of memory"):
        _may().inpaint(str(_trang(tmp_path)), [BBox(300, 200, 120, 60)])


def test_get_inpainter_chon_theo_cau_hinh(monkeypatch):
    from app.services.inpaint.lama import LamaInpainter
    from app.workers import tasks

    for engine, lop in (("khuech_tan", KhuechTanInpainter), ("lama", LamaInpainter)):
        monkeypatch.setattr(tasks.settings, "inpaint_engine", engine)
        tasks.reset_inpainter()
        may = tasks.get_inpainter()
        assert type(may) is lop
    tasks.reset_inpainter()


def test_chi_truyen_tham_so_pipeline_nhan(gia, tmp_path):
    """Mỗi họ model một chữ ký — truyền `negative_prompt` cho pipeline không nhận là TypeError."""
    pipe, _ = gia
    nhan = []

    def _hep(prompt, image, mask_image, width, height, strength, num_inference_steps,
             guidance_scale, generator):
        nhan.append(prompt)
        return types.SimpleNamespace(images=[Image.new("RGB", (width, height), (9, 9, 9))])

    may = _may(dilate_ratio=0.0)
    may._pipe = _hep  # đã "nạp" sẵn: pipeline là một hàm có chữ ký hẹp
    may.inpaint(str(_trang(tmp_path)), [BBox(300, 200, 120, 60)])
    assert nhan, "pipeline chữ ký hẹp vẫn phải được gọi"
