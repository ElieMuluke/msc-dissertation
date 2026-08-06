"""Metrics on synthetic journals: hand-computed expectations throughout."""

import pytest

from experiments.analysis import metrics
from experiments.analysis.stats import bootstrap_ci_mean, paired_permutation_pvalue


def test_pass_hat_k() -> None:
    assert metrics.pass_hat_k(5, 5, 5) == 1.0
    assert metrics.pass_hat_k(5, 0, 1) == 0.0
    assert metrics.pass_hat_k(5, 4, 5) == 0.0  # one failure kills all-5
    assert metrics.pass_hat_k(5, 4, 1) == pytest.approx(0.8)
    # C(3,2)/C(5,2) = 3/10
    assert metrics.pass_hat_k(5, 3, 2) == pytest.approx(0.3)
    with pytest.raises(ValueError):
        metrics.pass_hat_k(5, 5, 6)


def test_dar_and_flip() -> None:
    assert metrics.decision_agreement_rate(["a", "a", "a"]) == 1.0
    # pairs: (a,a) agree, (a,b) x2 disagree -> 1/3
    assert metrics.decision_agreement_rate(["a", "a", "b"]) == pytest.approx(1 / 3)
    assert not metrics.flipped(["a", "a"])
    assert metrics.flipped(["a", "malformed"])


def test_krippendorff_alpha_perfect_and_none() -> None:
    assert metrics.krippendorff_alpha([["a", "a"], ["b", "b"]]) == 1.0
    assert metrics.krippendorff_alpha([["a"], ["b"]]) is None  # no pairable values
    assert metrics.krippendorff_alpha([["a", "a"], ["a", "a"]]) == 1.0  # De == 0


def test_krippendorff_alpha_known_value() -> None:
    # Two units, two coders each: one unanimous, one split.
    # Coincidences: unit1 a-a (2), unit2 a-b + b-a (2). n_a=3, n_b=1, n=4.
    # Do = 2; De = (3*1 + 1*3)/3 = 2. alpha = 1 - 2/2 = 0.
    units = [["a", "a"], ["a", "b"]]
    assert metrics.krippendorff_alpha(units) == pytest.approx(0.0)


def test_majority_vote_tie_break_is_canonical() -> None:
    label, tied = metrics.majority_vote(["dismiss", "escalate"])
    assert label == "escalate" and tied  # OUTCOMES order: escalate first
    label, tied = metrics.majority_vote(["dismiss", "dismiss", "escalate"])
    assert label == "dismiss" and not tied


def test_normalised_entropy() -> None:
    assert metrics.normalised_entropy(["a", "a", "a"]) == 0.0
    # uniform over 4 categories = maximal = 1.0
    assert metrics.normalised_entropy(
        ["escalate", "dismiss", "investigate", "malformed"]
    ) == pytest.approx(1.0)
    # 50/50 over 2 of 4 categories: H=1 bit / log2(4)=2 -> 0.5
    assert metrics.normalised_entropy(["a", "b"]) == pytest.approx(0.5)


def test_trajectory_metrics() -> None:
    same = [["t1", "t2"], ["t1", "t2"], ["t1", "t2"]]
    assert metrics.trajectory_agreement_rate(same) == 1.0
    assert metrics.trajectory_jaccard(same) == 1.0
    assert metrics.trajectory_nlcs(same) == 1.0

    mixed = [["t1", "t2"], ["t2", "t1"]]
    assert metrics.trajectory_agreement_rate(mixed) == 0.0  # order matters
    assert metrics.trajectory_jaccard(mixed) == 1.0  # sets equal
    assert metrics.trajectory_nlcs(mixed) == pytest.approx(0.5)  # LCS len 1 / 2

    empties = [[], []]
    assert metrics.trajectory_jaccard(empties) == 1.0
    assert metrics.trajectory_nlcs(empties) == 1.0
    assert metrics.trajectory_nlcs([[], ["t1"]]) == 0.0


