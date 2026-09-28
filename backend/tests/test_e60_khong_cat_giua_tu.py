"""E60 — không cắt giữa từ, và không nướng khung đỏ vào tệp người đọc tải về.

## Hai lỗi, cùng một trang thật

Chủ dự án chạy một trang manga thật (28-09-2026) và gửi ảnh kết quả. Hai thứ hỏng nhìn thấy ngay:

1. **Khung đỏ nằm giữa truyện.** Đó là dấu cảnh báo tràn khung của `PagePreviewRenderer`
   (`mark_overflow`, mặc định `True`) — dấu dành cho người **rà soát** trên ảnh xem thử. Đường
   **xuất tệp** dựng renderer mà không truyền `mark_overflow=False`, nên nó bị vẽ vào chính file
   người đọc tải về.

2. **Chữ vỡ từng ký tự**: `VÒNG QUA` → `VỌN / G QUA`, `TRẮNG` → `TRẢ / NG`.

## Cơ chế của lỗi 2 — và vì sao bộ căn cỡ chữ KHÔNG thấy nó

`wrap_to_width` cắt token theo **ký tự** khi token rộng hơn khung. Chú thích gốc nói nhánh đó dành
cho "URL, tên chiêu thức". Nhưng bong bóng **dọc hẹp** kiểu Nhật làm `max_width` rất nhỏ, nên **từ
tiếng Việt bình thường** cũng rơi vào đó.

Và cắt theo ký tự làm bề rộng **luôn vừa** ⇒ phép kiểm `w <= rect.width` luôn qua ⇒ vòng dò cỡ chữ
**không bao giờ biết** khung quá hẹp. Nó chỉ thấy chiều cao sai, thu nhỏ chữ, rồi trả `FIT_OK` cho
một khối chữ vỡ vụn. Lỗi tự che mắt chính phép đo dùng để phát hiện nó.
"""
from __future__ import annotations

import glob

import pytest
from PIL import ImageFont

from app.services.interfaces import BBox
from app.services.typeset.fitter import FitToBoxTypesetter
from app.services.typeset.layout import TextLayoutEngine

FONT = glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)[0]


class _Resolver:
    """Bộ cấp font tối thiểu — test này đo NGẮT DÒNG, không đo chọn font."""

    def resolve(self, _family: str, size: int):
        return ImageFont.truetype(FONT, int(size))

    def assert_can_render(self, _font, _text) -> None:
        return None


def _fitter(**kw) -> FitToBoxTypesetter:
    tham_so = dict(
        font_resolver=_Resolver(),
        min_font_size=10,
        max_font_size=40,
        padding_ratio=0.06,
        line_spacing_ratio=0.2,
        stroke_width=0,
    )
    tham_so.update(kw)
    return FitToBoxTypesetter(**tham_so)


def _co_dong_cat_giua_tu(wrapped: str, nguyen_van: str) -> bool:
    """Có dòng nào KHÔNG phải một (hoặc nhiều) từ trọn vẹn của câu gốc không."""
    tu_that = set(nguyen_van.split())
    for dong in wrapped.split("\n"):
        for tu in dong.split():
            if tu not in tu_that:
                return True
    return False


# ── Bộ ngắt dòng ──────────────────────────────────────────────────────────────────────────


def test_bao_ra_khi_phai_cat_giua_tu():
    e = TextLayoutEngine()
    font = ImageFont.truetype(FONT, 20)
    rong, cat_rong = e.wrap_bao_cat_tu("VÒNG QUA ĐÂY", font, 400)
    hep, cat_hep = e.wrap_bao_cat_tu("VÒNG QUA ĐÂY", font, 40)

    assert cat_rong is False and "\n" not in rong
    assert cat_hep is True, "khung 40px không chứa nổi một từ ⇒ phải báo là đã cắt giữa từ"


def test_wrap_to_width_giu_nguyen_chu_ky_cu():
    """Nhiều nơi đang gọi `wrap_to_width` và mong nhận CHUỖI. Đổi kiểu trả về là làm hỏng chúng."""
    e = TextLayoutEngine()
    kq = e.wrap_to_width("một hai ba", ImageFont.truetype(FONT, 20), 400)
    assert isinstance(kq, str)


