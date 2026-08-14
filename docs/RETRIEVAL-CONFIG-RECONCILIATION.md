# Retrieval configuration reconciliation

**Status:** evidence gathered, replacement collections built and verified. **The flip has
not been performed** — `backend/app/deps.py` still points at the live `aml_sections_c`.
The owner must run §6 after the Component-2 sweeps finish.

**Date of investigation:** 2026-08-14. All measurements below were taken by direct
read-only inspection of `backend/chroma_db/chroma.sqlite3` and by CPU-only re-execution of
the ingestion pipeline. No GPU, no LLM, no writes to any existing collection.

---

## 1. The problem in one line

Chapter 4 Tables 2 and 3 report retrieval metrics measured on **2,569 section chunks** in a
collection named `aml_sections_c`. The collection on disk under that name today holds
**3,193 page-window chunks** from a **different document set**, produced by a **different
chunker**. The live app serves the latter. **0 of 57** golden-set queries reproduce the
retrievals the adopted run recorded.

---

## 2. Measured evidence

### 2.1 What is actually on disk (`backend/chroma_db/chroma.sqlite3`)

| Collection | live chunks | Ch.4 Table 2 figure | id shape | `section` metadata | ingested (UTC) |
|---|---|---|---|---|---|
| `aml_corpus` | 3,114 | 3,015 | `-p<page>#<i>` | 99 rows only | 2026-07-16T15:39 (3,015) + 2026-08-06T15:52 (99 OFSI) |
| `aml_sections_a` | 3,121 | 3,121 | `-s<n>` | all | 2026-07-16T15:42 |
| `aml_sections_b` | 3,220 | 3,220 | `-s<n>` | all | 2026-07-16T15:46 |
| **`aml_sections_c`** (served by the app) | **3,193** | **2,569** | **`-p<page>#<i>`** | **none (0 rows)** | **2026-07-17T17:46:53 – 17:47:20** |

Two collections disagree with the dissertation. `aml_sections_a` and `aml_sections_b` are
intact.

### 2.2 Timeline — the re-ingest happened after the sweep, not before

| UTC | Event | Evidence |
|---|---|---|
| 2026-07-16T10:25:40 | first `aml_sections_c` sweep run, **2,569 chunks, "section chunking"** | `eval_results/report_k4_20260716T102540Z.md` |
| 2026-07-16T18:01:29 | **the adopted run**: `aml_sections_c`, 2,569 chunks, bm25_weight 0.4 — the source of Table 3 | `eval_results/report_k4_20260716T180129Z.md` |
| 2026-07-17T03:37:12 | last `aml_sections_c` sweep run, still **2,569 chunks, "section chunking"** | `report_k4_20260717T033712Z.md` |
| 2026-07-17T04:40:06 | last sweep run of any collection (`aml_sections_a`) | `report_k4_20260717T044006Z.md` |
| **2026-07-17T17:46:53** | **`aml_sections_c` overwritten with a page-window ingest of 7 PDFs** | `ingested_at` metadata in the store |

The overwrite is **13 h 06 m after the last sweep run of any collection**, and **14 h 09 m
after the last `aml_sections_c` run**. (An earlier note in `docs/SESSION-HANDOFF.md` §2.5
says "~11 h" — that figure is wrong; the measured gaps are the two above.)

The 2,569-chunk build of `aml_sections_c` no longer exists on disk. It was destroyed by the
overwrite. Everything downstream of Table 3 rests on the reports in `backend/eval_results/`
and on the reproduction in §4.

### 2.3 The evaluated configuration, established from source

Reconstructed from `backend/app/deps.py`, `backend/app/ingestion/rag/{config,cli,section_chunking,rag,hybrid}.py`,
`docs/PRD-B-production.md` and the sweep report headers:

| Parameter | Evaluated value | Where it is fixed |
|---|---|---|
| chunker | `section` (structure-aware) | `RagConfig.chunker="section"`, `cli.load_pdf_sections` |
| `parent_context` | `True` (`[<doc title> — <heading>] ` prefix) | Table 2 row for `aml_sections_c` |
| `chunk_size` / `chunk_overlap` | `0` / n/a — sections stored as produced | `cli.main`: `RagConfig(**overrides, chunk_size=0)` when `chunker=="section"` |
| `max_chunk_chars` | **2,200** | `cli._resolve_max_chunk_chars` = `512 × 1100 / 256`; bge reports `max_seq_length=512` (measured) |
| embedding model | `BAAI/bge-small-en-v1.5` (384-dim) | `deps.py::_RAG_CONFIG` |
| distance | `cosine` | `RagConfig.distance`; `collection_metadata.hnsw:space='cosine'` in the store |
| `bm25_weight` | `0.4` (adopted; sweep covered 0.0–1.0) | `deps.py::_RAG_CONFIG`, report headers |
| `k` | 4 | report headers |
| scope gate threshold | 0.638 (bge-specific) | `resolve_scope_gate_threshold` |
| source documents | **5 PDFs** (below) | Table 2: "the same five source PDFs" |

