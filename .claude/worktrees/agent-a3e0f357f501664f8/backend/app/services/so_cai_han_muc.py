"""Lõi sổ cái hạn mức — giữ chỗ, tiêu, hoàn.

## Ba bảo đảm, và cách từng cái được giữ

### 1. Không tiêu quá hạn mức khi có request song song

Hai request cùng đọc "còn 6", cùng thấy đủ, cùng ghi ⇒ tiêu 12. Kiểm rồi ghi trong hai bước
riêng **luôn** có khe hở này, dù mã trông rất hợp lý.

Chặn bằng **khoá tư vấn của Postgres** (`pg_advisory_xact_lock`) khoá theo *chủ thể*: hai request
của cùng một người bị xếp hàng, còn người khác không bị ảnh hưởng. Khoá tự nhả khi giao dịch kết
thúc — kể cả khi giao dịch đổ — nên không có đường nào bỏ quên khoá.

Không dùng `SELECT ... FOR UPDATE`: chưa chắc có dòng nào để khoá (người mới, chưa dùng lượt nào).

### 2. Thử lại không trừ/hoàn hai lần

Mọi thao tác đi kèm `khoa_idempotency`, và cột đó **duy nhất** ở tầng CSDL. Thử lại lần hai thì
hoặc đụng ràng buộc, hoặc tìm thấy dòng cũ và trả về đúng kết quả cũ. Không dựa vào "kiểm trước
khi ghi" — kiểm trước khi ghi chính là thứ vừa nói ở mục 1.

### 3. Mẻ thành công một phần thì chỉ tiêu phần thành công

Giữ chỗ 8 trang, 5 trang xong, 3 trang hỏng do hệ thống ⇒ dòng giữ chỗ hạ xuống 5 và chuyển
`da_tieu`, đồng thời ghi thêm một dòng `da_hoan` 3 trang để còn truy được. Vì `da_hoan` **không**
được tính vào phần đã dùng, phép cộng ra đúng 5.

## Phần đã dùng tính thế nào

`SUM(so_trang)` của các dòng `giu_cho` **và** `da_tieu`. `giu_cho` phải được tính — nếu không,
hai mẻ đang chạy dở sẽ cùng thấy hạn mức còn nguyên.

## Vì sao có cả bản đồng bộ lẫn bất đồng bộ

Giữ chỗ xảy ra ở API (`AsyncSession`), còn tiêu/hoàn xảy ra ở worker (`sync_session`). Hai bản
dùng **chung** phần dựng câu lệnh bên dưới, nên luật chỉ được viết một lần.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

import sqlalchemy as sa

from app.models import SoCaiHanMuc
from app.models.enums import LoaiChuThe, TrangThaiHanMuc

#: Các trạng thái ĐƯỢC tính vào phần đã dùng. `da_hoan` cố ý không có ở đây.
DANG_CHIEM = (TrangThaiHanMuc.giu_cho, TrangThaiHanMuc.da_tieu)


@dataclass(frozen=True)
class KetQuaGiuCho:
    """Kết quả một lần giữ chỗ.

    `da_co_san` = True nghĩa là khoá này đã được giữ chỗ trước đó và đây là một lượt thử lại —
    **không** phải lỗi, và **không** trừ thêm lượt nào.
    """

    thanh_cong: bool
    da_dung: int
    con_lai: int
    da_co_san: bool = False
    ly_do: str | None = None


def _khoa_chu_the(loai: LoaiChuThe, chu_the: str) -> sa.TextClause:
    """Khoá tư vấn theo chủ thể, tự nhả khi giao dịch kết thúc.

    `hashtextextended` trả về `bigint` — `hashtext` chỉ trả `int4` và dễ đụng trùng hơn.
    """
    return sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))").bindparams(
        k=f"{loai.value}:{chu_the}"
    )


def _cau_da_dung(loai: LoaiChuThe, chu_the: str, ngay: date):
    return sa.select(sa.func.coalesce(sa.func.sum(SoCaiHanMuc.so_trang), 0)).where(
        SoCaiHanMuc.loai_chu_the == loai,
        SoCaiHanMuc.chu_the == chu_the,
        SoCaiHanMuc.ngay_han_muc == ngay,
        SoCaiHanMuc.trang_thai.in_(DANG_CHIEM),
    )


def _cau_tim_khoa(khoa: str):
    return sa.select(SoCaiHanMuc).where(SoCaiHanMuc.khoa_idempotency == khoa)


def _quyet_dinh(
    da_co: SoCaiHanMuc | None, da_dung: int, so_trang: int, tran: int
) -> KetQuaGiuCho | None:
    """Phần suy luận thuần, không đụng CSDL — nhờ vậy bản đồng bộ và bất đồng bộ dùng chung."""
    if da_co is not None:
        # Thử lại: trả về đúng kết quả cũ, KHÔNG trừ thêm.
        return KetQuaGiuCho(
            thanh_cong=da_co.trang_thai is not TrangThaiHanMuc.da_hoan,
            da_dung=da_dung,
            con_lai=max(0, tran - da_dung),
            da_co_san=True,
        )
    if so_trang <= 0:
        return KetQuaGiuCho(False, da_dung, max(0, tran - da_dung), ly_do="so_trang_khong_hop_le")
    if da_dung + so_trang > tran:
        # Từ chối NGUYÊN mẻ. Xử lý một phần âm thầm sẽ khiến người dùng nhận về nửa chapter mà
        # không hiểu vì sao — và không có cách nào nói cho họ biết phần nào thiếu.
        return KetQuaGiuCho(False, da_dung, max(0, tran - da_dung), ly_do="vuot_han_muc")
    return None  # đủ chỗ, nơi gọi tiến hành ghi


def _dong_moi(khoa: str, loai: LoaiChuThe, chu_the: str, ngay: date, so_trang: int) -> SoCaiHanMuc:
    return SoCaiHanMuc(
        khoa_idempotency=khoa,
        loai_chu_the=loai,
        chu_the=chu_the,
        ngay_han_muc=ngay,
        so_trang=so_trang,
        trang_thai=TrangThaiHanMuc.giu_cho,
    )


# --------------------------------------------------------------------------------------------
# Chuyển trạng thái MỘT dòng — phần luật dùng chung cho tra-theo-khoá và tra-theo-trang
# --------------------------------------------------------------------------------------------
def _tieu_dong(session, dong: SoCaiHanMuc, so_trang_thanh_cong: int | None) -> bool:
    """Chốt một dòng. Đã `da_tieu` ⇒ không làm gì, trả True. Đã `da_hoan` ⇒ trả False.

    Viết tách khỏi phần tra cứu để `tieu` (theo khoá) và `tieu_theo_trang` (theo trang) **không
    có hai bản luật lệch nhau** — kiểu lệch chỉ lộ ra khi một đường được sửa còn đường kia không.
    """
    if dong.trang_thai is TrangThaiHanMuc.da_tieu:
        return True
    if dong.trang_thai is TrangThaiHanMuc.da_hoan:
        return False  # đã hoàn thì không tiêu ngược lại được

    thanh_cong = dong.so_trang if so_trang_thanh_cong is None else max(0, so_trang_thanh_cong)
    thanh_cong = min(thanh_cong, dong.so_trang)
    con_lai = dong.so_trang - thanh_cong

    if thanh_cong == 0:
        dong.trang_thai = TrangThaiHanMuc.da_hoan
        dong.ly_do_hoan = "khong_trang_nao_thanh_cong"
        return True

    dong.so_trang = thanh_cong
    dong.trang_thai = TrangThaiHanMuc.da_tieu
    if con_lai:
        session.add(
            SoCaiHanMuc(
                khoa_idempotency=f"{dong.khoa_idempotency}#hoan-mot-phan",
                loai_chu_the=dong.loai_chu_the,
                chu_the=dong.chu_the,
                ngay_han_muc=dong.ngay_han_muc,
                so_trang=con_lai,
                trang_thai=TrangThaiHanMuc.da_hoan,
                ly_do_hoan="mot_phan_that_bai",
                trang_id=dong.trang_id,
            )
        )
    return True


def _hoan_dong(dong: SoCaiHanMuc, ly_do: str) -> bool:
    """Trả lại một dòng. Đã `da_hoan` ⇒ không làm gì, trả True. Đã `da_tieu` ⇒ trả False."""
    if dong.trang_thai is TrangThaiHanMuc.da_hoan:
        return True
    if dong.trang_thai is TrangThaiHanMuc.da_tieu:
        return False
    dong.trang_thai = TrangThaiHanMuc.da_hoan
    dong.ly_do_hoan = ly_do[:500]
    return True


# --------------------------------------------------------------------------------------------
# Bản ĐỒNG BỘ — dùng ở worker
# --------------------------------------------------------------------------------------------
def da_dung_dong_bo(session, loai: LoaiChuThe, chu_the: str, ngay: date) -> int:
    return int(session.execute(_cau_da_dung(loai, chu_the, ngay)).scalar_one())


def giu_cho_dong_bo(
    session, *, khoa: str, loai: LoaiChuThe, chu_the: str, ngay: date, so_trang: int, tran: int
) -> KetQuaGiuCho:
    session.execute(_khoa_chu_the(loai, chu_the))
    da_co = session.execute(_cau_tim_khoa(khoa)).scalar_one_or_none()
    da_dung = da_dung_dong_bo(session, loai, chu_the, ngay)
    xong = _quyet_dinh(da_co, da_dung, so_trang, tran)
    if xong is not None:
        return xong
    session.add(_dong_moi(khoa, loai, chu_the, ngay, so_trang))
    session.flush()
    moi = da_dung + so_trang
    return KetQuaGiuCho(True, moi, max(0, tran - moi))


def tieu(session, *, khoa: str, so_trang_thanh_cong: int | None = None) -> bool:
    """Chốt một khoản đã giữ chỗ.

    `so_trang_thanh_cong` nhỏ hơn số đã giữ ⇒ mẻ thành công một phần: hạ dòng này xuống đúng phần
    thành công và ghi thêm một dòng `da_hoan` cho phần còn lại.

    Gọi lại lần hai trên một dòng đã `da_tieu` là **không làm gì** và trả `True` — chạy lại task
    không được tiêu thêm lượt nào.
    """
    dong = session.execute(_cau_tim_khoa(khoa)).scalar_one_or_none()
    if dong is None:
        return False
    xong = _tieu_dong(session, dong, so_trang_thanh_cong)
    session.flush()
    return xong


def hoan(session, *, khoa: str, ly_do: str) -> bool:
    """Trả lại lượt vì **hệ thống** hỏng.

    Gọi lại lần hai là **không làm gì** và trả `True`. Lượt dọn job mồ côi có thể gọi hàm này
    nhiều lần cho cùng một mẻ; hoàn hai lần sẽ cho người dùng thêm lượt từ hư không.

    Dòng đã `da_tieu` thì **không** hoàn: việc đã chạy xong, lượt đã tiêu đúng.
    """
    dong = session.execute(_cau_tim_khoa(khoa)).scalar_one_or_none()
    if dong is None:
        return False
    xong = _hoan_dong(dong, ly_do)
    session.flush()
    return xong


# --------------------------------------------------------------------------------------------
# Bản BẤT ĐỒNG BỘ — dùng ở API
# --------------------------------------------------------------------------------------------
async def da_dung_bat_dong_bo(session, loai: LoaiChuThe, chu_the: str, ngay: date) -> int:
    return int((await session.execute(_cau_da_dung(loai, chu_the, ngay))).scalar_one())


async def giu_cho_bat_dong_bo(
    session, *, khoa: str, loai: LoaiChuThe, chu_the: str, ngay: date, so_trang: int, tran: int
) -> KetQuaGiuCho:
    await session.execute(_khoa_chu_the(loai, chu_the))
    da_co = (await session.execute(_cau_tim_khoa(khoa))).scalar_one_or_none()
    da_dung = await da_dung_bat_dong_bo(session, loai, chu_the, ngay)
    xong = _quyet_dinh(da_co, da_dung, so_trang, tran)
    if xong is not None:
        return xong
    session.add(_dong_moi(khoa, loai, chu_the, ngay, so_trang))
    await session.flush()
    moi = da_dung + so_trang
    return KetQuaGiuCho(True, moi, max(0, tran - moi))


# --------------------------------------------------------------------------------------------
# Theo TRANG — đơn vị worker thật sự làm việc
# --------------------------------------------------------------------------------------------
# Mỗi trang giữ chỗ MỘT dòng cho MỖI chốt (khách lạ có hai chốt: cookie và IP). Đơn vị "một dòng
# một trang" làm phần worker thành chuyện tầm thường: trang xong thì `tieu` các dòng của nó,
# trang hỏng hẳn thì `hoan` — không cần biết mẻ có bao nhiêu trang, cũng không cần ai điều phối
# "cả mẻ đã xong chưa". Mẻ thành công một phần tự đúng, vì từng trang tự quyết phần của mình.


def khoa_cua_trang(trang_id: uuid.UUID, loai: LoaiChuThe) -> str:
    """Khoá idempotency của một trang ở một chốt.

    Có `loai` trong khoá vì `khoa_idempotency` là DUY NHẤT toàn bảng: cùng một trang giữ chỗ ở
    hai chốt (cookie và IP) là hai dòng, nên phải là hai khoá khác nhau.
    """
    return f"trang:{trang_id}#{loai.value}"


def _cau_theo_trang(trang_id: uuid.UUID):
    return sa.select(SoCaiHanMuc).where(SoCaiHanMuc.trang_id == trang_id)


def _dong_trang(
    trang_id: uuid.UUID, loai: LoaiChuThe, chu_the: str, ngay: date
) -> SoCaiHanMuc:
    return SoCaiHanMuc(
        khoa_idempotency=khoa_cua_trang(trang_id, loai),
        loai_chu_the=loai,
        chu_the=chu_the,
        ngay_han_muc=ngay,
        so_trang=1,
        trang_thai=TrangThaiHanMuc.giu_cho,
        trang_id=trang_id,
    )


async def giu_cho_trang(
    session, *, trang_id: uuid.UUID, loai: LoaiChuThe, chu_the: str, ngay: date, tran: int
) -> KetQuaGiuCho:
    """Giữ chỗ MỘT trang ở MỘT chốt. Bản bất đồng bộ — giữ chỗ xảy ra ở API."""
    await session.execute(_khoa_chu_the(loai, chu_the))
    khoa = khoa_cua_trang(trang_id, loai)
    da_co = (await session.execute(_cau_tim_khoa(khoa))).scalar_one_or_none()
    da_dung = await da_dung_bat_dong_bo(session, loai, chu_the, ngay)
    xong = _quyet_dinh(da_co, da_dung, 1, tran)
    if xong is not None:
        return xong
    session.add(_dong_trang(trang_id, loai, chu_the, ngay))
    await session.flush()
    return KetQuaGiuCho(True, da_dung + 1, max(0, tran - da_dung - 1))


async def con_lai_bat_dong_bo(
    session, loai: LoaiChuThe, chu_the: str, ngay: date, tran: int
) -> int:
    """Số trang còn dùng được hôm nay. Chỉ ĐỌC — không giữ chỗ, không khoá.

    Dùng cho hai việc: hiện số lên giao diện, và chặn sớm một gói quá lớn **trước khi** ghi tệp
    nào xuống kho. Vì không khoá nên kết quả có thể cũ ngay khi trả về; chốt chặn thật vẫn là
    `giu_cho_trang`. Đừng dùng hàm này làm cổng duy nhất.
    """
    return max(0, tran - await da_dung_bat_dong_bo(session, loai, chu_the, ngay))


def tieu_theo_trang(session, trang_id: uuid.UUID, so_trang_thanh_cong: int | None = None) -> int:
    """Chốt mọi khoản đã giữ chỗ cho một trang. Trả về SỐ DÒNG đã chuyển sang `da_tieu`.

    Trả `0` nghĩa là không có dòng nào để tiêu — hoặc trang chưa từng giữ chỗ (đường tải lên cũ,
    trước khi có hạn mức), hoặc đã tiêu rồi. Nơi gọi **không** được coi `0` là lỗi.
    """
    dem = 0
    for dong in session.execute(_cau_theo_trang(trang_id)).scalars().all():
        truoc = dong.trang_thai
        if _tieu_dong(session, dong, so_trang_thanh_cong) and truoc is TrangThaiHanMuc.giu_cho:
            dem += 1
    session.flush()
    return dem


def hoan_theo_trang(session, trang_id: uuid.UUID, ly_do: str) -> int:
    """Trả lại mọi khoản đã giữ chỗ cho một trang. Trả về SỐ DÒNG vừa chuyển sang `da_hoan`.

    Dòng đã `da_tieu` **không** bị đụng tới: trang đã chạy xong thì lượt đã tiêu đúng, hoàn ngược
    là cho lượt từ hư không.
    """
    dem = 0
    for dong in session.execute(_cau_theo_trang(trang_id)).scalars().all():
        truoc = dong.trang_thai
        if _hoan_dong(dong, ly_do) and truoc is TrangThaiHanMuc.giu_cho:
            dem += 1
    session.flush()
    return dem
