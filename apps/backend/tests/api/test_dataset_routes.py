"""Benchmark dataset routes: catalog listing + admin gating."""
import pytest

pytestmark = pytest.mark.api


def test_list_datasets_returns_catalog_and_disk(client):
    body = client.get("/api/datasets").json()
    assert "disk" in body and {"total", "used", "free"} <= body["disk"].keys()
    keys = {d["key"] for d in body["datasets"]}
    # perf (single-file) + eval (whole-repo) datasets both listed
    assert {"share_gpt_zh", "openqa"} <= keys  # perf
    assert {"gsm8k", "mmlu", "ceval"} <= keys  # eval
    for d in body["datasets"]:
        assert {"label", "dataset_id", "category", "cached", "size_on_disk"} <= d.keys()
        if d["category"] == "perf":
            assert "file" in d


def test_download_unknown_dataset_is_400(client):
    assert client.post("/api/datasets/download", json={"key": "nope"}).status_code == 400


def test_download_requires_admin_when_enabled(auth_client):
    resp = auth_client.post("/api/datasets/download", json={"key": "openqa"})
    assert resp.status_code == 401


def test_delete_unknown_is_404(client):
    # Unknown key never touches the filesystem (delete returns False -> 404).
    assert client.delete("/api/datasets/nope").status_code == 404


def test_dataset_downloads_list_is_empty_initially(client):
    assert client.get("/api/datasets/downloads").json() == []
