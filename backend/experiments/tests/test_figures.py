"""Figure statistics on a synthetic journal: hand-computed expectations."""

import pytest

from experiments.analysis.figures import arm_stats


def _record(case_id: str, condition: str, repeat: int, decision: str) -> dict:
    return {
        "case_id": case_id,
        "arm": "single",
        "condition": condition,
        "repeat_idx": repeat,
        "decision": decision,
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "tool_calls": [],
    }


LABELS = {"C1": "escalate", "C2": "dismiss", "P1": "escalate"}


def test_arm_stats_on_two_cases() -> None:
    records = [
        # C1: 3 of 4 correct, one disagreement -> flipped
        _record("C1", "t07-varied", 0, "escalate"),
        _record("C1", "t07-varied", 1, "escalate"),
        _record("C1", "t07-varied", 2, "escalate"),
        _record("C1", "t07-varied", 3, "dismiss"),
        # C2: all four wrong but perfectly self-consistent -> not flipped
        _record("C2", "t07-varied", 0, "investigate"),
        _record("C2", "t07-varied", 1, "investigate"),
        _record("C2", "t07-varied", 2, "investigate"),
        _record("C2", "t07-varied", 3, "investigate"),
    ]
    stats = arm_stats(records, "single", ("t07-varied",), LABELS, pass_ks=(1,))

    assert stats is not None
    assert (stats.cases, stats.repeats) == (2, 4)
    # pass^1 is the mean over cases of (correct / repeats): (3/4 + 0) / 2
    assert stats.pass_k[1] == pytest.approx(0.375)
    # C1 agrees on 3 of 6 pairs, C2 on 6 of 6 -> (0.5 + 1.0) / 2
    assert stats.dar == pytest.approx(0.75)
    assert (stats.flipped_cases, stats.flip_rate) == (1, 0.5)
    assert stats.tokens_per_run == pytest.approx(120.0)
    assert stats.decision_share["investigate"] == pytest.approx(0.5)
    assert stats.decision_share["escalate"] == pytest.approx(0.375)
    assert stats.decision_share["malformed"] == 0.0


def test_conditions_are_pooled_as_separate_case_groups() -> None:
    """A case measured under two conditions contributes two groups, not one."""
    records = [
        _record("C1", "t0-fixed", 0, "escalate"),
        _record("C1", "t0-fixed", 1, "escalate"),
        _record("P1", "pert-t0", 0, "escalate"),
        _record("P1", "pert-t0", 1, "dismiss"),
    ]
    stats = arm_stats(records, "single", ("t0-fixed", "pert-t0"), LABELS, pass_ks=(1,))

    assert stats is not None
    assert stats.cases == 2
    assert stats.flipped_cases == 1


def test_missing_condition_returns_none() -> None:
    records = [_record("C1", "t07-varied", 0, "escalate")]
    assert arm_stats(records, "single", ("t0-fixed",), LABELS) is None


def test_single_repeat_case_is_excluded() -> None:
    """A case with one run cannot be scored for agreement, so it is dropped."""
    records = [_record("C1", "t07-varied", 0, "escalate")]
    assert arm_stats(records, "single", ("t07-varied",), LABELS) is None
