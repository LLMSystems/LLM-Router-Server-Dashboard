"""Leader election so only one backend replica runs the singleton control loops.

The reconciler, autoscaler and prune loops assume a single actor — running two
replicas of them would fight (dueling start/stop, double pruning). This elector
holds a DB lease (packages/llmops-store leader_lease): only the lease holder runs
the loops; if it dies, a peer steals the expired lease and takes over within ~TTL.

Single-machine mode (SQLite, no LLMOPS_DB_URL) has exactly one backend, so it's a
permanent leader — behaviour is identical to before this existed.

See docs/ha-phase2-design_zh-CN.md §2c.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("llmops.leader")


class LeaderElector:
    def __init__(self, store, holder: str, ttl: float, on_acquire, on_release,
                 name: str = "control-plane", db_mode: bool | None = None,
                 interval: float | None = None) -> None:
        self.store = store
        self.holder = holder
        self.ttl = max(2.0, ttl)
        self.on_acquire = on_acquire  # async, called once when leadership is gained
        self.on_release = on_release  # async, called when leadership is lost
        self.name = name
        # Heartbeat / re-check cadence (default ttl/3, floored so we don't hammer
        # the DB); overridable for tests.
        self._interval = interval if interval is not None else max(1.0, self.ttl / 3)
        # Postgres (shared store) => contend for the lease; SQLite => single
        # replica => permanent leader.
        self.db_mode = bool(getattr(store, "db_url", None)) if db_mode is None else db_mode
        self.is_leader = False
        self._stop = asyncio.Event()

    async def run(self) -> None:
        if not self.db_mode or self.store is None:
            # Single machine: lead forever (no lease, no contention).
            self.is_leader = True
            await self.on_acquire()
            await self._stop.wait()
            await self._step_down()
            return

        interval = self._interval
        try:
            while not self._stop.is_set():
                try:
                    got = await self.store.try_acquire_leader(self.name, self.holder, self.ttl)
                except Exception:
                    logger.warning("leader-lease acquire failed; treating as not leader",
                                   exc_info=True)
                    got = False
                if got and not self.is_leader:
                    self.is_leader = True
                    logger.info("Acquired leadership as %s", self.holder)
                    await self.on_acquire()
                elif not got and self.is_leader:
                    logger.warning("Lost leadership as %s", self.holder)
                    await self._step_down()
                try:  # heartbeat / re-check, interruptible by stop()
                    await asyncio.wait_for(self._stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
        finally:
            await self._step_down()
            if self.db_mode and self.store is not None:
                try:
                    await self.store.release_leader(self.name, self.holder)
                except Exception:
                    pass

    async def _step_down(self) -> None:
        if self.is_leader:
            self.is_leader = False
            try:
                await self.on_release()
            except Exception:
                logger.warning("on_release failed during step-down", exc_info=True)

    async def stop(self) -> None:
        self._stop.set()
