"""E74 — xoá chữ bằng mô hình KHUẾCH TÁN (SDXL inpainting mặc định; FLUX.1 tuỳ chọn) — CẦN GPU.

## Vì sao có

LaMa vá nền phẳng và hoạ tiết lặp tốt, nhưng vùng chữ đè lên NÉT VẼ (tóc, áo, cảnh) thì nó chỉ nhoè
ra một mảng. Mô hình khuếch tán VẼ LẠI được nét. Koharu có hai lựa chọn như vậy (`flux2-klein`,
`rorem-mixed` = SDXL inpainting — `koharu-pipeline/src/config.rs`); lời nhắc mặc định dưới đây
lấy từ `rorem_mixed/mod.rs` (MIT OR Apache-2.0).

## Dùng lại, không viết lại

Kế thừa `LamaInpainter` và chỉ thay ĐÚNG bước gọi model (`_chay_model`) + bước nạp model. Mọi thứ
đã kiểm chứng của đường xoá chữ giữ nguyên: tô phẳng E69 trước (vùng nền phẳng không cần GPU), chia
cụm theo bong bóng, chỉ thay điểm ảnh TRONG mặt nạ, không ghi đè ảnh gốc, bước OCR kiểm lại.

Khác LaMa ở hai chỗ, đều có lý do:
- **Luôn chạy theo cụm** (`whole_page_max_mpx=0`): model khuếch tán được huấn luyện quanh 1024px,
  đưa cả trang vào là vừa chậm vừa vẽ lệch tỉ lệ.
- **Không có trần diện tích ô cắt** (`max_crop_mpx=0`): ô lớn được THU NHỎ về `canh_dai_toi_da`
  trước khi vào model, nên bộ nhớ không leo theo cỡ ô như LaMa.

## Ranh giới

Không có GPU (hoặc thiếu torch/diffusers) ⇒ `InpaintFailed` nói rõ thiếu gì. KHÔNG lặng lẽ lùi về
LaMa: người chọn engine này phải biết trang của họ không đi qua nó — đúng nguyên tắc
`InpaintWeightsMissing` của M4.

## Model nào dùng được (đã kiểm trên diffusers 0.41.0, 15-10-2026)

`AutoPipelineForInpainting` nhận các họ: SD 1.x/2.x, **SDXL**, SD3, **FLUX.1** (`FluxInpaintPipeline`),
Qwen-Image, Z-Image… **FLUX.2-klein (thứ Koharu dùng) KHÔNG nằm trong đó**: `Flux2KleinPipeline` không
nhận `mask_image` — Koharu xoá chữ bằng nó qua stable-diffusion.cpp, không qua diffusers.

Giấy phép do người cài tự kiểm: SDXL inpainting 0.1 là CreativeML Open RAIL++-M; FLUX.1-schnell là
Apache-2.0; FLUX.1-dev CẤM dùng thương mại. Cấu hình gợi ý cho FLUX.1-schnell: 4 bước, guidance 0.
"""
from __future__ import annotations

import logging
import threading

import numpy as np
from PIL import Image

from app.services.inpaint.lama import InpaintFailed, LamaInpainter

logger = logging.getLogger(__name__)

#: Koharu `rorem_mixed/mod.rs` — lời nhắc mặc định cho SDXL inpainting trên manga.
LOI_NHAC_MAC_DINH = (
    "clean manga illustration, crisp black line art, flat colors, seamless original background, "
    "clean white speech bubble, no text"
)
LOI_NHAC_AM_MAC_DINH = (
    "text, letters, words, symbols, watermark, signature, blurry, smudged, dirty, gray artifacts, "
    "extra objects, photorealistic"
)
#: Cạnh ảnh đưa vào model phải chia hết 8 (VAE nén 8 lần). Koharu làm tròn 16 cho FLUX — 16 an
#: toàn cho cả hai.
BOI_SO_CANH = 16
CANH_NHO_NHAT = 256


def co_dua_vao_model(rong: int, cao: int, canh_dai_toi_da: int) -> tuple[int, int]:
    """Cỡ (rộng, cao) để đưa vào model: thu nhỏ cho cạnh dài ≤ trần, làm tròn bội 16, ≥ 256.

    PHÓNG TO ô nhỏ cho cạnh ngắn lên 256: model khuếch tán vẽ rác ở độ phân giải quá thấp. Nhưng
    cạnh dài KHÔNG BAO GIỜ vượt trần — ô dẹt 2000×100 mà ép cạnh ngắn lên 256 thì cạnh dài thành
    5120px và GPU hết bộ nhớ; ô đó chịu cạnh ngắn dưới 256.
    """
    tran = canh_dai_toi_da / max(rong, cao)
    he_so = min(1.0, tran)
    if min(rong, cao) * he_so < CANH_NHO_NHAT:
        he_so = min(CANH_NHO_NHAT / min(rong, cao), tran)

    def _tron(v: float) -> int:
        return max(BOI_SO_CANH, int(round(v / BOI_SO_CANH)) * BOI_SO_CANH)

    return _tron(rong * he_so), _tron(cao * he_so)