The 2,569 figure is **not** a corpus difference from `aml_sections_b`'s 3,220 — the same
five PDFs and the same chunker produce both. The count falls because
`_resolve_max_chunk_chars` scales the chunk ceiling to the embedder's window: MiniLM's
256-token window gives 1,100 chars, bge's 512-token window gives 2,200 chars, so sections
are sub-split half as often. This is confirmed by measurement in §4.

### 2.4 Document set: evaluated vs deployed

Per-source chunk counts, measured.

| Source PDF | Evaluated (rebuilt, §3) | Deployed `aml_sections_c` |
|---|---|---|
| `JMLSG-Guidance-Part-II_June-2023_updated-Dec-2025.pdf` | 1,037 | 1,176 |
| `JMLSG-Guidance-Part-I_June-2023-updated-Aug-2025.pdf` | 679 | 785 |
| `FATF Recommendations 2012.pdf.coredownload.inline.pdf` | 379 | 531 |
| `Assessment-Follow-Up-ICRG-Procedures-2022.pdf.coredownload.inline.pdf` | 253 | 279 |
| `Universal-Procedures-2023.pdf.coredownload.inline.pdf` | 221 | 244 |
| `4th-Round-Ratings.pdf.coredownload.inline.pdf` | — **not in sweep** | 168 |
| `Handout-5th-Round-Methodology.pdf.coredownload.pdf` | — **not in sweep** | 10 |
| OFSI *UK financial sanctions: general guidance* (Jan 2026) | — (post-dates the sweep) | **absent** |
| **Total** | **2,569** | **3,193** |

The deployed per-PDF counts for the five sweep documents (1,176 / 785 / 531 / 279 / 244 =
3,015) are **identical to `aml_corpus`'s page-window counts**, which independently confirms
that `aml_sections_c` was rebuilt with the `fixed` page-window chunker, not the section
chunker.

### 2.5 Is OFSI genuinely missing? Yes — and it was never in the evaluated set either

- OFSI's 99 chunks exist in **`aml_corpus` only**, ids `ofsi-general-guidance-jan2026-00…98`,
  `ingested_at = 2026-08-06T15:52:59Z`, `source = "OFSI UK financial sanctions: general
  guidance (Jan 2026)"`, `file = "Downloads/data/OFSI/UK-financial-sanctions-general-guidance-Jan-2026.html"`.
- They are **absent from `aml_sections_c`**, the collection the app serves. So the live
  system cannot retrieve the document rulebook rule **SAN-1** cites. Confirmed.
- They are also absent from the **evaluated** configuration, necessarily: OFSI was ingested
  2026-08-06, three weeks **after** the 2026-07-16/17 sweep. Chapter 4's numbers were never
  measured with OFSI in the corpus.

This creates a genuine conflict, and it must not be papered over: *the configuration Table 3
validated cannot satisfy SAN-1, and a configuration that satisfies SAN-1 is not the one
Table 3 validated.* §3 therefore builds both, and §4 quantifies the cost of adding OFSI.

Note also that the OFSI chunks were ingested from the **HTML** rendering, not the PDF, by an
ad-hoc script that was **never committed** (no such file exists in any commit in
`git log --all`). Their text is therefore only recoverable from the store itself, which is
how §3 obtains it.

### 2.6 Config default drift

- `RagConfig` defaults (`backend/app/ingestion/rag/config.py`) are **unchanged** and generic:
  `aml_corpus`, `fixed`, `all-MiniLM-L6-v2`, `chunk_size=900`, `bm25_weight=0.0`,
  `parent_context=False`. No drift here; these are library defaults, deliberately not the
  production values.
- `deps.py::_RAG_CONFIG` matches the evaluated config on **embedder (bge-small)**,
  **bm25_weight (0.4)** and **collection name (`aml_sections_c`)**. The code is correct.
  **Only the collection's contents are wrong.**
- `deps.py` does not override `persist_dir`, so it inherits `RagConfig`'s `./chroma_db`.
  This is why the flip in §6 needs a one-line code change rather than an env var alone.
- `docs/rag.md` is stale: it states the production config is `aml_sections_b` /
  `bm25_weight=0.3`. It has been superseded by `deps.py` and should be corrected (already
  logged in `docs/SESSION-HANDOFF.md` §2.6).

