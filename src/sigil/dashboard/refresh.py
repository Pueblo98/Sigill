"""Background refresh orchestrator.

Single APScheduler job (default every 60s) iterates all widgets, filters by
`requires_update`, and async-gathers fetches with a global semaphore. On
success: update cache, reset backoff. On exception: bump backoff, log
warning. Pages always read from the cache — they never block on a fetch.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, List, Optional, Sequence

from sigil.dashboard.cache import WidgetCache
from sigil.dashboard.widget import WidgetBase

logger = logging.getLogger(__name__)


SessionFactory = Callable[[], Any]


class RefreshOrchestrator:
    """Drives widget refresh.

    Construct with a list of widgets and a cache; call `start(scheduler,
    session_factory)` to register the periodic job. The orchestrator does
    not own the scheduler lifecycle (FastAPI does), it just schedules.

    The session_factory is expected to return an async context manager
    yielding a session object; widgets receive this session in
    `Widget.fetch`. Tests can pass a no-op factory.
    """

    def __init__(
        self,
        widgets: Sequence[WidgetBase],
        cache: WidgetCache,
        *,
        concurrency: int = 8,
        interval_seconds: int = 60,
    ):
        self._widgets: List[WidgetBase] = list(widgets)
        self._cache = cache
        self._concurrency = concurrency
        self._interval_seconds = interval_seconds
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._scheduler = None
        self._session_factory: Optional[SessionFactory] = None
        self._job = None

    @property
    def widgets(self) -> List[WidgetBase]:
        return list(self._widgets)

    def start(self, scheduler: Any, session_factory: SessionFactory) -> None:
        """Register the 60s tick job on the supplied AsyncIOScheduler."""
        self._scheduler = scheduler
        self._session_factory = session_factory
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._job = scheduler.add_job(
            self.tick,
            trigger="interval",
            seconds=self._interval_seconds,
            id="dashboard-refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    async def tick(self, *, now: Optional[datetime] = None) -> None:
        """One iteration of the refresh loop.

        Public for tests to drive deterministically. Real usage: APScheduler
        invokes this every `interval_seconds`. Reentrancy is prevented by
        APScheduler's `max_instances=1`; we additionally guard against
        re-entry within the same call by lazy-init of the semaphore.
        """
        now = now or datetime.now(timezone.utc)
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._concurrency)

        due = [w for w in self._widgets if w.requires_update(now)]
        if not due:
            return

        coros = [self._fetch_one(w, now) for w in due]
        await asyncio.gather(*coros, return_exceptions=True)

    async def _fetch_one(self, widget: WidgetBase, now: datetime) -> None:
        assert self._semaphore is not None
        async with self._semaphore:
            try:
                if self._session_factory is None:
                    data = await widget.fetch(None)
                else:
                    cm = self._session_factory()
                    if hasattr(cm, "__aenter__"):
                        async with cm as session:
                            data = await widget.fetch(session)
                    else:
                        data = await widget.fetch(cm)
            except Exception as exc:
                widget.mark_error(exc, now=now)
                logger.warning(
                    "dashboard widget fetch failed: type=%s key=%s err=%s",
                    widget.type,
                    widget.cache_key(),
                    exc,
                )
                # Surface it back so asyncio.gather sees the exception, but
                # don't crash the tick.
                raise
            else:
                self._cache.set((widget.type, widget.cache_key()), data)
                widget.mark_success(now=now)


# Used by tests to wait for a tick to complete deterministically.
TickAwaitable = Awaitable[None]