# ── Bộ căn cỡ chữ ─────────────────────────────────────────────────────────────────────────


def test_BONG_BONG_DOC_HEP_khong_con_vo_tung_ky_tu():
    """BÀI CANH NẶNG NHẤT — tái hiện đúng hình dạng đã gây lỗi trên trang thật.

    Bong bóng dọc kiểu Nhật: **hẹp và cao**. Trước E60, bộ căn trả `FIT_OK` ở cỡ chữ to kèm một
    khối chữ vỡ vụn, vì cắt theo ký tự làm bề rộng luôn "vừa".
    """
    cau = "VÒNG QUA ĐÂY ĐI"
    kq = _fitter().fit(cau, BBox(x=0, y=0, w=60, h=420), "bất kỳ")

    assert not _co_dong_cat_giua_tu(kq["wrapped_text"], cau), (
        f"vẫn cắt giữa từ: {kq['wrapped_text']!r}"
    )


def test_khung_hep_thi_THU_NHO_chu_chu_khong_cat_tu():
    """Hệ quả trực tiếp: cùng một câu, khung càng hẹp thì cỡ chữ càng nhỏ — chứ không phải giữ cỡ
    to rồi băm chữ ra."""
    cau = "VÒNG QUA ĐÂY ĐI"
    rong = _fitter().fit(cau, BBox(x=0, y=0, w=300, h=420), "bất kỳ")
    hep = _fitter().fit(cau, BBox(x=0, y=0, w=70, h=420), "bất kỳ")

    assert hep["font_size"] < rong["font_size"]
    assert not _co_dong_cat_giua_tu(hep["wrapped_text"], cau)


def test_khung_qua_hep_cho_CA_CO_NHO_NHAT_thi_van_ve_va_BAO_TRAN():
    """Bong bóng hẹp tới mức cỡ nhỏ nhất cũng không chứa nổi một từ: không có cách vẽ nào đúng.

    Lúc đó **vẫn phải hiện chữ** (im lặng bỏ trống còn tệ hơn) và phải gắn cảnh báo tràn. Đây là
    chỗ DUY NHẤT còn được cắt giữa từ — cắt là lựa chọn cuối, không phải đường đi thường.
    """
    kq = _fitter().fit("NGHIÊNGNGẢ", BBox(x=0, y=0, w=22, h=400), "bất kỳ")
    assert kq["fit_status"] == "overflow_warning"
    assert kq["wrapped_text"].strip(), "phải vẫn có chữ, không được trả rỗng"


def test_khung_rong_KHONG_bi_thu_nho_oan():
    """Đối chứng âm: bản vá không được làm chữ nhỏ đi ở khung bình thường.

    Nếu nó thu nhỏ cả khi không cần, mọi trang đều xấu đi — đắt hơn nhiều so với lỗi đang sửa.
    """
    kq = _fitter().fit("Chào cậu", BBox(x=0, y=0, w=320, h=200), "bất kỳ")
    assert kq["fit_status"] == "fit_ok"
    assert kq["font_size"] == 40.0, "khung rộng rãi thì phải lấy cỡ LỚN NHẤT như trước"


def test_mot_tu_dai_khong_khoang_trang_van_cat_duoc():
    """Nhánh gốc vẫn phải sống: URL / tên chiêu thức dài không có khoảng trắng thì buộc phải cắt,
    không thì nó tràn ngang vô hạn."""
    cau = "https://mot-dia-chi-rat-rat-dai.example.com/duong/dan/sau"
    kq = _fitter().fit(cau, BBox(x=0, y=0, w=90, h=400), "bất kỳ")
    assert "\n" in kq["wrapped_text"], "token dài vẫn phải được cắt xuống dòng"


# ── Khung đỏ không được vào tệp xuất ──────────────────────────────────────────────────────


