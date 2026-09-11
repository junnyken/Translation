"""D — bật `llm_context` làm mặc định chỉ AN TOÀN nếu khoá rỗng vẫn lùi được về google.

`test_llm_loi_thi_lui_ve_google_va_danh_dau_fallback` đã canh đường lùi, nhưng nó dùng translator
**giả** tự ném lỗi. Nó KHÔNG trả lời được câu quyết định việc đổi cấu hình production:

    Nếu production chưa cấu hình `GEMINI_API_KEYS` (hoặc cấu hình rỗng), đổi engine mặc định sang
    `llm_context` có làm hỏng mọi lượt dịch không?

Câu trả lời phải là KHÔNG — tệ nhất là quay về đúng hành vi hôm nay, có dán nhãn `fallback_used`.
Điều đó chỉ đúng khi CẢ HAI mệnh đề dưới đây đúng, và cả hai đều mong manh:

1. Dựng translator với khoá rỗng **không** được ném lỗi — vì `build_translator` được gọi NGOÀI
   khối try trong `_run_translate` (`tasks.py:1094`). Ném ở đó là mất hẳn đường lùi.
2. Lỗi khoá rỗng phải là đúng `QuotaExhausted` — đúng loại mà khối except bắt. Đổi sang loại khác
   (vd `ValueError`) là job đỏ thay vì lùi.

Không có mạng trong test này: cả hai mệnh đề đều vỡ ra TRƯỚC khi gọi HTTP.
"""
from __future__ import annotations

import pytest

from app.services.translate.engines import QuotaExhausted, get_translator


def test_dung_translator_voi_khoa_RONG_thi_KHONG_duoc_nem():
    """Mệnh đề 1 — `build_translator` nằm NGOÀI khối try, ném ở đây là mất đường lùi."""
    tr = get_translator("llm_context", api_keys=[])
    assert tr.key_count == 0


def test_khoa_rong_nem_dung_QuotaExhausted_luc_dich():
    """Mệnh đề 2 — phải đúng loại lỗi mà `_run_translate` bắt, không phải loại khác."""
    tr = get_translator("llm_context", api_keys=[])
    with pytest.raises(QuotaExhausted):
        tr.translate(["Hello."], "en", "vi")


def test_khoi_except_cua_run_translate_co_bat_QuotaExhausted():
    """Canh chính mã sản xuất, không chỉ canh engine.

    Nếu ai đó đổi khối except trong `_run_translate` thì hai test trên vẫn xanh mà đường lùi đã
    gãy. Test này đọc thẳng mã nguồn nên bắt được ca đó.
    """
    import inspect

    from app.workers import tasks

    src = inspect.getsource(tasks._run_translate)
    assert "except (QuotaExhausted, TranslationFailed)" in src, (
        "khối except của _run_translate không còn bắt QuotaExhausted — "
        "khoá Gemini rỗng sẽ làm ĐỎ job thay vì lùi về google_fast"
    )


@pytest.mark.parametrize("khoa", ["", "   ", ",", " , "])
def test_cac_dang_khoa_RONG_deu_ra_danh_sach_rong(khoa):
    """Chuỗi chỉ có dấu phẩy/khoảng trắng phải coi là CHƯA cấu hình, không thành một "khoá" rỗng.

    Quan trọng cho giao diện: `llm_configured=False` làm mờ mục "Dịch theo ngữ cảnh", nên người
    dùng biết trước thay vì bấm rồi mới thấy job lùi về bản thường.
    """
    from app.core.config import Settings

    s = Settings(gemini_api_keys=khoa)
    assert s.gemini_api_key_list == []
    assert s.llm_configured is False


def test_khoa_RAC_cung_ra_dung_loai_loi_ma_duong_lui_bat_duoc():
    """Ca kề bên khoá rỗng, và tôi đã đoán SAI về nó lúc đầu.

    Tôi từng viết rằng khoá rác *"ăn 400 — không phải QuotaExhausted — và mất đường lùi"*. Đo thật
    (2026-09-11, khoá `khoa-rac-khong-hop-le`): Gemini trả `400 API key not valid`, và
    `_call_api` bọc mọi HTTPError ngoài nhóm 429 thành **`TranslationFailed`** — mà khối except
    trong `_run_translate` bắt **cả hai** loại. Nên đường lùi VẪN chạy.

    Điều đó đáng chốt lại bằng test, vì `llm_configured` chỉ kiểm chuỗi có rỗng hay không: một
    khoá sai/hết hạn vẫn cho `True` và vẫn bật được mục chọn trên giao diện. Ca đó phải lùi êm
    chứ không được làm đỏ job.
    """
    import inspect

    from app.services.translate import engines

    src = inspect.getsource(engines.LLMContextTranslator._call_api)
    assert "raise last_error from exc" in src
    assert "TranslationFailed(f\"HTTP {exc.code}" in src, (
        "lỗi HTTP ngoài nhóm quota không còn được bọc thành TranslationFailed — "
        "khoá sai/hết hạn sẽ làm ĐỎ job thay vì lùi về google_fast"
    )
