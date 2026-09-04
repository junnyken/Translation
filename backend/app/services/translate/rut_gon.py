"""Dịch lại NGẮN HƠN cho vừa bong bóng (E18).

## Vì sao có bước này

Bong bóng manga được vẽ vừa đúng lượng chữ tiếng Nhật. Bản dịch tiếng Việt dài gấp hai ba lần
là chuyện thường — đo trên trang thật 04/09: một bong bóng chứa ~30 ký tự Nhật nhận về bản dịch
**105 ký tự**, và tràn khung kể cả sau khi đã nới khung hết cỡ (A1).

Tới đó thì **không có cách xếp chữ nào cứu được nữa**: chữ dài hơn chỗ chứa là chuyện vật lý.
Chỗ duy nhất còn sửa được là **chính bản dịch** — và bước dịch hiện không hề biết bong bóng to
bao nhiêu, nó dịch xong rồi mới có người đi tìm chỗ nhét.

## Ranh giới

- **Không tự chạy.** Rút gọn là làm mất chữ của bản dịch đầy đủ, nên phải do người dùng bấm.
- **Không đụng vùng người dùng đã sửa tay.** Đè lên chữ người ta tự gõ là việc không ai xin.
- **Không hứa là sẽ vừa.** Rút gọn xong vẫn chạy `fit()` thật; vẫn tràn thì vẫn báo tràn.
- **Đưa cả chữ gốc vào prompt**: để model dịch lại cho gọn theo nghĩa gốc, chứ không phải cắt
  cụt câu tiếng Việt đang có — cắt cụt thì mất nghĩa mà vẫn sai.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: `số. <bản dịch ngắn>` — cùng khuôn với các prompt khác của hệ thống.
_DONG = re.compile(r"^(\d{1,3})\s*[.)\]-]\s*(.*)$")

#: Từ bắt đầu bằng chữ HOA nằm giữa câu — cách nhận tên riêng đủ dùng mà không cần từ điển.
#: Chỉ xét từ không đứng ngay sau dấu kết câu, để không nhặt nhầm chữ đầu câu.
_TU = re.compile(r"[^\W\d_]+", re.UNICODE)

#: Bản rút gọn phải dùng ít nhất ngần này phần SỨC CHỨA. Dưới mức đó là model bỏ đi thông tin
#: trong khi vẫn còn chỗ để giữ — không còn là rút gọn mà là xoá.
#:
#: Đo trên trang thật 04/05: "Bạn không nghĩ vậy sao?" (23 ký tự) bị trả về đúng **một dấu
#: hỏi**, và bộ lọc cũ nhận vì nó "ngắn hơn bản cũ và không rỗng".
#:
#: Neo vào SỨC CHỨA chứ không vào độ dài bản cũ: bong bóng tí hon thì rút từ 200 ký tự xuống 25
#: là đúng việc phải làm, phạt nó là làm E18 vô dụng đúng ở ca cần nhất. Cái sai không nằm ở
#: "ngắn hơn bản cũ bao nhiêu" mà ở "còn chỗ mà không dùng".
TY_LE_SUC_CHUA_NHO_NHAT = 0.35
#: …và dù tỉ lệ có đạt, dưới ngần này ký tự thì cũng không còn là một câu thoại.
DAI_NGAN_NHAT = 4


#: Từ tiếng Việt hay bị viết hoa giữa câu mà KHÔNG phải tên riêng — chủ yếu là đại từ xưng hô
#: và liên từ đầu mệnh đề. Thiếu danh sách này thì "Tôi" bị coi là tên riêng, và mọi bản rút gọn
#: đổi cách xưng hô đều bị loại oan.
#:
#: Danh sách ngắn có chủ đích: nó chỉ cần đủ để không phạt nhầm, còn sót vài từ thì hậu quả là
#: giữ nguyên bản dịch cũ — an toàn. Ngược lại, nhét cả từ điển vào đây mới là chỗ nguy hiểm.
_KHONG_PHAI_TEN = frozenset({
    "tôi", "tớ", "mình", "cậu", "bạn", "anh", "chị", "em", "ông", "bà", "cô", "chú", "bác",
    "họ", "nó", "ta", "chúng", "và", "nhưng", "vì", "nếu", "thì", "mà", "rồi", "còn", "vậy",
})


def ten_rieng(text: str) -> set[str]:
    """Tên riêng đoán được trong một câu: từ viết hoa KHÔNG đứng đầu câu.

    Không dùng từ điển, không gọi mạng — chỉ cần đủ để **bắt lỗi bỏ mất tên riêng**, việc mà
    prompt đã dặn model nhưng model vẫn làm (đo trên trang thật: "Kazudake" biến mất khỏi bản
    rút gọn). Dặn suông không phải là chốt chặn; chỗ này mới là.
    """
    ket: set[str] = set()
    for cau in re.split(r"[.!?…]+", text or ""):
        tu = _TU.findall(cau)
        for t in tu[1:]:                       # bỏ từ đầu câu — viết hoa là chuyện đương nhiên
            if t[:1].isupper() and t.lower() not in _KHONG_PHAI_TEN:
                ket.add(t.lower())
    return ket


@dataclass(frozen=True)
class MucRutGon:
    """Một vùng cần rút gọn: chữ gốc, bản dịch hiện tại, và sức chứa đo được."""

    chu_goc: str
    ban_dich: str
    suc_chua: int


def dung_prompt(muc: list[MucRutGon], source_lang: str) -> str:
    def _mot_muc(i: int, m: MucRutGon) -> str:
        dong = (
            f"{i + 1}. [tối đa {m.suc_chua} ký tự] gốc: {m.chu_goc or '(không đọc được)'}\n"
            f"   bản dịch hiện tại ({len(m.ban_dich)} ký tự): {m.ban_dich}"
        )
        ten = sorted(ten_rieng(m.ban_dich))
        if ten:
            dong += f"\n   PHẢI GIỮ NGUYÊN tên riêng: {', '.join(ten)}"
        return dong

    danh_sach = "\n".join(_mot_muc(i, m) for i, m in enumerate(muc))
    return (
        "Bạn là biên tập viên truyện tranh tiếng Việt.\n\n"
        "Những câu thoại dưới đây **dài hơn bong bóng chứa được**, nên đang bị tràn ra ngoài "
        "khung. Hãy viết lại NGẮN HƠN cho vừa, dựa vào chữ gốc.\n\n"
        "Quy tắc bắt buộc:\n"
        f"- Trả về ĐÚNG {len(muc)} dòng, đánh số 1..{len(muc)} theo đúng thứ tự đầu vào.\n"
        "- Mỗi dòng KHÔNG vượt quá số ký tự ghi trong ngoặc vuông của mục đó.\n"
        "- Nhưng hãy **dùng gần hết** số ký tự cho phép. Rút ngắn hơn mức cần là bỏ đi thông "
        "tin mà lẽ ra vẫn còn chỗ để giữ.\n"
        "- Giữ ĐÚNG Ý và giọng điệu nhân vật. Được bỏ từ đệm, gộp câu, dùng từ ngắn hơn; "
        "KHÔNG được bỏ mất thông tin chính (tên riêng, con số, câu hỏi vẫn phải là câu hỏi).\n"
        "- Thoại truyện tranh vốn ngắn gọn — viết như người Việt nói, không viết văn.\n"
        "- Nếu bản dịch hiện tại đã đủ ngắn, chép lại nguyên văn.\n"
        "- Không thêm giải thích, không thêm dòng nào ngoài danh sách đã đánh số.\n\n"
        f"### Ngôn ngữ gốc: {source_lang}\n{danh_sach}"
    )


def phan_tich(text: str, muc: list[MucRutGon]) -> list[str | None]:
    """Tách phản hồi thành đúng `len(muc)` phần tử. `None` = KHÔNG dùng được, giữ bản cũ.

    Bị loại khi:

    - thiếu dòng · dòng rỗng · **dài hơn bản dịch hiện tại** (viết dài thêm thì rút gọn vô nghĩa)
    - **không còn chữ cái nào** — đo trên trang thật: một câu 23 ký tự bị trả về đúng `?`
    - **dùng chưa tới 35% sức chứa, hoặc dưới 4 ký tự** — còn chỗ mà không dùng thì là xoá,
      không phải rút gọn
    - **đánh rơi tên riêng** có trong bản cũ (`Kazudake` biến mất khỏi bản rút gọn ở trang thật)

    Cố ý KHÔNG loại dòng chỉ vì vượt quá sức chứa vài ký tự: sức chứa là ước lượng, còn bên có
    thẩm quyền nói vừa hay không là `fit()` chạy ngay sau đó. Loại ở đây là vứt đi một bản dịch
    ngắn hơn hẳn chỉ vì lệch con số ước lượng.

    Bị loại nghĩa là **giữ nguyên bản cũ** — vùng đó tiếp tục báo tràn. Một cảnh báo tràn thành
    thật tốt hơn một câu thoại bị xoá mất mà không ai biết.
    """
    thu: dict[int, str] = {}
    for raw in (text or "").splitlines():
        dong = raw.strip()
        if not dong or dong.startswith("#"):
            continue
        m = _DONG.match(dong)
        if not m:
            continue
        i = int(m.group(1))
        if 1 <= i <= len(muc):
            thu[i] = m.group(2).strip()

    ket: list[str | None] = []
    for i, cu in enumerate(muc, start=1):
        moi = thu.get(i, "")
        if not moi or len(moi) >= len(cu.ban_dich):
            ket.append(None)
        elif not _TU.search(moi):
            ket.append(None)                                   # chỉ còn dấu câu
        elif len(moi) < max(DAI_NGAN_NHAT, TY_LE_SUC_CHUA_NHO_NHAT * cu.suc_chua):
            ket.append(None)                                   # xoá chứ không phải rút gọn
        elif ten_rieng(cu.ban_dich) - ten_rieng(moi):
            ket.append(None)                                   # đánh rơi tên riêng
        else:
            ket.append(moi)
    return ket
