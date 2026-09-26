"""E50 — vòng đời tệp: chapter tự xoá sau khi xong một khoảng.

## Đồng hồ bắt đầu khi CẢ CHAPTER xong, không phải khi tải lên

Một chapter 24 trang mất 30–40 phút để chạy. Đếm từ lúc tải lên thì **tệp hết hạn trước khi dịch
xong** — người dùng chờ nửa tiếng rồi nhận về con số 0.

Cũng không đếm theo từng trang: trang 1 sẽ hết hạn trong khi trang 24 còn đang chạy.

"Cả chapter xong" ở đây định nghĩa bằng **không còn job nào `queued`/`running`** trỏ vào trang
của nó. Cố ý KHÔNG định nghĩa bằng `page.status`: một trang kẹt ở `detection_failed` sẽ không bao
giờ đạt trạng thái cuối, và chapter đó sẽ giữ tệp mãi mãi.

## Ba tiền tố, không phải một

Hiện vật của một chapter nằm rải ở **ba** chỗ:

| Tiền tố | Theo | Chứa |
|---|---|---|
| `projects/{project_id}/` | chapter | ảnh gốc + ảnh đã xoá chữ |
| `exports/{project_id}` | chapter | tệp xuất |
| `previews/{page_id}/` | **TRANG** | ảnh xem thử đã căn chữ |

Chỉ xoá tiền tố đầu là bỏ sót `previews/` — đúng kiểu "đĩa đầy dần trong im lặng" mà §2.5 đặc tả
cấm. Và vì `previews/` đánh theo **trang**, phải lấy danh sách `page_id` **TRƯỚC** khi xoá
chapter, lúc đó mới còn dòng để mà đọc.

## Xoá tệp TRƯỚC, xoá dòng SAU

Xoá dòng trước rồi xoá tệp hỏng ⇒ mất luôn đường tìm lại tệp mồ côi (không còn `page_id` nào để
dựng tiền tố). Xoá tệp trước mà xoá dòng hỏng ⇒ dòng trỏ vào tệp không còn, xấu nhưng **thấy
được** và lượt dọn sau sẽ dọn nốt.

Chọn cái hỏng nhìn thấy được, không chọn cái hỏng im lặng.

## Hết hạn KHÔNG hoàn lượt

§2.8 đặc tả: hạn mức tiêu vào lúc **xử lý**, không phải lúc tải về. Tệp hết hạn vì người dùng
không tải kịp thì lượt vẫn đã dùng — khác hẳn §1.3(b), nơi **hệ thống** hỏng nên phải hoàn.

Điều này chạy được là nhờ `so_cai_han_muc.trang_id` **cố ý không có khoá ngoại**: chapter bị xoá
mà sổ cái vẫn còn nguyên. Có khoá ngoại `CASCADE` thì xoá chapter sẽ xoá luôn bằng chứng đã tiêu
lượt ⇒ người dùng được lượt từ hư không.

## Phép dọn phải NHẸ

Nó chạy chung tiến trình worker đang bó 4096 MB, mà worker **đã bị hệ điều hành giết 3 lần**.
Nên: chỉ xoá tệp và xoá dòng, làm từng chapter một, và có `gioi_han` để một lượt dọn không bao
giờ kéo dài vô hạn.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import Job, Page, Project
from app.models.enums import JobStatus
from app.services.export.paths import export_relative_dir
from app.services.typeset.paths import preview_relative_path

logger = logging.getLogger(__name__)

# Mốc hết hạn dùng **UTC**, không dùng múi giờ hạn mức. Cố ý khác `services/han_muc.py`: hạn mức
# gom theo NGÀY LỊCH nên phải biết "ngày nào ở Việt Nam", còn hết hạn tệp là **thời lượng trôi
# qua** (§2.2 đặc tả) nên múi giờ không tham gia vào phép tính. Trộn hai thứ đó lại là mời một
# lỗi lệch 7 tiếng vào chỗ không cần múi giờ.

#: Job ở hai trạng thái này nghĩa là chapter CÒN ĐANG CHẠY.
DANG_CHAY = (JobStatus.queued, JobStatus.running)


@dataclass
class KetQuaDonTep:
    """Kết quả một lượt dọn. Đếm riêng từng loại vì chúng có ý nghĩa vận hành khác nhau."""

    chapter_da_xoa: int = 0
    #: Đã quá hạn nhưng còn việc chạy dở ⇒ **bỏ qua**, không phải lỗi. Con số này lớn dai dẳng
    #: mới là dấu hiệu có job kẹt.
    chapter_bo_qua_dang_chay: int = 0
    tep_da_xoa: int = 0
    #: §2.6 đặc tả: dọn thất bại mà không ai biết thì đĩa đầy dần. `> 0` kéo dài là cần người xem.
    tep_that_bai: int = 0
    chi_tiet: list[str] = field(default_factory=list)


def _con_viec_dang_chay(session: Session, project_id: uuid.UUID) -> bool:
    return bool(session.execute(
        sa.select(sa.literal(1))
        .select_from(Job).join(Page, Page.id == Job.page_id)
        .where(Page.project_id == project_id, Job.status.in_(DANG_CHAY))
        .limit(1)
    ).scalar())


def danh_dau_het_han(
    session: Session, project_id: uuid.UUID | None, settings: Settings | None = None,
    bay_gio: datetime | None = None,
) -> bool:
    """Đặt (hoặc xoá) mốc hết hạn của một chapter. Trả `True` nếu vừa ĐẶT mốc.

    Gọi sau mỗi bước pipeline. Idempotent: chapter đã có mốc thì **không dời mốc** — dời mốc mỗi
    lần chạy lại một bước sẽ khiến chapter không bao giờ hết hạn.

    Còn việc chạy dở ⇒ **xoá** mốc. Trường hợp này có thật: người dùng bấm "chạy lại" một trang
    sau khi chapter đã xong; lúc đó chapter quay lại trạng thái đang chạy và không được biến mất
    giữa chừng.
    """
    if project_id is None:
        return False
    st = settings or get_settings()
    project = session.get(Project, project_id)
    if project is None:
        return False

    if _con_viec_dang_chay(session, project_id):
        if project.het_han_luc is not None:
            project.het_han_luc = None
            session.flush()
        return False

    co_trang = bool(session.execute(
        sa.select(sa.literal(1)).select_from(Page)
        .where(Page.project_id == project_id).limit(1)
    ).scalar())
    if not co_trang or project.het_han_luc is not None:
        return False

    moc = (bay_gio or datetime.now(timezone.utc)) + timedelta(minutes=st.giu_ket_qua_phut)
    project.het_han_luc = moc
    session.flush()
    logger.info("chapter %s sẽ tự xoá lúc %s", project_id, moc.isoformat())
    return True


def _tien_to_can_xoa(project_id: uuid.UUID, page_ids: list[uuid.UUID]) -> list[str]:
    """Mọi tiền tố hiện vật của một chapter. Xem bảng ba tiền tố ở docstring module."""
    tien_to = [f"projects/{project_id}", export_relative_dir(project_id)]
    # `previews/` đánh theo TRANG, nên phải liệt kê từng trang. Cắt phần `/typeset.png` để lấy
    # đúng thư mục — dùng lại quy ước đường dẫn thay vì gõ lại chuỗi ở đây.
    tien_to += [preview_relative_path(pid).rsplit("/", 1)[0] for pid in page_ids]
    return tien_to


def don_chapter_het_han(
    session: Session, *, ap_dung: bool = True, bay_gio: datetime | None = None,
    gioi_han: int = 50, settings: Settings | None = None,
) -> KetQuaDonTep:
    """Xoá các chapter đã quá hạn. `ap_dung=False` chỉ đếm — để soi trước khi động vào dữ liệu.

    `gioi_han` giữ cho một lượt dọn không kéo dài vô hạn trên tiến trình worker đã bó bộ nhớ.
    Còn sót thì lượt sau dọn tiếp; đây không phải việc gấp.
    """
    from app.services.storage import get_storage  # noqa: PLC0415 — tránh vòng import

    st = settings or get_settings()
    kq = KetQuaDonTep()
    moc = bay_gio or datetime.now(timezone.utc)

    dieu_kien = [Project.het_han_luc.isnot(None), Project.het_han_luc <= moc]
    if not st.tu_xoa_cho_tai_khoan:
        # Chỉ dọn chapter của KHÁCH LẠ. Chapter chưa có chủ (từ trước slice B) cũng không đụng:
        # chúng là dữ liệu cũ của người dùng thật, không phải rác của khách vãng lai.
        dieu_kien.append(Project.chu_khach.isnot(None))

    het_han = list(session.scalars(
        sa.select(Project).where(*dieu_kien).order_by(Project.het_han_luc).limit(gioi_han)
    ))
    if not het_han:
        return kq

    storage = get_storage()
    for project in het_han:
        if _con_viec_dang_chay(session, project.id):
            # §2.4 — TUYỆT ĐỐI không xoá thứ đang chạy dở. Xoá tệp giữa lúc worker đang đọc là
            # cách chắc chắn tạo ra lỗi không tái hiện được.
            kq.chapter_bo_qua_dang_chay += 1
            kq.chi_tiet.append(f"chapter {project.id}: quá hạn nhưng CÒN VIỆC CHẠY — bỏ qua")
            continue

        page_ids = list(session.scalars(
            sa.select(Page.id).where(Page.project_id == project.id)
        ))
        tien_to = _tien_to_can_xoa(project.id, page_ids)
        kq.chi_tiet.append(
            f"chapter {project.id}: {len(page_ids)} trang, {len(tien_to)} tiền tố"
        )
        if not ap_dung:
            kq.chapter_da_xoa += 1
            continue

        for tt in tien_to:
            try:
                kq.tep_da_xoa += len(storage.delete_prefix(tt))
            except Exception:  # noqa: BLE001 — §2.6: ghi lại, không nuốt
                kq.tep_that_bai += 1
                logger.exception("dọn tệp hỏng ở tiền tố %s (chapter %s)", tt, project.id)

        # Xoá dòng SAU khi xoá tệp — xem docstring module. Cascade của `Project` kéo theo trang,
        # vùng, kết quả OCR/dịch/căn chữ. Sổ cái hạn mức KHÔNG bị kéo theo (không có khoá ngoại),
        # đúng §2.8: hết hạn thì không hoàn lượt.
        session.delete(project)
        kq.chapter_da_xoa += 1

    if ap_dung and (kq.chapter_da_xoa or kq.tep_that_bai):
        session.commit()

    if kq.chapter_da_xoa or kq.tep_that_bai or kq.chapter_bo_qua_dang_chay:
        logger.warning(
            "dọn tệp hết hạn (%s): %d chapter đã xoá, %d tệp đã xoá, %d tiền tố lỗi, "
            "%d chapter bỏ qua vì còn việc chạy",
            "ĐÃ SỬA" if ap_dung else "chỉ đếm",
            kq.chapter_da_xoa, kq.tep_da_xoa, kq.tep_that_bai, kq.chapter_bo_qua_dang_chay,
        )
        for d in kq.chi_tiet:
            logger.warning("  %s", d)
    return kq


def danh_dau_het_han_cho_trang(page_id: uuid.UUID | None) -> bool:
    """Bản tiện dụng cho worker: từ `page_id` lần ra chapter rồi đặt mốc. Tự mở phiên.

    Hỏng thì ghi ERROR và trả `False`, **không** kéo theo việc của trang: trang đã chạy xong mà
    ghi mốc hỏng thì trang vẫn phải xong. Hậu quả của việc nuốt lỗi ở đây là chapter không bao
    giờ hết hạn (đĩa đầy dần) — nên nó phải ồn ào.
    """
    from app.core.db_sync import sync_session  # noqa: PLC0415 — tránh vòng import

    if page_id is None:
        return False
    try:
        with sync_session() as session:
            page = session.get(Page, page_id)
            if page is None:
                return False
            xong = danh_dau_het_han(session, page.project_id)
            if xong:
                session.commit()
            return xong
    except Exception:  # noqa: BLE001 — xem docstring
        logger.exception(
            "KHÔNG đặt được mốc tự xoá cho chapter của trang %s. Chapter này sẽ giữ tệp vô "
            "thời hạn cho tới khi có người xử lý.", page_id
        )
        return False
