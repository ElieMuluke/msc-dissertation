# Tabular AML Dataset Ingestion

Loads the IBM/Kaggle **"HI-Large"** synthetic AML transaction dataset into SQLite via the
SQLAlchemy ORM. Lives in `backend/app/ingestion/tabular/`. Separate from the RAG feature
(`app/ingestion/rag/`) — this is structured, tabular data (accounts/transactions), not
documents for semantic search.

## What it ingests

Three HI-Large source files, each with a distinct shape:

| File | Format | Header / row shape |
| --- | --- | --- |
| `HI-Large_accounts.csv` | CSV, header row | `Bank Name, Bank ID, Account Number, Entity ID, Entity Name` |
| `HI-Large_Trans.csv` | CSV, header row | `Timestamp, From Bank, Account, To Bank, Account, Amount Received, Receiving Currency, Amount Paid, Payment Currency, Payment Format, Is Laundering` (11 fields; the header has two columns both literally named `Account` — pandas auto-dedupes the second to `Account.1`, see below) |
| `HI-Large_Patterns.txt` | plain text, no header | Same 11-field transaction rows as above, but grouped into blocks delimited by marker lines `BEGIN LAUNDERING ATTEMPT - <TYPE>` / `END LAUNDERING ATTEMPT - <TYPE>` (case-insensitive) |

`Timestamp` is `%Y/%m/%d %H:%M`. `Bank ID`/`Account Number` are kept as **strings** —
they carry leading zeros and must never be cast to int.

## ORM schema

Two tables only (`app/ingestion/tabular/models.py`):

- **`accounts`** — one row per `HI-Large_accounts.csv` line (`bank_name`, `bank_id`,
  `account_number`, `entity_id`, `entity_name`, `source_file`). `UniqueConstraint("bank_id",
  "account_number")` makes re-ingesting the same accounts file idempotent — a repeat upload
  inserts zero new rows instead of duplicating.
- **`transactions`** — one row per transaction, from *either* `HI-Large_Trans.csv` or
  `HI-Large_Patterns.txt`. Pattern rows reuse this table rather than a separate one (DRY: a
  pattern row *is* a transaction row with extra provenance) — they simply carry non-null
  `pattern_type` (the laundering-pattern label, e.g. `CYCLE`) and `pattern_group_id` (a
  counter incremented per `BEGIN` block). Ordinary transaction rows leave both `NULL`. No
  uniqueness constraint on `transactions`: legitimate duplicate transactions can occur, so
  ingestion there is a plain bulk insert.

**`is_laundering` (ground truth, never a detection feature).** Every transaction row carries
the dataset's `Is Laundering` 0/1 label in `is_laundering`. This column exists **only** to
score an AML detection system after the fact against known ground truth. It must never be
fed into a detection model as an input feature — doing so is data leakage (the target
leaking into its own predictors), since the label would not be available at prediction time
in a real deployment.

## Streaming + batched-insert design

HI-Large files can run to millions of rows, so two layers keep memory bounded
(`loaders.py` / `service.py`):

- **Loaders are pure generators** (`iter_accounts`, `iter_transactions`, `iter_patterns`):
  no DB session, no batching, no side effects beyond reading — pure core. `iter_accounts`/
  `iter_transactions` stream via `pandas.read_csv(..., chunksize=50_000)` (id-like columns
  read with `dtype=str` to preserve leading zeros; `iter_transactions` relies on pandas
  auto-deduping the header's two `Account` columns into `Account`/`Account.1` rather than
  positional parsing; `Timestamp` is parsed with `pd.to_datetime(..., format=...)` then
  converted back to a plain `datetime` via `.to_pydatetime()`), yielding one row dict per
  record regardless of chunk boundaries. `iter_patterns` is unchanged: still line-by-line
  with the stdlib `csv` module, because `HI-Large_Patterns.txt` mixes `BEGIN`/`END` marker
  lines in with data rows and isn't a plain CSV pandas can parse directly. All three keep
  the same public contract — yield one plain row `dict` at a time.
- **`count_rows(path, data_type) -> int`** (`loaders.py`) is a separate, lightweight line
  count — no parsing/type-conversion — used only to size progress-bar percentages (see
  below); it is not on the hot ingestion path.