---

## 3. What was built

Both collections live in a **new persist directory** — nothing existing was written.

```
backend/chroma_eval/          <- NEW store (already matched by .gitignore's `chroma_eval/`)
  ├─ aml_sections_eval        <- 2,569 chunks — exact reproduction of the evaluated config
  └─ aml_sections_eval_ofsi   <- 2,668 chunks — the same 2,569 + the 99 OFSI chunks
```

Build parameters (identical for both, and identical to §2.3):
`chunker=section`, `parent_context=True`, `chunk_size=0`, `max_chunk_chars=2200`,
`embedding_model=BAAI/bge-small-en-v1.5`, `distance=cosine`, `bm25_weight=0.4`.

Source PDFs were read from `/mnt/c/Users/u5749933/Downloads/data/{JMLSG,FATF}/`. All five
were present; nothing was substituted. The 99 OFSI chunks were lifted **verbatim** (text and
metadata) out of `aml_corpus` via a read-only SQLite connection and re-embedded with bge —
their text is byte-identical to what was ingested on 2026-08-06.

Compute: CPU only (`CUDA_VISIBLE_DEVICES=""`, `OMP_NUM_THREADS=4`; the process asserted
`torch.cuda.is_available() == False` before loading the model, and reported `device: cpu`).
GPU memory was 36,638 MiB before and 36,638 MiB after, with the same two compute PIDs
(77260, 77264) throughout — the running sweep was not disturbed.

---

## 4. Verification results

### 4.1 Chunk count — exact

| Collection | Target | Measured | Residual |
|---|---|---|---|
| `aml_sections_eval` | 2,569 (Table 2) | **2,569** | **0** |
| `aml_sections_eval_ofsi` | 2,569 + 99 | **2,668** | **0** |

Per-source counts are in §2.4. The reproduction is exact at the whole-collection level and
at the per-document level, which confirms the parameter set in §2.3 is the one that produced
Table 2's 2,569 — including the `max_chunk_chars=2200` inference, which was the only
non-obvious parameter.

### 4.2 Retrieval reproduction against the adopted run

Every one of the 57 golden-set questions was re-run at `bm25_weight=0.4, k=4` and its top-4
contexts compared, text-for-text, against `retrieved_contexts` recorded in
`backend/eval_results/core4_per_query_k4_20260716T180129Z.json` — the per-query artefact of
**the exact run Table 3 reports**. No LLM was involved; this compares retrieval only.

| Collection | Identical top-4, same order | Individual contexts recovered | Mean Jaccard |
|---|---|---|---|
| **`aml_sections_eval`** | **56 / 57 (98.2 %)** | **227 / 228 (99.6 %)** | **0.993** |
| `aml_sections_eval_ofsi` | 48 / 57 (84.2 %) | 219 / 228 (96.1 %) | 0.944 |
| `aml_sections_c` (live, as deployed) | **0 / 57 (0.0 %)** | **0 / 228 (0.0 %)** | **0.000** |

**Reading of these numbers.**

- `aml_sections_eval` **is** the evaluated configuration. The single discrepancy is on
  *"What is the travel rule for wire transfers?"*, where one rank-4 context differs: the
  rebuild returns a *Wire Transfer Regulation* section in place of an *electronic vouchers /
  Definitions* section. This is a near-tie at the fusion cutoff, not a configuration
  difference — and the rebuild's pick is the more on-topic of the two. The remaining 3 of
  that query's 4 contexts, and all 4 contexts of the other 56 queries, match exactly.
- The live collection reproduces **nothing**. This is the quantitative statement of the
  defensibility problem: it is not a slightly-different index, it is a different retrieval
  surface with no chunk in common.

### 4.3 Cost of adding OFSI — measured, not assumed

Adding the 99 OFSI chunks perturbs 9 of the 57 golden queries. The perturbation splits into
two mechanisms, both worth stating plainly:

1. **OFSI legitimately outranking (3 queries)** — *"penalties under the US Bank Secrecy
   Act"*, *"OFAC 50 percent rule"*, *"maximum fine under the UK MLRs 2017"*. All three are
   penalty/fine questions; OFSI §7.3.4–7.3.5 (*Monetary penalties*) displaces weaker JMLSG
   and FATF-ICRG contexts. These are arguably **better** retrievals — but they are outside
   what Table 3 measured.
2. **BM25 corpus statistics shifting (6 queries)** — 3 pure reorderings and 3 content
   changes in which **no OFSI chunk appears at all**. `Bm25Index` (`hybrid.py`) is built over
   the whole collection, so adding 99 documents changes IDF and average document length for
   every query. Hybrid retrieval is corpus-relative; a corpus addition is never inert.

