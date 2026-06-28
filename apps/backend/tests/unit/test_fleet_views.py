"""Fleet view assembly (HA Phase 3d-2).

The leader reports the fleet from its live registry; a follower reports it from the
shared store's observed state (backfilled by the owning agents), so any replica
shows the real fleet rather than its own idle registry.
"""
import json

import pytest

from app.llmops.state import ModelState

pytestmark = pytest.mark.unit

KEY = "Qwen3-0.6B::qwen3"


async def test_leader_fleet_views_come_from_registry(app):
    mgr = app.state.manager
    mgr.registry.get(KEY).set_state(ModelState.READY)
    views = {v["key"]: v for v in await mgr.fleet_views(prefer_store=False)}
    assert views[KEY]["state"] == "ready"
    # Every view is stamped with this node's id.
    assert all(v["node_id"] == mgr.settings.instance_id for v in views.values())


async def test_follower_fleet_views_prefer_store_observed(app):
    mgr = app.state.manager
    # This replica's registry is idle (STOPPED) ...
    mgr.registry.get(KEY).set_state(ModelState.STOPPED)
    # ... but the owning agent backfilled READY on another node into the store.
    view = {**mgr.registry.get(KEY).observed_dict(), "state": "ready", "pid": 4321}
    await mgr.store.upsert_instance_observed(KEY, "node-B", "ready", json.dumps(view), ttl=30)

    views = {v["key"]: v for v in await mgr.fleet_views(prefer_store=True)}
    assert views[KEY]["state"] == "ready"
    assert views[KEY]["pid"] == 4321
    assert views[KEY]["node_id"] == "node-B"


async def test_follower_falls_back_to_registry_for_unbackfilled(app):
    mgr = app.state.manager
    # Nothing in the store -> follower still lists every config instance (from the
    # registry base), just with local/idle state.
    views = {v["key"]: v for v in await mgr.fleet_views(prefer_store=True)}
    assert KEY in views
    other = "Qwen3-0.6B::qwen3-2"
    assert other in views
