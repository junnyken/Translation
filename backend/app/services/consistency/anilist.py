"""E17 tầng 3b — đối chiếu danh xưng của chapter với CSDL nhân vật AniList.

## Vì sao thêm nguồn ngoài, và vì sao vẫn KHÔNG lấy danh sách từ nó

Tầng 3a (`goi_y_ten.py`) hỏi mô hình cách dịch. Mô hình **luôn trả lời kể cả khi không biết**.
AniList thì khác về bản chất: nó là **CSDL có thật**, tra được, không bịa.

Nhưng đo trước khi tin (2026-09-04, API thật):

    One Piece / Chainsaw Man (MANGA)  -> 500 nhân vật
    một chapter thật                  ->   3 danh xưng
    "Naruto" bản MANGA                ->   2 nhân vật   (bản ANIME: 500)
    mô tả nhân vật                    -> chiều cao, gia đình, liên kết — KHÔNG có cách xưng hô

Ba kết luận, và cả ba đều định hình thiết kế này:

1. **Quy mô lệch 150 lần** ⇒ đổ danh sách CSDL vào glossary là làm mọi lượt rà soát ngập cảnh báo
   vô nghĩa. Nên **chapter vẫn là nguồn quyết định CẦN GÌ**; AniList chỉ trả lời VIẾT THẾ NÀO.
2. **Phủ sóng không đều** ⇒ không tìm thấy là chuyện bình thường, phải nói thẳng "không có dữ
   liệu", không được im lặng để người dùng tưởng đã đối chiếu xong.
3. **Không có dữ liệu xưng hô** ⇒ tầng 2 (đọc kính ngữ/đại từ có thật trong bản gốc) vẫn là nguồn
   duy nhất cho việc đó. AniList không thay được, và không được giả vờ thay được.

## Cổng đối chiếu — giống hệt tầng 3a

Mọi nhân vật AniList trả về mà **không khớp một danh xưng nào của chapter** đều bị **loại thẳng**
và đếm vào `bo_qua`. Con số ấy giữ nguyên để nhìn: nó cho biết CSDL rộng hơn chapter bao nhiêu.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

API_URL = "https://graphql.anilist.co"

#: Tự xưng danh cho tử tế: nguồn miễn phí có quyền biết ai đang gọi mình, và nếu ta gây phiền
#: thì họ chặn được đúng ta thay vì chặn cả dải.
USER_AGENT = "Translation-MTE/1.0 (manga translation tool; contact via repo)"

#: Một lượt hỏi lấy tối đa chừng này nhân vật. AniList phân trang 25/lượt và giới hạn 90 req/phút;
#: lấy 50 là đủ phủ dàn chính của gần như mọi bộ mà chỉ tốn 2 lượt.
TRAN_NHAN_VAT = 50

_TRUY_VAN = """
query ($ten: String, $so: Int) {
  Media(search: $ten, type: MANGA) {
    id
    title { romaji native english }
    characters(perPage: $so, sort: FAVOURITES_DESC) {
      nodes { name { full native alternative } }
    }
  }
}
"""


@dataclass
class TenChinhThuc:
    """Một danh xưng của chapter đã tìm thấy bản ghi tương ứng trong CSDL."""

    #: Danh xưng ĐÚNG NHƯ chapter viết. Không bao giờ thay bằng dạng của CSDL.
    danh_xung: str
    ten_day_du: str | None = None
    ten_goc: str | None = None
    ten_khac: list[str] = field(default_factory=list)
    #: Khớp nhờ đâu — hiện thẳng cho người dùng, giống mọi tầng khác của E17.
    ly_do: str = ""


@dataclass
class KetQuaDoiChieu:
    tim_thay_bo_truyen: str | None = None
    khop: list[TenChinhThuc] = field(default_factory=list)
    #: Số nhân vật CSDL trả về nhưng KHÔNG có trong chapter ⇒ bị loại. Giữ để nhìn thấy độ lệch.
    bo_qua: int = 0
    #: Vì sao không có kết quả. `None` = chạy bình thường.
    khong_dung_duoc: str | None = None


def _cac_dang(nv: dict) -> list[tuple[str, str]]:
    """Mọi cách viết của một nhân vật, kèm nhãn để giải thích vì sao khớp."""
    ten = nv.get("name") or {}
    ra: list[tuple[str, str]] = []
    if ten.get("full"):
        ra.append((ten["full"], "tên đầy đủ"))
        # Chapter thường chỉ gọi "Naruto" trong khi CSDL ghi "Naruto Uzumaki" — không tách phần
        # thì gần như không bao giờ khớp được gì.
        for phan in ten["full"].split():
            if len(phan) >= 2:
                ra.append((phan, "một phần của tên đầy đủ"))
    if ten.get("native"):
        ra.append((ten["native"], "tên gốc"))
    for k in ten.get("alternative") or []:
        if k and len(k) >= 2:
            ra.append((k, "tên gọi khác"))
    return ra


def doi_chieu(danh_xung_chapter: list[str], nhan_vat: list[dict],
              ten_bo_truyen: str | None) -> KetQuaDoiChieu:
    """Ghép danh xưng của CHAPTER với nhân vật CSDL. Thuần tính toán, không gọi mạng.

    Tách khỏi phần gọi mạng có chủ đích: phần quyết định đúng/sai phải test được mà không phụ
    thuộc một dịch vụ bên ngoài có thể sập bất cứ lúc nào.
    """
    kq = KetQuaDoiChieu(tim_thay_bo_truyen=ten_bo_truyen)
    if not danh_xung_chapter:
        return kq

    # Khoá so khớp: bỏ hoa/thường và khoảng trắng hai đầu. KHÔNG bỏ dấu, không rút gọn — hai
    # danh xưng khác nhau bị gộp làm một còn tệ hơn là không khớp được cái nào.
    cua_chapter = {dx.strip().casefold(): dx for dx in danh_xung_chapter if dx and dx.strip()}
    da_khop: dict[str, TenChinhThuc] = {}

    for nv in nhan_vat:
        trung = None
        for dang, nhan in _cac_dang(nv):
            goc = cua_chapter.get(dang.strip().casefold())
            if goc is not None:
                trung = (goc, nhan)
                break
        if trung is None:
            kq.bo_qua += 1
            continue
        goc, nhan = trung
        if goc in da_khop:
            continue          # đã khớp bằng một nhân vật khác rồi, giữ bản đầu cho tất định
        ten = nv.get("name") or {}
        da_khop[goc] = TenChinhThuc(
            danh_xung=goc,
            ten_day_du=ten.get("full"),
            ten_goc=ten.get("native"),
            ten_khac=[k for k in (ten.get("alternative") or []) if k][:5],
            ly_do=f"khớp {nhan} trong CSDL AniList",
        )

    # Sắp theo thứ tự danh xưng của chapter để kết quả TẤT ĐỊNH, không phụ thuộc thứ tự CSDL trả.
    kq.khop = [da_khop[dx] for dx in danh_xung_chapter if dx in da_khop]
    return kq


def hoi_anilist(ten_bo_truyen: str, timeout: float = 10.0,
                so_nhan_vat: int = TRAN_NHAN_VAT) -> tuple[str | None, list[dict], str | None]:
    """Gọi AniList. Trả `(tên bộ tìm được, danh sách nhân vật, lý do không dùng được)`.

    Dùng `urllib` của thư viện chuẩn, theo đúng tiền lệ của engine dịch (`translate/engines.py`).
    Không kéo thêm `httpx` vào chỉ để gọi một endpoint — `httpx` hiện chỉ là phụ thuộc GIÁN TIẾP,
    không khai trong `requirements.txt`, nên dựa vào nó là dựa vào một thứ có thể biến mất ở lần
    nâng phiên bản bất kỳ.

    **Không bao giờ ném ra ngoài.** Nguồn ngoài sập thì tính năng này mất, chứ không được kéo
    theo cả lượt rà soát. Nhưng cũng KHÔNG im lặng: lý do được trả về để hiện thẳng cho người dùng
    — "không tìm thấy" và "AniList đang hỏng" là hai chuyện khác nhau, và gộp chúng lại là nói dối.
    """
    import json
    import urllib.error
    import urllib.request

    than = json.dumps({
        "query": _TRUY_VAN,
        "variables": {"ten": ten_bo_truyen, "so": max(1, min(so_nhan_vat, TRAN_NHAN_VAT))},
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=than,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # BẮT BUỘC. AniList đứng sau Cloudflare và trả 403 cho User-Agent mặc định của
            # urllib ("Python-urllib/3.x"). Đo được 2026-09-04: cùng truy vấn, curl 200 /
            # urllib 403 — khác biệt duy nhất là dòng này.
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            goi = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            # Vượt giới hạn nhịp (AniList cho 90 lượt/phút). Nói rõ là CHỜ ĐƯỢC — rất khác
            # "không có truyện này", vì hai câu dẫn người dùng đi sửa hai chỗ khác nhau.
            return None, [], "AniList đang giới hạn số lượt hỏi, thử lại sau một phút"
        if e.code == 404:
            # AniList báo "không tìm thấy" bằng HTTP 404 chứ KHÔNG phải bằng `Media: null` như
            # tưởng ban đầu — đo được trên host 2026-09-04:
            #     {"errors":[{"message":"Not Found.","status":404}],"data":{"Media":null}}
            # Bản đầu rơi vào nhánh lỗi chung và hiện "AniList trả lỗi 404" — một câu kỹ thuật
            # không giúp người dùng biết phải làm gì.
            return None, [], f"AniList không có bộ truyện nào tên {ten_bo_truyen!r}"
        return None, [], f"AniList trả lỗi {e.code}"
    except Exception as e:  # noqa: BLE001 — gồm cả timeout, DNS, mạng đứt
        logger.warning("hỏi AniList hỏng: %s", e)
        return None, [], "không kết nối được tới AniList"

    if goi.get("errors"):
        return None, [], "AniList từ chối truy vấn"
    media = (goi.get("data") or {}).get("Media")
    if not media:
        return None, [], f"AniList không có bộ truyện nào tên {ten_bo_truyen!r}"

    tieu_de = media.get("title") or {}
    ten = tieu_de.get("romaji") or tieu_de.get("english") or tieu_de.get("native")
    nodes = ((media.get("characters") or {}).get("nodes")) or []
    return ten, nodes, None


def tra_ten_chinh_thuc(danh_xung_chapter: list[str], ten_bo_truyen: str,
                       timeout: float = 10.0) -> KetQuaDoiChieu:
    """Đường vào chính: lấy danh xưng CỦA CHAPTER đi hỏi AniList, rồi đối chiếu."""
    ten, nhan_vat, loi = hoi_anilist(ten_bo_truyen, timeout=timeout)
    if loi is not None:
        return KetQuaDoiChieu(khong_dung_duoc=loi)
    kq = doi_chieu(danh_xung_chapter, nhan_vat, ten)
    logger.info(
        "AniList %r: %d nhân vật, khớp %d danh xưng của chapter, bỏ qua %d",
        ten_bo_truyen, len(nhan_vat), len(kq.khop), kq.bo_qua,
    )
    return kq
