"""Best-effort rollback cleanup for private keyed uploads.

Storage is not part of the SQL transaction. After an uncertain commit, inspect
its key under the same advisory lock on a fresh primary connection BEFORE deleting.
An unreachable DB or failed cleanup is logged for reconciliation, never guessed.
A process kill still requires a future orphan sweeper.
"""
import logging

from starlette.concurrency import run_in_threadpool

log = logging.getLogger(__name__)


class UploadArtifactGuard:
    def __init__(self, session, owner_id, request_key):
        self.session = session
        self.owner_id = owner_id
        self.request_key = request_key
        self.project_id = None
        self.page_id = None
        self.storage = None
        self.commit_attempted = False
        self.committed = False

    async def __aenter__(self):
        return self

    async def _accepted(self):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from app.models import UploadRequest
        from app.services.upload_identity import upload_lock_id

        maker = async_sessionmaker(self.session.bind, expire_on_commit=False)
        async with maker() as probe:
            # Wait until the original transaction has definitely committed/rolled back.
            await probe.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"),
                                {"lock_id": upload_lock_id(self.owner_id, self.request_key)})
            row = await probe.get(UploadRequest, (self.owner_id, self.request_key))
            return row is not None and (row.page_id is None or row.page_id == self.page_id)

    async def __aexit__(self, exc_type, exc, traceback):
        if exc_type is None or self.request_key is None or self.committed or self.storage is None:
            return False
        try:
            await self.session.rollback()
            if self.commit_attempted and await self._accepted():
                return False
            await run_in_threadpool(self.storage.delete_prefix, f"projects/{self.project_id}/")
        except Exception:
            # Never hide the original error or delete on an uncertain acceptance outcome.
            log.exception("upload artifact reconciliation needed: project=%s request=%s", self.project_id, self.request_key)
        return False
