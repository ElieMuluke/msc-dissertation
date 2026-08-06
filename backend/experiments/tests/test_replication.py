"""Replication parameterisation: per-model isolation, shared seed schedule."""

from __future__ import annotations

import pytest

from experiments.config import (
    DEFAULT_CONFIG,
    EXPERIMENTS_DIR,
    REPLICATION_MODELS,
    config_for_model,
)
from experiments.harness import manifest as manifest_mod


def test_config_for_model_isolated_results_dirs() -> None:
    configs = {m: config_for_model(m) for m in REPLICATION_MODELS}
    dirs = {m: c.results_dir for m, c in configs.items()}
    assert len(set(dirs.values())) == len(dirs)  # pairwise distinct
    for m, c in configs.items():
        assert c.model == m
        assert c.results_dir.parent == EXPERIMENTS_DIR
    # headline model keeps the original results dir
    assert configs["qwen3.5:9b"].results_dir == DEFAULT_CONFIG.results_dir


def test_config_for_model_think_handling() -> None:
    assert config_for_model("qwen3.5:9b").think is False  # thinking model: send false
    assert config_for_model("qwen2.5:7b-instruct").think is None  # omit param
    assert config_for_model("mistral-nemo:latest").think is None
    with pytest.raises(KeyError, match="unknown replication model"):
        config_for_model("gpt-oss:20b")


def test_seed_schedule_identical_across_models() -> None:
    """Cross-model comparability: planned runs (incl. every seed) must be
    byte-identical across models — seeds derive from MASTER_SEED only."""
    plans = [
        manifest_mod.planned_runs(config_for_model(m)) for m in REPLICATION_MODELS
    ]
    assert plans[0] == plans[1] == plans[2]
    assert len(plans[0]) == 2300


def test_config_record_flows_model_and_think() -> None:
    records = {m: manifest_mod.config_record(config_for_model(m)) for m in REPLICATION_MODELS}
    hashes = {m: manifest_mod._sha256(r) for m, r in records.items()}
    assert len(set(hashes.values())) == 3  # model identity is hashed
    for m, r in records.items():
        assert r["model"] == m
    # everything except model identity is the identical design
    for r in records.values():
        r.pop("model"), r.pop("think")
    assert list(records.values())[0] == list(records.values())[1] == list(records.values())[2]


def test_build_manifest_uses_model_config(monkeypatch, tmp_path) -> None:
    """Manifest content flows per-model digest/identity without touching
    any real results dir (network calls stubbed)."""
    fake_digests = {"qwen2.5:7b-instruct": "sha-qwen25", "mistral-nemo:latest": "sha-nemo"}
    monkeypatch.setattr(
        manifest_mod, "model_digest", lambda url, model: fake_digests[model]
    )
    monkeypatch.setattr(
        manifest_mod, "model_show", lambda url, model: {"parameters": model}
    )
    monkeypatch.setattr(manifest_mod, "ollama_version", lambda url: "0.31.1")
    m1 = manifest_mod.build_manifest(config_for_model("qwen2.5:7b-instruct"))
    m2 = manifest_mod.build_manifest(config_for_model("mistral-nemo:latest"))
    assert m1["model"] == "qwen2.5:7b-instruct" and m1["model_digest"] == "sha-qwen25"
    assert m2["model"] == "mistral-nemo:latest" and m2["model_digest"] == "sha-nemo"
    assert m1["config_hash"] != m2["config_hash"]
    assert m1["runs"] == m2["runs"]  # identical plan + seeds
    assert m1["totals"] == m2["totals"] == {"single": 1150, "mas": 1150}
