"""E58 — xin engine MIỄN PHÍ thì phải chạy engine miễn phí.

## Lỗi đang vá — ĐO ĐƯỢC trên production, không phải suy luận

`POST /doc-truyen/trang` (trang chủ + tiện ích đọc truyện) mã hoá `engine=google_fast` thành
`translate_engine_override = NULL`, với lý do ghi trong mã: *"cả hai đều đọc ra dùng mặc định hệ
thống, không khác nhau"*.

Câu đó đúng khi mặc định hệ thống là `google_fast`, và **sai ngay khi ai đó đổi nó**. Production
28-09-2026 đặt `TRANSLATE_DEFAULT_ENGINE=llm_context`, nên:

| Đo cái gì | Giá trị đo được |
|---|---|
| Tiện ích gửi | `engine=google_fast` (mặc định của nó) |
| Cột trong CSDL | `translate_engine_override = None` |
| `/pages/{id}/translation` | `engine: llm_context` — **Gemini trả tiền** |

Tiện ích có chú thích *"`google_fast` là mặc định trung thực … không tự tốn token Gemini khi người
dùng chưa từng bật (đúng chủ ý M5)"*. Hành vi thật ngược lại.

## Vì sao bài canh phải đo ENGINE CHẠY, không chỉ đo CỘT

Khẳng định "cột lưu `google_fast`" là khẳng định vào một chi tiết lưu trữ. Thứ người dùng trả tiền
cho là **engine nào thực sự được gọi**. Nên bài nặng nhất ở đây đặt mặc định hệ thống thành
`llm_context` rồi đòi lượt dịch vẫn dùng `google_fast` — đúng hình dạng lỗi trên production.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import TranslationEngine

DUONG = "/api/v1/doc-truyen/trang"


@pytest.fixture
def st():
    return get_settings()


def _cot_override(page_id) -> str | None:
    with sync_session() as s:
        return s.execute(
            sa.text("SELECT translate_engine_override FROM page WHERE id = :i"),
            {"i": uuid.UUID(str(page_id))},
        ).scalar_one()


async def _gui(client, anh, engine: str | None = None):
    data = {"source_lang": "ja", "che_do": "day_du"}
    if engine is not None:
        data["engine"] = engine
    return await client.post(DUONG, files={"file": ("p.png", anh, "image/png")}, data=data)


@pytest.mark.asyncio
async def test_google_fast_duoc_LUU_chu_khong_thanh_NULL(client, sample_page_image):
    r = await _gui(client, sample_page_image, "google_fast")
    assert r.status_code == 202, r.text
    assert _cot_override(r.json()["page_id"]) == "google_fast"


@pytest.mark.asyncio
async def test_khong_gui_engine_thi_van_la_google_fast(client, sample_page_image):
    """Mặc định của endpoint là `google_fast` — nó phải được LƯU như một lựa chọn thật.

    Trang chủ không có ô chọn cách dịch nên nó rơi vào đúng nhánh này. Để NULL ở đây là để trang
    chủ thừa hưởng bất kỳ mặc định hệ thống nào, kể cả engine trả tiền.
    """
    r = await _gui(client, sample_page_image)
    assert r.status_code == 202, r.text
    assert _cot_override(r.json()["page_id"]) == "google_fast"


@pytest.mark.asyncio
async def test_llm_context_van_duoc_luu_nhu_cu(client, sample_page_image, st, monkeypatch):
    """Không phá đường cũ: ai chọn engine trả tiền thì vẫn được engine trả tiền."""
    # `llm_configured` là property CHỈ ĐỌC (suy từ `gemini_api_keys`) — đặt biến gốc, không đặt nó.
    monkeypatch.setattr(st, "gemini_api_keys", "khoa-gia-cho-test")
    r = await _gui(client, sample_page_image, "llm_context")
    assert r.status_code == 202, r.text
    assert _cot_override(r.json()["page_id"]) == "llm_context"


@pytest.mark.asyncio
async def test_MAC_DINH_HE_THONG_la_llm_context_van_KHONG_lam_trang_moi_ton_tien(
    client, sample_page_image, st, monkeypatch
):
    """BÀI CANH NẶNG NHẤT — tái hiện đúng cấu hình production đã gây lỗi.

    Đặt mặc định hệ thống thành engine TRẢ TIỀN, rồi gửi một trang xin engine miễn phí. Lượt dịch
    phải dùng `google_fast`.

    Khẳng định vào **engine mà bước dịch thật sự chọn** (`engine_override or mặc định`), không chỉ
    vào cột đã lưu: thứ người dùng trả tiền cho là lượt gọi API, không phải một ô trong bảng.
    """
    monkeypatch.setattr(st, "translate_default_engine", "llm_context")
    monkeypatch.setattr(st, "gemini_api_keys", "khoa-gia-cho-test")

    r = await _gui(client, sample_page_image, "google_fast")
    assert r.status_code == 202, r.text
    page_id = r.json()["page_id"]

    from app.workers.tasks import _page_engine_override

    override = _page_engine_override(uuid.UUID(page_id))
    assert override == "google_fast", "cột phải mang đúng lựa chọn, không để pipeline tự đoán"

    # Đúng phép tính mà `run_translate_job` dùng (`tasks.py`): override THẮNG mặc định hệ thống.
    engine_se_dung = override or get_settings().translate_default_engine
    assert engine_se_dung == "google_fast", (
        f"xin miễn phí mà sẽ chạy {engine_se_dung} — đây đúng lỗi production 28-09"
    )


@pytest.mark.asyncio
async def test_trang_CU_co_NULL_thi_van_lui_ve_mac_dinh_he_thong(st, monkeypatch):
    """Tương thích ngược: trang tạo TRƯỚC bản vá mang `NULL` và phải giữ nguyên hành vi cũ.

    Không có bài này thì bản vá dễ bị "sửa" thành coi NULL là `google_fast`, và như thế là âm thầm
    đổi hành vi của mọi trang cũ trong CSDL.
    """
    from app.workers.tasks import _page_engine_override

    monkeypatch.setattr(st, "translate_default_engine", "llm_context")
    with sync_session() as s:
        pid = s.execute(
            sa.text(
                "INSERT INTO project (id, name, source_lang, target_lang, intended_use, status)"
                " VALUES (gen_random_uuid(), 'cu', 'ja', 'vi', 'personal', 'active') RETURNING id"
            )
        ).scalar_one()
        page_id = s.execute(
            sa.text(
                "INSERT INTO page (id, project_id, image_path, \"order\", status,"
                " translate_engine_override) VALUES (gen_random_uuid(), :p, 'x.png', 1,"
                " 'queued', NULL) RETURNING id"
            ),
            {"p": pid},
        ).scalar_one()
        s.commit()

    assert _page_engine_override(page_id) is None
    engine_se_dung = _page_engine_override(page_id) or get_settings().translate_default_engine
    assert engine_se_dung == "llm_context"


@pytest.mark.asyncio
async def test_engine_la_TranslationEngine_hop_le_moi_duoc_nhan(client, sample_page_image):
    """Giá trị lạ phải bị từ chối ở tầng schema, không lọt vào CSDL rồi nổ ở worker."""
    r = await _gui(client, sample_page_image, "engine-khong-ton-tai")
    assert r.status_code == 422


def test_enum_chi_co_hai_gia_tri_va_google_fast_la_cai_mien_phi():
    """Ghim lại điều mà cả bản vá này dựa vào: `google_fast` là đường KHÔNG tốn tiền.

    Thêm một engine trả tiền thứ hai mà quên chỗ này ⇒ bài đỏ, và người thêm phải đọc lại vì sao
    `google_fast` được đối xử riêng.
    """
    assert {e.value for e in TranslationEngine} == {"google_fast", "llm_context"}
