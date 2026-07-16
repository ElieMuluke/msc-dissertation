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
  lines in with data rows and isn't a plain CSV pandas can parse directly. All three accept
  either a path **or** an already-open binary file-like object (see "Byte-based progress,
  no redundant I/O passes" below), and keep the same public contract otherwise — yield one
  plain row `dict` at a time.
- **The service owns the only side effects**: `TabularSystem` (`service.py`) chunks the
  streamed rows into lists of `TabularConfig.batch_size` (default 30,000) via `_batched` and
  bulk-inserts each chunk in one `INSERT`. Accounts use `INSERT ... ON CONFLICT DO NOTHING`
  (SQLite upsert-ignore) on `(bank_id, account_number)` so re-ingesting is idempotent; the
  inserted-row count for that path is measured as the before/after `SELECT COUNT(*)` delta,
  since `executemany` affected-row counts aren't reliable across DBAPI/SQLAlchemy versions
  for `ON CONFLICT DO NOTHING`. Transactions/patterns use a plain insert and return the
  number of rows streamed. Every `ingest_*`/`ingest` method accepts an optional
  `on_batch: Callable[[int], None]`, invoked with the cumulative inserted/streamed row count
  after *every* batch — the service itself still reports rows (its own unit of work) and has
  no idea who's listening; the **API layer** is what turns that into a progress percentage,
  and it does so from bytes, not rows — see below.
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
- **Byte-based progress, no redundant I/O passes**: `POST /tabular/ingest` used to make 4
  full passes over the uploaded file before this fix — Starlette's multipart parser
  spooling the body to a temp file, this route's own `shutil.copyfileobj` copying that into
  a *second* temp file, a separate `count_rows()` read just to size the progress
  percentage, then pandas reading the file a fourth time to actually ingest. `/ingest/local`
  already skipped the first two (no upload, no copy), which is why it was always faster.
  The route now opens the file itself (the upload's `UploadFile.file`, or the local path)
  and wraps it in `ByteCountingReader` (`loaders.py`) — a thin file-like wrapper that counts
  bytes read through `.read()`/`.read1()` — and passes that wrapper straight into
  `TabularSystem.ingest`, which pandas reads directly with no on-disk copy and no separate
  counting pass. Progress percent is `bytes_read / file_size` (from `UploadFile.size` or
  `os.path.getsize`), not an exact row count — a good approximation since these datasets'
  rows are roughly fixed-width, and it's what let the redundant `count_rows` pass be deleted
  entirely (removed from `loaders.py`/`__init__.py`).
- **`counts()` is cached, not re-scanned per call**: at real dataset scale (the live
  `transactions` table has ~180M rows), a fresh `SELECT COUNT(*)` on every call is slow
  enough to occasionally look like a failure — and since `GET /tabular/counts` is polled by
  the frontend on every page load, that repeated full scan was the actual cause of "no
  tabular data" showing up in the UI despite data being present (a slow/failed fetch
  rendered identically to a genuinely-empty result). `TabularSystem` now keeps an in-memory
  `_counts_cache`, populated by one scan the first time `counts()` is called and kept correct
  incrementally by every `ingest_*`/`clear()` call afterwards (`_bump_counts_cache`) — so at
  most one full table scan happens per process lifetime, not per request. Since
  `get_tabular()` (`app/deps.py`) is `@lru_cache`d to a single process-wide `TabularSystem`,
  this cache is safe as long as nothing else writes to the same SQLite file out-of-process.

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

# Pasted/typed CSV text (validated in full before any DB write; raises CsvValidationError
# instead of inserting anything if the text is malformed):
tabular.ingest_text(TabularDataType.ACCOUNTS, "Bank Name,Bank ID,...\n...")
```

### API

```bash
# from backend/
uvicorn app.main:app --reload   # http://localhost:8000
```

**`POST /tabular/ingest`** — multipart form, **streamed response**:

| Field | Type | Notes |
| --- | --- | --- |
| `data_type` | `"accounts" \| "transactions" \| "patterns"` | Selects the table/loader. |
| `files` | one or more file uploads | `.csv` for `accounts`/`transactions`; `.csv` or `.txt` for `patterns`. Wrong extension → an `error` SSE frame. |

```bash
curl -N -X POST http://localhost:8000/tabular/ingest \
  -F "data_type=accounts" \
  -F "files=@HI-Large_accounts.csv"
```

Response is `text/event-stream` (Server-Sent Events), not a single JSON body — mirrors
`POST /rag/answer/stream`'s existing SSE pattern (`app/api/sse.py` generalizes the shared
bits: frame formatting, and bridging a blocking worker-thread producer of progress updates
to an async generator via `bridge_thread_progress`). Frames, per file:

| event | data | when |
| --- | --- | --- |
| `progress` | `{"filename", "progress": 10, "status": "uploading"}` | once, before ingestion starts |
| `progress` | `{"filename", "progress": 10-99, "status": "inserting"}` | repeatedly as bytes are read (see "Byte-based progress" above) |
| `error` | `{"filename", "message"}` | instead of further progress, if the file fails — stops processing any remaining files in the request |

Once every file in the request has ingested successfully, one final frame:

```
event: done
data: {"ingested": 1000, "data_type": "accounts"}
```

`/tabular/ingest/local` streams the identical frame shape (see below). The `/ws` WebSocket
gateway this used to broadcast over (`app/realtime.py`) has been removed entirely — progress
is now scoped to the request that asked for it, with no separate connection to manage.

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

**`POST /tabular/ingest/local`** — ingest a file already on the backend's local disk, by
path; no HTTP upload. JSON body:

```json
{"data_type": "transactions", "path": "/absolute/path/HI-Large_Trans.csv"}
```

An `error` SSE frame (`{"filename", "message"}`) if `path` doesn't exist or has the wrong
extension for `data_type`. Same streamed frame shape as `POST /tabular/ingest` otherwise
(see above). See "Why a local-path endpoint" below for the reason this exists alongside the
upload endpoint.

```bash
curl -N -X POST http://localhost:8000/tabular/ingest/local \
  -H "Content-Type: application/json" \
  -d '{"data_type":"transactions","path":"/absolute/path/to/HI-Large_Trans.csv"}'
```

**`POST /tabular/ingest/text`** — ingest raw CSV/TXT *text* pasted or typed directly
(e.g. from a browser textarea), instead of uploading a file. JSON body:

```json
{"data_type": "accounts", "csv_text": "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\n...\n"}
```

Response (`TabularIngestResponse`), same shape as the other ingest endpoints:
```json
{"ingested": 3, "data_type": "accounts"}
```

**Guarantee: validate everything first, insert only if 100% valid — no partial writes.**
The entire payload is parsed and checked (header columns present, every row
parseable/convertible) *before* a single row is written to the database. If anything is
wrong — a missing header column, a malformed row anywhere in the text, empty text, or
zero data rows — the request returns `422` with a JSON body of
`{"detail": [<error string>, ...]}` (a **list**, not a single message, so every problem
found is reported at once) and the database is left completely untouched. This is the
point of this endpoint: unlike the streaming file-based ingest paths (which insert
batch-by-batch as they read), pasted text is fully materialized and validated up front so
a malformed paste can never corrupt the DB with a partial insert.

Plain JSON, not SSE, for this endpoint (unlike `/tabular/ingest` and `/tabular/ingest/local`)
— pasted text is expected to be small, so ingestion completes in one synchronous-feeling
request/response.

```bash
curl -X POST http://localhost:8000/tabular/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"data_type": "accounts", "csv_text": "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\nBank A,001,111,E1,Alice\n"}'
```

### Why a local-path endpoint

`POST /tabular/ingest` round-trips the whole file over HTTP and stages a copy to disk
before ingesting it. That's fine for the ~148MB `HI-Large_accounts.csv`, but the real
`HI-Large_Trans.csv` is ~17GB, and on this dev machine `/tmp` is a 7.6GB `tmpfs` (RAM-backed)
— both Starlette's multipart upload spooling (`SpooledTemporaryFile`) and the route's own
upload staging dir (`tempfile.TemporaryDirectory()`) resolve through `tempfile.gettempdir()`,
which defaults to `/tmp`. A file bigger than that fails mid-upload with `OSError: No space
left on device`; FastAPI's routing layer catches *any* exception raised while parsing the
request body and reports it as the generic `{"detail":"There was an error parsing the
body"}`, hiding the real cause.

Two independent fixes:
1. **`app/main.py`** redirects `tempfile.tempdir` to `/var/tmp` (disk-backed, not tmpfs) at
   process startup, unless the caller already set `TMPDIR`. This alone fixes both temp-file
   call sites for any upload size.
2. **`POST /tabular/ingest/local`** sidesteps the problem architecturally for files that are
   already on the same machine as the backend: it reads straight from the given path, with
   no HTTP body and no temp copy at all — faster and immune to `/tmp` sizing regardless of
   where `TMPDIR` points.

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
| `iter_accounts`, `iter_transactions`, `iter_patterns` | Pure row-streaming generators (`loaders.py`), reusable outside the ORM service; each accepts a path or an already-open binary file-like object. |
| `ByteCountingReader` | Binary file-like wrapper (`loaders.py`) counting bytes read through `.read()`/`.read1()` in a public `.bytes_read` attribute; used by the API layer to compute upload/ingest progress percentages without a separate counting pass. |
| `parse_csv_text(data_type, text) -> list[dict]` | Validate + fully parse pasted CSV/TXT `text` for `data_type`, all-or-nothing (`loaders.py`); raises `CsvValidationError` before returning anything if the header is missing expected columns, any row fails to parse, or there are zero data rows. |
| `CsvValidationError` | Exception raised by `parse_csv_text`/`TabularSystem.ingest_text`; carries every problem found as `.errors: list[str]` (not just the first). |
| `TabularSystem.ingest_text(data_type, text, source_file=None) -> int` | Validate + bulk-insert pasted CSV/TXT `text`, all-or-nothing: calls `parse_csv_text` (raises before any DB write if invalid), then inserts via the same `_insert`/`_insert_ignore_duplicates` paths as the file-based ingest methods. No `on_batch` progress callback. |

Routes (`app/api/routes/tabular.py`): `POST /tabular/ingest` (upload, SSE), `POST
/tabular/ingest/local` (server-local path, no upload, SSE), `POST /tabular/ingest/text`
(pasted CSV/TXT text, validated before any write, plain JSON), `GET /tabular/counts`,
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
- **Progress transport is request-scoped, not a shared broadcast**: `/tabular/ingest` and
  `/ingest/local` used to push progress over a shared `/ws` WebSocket gateway
  (`app/realtime.py`, now deleted) that every connected client received frames from,
  filtered client-side by filename. They now stream Server-Sent Events on the response of
  the very request that triggered them (`app/api/sse.py`'s `bridge_thread_progress` bridges
  the blocking worker thread doing the actual ingestion to the async generator the
  `StreamingResponse` consumes) — no separate connection, no fan-out/filtering, and the
  same pattern `POST /rag/answer/stream` already established for LLM token streaming.
- **Full eager materialization is correct for pasted text, deliberately unlike the
  streaming file paths**: `parse_csv_text` loads and validates the *entire* input into a
  `list[dict]` before returning anything, whereas `iter_accounts`/`iter_transactions`/
  `iter_patterns` are pure generators sized for multi-million-row, multi-gigabyte on-disk
  files. Pasted/typed text comes from a UI textarea — it is expected to be small (rows,
  not millions) — so the memory cost of materializing it fully is negligible, and doing so
  is what makes the "validate everything, then insert only if 100% valid" guarantee
  possible: you cannot know the whole payload is valid without having parsed the whole
  payload. Reusing the streaming generators for the file paths remains correct there
  because progress reporting + bounded memory matter far more than atomicity for
  multi-GB files.
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
- `POST /tabular/ingest/local` trusts any path readable by the backend process — there is
  no allowlist/sandboxing of which directories may be read. Acceptable for this project's
  single-user local-dev deployment model; would need a path allowlist before ever being
  exposed beyond localhost.
- `parse_csv_text`/`POST /tabular/ingest/text` only validates header columns up front for
  `ACCOUNTS`/`TRANSACTIONS` (`_EXPECTED_HEADERS`); `PATTERNS` text has no header to check
  and is only validated by attempting to parse every row, so a `PATTERNS` paste with
  entirely wrong columns fails with whatever parse error the first bad row produces rather
  than an explicit "missing column" message.
- SSE progress on `/tabular/ingest`/`/ingest/local` is request-scoped: if the client
  disconnects mid-stream, ingestion continues server-side to completion (or failure), but
  there's no way to reconnect and resume watching it — the same limitation the old `/ws`
  broadcast had if a client dropped and reconnected without still being subscribed.