So `aml_sections_eval_ofsi` is **not** the configuration Table 3 measured, and must not be
described as such. It is the evaluated configuration plus a documented, quantified addition.

### 4.4 OFSI retrievability

On `aml_sections_eval_ofsi` (bm25 0.4, k=4), OFSI content is retrieved and dominant:

- *"Who does OFSI licence and when is a specific licence needed?"* → top-4 all OFSI
  (`…-69` §6.15 *Complying with a licence* @ 0.954, `…-50` §6.5 *Licensing overview* @ 0.928,
  `…-57` §6.9 *General licences* @ 0.799, `…-59` §6.10 *Applying for a specific licence* @ 0.678).
- *"asset freeze reporting obligations to OFSI"* → top-4 all OFSI (`…-40` §5.8 *Annual frozen
  assets review* @ 0.959, `…-41` §5.9 *Other reporting obligations* @ 0.622, `…-87` §7.2
  *Reporting a suspected breach* @ 0.515, `…-93` §7.3.5 @ 0.509).

The same queries against `aml_sections_eval` (no OFSI) return only JMLSG surrogates at
markedly lower scores (top hit 0.748 vs 0.954). **SAN-1 is servable from
`aml_sections_eval_ofsi` and is not servable from `aml_sections_eval` or from the live
`aml_sections_c`.**

### 4.5 Scope gate still calibrated

The gate threshold for bge-small is 0.638. Measured `scope_confidence`:

| Query | Kind | `aml_sections_eval` | `aml_sections_eval_ofsi` |
|---|---|---|---|
| "What are the FATF Recommendations?" | in-scope | 0.7289 | 0.7289 |
| "What is the capital of France?" | out-of-scope | 0.4910 | 0.4910 |
| "What are OFSI's financial sanctions licensing grounds?" | in-scope (sanctions) | 0.7437 | **0.8645** |

The gate separates correctly on both collections and no recalibration is implied. Adding
OFSI *raises* confidence on sanctions queries, which is the desired direction.
`scope_confidence` bypasses BM25 fusion, so it is unaffected by §4.3's mechanism 2.

---

## 5. Disclosure: one unintended side effect

To measure the live collection's 0/57 reproduction rate (§4.2, row 3), `build_rag` was
pointed at `backend/chroma_db` for read-only searches. Chroma has no read-only open mode —
`Chroma(...)` calls `get_or_create_collection`, which opens the database read-write. This
**moved the mtime** of `backend/chroma_db/chroma.sqlite3` from `2026-08-07 16:46:12` to
`2026-08-14 16:57:45`.

**No data changed.** Verified after the fact against the readings taken before any of this
work began: file size identical (112,652,288 bytes); the same 6 collections with the same
UUIDs and dimensions; `aml_corpus` 3,114 / `aml_sections_a` 3,121 / `aml_sections_b` 3,220 /
`aml_sections_c` 3,193; all 6 `collection_metadata` rows still `hnsw:space=cosine`;
`aml_sections_c`'s 7 per-source counts and all 7 `ingested_at` timestamps unchanged; no
collection created or removed. The mtime change is a SQLite open/WAL touch only.

---

## 6. What the owner must do AFTER the sweeps finish

Nothing below has been done. Steps 1–2 are the flip; steps 3–4 are the write-up obligations.

### Step 0 — decide which collection to deploy

| Choice | Defensibility |
|---|---|
| `aml_sections_eval` (2,569) | Exactly what Ch.4 measured. **SAN-1 cannot be served.** |
| `aml_sections_eval_ofsi` (2,668) | Serves SAN-1. Is the evaluated config **+ 99 documented chunks**; Ch.4 must say so (§4.3 supplies the measured perturbation). |

Recommended: **`aml_sections_eval_ofsi`**, with the §4.3 numbers disclosed in Ch.4 §4.2.5.
The alternative — deploying a rulebook whose SAN-1 citation is unretrievable — is the worse
defect.

### Step 1 — point the app at the new store

`backend/app/deps.py`, `_RAG_CONFIG` (line 33). `persist_dir` is currently not set and so
inherits `RagConfig`'s `./chroma_db`; it must be set. Change:

```python
_RAG_CONFIG = RagConfig(
    persist_dir=os.getenv("RAG_PERSIST_DIR", "./chroma_eval"),
    collection_name=os.getenv("RAG_COLLECTION_NAME", "aml_sections_eval_ofsi"),
    embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
    bm25_weight=float(os.getenv("RAG_BM25_WEIGHT", "0.4")),
)
```

