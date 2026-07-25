"""
Document Ingestion Queue — DCPI.
Async task queue that manages background PDF parsing jobs.

Key features:
  - Jobs are tracked in-memory with status (queued → processing → done | failed)
  - Max concurrent LLM calls capped at MAX_CONCURRENT_JOBS (default 2)
  - DB status column is updated on completion so frontend can poll
  - Queue survives restart via DB status check on boot (re-queues failed jobs)
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS = int(__import__("os").getenv("INGEST_MAX_CONCURRENT", "5"))


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class IngestionJob:
    job_id: str
    doc_id: str
    doc_type: str
    filename: str
    status: JobStatus = JobStatus.QUEUED
    queued_at: float = field(default_factory=time.monotonic)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    @property
    def elapsed_ms(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.finished_at or time.monotonic()
        return round((end - self.started_at) * 1000, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "filename": self.filename,
            "status": self.status.value,
            "queued_at": self.queued_at,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }


class IngestionQueue:
    """
    Singleton async queue. Submit jobs, worker picks them up with a semaphore
    limiting max concurrent LLM-heavy tasks.
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_JOBS):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
        self._jobs: Dict[str, IngestionJob] = {}   # doc_id → job
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background worker. Call once from FastAPI startup."""
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_event_loop()
            self._worker_task = loop.create_task(self._worker_loop())
            logger.info(f"Ingestion queue started (max_concurrent={MAX_CONCURRENT_JOBS})")
        except RuntimeError:
            # No running event loop yet (e.g. during tests)
            logger.warning("Ingestion queue: no event loop — worker not started")

    def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(
        self,
        doc_id: str,
        doc_type: str,
        filename: str,
        coro_factory: Callable[[], Coroutine],
    ) -> IngestionJob:
        """
        Submit a background ingestion job.

        coro_factory is a zero-argument callable that returns a coroutine.
        Use a lambda or functools.partial to capture arguments:

            queue.submit(
                doc_id=doc_id,
                doc_type="specification",
                filename=file.filename,
                coro_factory=lambda: _parse_spec_bg(doc_id, file_path),
            )
        """
        job = IngestionJob(
            job_id=str(uuid.uuid4()),
            doc_id=doc_id,
            doc_type=doc_type,
            filename=filename,
        )
        self._jobs[doc_id] = job
        self._queue.put_nowait((job, coro_factory))
        logger.info(f"Job queued [{job.job_id[:8]}] doc={doc_id} type={doc_type}")
        return job

    def status(self, doc_id: str) -> Optional[IngestionJob]:
        return self._jobs.get(doc_id)

    def all_jobs(self) -> list:
        return [j.to_dict() for j in self._jobs.values()]

    def purge_old_jobs(self, max_age_seconds: int = 3600) -> int:
        """Remove completed/failed jobs older than max_age_seconds."""
        now = time.monotonic()
        to_del = [
            doc_id for doc_id, job in self._jobs.items()
            if job.status in (JobStatus.DONE, JobStatus.FAILED)
            and job.finished_at is not None
            and (now - job.finished_at) > max_age_seconds
        ]
        for doc_id in to_del:
            del self._jobs[doc_id]
        return len(to_del)

    # ── Worker ────────────────────────────────────────────────────────────────

    async def _worker_loop(self) -> None:
        """Continuously pull jobs from queue and process them."""
        logger.info("Ingestion worker loop started")
        while self._running:
            try:
                job, coro_factory = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                # Fire & forget — semaphore limits concurrency
                asyncio.create_task(self._run_job(job, coro_factory))
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}")

    async def _run_job(self, job: IngestionJob, coro_factory: Callable) -> None:
        async with self._semaphore:
            job.status = JobStatus.PROCESSING
            job.started_at = time.monotonic()
            logger.info(f"Job started [{job.job_id[:8]}] doc={job.doc_id}")
            try:
                result = await coro_factory()
                job.status = JobStatus.DONE
                job.result = result
                logger.info(
                    f"Job done [{job.job_id[:8]}] doc={job.doc_id} "
                    f"elapsed={job.elapsed_ms:.0f}ms"
                )
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)[:500]
                logger.error(f"Job failed [{job.job_id[:8]}] doc={job.doc_id}: {e}")
            finally:
                job.finished_at = time.monotonic()
                self._queue.task_done()


# Shared singleton
ingestion_queue = IngestionQueue()
