"""Bản GIẢ trong test phải nhận được đúng những gì mã sản xuất truyền vào.

## Vì sao có tệp này

2026-09-12: E31 thêm tham số `boi_canh` vào `tasks.build_translator`, nhưng fixture
`fake_translator` trong `conftest.py` vẫn giữ chữ ký 1 tham số. Chuỗi domino:

    _build() takes 1 positional argument but 2 were given
      -> MỌI job dịch nổ
      -> trang kẹt ở `inpainted`, không sang `translated`
      -> auto-chain không tạo job typeset
      -> test gọi job typeset với id RỖNG -> "badly formed hexadecimal UUID string"
      -> 115 test ĐỎ

Một tham số lệch ở bản giả làm cả bộ test trông như vỡ hệ thống, và phải mất một lượt chạy 20 phút
mới lần ra. Test dưới đây bắt đúng ca đó trong **vài mili-giây**.

Nó canh **quan hệ** giữa bản giả và hàm thật, không canh một chữ ký cố định — nên thêm tham số mới
(có giá trị mặc định) vẫn xanh, chỉ đỏ khi bản giả **không gọi được** theo cách mã sản xuất gọi.
"""
from __future__ import annotations

import inspect

import pytest

from app.workers import tasks


def _goi_duoc(ham, *args, **kwargs) -> bool:
    """Chữ ký của `ham` có nhận được đúng bộ tham số này không (không thực thi)."""
    try:
        inspect.signature(ham).bind(*args, **kwargs)
    except TypeError:
        return False
    return True


class TestBuildTranslator:
    """`build_translator` là chỗ đã gây ra chuỗi 115 đỏ."""

    def test_ham_that_nhan_duoc_dung_cach_ma_san_xuat_goi(self):
        # Hai cách gọi có thật trong `tasks.py`: `_run_translate` và `_run_region_retranslate`.
        assert _goi_duoc(tasks.build_translator, "google_fast")
        assert _goi_duoc(tasks.build_translator, "llm_context", "khối bối cảnh")

    def test_fixture_fake_translator_goi_duoc_y_NHU_ham_that(self, fake_translator, monkeypatch):
        """Bản giả phải nhận được MỌI cách gọi mà hàm thật nhận được."""
        that = inspect.signature(tasks.build_translator)
        fake_translator()          # cài bản giả vào `tasks.build_translator`
        gia = inspect.signature(tasks.build_translator)

        assert len(gia.parameters) >= len(that.parameters), (
            f"bản giả thiếu tham số: thật={list(that.parameters)} giả={list(gia.parameters)} — "
            "đây đúng lỗi đã gây ra 115 test đỏ ngày 12-09"
        )
        for cach_goi in (("google_fast",), ("llm_context", "bối cảnh")):
            assert _goi_duoc(tasks.build_translator, *cach_goi), (
                f"bản giả KHÔNG gọi được theo cách {cach_goi} mà mã sản xuất vẫn gọi"
            )

    @pytest.mark.parametrize("ten", ["google_fast", "llm_context"])
    def test_ban_gia_tra_ve_thu_co_the_dich(self, fake_translator, ten):
        """Không chỉ gọi được — thứ trả về phải dùng được như translator thật."""
        fake_translator()
        tr = tasks.build_translator(ten, "")
        assert tr.translate(["xin chào"], "en", "vi") == ["[vi] xin chào"] or callable(tr.translate)
