"""Replication parameterisation: per-model isolation, shared seed schedule,
the key/tag registry extension (infra-context-2 keys, 2026-08-08), and the
per-key num_predict override behind the budget-raised thinking-on condition
(2026-08-12). No network: the wire is monkeypatched by the ``wire`` fixture."""

from __future__ import annotations

import asyncio

import pytest

from experiments.config import (
    DEFAULT_CONFIG,
    EXPERIMENTS_DIR,
    REPLICATION_MODELS,
    THINKING_BUDGET_OVERRIDES,
    THINKING_KEY_SUFFIX,
    config_for_model,
    is_budget_track_key,
    replication_entry,
    thinking_keys,
)
from experiments.harness import manifest as manifest_mod
from experiments.tests.test_harness_v2 import (  # noqa: F401
    CASE,
    IDENTITY,
    _entry,
    _response,
    _tools,
    wire,
)

#: Original (pre-key/tag-extension) entries: registry key == served model tag.
ORIGINAL_KEYS = tuple(k for k, v in REPLICATION_MODELS.items() if len(v) == 2)
#: Keys with an explicit served tag: infra-context keys ("@<version>") and
#: thinking-on keys ("@think", "@think-budget"). Both reuse a tag under a new
#: results dir; only the thinking-on ones change the wire ``think`` value.
ALIAS_KEYS = tuple(k for k, v in REPLICATION_MODELS.items() if len(v) == 3)
THINKING_KEYS = tuple(thinking_keys())
#: Budget-sensitivity track keys ("@b32"): equalised + disclosed budgets.
B32_KEYS = tuple(k for k in REPLICATION_MODELS if is_budget_track_key(k))
CONTEXT_KEYS = tuple(
    k for k in ALIAS_KEYS if k not in THINKING_KEYS and k not in B32_KEYS
)
#: Keys whose locked ``num_predict`` is raised by a pre-registered override.
BUDGET_KEYS = tuple(k for k in REPLICATION_MODELS if k in THINKING_BUDGET_OVERRIDES)


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
    # muse-glimmer reports the "thinking" capability, so its thinking-OFF
    # entry must send think:false explicitly — never omit (it would think).
    assert config_for_model("muse-glimmer:30b").think is False
    # thinking-on track: the ONLY entries that send think:true.
    assert config_for_model("qwen3.5:9b@think").think is True
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
    # Thinking-on keys serve the same tag with think=True — a DIFFERENT
    # identity, so they get their own hash: the manipulation is in the hash.
    # A budget-raised key serves the same tag AND think, so its raised
    # num_predict is what must separate it — hence it joins the identity.
    # The b32 track joins the identity: same tag/think/num_predict as a v2
    # key must STILL hash differently there (budgets + prompts differ).
    identities = {
        (r["model"], r["think"], r["num_predict"], "iteration_budgets" in r)
        for r in records.values()
    }
    assert len(set(hashes.values())) == len(identities)
    assert (
        len(set(hashes.values()))
        == len(ORIGINAL_KEYS) + len(THINKING_KEYS) + len(B32_KEYS)
    )
    for m, r in records.items():
        assert r["model"] == replication_entry(m)[0]
    # everything except model identity + generation budget is the same design
    # WITHIN each track; the b32 track additionally differs in prompts and
    # carries the iteration_budgets record (and in nothing else).
    for r in records.values():
        r.pop("model"), r.pop("think"), r.pop("num_predict")
    v2 = [r for m, r in records.items() if m not in B32_KEYS]
    b32 = [r for m, r in records.items() if m in B32_KEYS]
    assert all(r == v2[0] for r in v2)
    assert all(r == b32[0] for r in b32)
    extra_keys = set(b32[0]) - set(v2[0])
    assert extra_keys == {"iteration_budgets"}
    differing = {k for k in v2[0] if b32[0][k] != v2[0][k]}
    assert differing == {"prompts"}


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
        # gate battery 2026-08-11 (0.32.6), re-gated under 0.32.9
        "granite4.1:8b": ("granite4.1:8b", "results-granite4.1-8b", None),
        "lfm2.5:8b": ("lfm2.5:8b", "results-lfm2.5-8b", None),
        # pulled 2026-08-11 under 0.32.9; thinking-capable -> explicit false
        "muse-glimmer:30b": ("muse-glimmer:30b", "results-muse-glimmer-30b", False),
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


# --- thinking-on track (infra context 3) ------------------------------------


