"""Điều phối mẻ chạy cả project (M9).

Nguyên tắc: **không sao chép logic của M2–M8**. Bộ này chỉ xếp việc, theo dõi và gộp trạng thái;
mọi bước nặng vẫn do đúng các task cũ làm.

Cũng **không** dùng một task Celery ngồi chờ các task con — làm vậy là giam mất một worker và
dễ khoá chết cả hàng đợi. Thay vào đó: xếp việc rồi thoát; khi một trang tới trạng thái cuối,
task của nó gọi ngược lại `on_page_terminal` để đẩy trang kế tiếp.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.db_sync import sync_session
from app.models import BatchItem, BatchRun, Job, Page, Project
from app.models.enums import (
    BatchItemStatus,
    BatchPipeline,
    BatchStatus,
    JobStatus,
    PageStatus,
)
from app.services.batch.errors import (
    MA_TAM_THOI,
    ErrorClass,
    RetryPolicy,
    TransientErrorClassifier,
)
from app.services.batch.dispatch import viec_dang_song
from app.services.batch.rollup import TRANG_DA_XONG, buoc_cho_trang, gop_trang_thai_me

logger = logging.getLogger(__name__)


class BatchInvalid(ValueError):
    """Yêu cầu tạo/tiếp tục mẻ không hợp lệ — báo ngay, không xếp việc rồi mới hỏng."""


#: Trạng thái cuối của một mục: từ đây không tự chạy tiếp nữa.
KET_THUC = (
    BatchItemStatus.completed,
    BatchItemStatus.failed,
    BatchItemStatus.blocked_quota,
    BatchItemStatus.skipped,
)


class BatchOrchestrator:
    def __init__(
        self,
        max_concurrent_pages: int = 1,
        retry_policy: RetryPolicy | None = None,
        classifier: TransientErrorClassifier | None = None,
        dispatcher=None,
        stale_item_seconds: float = 1800.0,
    ) -> None:
        self.max_concurrent_pages = max(1, max_concurrent_pages)
        #: Mục `running` quá lâu coi như mồ côi (worker đã chết) và được thu hồi.
        self.stale_item_seconds = stale_item_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.classifier = classifier or TransientErrorClassifier()
        #: Hàm đẩy việc thật; tách ra để test không cần Celery/Redis.
        self._dispatcher = dispatcher

    # ---------------- tạo mẻ ----------------
    def create_full_pipeline_run(
        self, project_id: uuid.UUID, translation_engine: str | None,
        pipeline: BatchPipeline = BatchPipeline.full_pipeline,
    ) -> uuid.UUID:
        """Chụp danh sách trang theo `Page.order` NGAY LÚC TẠO rồi dựng mẻ.

        Chụp trước là điều kiện để trang tải lên sau đó không lẫn vào mẻ đang chạy — thứ khiến
        tổng số trang nhảy lung tung giữa chừng và người vận hành không biết mẻ đã xong chưa.
        """
        with sync_session() as session:
            if session.get(Project, project_id) is None:
                raise BatchInvalid(f"project_not_found: {project_id}")

            trang = list(
                session.execute(
                    select(Page).where(Page.project_id == project_id).order_by(Page.order)
                ).scalars()
            )
            if not trang:
                raise BatchInvalid("no_page: project chưa có trang nào, không tạo mẻ rỗng")

            if pipeline is BatchPipeline.retry_failed:
                trang = [p for p in trang if p.status not in TRANG_DA_XONG]
                if not trang:
                    raise BatchInvalid("no_page_to_retry: mọi trang đã xong, không có gì để chạy lại")

            me = BatchRun(
                project_id=project_id,
                requested_pipeline=pipeline,
                translation_engine=translation_engine,
                status=BatchStatus.queued,
                total_pages=len(trang),
            )
            session.add(me)
            session.flush()
            for p in trang:
                session.add(
                    BatchItem(batch_run_id=me.id, page_id=p.id, page_order=p.order,
                              status=BatchItemStatus.pending)
                )
            session.commit()
            me_id = me.id

        logger.info("tạo mẻ %s: %d trang, engine=%s", me_id, len(trang), translation_engine)
        self.dispatch_next(me_id)
        return me_id

    # ---------------- đẩy việc ----------------
    def dispatch_next(self, batch_run_id: uuid.UUID, _con_lai: int = 50) -> int:
        """Đẩy thêm việc cho tới khi chạm giới hạn số trang chạy song song. Trả số việc vừa đẩy.

        `_con_lai` chặn vòng lặp vô hạn khi mọi mục đều bị bỏ qua.
        """
        can_day: list[tuple[uuid.UUID, uuid.UUID, str, int]] = []
        bo_qua = 0
        with sync_session() as session:
            me = session.get(BatchRun, batch_run_id)
            if me is None or me.status is BatchStatus.cancelled:
                return 0

            dang_chay = session.execute(
                select(func.count()).select_from(BatchItem).where(
                    BatchItem.batch_run_id == batch_run_id,
                    BatchItem.status == BatchItemStatus.running,
                )
            ).scalar() or 0
            con_cho = self.max_concurrent_pages - dang_chay
            if con_cho <= 0:
                return 0

            # Lấy RỘNG hơn số chỗ trống rồi mới lọc: một mục không đẩy được (trang đang chạy
            # dở) mà chiếm mất chỗ thì các trang sau không bao giờ tới lượt — mẻ treo.
            cho = list(
                session.execute(
                    select(BatchItem).where(
                        BatchItem.batch_run_id == batch_run_id,
                        BatchItem.status == BatchItemStatus.pending,
                    ).order_by(BatchItem.page_order)
                ).scalars()
            )
            for muc in cho:
                if len(can_day) >= con_cho:
                    break
                page = session.get(Page, muc.page_id)
                if page is None:
                    muc.status = BatchItemStatus.failed
                    muc.error_code = "permanent_input"
                    muc.error_message = "page_not_found"
                    bo_qua += 1
                    continue
                buoc = buoc_cho_trang(page.status)
                if buoc is None:
                    if page.status in TRANG_DA_XONG:
                        # Đã xong từ trước: bỏ qua là ĐÚNG, và tính là xong.
                        muc.status = BatchItemStatus.skipped
                        muc.error_code = "da_xong"
                        muc.finished_at = datetime.now(timezone.utc)
                        bo_qua += 1
                    else:
                        # Trang đang chạy dở (`detecting`): KHÔNG đụng vào, nhưng cũng KHÔNG
                        # được coi là xong. Giữ `pending` để mẻ nói thật rằng còn việc.
                        # (Lỗi thật: từng đánh `skipped` ở đây, khiến mẻ báo "3/3 hoàn thành"
                        #  trong khi một trang vẫn kẹt ở `detecting` — xem TEST_LOG § M9.)
                        muc.error_code = "dang_chay"
                    continue
                muc.status = BatchItemStatus.running
                muc.started_at = muc.started_at or datetime.now(timezone.utc)
                # CHỈ chờ khi lần đẩy này là hệ quả của một lỗi tạm thời vừa xảy ra.
                # Lỗi thật đo ở Run B: dùng thẳng `retry_count` khiến MỌI bước sau đó của trang
                # (canh chữ, xuất…) cũng bị phạt chờ, dù bước trước đã chạy tốt.
                la_thu_lai = (muc.error_code or "") in MA_TAM_THOI
                can_day.append((muc.id, muc.page_id, buoc, muc.retry_count if la_thu_lai else 0))

            if me.status is BatchStatus.queued and (can_day or cho):
                me.status = BatchStatus.running
                me.started_at = me.started_at or datetime.now(timezone.utc)
            session.commit()

        for muc_id, page_id, buoc, so_lan_thu in can_day:
            self._day_viec(batch_run_id, muc_id, page_id, buoc, so_lan_thu)

        if can_day:
            return len(can_day)

        self._gop_lai(batch_run_id)
        # Vòng vừa rồi chỉ toàn mục bị bỏ qua nên KHÔNG đẩy được việc nào. Không thử lại ở đây
        # thì mẻ treo vĩnh viễn với các mục còn `pending` mà không ai đánh thức.
        # (Lỗi thật: trang đầu đang chạy dở do pipeline tự chảy sau upload -> bị bỏ qua ->
        #  mẻ đứng im, xem TEST_LOG § M9.)
        if bo_qua and _con_lai > 0:
            return self.dispatch_next(batch_run_id, _con_lai - 1)
        return 0

    def _day_viec(self, batch_run_id: uuid.UUID, muc_id: uuid.UUID, page_id: uuid.UUID, buoc: str,
                  so_lan_thu: int = 0) -> None:
        if self._dispatcher is None:
            from app.services.batch.dispatch import day_viec_buoc

            self._dispatcher = day_viec_buoc
        # Lần thử lại phải CHỜ trước khi gọi lại. Gọi lại ngay sau khi nhà cung cấp vừa báo
        # "quá nhịp" là cách chắc chắn nhất để bị chặn tiếp — và nếu mọi trang cùng gọi lại
        # đúng một thời điểm thì lại chặn nhau, nên thời gian chờ có nhiễu.
        cho_giay = (
            self.retry_policy.next_delay_seconds(so_lan_thu - 1, khoa_nhieu=str(muc_id))
            if so_lan_thu > 0
            else 0.0
        )
        try:
            job_id = self._dispatcher(page_id, buoc, batch_run_id, cho_giay)
        except Exception as exc:  # noqa: BLE001
            logger.exception("không đẩy được việc %s cho trang %s", buoc, page_id)
            self.on_page_terminal(page_id, None, "failed", str(exc), batch_run_id)
            return
        with sync_session() as session:
            muc = session.get(BatchItem, muc_id)
            if muc is not None:
                muc.current_job_id = job_id
                session.commit()

    # ---------------- nhận kết quả ----------------
    def on_page_terminal(
        self, page_id: uuid.UUID, job_id: uuid.UUID | None, outcome: str,
        mo_ta_loi: str | None = None, batch_run_id: uuid.UUID | None = None,
    ) -> None:
        """Task pipeline gọi vào đây khi một trang tới trạng thái cuối.

        `outcome`: `completed` | `failed`. Không suy ra `completed` chỉ vì Celery nhận task —
        phải là trạng thái thật của trang trong DB.
        """
        with sync_session() as session:
            q = select(BatchItem).join(BatchRun).where(
                BatchItem.page_id == page_id,
                BatchItem.status == BatchItemStatus.running,
                BatchRun.status.notin_([BatchStatus.cancelled]),
            )
            if batch_run_id is not None:
                q = q.where(BatchItem.batch_run_id == batch_run_id)
            muc = session.execute(q.order_by(BatchItem.created_at.desc())).scalars().first()
            if muc is None:
                return  # trang này không thuộc mẻ nào đang chạy — chạy lẻ, không phải lỗi
            me_id = muc.batch_run_id

            if outcome == "completed":
                page = session.get(Page, page_id)
                if page is not None and page.status not in TRANG_DA_XONG:
                    # Bước vừa xong nhưng trang chưa đi hết pipeline -> còn việc, để `pending`
                    # cho vòng đẩy kế tiếp chạy bước sau.
                    muc.status = BatchItemStatus.pending
                    muc.current_job_id = job_id
                    # Bước vừa rồi CHẠY ĐƯỢC ⇒ xoá dấu lỗi cũ, để bước kế tiếp không bị coi là
                    # "đẩy lại sau lỗi" và phải chờ oan.
                    muc.error_code = None
                    muc.error_message = None
                    session.commit()
                    self.dispatch_next(me_id)
                    return
                muc.status = BatchItemStatus.completed
                muc.error_code = None
                muc.error_message = None
                muc.finished_at = datetime.now(timezone.utc)
            else:
                loai = self.classifier.classify(mo_ta=mo_ta_loi or "")
                if self.retry_policy.should_retry(loai, muc.retry_count):
                    muc.retry_count += 1
                    muc.status = BatchItemStatus.pending
                    muc.error_code = loai.value
                    muc.error_message = _lam_sach(mo_ta_loi)
                    logger.info("trang %s lỗi tạm thời (%s) -> thử lại lần %d",
                                page_id, loai.value, muc.retry_count)
                elif loai in (ErrorClass.QUOTA_EXHAUSTED, ErrorClass.TRANSIENT_RATE_LIMIT):
                    # Hết quota, hoặc bị chặn vì quá nhịp mà đã hết lượt thử lại: cả hai đều là
                    # "chưa chạy được vì HẠN MỨC", không phải "hỏng". Gọi nó là `failed` sẽ che
                    # mất lý do thật và khiến người vận hành đi tìm lỗi ở chỗ không có lỗi.
                    # Giữ nguyên `error_code` để phân biệt hết-quota với quá-nhịp.
                    muc.status = BatchItemStatus.blocked_quota
                    muc.error_code = loai.value
                    muc.error_message = _lam_sach(mo_ta_loi)
                    muc.finished_at = datetime.now(timezone.utc)
                else:
                    muc.status = BatchItemStatus.failed
                    muc.error_code = loai.value
                    muc.error_message = _lam_sach(mo_ta_loi)
                    muc.finished_at = datetime.now(timezone.utc)
            muc.current_job_id = job_id
            session.commit()

        self._gop_lai(me_id)
        self.dispatch_next(me_id)

    # ---------------- gộp trạng thái ----------------
    def _gop_lai(self, batch_run_id: uuid.UUID) -> BatchStatus:
        """Đọc lại TOÀN BỘ mục rồi suy ra trạng thái mẻ. Bộ đếm chỉ là cache, luôn tính lại."""
        with sync_session() as session:
            me = session.get(BatchRun, batch_run_id)
            if me is None:
                return BatchStatus.failed
            items = list(
                session.execute(
                    select(BatchItem.status).where(BatchItem.batch_run_id == batch_run_id)
                ).scalars()
            )
            tt = gop_trang_thai_me(items, da_huy=me.status is BatchStatus.cancelled)
            me.status = tt
            me.completed_pages = sum(
                1 for s in items if s in (BatchItemStatus.completed, BatchItemStatus.skipped)
            )
            me.failed_pages = sum(1 for s in items if s is BatchItemStatus.failed)
            me.blocked_pages = sum(1 for s in items if s is BatchItemStatus.blocked_quota)
            if tt in (BatchStatus.completed, BatchStatus.partial_failed,
                      BatchStatus.blocked_quota, BatchStatus.failed, BatchStatus.cancelled):
                me.finished_at = me.finished_at or datetime.now(timezone.utc)
            session.commit()
            return tt

    # ---------------- thu hồi mục mồ côi ----------------
    def thu_hoi_muc_mo_coi(self, batch_run_id: uuid.UUID, hoi_broker: bool = False) -> int:
        """Đưa các mục `running` quá lâu về `pending` để chạy lại.

        Lỗi thật đã gặp: worker bị khởi động lại (hoặc bị hệ điều hành giết vì hết bộ nhớ) thì
        task Celery biến mất, nhưng `BatchItem` vẫn nằm ở `running` **vĩnh viễn** — mẻ đứng im
        mà nhìn vào không biết vì sao, và `resume` cũng không cứu được vì nó chỉ nhận
        `failed`/`blocked_quota`. Xem REPORT_M8 §7 cho cùng triệu chứng ở mức Job.
        """
        moc = datetime.now(timezone.utc)
        dem = 0
        # Hỏi broker xem việc nào còn sống THẬT. Biết chắc thì thu hồi ngay, không phải chờ hết
        # đồng hồ — đây là điều người vận hành mong đợi khi bấm "chạy lại" ngay sau sự cố.
        con_song = viec_dang_song() if hoi_broker else None
        #: Không hỏi được (không worker nào trả lời) thì vẫn chờ một khoảng ngắn cho chắc.
        an_toan_giay = 60.0
        with sync_session() as session:
            for m in session.execute(
                select(BatchItem).where(
                    BatchItem.batch_run_id == batch_run_id,
                    BatchItem.status == BatchItemStatus.running,
                )
            ).scalars():
                bat_dau = m.started_at or m.created_at
                if bat_dau is None:
                    continue
                if bat_dau.tzinfo is None:
                    bat_dau = bat_dau.replace(tzinfo=timezone.utc)
                tuoi = (moc - bat_dau).total_seconds()
                if con_song is not None:
                    # Broker trả lời được: việc không nằm trong danh sách đang chạy nghĩa là nó
                    # đã chết. Không cần đợi đồng hồ.
                    if str(m.current_job_id) in con_song:
                        continue
                elif hoi_broker:
                    if tuoi < an_toan_giay:
                        continue
                elif tuoi < self.stale_item_seconds:
                    continue
                m.status = BatchItemStatus.pending
                m.error_code = "stale_reclaimed"
                m.error_message = (
                    "Việc đang chạy bị mất (worker khởi động lại hoặc bị giết) — xếp lại."
                )
                # Job cũng phải nói thật: nó KHÔNG còn chạy nữa.
                job_cu = session.get(Job, m.current_job_id) if m.current_job_id else None
                if job_cu is not None and job_cu.status is JobStatus.running:
                    job_cu.status = JobStatus.failed
                    job_cu.error_log = "worker mất giữa chừng — việc được mẻ xếp lại"
                dem += 1

            # Trang kẹt ở trạng thái tạm (`detecting`) quá lâu: việc chạy nó đã mất, mà máy
            # trạng thái của M1 không cho đi tiếp từ đó. Đánh hỏng CÓ LÝ DO còn hơn để mẻ treo
            # mãi — người vận hành phải nhìn thấy để xử lý.
            for m in session.execute(
                select(BatchItem).where(
                    BatchItem.batch_run_id == batch_run_id,
                    BatchItem.status == BatchItemStatus.pending,
                    BatchItem.error_code == "dang_chay",
                )
            ).scalars():
                moc_bd = m.started_at or m.created_at
                if moc_bd is None:
                    continue
                if moc_bd.tzinfo is None:
                    moc_bd = moc_bd.replace(tzinfo=timezone.utc)
                if (moc - moc_bd).total_seconds() < self.stale_item_seconds:
                    continue
                page = session.get(Page, m.page_id)
                m.status = BatchItemStatus.failed
                m.error_code = "stale_page"
                m.error_message = (
                    f"Trang kẹt ở '{page.status.value if page else '?'}' quá lâu — "
                    "việc chạy nó đã mất. Chạy lại bước đó cho trang này."
                )
                m.finished_at = moc
                dem += 1
            if dem:
                session.commit()
        if dem:
            logger.warning("mẻ %s: thu hồi %d mục mồ côi", batch_run_id, dem)
        return dem

    # ---------------- chạy lại / huỷ ----------------
    def resume_failed(self, batch_run_id: uuid.UUID, item_ids: list[uuid.UUID] | None = None) -> int:
        """Chỉ xếp lại các mục `failed`/`blocked_quota`. KHÔNG đụng mục đã `completed`."""
        with sync_session() as session:
            if session.get(BatchRun, batch_run_id) is None:
                raise BatchInvalid(f"batch_not_found: {batch_run_id}")

        # Thu hồi trước: mục kẹt `running` vì worker chết cũng phải chạy lại được, nếu không
        # người dùng bấm "chạy lại" mà không có gì xảy ra.
        da_thu_hoi = 0 if item_ids else self.thu_hoi_muc_mo_coi(batch_run_id, hoi_broker=True)

        with sync_session() as session:
            me = session.get(BatchRun, batch_run_id)
            q = select(BatchItem).where(BatchItem.batch_run_id == batch_run_id)
            if item_ids:
                q = q.where(BatchItem.id.in_(item_ids))
            muc_list = list(session.execute(q).scalars())

            if item_ids:
                thay = {m.id for m in muc_list}
                thieu = set(item_ids) - thay
                if thieu:
                    raise BatchInvalid(f"item_not_in_batch: {sorted(str(i) for i in thieu)}")
                sai = [m for m in muc_list
                       if m.status not in (BatchItemStatus.failed, BatchItemStatus.blocked_quota)]
                if sai:
                    # Không âm thầm bỏ qua: người dùng chọn nhầm thì phải biết.
                    raise BatchInvalid(
                        "item_not_resumable: chỉ chạy lại được mục failed/blocked_quota, "
                        f"nhận được {[m.status.value for m in sai]}"
                    )

            dem = 0
            for m in muc_list:
                if m.status in (BatchItemStatus.failed, BatchItemStatus.blocked_quota):
                    m.status = BatchItemStatus.pending
                    m.retry_count = 0
                    m.error_code = None
                    m.error_message = None
                    m.finished_at = None
                    dem += 1
            if dem or da_thu_hoi:
                me.status = BatchStatus.running
                me.finished_at = None
            session.commit()

        tong = dem + da_thu_hoi
        if tong:
            self.dispatch_next(batch_run_id)
        return tong

    def cancel(self, batch_run_id: uuid.UUID) -> int:
        """Dừng đẩy việc mới. Việc ĐANG chạy được để chạy nốt — cắt ngang dễ để lại dữ liệu dở."""
        with sync_session() as session:
            me = session.get(BatchRun, batch_run_id)
            if me is None:
                raise BatchInvalid(f"batch_not_found: {batch_run_id}")
            dem = 0
            for m in session.execute(
                select(BatchItem).where(
                    BatchItem.batch_run_id == batch_run_id,
                    BatchItem.status == BatchItemStatus.pending,
                )
            ).scalars():
                m.status = BatchItemStatus.skipped
                m.error_code = "cancelled"
                m.finished_at = datetime.now(timezone.utc)
                dem += 1
            me.status = BatchStatus.cancelled
            me.finished_at = datetime.now(timezone.utc)
            session.commit()
            return dem


def _lam_sach(mo_ta: str | None) -> str | None:
    """Cắt ngắn và loại thứ trông giống khoá bí mật trước khi lưu vào DB.

    Thông điệp lỗi đi thẳng ra API và giao diện, nên không được mang theo API key.
    """
    if not mo_ta:
        return None
    import re

    sach = re.sub(r"(AIza[\w-]{10,}|vays_pat_[\w-]{10,}|sk-[\w]{10,}|Bearer\s+\S+)", "***", mo_ta)
    return sach[:2000]
