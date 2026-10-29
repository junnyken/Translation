"""E66 — prompt dịch không được BỊA TRÔI CHẢY từ chữ rác.

## Lỗi đang sửa — đo trên trang thật, 28-09-2026

Chạy CÙNG một trang (368×543) hai lần qua production. Chữ OCR đọc ra **khác nhau**, và bản dịch
của cả hai lượt đều trôi chảy, không có dấu hiệu nào cho người đọc biết chữ gốc đã sai:

| Vị trí | Lượt 1 | Lượt 2 |
|---|---|---|
| (13,13) | `あの妹山です` → "Đó là Seyama." | `あの暁山です` → **"Đó là núi Akatsuki."** |
| (11,1) | `あっこも天音が好き…` → "Akko… thích Amane" | `あっでも元者が好き…` → **"người yêu cũ"** |
| (6,22) | `心の赤輪` → "vòng đỏ" | `心の家族` → **"gia đình"** |

**Bản dịch không sai.** Nó dịch đúng thứ nó nhận được — `あの暁山です` thật sự nghĩa là "đó là núi
Akatsuki". Hai chỗ sai là:

1. Chữ đọc từ ảnh 368px không ổn định (việc của bước ĐỌC, E65 đã tách xong độ phân giải vẽ —
   nhưng độ phân giải ĐỌC thì vẫn là ảnh gốc, và đó là giới hạn của chính tấm ảnh).
2. Prompt **bảo mô hình tự sửa chữ rác** và **không cho nó đường nào nói "tôi không chắc"**.

Lượt này sửa (2).
"""
from __future__ import annotations

import pytest

from app.services.translate.engines import DAU_KHONG_CHAC, LLMContextTranslator


def _bo_dich(**kw) -> LLMContextTranslator:
    tham = dict(api_keys=["khoa-gia"])
    tham.update(kw)
    return LLMContextTranslator(**tham)


def _prompt(texts=("あの暁山です", "うみちゃん？")) -> str:
    return _bo_dich().build_prompt(list(texts), "ja", "vi")


# ── Prompt ────────────────────────────────────────────────────────────────────────────────


def test_KHONG_con_cau_cho_phep_tu_suy_luan_va_sua():
    """Bài canh hồi quy cho đúng câu đã gây lỗi.

    Câu cũ: *"Đầu vào là chữ do OCR đọc nên có thể sai chính tả; tự suy luận và sửa khi dịch."*
    Nó CHO PHÉP chế, và đo được là mô hình chế thật. Ai viết lại câu này là mở lại lỗi.
    """
    assert "tự suy luận và sửa" not in _prompt()


def test_van_cho_phep_sua_loi_doc_NHO___khong_phai_cam_tiet():
    """Đối chứng: gỡ hẳn quyền sửa là đổi một lỗi lấy một lỗi khác. Lệch một kana mà không cho
    sửa thì mọi trang đều đầy dấu cảnh báo, và cảnh báo nào cũng như nhau thì không ai đọc."""
    p = _prompt()
    assert "NHỎ" in p and "khác hẳn" in p.lower() or "KHÁC HẲN" in p


def test_prompt_day_du_ba_luat_moi():
    p = _prompt()
    assert DAU_KHONG_CHAC in p, "phải dạy mô hình cách báo là đang đoán"
    assert "TÊN RIÊNG" in p, "phải có luật riêng cho tên người / địa danh"
    assert "danh từ chung" in p, "phải cấm thay một cái tên bằng một từ thường"


def test_luat_cam_giai_thich_KHONG_bit_mieng_dau_bao_doan():
    """Hai luật trong cùng một prompt kéo ngược chiều nhau là chỗ mô hình sẽ chọn bừa.

    `"Không thêm giải thích, không thêm dòng nào ngoài danh sách đã đánh số"` bịt miệng mô hình
    ĐÚNG LÚC nó muốn báo là đang đoán — nên nó đành nhét phần đoán vào một câu trôi chảy. Thêm
    dấu mà quên gỡ khoá miệng là thêm một luật chết.
    """
    p = _prompt()
    assert "Không thêm giải thích" in p, "vẫn phải cấm mô hình tán gẫu"
    # E68 đổi CÁCH NÓI: "ngoại lệ của luật cấm giải thích" bị mô hình hiểu thành "được phép
    # giải thích". Nay nói theo hướng ngược lại — liệt kê thứ DUY NHẤT được thêm. Bài canh bám
    # vào hành vi (dấu vẫn được phép) chứ không bám vào một cụm chữ cụ thể.
    assert "DUY NHẤT được thêm" in p, "phải nói rõ dấu báo-đoán vẫn được phép"
    assert DAU_KHONG_CHAC in p