def test_thinking_keys_registry() -> None:
    """Every '@think' key serves an existing tag with think=True into its
    own '-thinking' results dir."""
    expected = {
        "qwen3.5:9b@think": ("qwen3.5:9b", "results-qwen3.5-9b-thinking"),
        "lfm2.5:8b@think": ("lfm2.5:8b", "results-lfm2.5-8b-thinking"),
        "gemma4:latest@think": ("gemma4:latest", "results-gemma4-thinking"),
        "gpt-oss:20b@think": ("gpt-oss:20b", "results-gpt-oss-20b-thinking"),
        "deepseek-r1:14b@think": ("deepseek-r1:14b", "results-deepseek-r1-14b-thinking"),
        "muse-glimmer:30b@think": ("muse-glimmer:30b", "results-muse-glimmer-30b-thinking"),
        # budget-raised condition (2026-08-12); same tag + think as
        # qwen3.5:9b@think, isolated dir, raised num_predict
        "qwen3.5:9b@think-budget": (
            "qwen3.5:9b", "results-qwen3.5-9b-thinking-budget"),
    }
    assert set(THINKING_KEYS) == set(expected)
    for key, (tag, dirname) in expected.items():
        assert THINKING_KEY_SUFFIX in key
        assert replication_entry(key) == (tag, dirname, True)
        c = config_for_model(key)
        assert c.model == tag and c.model != key
        assert c.think is True  # the manipulation, on the wire
        assert c.results_dir == EXPERIMENTS_DIR / dirname


def test_think_is_the_only_difference_from_thinking_off() -> None:
    """Within-model cross-track validity: a plain '@think' key must differ
    from its tag's thinking-off entry in ``think`` and results dir ONLY —
    every other locked design constant carries over verbatim. Budget-raised
    keys are excluded by construction (they differ in num_predict too, which
    is exactly why their cross-track comparison is confounded)."""
    for key in THINKING_KEYS:
        if key in BUDGET_KEYS:
            continue
        tag = replication_entry(key)[0]
        if tag not in REPLICATION_MODELS:
            continue  # thinking-only candidate (no thinking-off entry)
        on = manifest_mod.config_record(config_for_model(key))
        off = manifest_mod.config_record(config_for_model(tag))
        assert on["think"] is True and off["think"] is not True
        assert on["num_predict"] == off["num_predict"] == DEFAULT_CONFIG.num_predict
        assert config_for_model(key).results_dir != config_for_model(tag).results_dir
        on.pop("think"), off.pop("think")
        assert on == off  # same cases, conditions, prompts, seeds, caps


def test_thinking_dirs_never_collide_with_sealed_dirs() -> None:
    """A thinking-on sweep must never write into a sealed corpus dir."""
    sealed = {config_for_model(k).results_dir
              for k in REPLICATION_MODELS if k not in THINKING_KEYS}
    for key in THINKING_KEYS:
        results_dir = config_for_model(key).results_dir
        assert results_dir not in sealed
        assert "-thinking" in results_dir.name


# --- budget-raised thinking-on condition (pre-registered 2026-08-12) ---------


def test_budget_override_registry() -> None:
    """The override is keyed by registry KEY, raises the locked num_predict,
    and leaves num_ctx (and every other locked constant) alone."""
    # the b32 track's qwen3.5 thinking-on sweep carries the same 8192
    # override as its sealed counterpart (pre-approved; same confound).
    assert set(BUDGET_KEYS) == {"qwen3.5:9b@think-budget", "qwen3.5:9b@b32-think-budget"}
    assert THINKING_BUDGET_OVERRIDES["qwen3.5:9b@think-budget"] == 8192
    assert THINKING_BUDGET_OVERRIDES["qwen3.5:9b@b32-think-budget"] == 8192
    for key, dirname in (
        ("qwen3.5:9b@think-budget", "results-qwen3.5-9b-thinking-budget"),
        ("qwen3.5:9b@b32-think-budget", "results-budget-qwen3.5-9b-thinking"),
    ):
        c = config_for_model(key)
        assert c.model == "qwen3.5:9b"  # same served tag
        assert c.think is True
        assert c.num_predict == 8192  # the raised budget
        assert c.num_ctx == DEFAULT_CONFIG.num_ctx == 16384  # prompt+gen still fit
        assert c.results_dir == EXPERIMENTS_DIR / dirname
    # every other key in the registry keeps the locked constant
    for key in REPLICATION_MODELS:
        if key not in BUDGET_KEYS:
            assert config_for_model(key).num_predict == 2048, key