- **The service owns the only side effects**: `TabularSystem` (`service.py`) chunks the
  streamed rows into lists of `TabularConfig.batch_size` (default 2000) via `_batched` and
  bulk-inserts each chunk in one `INSERT`. Accounts use `INSERT ... ON CONFLICT DO NOTHING`
  (SQLite upsert-ignore) on `(bank_id, account_number)` so re-ingesting is idempotent; the
  inserted-row count for that path is measured as the before/after `SELECT COUNT(*)` delta,
  since `executemany` affected-row counts aren't reliable across DBAPI/SQLAlchemy versions
  for `ON CONFLICT DO NOTHING`. Transactions/patterns use a plain insert and return the
  number of rows streamed. Every `ingest_*`/`ingest` method accepts an optional
  `on_batch: Callable[[int], None]`, invoked with the cumulative inserted/streamed row count
  after *every* batch — the service has no idea who's listening (a WebSocket, a log line,
  nothing); it just reports progress if asked (dependency inversion).
- **Commit cadence is decoupled from progress reporting**: `session.commit()` only runs
  every `_COMMIT_EVERY_N_BATCHES` (25) batches, not every batch — `on_batch` still fires
  every batch since it's a cheap in-memory callback, but `commit()` triggers a disk fsync,
  and doing that every 2000-row batch on a multi-million-row file meant tens of thousands
  of fsyncs dominating total ingest time. Batching commits ~25x cuts that overhead while
  still bounding how much work is lost if the process dies mid-file.
- **SQLite is switched to WAL** (`store.py`, `build_engine`): every new connection gets
  `PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL`. The SQLite default (rollback
  journal + `synchronous=FULL`) fsyncs the *entire* database file on every commit; WAL
  instead appends to a separate log file, which is far cheaper per commit and still safe
  for this single-writer local dev setup. No-op for `sqlite:///:memory:` (used by tests).
  Combined with the decoupled commit cadence above, ingesting the real 2.1M-row
  `HI-Large_accounts.csv` (147.7MB) dropped from ~7 minutes to ~2 minutes measured locally.

## Usage

### Python

```python
from app.ingestion.tabular import build_tabular_system, TabularDataType

tabular = build_tabular_system()  # default: sqlite:///./tabular_data_db.sqlite

tabular.ingest_accounts("HI-Large_accounts.csv", source_file="HI-Large_accounts.csv")
tabular.ingest_transactions("HI-Large_Trans.csv", source_file="HI-Large_Trans.csv")
tabular.ingest_patterns("HI-Large_Patterns.txt", source_file="HI-Large_Patterns.txt")

# Or dispatch by TabularDataType (what the API route does):
tabular.ingest(TabularDataType.ACCOUNTS, "HI-Large_accounts.csv")

# Optional progress callback, called with the cumulative row count per batch commit:
tabular.ingest_accounts("HI-Large_accounts.csv", on_batch=lambda n: print(f"{n} rows so far"))

tabular.counts()  # {"accounts": ..., "transactions": ...}
tabular.clear()   # delete all rows (transactions, then accounts)
```

### API

```bash
# from backend/
uvicorn app.main:app --reload   # http://localhost:8000
```

**`POST /tabular/ingest`** — multipart form:

| Field | Type | Notes |
| --- | --- | --- |
| `data_type` | `"accounts" \| "transactions" \| "patterns"` | Selects the table/loader. |
| `files` | one or more file uploads | `.csv` for `accounts`/`transactions`; `.csv` or `.txt` for `patterns`. Wrong extension → `400`. |

```bash
curl -X POST http://localhost:8000/tabular/ingest \
  -F "data_type=accounts" \
  -F "files=@HI-Large_accounts.csv"
```

Response (`TabularIngestResponse`):
```json
{"ingested": 1000, "data_type": "accounts"}
```

Per file, `/tabular/ingest` also broadcasts realtime progress frames over the shared `/ws`
WebSocket gateway (`app/realtime.py`), the same one `POST /rag/documents/pdf` uses:
`uploading` (10%) → `inserting` (10-99%, computed from `count_rows`'s total against the
cumulative count reported by the `on_batch` callback, pushed from the worker thread via
`asyncio.run_coroutine_threadsafe`) → `completed` (100%), or `error` with the failure
message if ingestion raises. `app.realtime.Status` includes `"inserting"` for this reason
(tabular ingestion inserts rows rather than parsing/vectorizing documents).