def test_E68_cam_ky_tu_Nhat_trong_ban_dich():
    """Đo thật 28-09 trên trang Pepper&Carrot E02P04: mô hình trả về

        `"* (Chữ trên ảnh là ごくごく - Ực ực)"`

    Chuỗi đó mang ký tự Nhật ⇒ `MissingGlyph` ⇒ **bong bóng để TRỐNG** (đúng lỗi F1). Nguyên nhân:
    câu "dấu [?] là NGOẠI LỆ của luật cấm giải thích" được hiểu thành "được phép giải thích".
    Nên phải cấm thẳng ký tự ngoài tiếng Việt, chứ không chỉ cấm khái niệm "giải thích".
    """
    p = _prompt()
    assert "chỉ được chứa chữ VIỆT" in p
    assert "bỏ trống" in p, "phải nói HẬU QUẢ, không chỉ ra lệnh"
    assert "NGOẠI LỆ DUY NHẤT" not in p, "câu này chính là chỗ mô hình bám vào để giải thích"


def test_E68_cam_danh_dau_tran_lan():
    """`どうして` ("tại sao?") là tiếng Nhật sạch mà vẫn bị đánh dấu — đo được trên trang thật.

    Cảnh báo gắn tràn lan thì người dùng tắt mắt với nó (bài học đã ghi ở dự án SEO: 144 thẻ/ngày
    ⇒ người dùng tắt chuông). Một cảnh báo ai cũng bỏ qua tệ hơn không có cảnh báo.
    """
    assert "rõ nghĩa" in _prompt()


def test_luat_ten_rieng_neu_dung_vi_du_THAT_da_gay_loi():
    """Ví dụ trong prompt lấy từ lỗi THẬT chứ không phải ví dụ bịa — để người sửa prompt sau này
    biết luật đó sinh ra từ đâu."""
    assert "phiên âm" in _prompt()


# ── Bóc dấu ───────────────────────────────────────────────────────────────────────────────


def test_boc_dau_o_dau_dong():
    sach, dd = LLMContextTranslator.tach_dau_khong_chac(
        [f"{DAU_KHONG_CHAC} Đó là núi Akatsuki.", "Umi-chan?"]
    )
    assert sach == ["Đó là núi Akatsuki.", "Umi-chan?"]
    assert dd == {0}


def test_boc_ca_dau_LOT_VAO_GIUA():
    """Mô hình gõ lệch thì dấu rơi vào giữa câu. Để sót một `[?]` là nó bị **nướng vào bong bóng**
    trên ảnh người đọc tải về — tệ hơn hẳn so với không có dấu."""
    sach, dd = LLMContextTranslator.tach_dau_khong_chac([f"Đó là {DAU_KHONG_CHAC} núi nào đó"])
    assert DAU_KHONG_CHAC not in sach[0]
    assert dd == {0}


def test_KHONG_dong_nao_bi_danh_dau_thi_tap_rong():
    """ĐỐI CHỨNG ÂM: trang đọc tốt phải đi qua mà không gắn cờ nào. Gắn cờ tràn lan thì cảnh báo
    mất hết giá trị — người dùng tắt mắt với nó đúng như đã xảy ra ở dự án SEO."""
    sach, dd = LLMContextTranslator.tach_dau_khong_chac(["Chào cậu", "Ừm... hoàn hảo."])
    assert dd == set()
    assert sach == ["Chào cậu", "Ừm... hoàn hảo."]


def test_dong_rong_khong_lam_no():
    sach, dd = LLMContextTranslator.tach_dau_khong_chac(["", None, "  "])
    assert sach == ["", "", ""]
    assert dd == set()


@pytest.mark.parametrize("dong", [f"{DAU_KHONG_CHAC}Sát ngay chữ", f"  {DAU_KHONG_CHAC}   thừa cách"])
def test_khoang_trang_quanh_dau_khong_lam_lech(dong):
    sach, dd = LLMContextTranslator.tach_dau_khong_chac([dong])
    assert dd == {0}
    assert not sach[0].startswith(" ") and "  " not in sach[0]


# ── Nối vào luồng dịch ────────────────────────────────────────────────────────────────────


def test_translate_ghi_lai_chi_so_dong_bi_danh_dau(monkeypatch):
    """Bài canh nối: `translate()` phải TRẢ VỀ chữ sạch và ĐỂ LẠI chỉ số trên `self`.

    Không có bài này thì việc bóc dấu vẫn đúng mà cờ không bao giờ tới được CSDL — đúng hình dạng
    `feedback_tinh_nang_chet_vi_hai_dau_khong_gap`.
    """
    bo = _bo_dich()
    monkeypatch.setattr(
        bo, "_call_api",
        lambda _p: (f"1. Chào cậu\n2. {DAU_KHONG_CHAC} Đó là núi Akatsuki.\n", {}),
    )
    ra = bo.translate(["こんにちは", "あの暁山です"], "ja", "vi")
    assert ra == ["Chào cậu", "Đó là núi Akatsuki."]
    assert bo.vung_khong_chac == {1}


def test_thuoc_tinh_co_san_ngay_ca_khi_chua_dich():
    """Bên gọi đọc bằng `getattr(..., set())`, nhưng thuộc tính vẫn phải có sẵn để không ai phải
    nhớ cái mặc định đó."""
    assert _bo_dich().vung_khong_chac == set()