def test_budget_override_is_hashed_into_the_manifest_config() -> None:
    """The raised budget reaches the manifest's hashed config record, so a
    budget-raised sweep can never be confused with a standard one — not with
    its own thinking-on twin, nor with the sealed thinking-off sweep."""
    budget = manifest_mod.config_record(config_for_model("qwen3.5:9b@think-budget"))
    think_on = manifest_mod.config_record(config_for_model("qwen3.5:9b@think"))
    think_off = manifest_mod.config_record(config_for_model("qwen3.5:9b"))
    assert budget["num_predict"] == 8192
    assert think_on["num_predict"] == think_off["num_predict"] == 2048
    hashes = [manifest_mod._sha256(r) for r in (budget, think_on, think_off)]
    assert len(set(hashes)) == 3

    # THE CONFOUND, asserted: vs the sealed thinking-off sweep TWO factors
    # differ (think and num_predict); vs its thinking-on twin only the budget.
    differs = {k for k in budget if budget[k] != think_off[k]}
    assert differs == {"think", "num_predict"}
    assert {k for k in budget if budget[k] != think_on[k]} == {"num_predict"}


def test_budget_override_flows_onto_every_journal_line(wire) -> None:  # noqa: F811
    """num_predict is stamped on the journal line, so a pooled read of the
    journals separates budget-raised runs from standard ones."""
    from experiments.harness.adapter import ArmAdapter
    from experiments.harness.runner import execute_run

    config = config_for_model("qwen3.5:9b@think-budget")
    payloads, responses = wire
    responses += [_response("FINAL DECISION: escalate")]
    adapter = ArmAdapter("single", config, tool_builder=_tools)
    record = asyncio.run(execute_run(_entry("single"), adapter, CASE, config, IDENTITY))
    assert record["num_predict"] == 8192
    assert record["think"] is True
    assert payloads[0]["options"]["num_predict"] == 8192  # and onto the wire

    # a standard key still journals (and sends) the locked 2048
    responses += [_response("FINAL DECISION: escalate")]
    standard = config_for_model("qwen3.5:9b@think")
    record = asyncio.run(
        execute_run(_entry("single"), ArmAdapter("single", standard, tool_builder=_tools),
                    CASE, standard, IDENTITY)
    )
    assert record["num_predict"] == 2048
    assert payloads[-1]["options"]["num_predict"] == 2048


#: config_hash pinned per registry key, EXCLUDING the budget-raised key.
#: These are the identities every already-run and future non-overridden sweep
#: is pre-registered under; the override must not perturb a single one.
PINNED_CONFIG_HASHES = {
    "qwen3.5:9b": "8ea3c3a262359d5f9c8e9a14740bbdcde9294cf585fb2a49fcb94e14bdac2483",
    "qwen2.5:7b-instruct": "5346d4042de984529236a224202329951a20a71071704fb1e7eb20aea858ecc2",
    "mistral-nemo:latest": "8bee7231e60cd51cd016b9ce13cc9f8ad938015a31ad891cecf655d199830906",
    "mistral-small3.2:24b": "3e417b98d7ff56edf8f3ffb88e288a66105fd02259405eee65c381654f7da08b",
    "llama3.1:8b": "fd845938b1a9030f504cfbd492312afc5a453f03432ffa12153b089f42b3d145",
    "qwen2.5:14b-instruct": "99a76286972cdb9219f9d5a04eb4841d4d6f04a072bff243ba41eaf2f69ea37d",
    "gemma3:27b": "634d7c41ec5b1055eaaaddef4f295833228058a8b39403eeba6dc53749b59949",
    "gemma4:latest": "db5d8884bd7f74bd8f4d2c934b4d87d6669ba7c5dff7edfd85a258b40b8dc180",
    "granite4:latest": "744ed6a04d3dfa19c2c24911db4e59f4f863fe0b4d7a89e72c888c2ea73d70f9",
    "gpt-oss:20b": "269009891340729e948a15149286a98b7cfdc807e50842927d22034951cb2175",
    "granite4.1:8b": "c3658d08da83012947f2ade7512c71034536c8d68a3a1740f4077b864904187d",
    "lfm2.5:8b": "7a6d1317a9afd4d25c5ea23b005077d01b386ebe97a9218bcfc43dfc45e1a488",
    "muse-glimmer:30b": "a720737f7798474c268eb4573fcd21cf5c4ca5d02856401dd9fb8c45a89421bd",
    "qwen2.5:7b-instruct@0.32.6":
        "5346d4042de984529236a224202329951a20a71071704fb1e7eb20aea858ecc2",
    "qwen3.5:9b@0.32.6":
        "8ea3c3a262359d5f9c8e9a14740bbdcde9294cf585fb2a49fcb94e14bdac2483",
    "qwen2.5:14b-instruct@0.32.6":
        "99a76286972cdb9219f9d5a04eb4841d4d6f04a072bff243ba41eaf2f69ea37d",
    "qwen3.5:9b@think": "c5fbb8374bad4452506114145f61e5cf2d283b069f494a17f3cb3ff89557e46d",
    "lfm2.5:8b@think": "6a8531923a5903f874ee58f9512cd7f09314096435881e5d4b77d28a82234171",
    "gemma4:latest@think": "408ba3dd3f4434a857c21ae6b48f2a55c00d0243a49c2267a07daeaf2f943360",
    "gpt-oss:20b@think": "14b2d07f1549e8b11407912c4c604564fd9f873365b4ddbd748408b3d036ec90",
    "deepseek-r1:14b@think":
        "0adb076dd556dd7230d1c198d8bc53491e56ea5ba538aea5d3d759649442496c",
    "muse-glimmer:30b@think":
        "4fcdbb64fd00534711bd2aca70d1896429e7e219f97ac2e1fe025648dd0812b8",
    # budget-sensitivity track (v2b): new identities by design — budgets +
    # disclosure prompts are hashed. Pinned pre-launch 2026-08-18.
    "qwen2.5:7b-instruct@b32":
        "dff4516b50da49fef61498365e26c1323be542e4f3a44490c7fd8cee21756fc0",
    "granite4.1:8b@b32":
        "d04c66dc090443c6d26e8e52f5dcbd918907275f9d4fde4ac45834b1a8801236",
    "qwen3.5:9b@b32":
        "57724ba1c490e4dd1eb8f2853a4eba5dc2dbe93ff79082d9430905eab30bc33a",
    "lfm2.5:8b@b32-think":
        "29b037af9d23c0084edd1f9c5b6e6470f9b7b52e92e8df5df7b309123431d3e7",
    "gemma4:latest@b32":
        "548dc4adbfcbd00cb559a57843af54a8539d8652ae31eca3ab8e57d10a77cc37",
}


