"""E46 — nhận diện khung chữ bằng Gemini, thay cho ONNX cục bộ.

## Vì sao có tệp này

`comic-text-detector` chạy CPU mất **42–70s/trang** và chiếm ~60% thời gian một trang
(`REPORT_E45.md` §8). E25 và E45 đã đóng sáu hướng tối ưu — cả sáu đều *chia lại* cùng một khối
tính toán nên thất bại cùng lý do. Gọi AI thì **bỏ hẳn khối đó ra khỏi máy**: đo được **3,5s**,
tốn ~1,2 xu Mỹ cho một chapter 24 trang (`REPORT_E46.md`).

## Ba quyết định KHÔNG được đảo, mỗi cái đều có số đo đứng sau

### 1. `responseSchema` là BẮT BUỘC, không phải tuỳ chọn

Xin JSON bằng lời nhắc **hỏng âm thầm**. Đo được trên chính fixture của dự án: model dừng giữa
mảng JSON (thiếu dấu đóng) mà vẫn báo `finishReason: STOP` — tức nó *tưởng* đã trả lời xong — và
đổi tên khoá ngay trong một câu trả lời (`box` rồi `box_2d`). Tái hiện **7/7 lần trên cùng một
trang**, tức hỏng **tất định theo trang** chứ không phải nhiễu.

Không ngoại lệ mạng, không mã lỗi, chỉ là **dữ liệu thiếu** ⇒ trang đó im lặng mất vùng chữ.

Ép schema: **45/45 thành công** (so với 24/30), và còn *nhanh hơn* (2,46s so với 3,58s) vì không
phải sinh rào markdown hay lời dẫn.

### 2. Đòi khung CHỮ, KHÔNG đòi khung BONG BÓNG

Lời nhắc đầu tiên nói *"speech balloon and text area"* — chính nó mời model khoanh cả bong bóng.
Hậu quả đo được: diện tích ăn vào nét vẽ **gấp 2,7 lần** khung của model cũ. Khung này còn làm
**mask cho LaMa**, nên thừa nghĩa là **xoá cả nét vẽ quanh bong bóng**.

Đổi sang đòi khung bám sát nét chữ: **2,7× → 1,3×**. Đừng nới lời nhắc này ra cho "an toàn hơn" —
nới là quay lại đúng lỗi cũ.

### 3. `confidence = None`, KHÔNG bịa số

Gemini không trả điểm tin cậy. Điền 1.0 cho gọn là **bịa ra một con số không hề tồn tại** — đúng
thứ `ConfidenceState.unavailable` sinh ra để tránh (xem docstring của nó). Vùng do engine này tạo
có `confidence=None` và **không bao giờ** bị gắn cờ `low_confidence`, vì không có bằng chứng nào
để gắn.

## Vì sao KHÔNG đặt làm mặc định

Đo trên 5 trang Pepper&Carrot: engine này **bỏ sót 2/27 vùng**, model cũ sót **0/27**. Sót một
bong bóng nghĩa là **mất hẳn một câu thoại** trong bản giao cho người đọc. Mặc định vẫn là `ctd`;
ai bật cái này là chấp nhận đánh đổi đó một cách có ý thức.

Thêm nữa, toàn bộ phép đo chạy trên **truyện tiếng Anh, khung tranh phương Tây**. Truyện Nhật —
chữ dọc, bong bóng không viền, chữ tượng thanh đè lên nét vẽ — **chưa thử lần nào**.

## Hỏng thì BÁO, không lặng lẽ lùi về model cũ

Tự lùi về `ctd` khi API lỗi nghe có vẻ an toàn nhưng phá nguyên tắc evidence-first: người dùng
tưởng đang chạy engine mình chọn, và một sự cố kéo dài sẽ không ai thấy. Lỗi ở đây ném
`AIDetectError`; job detect sẽ mang đúng lý do đọc được.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox

logger = logging.getLogger(__name__)

#: Toạ độ Gemini trả về đã chuẩn hoá về thang này (`[ymin, xmin, ymax, xmax]`).
#: Đã XÁC MINH bằng cách vẽ khung lên ảnh và nhìn — đoán sai thứ tự sẽ cho khung
#: trông hợp lý mà sai hoàn toàn.
THANG = 1000.0

#: Ép cấu trúc đầu ra. Xem §1 ở docstring đầu tệp — bỏ cái này là mở lại đường hỏng âm thầm.
SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "box": {"type": "ARRAY", "items": {"type": "INTEGER"},
                    "minItems": 4, "maxItems": 4},
        },
        "required": ["box"],
    },
}

#: Xem §2 ở docstring đầu tệp. Mỗi câu ở đây đều đang gánh một con số đo được.
LOI_NHAC = (
    "Find every block of written text in this comic page. For each one give a TIGHT bounding box "
    "around the TEXT CHARACTERS THEMSELVES as [ymin, xmin, ymax, xmax] normalized 0-1000. "
    "Do NOT include the speech balloon, bubble outline, or the blank space around the text. "
    "The box edges must touch the outermost letters."
)


class AIDetectError(RuntimeError):
    """Nhận diện bằng AI thất bại. Mang lý do đọc được, không nuốt."""


@dataclass
class AIGeminiDetector:
    """Nhận diện khung chữ qua Gemini. Cùng interface với `CTDDetector` nên thay được tại chỗ."""

    api_keys: list[str]
    model_name: str = "gemini-3.1-flash-lite"
    timeout: int = 120
    #: Cạnh dài ảnh gửi đi. Gemini tính tiền theo ô 768×768 nên gửi nguyên cỡ là đốt token vô ích;
    #: 1024 là mức E32 đã chốt (giữ được chữ đọc được). Xem `translate/anh_kem.py`.
    canh_toi_da: int = 1024

    def detect(self, image_path: str) -> list[BBox]:
        return [r.bbox for r in self.detect_regions(image_path)]

    def detect_regions(self, image_path: str) -> list[DetectedRegion]:
        if not self.api_keys:
            raise AIDetectError(
                "Chưa cấu hình GEMINI_API_KEYS — engine nhận diện 'ai_gemini' cần khoá API. "
                "Đặt khoá, hoặc chuyển DETECT_ENGINE về 'ctd' để chạy model cục bộ."
            )

        from PIL import Image

        from app.services.translate.anh_kem import chuan_bi_anh

        with Image.open(image_path) as im:
            rong_goc, cao_goc = im.size

        with open(image_path, "rb") as f:
            goc = f.read()
        da_chuan = chuan_bi_anh(goc, self.canh_toi_da)
        if da_chuan is None:
            raise AIDetectError(f"Không chuẩn bị được ảnh để gửi: {image_path}")
        anh, mime = da_chuan

        tho = self._goi(anh, mime)

        ra: list[DetectedRegion] = []
        for muc in tho:
            hop = muc.get("box")
            if not (isinstance(hop, list) and len(hop) == 4):
                continue
            y0, x0, y1, x1 = (float(v) for v in hop)
            # Toạ độ chuẩn hoá theo ẢNH ĐÃ THU NHỎ, nhưng vì là tỷ lệ nên quy thẳng về cỡ GỐC
            # được — không cần biết ảnh gửi đi to bao nhiêu.
            x0, x1 = x0 / THANG * rong_goc, x1 / THANG * rong_goc
            y0, y1 = y0 / THANG * cao_goc, y1 / THANG * cao_goc
            if x1 <= x0 or y1 <= y0:
                continue  # khung rỗng/đảo chiều: bỏ, không tự "sửa" thành khung đoán
            x0, y0 = max(0.0, x0), max(0.0, y0)
            x1, y1 = min(float(rong_goc), x1), min(float(cao_goc), y1)
            ra.append(DetectedRegion(
                bbox=BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0),
                confidence=None,   # §3: KHÔNG bịa. Xem docstring đầu tệp.
                cls=0,
            ))

        logger.info(
            "ai_gemini detect: %s -> %d khung (model %s)", image_path, len(ra), self.model_name
        )
        return ra

    def _goi(self, anh: bytes, mime: str) -> list[dict]:
        """Gọi API, xoay key khi gặp lỗi có thể do key. Hết key thì ném lỗi cuối cùng."""
        than = json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(anh).decode()}},
                {"text": LOI_NHAC},
            ]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
                "thinkingConfig": {"thinkingBudget": 0},
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA,
            },
        }).encode()

        loi_cuoi: Exception | None = None
        for key in self.api_keys:
            try:
                req = urllib.request.Request(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.model_name}:generateContent?key={key}",
                    data=than,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    d = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                # Đọc THÂN lỗi: thông điệp thật nằm ở đó. Đoán theo mã HTTP là cách chắc chắn
                # chẩn sai — 400 của bậc pro hoá ra là "model only works in thinking mode".
                try:
                    chi_tiet = json.loads(exc.read()).get("error", {}).get("message", "")
                except Exception:
                    chi_tiet = ""
                loi_cuoi = AIDetectError(f"Gemini HTTP {exc.code}: {chi_tiet[:300]}")
                if exc.code in (400, 404):
                    raise loi_cuoi from exc   # lỗi cấu hình: xoay key không cứu được
            except Exception as exc:
                loi_cuoi = AIDetectError(f"Gọi Gemini thất bại: {type(exc).__name__}: {exc}")
        else:
            raise loi_cuoi or AIDetectError("Gọi Gemini thất bại, không rõ lý do")

        try:
            ung_vien = d["candidates"][0]
            # Gộp MỌI phần: câu trả lời có thể bị tách thành nhiều `parts`.
            chu = "".join(p.get("text", "") for p in ung_vien["content"]["parts"])
        except (KeyError, IndexError) as exc:
            raise AIDetectError(f"Phản hồi Gemini thiếu nội dung: {json.dumps(d)[:300]}") from exc

        try:
            tho = json.loads(chu)
        except json.JSONDecodeError as exc:
            # Với `responseSchema` thì đây gần như không xảy ra — nhưng nếu xảy ra thì phải BÁO,
            # vì im lặng ở đây chính là kiểu hỏng §1 đã mô tả.
            raise AIDetectError(
                f"Gemini trả JSON hỏng dù đã ép schema (finishReason="
                f"{ung_vien.get('finishReason')!r}): {chu[:200]}"
            ) from exc

        if not isinstance(tho, list):
            raise AIDetectError(f"Gemini trả về không phải mảng: {type(tho).__name__}")
        return tho
