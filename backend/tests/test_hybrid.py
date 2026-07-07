"""Unit tests for BM25 index and hybrid score fusion (pure logic, no Chroma/embedder)."""

from __future__ import annotations

from app.ingestion.rag.hybrid import Bm25Index, fuse


def _index():
    return Bm25Index(
        ids=["a", "b", "c"],
        texts=[
            "tipping off an investigation is prohibited",
            "customer due diligence requirements for banks",
            "wire transfer originator information travel rule",
        ],
        metadatas=[{"doc_type": "policy"}, {"doc_type": "policy"}, {"doc_type": "action"}],
    )


def test_bm25_ranks_exact_term_match_first():
    scores = _index().scores("tipping off")
    assert max(scores, key=scores.get) == "a"


def test_bm25_where_filter_restricts_candidates():
    scores = _index().scores("wire transfer travel rule", where={"doc_type": "policy"})
    assert "c" not in scores


def test_bm25_empty_index_returns_nothing():
    assert Bm25Index([], [], []).scores("anything") == {}


def test_fuse_weight_0_is_pure_vector_order():
    top = fuse({"a": 0.9, "b": 0.5}, {"b": 10.0}, bm25_weight=0.0, k=2)
    assert [cid for cid, _ in top] == ["a", "b"]


def test_fuse_weight_1_is_pure_bm25_order():
    top = fuse({"a": 0.9, "b": 0.5}, {"b": 10.0, "a": 1.0}, bm25_weight=1.0, k=2)
    assert [cid for cid, _ in top] == ["b", "a"]


def test_fuse_blends_union_of_candidates():
    # "c" is BM25-only; with an even split it must be able to beat a weak vector hit
    top = fuse({"a": 0.9, "b": 0.2}, {"c": 5.0, "b": 1.0}, bm25_weight=0.5, k=3)
    ids = [cid for cid, _ in top]
    assert set(ids) == {"a", "b", "c"}
    assert ids[0] in {"a", "c"}  # both have one full-strength side


def test_fuse_k_truncates():
    assert len(fuse({"a": 1.0, "b": 0.5, "c": 0.1}, {}, 0.0, k=2)) == 2
