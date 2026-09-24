"""P1 — `token_cost` đi được từ CSDL ra tới API, và giữ đúng nghĩa của `NULL`.

Trọng tâm không phải "có trường đó chưa", mà là **phân biệt `NULL` với `0`**:

- `NULL` = engine miễn phí (`google_fast`) hoặc chưa dịch ⇒ giao diện im lặng
- `0`    = đã dùng engine tốn token mà tốn hết 0 token

Gộp hai thứ này lại là báo sai chi phí cho người trả tiền. Đây đúng nguyên tắc đã chốt của dự án:
*chưa có → NULL, không điền giá trị mặc định giả.*
"""

from __future__ import annotations

import uuid

import pytest

from app.core.db_sync import sync_session
from app.models import OCRResult, Page, Project, TextRegion, TranslationResult
from app.models.enums import (
    IntendedUse,
    OCREngine,
    OCRStatus,
    PageStatus,
    TranslationStatus,
)

pytestmark = pytest.mark.anyio


def _dung_chapter(token_moi_vung: list[int | None], project_id: str | None = None) -> tuple[str, str]:
    """Dựng 1 chapter 1 trang, mỗi vùng mang đúng `token_cost` truyền vào (`None` = miễn phí).

    `project_id` để truyền vào một chapter **đã có chủ** (tạo qua API). Chapter dựng thẳng vào
    CSDL ở đây **không có chủ**, và chapter không chủ thì hệ thống **cố ý cho mọi tài khoản
    thấy** — để chapter tạo từ trước slice B không biến mất khỏi tầm nhìn. Nên muốn kiểm quyền
    chéo tài khoản thì bắt buộc phải có chủ thật, không dùng fixture trần này được.
    """
    with sync_session() as s:
        if project_id is None:
            pr = Project(name="P1 token", source_lang="en", target_lang="vi",
                         intended_use=IntendedUse.study)
            s.add(pr); s.flush()
            pid = pr.id
        else:
            pid = uuid.UUID(project_id)
        page = Page(project_id=pid, image_path="x.png", order=1,
                    status=PageStatus.typeset_done)
        s.add(page); s.flush()
        for i, tok in enumerate(token_moi_vung):
            r = TextRegion(page_id=page.id, bbox_x=10 + i * 50, bbox_y=10, bbox_w=40, bbox_h=20,
                           confidence=0.9, reading_order=i + 1)
            s.add(r); s.flush()
            s.add(OCRResult(region_id=r.id, raw_text="hello",
                            ocr_engine=OCREngine.paddle_ocr, status=OCRStatus.ok))
            s.add(TranslationResult(region_id=r.id, translated_text="Xin chào",
                                    status=TranslationStatus.ok, token_cost=tok))
        s.commit()
        return str(pid), str(page.id)


class TestTokenCostRaToiApi:
    async def test_vung_dung_engine_ton_token_thi_API_tra_dung_so(self, client):
        _pr, pg = _dung_chapter([542, 318])
        r = await client.get(f"/api/v1/pages/{pg}/detail")
        assert r.status_code == 200, r.text
        assert sorted(v["token_cost"] for v in r.json()["regions"]) == [318, 542]

    async def test_vung_dung_engine_MIEN_PHI_thi_tra_NULL_khong_tra_0(self, client):
        """`0` sẽ bị đọc thành 'đã tốn tiền mà hết 0 token'. Hai nghĩa khác hẳn nhau."""
        _pr, pg = _dung_chapter([None, None])
        r = await client.get(f"/api/v1/pages/{pg}/detail")
        assert [v["token_cost"] for v in r.json()["regions"]] == [None, None]

    async def test_chapter_tron_lan_thi_giu_nguyen_tung_vung(self, client):
        _pr, pg = _dung_chapter([100, None, 250])
        got = [v["token_cost"] for v in (await client.get(f"/api/v1/pages/{pg}/detail")).json()["regions"]]
        assert got == [100, None, 250]


class TestTongTokenCuaChapter:
    async def test_cong_dung_tong(self, client):
        pr, _pg = _dung_chapter([542, 318, None])
        r = await client.get(f"/api/v1/projects/{pr}/export-warnings")
        assert r.status_code == 200, r.text
        assert r.json()["token_cost_total"] == 860

    async def test_chua_trang_nao_ton_token_thi_tong_la_NULL(self, client):
        """`SUM` của Postgres trả NULL khi không có dòng nào — giữ nguyên, KHÔNG ép về 0.

        Ép về 0 sẽ khiến màn tóm tắt hiện 'đã tiêu 0 token' cho một chapter chạy hoàn toàn bằng
        engine miễn phí — một câu đúng về số nhưng sai về nghĩa.
        """
        pr, _pg = _dung_chapter([None, None])
        r = await client.get(f"/api/v1/projects/{pr}/export-warnings")
        assert r.json()["token_cost_total"] is None

    async def test_chapter_rong_khong_no(self, client):
        with sync_session() as s:
            pr = Project(name="P1 rỗng", source_lang="en", target_lang="vi",
                         intended_use=IntendedUse.study)
            s.add(pr); s.commit()
            pid = str(pr.id)
        r = await client.get(f"/api/v1/projects/{pid}/export-warnings")
        assert r.status_code == 200
        assert r.json()["token_cost_total"] is None


class TestKhongPhaGiKhac:
    async def test_cac_so_canh_bao_cu_van_con(self, client):
        """Thêm một trường KHÔNG được làm rơi trường nào đang có."""
        pr, _pg = _dung_chapter([10])
        d = (await client.get(f"/api/v1/projects/{pr}/export-warnings")).json()
        for k in ("overflow_warning_count", "needs_manual_count", "font_missing_count",
                  "quality_needs_review_count", "acknowledged"):
            assert k in d, f"mất trường {k}"

    async def test_chapter_CO_CHU_thi_nguoi_khac_bi_chan(self, client, client_b):
        """Chapter phải được tạo QUA API để có chủ thật.

        Lượt viết đầu tôi dựng project thẳng vào CSDL và bài này đỏ với `200` thay vì `404` —
        nhưng đó là **fixture sai**, không phải sản phẩm hở: chapter không có chủ được hệ thống
        **cố ý** cho mọi tài khoản thấy, để chapter tạo từ trước slice B không biến mất. Suýt đi
        sửa sản phẩm cho vừa cái test.
        """
        pr = (await client.post("/api/v1/projects", json={
            "name": "P1 có chủ", "source_lang": "en", "intended_use": "study",
        })).json()["id"]
        _dung_chapter([10], project_id=pr)

        assert (await client.get(f"/api/v1/projects/{pr}/export-warnings")).status_code == 200
        assert (await client_b.get(f"/api/v1/projects/{pr}/export-warnings")).status_code == 404