**`GET /tabular/counts`** — current ingested row counts, e.g. for a frontend
ingested-volumes display:

```json
{"accounts": 1000, "transactions": 50000}
```

**`DELETE /tabular/data`** — clear all ingested tabular data (transactions, then accounts).
Mirrors `DELETE /rag/documents`.

```json
{"status": "cleared"}
```

## Public API

Exported from `backend/app/ingestion/tabular/__init__.py`:

| Symbol | Purpose |
| --- | --- |
| `build_tabular_system(config=None) -> TabularSystem` | Wire an engine + sessionmaker into a ready system; creates tables if missing. |
| `TabularSystem.ingest(data_type, path, source_file=None, on_batch=None) -> int` | Dispatch to the right loader/table for `data_type`. |
| `TabularSystem.ingest_accounts/ingest_transactions/ingest_patterns(path, source_file=None, on_batch=None) -> int` | Per-file-type ingest methods. `on_batch`, if given, is called with the cumulative row count after each batch commits. |
| `TabularSystem.counts() -> dict[str, int]` | `{"accounts": ..., "transactions": ...}`. |
| `TabularSystem.clear() -> None` | Delete all rows from `transactions` then `accounts`. |
| `TabularDataType` | `ACCOUNTS` / `TRANSACTIONS` / `PATTERNS`. |
| `Account`, `Transaction` | ORM models (`models.py`). |
| `TabularConfig` | `db_url`, `batch_size`. |
| `iter_accounts`, `iter_transactions`, `iter_patterns` | Pure row-streaming generators (`loaders.py`), reusable outside the ORM service. |
| `count_rows(path, data_type) -> int` | Fast line-count (no parsing) matching what the corresponding `iter_*` would yield; used to size ingestion progress percentages. |

Routes (`app/api/routes/tabular.py`): `POST /tabular/ingest`, `GET /tabular/counts`,
`DELETE /tabular/data`.

## Design notes

- **Pure core / thin shell**: loaders (`loaders.py`) have no DB/session dependency; the only
  side effects (batching, inserts, commits) live in `service.py`. Loaders are unit-tested
  with plain temp files and no database at all.
- **Dependency inversion**: `TabularConfig` (db URL, batch size) is injected at build time
  (`config.py`); `store.py` builds the engine/sessionmaker and hands them to `TabularSystem`,
  which never constructs an engine itself. `backend/app/deps.py` wires a single shared
  `TabularSystem` per process via `get_tabular` (mirrors `get_rag`).
- **DRY schema**: patterns reuse the `transactions` table instead of a third, near-identical
  table — the only difference is two extra provenance columns.
- **Soft relationships, deliberately no FKs**: `Transaction.from_bank/from_account/to_bank/
  to_account` are indexed for joins against `Account` but are **not** SQLAlchemy `ForeignKey`
  columns, and `Account`'s `(bank_id, account_number)` uniqueness is likewise not an FK
  target. The three source files (accounts/transactions/patterns) can each be ingested
  independently, in any order, or partially, so cross-file referential integrity can't be
  guaranteed at ingest time — a real FK constraint would make ingesting transactions before
  accounts (a normal occurrence) fail. See the comments in `models.py` for the exact columns.
- **Thin API layer**: `app/api/routes/tabular.py` does not branch on `data_type` itself; it
  delegates to `TabularSystem.ingest`, which owns the dispatch (`Open/Closed` — adding a new
  data type only touches the service, not the route).
- **Testable**: `tests/test_tabular_loaders.py` (pure generators, no DB), `test_tabular_service.py`
  (against `sqlite:///:memory:`), `test_tabular_api.py` (route tested with a fake
  `TabularSystem` via FastAPI dependency override).

## Limitations / TODO

- No pagination/streaming on `GET /tabular/counts` beyond a full-table count — fine at
  current scale, would need indexed aggregates for much larger data.
- No detection/scoring logic yet — this feature only ingests and stores; using
  `is_laundering` for evaluation only (never as a model input) is a design constraint
  the next feature (detection) must respect, not something enforced in code today.
- No referential-integrity checks between `accounts` and `transactions` (by design — see
  "soft relationships" above); a `from_account`/`to_account` that never appears in
  `accounts` is not flagged or rejected.
