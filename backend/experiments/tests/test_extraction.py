"""Decision-extraction regex: the pre-registered parse, exercised edge-first."""

import pytest

from experiments.harness.extraction import MALFORMED, extract_decision


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Evidence gathered.\nFINAL DECISION: escalate", "escalate"),
        ("FINAL DECISION: dismiss", "dismiss"),
        ("...\nFINAL DECISION: investigate\n\n", "investigate"),
        ("reasoning\nfinal decision: ESCALATE", "escalate"),  # case-insensitive
        ("reasoning\n**FINAL DECISION: dismiss**", "dismiss"),  # markdown bold
        ("reasoning\nFINAL DECISION: escalate.", "escalate"),  # trailing period
        ("reasoning\n`FINAL DECISION: investigate`", "investigate"),
        ("reasoning\nFINAL  DECISION:  dismiss", "dismiss"),  # extra spaces
    ],
)
def test_valid_final_lines(text: str, expected: str) -> None:
    assert extract_decision(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "   \n\n  ",
        "I would escalate this alert.",  # no contract line
        "FINAL DECISION: escalate\nbut let me reconsider...",  # not last line
        "FINAL DECISION: maybe",  # invalid label
        "FINAL DECISION escalate",  # missing colon
        "FINAL DECISION: escalate or dismiss",  # trailing content
        "THE FINAL DECISION: dismiss",  # prefix content on the line
    ],
)
def test_malformed(text: str | None) -> None:
    assert extract_decision(text) == MALFORMED
