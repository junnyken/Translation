"""PostgreSQL transaction boundary for keyed private uploads.

Caller must keep this transaction open until page + quota + Job are committed.
No TTL or cleanup: deleted pages keep a tombstone, keys cannot resurrect work.
"""
from fastapi import HTTPException
from sqlalchemy import select, text

from app.models import UploadRequest
from app.services.upload_identity import upload_lock_id


async def lock_and_find(session, owner_id, request_key, request_hash):
    await session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"),
                          {"lock_id": upload_lock_id(owner_id, request_key)})
    row = await session.get(UploadRequest, (owner_id, request_key))
    if row is not None:
        if row.request_hash != request_hash:
            raise HTTPException(409, "Mã yêu cầu đã gắn với ảnh hoặc cấu hình khác; không tạo việc mới.")
        if row.page_id is None:
            raise HTTPException(410, "Trang của yêu cầu này đã bị xoá; không tự tạo lại hoặc trừ thêm lượt.")
    return row


async def find_owned(session, owner_id, request_key):
    row = (await session.execute(select(UploadRequest).where(
        UploadRequest.owner_id == owner_id, UploadRequest.request_key == request_key,
    ))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Chưa thấy yêu cầu của tài khoản này.")
    if row.page_id is None:
        raise HTTPException(410, "Trang của yêu cầu này đã bị xoá; không tự tạo lại.")
    return row
