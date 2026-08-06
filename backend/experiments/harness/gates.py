"""Pre-launch gate probes G0 (think-off) and G1 (determinism).

Both talk to the Ollama HTTP API directly (no LangChain) so the evidence
reflects the raw wire behaviour. Raw responses are written to
``experiments/results/gates/`` for the pilot notes.

Usage (from ``backend/``, backend venv)::

    python -m experiments.harness.gates g0 [--base-url URL] [--n 10]
    python -m experiments.harness.gates g1 [--base-url URL] [--n 5]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from experiments.config import DEFAULT_CONFIG, FIXED_SEED, RESULTS_DIR

GATES_DIR = RESULTS_DIR / "gates"

_THINK_TAG_RE = re.compile(r"<think\b|</think>", re.IGNORECASE)

_G0_PROMPTS = [
    "Reply with exactly one word: which is larger, 17 or 71?",
    "A wire transfer of $9,999 from a cash-intensive business was flagged. "
    "In two sentences, is this suspicious and why?",
    "List three red flags for money laundering in trade finance.",
    "What is 23 * 17? Answer with the number only.",
    "In one sentence, what does KYC stand for and why does it matter?",
]


def _chat(
    base_url: str,
    prompt: str,
    *,
    temperature: float,
    seed: int,
    think: bool | None,
    num_predict: int = 512,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """One non-streaming /api/chat call, returning the parsed response body."""
    payload: dict[str, Any] = {
        "model": DEFAULT_CONFIG.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": temperature, "seed": seed},
    }
    if think is not None:
        payload["think"] = think
    resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def g0_think_off(base_url: str, n: int = 10) -> bool:
    """G0: ``think: false`` must yield zero think content over ``n`` calls.

    Checks both surfaces where think content can appear: the dedicated
    ``message.thinking`` field and inline ``<think>`` tags in ``message.content``.
    """
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    clean = True
    for i in range(n):
        prompt = _G0_PROMPTS[i % len(_G0_PROMPTS)]
        t0 = time.monotonic()
        body = _chat(base_url, prompt, temperature=0.7, seed=1000 + i, think=False)
        msg = body.get("message", {})
        content = msg.get("content", "")
        thinking = msg.get("thinking")
        inline = bool(_THINK_TAG_RE.search(content))
        ok = not thinking and not inline
        clean &= ok
        records.append(
            {
                "call": i,
                "prompt": prompt,
                "http_ok": True,
                "thinking_field": thinking,
                "inline_think_tags": inline,
                "content_head": content[:400],
                "response_keys": sorted(body.keys()),
                "message_keys": sorted(msg.keys()),
                "wall_s": round(time.monotonic() - t0, 2),
                "clean": ok,
            }
        )
        print(f"G0 call {i}: clean={ok} thinking_field={thinking!r:.60} "
              f"inline={inline}", flush=True)
    out = GATES_DIR / "g0-think-off.json"
    out.write_text(json.dumps({"pass": clean, "n": n, "records": records}, indent=2))
    print(f"G0 {'PASS' if clean else 'FAIL'} — evidence in {out}")
    return clean


def g1_determinism(base_url: str, n: int = 5) -> bool:
    """G1: T=0 + fixed seed must give byte-identical output on ``n`` calls.

    One warm-up call is made first and discarded (PRD-A sweep rule).
    """
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    prompt = (
        "COMPLIANCE ALERT: a $47,500 USD wire from ABC Corp to XYZ Holdings in "
        "the Cayman Islands, flags: unusual_amount, offshore_destination. "
        "In under 150 words, assess the alert and end with one line "
        "'FINAL DECISION: <escalate|dismiss|investigate>'."
    )
    _chat(base_url, prompt, temperature=0.0, seed=FIXED_SEED, think=False)  # warm-up
    outputs: list[str] = []
    for i in range(n):
        body = _chat(base_url, prompt, temperature=0.0, seed=FIXED_SEED, think=False)
        content = body["message"]["content"]
        outputs.append(content)
        digest = hashlib.sha256(content.encode()).hexdigest()[:16]
        print(f"G1 call {i}: sha256[:16]={digest} len={len(content)}", flush=True)
    identical = all(o == outputs[0] for o in outputs)
    out = GATES_DIR / "g1-determinism.json"
    out.write_text(
        json.dumps(
            {
                "pass": identical,
                "n": n,
                "prompt": prompt,
                "seed": FIXED_SEED,
                "sha256": [hashlib.sha256(o.encode()).hexdigest() for o in outputs],
                "outputs": outputs,
            },
            indent=2,
        )
    )
    print(f"G1 {'PASS' if identical else 'FAIL'} — evidence in {out}")
    return identical


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=["g0", "g1"])
    parser.add_argument("--base-url", default=DEFAULT_CONFIG.base_url("single"))
    parser.add_argument("--n", type=int, default=None)
    args = parser.parse_args()
    if args.gate == "g0":
        ok = g0_think_off(args.base_url, args.n or 10)
    else:
        ok = g1_determinism(args.base_url, args.n or 5)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
