"""Run RAGAS RAG-generation evaluation and log results to local MLflow.

    python -m app.evaluation.ragas_run --k 4
    mlflow ui --backend-store-uri sqlite:///mlflow.db   # experiment: rag-ragas

Requires Ollama running (used both to generate answers and as the RAGAS LLM judge).
The corpus is ingested into a throwaway store, so the live database is never touched.

RAGAS defaults to OpenAI; this runner wires it to the local stack instead:
``langchain_ollama.ChatOllama`` (via :class:`GenerationConfig`) wrapped in
``ragas.llms.LangchainLLMWrapper``, and the same ``all-MiniLM-L6-v2`` HuggingFace
embeddings used for retrieval, wrapped in ``ragas.embeddings.LangchainEmbeddingsWrapper``.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from app.evaluation import _ragas_compat  # noqa: F401 - side effect: must precede `import ragas`

import mlflow
import ragas

from app.evaluation.ragas_eval import RagasRecord, run_ragas, to_evaluation_dataset
from app.generation import GenerationConfig, build_answer_generator
from app.ingestion.rag import Document, DocumentType, RagConfig, build_rag

_BACKEND = Path(__file__).resolve().parents[2]
_DATASETS = Path(__file__).resolve().parent / "datasets"


def _load_corpus(path: Path) -> list[Document]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [Document(r["id"], r["text"], DocumentType(r["doc_type"]), r.get("metadata", {})) for r in rows]


def _load_questions(path: Path) -> list[dict]:
    """Load ``{"question": ..., "reference": ...}`` rows from a JSONL file."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_ragas_llm(config: GenerationConfig):
    """Wrap a local Ollama chat model as the RAGAS LLM judge.

    The judge is configured independently of answer generation: RAGAS metrics require the
    model to emit well-formed structured JSON, so it uses a stronger default model
    (``RAGAS_JUDGE_MODEL``, default ``qwen3.5:4b``), a deterministic temperature, and a
    high token cap so the structured output is never truncated (which would fail parsing).
    """
    import os

    from langchain_ollama import ChatOllama
    from ragas.llms import LangchainLLMWrapper

    chat = ChatOllama(
        model=os.getenv("RAGAS_JUDGE_MODEL", "qwen3.5:4b"),
        base_url=config.base_url,
        temperature=0.0,
        num_predict=2048,
        num_ctx=config.num_ctx,
        keep_alive=config.keep_alive,
    )
    return LangchainLLMWrapper(chat)


def _build_ragas_embeddings(embedding_model: str):
    """Wrap the local HuggingFace embedding model for RAGAS metrics that need it."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    hf = HuggingFaceEmbeddings(model_name=embedding_model, encode_kwargs={"normalize_embeddings": True})
    return LangchainEmbeddingsWrapper(hf)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG generation with RAGAS and log to MLflow.")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--corpus", type=Path, default=_DATASETS / "ragas_corpus.json")
    parser.add_argument("--questions", type=Path, default=_DATASETS / "ragas_questions.jsonl")
    parser.add_argument("--experiment", default="rag-ragas")
    args = parser.parse_args(argv)

    corpus = _load_corpus(args.corpus)
    questions = _load_questions(args.questions)
    rag_config = RagConfig()
    gen_config = GenerationConfig()

    with tempfile.TemporaryDirectory() as tmp_dir:
        rag = build_rag(RagConfig(persist_dir=tmp_dir, collection_name="ragas_eval"))
        rag.ingest(corpus)
        generator = build_answer_generator(rag, gen_config)
        records = []
        for row in questions:
            answer = generator.generate(row["question"], k=args.k)
            records.append(RagasRecord(row["question"], answer.answer, answer.contexts, row["reference"]))

    dataset = to_evaluation_dataset(records)
    llm = _build_ragas_llm(gen_config)
    embeddings = _build_ragas_embeddings(rag_config.embedding_model)
    result = run_ragas(dataset, llm=llm, embeddings=embeddings)

    mlflow.set_tracking_uri(f"sqlite:///{_BACKEND / 'mlflow.db'}")
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run():
        mlflow.log_params(
            {
                "k": args.k,
                "n_questions": len(questions),
                "model": gen_config.model,
                "embedding_model": rag_config.embedding_model,
                "ragas_version": ragas.__version__,
            }
        )
        mlflow.log_metrics(result.mean_scores)
        mlflow.log_dict({"samples": result.sample_scores}, "ragas_sample_scores.json")

    print(f"RAGAS evaluation over {len(questions)} questions (k={args.k}):")
    for name, value in result.mean_scores.items():
        print(f"  {name}: {value:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