def test_lexical_consistency_rouge_l_hand_computed() -> None:
    """3 short synthetic outputs, pairwise ROUGE-L F1 worked by hand.

    Tokens (lowercased, whitespace): o1 = o2 = [final, decision:, escalate];
    o3 = [final, verdict, escalate]. Pairs: (o1,o2) F1 = 1.0;
    (o1,o3) and (o2,o3): LCS = 2 -> P = R = 2/3 -> F1 = 2/3.
    Mean = (1 + 2/3 + 2/3) / 3 = 7/9.
    """
    outputs = [
        "FINAL DECISION: escalate",
        "final decision: escalate",  # identical after lowercasing
        "FINAL verdict escalate",
    ]
    assert metrics.lexical_consistency(outputs) == pytest.approx(7 / 9)


def test_lexical_consistency_edges() -> None:
    assert metrics.lexical_consistency(["same text", "same text"]) == 1.0
    assert metrics.lexical_consistency(["", ""]) == 1.0  # both empty: identical
    assert metrics.lexical_consistency(["", "something"]) == 0.0
    assert metrics.lexical_consistency(["aa bb", "cc dd"]) == 0.0  # no overlap


def _journal(arm: str, condition: str, case_decisions: dict[str, list[str]]) -> list[dict]:
    records = []
    for case_id, decisions in case_decisions.items():
        for idx, decision in enumerate(decisions):
            records.append(
                {
                    "arm": arm,
                    "condition": condition,
                    "case_id": case_id,
                    "repeat_idx": idx,
                    "decision": decision,
                    "tool_calls": ["check_sanctions_list"],
                    "raw_output": f"case {case_id}\nFINAL DECISION: {decision}",
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "wall_clock_s": 2.0,
                }
            )
    return records


def test_condition_summary_on_synthetic_journal() -> None:
    journal = _journal(
        "single",
        "t07-varied",
        {
            "C1": ["escalate"] * 5,  # all agree with label
            "C2": ["dismiss", "dismiss", "escalate", "dismiss", "dismiss"],  # 1 flip
        },
    )
    labels = {"C1": "escalate", "C2": "dismiss"}
    groups = metrics.group_case_runs(journal, "single", "t07-varied")
    assert set(groups) == {"C1", "C2"}
    summary = metrics.condition_summary(groups, labels)
    assert summary["cases"] == 2 and summary["repeats"] == 5
    assert summary["pass^5"] == pytest.approx(0.5)  # C1 yes, C2 no
    assert summary["pass^1"] == pytest.approx((1.0 + 0.8) / 2)
    # DAR: C1 = 1.0; C2 pairs: C(5,2)=10, agreeing = C(4,2)=6 -> 0.6
    assert summary["DAR"] == pytest.approx((1.0 + 0.6) / 2)
    assert summary["flip_rate"] == pytest.approx(0.5)
    assert summary["majority_vote_accuracy"] == 1.0
    assert summary["malformed_rate"] == 0.0
    assert summary["tokens_per_run"] == pytest.approx(150.0)
    # tokens/pass^k at every supported k (all-k reporting, no post-hoc choice);
    # k=15 unsupported at 5 repeats -> key absent, report renders "—".
    assert summary["tokens_per_pass^1"] == pytest.approx(150.0 / 0.9)
    assert summary["tokens_per_pass^5"] == pytest.approx(150.0 / 0.5)
    assert "pass^15" not in summary and "tokens_per_pass^15" not in summary
    assert summary["TAR"] == 1.0
    # rouge_l_f1: C1 outputs identical -> 1.0. C2 outputs are 5 tokens each,
    # differing only in the decision token: 6 identical pairs (4 dismiss) +
    # 4 cross pairs with LCS=4 -> F1=0.8; case mean (6*1 + 4*0.8)/10 = 0.92.
    assert summary["rouge_l_f1"] == pytest.approx((1.0 + 0.92) / 2)
    assert summary["worst_entropy_cases"][0] == "C2"
    # grouping excludes other arms/conditions
    assert metrics.group_case_runs(journal, "mas", "t07-varied") == {}


def test_stats_helpers() -> None:
    lo, hi = bootstrap_ci_mean([1.0, 1.0, 1.0, 1.0], seed=0)
    assert lo == hi == 1.0
    diffs = [0.0] * 20
    assert paired_permutation_pvalue(diffs, seed=0) == 1.0
    strong = [0.5] * 20
    assert paired_permutation_pvalue(strong, seed=0) < 0.01
