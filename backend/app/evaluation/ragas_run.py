"""Run RAGAS RAG-generation evaluation over the golden set and log results to MLflow.

    python -m app.evaluation.ragas_run --k 4
    python -m app.evaluation.ragas_run --k 4 --limit 6   # quick bounded run
    python -m app.evaluation.ragas_run --k 4 --collection aml_sections_b --bm25-weight 0.3
    mlflow ui --backend-store-uri sqlite:///mlflow.db    # experiment: rag-ragas

The retrieval side under test is chosen entirely by flags: ``--collection`` picks the
chunking variant (``aml_corpus`` = page-window baseline; ``aml_sections_a`` = section
chunks; ``aml_sections_b`` = section chunks with parent-context prefix) and
``--bm25-weight`` turns on hybrid BM25+vector fusion. The active config — including a
store fingerprint (chunk count + detected chunking style) — is printed at startup and
logged to MLflow, so a run can never silently evaluate the wrong index.

Requires Ollama running. Answers are generated against the *real* ingested corpus (the
persisted Chroma store built from the JMLSG/FATF/sanctions PDFs), so the evaluation
exercises the actual retriever — the golden set's ground truths are grounded in that
corpus (see ``datasets/golden_set_v1.jsonl``).

Two evaluations are run and persisted:

- Core-4 generation metrics (faithfulness, answer relevancy, context precision/recall)
  over the golden set, using the ground-truth answer as the RAGAS ``reference``.
- TopicAdherence (precision/recall/F1) over in-scope golden questions only, scored against
  the KYC/AML ``REFERENCE_TOPICS``.
- Out-of-scope behavior over deliberately off-topic queries (``datasets/out_of_scope_v1.jsonl``),
  reported *separately* from topic adherence because RAGAS's precision formula scores a
  correct refusal as 0.0 (answered∧on-topic true positives = 0, false positives = 0 →
  0/(0+1e-10)); mixing the two sets pinned ~20% of the topic-adherence mean at 0
  regardless of agent behavior.

Every metric is grouped by which layer produced it (see :func:`build_layer_summary`,
printed/persisted as "Metrics by layer" at the top of each run's report):

- **Retrieval layer**: ``context_precision``/``context_recall`` (57 golden questions,
  against the ground-truth reference); ``retrieval_scope_confidence`` and
  ``gated_by_retrieval_confidence_rate`` (13 out-of-scope queries — the F25 scope gate's
  raw top-1 relevance signal and how often it alone short-circuits generation).
- **Generation layer**: ``faithfulness``/``answer_relevancy`` (57 golden questions);
  ``topic_adherence_{precision,recall,f1}`` (51 in-scope questions, golden minus
  ``no_answer``); ``generation_refusal_rate`` (out-of-scope queries the retrieval gate did
  *not* catch, judged via RAGAS's ``TopicRefusedPrompt`` for whether the model declined
  anyway — NaN if the gate caught every query).
- ``out_of_scope_refusal_rate`` is a **combined** figure (gate ∨ generation-refusal, kept
  for continuity with pre-gate runs) — not a single layer's number.

Chunking is *not* a fourth parallel layer: RAGAS has no standalone chunk-quality metric.
It is a retrieval design variable, only observable as a shift in the retrieval-layer
numbers when comparing collections (``--collection``/``--bm25-weight`` A/B runs, all
logged to the same MLflow experiment).

Judge independence: to avoid self-evaluation bias the RAGAS LLM judge should be a
*different model family* than the agent's answer generator. Set an independent judge via
``RAGAS_JUDGE_MODEL`` (e.g. ``gemma2:9b`` or ``mistral:7b``); when the judge shares the
generator's family a warning is emitted. The default (``qwen2.5:3b``) is chosen because it
reliably emits the structured JSON RAGAS requires — some small models (e.g. ``llama3.2:3b``)
fail to and yield NaN. The judge model and temperature are logged to MLflow for
reproducibility.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from app.evaluation import _ragas_compat  # noqa: F401 - side effect: must precede `import ragas`

import mlflow
import ragas

from app.evaluation.ragas_eval import (
    RagasRecord,
    RagasResult,
    default_metrics,
    run_ragas,
    to_evaluation_dataset,
    to_topic_adherence_sample,
    topic_adherence_metrics,
)
from app.generation import (
    OUT_OF_SCOPE_REFUSAL,
    GenerationConfig,
    build_answer_generator,
    resolve_scope_gate_threshold,
)
from app.ingestion.rag import RagConfig, build_rag

_BACKEND = Path(__file__).resolve().parents[2]
_DATASETS = Path(__file__).resolve().parent / "datasets"

# The RAGAS judge should be a different model family than the answer generator to avoid
# self-evaluation bias. The default below is chosen to reliably emit the structured JSON that
# RAGAS metrics require; a truly independent judge (e.g. ``gemma2:9b`` or ``mistral:7b``) can
# be set via ``RAGAS_JUDGE_MODEL``. When the judge and generator share a family a warning is
# emitted (see :func:`_warn_if_self_eval`). Deterministic temperature for reproducibility.
_DEFAULT_JUDGE_MODEL = "qwen2.5:3b"
_JUDGE_TEMPERATURE = 0.0


def _model_family(model: str) -> str:
    """Coarse model family key (text before ':' or a version digit), for bias detection."""
    return model.split(":", 1)[0].rstrip("0123456789.")


def _warn_if_self_eval(judge_model: str, generator_model: str) -> None:
    """Warn when the judge shares the generator's family (self-evaluation bias, Gap #5)."""
    if _model_family(judge_model) == _model_family(generator_model):
        logger.warning(
            "RAGAS judge (%s) shares a model family with the answer generator (%s): scores "
            "may be affected by self-evaluation bias. Set RAGAS_JUDGE_MODEL to an independent "
            "model (e.g. gemma2:9b or mistral:7b) for a bias-free judge.",
            judge_model,
            generator_model,
        )


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class _InMemoryJudgeCache:
    """Per-run judge-response cache, shared across all metrics scoring one dataset.

    ``topic_adherence_metrics()`` instantiates one ``TopicAdherenceScore`` per mode
    (precision/recall/f1); each is a fully independent metric object that re-runs topic
    extraction, refusal-checking and classification against the judge LLM for the *same*
    query. Without a shared cache, the three modes can disagree with each other (observed:
    ~16% of queries in a 2026-07 run had a reported F1 inconsistent with the harmonic mean
    of that same row's own precision/recall — proof the three modes were scored from
    different judge calls rather than one shared confusion matrix). RAGAS's
    ``LangchainLLMWrapper`` accepts a cache backend and wraps its ``generate``/``agenerate``
    calls with it (see ``ragas.cache.cacher``); passing one shared instance here makes
    identical judge prompts (same question/topic/reference_topics) resolve once per
    ``evaluate()`` run and get reused by every mode, keeping precision/recall/f1 consistent.
    """

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def get(self, key: str) -> object:
        return self._store.get(key)

    def set(self, key: str, value: object) -> None:
        self._store[key] = value

    def has_key(self, key: str) -> bool:
        return key in self._store


