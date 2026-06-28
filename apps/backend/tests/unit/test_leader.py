"""LeaderElector: single-machine permanent leader + DB-mode acquire/lose/takeover
gating of the control loops (HA Phase 2c)."""
import asyncio

import pytest

from app.core.leader import LeaderElector

pytestmark = pytest.mark.unit


class _Hooks:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    async def on_acquire(self):
        self.acquired += 1

    async def on_release(self):
        self.released += 1


class _LeaseStore:
    """Scriptable lease: try_acquire_leader returns the next queued result."""
    db_url = "postgres://x"  # marks DB mode

    def __init__(self, results):
        self._results = list(results)
        self.released = False

    async def try_acquire_leader(self, name, holder, ttl):
        return self._results.pop(0) if self._results else False

    async def release_leader(self, name, holder):
        self.released = True
        return True


async def test_single_machine_is_permanent_leader():
    # No DB (db_mode False) -> acquire once, lead forever, never release until stop.
    h = _Hooks()
    el = LeaderElector(store=None, holder="solo", ttl=10, on_acquire=h.on_acquire,
                       on_release=h.on_release, db_mode=False)
    task = asyncio.create_task(el.run())
    await asyncio.sleep(0.02)
    assert el.is_leader and h.acquired == 1 and h.released == 0
    await el.stop()
    await task
    assert h.released == 1  # stepped down on shutdown


async def test_db_mode_acquire_then_lose_then_reacquire():
    h = _Hooks()
    store = _LeaseStore([True, True, False, True])  # lead, hold, lose, regain
    el = LeaderElector(store, holder="A", ttl=6, on_acquire=h.on_acquire,
                       on_release=h.on_release, interval=0.01)
    task = asyncio.create_task(el.run())
    await asyncio.sleep(0.1)
    await el.stop()
    await task
    assert h.acquired == 2  # gained leadership twice
    assert h.released >= 1  # released when it lost it
    assert store.released is True  # lease released on shutdown


async def test_follower_never_acquires():
    h = _Hooks()
    store = _LeaseStore([False, False, False])  # someone else holds it
    el = LeaderElector(store, holder="B", ttl=6, on_acquire=h.on_acquire,
                       on_release=h.on_release, interval=0.01)
    task = asyncio.create_task(el.run())
    await asyncio.sleep(0.05)
    await el.stop()
    await task
    assert h.acquired == 0 and not el.is_leader


async def test_acquire_exception_is_treated_as_not_leader():
    h = _Hooks()

    class _Boom(_LeaseStore):
        async def try_acquire_leader(self, name, holder, ttl):
            raise RuntimeError("db down")

    el = LeaderElector(_Boom([]), holder="A", ttl=6, on_acquire=h.on_acquire,
                       on_release=h.on_release, interval=0.01)
    task = asyncio.create_task(el.run())
    await asyncio.sleep(0.05)
    await el.stop()
    await task
    assert h.acquired == 0  # never leads while the DB is unreachable