Update the comment above it to cite this document. Do **not** touch
`RagConfig`'s own defaults — the CLI and tests rely on them staying generic.

### Step 2 — verify the flip, from `backend/`, with the venv

```bash
cd backend
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=4 ./.venv/bin/python -c "
from app.deps import get_rag
r = get_rag()
print('chunks:', len(r._store.get()['ids']))
print([ (round(h.score,3), h.id[:44]) for h in r.search('Who does OFSI licence and when is a specific licence needed?', k=4) ])
"
```

Expect `chunks: 2668` and four `ofsi-general-guidance-jan2026-*` ids. Then start the API and
confirm `GET /health` reports the database up, and that `GET /rag/documents` lists six
sources including the OFSI entry.

### Step 3 — leave the old collection alone

Do **not** delete or overwrite `aml_sections_c`. It is the evidence that the discrepancy was
real. `backend/chroma_db/` stays as-is; `backend/chroma_eval/` becomes the served store.
(Both are gitignored, so neither is in version control — back up `chroma_eval/` alongside
`chroma_db/` when archiving.)

### Step 4 — the write-up

1. **Ch.4 §4.2.5 (or a footnote to Table 3)** must state that the deployed store was rebuilt
   on 2026-08-14 to restore the evaluated configuration, that the reproduction is exact at
   2,569 chunks and 98.2 % identical on top-4 retrievals over the 57-question golden set,
   and — if `aml_sections_eval_ofsi` is deployed — that 99 OFSI chunks were added after the
   sweep with the §4.3 perturbation. Cite this file.
2. `docs/rag.md` "Production config" is stale (`aml_sections_b` / `0.3`) and must be brought
   in line with `deps.py` — see §2.6.
3. `docs/SESSION-HANDOFF.md` §2.5's "~11 h" should be corrected to the measured 13 h 06 m
   (last sweep run) / 14 h 09 m (last `aml_sections_c` run), and §2.5's open question "which
   embedder produced those vectors" is now moot for the deployed path, since the deployed
   path moves to a store whose provenance is documented here.
4. Ch.4 Table 2's `aml_corpus` figure of 3,015 no longer matches disk either (3,114 since the
   OFSI addition). `aml_corpus` is not served by the app, so this is a lesser issue, but the
   3,015 figure should be labelled "as evaluated, 2026-07-16".

---

## Appendix — reproducing the rebuild

The five sweep PDFs must be staged in one directory, isolated from the two FATF PDFs that
were *not* in the sweep (`4th-Round-Ratings`, `Handout-5th-Round-Methodology`), because
`load_pdf_sections` globs `*.pdf` over whatever directory it is given:

```bash
D=/mnt/c/Users/u5749933/Downloads/data
mkdir -p /tmp/sweep_pdfs && cd /tmp/sweep_pdfs
ln -sf "$D/JMLSG/JMLSG-Guidance-Part-I_June-2023-updated-Aug-2025.pdf" .
ln -sf "$D/JMLSG/JMLSG-Guidance-Part-II_June-2023_updated-Dec-2025.pdf" .
ln -sf "$D/FATF/FATF Recommendations 2012.pdf.coredownload.inline.pdf" .
ln -sf "$D/FATF/Assessment-Follow-Up-ICRG-Procedures-2022.pdf.coredownload.inline.pdf" .
ln -sf "$D/FATF/Universal-Procedures-2023.pdf.coredownload.inline.pdf" .
```

Then, from `backend/`, CPU-only:

```bash
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=4 ./.venv/bin/python -c "
from app.ingestion.rag import build_rag
from app.ingestion.rag.config import RagConfig
from app.ingestion.rag.cli import _resolve_max_chunk_chars
from app.ingestion.rag.section_chunking import load_pdf_sections
cfg = RagConfig(persist_dir='./chroma_eval', collection_name='aml_sections_eval',
                embedding_model='BAAI/bge-small-en-v1.5', distance='cosine',
                chunk_size=0, bm25_weight=0.4, chunker='section', parent_context=True)
rag = build_rag(cfg)
docs = load_pdf_sections('/tmp/sweep_pdfs', parent_context=True,
                         max_chunk_chars=_resolve_max_chunk_chars(rag))
print(len(docs))          # -> 2569
rag.ingest(docs)
"
```

For the `+OFSI` variant, ingest the same `docs` into collection `aml_sections_eval_ofsi`,
then additionally ingest the 99 OFSI chunks read out of `aml_corpus` (segment
`fd14f200-ddd3-47ea-95ef-36386797ec32`, rows whose `source` metadata starts with `OFSI`),
preserving each chunk's `embedding_id` as the `Document.id` and its `chroma:document` value
as the text.