# Binary judge-verdict keys across the RAGAS metric schemas: context_recall's
# ``attributed`` and faithfulness's ``verdict`` are pydantic ``int`` fields, so a judge
# emitting a fractional "partially true" value (0.5) fails validation even in valid JSON.
_BINARY_VERDICT_KEYS = ("attributed", "verdict")


def _coerce_binary_verdicts(node: object) -> None:
    """Recursively round fractional binary verdicts to ints, in place.

    Conservative policy (disclosed in docs/evaluation.md): 0.5 rounds *down* — an unsure
    judge gives no credit, biasing scores down rather than up.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _BINARY_VERDICT_KEYS and isinstance(value, float):
                node[key] = 1 if value > 0.5 else 0
            else:
                _coerce_binary_verdicts(value)
    elif isinstance(node, list):
        for item in node:
            _coerce_binary_verdicts(item)


def _repair_judge_json(text: str) -> str:
    """Repair a judge completion so RAGAS's first-pass pydantic parse succeeds.

    Two failure classes observed with small local judges (2026-07-06/07 runs), both of
    which otherwise NaN the sample — and worse, trigger RAGAS's ``FixOutputFormat``
    retry, which is itself broken with a JSON-constrained judge (it expects
    ``{"text": ...}`` back and instead receives the corrected object, or a
    double-escaped string):

    - Invalid/double-encoded JSON (literal ``\\n`` outside strings, the whole object
      wrapped in a JSON string) — repaired via ``json_repair``.
    - Valid JSON with fractional binary verdicts (``"attributed": 0.5``) — coerced by
      :func:`_coerce_binary_verdicts`.

    Text that cannot be repaired into an object/array is returned unchanged so RAGAS's
    normal failure path (and the NaN accounting) still applies.
    """
    import json_repair

    def _parse(raw: str) -> object:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Literal \n / \t sequences *between* tokens are the most common breakage; turn
        # them into real whitespace (strict=False keeps any now-raw newline legal inside
        # strings), then fall back to full repair.
        unescaped = raw.replace("\\n", "\n").replace("\\t", "\t")
        try:
            return json.loads(unescaped, strict=False)
        except json.JSONDecodeError:
            return json_repair.loads(unescaped)

    parsed = _parse(text)
    if isinstance(parsed, str) and parsed.strip().startswith(("{", "[")):
        # double-encoded: a JSON string whose content is the actual JSON object
        parsed = _parse(parsed)
    if not isinstance(parsed, (dict, list)):
        return text
    _coerce_binary_verdicts(parsed)
    return json.dumps(parsed, ensure_ascii=False)


def _repair_generations(result):
    """Apply :func:`_repair_judge_json` to every generation in a ChatResult.

    Both ``generation.text`` and ``message.content`` are updated: RAGAS reads ``.text``
    off the LLMResult, and ``.text`` is derived from the message only at construction.
    """
    for generation in result.generations:
        repaired = _repair_judge_json(generation.text)
        if repaired != generation.text:
            generation.text = repaired
            generation.message.content = repaired
    return result


def _build_ragas_llm(config: GenerationConfig):
    """Wrap a local Ollama chat model as the RAGAS LLM judge (independent of the generator).

    The judge is set via ``RAGAS_JUDGE_MODEL`` (default :data:`_DEFAULT_JUDGE_MODEL`) and
    should be a *different family* from answer generation to avoid self-evaluation bias.
    ``format="json"`` turns on Ollama's grammar-constrained JSON decoding: every RAGAS
    judge prompt expects structured JSON, and small judges otherwise emit invalid escapes
    (observed: ``OutputParserException`` → NaN scores). Each completion is additionally
    passed through :func:`_repair_judge_json` before RAGAS parses it. Deterministic
    temperature and a high token cap keep that JSON untruncated. A shared in-memory cache
    is attached so repeated identical judge prompts within one run (see
    :class:`_InMemoryJudgeCache`) are answered once and reused rather than re-invoked
    with a possibly different result.

    Returns:
        A tuple ``(wrapped_llm, judge_model_name)`` so the caller can log which judge ran.
    """
    from langchain_ollama import ChatOllama
    from ragas.llms import LangchainLLMWrapper

    class _JudgeChatOllama(ChatOllama):
        """ChatOllama whose completions are repaired before RAGAS's pydantic parse."""

        def _generate(self, *args, **kwargs):
            return _repair_generations(super()._generate(*args, **kwargs))

        async def _agenerate(self, *args, **kwargs):
            return _repair_generations(await super()._agenerate(*args, **kwargs))

    judge_model = os.getenv("RAGAS_JUDGE_MODEL", _DEFAULT_JUDGE_MODEL)
    chat = _JudgeChatOllama(
        model=judge_model,
        base_url=config.base_url,
        temperature=_JUDGE_TEMPERATURE,
        format="json",
        num_predict=2048,
        num_ctx=config.num_ctx,
        keep_alive=config.keep_alive,
    )
    return LangchainLLMWrapper(chat, cache=_InMemoryJudgeCache()), judge_model


