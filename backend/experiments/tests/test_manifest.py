"""Planned-run expansion: counts, determinism, and seed policy."""

from experiments.config import FIXED_SEED
from experiments.harness.manifest import config_record, planned_runs


def test_run_matrix_totals() -> None:
    runs = planned_runs()
    assert len(runs) == 2300  # 2000 primary + 300 perturbation
    assert sum(r["block"] == "primary" for r in runs) == 2000
    assert sum(r["block"] == "perturbation" for r in runs) == 300
    assert sum(r["arm"] == "single" for r in runs) == 1150
    assert len({r["run_id"] for r in runs}) == 2300


def test_seed_policy() -> None:
    runs = planned_runs()
    for r in runs:
        if r["condition"] in ("t0-fixed", "pert-t0"):
            assert r["seed"] == FIXED_SEED and r["temperature"] == 0.0
    varied = [r for r in runs if r["condition"] == "t07-varied"]
    # seed shared across arms for the same (case, repeat), varied across repeats
    by_key: dict[tuple[str, int], set[int]] = {}
    for r in varied:
        by_key.setdefault((r["case_id"], r["repeat_idx"]), set()).add(r["seed"])
    assert all(len(seeds) == 1 for seeds in by_key.values())
    all_seeds = [next(iter(s)) for s in by_key.values()]
    assert len(set(all_seeds)) > 1


def test_expansion_is_deterministic() -> None:
    assert planned_runs() == planned_runs()


def test_config_record_pins_prompts() -> None:
    cfg = config_record()
    assert "FINAL DECISION" in cfg["prompts"]["single_system"]
    assert "FINAL DECISION" in cfg["prompts"]["mas_reporting"]
    assert set(cfg["mas_tool_partition"]) == {
        "orchestrator", "data", "policy_risk", "reporting"
    }
    # R2: sampling defaults recorded numerically, min_p included
    sampling = cfg["sampling"]
    assert sampling["set_by_harness"] is False
    assert sampling["min_p"]["server_default"] == 0.0
    assert sampling["top_p"]["server_default"] == 0.9
    assert sampling["top_k"]["server_default"] == 40
