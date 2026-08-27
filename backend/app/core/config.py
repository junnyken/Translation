"""Cấu hình ứng dụng — đọc toàn bộ từ biến môi trường (.env), không hard-code credential."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://translation:translation@db:5432/translation"
    alembic_database_url: str | None = None

    # Job queue (dùng thật từ M2)
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # Storage
    storage_backend: Literal["local", "supabase"] = "local"
    storage_local_root: str = "/data/storage"
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "manga-pages"

    # Upload
    max_upload_mb: int = 25

    # ---- M2: comic-text-detector ----
    #: Đường dẫn file weight ONNX. Không có file -> job detect fail rõ ràng,
    #: tuyệt đối không detect bằng weight giả.
    model_weights_path: str = "/models/comic-text-detector.onnx"
    ctd_device: str = "cpu"
    #: Dưới ngưỡng này region vẫn được LƯU với status=low_confidence (không loại bỏ).
    ctd_conf_threshold: float = 0.5
    #: Sàn nhiễu trước NMS — phải nhỏ hơn ctd_conf_threshold để low_confidence còn được giữ.
    ctd_raw_min_conf: float = 0.25
    ctd_nms_iou: float = 0.45
    ctd_input_size: int = 1024
    ctd_intra_op_threads: int = 0
    #: 2 box chồng nhau quá tỷ lệ này (so với box nhỏ hơn) -> gắn cờ overlap_suspect.
    ctd_overlap_suspect_ratio: float = 0.8
    #: Timeout job detect. Mặc định 60s theo spec; trên máy chỉ có CPU nên đặt cao hơn
    #: trong .env (đo thật: ~39s/ảnh 1400x2000 trên workspace này).
    detect_timeout_seconds: int = 60

    # ---- M3: OCR ----
    ocr_device: str = "cpu"
    #: Chỉ áp cho engine CÓ confidence thật (PaddleOCR). manga-ocr không trả confidence
    #: -> confidence=NULL, tiêu chí needs_manual dựa vào text rỗng/không có ký tự có nghĩa.
    ocr_conf_threshold: float = 0.5
    #: Timeout RIÊNG cho OCR (không dùng chung với detect): OCR chạy N vùng/trang nên chậm hơn.
    ocr_timeout_seconds: int = 600
    #: Tự nối OCR ngay sau khi detect xong (pipeline tự chảy).
    ocr_auto_chain: bool = True
    # ---- M5: dịch ----
    #: Engine chạy tự động sau inpaint. MẶC ĐỊNH google_fast (miễn phí) — không tự tiêu
    #: token của người dùng khi họ chưa chọn. Đổi sang llm_context qua .env hoặc query param.
    translate_default_engine: str = "google_fast"
    #: Nhiều key ngăn cách bằng dấu phẩy, chỉ đọc từ .env — KHÔNG bao giờ lưu vào DB/git.
    gemini_api_keys: str = ""
    #: gemini-2.5-flash đã bị Google chặn với key mới (404 "no longer available to new users").
    llm_model_name: str = "gemini-3.1-flash-lite"
    #: 0 = TẮT thinking. Đo thật: không tắt thì 938 token suy nghĩ cho 6 dòng (đắt gấp ~7,7 lần).
    llm_thinking_budget: int = 0
    llm_temperature: float = 0.3
    llm_max_output_tokens: int = 8192
    #: LLM lỗi/hết quota -> tự lùi về google_fast, ghi status=fallback_used (không trả bản rỗng).
    llm_fallback_to_google: bool = True
    #: Timeout RIÊNG cho dịch, không dùng chung với detect/OCR/inpaint.
    translate_timeout_seconds: int = 900
    translate_auto_chain: bool = True
    #: Ép hướng đọc (ltr/rtl). Rỗng = suy theo source_lang (ja -> rtl).
    reading_direction_override: str = ""

    # ---- M4: inpaint (LaMa) ----
    inpaint_weights_path: str = "/models/lama-manga-dynamic.onnx"
    inpaint_device: str = "cpu"
    #: Nới mask quanh bbox để không sót viền chữ. Trần cứng 15% ở tầng code (mask.MAX_DILATE_RATIO).
    inpaint_dilate_ratio: float = 0.08
    #: Timeout RIÊNG cho inpaint (đo thật: 54,3s/ảnh 1400x2000 trên CPU, chưa tính bước kiểm chứng).
    inpaint_timeout_seconds: int = 600
    inpaint_auto_chain: bool = True
    #: Kiểm chứng khách quan: OCR lại đúng vùng đã xoá, còn chữ -> inpaint_needs_review.
    inpaint_verify_by_ocr: bool = True
    inpaint_intra_op_threads: int = 0
    #: Constraint 10 của M4: KHÔNG lặng lẽ lùi về cv2.inpaint khi LaMa lỗi.
    #: Muốn cho phép fallback thì phải bật tường minh ở đây.
    inpaint_allow_opencv_fallback: bool = False

    #: paddlepaddle 3.3.1 vỡ ở nhánh oneDNN/PIR trên CPU này
    #: (NotImplementedError: ConvertPirAttribute2RuntimeAttribute ... onednn_instruction.cc)
    #: -> phải tắt oneDNN thì PaddleOCR mới chạy. Xem docs/TEST_LOG.md § M3.
    ocr_paddle_enable_mkldnn: bool = False

    app_env: str = "dev"
    log_level: str = "INFO"

    @property
    def gemini_api_key_list(self) -> list[str]:
        """Tách chuỗi key thành list. Không log, không trả ra API."""
        return [k.strip() for k in self.gemini_api_keys.split(",") if k.strip()]

    @property
    def sync_database_url(self) -> str:
        """URL driver đồng bộ cho Alembic (suy ra từ database_url nếu không khai báo riêng)."""
        if self.alembic_database_url:
            return self.alembic_database_url
        return self.database_url.replace("+asyncpg", "+psycopg")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
