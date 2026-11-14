"""Engine OCR — chọn theo Project.source_lang (M3).

- `ja`      → manga-ocr (transformer, kha-white/manga-ocr-base)
- `zh`,`en` → PaddleOCR

Import thư viện OCR đều là import TRỄ, chỉ xảy ra trong worker khi thực sự nhận diện.
Tiến trình API không bao giờ nạp (có guardrail test canh).
"""
from __future__ import annotations

import logging
import re
import threading

from PIL import Image, ImageFilter, ImageOps

from app.models.enums import OCREngine, SourceLang
from app.services.interfaces import BBox
from app.services.ocr.crop import crop_region

logger = logging.getLogger(__name__)

#: Bảng quy đổi chữ số & dấu câu Full-width (Nhật/Trung) sang Half-width chuẩn để dịch thuật chính xác hơn.
_BANG_CHUAN_HOA_FULLWIDTH = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ！？",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!?",
)


def chuan_hoa_van_ban_ocr(text: str) -> str:
    """Hậu xử lý văn bản OCR: chuẩn hoá chữ số/chữ cái full-width, nối từ gạch ngang xuống dòng, gộp dấu chấm lửng và khoảng trắng thừa."""
    if not text:
        return ""
    cleaned = text.translate(_BANG_CHUAN_HOA_FULLWIDTH)
    # Khử gạch nối tách âm tiết khi xuống dòng trong bóng thoại hẹp (VD: "some-\nthing" -> "something")
    cleaned = re.sub(r"([A-Za-z]{2,})-\s*\n\s*([a-z]{2,})", r"\1\2", cleaned)
    cleaned = re.sub(r"[・･]{3,}", "…", cleaned)
    cleaned = re.sub(r"\.{3,}", "…", cleaned)
    cleaned = re.sub(r"[ \t\u3000]+", " ", cleaned)
    return "\n".join(line.strip() for line in cleaned.splitlines() if line.strip()).strip()


