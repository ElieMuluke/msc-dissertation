"""Run RAGAS RAG-generation evaluation over the golden set and log results to MLflow.

    python -m app.evaluation.ragas_run --k 4
    python -m app.evaluation.ragas_run --k 4 --limit 6   # quick bounded run
    mlflow ui --backend-store-uri sqlite:///mlflow.db    # experiment: rag-ragas

Requires Ollama running. Answers are generated against the *real* ingested corpus (the
persisted Chroma store built from the JMLSG/FATF/sanctions PDFs), so the evaluation
exercises the actual retriever — the golden set's ground truths are grounded in that
corpus (see ``datasets/golden_set_v1.jsonl``).

Two evaluations are run and persisted:

- Core-4 generation metrics (faithfulness, answer relevancy, context precision/recall)
  over the golden set, using the ground-truth answer as the RAGAS ``reference``.
- TopicAdherence (precision/recall/F1) over in-scope golden questions plus deliberately
  out-of-scope queries (``datasets/out_of_scope_v1.jsonl``), scored against the KYC/AML
  ``REFERENCE_TOPICS`` — this measures whether the agent stays in scope and refuses
  off-topic asks.

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
import os
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
from app.generation import GenerationConfig, build_answer_generator
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


def _build_ragas_llm(config: GenerationConfig):
    """Wrap a local Ollama chat model as the RAGAS LLM judge (independent of the generator).

    The judge is a *different model* from answer generation to avoid self-evaluation bias:
    ``RAGAS_JUDGE_MODEL`` (default ``llama3.2:3b``, a different family than the ``qwen*``
    generator). Deterministic temperature and a high token cap keep the structured JSON that
    RAGAS metrics require well-formed and untruncated.

    Returns:
        A tuple ``(wrapped_llm, judge_model_name)`` so the caller can log which judge ran.
    """
    from langchain_ollama import ChatOllama
    from ragas.llms import LangchainLLMWrapper

    judge_model = os.getenv("RAGAS_JUDGE_MODEL", _DEFAULT_JUDGE_MODEL)
    chat = ChatOllama(
        model=judge_model,
        base_url=config.base_url,
        temperature=_JUDGE_TEMPERATURE,
        num_predict=2048,
        num_ctx=config.num_ctx,
        keep_alive=config.keep_alive,
    )
    return LangchainLLMWrapper(chat), judge_model


def _build_ragas_embeddings(embedding_model: str):
    """Wrap the local HuggingFace embedding model for RAGAS metrics that need it."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    hf = HuggingFaceEmbeddings(model_name=embedding_model, encode_kwargs={"normalize_embeddings": True})
    return LangchainEmbeddingsWrapper(hf)


def _persist(result: RagasResult, name: str, results_dir: Path) -> None:
    """Write per-query results to ``<results_dir>/<name>.{csv,json}`` for inspection."""
    import pandas as pd

    results_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(result.sample_scores)
    df.to_csv(results_dir / f"{name}.csv", index=False)
    (results_dir / f"{name}.json").write_text(
        json.dumps(result.sample_scores, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


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


def _run_core4(generator, k, golden_rows, llm, embeddings) -> RagasResult:
    records = []
    for row in golden_rows:
        answer = generator.generate(row["question"], k=k)
        records.append(RagasRecord(row["question"], answer.answer, answer.contexts, row["ground_truth"]))
    dataset = to_evaluation_dataset(records)
    return run_ragas(dataset, llm=llm, embeddings=embeddings, metrics=default_metrics())


def _run_topic_adherence(generator, k, in_scope_rows, out_of_scope_rows, llm) -> RagasResult:
    from ragas import EvaluationDataset

    samples = []
    for row in in_scope_rows:
        answer = generator.generate(row["question"], k=k)
        samples.append(to_topic_adherence_sample(row["question"], answer.answer))
    for row in out_of_scope_rows:
        answer = generator.generate(row["question"], k=k)
        samples.append(to_topic_adherence_sample(row["question"], answer.answer))
    dataset = EvaluationDataset(samples=samples)
    return run_ragas(dataset, llm=llm, metrics=topic_adherence_metrics())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG generation with RAGAS and log to MLflow.")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--golden", type=Path, default=_DATASETS / "golden_set_v1.jsonl")
    parser.add_argument("--out-of-scope", type=Path, default=_DATASETS / "out_of_scope_v1.jsonl")
    parser.add_argument("--persist-dir", default="./chroma_db", help="Chroma store with the real corpus")
    parser.add_argument("--collection", default="aml_corpus")
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

    rag_config = RagConfig(persist_dir=args.persist_dir, collection_name=args.collection)
    gen_config = GenerationConfig()
    rag = build_rag(rag_config)  # real, already-ingested corpus — no ingestion here
    generator = build_answer_generator(rag, gen_config)

    llm, judge_model = _build_ragas_llm(gen_config)
    _warn_if_self_eval(judge_model, gen_config.model)
    embeddings = _build_ragas_embeddings(rag_config.embedding_model)

    core4 = _run_core4(generator, args.k, golden, llm, embeddings)
    _persist(core4, "core4_per_query", args.results_dir)

    topic = None
    if not args.skip_topic:
        in_scope = [r for r in golden if r.get("category") != "no_answer"]
        topic = _run_topic_adherence(generator, args.k, in_scope, out_of_scope, llm)
        _persist(topic, "topic_adherence_per_query", args.results_dir)

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
            }
        )
        mlflow.log_metrics(core4.mean_scores)
        mlflow.log_metrics({f"{k}_nan": v for k, v in core4.nan_counts.items()})
        mlflow.log_dict({"samples": core4.sample_scores}, "core4_sample_scores.json")
        if topic is not None:
            mlflow.log_metrics(topic.mean_scores)
            mlflow.log_metrics({f"{k}_nan": v for k, v in topic.nan_counts.items()})
            mlflow.log_dict({"samples": topic.sample_scores}, "topic_adherence_sample_scores.json")
        mlflow.log_artifacts(str(args.results_dir), artifact_path="eval_results")

    print(f"\nJudge model: {judge_model} (temp {_JUDGE_TEMPERATURE}) | Generator: {gen_config.model}")
    _print_summary(f"Core-4 generation metrics over {len(golden)} golden questions (k={args.k})", core4)
    if topic is not None:
        _print_summary(f"Topic adherence over {len(golden)} in-scope + {len(out_of_scope)} out-of-scope", topic)
    print(f"\nPer-query results written to {args.results_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