def _build_ragas_embeddings(embedding_model: str):
    """Wrap the local HuggingFace embedding model for RAGAS metrics that need it."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    hf = HuggingFaceEmbeddings(model_name=embedding_model, encode_kwargs={"normalize_embeddings": True})
    return LangchainEmbeddingsWrapper(hf)


def _persist(result: RagasResult, name: str, results_dir: Path) -> list[Path]:
    """Write per-query results to ``<results_dir>/<name>.{csv,json}``; return the paths."""
    import pandas as pd

    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / f"{name}.csv"
    json_path = results_dir / f"{name}.json"
    pd.DataFrame(result.sample_scores).to_csv(csv_path, index=False)
    json_path.write_text(
        json.dumps(result.sample_scores, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return [csv_path, json_path]


def _print_summary(title: str, result: RagasResult) -> None:
    print(f"\n=== {title} ===")
    print("Means:")
    for name, value in result.mean_scores.items():
        flag = "  [NaN]" if value != value else ""
        print(f"  {name}: {value:.3f}{flag}")
    if any(result.nan_counts.values()):
        print("NaN counts (flagged — malformed input or judge parse failure):")
        for name, count in result.nan_counts.items():
            if count:
                print(f"  {name}: {count}")


def _row_question(row: dict) -> str:
    """Extract the question from any per-sample row shape RAGAS/our runners produce.

    Handles the three shapes seen in ``RagasResult.sample_scores``: a plain string
    ``user_input`` (core-4 rows), a message list ``user_input`` (topic-adherence rows —
    the human turn's content is the question), and a ``question`` key (refusal rows).
    """
    user_input = row.get("user_input")
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, list):
        for message in user_input:
            mtype = getattr(message, "type", None) or (message.get("type") if isinstance(message, dict) else None)
            if mtype == "human":
                content = getattr(message, "content", None) or (
                    message.get("content") if isinstance(message, dict) else None
                )
                return content or "?"
        return "?"
    return str(row.get("question", "?"))


def _valid_scores(rows: list[dict], metric: str) -> list[tuple[float, dict]]:
    """(value, row) pairs for rows where ``metric`` is a valid (non-NaN) number."""
    scored = []
    for row in rows:
        value = row.get(metric)
        if isinstance(value, (int, float)) and not math.isnan(value):
            scored.append((float(value), row))
    return scored


def build_report(
    header: str,
    sections: list[tuple[str, RagasResult, list[str]]],
    categories: dict[str, str] | None = None,
    layer_summary: str | None = None,
) -> str:
    """Build a detailed markdown diagnostic report from one or more RAGAS results.

    Pure function (no I/O): callers print it and/or write it to disk. Each section is a
    ``(title, result, metric_names)`` triple and emits, per metric found in the rows:
    means (with NaN counts), a min/p25/median/p75/max/n distribution table over valid
    samples, per-category means (when ``categories`` maps questions to golden-set
    categories such as clear/ambiguous/no_answer), and the worst-5 queries sorted
    ascending by score. Refusal-shaped rows (a boolean ``refused`` column) additionally
    get a "Non-refused queries" list. Anything a section's rows don't carry is skipped.
    ``layer_summary`` (e.g. from :func:`build_layer_summary`) is inserted right after the
    header, before the per-section detail.
    """
    lines = ["# RAGAS evaluation report", "", header]
    if layer_summary:
        lines += ["", layer_summary.rstrip("\n")]
    for title, result, metric_names in sections:
        rows = result.sample_scores
        lines += ["", f"## {title}", "", "**Means**", ""]
        for metric in metric_names:
            if metric not in result.mean_scores:
                continue
            nan_count = result.nan_counts.get(metric, 0)
            suffix = f"  (NaN: {nan_count}/{len(rows)})" if nan_count else ""
            lines.append(f"- {metric}: {result.mean_scores[metric]:.3f}{suffix}")

        distribution_rows = []
        for metric in metric_names:
            values = sorted(value for value, _ in _valid_scores(rows, metric))
            if not values:
                continue
            if len(values) >= 2:
                p25, median, p75 = statistics.quantiles(values, n=4)
            else:
                p25 = median = p75 = values[0]
            distribution_rows.append(
                f"| {metric} | {values[0]:.3f} | {p25:.3f} | {median:.3f} | {p75:.3f} "
                f"| {values[-1]:.3f} | {len(values)} |"
            )
        if distribution_rows:
            lines += [
                "",
                "**Distributions** (valid samples only)",
                "",
                "| metric | min | p25 | median | p75 | max | n |",
                "|---|---|---|---|---|---|---|",
                *distribution_rows,
            ]

        if categories:
            matched = [(categories[q], row) for row in rows if (q := _row_question(row)) in categories]
            if matched:
                category_names = sorted({category for category, _ in matched})
                table_rows = []
                for metric in metric_names:
                    cells = []
                    for category in category_names:
                        values = [
                            value
                            for cat, row in matched
                            if cat == category
                            for value, _ in _valid_scores([row], metric)
                        ]
                        cells.append(f"{statistics.fmean(values):.3f} (n={len(values)})" if values else "—")
                    if any(cell != "—" for cell in cells):
                        table_rows.append(f"| {metric} | " + " | ".join(cells) + " |")
                if table_rows:
                    lines += [
                        "",
                        "**Per-category means**",
                        "",
                        "| metric | " + " | ".join(category_names) + " |",
                        "|---|" + "---|" * len(category_names),
                        *table_rows,
                    ]

        for metric in metric_names:
            scored = sorted(_valid_scores(rows, metric), key=lambda pair: pair[0])
            if not scored:
                continue
            lines += ["", f"**Worst 5 — {metric}**", ""]
            for value, row in scored[:5]:
                lines.append(f"- {value:.3f} | {_row_question(row)[:90]}")

        if any("refused" in row for row in rows):
            non_refused = [row for row in rows if not row.get("refused")]
            lines += ["", "**Non-refused queries**", ""]
            lines += [f"- {_row_question(row)[:90]}" for row in non_refused] or ["- none"]
    return "\n".join(lines) + "\n"


def _fmt_cell(result: RagasResult | None, metric_names: list[str]) -> str:
    """Render ``name: value`` pairs from a result's mean_scores, comma-joined; "—" if none.

    NaN means are shown, flagged ``[NaN]`` — never silently hidden (matches
    :func:`_print_summary`'s convention).
    """
    if result is None:
        return "—"
    parts = []
    for name in metric_names:
        if name not in result.mean_scores:
            continue
        value = result.mean_scores[name]
        flag = " [NaN]" if value != value else ""  # NaN != NaN
        parts.append(f"{name}: {value:.3f}{flag}")
    return ", ".join(parts) if parts else "—"


def build_layer_summary(
    core4: RagasResult,
    topic: RagasResult | None,
    out_of_scope: RagasResult | None,
    n_golden: int,
    n_in_scope: int,
    n_out_of_scope: int,
) -> str:
    """Group the run's metrics by evaluation layer (retrieval vs generation) and by
    question population, so it is clear which layer produced which number.

    Chunking is **not** an independent layer here — RAGAS has no standalone "chunk
    quality" metric; chunking is a retrieval *design variable*, only observable as a
    shift in the retrieval-layer numbers when comparing collections (see the
    ``--collection``/``--bm25-weight`` A/B runs logged to MLflow experiment ``rag-ragas``),
    not a parallel metric set measured here.
    """
    golden_col = f"{n_golden} golden questions (core-4)"
    in_scope_col = f"{n_in_scope} in-scope questions (topic adherence)"
    oos_col = f"{n_out_of_scope} out-of-scope questions"
    lines = [
        "## Metrics by layer",
        "",
        f"| Layer | {golden_col} | {in_scope_col} | {oos_col} |",
        "|---|---|---|---|",
        f"| Retrieval | {_fmt_cell(core4, ['context_precision', 'context_recall'])} | — | "
        f"{_fmt_cell(out_of_scope, ['retrieval_scope_confidence', 'gated_by_retrieval_confidence_rate'])} |",
        f"| Generation | {_fmt_cell(core4, ['faithfulness', 'answer_relevancy'])} | "
        f"{_fmt_cell(topic, ['topic_adherence_precision', 'topic_adherence_recall', 'topic_adherence_f1'])} | "
        f"{_fmt_cell(out_of_scope, ['generation_refusal_rate'])} |",
        f"| Combined (gate ∨ generation) | — | — | {_fmt_cell(out_of_scope, ['out_of_scope_refusal_rate'])} |",
        "",
        "Chunking has no standalone metric — it is a retrieval design variable, evaluated by "
        "A/B-comparing `--collection`/`--bm25-weight` runs (see `rag-ragas` in MLflow), not a "
        "parallel layer measured per-run.",
    ]
    return "\n".join(lines) + "\n"


def _describe_store(rag) -> tuple[int, str]:
    """Fingerprint the store the eval will retrieve from: chunk count + chunking style.

    Style is inferred from a probe retrieval (what the eval will actually see):
    section-aware chunks carry a ``section`` metadata key; page-window chunks don't.
    """
    n_chunks = sum(source.pages for source in rag.list_sources())
    probe = rag.search("customer due diligence", k=1)
    if not probe:
        return n_chunks, "unknown"
    return n_chunks, "section" if "section" in probe[0].metadata else "page-window"


def _run_core4(generator, k, golden_rows, llm, embeddings) -> RagasResult:
    records = []
    for row in golden_rows:
        answer = generator.generate(row["question"], k=k)
        records.append(RagasRecord(row["question"], answer.answer, answer.contexts, row["ground_truth"]))
    dataset = to_evaluation_dataset(records)
    return run_ragas(dataset, llm=llm, embeddings=embeddings, metrics=default_metrics())


def _run_topic_adherence(generator, k, in_scope_rows, llm) -> RagasResult:
    """Score TopicAdherence P/R/F1 over in-scope rows only (out-of-scope refusals are
    measured separately by :func:`_run_refusal_rate` — RAGAS's precision formula scores a
    correct refusal as 0.0, so mixing the sets pins part of the mean at 0)."""
    from ragas import EvaluationDataset

    samples = []
    for row in in_scope_rows:
        answer = generator.generate(row["question"], k=k)
        samples.append(to_topic_adherence_sample(row["question"], answer.answer))
    dataset = EvaluationDataset(samples=samples)
    return run_ragas(dataset, llm=llm, metrics=topic_adherence_metrics())


def _run_out_of_scope(rag, generator, k, out_of_scope_rows, llm) -> RagasResult:
    """Out-of-scope behavior, split by which layer actually did the refusing.

    Two independent mechanisms can produce a refusal, and conflating them hides which
    one is doing the work:

    - **Retrieval layer**: ``RagSystem.scope_confidence`` (raw top-1 vector relevance,
      bypassing hybrid fusion) is low, so ``AnswerGenerator``'s F25 gate short-circuits
      *before* any retrieval is surfaced or any LLM call is made — detected here by the
      generator returning the exact fixed :data:`OUT_OF_SCOPE_REFUSAL` string. Reported as
      ``retrieval_scope_confidence`` (mean top-1 relevance over all queries — low is
      correct here) and ``gated_by_retrieval_confidence_rate`` (fraction the gate caught).
    - **Generation layer**: for the remaining, *ungated* queries (the gate let them
      through, or the gate is disabled), the agent still received context and generated
      an answer; that answer is judged with RAGAS's ``TopicRefusedPrompt`` for whether it
      declined anyway. Reported as ``generation_refusal_rate`` (NaN if every query was
      gated — there is nothing left to judge).

    ``out_of_scope_refusal_rate`` (gate ∨ generation-refusal, over all queries) is kept
    for continuity with earlier runs but is a combined figure, not a single layer's.
    """
    import asyncio

    from ragas.metrics._topic_adherence import TopicRefusedInput, TopicRefusedPrompt

    prompt = TopicRefusedPrompt()
    rows = []
    for row in out_of_scope_rows:
        question = row["question"]
        confidence = rag.scope_confidence(question)
        answer = generator.generate(question, k=k)
        gated = answer.answer == OUT_OF_SCOPE_REFUSAL
        rows.append({"question": question, "answer": answer.answer, "scope_confidence": confidence, "gated": gated})

    async def _judge_ungated() -> None:
        for row in rows:
            if row["gated"]:
                row["refused"] = True  # the gate's fixed message is a refusal by construction
                continue
            data = TopicRefusedInput(user_input=f"Human: {row['question']}\nAI: {row['answer']}", topic=row["question"])
            row["refused"] = (await prompt.generate(data=data, llm=llm)).refused_to_answer

    asyncio.run(_judge_ungated())

    n = len(rows)
    gated_count = sum(row["gated"] for row in rows)
    ungated = [row for row in rows if not row["gated"]]
    mean_scores = {
        "retrieval_scope_confidence": sum(row["scope_confidence"] for row in rows) / n if n else float("nan"),
        "gated_by_retrieval_confidence_rate": gated_count / n if n else float("nan"),
        "generation_refusal_rate": (
            sum(row["refused"] for row in ungated) / len(ungated) if ungated else float("nan")
        ),
        "out_of_scope_refusal_rate": sum(row["refused"] for row in rows) / n if n else float("nan"),
    }
    nan_counts = {"generation_refusal_rate": 0 if ungated else 1}
    return RagasResult(mean_scores=mean_scores, sample_scores=rows, nan_counts=nan_counts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG generation with RAGAS and log to MLflow.")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--golden", type=Path, default=_DATASETS / "golden_set_v1.jsonl")
    parser.add_argument("--out-of-scope", type=Path, default=_DATASETS / "out_of_scope_v1.jsonl")
    parser.add_argument("--persist-dir", default="./chroma_db", help="Chroma store with the real corpus")
    parser.add_argument("--collection", default="aml_corpus")
    parser.add_argument("--bm25-weight", type=float, default=0.0, help="BM25 weight for hybrid search (0 = pure vector)")
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="sentence-transformers model id (default from RagConfig / RAG_EMBEDDING_MODEL env var)",
    )
    parser.add_argument("--experiment", default="rag-ragas")
    parser.add_argument("--results-dir", type=Path, default=_BACKEND / "eval_results")
    parser.add_argument("--limit", type=int, default=None, help="Cap questions per set (bounded runs)")
    parser.add_argument("--skip-topic", action="store_true")
    args = parser.parse_args(argv)

    golden = _load_jsonl(args.golden)
    out_of_scope = _load_jsonl(args.out_of_scope)
    if args.limit:
        golden = golden[: args.limit]
        out_of_scope = out_of_scope[: args.limit]

    rag_config = RagConfig(
        persist_dir=args.persist_dir,
        collection_name=args.collection,
        bm25_weight=args.bm25_weight,
        **({"embedding_model": args.embedding_model} if args.embedding_model else {}),
    )
    # gen_config's own field default only sees RAG_EMBEDDING_MODEL (the env var); --embedding-model
    # can override rag_config's embedder independently of that env var, so the scope-gate default
    # must be resolved from rag_config's actual embedding_model, not gen_config's own default.
    gen_config = GenerationConfig(scope_gate_threshold=resolve_scope_gate_threshold(rag_config.embedding_model))
    rag = build_rag(rag_config)  # real, already-ingested corpus — no ingestion here
    generator = build_answer_generator(rag, gen_config)

    n_chunks, chunk_style = _describe_store(rag)
    if n_chunks == 0:
        parser.error(
            f"collection {args.collection!r} in {args.persist_dir} is empty — "
            "ingest the corpus first (or pass --collection/--persist-dir)."
        )
    print(
        f"Active config: collection={args.collection!r} @ {args.persist_dir} | "
        f"{n_chunks} chunks ({chunk_style} chunking) | bm25_weight={args.bm25_weight} | "
        f"k={args.k} | generator={gen_config.model} | scope_gate={gen_config.scope_gate_threshold} | "
        f"embedding_model={rag_config.embedding_model!r}"
    )

    llm, judge_model = _build_ragas_llm(gen_config)
    _warn_if_self_eval(judge_model, gen_config.model)
    embeddings = _build_ragas_embeddings(rag_config.embedding_model)

    # Unique per-run tag (k + UTC timestamp) so runs don't overwrite each other.
    run_tag = f"k{args.k}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    core4 = _run_core4(generator, args.k, golden, llm, embeddings)
    run_files = _persist(core4, f"core4_per_query_{run_tag}", args.results_dir)

    topic = None
    refusal = None
    in_scope = []
    if not args.skip_topic:
        in_scope = [r for r in golden if r.get("category") != "no_answer"]
        topic = _run_topic_adherence(generator, args.k, in_scope, llm)
        run_files += _persist(topic, f"topic_adherence_per_query_{run_tag}", args.results_dir)
        refusal = _run_out_of_scope(rag, generator, args.k, out_of_scope, llm)
        run_files += _persist(refusal, f"out_of_scope_refusal_per_query_{run_tag}", args.results_dir)

    categories = {row["question"]: row.get("category", "?") for row in golden}
    header = (
        f"collection={args.collection!r} @ {args.persist_dir} | {n_chunks} chunks "
        f"({chunk_style} chunking) | bm25_weight={args.bm25_weight} | k={args.k} | "
        f"generator={gen_config.model} | judge={judge_model} (temp {_JUDGE_TEMPERATURE}) | "
        f"run_tag={run_tag}"
    )
    sections = [
        (
            f"Core-4 generation metrics over {len(golden)} golden questions (k={args.k})",
            core4,
            ["faithfulness", "answer_relevancy", "context_precision", "context_recall"],
        )
    ]
    if topic is not None:
        sections.append(
            (
                f"Topic adherence over {len(in_scope)} in-scope questions",
                topic,
                ["topic_adherence_precision", "topic_adherence_recall", "topic_adherence_f1"],
            )
        )
    if refusal is not None:
        sections.append(
            (
                f"Out-of-scope behavior over {len(out_of_scope)} queries",
                refusal,
                [
                    "retrieval_scope_confidence",
                    "gated_by_retrieval_confidence_rate",
                    "generation_refusal_rate",
                    "out_of_scope_refusal_rate",
                ],
            )
        )
    layer_summary = build_layer_summary(core4, topic, refusal, len(golden), len(in_scope), len(out_of_scope))
    report = build_report(header, sections, categories, layer_summary=layer_summary)
    report_path = args.results_dir / f"report_{run_tag}.md"
    report_path.write_text(report, encoding="utf-8")
    run_files.append(report_path)

    mlflow.set_tracking_uri(f"sqlite:///{_BACKEND / 'mlflow.db'}")
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run():
        mlflow.log_params(
            {
                "k": args.k,
                "n_golden": len(golden),
                "n_out_of_scope": len(out_of_scope),
                "generator_model": gen_config.model,
                "generator_temperature": gen_config.temperature,
                "judge_model": judge_model,
                "judge_temperature": _JUDGE_TEMPERATURE,
                "embedding_model": rag_config.embedding_model,
                "ragas_version": ragas.__version__,
                "golden_set": args.golden.name,
                "collection": args.collection,
                "bm25_weight": args.bm25_weight,
                "n_chunks": n_chunks,
                "chunk_style": chunk_style,
                "scope_gate_threshold": gen_config.scope_gate_threshold,
            }
        )
        mlflow.log_metrics(core4.mean_scores)
        mlflow.log_metrics({f"{k}_nan": v for k, v in core4.nan_counts.items()})
        mlflow.log_dict({"samples": core4.sample_scores}, "core4_sample_scores.json")
        if topic is not None:
            mlflow.log_metrics(topic.mean_scores)
            mlflow.log_metrics({f"{k}_nan": v for k, v in topic.nan_counts.items()})
            mlflow.log_dict({"samples": topic.sample_scores}, "topic_adherence_sample_scores.json")
        if refusal is not None:
            mlflow.log_metrics(refusal.mean_scores)
            mlflow.log_dict({"samples": refusal.sample_scores}, "out_of_scope_refusal_samples.json")
        for path in run_files:  # only this run's files, not the whole accumulating dir
            mlflow.log_artifact(str(path), artifact_path="eval_results")

    print(f"\nJudge model: {judge_model} (temp {_JUDGE_TEMPERATURE}) | Generator: {gen_config.model}")
    _print_summary(f"Core-4 generation metrics over {len(golden)} golden questions (k={args.k})", core4)
    if topic is not None:
        _print_summary(f"Topic adherence over {len(in_scope)} in-scope questions", topic)
    if refusal is not None:
        _print_summary(f"Out-of-scope behavior over {len(out_of_scope)} queries", refusal)
    print()
    print(report)
    print(f"Per-query results written to {args.results_dir} (detail report: {report_path.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