def _la_bong_thoai_nen_toi(crop_rgb: Image.Image) -> bool:
    """Phát hiện khung thoại nền tối / đen có chữ sáng (narration box, suy nghĩ nội tâm, hồi tưởng)."""
    w, h = crop_rgb.size
    if w < 16 or h < 16:
        return False
    px = crop_rgb.load()
    step_x = max(1, w // 24)
    step_y = max(1, h // 24)
    total = 0
    dark = 0
    bright = 0
    sum_lum = 0.0
    for y in range(0, h, step_y):
        for x in range(0, w, step_x):
            r, g, b = px[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            sum_lum += lum
            total += 1
            if lum <= 85:
                dark += 1
            elif lum >= 175:
                bright += 1
    if total == 0:
        return False
    mean_lum = sum_lum / total
    return mean_lum < 105.0 and (dark / total) >= 0.52 and 0.04 <= (bright / total) <= 0.42


def tien_xu_ly_crop_ocr(
    crop: Image.Image, *, for_layout: bool = False, dao_cuc_nen_toi: bool = True
) -> Image.Image:
    """Tiền xử lý thích ứng theo từng khung hình (Per-Frame Adaptive OCR Preprocessing).

    - Đảm bảo ảnh ở hệ màu `RGB` hoặc `L` trước khi cân bằng tương phản (tránh lỗi `mode P` của PIL).
    - Tự động phát hiện khung dẫn chuyện nền tối chữ trắng (`_la_bong_thoai_nen_toi`) và đảo cực
      (`ImageOps.invert`) để mô hình OCR đọc chữ đen trên nền sáng chuẩn xác mà không làm lệch toạ độ.
    - Giữ nguyên kích thước nếu `for_layout=True` (để không làm lệch toạ độ đa giác dòng chữ của PaddleOCR)
      hoặc nếu ảnh thử nghiệm quá nhỏ (< 16px).
    - Với vùng chữ thật có cạnh ngắn nhỏ (16..42px — thường là chữ lầm bầm, chú thích lề trang),
      phóng đại 2× bằng bộ lọc Lanczos kèm làm nét nhẹ (UnsharpMask) và cân bằng tương phản tự động
      để giảm tỷ lệ đọc nhầm nét kanji/hangul/comic font dính nhau.
    """
    w, h = crop.size
    if w < 16 or h < 16:
        return crop
    out = crop.convert("RGB") if crop.mode not in ("RGB", "L") else crop
    if not for_layout and min(w, h) < 42 and max(w, h) <= 600:
        resample = getattr(Image, "Resampling", Image).LANCZOS
        out = out.resize((w * 2, h * 2), resample=resample)
    try:
        if dao_cuc_nen_toi and _la_bong_thoai_nen_toi(out.convert("RGB") if out.mode != "RGB" else out):
            out = ImageOps.invert(out.convert("RGB"))
        out = ImageOps.autocontrast(out, cutoff=1)
        if not for_layout and min(w, h) < 64:
            out = out.filter(ImageFilter.UnsharpMask(radius=1.0, percent=115, threshold=3))
    except Exception:  # noqa: BLE001
        return crop
    return out

#: Ký tự "rác" thường gặp khi model đoán bừa trên vùng không có chữ.
_MEANINGFUL = re.compile(r"[0-9A-Za-z぀-ヿ㐀-鿿＀-￯À-ỹ가-힣ㄱ-ㆎᄀ-ᇿ]")


def has_meaningful_text(text: str) -> bool:
    """True nếu chuỗi có ít nhất 1 ký tự chữ/số thật (không chỉ khoảng trắng/dấu câu)."""
    return bool(_MEANINGFUL.search(text or ""))


def dem_ky_tu_co_nghia(text: str) -> int:
    """Đếm ký tự chữ/số thật. Dùng khi "có hay không" là ngưỡng quá lỏng.

    Sinh ra ở E23: phép kiểm chứng xoá chữ dùng `has_meaningful_text` (>=1 ký tự) và gắn cờ
    `inpaint_needs_review` cho 7/24 trang — mà **cả 11 vùng bị gắn cờ đều chỉ ra ĐÚNG MỘT ký tự**
    ('O' x4, 'X' x2, 'G', '1', 'C', 'è', và một '中' trên trang tiếng Anh). Đó là hình mà OCR bịa
    ra từ nét cong/góc còn lại trên nền đã xoá, không phải chữ chưa xoá.

    KHÔNG đổi `has_meaningful_text`: nó còn dùng cho `needs_manual` của bước OCR, nơi một ký tự
    đơn VẪN là chữ đọc được thật. Hai câu hỏi khác nhau thì hai hàm khác nhau.
    """
    return len(_MEANINGFUL.findall(text or ""))


_KY_TU_HINH_HOC_DON = frozenset("Oo0Il1|VvXx+*•·○●◯△▲▽▼◁▷◇□■")


def vung_dang_xoa_chu(text: str, confidence: float | None,
                      min_conf: float, min_ky_tu: int) -> bool:
    """Vùng này có đáng XOÁ CHỮ không?

    ## Vì sao cần

    Khung nhận diện còn làm **mask cho LaMa**, nên khoanh nhầm nét vẽ là **xoá mất nét vẽ**.
    Đã chứng minh được thiệt hại: chạy bước xoá chữ với các vùng `comic-text-detector` khoanh
    trên một trang truyện có hiệu ứng phát sáng thì **toàn bộ ánh sáng, tia lấp lánh và vật
    phát quang bị xoá sạch**, chỉ còn nền tối phẳng.

    ## Luật

    Chỉ xoá vùng mà ta **sẽ vẽ chữ dịch đè lên**. Vùng không đọc ra chữ thì không có gì để dịch,
    nên xoá nó là phá tranh mà **không đổi lại lợi ích nào**.

    ## Ngưỡng lấy từ SỐ ĐO, không chọn cho tròn

    Đọc toàn bộ 27 vùng `comic-text-detector` khoanh trên 5 trang Pepper&Carrot:

        vùng nhiễu (nét khói vẽ)  : 1 ký tự có nghĩa, confidence 0.38
        MỌI vùng chữ thật         : 3-76 ký tự,        confidence 0.96-1.00

    ⇒ **Confidence tách bạch hơn hẳn** (0,38 so với ≥0,96 — khoảng cách rất rộng), nên khi có
    điểm thì dùng điểm. `manga-ocr` KHÔNG trả điểm, lúc đó mới lùi về đếm ký tự — thô hơn, và
    đó là đánh đổi có ý thức chứ không phải bỏ sót.
    """
    n = dem_ky_tu_co_nghia(text)
    if n == 0:
        return False                      # không ký tự nào: chắc chắn không có gì để dịch
    if confidence is not None:
        if min_conf > 0:
            sach = re.sub(r"[\s.!?,…~\"'`´-]+", "", text or "")
            if sach and len(sach) <= 2 and set(sach) <= _KY_TU_HINH_HOC_DON:
                return confidence >= max(min_conf, 0.88)
            if n == 1:
                if len(sach) == 1 and (sach.isdigit() or sach.isascii()):
                    return confidence >= max(min_conf, 0.88)
                if min_ky_tu >= 2:
                    return confidence >= max(min_conf, 0.72)
        return confidence >= min_conf     # engine có trả điểm -> tin điểm
    return n >= min_ky_tu                 # engine không trả điểm -> đếm ký tự


class UnsupportedSourceLang(ValueError):
    """source_lang không nằm trong 3 giá trị đã chốt — KHÔNG fallback âm thầm sang engine khác."""


class OCREngineUnavailable(RuntimeError):
    """Thư viện/model OCR chưa cài được — báo rõ thay vì trả text rỗng giả vờ đã OCR."""


class _BaseOCREngine:
    engine_enum: OCREngine

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._model = None
        self._lock = threading.Lock()

    def _load(self):  # pragma: no cover - override
        raise NotImplementedError

    def _get_model(self):
        """Nạp model 1 lần/process (cold-start lặp lại sẽ giết hiệu năng)."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = self._load()
        return self._model

    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float | None]:  # pragma: no cover
        raise NotImplementedError


class MangaOCREngine(_BaseOCREngine):
    """source_lang == 'ja'.

    manga-ocr KHÔNG trả confidence (đã kiểm source 0.1.16: `__call__` chỉ trả chuỗi text).
    → confidence = None. Không bịa số. Tiêu chí `needs_manual` dựa vào text rỗng/không có
    ký tự có nghĩa. Xem docs/ARCH.md § OCR.
    Hỗ trợ nâng cấp biến thể model `manga-ocr-base-CPT-flex` (hoặc checkpoint tuỳ chỉnh) qua cấu hình.
    """

    engine_enum = OCREngine.manga_ocr

    def __init__(
        self,
        device: str = "cpu",
        pretrained_model_name_or_path: str | None = None,
        preprocess_crop: bool = True,
    ) -> None:
        super().__init__(device=device)
        self.pretrained_model_name_or_path = pretrained_model_name_or_path
        self.preprocess_crop = preprocess_crop

    def _load(self):
        try:
            from manga_ocr import MangaOcr
        except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
            raise OCREngineUnavailable(f"Chưa cài manga-ocr: {exc}") from exc
        custom_model = (self.pretrained_model_name_or_path or "").strip()
        if custom_model and custom_model != "kha-white/manga-ocr-base":
            logger.info("Nạp manga-ocr nâng cấp %s (device=%s)", custom_model, self.device)
            try:
                return MangaOcr(
                    pretrained_model_name_or_path=custom_model,
                    force_cpu=self.device == "cpu",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Không nạp được model %s (%s) -> lùi về manga-ocr chuẩn",
                    custom_model,
                    exc,
                )
        logger.info("Nạp manga-ocr (device=%s)", self.device)
        return MangaOcr(force_cpu=self.device == "cpu")

    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float | None]:
        with Image.open(image_path) as im:
            crop = crop_region(im.convert("RGB"), bbox)
        if self.preprocess_crop:
            crop = tien_xu_ly_crop_ocr(crop, for_layout=False)
        text = self._get_model()(crop)
        return chuan_hoa_van_ban_ocr(text or ""), None


class PaddleOCREngine(_BaseOCREngine):
    """source_lang in ('zh', 'en'). PaddleOCR trả confidence thật theo từng dòng."""

    engine_enum = OCREngine.paddle_ocr

    def __init__(self, lang: str, device: str = "cpu", enable_mkldnn: bool = False) -> None:
        super().__init__(device=device)
        self.lang = lang
        #: paddlepaddle 3.3.1 ném NotImplementedError ở nhánh oneDNN trên CPU này
        #: -> mặc định TẮT. Bằng chứng + cách tái hiện: docs/TEST_LOG.md § M3.
        self.enable_mkldnn = enable_mkldnn

    def build_kwargs(self) -> dict:
        return {
            "lang": self.lang,
            "device": self.device,
            "use_textline_orientation": True,
            "enable_mkldnn": self.enable_mkldnn,
            # Đầu vào của ta là 1 crop bubble, KHÔNG phải trang tài liệu. Bộ phân loại hướng
            # trang không có gì để dựa vào nên đoán bừa và xoay crop 180° -> thứ tự dòng đảo
            # ngược ("OUT!/LOOK" thay vì "LOOK/OUT!"). Đo thật, xem docs/TEST_LOG.md § M3.
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
        }

    def _load(self):
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
            raise OCREngineUnavailable(f"Chưa cài paddleocr: {exc}") from exc
        kwargs = self.build_kwargs()
        logger.info("Nạp PaddleOCR %s", kwargs)
        return PaddleOCR(**kwargs)

    @classmethod
    def _parse(cls, result) -> tuple[str, float | None]:
        """Gom các dòng của 1 vùng crop thành 1 chuỗi + confidence trung bình.

        PaddleOCR đổi format output giữa các phiên bản (list lồng cũ vs dict mới) nên đọc cả 2
        dạng thay vì bám 1 dạng rồi vỡ khi nâng version.

        Thứ tự dòng trong output KHÔNG đảm bảo theo vị trí (đo thật: 1 bubble 2 dòng trả về
        đảo ngược) → sắp lại theo toạ độ trên→dưới, trái→phải. Chỉ sắp thứ tự dòng,
        TUYỆT ĐỐI không sửa ký tự nào trong text (việc sửa lỗi OCR là của bước dịch M5).
        """
        return cls._parse_with_polys(result)[:2]

    @staticmethod
    def _doc_dong(result) -> list[tuple[float, float, str, float | None, list]]:
        """Đọc từng dòng + đường bao từ output của PaddleOCR (cả dạng cũ lẫn dạng mới)."""
        lines: list[tuple[float, float, str, float | None, list]] = []

        def _take(text, score, poly=None):
            if text is None:
                return
            y, x = 0.0, 0.0
            pts: list[list[float]] = []
            if poly is not None:
                pts = [[float(px), float(py)] for px, py in (list(pt) for pt in poly)]
                if pts:
                    y = min(py for _, py in pts)
                    x = min(px for px, _ in pts)
            lines.append(
                (y, x, str(text), float(score) if score is not None else None, pts)
            )

        if not result:
            return []

        for page in result:
            if isinstance(page, dict):  # PaddleOCR >= 3.x
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or [None] * len(texts)
                polys = page.get("rec_polys")
                if polys is None:
                    polys = page.get("dt_polys")
                if polys is None:
                    polys = [None] * len(texts)
                for text, score, poly in zip(texts, scores, polys, strict=False):
                    _take(text, score, poly)
                continue
            for line in page or []:  # PaddleOCR 2.x: [[bbox, (text, score)], ...]
                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    poly, payload = line[0], line[1]
                    if isinstance(payload, (list, tuple)) and len(payload) >= 2:
                        _take(payload[0], payload[1], poly)
                    else:
                        _take(payload, None, poly)

        return lines

    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float | None]:
        text, conf, _poly = self.recognize_with_layout(image_path, bbox)
        return text, conf

    def recognize_with_layout(
        self, image_path: str, bbox: BBox
    ) -> tuple[str, float | None, list[list[list[float]]]]:
        """Như `recognize` nhưng trả THÊM đường bao từng dòng chữ, toạ độ **ảnh gốc**.

        Đường bao này engine vốn đã tính để sắp thứ tự dòng, trước nay dùng xong rồi vứt. Giữ
        lại vì nó là **bằng chứng hình học duy nhất** hệ thống có về hướng của chữ: bộ nhận
        diện chỉ cho khung chữ nhật, còn ảnh đã xoá chữ thì không còn chữ để mà đo.

        `recognize()` giữ nguyên chữ ký cũ — hợp đồng M1 không được đổi.
        """
        import numpy as np

        with Image.open(image_path) as im:
            crop = crop_region(im.convert("RGB"), bbox)
        model = self._get_model()
        predict = getattr(model, "predict", None) or model.ocr
        result = predict(np.asarray(crop))
        text, conf, polys = self._parse_with_polys(result)
        # Nếu khung hình là nền tối chữ trắng hoặc tương phản thấp khiến độ tự tin thấp (< 0.78),
        # tự động kích hoạt bước tăng cường thích ứng theo khung hình (giữ nguyên kích thước w, h)
        if not text or (conf is not None and conf < 0.78):
            crop_enh = tien_xu_ly_crop_ocr(crop, for_layout=True, dao_cuc_nen_toi=True)
            if crop_enh is not crop:
                res_enh = predict(np.asarray(crop_enh))
                text_enh, conf_enh, polys_enh = self._parse_with_polys(res_enh)
                if text_enh and (
                    not text
                    or (conf_enh or 0.0) > (conf or 0.0) + 0.04
                    or dem_ky_tu_co_nghia(text_enh) > dem_ky_tu_co_nghia(text) + 2
                ):
                    text, conf, polys = text_enh, conf_enh, polys_enh
        text = chuan_hoa_van_ban_ocr(text)
        # Đổi về toạ độ ảnh gốc để bên dùng khỏi phải nhớ cộng offset — quên cộng là lệch cả trang.
        doi = [[[px + bbox.x, py + bbox.y] for px, py in poly] for poly in polys]
        return text, conf, doi

    def doc_toan_anh(self, image_path: str) -> list[str]:
        """Đọc CHỮ TRÊN CẢ ẢNH, không cần bbox. Trả danh sách dòng chữ (E57).

        PaddleOCR là một pipeline **dò + đọc**: nó tự tìm dòng chữ. Pipeline dịch không dùng phần
        dò đó vì nó đã có bộ dò bong bóng riêng (comic-text-detector) tốt hơn cho truyện tranh —
        nhưng cho việc **đoán ngôn ngữ** thì phần dò sẵn này là đủ, và nó tiết kiệm được cả một
        model: không phải nạp comic-text-detector chỉ để lấy vài khung chữ.

        Cố ý KHÔNG lọc theo confidence: chữ đọc sai vẫn nói đúng **hệ chữ**. Một dòng kanji đọc
        nhầm chữ vẫn là kanji, và đó là toàn bộ thông tin mà phép phân loại cần.
        """
        import numpy as np

        with Image.open(image_path) as im:
            anh = np.asarray(im.convert("RGB"))
        model = self._get_model()
        predict = getattr(model, "predict", None) or model.ocr
        lines = self._doc_dong(predict(anh))
        return [t for _, _, t, _, _ in lines if t]

    @classmethod
    def _parse_with_polys(cls, result):
        """Bản đầy đủ của `_parse`: trả thêm đường bao, đã sắp cùng thứ tự với các dòng chữ."""
        lines = cls._doc_dong(result)
        lines.sort(key=lambda item: (item[0], item[1]))
        texts = [t for _, _, t, _, _ in lines if t]
        scores = [sc for _, _, _, sc, _ in lines if sc is not None]
        polys = [pl for _, _, t, _, pl in lines if t and pl]
        conf = sum(scores) / len(scores) if scores else None
        return "\n".join(texts).strip(), conf, polys


def get_ocr_engine(
    source_lang: str | SourceLang,
    device: str = "cpu",
    paddle_enable_mkldnn: bool = False,
    manga_ocr_model_id: str | None = None,
) -> _BaseOCREngine:
    """Factory theo source_lang. Giá trị lạ → raise rõ ràng, không fallback âm thầm."""
    value = source_lang.value if isinstance(source_lang, SourceLang) else str(source_lang)
    if value == SourceLang.ja.value:
        return MangaOCREngine(
            device=device,
            pretrained_model_name_or_path=manga_ocr_model_id,
        )
    if value in (SourceLang.zh.value, SourceLang.en.value, SourceLang.ko.value):
        paddle_lang = {"zh": "ch", "en": "en", "ko": "korean"}[value]
        return PaddleOCREngine(
            lang=paddle_lang,
            device=device,
            enable_mkldnn=paddle_enable_mkldnn,
        )
    raise UnsupportedSourceLang(
        f"source_lang '{value}' không được hỗ trợ ở M3 (chỉ ja/zh/en/ko)"
    )
