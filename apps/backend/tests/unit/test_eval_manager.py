"""EvalManager config-building (no subprocess)."""
from types import SimpleNamespace

import pytest

from app.core.settings import BackendSettings
from app.eval.manager import EvalError, EvalManager

pytestmark = pytest.mark.unit


def _manager(tmp_path):
    engine = SimpleNamespace(
        settings=SimpleNamespace(model_tag="Qwen/Qwen2.5-0.5B-Instruct"),
        instances=[SimpleNamespace(id="a", port=8006)],
    )
    fake_mgr = SimpleNamespace(config=SimpleNamespace(LLM_engines={"Qwen2.5-0.5B": engine}))
    settings = BackendSettings(admin_token="adm")
    return EvalManager(None, fake_mgr, settings, str(tmp_path), "http://127.0.0.1:8887")


def test_build_cfg_router_target(tmp_path):
    em = _manager(tmp_path)
    cfg = em._build_cfg(
        {"model": "Qwen2.5-0.5B", "target": "router", "datasets": ["gsm8k", "mmlu"],
         "limit": 5, "temperature": 0.0, "max_tokens": 1024},
        str(tmp_path / "1"),
    )
    assert cfg["api_url"] == "http://127.0.0.1:8887/v1"
    assert cfg["model"] == "Qwen2.5-0.5B"  # router routes by group key
    assert cfg["eval_type"] == "openai_api"
    assert cfg["datasets"] == ["gsm8k", "mmlu"]
    assert cfg["limit"] == 5
    assert cfg["generation_config"] == {"temperature": 0.0, "max_tokens": 1024}
    assert cfg["api_key"] == "adm"
    assert cfg["work_dir"] == str(tmp_path / "1") and cfg["no_timestamp"] is True
    assert cfg["ignore_errors"] is True


def test_build_cfg_instance_target_uses_port_and_tag(tmp_path):
    em = _manager(tmp_path)
    cfg = em._build_cfg(
        {"model": "Qwen2.5-0.5B", "target": "instance", "instance_key": "Qwen2.5-0.5B::a",
         "datasets": ["gsm8k"]},
        str(tmp_path / "1"),
    )
    assert cfg["api_url"] == "http://127.0.0.1:8006/v1"
    assert cfg["model"] == "Qwen/Qwen2.5-0.5B-Instruct"  # direct to vLLM by served tag


def test_build_cfg_no_limit_means_full(tmp_path):
    em = _manager(tmp_path)
    cfg = em._build_cfg(
        {"model": "Qwen2.5-0.5B", "target": "router", "datasets": ["gsm8k"], "limit": None},
        str(tmp_path / "1"),
    )
    assert "limit" not in cfg  # full dataset


def test_resolve_unknown_group_raises(tmp_path):
    em = _manager(tmp_path)
    with pytest.raises(EvalError):
        em._resolve("ghost", "router", None)


def test_resolve_unknown_instance_raises(tmp_path):
    em = _manager(tmp_path)
    with pytest.raises(EvalError):
        em._resolve("Qwen2.5-0.5B", "instance", "Qwen2.5-0.5B::nope")
