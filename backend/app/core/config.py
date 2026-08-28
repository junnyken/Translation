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

    # ---- M6: canh chữ vào bubble ----
    #: Thư mục font, mount vào worker. API KHÔNG cần đọc (không nạp engine render).
    font_dir: str = "/fonts"
    #: Family mặc định khi Project chưa chọn. Phải nằm trong whitelist FONT_REGISTRY.
    default_font_family: str = "Bangers"
    #: Font hỏng/thiếu ⇒ lỗi rõ. Chỉ bật cái này khi CHẤP NHẬN bị đổi font âm thầm.
    allow_font_fallback: bool = False
    #: Không bao giờ co chữ nhỏ hơn min để giả vờ vừa khung — dưới min là overflow_warning.
    typeset_min_font_size: int = 10
    #: Spec đề xuất 28, nhưng ĐO THẬT trên trang 1400x2000: 5/6 vùng dừng đúng ở 28 ⇒ trần
    #: đang chặn chứ không phải bubble. Nới lên 40 thì không vùng nào chạm trần (30-36) và
    #: trên 40 không đổi gì nữa. Xem REPORT_M6 §3.
    typeset_max_font_size: int = 40
    typeset_padding_ratio: float = 0.09
    typeset_line_spacing_ratio: float = 0.18
    #: Viền chữ (0 = tắt). Bật lên thì phép đo cũng tính viền, không lệch.
    typeset_stroke_width: int = 0
    typeset_text_color: str = "black"
    typeset_stroke_color: str = "white"
    #: Timeout RIÊNG cho typeset — nay là năm timeout độc lập (có test canh).
    typeset_timeout_seconds: int = 600
    typeset_auto_chain: bool = True
    # ---- M7: sửa tay từng vùng ----
    #: Canh lại 1 vùng nhanh hơn cả trang nhiều (đo thật ~0,5s/trang) nên timeout ngắn hơn.
    refit_timeout_seconds: int = 180
    # ---- M8: xuất chapter ----
    #: Timeout RIÊNG — nay là bảy timeout độc lập (có test canh). Đo thật rồi chỉnh, đừng copy
    #: số của job khác: xuất chapter là nhiều trang nhân lên, không phải một trang.
    export_timeout_seconds: int = 900

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
    #: Trang bao nhiêu TRIỆU ĐIỂM ẢNH trở xuống thì xoá chữ cả trang một lượt; lớn hơn thì chia
    #: theo cụm bong bóng. Đo thật: LaMa cần ~1,6 GB RAM cho mỗi triệu điểm ảnh, nên trang truyện
    #: thật ở cỡ đọc (3,6 triệu điểm) chạy cả trang là bị hệ điều hành giết.
    inpaint_whole_page_max_mpx: float = 2.5
    inpaint_tile_margin: int = 96
    #: Constraint 10 của M4: KHÔNG lặng lẽ lùi về cv2.inpaint khi LaMa lỗi.
    #: Muốn cho phép fallback thì phải bật tường minh ở đây.
    inpaint_allow_opencv_fallback: bool = False

    #: paddlepaddle 3.3.1 vỡ ở nhánh oneDNN/PIR trên CPU này
    #: (NotImplementedError: ConvertPirAttribute2RuntimeAttribute ... onednn_instruction.cc)
    #: -> phải tắt oneDNN thì PaddleOCR mới chạy. Xem docs/TEST_LOG.md § M3.
    ocr_paddle_enable_mkldnn: bool = False

    #: Danh sách tên miền được phép gọi API, ngăn cách bằng dấu phẩy.
    #: RỖNG = không cho phép gọi chéo nguồn. Cố ý không mặc định `*`.
    cors_allow_origins: str = ""
    app_env: str = "dev"
    log_level: str = "INFO"

    @property
    def cors_allow_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def gemini_api_key_list(self) -> list[str]:
        """Tách chuỗi key thành list. Không log, không trả ra API."""
        return [k.strip() for k in self.gemini_api_keys.split(",") if k.strip()]

    @staticmethod
    def _doi_driver(url: str, driver: str) -> str:
        """Ép URL Postgres về đúng driver cần dùng, dù URL vào ở dạng nào.

        Nền tảng hosting tiêm `DATABASE_URL` dạng `postgresql://user:pass@host/db` — KHÔNG có
        driver. SQLAlchemy gặp dạng đó sẽ mặc định `psycopg2`, mà repo này cài `psycopg` (v3)
        và `asyncpg`, nên nổ `ModuleNotFoundError: No module named 'psycopg2'` lúc khởi động.
        Cũng nhận cả `postgres://` (kiểu Heroku cũ) mà SQLAlchemy không còn hiểu.
        """
        for tien_to in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgresql+psycopg2://"):
            if url.startswith(tien_to):
                return f"postgresql+{driver}://" + url[len(tien_to):]
        for tien_to in ("postgresql://", "postgres://"):
            if url.startswith(tien_to):
                return f"postgresql+{driver}://" + url[len(tien_to):]
        return url

    @property
    def async_database_url(self) -> str:
        """URL cho engine bất đồng bộ của API."""
        return self._doi_driver(self.database_url, "asyncpg")

    @property
    def sync_database_url(self) -> str:
        """URL driver đồng bộ cho Alembic + worker (suy ra từ database_url nếu không khai riêng)."""
        if self.alembic_database_url:
            return self._doi_driver(self.alembic_database_url, "psycopg")
        return self._doi_driver(self.database_url, "psycopg")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
