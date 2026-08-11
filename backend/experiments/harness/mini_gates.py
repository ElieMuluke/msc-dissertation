"""Replication mini-gates: per-model pre-launch checks in one command.

For each replication model (see ``config.REPLICATION_MODELS``) this runs:

1. **Think-behavior capture** — calls with ``think: false``, with the
   parameter omitted, and with ``think: true``, recording exactly how the
   model/server behave (non-thinking models may reject the parameter —
   that decides the model's ``think`` config value, which for the
   thinking-off replication models is ``None`` = omit).

   The PASS criterion depends on the track and is **inverted** for the
   thinking-on one (pre-registered, CHANGELOG 2026-08-11 evening):

   - thinking OFF (``config.think`` is ``False`` or ``None``) — every call
     in the configured mode must show NO reasoning anywhere: no
     ``message.thinking`` and no inline ``<think>`` markup in content.
   - thinking ON (``config.think is True``) — every call in the configured
     mode must show reasoning on a SEPARATE channel (``message.thinking``
     non-empty) AND content free of inline reasoning markup. A model that
     inlines its reasoning into ``content`` contaminates the measured
     output and FAILS — the exact failure lfm2.5:8b showed under
     ``think: false`` on 0.32.6.

   Override the inference with ``--expect-thinking`` /
   ``--no-expect-thinking`` (evidence records which was used).

2. **G1-style determinism** — one discarded warm-up, then 5 calls at T=0
   with the fixed seed; byte-identical outputs required. On the
   thinking-on track "byte-identical" is required of BOTH channels
   (content and thinking), and the probe uses the sweep's own
   ``num_predict`` so a deliberation preamble cannot truncate the answer
   into a trivially-identical empty string.
3. **2-case × 2-repeat pilot per arm** through the real runner into a
   scratch dir (never the model's results dir), with an extraction check
   (bar: ≥ 7/8 valid decisions overall, mirroring G3's ≥13/15). Unchanged
   on both tracks; inline-reasoning contamination seen in pilot outputs is
   recorded as evidence but does not move this bar (the think probe is
   where that is adjudicated).

Every stage also records per-call wall clock and token counts, so a sweep
ETA can be computed from the evidence — thinking-on runs cost roughly 3-5x
a thinking-off run.

Evidence is written to ``<model results dir>/gates/mini-gates<suffix>.json``
(``--evidence-suffix``, e.g. ``-ollama0329``, so a re-gate under a new
infra context never overwrites the previous context's evidence).
Requires the model's manifest to exist (``harness.manifest --model …``)
and the pinned arm servers to be up. Run only when no sweep is writing.

Usage (from ``backend/``)::

    python -m experiments.harness.mini_gates --model qwen2.5:7b-instruct
    python -m experiments.harness.mini_gates --model 'qwen3.5:9b@think'
    python -m experiments.harness.mini_gates --model granite4.1:8b \\
        --evidence-suffix -ollama0329
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from experiments.config import ARMS, FIXED_SEED, ExperimentConfig, config_for_model
from experiments.harness.gates import _chat
from experiments.harness.journal import read_journal, journal_path
from experiments.harness.models import ollama_version
from experiments.harness import runner as runner_mod

#: Inline reasoning markup in the ANSWER channel. Deliberately broader than
#: gates._THINK_TAG_RE: the pre-registered criterion says "<think>/</think>
#: or equivalent", and different families inline reasoning differently
#: (harmony channel markers, bracket and unicode delimiters). Any hit means
#: the reasoning was NOT confined to the separate channel.
_INLINE_REASONING_RE = re.compile(
    r"</?think(?:ing)?\b"  # <think> </think> <thinking>
    r"|</?reason(?:ing)?\b"  # <reasoning> </reasoning>
    r"|</?thought\b"  # <thought>
    r"|</?scratchpad\b"  # <scratchpad>
    r"|<\|(?:channel|start|end|message|constrain)\|>"  # gpt-oss harmony
    r"|◁/?think▷"  # kimi-style unicode delimiters
    r"|\[/?(?:THINK|THINKING|REASONING)\]",  # bracket delimiters
    re.IGNORECASE,
)


def has_inline_reasoning(text: str | None) -> bool:
    """True when the answer channel carries inline reasoning markup."""
    return bool(_INLINE_REASONING_RE.search(text or ""))


_THINK_PROBE_PROMPT = "Which is larger, 17 or 71? Answer with one word."
_DET_PROMPT = (
    "COMPLIANCE ALERT: a $47,500 USD wire from ABC Corp to XYZ Holdings in "
    "the Cayman Islands, flags: unusual_amount, offshore_destination. "
    "In under 150 words, assess the alert and end with one line "
    "'FINAL DECISION: <escalate|dismiss|investigate>'."
)


def _server_version(base_url: str) -> str:
    """Arm server version, recorded in the evidence (infra context stamp)."""
    try:
        return ollama_version(base_url)
    except Exception as exc:  # evidence, never a gate crash
        return f"unavailable: {type(exc).__name__}: {exc}"


def _usage(body: dict[str, Any], wall_s: float) -> dict[str, Any]:
    """Per-call cost evidence (feeds the sweep ETA)."""
    return {
        "wall_s": round(wall_s, 2),
        "prompt_tokens": body.get("prompt_eval_count"),
        "completion_tokens": body.get("eval_count"),
    }


def expects_thinking(config: ExperimentConfig) -> bool:
    """Which track this config belongs to (drives the inverted criterion)."""
    return config.think is True


def _probe(
    base_url: str, model: str, think: bool | None, num_predict: int = 512
) -> dict[str, Any]:
    """One probe call; HTTP errors are captured as data, never raised."""
    t0 = time.monotonic()
    try:
        body = _chat(
            base_url, _THINK_PROBE_PROMPT,
            temperature=0.0, seed=FIXED_SEED, think=think, model=model,
            num_predict=num_predict,
        )
        message = body.get("message", {})
        content = message.get("content") or ""
        thinking = message.get("thinking") or ""
        return {
            "think_param": think,
            "http_ok": True,
            "thinking_field_present": "thinking" in message,
            # Non-emptiness is what the inverted criterion requires: a
            # present-but-empty field is not reasoning on a separate channel.
            "thinking_nonempty": bool(thinking.strip()),
            "thinking_len": len(thinking),
            "thinking_head": thinking[:120],
            "inline_think_tags": has_inline_reasoning(content),
            "content_nonempty": bool(content.strip()),
            "content_head": content[:120],
            **_usage(body, time.monotonic() - t0),
        }
    except httpx.HTTPStatusError as exc:
        return {
            "think_param": think,
            "http_ok": False,
            "status": exc.response.status_code,
            "error_body": exc.response.text[:300],
            "wall_s": round(time.monotonic() - t0, 2),
        }


def _probe_verdict(record: dict[str, Any], expect_thinking: bool) -> bool:
    """The per-call pass rule for one probe, per track."""
    if not record["http_ok"]:
        return False
    if expect_thinking:
        # INVERTED: reasoning must exist, and only on the separate channel.
        return bool(record["thinking_nonempty"]) and not record["inline_think_tags"]
    # Thinking off: no reasoning on either surface.
    return not record["thinking_field_present"] and not record["inline_think_tags"]


def think_behavior(
    config: ExperimentConfig, expect_thinking: bool | None = None
) -> dict[str, Any]:
    """Capture think-parameter behavior; pass rule depends on the track.

    ``expect_thinking`` defaults to ``config.think is True``. All three wire
    modes are always probed (that capture is the point of this gate); only
    the calls made in the CONFIGURED mode are adjudicated. The thinking-on
    track probes its configured mode three times too, and at the sweep's own
    ``num_predict`` so a long deliberation cannot truncate the answer away.
    """
    if expect_thinking is None:
        expect_thinking = expects_thinking(config)
    base_url = config.base_url("single")
    probes: list[bool | None] = [False, False, False, None, True]
    if config.think is True:
        probes += [True, True]  # 3 samples of the configured mode, as elsewhere
    records = []
    for think in probes:
        num_predict = config.num_predict if think is True else 512
        records.append(_probe(base_url, config.model, think, num_predict))
    configured = [r for r in records if r["think_param"] is config.think]
    verdicts = [_probe_verdict(r, expect_thinking) for r in configured]
    for record, verdict in zip(configured, verdicts):
        record["verdict"] = verdict
    return {
        "pass": bool(verdicts) and all(verdicts),
        "configured_think": config.think,
        "expect_thinking": expect_thinking,
        "criterion": (
            "inverted (pre-registered 2026-08-11): message.thinking non-empty "
            "AND no inline reasoning markup in content"
            if expect_thinking else
            "no message.thinking AND no inline reasoning markup in content"
        ),
        "records": records,
    }


def determinism(
    config: ExperimentConfig, n: int = 5, expect_thinking: bool | None = None
) -> dict[str, Any]:
    """Warm-up + n byte-identical calls at T=0/fixed seed on the arm-A server.

    On the thinking-on track both channels must be byte-identical and the
    sweep's ``num_predict`` is used, so a deliberation preamble cannot
    truncate every answer to the same empty string and fake a pass.
    """
    if expect_thinking is None:
        expect_thinking = expects_thinking(config)
    base_url = config.base_url("single")
    kwargs: dict[str, Any] = dict(
        temperature=0.0, seed=FIXED_SEED, think=config.think, model=config.model
    )
    if expect_thinking:
        kwargs["num_predict"] = config.num_predict
    _chat(base_url, _DET_PROMPT, **kwargs)  # warm-up, discarded

    contents: list[str] = []
    thinkings: list[str] = []
    usage: list[dict[str, Any]] = []
    for _ in range(n):
        t0 = time.monotonic()
        body = _chat(base_url, _DET_PROMPT, **kwargs)
        message = body.get("message", {})
        contents.append(message.get("content") or "")
        thinkings.append(message.get("thinking") or "")
        usage.append(_usage(body, time.monotonic() - t0))

    def _hashes(values: list[str]) -> list[str]:
        return sorted({hashlib.sha256(v.encode()).hexdigest() for v in values})

    content_pass = len(_hashes(contents)) == 1
    thinking_pass = len(_hashes(thinkings)) == 1
    return {
        "pass": content_pass and (thinking_pass or not expect_thinking),
        "n": n,
        "expect_thinking": expect_thinking,
        "content_pass": content_pass,
        "thinking_pass": thinking_pass,
        "sha256": _hashes(contents),
        "thinking_sha256": _hashes(thinkings),
        "output_len": len(contents[0]),
        "thinking_len": len(thinkings[0]),
        "num_predict": kwargs.get("num_predict", 512),
        "usage": usage,
        "mean_wall_s": round(sum(u["wall_s"] for u in usage) / max(n, 1), 2),
        "mean_completion_tokens": round(
            sum(u["completion_tokens"] or 0 for u in usage) / max(n, 1), 1
        ),
    }


async def _pilot(config: ExperimentConfig, scratch: Path, key: str) -> dict[str, Any]:
    """2 cases × 2 repeats per arm through the real runner, extraction check."""
    manifest_src = config.results_dir / "manifest.json"
    if not manifest_src.exists():
        raise SystemExit(
            f"{manifest_src} missing — generate it first: "
            f"python -m experiments.harness.manifest --model '{key}'"
        )
    shutil.copy(manifest_src, scratch / "manifest.json")
    per_arm: dict[str, Any] = {}
    for arm in ARMS:
        args = argparse.Namespace(
            arm=arm, condition="t0-fixed", max_cases=2, max_repeats=2,
            no_git=True, allow_digest_mismatch=False, results_dir=scratch,
        )
        pilot_config = dataclasses.replace(config, results_dir=scratch)
        await runner_mod.run_sweep(args, pilot_config)
        records = [
            r for r in read_journal(journal_path(scratch, arm))
            if r["condition"] == "t0-fixed"
        ]
        n = max(len(records), 1)
        per_arm[arm] = {
            "runs": len(records),
            "valid": sum(r["decision"] != "malformed" for r in records),
            "decisions": [r["decision"] for r in records],
            "errors": [r["error"] for r in records if r["error"]],
            "mean_wall_clock_s": round(
                sum(r["wall_clock_s"] for r in records) / n, 2
            ),
            "mean_prompt_tokens": round(sum(r["prompt_tokens"] for r in records) / n, 1),
            "mean_completion_tokens": round(
                sum(r["completion_tokens"] for r in records) / n, 1
            ),
            # Contamination evidence only — the pilot bar is unchanged on both
            # tracks; inline reasoning is adjudicated by the think probe.
            "inline_reasoning_outputs": sum(
                has_inline_reasoning(r["raw_output"]) for r in records
            ),
        }
    total_valid = sum(a["valid"] for a in per_arm.values())
    total_runs = sum(a["runs"] for a in per_arm.values())
    return {"pass": total_runs == 8 and total_valid >= 7,
            "valid_total": f"{total_valid}/{total_runs}",
            "inline_reasoning_outputs": sum(
                a["inline_reasoning_outputs"] for a in per_arm.values()
            ),
            "arms": per_arm}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", required=True,
        help="replication registry key (config.REPLICATION_MODELS; may differ "
             "from the served model tag, e.g. 'qwen2.5:7b-instruct@0.32.6')",
    )
    parser.add_argument("--skip-pilot", action="store_true",
                        help="probes only (e.g. while servers are busy)")
    parser.add_argument(
        "--expect-thinking", action=argparse.BooleanOptionalAction, default=None,
        help="force the think-probe criterion instead of inferring it from "
             "config.think. --expect-thinking applies the INVERTED "
             "(thinking-on) rule: message.thinking non-empty AND no inline "
             "reasoning markup in content. --no-expect-thinking applies the "
             "thinking-off rule. Default: inferred (think is True -> inverted).",
    )
    parser.add_argument(
        "--evidence-suffix", default="",
        help="suffix for the evidence filename, e.g. '-ollama0329' -> "
             "gates/mini-gates-ollama0329.json. Use it whenever re-gating a "
             "model that already has evidence, so the earlier infra context's "
             "file is never overwritten.",
    )
    args = parser.parse_args()
    config = config_for_model(args.model)
    expect_thinking = (
        expects_thinking(config) if args.expect_thinking is None else args.expect_thinking
    )
    track = "thinking-on" if expect_thinking else "thinking-off"

    evidence: dict[str, Any] = {
        "registry_key": args.model,
        "model": config.model,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "servers": dict(config.arm_base_urls),
        "track": track,
        "configured_think": config.think,
        "expect_thinking": expect_thinking,
        "expect_thinking_source": (
            "inferred from config.think" if args.expect_thinking is None else "--expect-thinking flag"
        ),
        "ollama_version": {
            arm: _server_version(url) for arm, url in config.arm_base_urls.items()
        },
    }
    print(f"[mini-gates] {config.model}: {track} track "
          f"(think={config.think!r}); think-behavior probe...")
    evidence["think_behavior"] = think_behavior(config, expect_thinking)
    print(f"  pass={evidence['think_behavior']['pass']} "
          f"criterion={evidence['think_behavior']['criterion']}")
    print(f"[mini-gates] {config.model}: determinism (warm-up + 5)...")
    evidence["determinism"] = determinism(config, expect_thinking=expect_thinking)
    det = evidence["determinism"]
    print(f"  pass={det['pass']} sha256[:16]={det['sha256'][0][:16]} "
          f"mean_wall={det['mean_wall_s']}s "
          f"mean_completion_tokens={det['mean_completion_tokens']}")
    if not args.skip_pilot:
        print(f"[mini-gates] {config.model}: 2x2 pilot per arm...")
        scratch = Path(tempfile.mkdtemp(
            prefix=f"mini-gate-{args.model.replace(':', '-').replace('@', '-')}-"))
        evidence["pilot"] = asyncio.run(_pilot(config, scratch, args.model))
        evidence["pilot"]["scratch_dir"] = str(scratch)
        pilot = evidence["pilot"]
        print(f"  pass={pilot['pass']} valid={pilot['valid_total']} "
              f"inline_reasoning_outputs={pilot['inline_reasoning_outputs']}")
        for arm, stats in pilot["arms"].items():
            print(f"    {arm}: mean_wall={stats['mean_wall_clock_s']}s "
                  f"prompt_tok={stats['mean_prompt_tokens']} "
                  f"completion_tok={stats['mean_completion_tokens']}")

    gates_dir = config.results_dir / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    out = gates_dir / f"mini-gates{args.evidence_suffix}.json"
    out.write_text(json.dumps(evidence, indent=2))
    overall = all(evidence[k]["pass"] for k in ("think_behavior", "determinism", "pilot")
                  if k in evidence)
    print(f"[mini-gates] {config.model}: {'ALL PASS' if overall else 'FAIL'} — {out}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