def test_non_overridden_config_hashes_unchanged() -> None:
    """Every non-overridden key's config identity is byte-pinned here
    (v2 keys pinned 2026-08-12; b32 keys pinned pre-launch 2026-08-18).
    Only the num_predict-overridden keys (BUDGET_KEYS) hash outside this
    table; a diff on any line below means a locked constant moved."""
    assert set(PINNED_CONFIG_HASHES) | set(BUDGET_KEYS) == set(REPLICATION_MODELS)
    for key, expected in PINNED_CONFIG_HASHES.items():
        config = config_for_model(key)
        assert config.num_predict == 2048, key
        assert manifest_mod._sha256(manifest_mod.config_record(config)) == expected, key
    budget_hashes = {
        key: manifest_mod._sha256(
            manifest_mod.config_record(config_for_model(key))
        )
        for key in BUDGET_KEYS
    }
    assert len(set(budget_hashes.values())) == len(budget_hashes)
    for key, budget_hash in budget_hashes.items():
        assert budget_hash not in set(PINNED_CONFIG_HASHES.values()), key


@pytest.mark.parametrize(
    "key,dirname",
    [
        ("qwen3.5:9b", "results"),
        ("qwen2.5:7b-instruct", "results-qwen2.5-7b"),
        ("qwen2.5:14b-instruct", "results-qwen2.5-14b"),
        ("gemma4:latest", "results-gemma4"),
        ("qwen2.5:7b-instruct@0.32.6", "results-qwen2.5-7b-ollama0326"),
        ("qwen3.5:9b@0.32.6", "results-qwen3.5-9b-ollama0326"),
        ("qwen2.5:14b-instruct@0.32.6", "results-qwen2.5-14b-ollama0326"),
        ("qwen3.5:9b@think", "results-qwen3.5-9b-thinking"),
    ],
)
def test_sealed_manifests_untouched_by_the_override(key, dirname) -> None:
    """The on-disk manifests of already-generated sweeps must still verify:
    self-consistent hash, locked num_predict=2048, and a config record that
    the CURRENT code still reproduces.

    The sealed (pre-harness-v2) manifests predate ``cache_policy`` entering
    the config record (CHANGELOG 2026-08-10), so that ONE key may be absent;
    nothing else may differ, and in particular the override must not add or
    move any field for these keys.
    """
    import json

    manifest = json.loads((EXPERIMENTS_DIR / dirname / "manifest.json").read_text())
    on_disk = manifest["config"]
    assert on_disk["num_predict"] == 2048
    # the pre-registered hash still verifies against its own record
    assert manifest_mod._sha256(on_disk) == manifest["config_hash"]
    current = manifest_mod.config_record(config_for_model(key))
    added_post_seal = set(current) - set(on_disk)
    assert added_post_seal <= {"cache_policy"}
    for field in on_disk:
        assert current[field] == on_disk[field], field
