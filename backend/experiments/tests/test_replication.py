"""Replication parameterisation: per-model isolation, shared seed schedule,
and the key/tag registry extension (infra-context-2 keys, 2026-08-08)."""

from __future__ import annotations

import pytest

from experiments.config import (
    DEFAULT_CONFIG,
    EXPERIMENTS_DIR,
    REPLICATION_MODELS,
    config_for_model,
    replication_entry,
)
from experiments.harness import manifest as manifest_mod

#: Original (pre-key/tag-extension) entries: registry key == served model tag.
ORIGINAL_KEYS = tuple(k for k, v in REPLICATION_MODELS.items() if len(v) == 2)
#: Infra-context keys: explicit served model tag differing from the key.
CONTEXT_KEYS = tuple(k for k, v in REPLICATION_MODELS.items() if len(v) == 3)


def test_config_for_model_isolated_results_dirs() -> None:
    configs = {m: config_for_model(m) for m in REPLICATION_MODELS}
    dirs = {m: c.results_dir for m, c in configs.items()}
    assert len(set(dirs.values())) == len(dirs)  # pairwise distinct
    for m, c in configs.items():
        assert c.model == replication_entry(m)[0]  # .model is the served TAG
        assert c.results_dir.parent == EXPERIMENTS_DIR
    # headline model keeps the original results dir
    assert configs["qwen3.5:9b"].results_dir == DEFAULT_CONFIG.results_dir


def test_config_for_model_think_handling() -> None:
    assert config_for_model("qwen3.5:9b").think is False  # thinking model: send false
    assert config_for_model("qwen2.5:7b-instruct").think is None  # omit param
    assert config_for_model("mistral-nemo:latest").think is None
    with pytest.raises(KeyError, match="unknown replication model"):
        config_for_model("never-registered-model:1b")
    with pytest.raises(KeyError, match="unknown replication model"):
        replication_entry("never-registered-model:1b")


def test_seed_schedule_identical_across_models() -> None:
    """Cross-model comparability: planned runs (incl. every seed) must be
    byte-identical across models — seeds derive from MASTER_SEED only."""
    plans = [
        manifest_mod.planned_runs(config_for_model(m)) for m in REPLICATION_MODELS
    ]
    assert all(p == plans[0] for p in plans)
    assert len(plans[0]) == 2300


def test_config_record_flows_model_and_think() -> None:
    records = {m: manifest_mod.config_record(config_for_model(m)) for m in REPLICATION_MODELS}
    hashes = {m: manifest_mod._sha256(r) for m, r in records.items()}
    # model identity (tag + think) is hashed: one hash per distinct identity.
    # Context keys serve the SAME tag/think as their original key, so their
    # config_hash intentionally matches it (identical design; infra context
    # is carried by manifest ollama_version + per-run journal fields).
    identities = {(r["model"], r["think"]) for r in records.values()}
    assert len(set(hashes.values())) == len(identities)
    assert len(set(hashes.values())) == len(ORIGINAL_KEYS)
    for m, r in records.items():
        assert r["model"] == replication_entry(m)[0]
    # everything except model identity is the identical design
    for r in records.values():
        r.pop("model"), r.pop("think")
    stripped = list(records.values())
    assert all(r == stripped[0] for r in stripped)


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


# --- key/tag registry extension (infra context 2) ----------------------------


def test_original_keys_resolve_exactly_as_before() -> None:
    """Backward compatibility: the pre-extension keys must resolve to the
    identical (model, think, results dirname) they always had — sealed
    sweeps' dirs and manifests depend on it."""
    expected = {
        "qwen3.5:9b": ("qwen3.5:9b", "results", False),
        "qwen2.5:7b-instruct": ("qwen2.5:7b-instruct", "results-qwen2.5-7b", None),
        "mistral-nemo:latest": ("mistral-nemo:latest", "results-mistral-nemo", None),
        "mistral-small3.2:24b": ("mistral-small3.2:24b", "results-mistral-small3.2", None),
        "llama3.1:8b": ("llama3.1:8b", "results-llama3.1-8b", None),
        "qwen2.5:14b-instruct": ("qwen2.5:14b-instruct", "results-qwen2.5-14b", None),
        "gemma3:27b": ("gemma3:27b", "results-gemma3-27b", None),
        "gemma4:latest": ("gemma4:latest", "results-gemma4", None),
        "granite4:latest": ("granite4:latest", "results-granite4", None),
        "gpt-oss:20b": ("gpt-oss:20b", "results-gpt-oss-20b", None),
    }
    assert set(ORIGINAL_KEYS) == set(expected)
    for key, (tag, dirname, think) in expected.items():
        assert replication_entry(key) == (tag, dirname, think)
        c = config_for_model(key)
        assert c.model == tag == key
        assert c.think == think
        assert c.results_dir == EXPERIMENTS_DIR / dirname


def test_context2_keys_key_tag_separation() -> None:
    """Infra-context-2 keys: registry key differs from the served tag;
    config .model is the TAG, results dir is the context-2 dir."""
    expected = {
        "qwen2.5:7b-instruct@0.32.6": (
            "qwen2.5:7b-instruct", "results-qwen2.5-7b-ollama0326", None),
        "qwen3.5:9b@0.32.6": (
            "qwen3.5:9b", "results-qwen3.5-9b-ollama0326", False),
        "qwen2.5:14b-instruct@0.32.6": (
            "qwen2.5:14b-instruct", "results-qwen2.5-14b-ollama0326", None),
    }
    assert set(CONTEXT_KEYS) == set(expected)
    for key, (tag, dirname, think) in expected.items():
        assert replication_entry(key) == (tag, dirname, think)
        c = config_for_model(key)
        assert c.model == tag  # what runners/manifests/servers use
        assert c.model != key
        assert c.think == think
        assert c.results_dir == EXPERIMENTS_DIR / dirname


def test_context2_dirs_isolated_from_original_dirs() -> None:
    """A context-2 key must never write into its original key's dir."""
    for key in CONTEXT_KEYS:
        tag = replication_entry(key)[0]
        assert tag in REPLICATION_MODELS  # the original entry still exists
        original = config_for_model(tag)
        context2 = config_for_model(key)
        assert context2.results_dir != original.results_dir
        # identical wire behaviour: same tag, same think handling
        assert context2.model == original.model
        assert context2.think == original.think


def test_context2_config_hash_matches_original() -> None:
    """Same design + same served model identity => same config_hash; the
    infra context is carried by manifest/journal ollama_version fields."""
    for key in CONTEXT_KEYS:
        tag = replication_entry(key)[0]
        h_ctx = manifest_mod._sha256(manifest_mod.config_record(config_for_model(key)))
        h_orig = manifest_mod._sha256(manifest_mod.config_record(config_for_model(tag)))
        assert h_ctx == h_orig