def test_KHONG_anh_nao_bi_nuong_khung_do_vao():
    """**Bài canh cấu trúc.** Mặc định của renderer phải là **KHÔNG** vẽ dấu tràn.

    ## Bản trước của bài này khẳng định NGƯỢC LẠI, và nó SAI

    Lượt E60 đầu, bài này đòi `render_page_preview` **giữ** khung đỏ, với lý do *"đó là đường duy
    nhất người rà soát thấy chỗ tràn"*.

    Lý do đó **sai, và kiểm được là sai**: giao diện web đã vẽ cảnh báo tràn ở phía máy khách
    (`BboxOverlay.jsx` đọc `fit_status === 'overflow_warning'`), và số vùng tràn hiện ở ba chỗ khác
    (`ChapterProgress`, `ChapterSummary`, `ExportPanel`). Khung đỏ trong ảnh là **thừa**.

    Và nó có hại thật: `GET /doc-truyen/trang/{id}/anh` — đường trang chủ dùng để **tải ảnh về cho
    người dùng** — phục vụ chính ảnh preview đó. Nên bản vá E60 đầu (chỉ tắt ở đường xuất ZIP/CBZ)
    **không chạm tới đường người dùng thật sự đi**. Chủ dự án chạy lại trang của họ và khung đỏ vẫn
    còn — đó là cách phát hiện.
    """
    import inspect

    from app.services.typeset.preview import PagePreviewRenderer
    from app.workers import tasks

    mac_dinh = inspect_signature_defaults(PagePreviewRenderer)
    assert mac_dinh["mark_overflow"] is False, (
        "mặc định phải TẮT — mặc định bật là lý do lỗi gốc lọt: tham số có sẵn, không ai truyền"
    )

    for ten_ham in ("_run_export", "render_page_preview"):
        src = inspect.getsource(getattr(tasks, ten_ham))
        assert "PagePreviewRenderer(" in src, f"bài canh đọc nhầm hàm {ten_ham}"
        assert "mark_overflow=True" not in src, (
            f"{ten_ham} không được bật dấu tràn: ảnh này tới tay NGƯỜI ĐỌC"
        )


def test_GO_KHUNG_DO_khoi_anh_thi_GIAO_DIEN_phai_con_cho_hien_canh_bao():
    """Đối chứng cặp — thứ khiến việc gỡ khung đỏ là AN TOÀN chứ không phải giấu lỗi.

    Gỡ dấu khỏi ảnh chỉ đúng **khi** cảnh báo tràn còn hiện ở chỗ khác. Bài này canh đúng điều đó ở
    phía giao diện: `BboxOverlay.jsx` phải còn đọc `fit_status === 'overflow_warning'` để vẽ vùng
    tràn trên màn.

    Ai xoá lớp phủ đó sẽ làm bài này đỏ, và phải quyết lại: hoặc trả cảnh báo về chỗ khác, hoặc bật
    lại `mark_overflow`. Không có bài này thì việc gỡ dấu khỏi ảnh biến một lỗi NHÌN THẤY ĐƯỢC thành
    một lỗi im lặng — tệ hơn ban đầu.
    """
    from pathlib import Path

    goc = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "BboxOverlay.jsx"
    assert goc.exists(), f"không thấy {goc} — bài canh này đọc nhầm đường dẫn"
    src = goc.read_text(encoding="utf-8")
    assert "overflow_warning" in src, (
        "giao diện phải còn chỗ hiện vùng TRÀN KHUNG — nếu không thì gỡ khung đỏ khỏi ảnh là "
        "giấu lỗi, không phải dọn rác"
    )


def inspect_signature_defaults(cls) -> dict:
    import inspect

    return {
        ten: tham.default
        for ten, tham in inspect.signature(cls.__init__).parameters.items()
        if tham.default is not inspect.Parameter.empty
    }


@pytest.mark.parametrize("cau", ["Ừm... Hoàn hảo.", "Cái đó là thật à?", "Có lẽ là lần sau"])
def test_cau_thoai_thuong_trong_bong_bong_thuong_van_nguyen_ven(cau):
    """Ba câu thoại thật lấy từ các lượt chạy trước, trong bong bóng cỡ bình thường."""
    kq = _fitter().fit(cau, BBox(x=0, y=0, w=240, h=180), "bất kỳ")
    assert not _co_dong_cat_giua_tu(kq["wrapped_text"], cau)
