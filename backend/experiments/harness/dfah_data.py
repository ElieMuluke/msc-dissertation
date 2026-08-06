"""DFAH Compliance Triage case loading (verbatim, plus perturbation variants).

Cases come from the dfah-bench 0.1.1 source checkout (path pinned in
``experiments.config``). Ground-truth labels and rationales are kept out of
every prompt: :func:`render_case` whitelists presentation fields explicitly.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from experiments.config import ALERTS_JSON, PERTURBATION_JSON

#: Fields the model is allowed to see. Everything else (ground_truth,
#: rationale, perturbation metadata) is withheld.
_PROMPT_FIELDS = ("alert_id", "amount", "currency", "sender", "receiver",
                  "country", "flags", "description")


def load_primary_cases(path: Path = ALERTS_JSON) -> list[dict[str, Any]]:
    """Load the 50 scored DFAH alerts, verbatim."""
    data = json.loads(path.read_text())
    alerts = data["alerts"]
    if len(alerts) != 50:
        raise ValueError(f"expected 50 DFAH alerts, found {len(alerts)}")
    return alerts


def load_perturbation_cases(path: Path = PERTURBATION_JSON) -> list[dict[str, Any]]:
    """Load the 10 instrument-check perturbation variants."""
    data = json.loads(path.read_text())
    alerts = data["alerts"]
    if len(alerts) != 10:
        raise ValueError(f"expected 10 perturbation cases, found {len(alerts)}")
    return alerts


def ground_truth(cases: list[dict[str, Any]]) -> dict[str, str]:
    """Map ``case_id -> label`` for scoring (never enters a prompt)."""
    return {c["alert_id"]: c["ground_truth"] for c in cases}


def render_case(case: Mapping[str, Any]) -> str:
    """Render one alert as the user prompt, whitelisted fields only."""
    missing = [f for f in _PROMPT_FIELDS if f not in case]
    if missing:
        raise ValueError(f"case {case.get('alert_id')} missing fields: {missing}")
    return (
        f"COMPLIANCE ALERT: {case['alert_id']}\n\n"
        "Transaction details:\n"
        f"- Amount: {case['amount']:,.2f} {case['currency']}\n"
        f"- Sender: {case['sender']}\n"
        f"- Receiver: {case['receiver']}\n"
        f"- Destination country: {case['country']}\n"
        f"- Flags triggered: {', '.join(case['flags'])}\n"
        f"- Description: {case['description']}\n"
    )
