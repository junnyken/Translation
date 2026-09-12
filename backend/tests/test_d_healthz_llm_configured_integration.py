"""D — `/healthz` nói ra `llm_context` có dùng được không, mà KHÔNG lộ khoá.

Trước thay đổi này, muốn biết production đã cấu hình khoá Gemini chưa thì phải đăng nhập rồi gọi
`/batch-config`. Nên câu hỏi "bật dịch theo ngữ cảnh được chưa" không ai trả lời được từ ngoài.

Hai thứ phải cùng đúng, và chúng kéo ngược chiều nhau:
- Phải NÓI RA trạng thái (nếu không thì thêm trường này vô nghĩa).
- Phải KHÔNG lộ một mảnh khoá nào (endpoint này mở, không đòi đăng nhập).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


async def test_healthz_co_truong_llm_configured(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert isinstance(r.json()["llm_configured"], bool), "phải là true/false, không phải chuỗi"


async def test_healthz_KHONG_lo_bat_ky_manh_khoa_nao(client, monkeypatch):
    """Chốt chặn rò rỉ: đặt khoá giả rồi soi TOÀN BỘ thân phản hồi.

    Kiểm cả mảnh 8 ký tự đầu, vì một lần "rút gọn cho dễ nhìn" là đủ để lộ tiền tố khoá.
    """
    from app.core.config import get_settings

    # Ghép lúc CHẠY, không viết liền trong mã nguồn. `test_khong_co_api_key_nao_bi_commit_vao_git`
    # quét mọi tệp đã vào git bằng mẫu `AIza[0-9A-Za-z_\-]{30,}` — một khoá GIẢ viết liền vẫn khớp
    # mẫu đó và làm cổng chặn key đỏ. Đúng như vậy: cổng chặn không thể phân biệt thật/giả, và nó
    # chỉ có giá trị khi tuyệt đối. (Tôi đã đẩy đúng lỗi này lên git ở commit `1656eb1`.)
    KHOA = "AIza" + "Sy" + "K" * 33
    get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEYS", KHOA)
    try:
        r = await client.get("/healthz")
        # Chốt chặn test-rỗng-nghĩa: nếu khoá giả không được nạp thì phần soi rò rỉ bên dưới
        # đang soi một phản hồi CHƯA CẤU HÌNH và sẽ xanh mà chẳng kiểm gì.
        assert r.json()["llm_configured"] is True, "khoá giả không được nạp — test này vô nghĩa"
        than = r.text
        assert KHOA not in than
        assert KHOA[:8] not in than
        assert "AIza" not in than
    finally:
        get_settings.cache_clear()


async def test_healthz_van_KHONG_doi_hoi_dang_nhap(client):
    """Nền tảng hosting thăm dò endpoint này. Thêm trường không được kéo theo yêu cầu đăng nhập."""
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_cac_truong_cu_con_nguyen(client):
    """Thêm trường là thay đổi CỘNG THÊM — thứ đang đọc `/healthz` không được gãy."""
    body = (await client.get("/healthz")).json()
    for truong in ("status", "worker", "rss_mb", "rss_api_mb"):
        assert truong in body, f"mất trường cũ `{truong}` — phá hợp đồng API.md §healthz"