class KhuechTanInpainter(LamaInpainter):
    """`IInpainter` bằng diffusers. Cùng chữ ký `inpaint(image_path, masks)` với LaMa."""

    def __init__(
        self,
        model_id: str,
        device: str = "cuda",
        dilate_ratio: float = 0.08,
        so_buoc: int = 20,
        strength: float = 0.99,
        guidance: float = 7.0,
        canh_dai_toi_da: int = 1024,
        seed: int = 0,
        loi_nhac: str = LOI_NHAC_MAC_DINH,
        loi_nhac_am: str = LOI_NHAC_AM_MAC_DINH,
        thu_muc_cache: str | None = None,
        tile_margin: int = 128,
        flat_fill: bool = True,
    ) -> None:
        super().__init__(
            weights_path=model_id,
            device=device,
            dilate_ratio=dilate_ratio,
            whole_page_max_mpx=0.0,
            tile_margin=tile_margin,
            max_crop_mpx=0.0,
            flat_fill=flat_fill,
        )
        self.model_id = model_id
        self.so_buoc = so_buoc
        self.strength = strength
        self.guidance = guidance
        self.canh_dai_toi_da = canh_dai_toi_da
        self.seed = seed
        self.loi_nhac = loi_nhac
        self.loi_nhac_am = loi_nhac_am
        self.thu_muc_cache = thu_muc_cache
        self._pipe = None
        self._khoa_pipe = threading.Lock()

    def _nap_pipe(self):
        if self._pipe is not None:
            return self._pipe
        with self._khoa_pipe:
            if self._pipe is not None:
                return self._pipe
            try:
                import torch
                from diffusers import AutoPipelineForInpainting
            except ImportError as exc:
                raise InpaintFailed(
                    "khuech_tan_thieu_thu_vien: cần torch + diffusers (image worker GPU — "
                    "deploy/docker-compose.gpu.yml). Đang chạy image CPU thì đặt INPAINT_ENGINE=lama."
                ) from exc
            dung_gpu = self.device.lower() in ("cuda", "gpu")
            if dung_gpu and not torch.cuda.is_available():
                raise InpaintFailed(
                    "khuech_tan_khong_co_gpu: INPAINT_ENGINE=khuech_tan cần GPU NVIDIA mà máy này "
                    "không thấy GPU nào (torch.cuda.is_available() = False). Đặt INPAINT_ENGINE=lama."
                )
            logger.info("Nạp model khuếch tán %s (%s)", self.model_id, self.device)
            pipe = AutoPipelineForInpainting.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if dung_gpu else torch.float32,
                cache_dir=self.thu_muc_cache,
            )
            self._pipe = pipe.to("cuda" if dung_gpu else "cpu")
            if hasattr(self._pipe, "set_progress_bar_config"):
                self._pipe.set_progress_bar_config(disable=True)
            return self._pipe

    def _get_session(self):  # LaMa nạp ONNX ở đây — engine này không dùng ONNX
        return self._nap_pipe()

    def _chay_model(self, rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Vẽ lại một ô. `rgb` HWC [0,1], `mask` HW (1 = xoá). Trả HWC [0,1] CÙNG cỡ ô."""
        cao, rong = mask.shape
        pipe = self._nap_pipe()
        w, h = co_dua_vao_model(rong, cao, self.canh_dai_toi_da)
        anh = Image.fromarray(np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)).resize(
            (w, h), Image.LANCZOS)
        # Mặt nạ thu phóng NEAREST rồi vẫn là nhị phân — không để mép mờ thành "xoá một nửa".
        mat_na = Image.fromarray((mask > 0.5).astype(np.uint8) * 255).resize((w, h), Image.NEAREST)

        import inspect

        import torch

        bo_sinh = torch.Generator(device="cpu").manual_seed(self.seed)
        tham_so = dict(
            prompt=self.loi_nhac,
            negative_prompt=self.loi_nhac_am,
            image=anh,
            mask_image=mat_na,
            width=w,
            height=h,
            strength=self.strength,
            num_inference_steps=self.so_buoc,
            guidance_scale=self.guidance,
            generator=bo_sinh,
        )
        # Chỉ truyền tham số pipeline này NHẬN: mỗi họ model một chữ ký, truyền thừa là TypeError.
        try:
            # `signature(pipe)` chứ không `signature(pipe.__call__)`: với một hàm, `__call__` là
            # method-wrapper có chữ ký (*args, **kwargs) ⇒ bước lọc bị bỏ qua im lặng.
            nhan = inspect.signature(pipe).parameters
            if not any(p.kind is p.VAR_KEYWORD for p in nhan.values()):
                tham_so = {k: v for k, v in tham_so.items() if k in nhan}
        except (TypeError, ValueError):
            pass
        try:
            ket = pipe(**tham_so).images[0]
        except Exception as exc:  # noqa: BLE001 — lỗi CUDA/OOM phải thành lỗi đọc được của trang
            raise InpaintFailed(f"khuech_tan_loi_suy_dien: {type(exc).__name__}: {exc}") from exc
        ra = ket.convert("RGB")
        if ra.size != (rong, cao):
            ra = ra.resize((rong, cao), Image.LANCZOS)
        return np.asarray(ra, dtype=np.float32) / 255.0
