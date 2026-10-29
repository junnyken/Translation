"""Đơn nạp lượt trên bảng `don_nap_luot` — thay tệp `quan_tri/don_nap_luot.json`.

Mọi chuyển trạng thái đi qua `chuyen_trang_thai`: một câu `UPDATE ... WHERE trang_thai IN (...)
RETURNING`, nên hai lượt duyệt song song chỉ một lượt thắng và chỉ lượt đó được cộng/trừ lượt.
Cộng/trừ lượt cũng là một `UPDATE` cộng dồn trên CSDL, không đọc-sửa-ghi trong Python.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DonNapLuot, NguoiDung
from app.schemas.common import DonNapLuotRead
from app.services.han_muc import bay_gio

logger = logging.getLogger(__name__)

_TEP_JSON_CU = "quan_tri/don_nap_luot.json"
_da_nhap_json_cu = False


def sinh_ma_don() -> str:
    return f"ACB-{uuid.uuid4().hex[:8].upper()}"


def sang_read(don: DonNapLuot) -> DonNapLuotRead:
    tao = don.created_at.isoformat() if don.created_at else ""
    return DonNapLuotRead(
        ma_don=don.ma_don,
        email=don.email,
        ten_hien=don.ten_hien,
        ma_goi=don.ma_goi,
        ten_goi=don.ten_goi,
        so_tien_vnd=int(don.so_tien_vnd),
        so_trang_cong=don.so_trang_cong,
        noi_dung_ck=don.noi_dung_chuyen_khoan,
        noi_dung_chuyen_khoan=don.noi_dung_chuyen_khoan,
        trang_thai=don.trang_thai,
        tao_luc=tao,
        created_at=tao,
        duyet_luc=don.duyet_luc.isoformat() if don.duyet_luc else None,
    )


async def nhap_json_cu_neu_co(session: AsyncSession) -> int:
    """Chép các đơn trong tệp JSON cũ vào bảng (một lần mỗi tiến trình). Trùng `ma_don` thì bỏ qua.

    Không xoá tệp cũ — giữ làm bản đối chiếu. Lỗi đọc tệp không chặn luồng chính.
    """
    global _da_nhap_json_cu
    if _da_nhap_json_cu:
        return 0
    from app.services.storage import get_storage

    try:
        storage = get_storage()
        if not storage.exists(_TEP_JSON_CU):
            _da_nhap_json_cu = True
            return 0
        ds = json.loads(storage.read(_TEP_JSON_CU).decode("utf-8"))
    except Exception:  # noqa: BLE001
        logger.warning("Không đọc được %s — bỏ qua bước chép đơn cũ", _TEP_JSON_CU, exc_info=True)
        _da_nhap_json_cu = True
        return 0

    dong = []
    for d in ds if isinstance(ds, list) else []:
        if not isinstance(d, dict) or not d.get("ma_don") or not d.get("email"):
            continue
        try:
            tao = datetime.fromisoformat(str(d.get("created_at") or d.get("tao_luc")))
        except ValueError:
            tao = bay_gio()
        dong.append({
            "id": uuid.uuid4(),
            "ma_don": str(d["ma_don"])[:32],
            "email": str(d["email"]).strip().lower()[:320],
            "ten_hien": str(d.get("ten_hien") or "")[:120],
            "ma_goi": str(d.get("ma_goi") or "")[:60],
            "ten_goi": str(d.get("ten_goi") or "")[:160],
            "so_tien_vnd": int(d.get("so_tien_vnd") or 0),
            "so_trang_cong": int(d.get("so_trang_cong") or 0),
            "noi_dung_chuyen_khoan": str(
                d.get("noi_dung_chuyen_khoan") or d.get("noi_dung_ck") or ""
            ),
            "trang_thai": str(d.get("trang_thai") or "cho_duyet")[:32],
            "created_at": tao,
        })
    if dong:
        await session.execute(
            pg_insert(DonNapLuot).values(dong).on_conflict_do_nothing(index_elements=["ma_don"])
        )
        await session.commit()
        logger.info("Đã chép %d đơn nạp từ %s vào bảng don_nap_luot", len(dong), _TEP_JSON_CU)
    _da_nhap_json_cu = True
    return len(dong)


async def ds_don_moi_nhat(session: AsyncSession, gioi_han: int = 50) -> list[DonNapLuot]:
    await nhap_json_cu_neu_co(session)
    return list(
        (await session.execute(
            select(DonNapLuot).order_by(DonNapLuot.created_at.desc()).limit(gioi_han)
        )).scalars()
    )


async def tim_don(session: AsyncSession, ma_don: str) -> DonNapLuot | None:
    await nhap_json_cu_neu_co(session)
    return (
        await session.execute(select(DonNapLuot).where(DonNapLuot.ma_don == ma_don))
    ).scalars().first()


async def tim_don_cho_duyet(
    session: AsyncSession, email: str, ma_goi: str | None = None
) -> DonNapLuot | None:
    await nhap_json_cu_neu_co(session)
    cau = select(DonNapLuot).where(
        func.lower(DonNapLuot.email) == email.lower(), DonNapLuot.trang_thai == "cho_duyet"
    )
    if ma_goi is not None:
        cau = cau.where(DonNapLuot.ma_goi == ma_goi)
    return (await session.execute(cau.order_by(DonNapLuot.created_at.desc()))).scalars().first()


async def chuyen_trang_thai(
    session: AsyncSession,
    don_id: uuid.UUID,
    *,
    tu: tuple[str, ...],
    sang: str,
    ma_giao_dich: str | None = None,
    **cot_khac: object,
) -> bool:
    """Đổi trạng thái NGUYÊN TỬ. Trả True nếu lượt này là lượt đổi được (chưa ai đổi trước)."""
    gia_tri: dict = {"trang_thai": sang, "duyet_luc": bay_gio(), **cot_khac}
    if ma_giao_dich is not None:
        gia_tri["ma_giao_dich_ngan_hang"] = ma_giao_dich
    kq = await session.execute(
        update(DonNapLuot)
        .where(DonNapLuot.id == don_id, DonNapLuot.trang_thai.in_(tu))
        .values(**gia_tri)
        .returning(DonNapLuot.id)
    )
    return kq.first() is not None


async def cong_luot(session: AsyncSession, nguoi_id: uuid.UUID, so_trang: int) -> None:
    """Cộng (hoặc trừ khi âm) lượt mua thêm, không xuống dưới 0. Một câu UPDATE trên CSDL."""
    await session.execute(
        update(NguoiDung)
        .where(NguoiDung.id == nguoi_id)
        .values(so_luot_mua_them=func.greatest(0, NguoiDung.so_luot_mua_them + so_trang))
    )
