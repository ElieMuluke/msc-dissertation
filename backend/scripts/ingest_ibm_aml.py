"""Ingest the IBM AML Kaggle dataset ("IBM Transactions for Anti Money Laundering")
into the tabular SQLite store, recording dataset provenance in a manifest (PRD-B §2).

Kaggle downloads require credentials, so this script takes *local* file paths: download
the dataset yourself (https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml,
schema per https://github.com/IBM/AML-Data) and drop the CSV/TXT files under
``backend/data/ibm_aml/`` (any path works — that directory is just the documented
drop point). Then, from ``backend/``:

    .venv/bin/python scripts/ingest_ibm_aml.py \
        --transactions data/ibm_aml/HI-Small_Trans.csv \
        --accounts data/ibm_aml/HI-Small_accounts.csv \
        --patterns data/ibm_aml/HI-Small_Patterns.txt \
        --dataset-version HI-Small --download-date 2026-08-05

Every flag is optional — pass whichever files you have. A synthetic end-to-end sample
matching the IBM schema ships under ``backend/data/samples/`` (``ibm_aml_sample_*``), so
the pipeline is testable before the real download:

    .venv/bin/python scripts/ingest_ibm_aml.py \
        --transactions data/samples/ibm_aml_sample_transactions.csv \
        --accounts data/samples/ibm_aml_sample_accounts.csv \
        --patterns data/samples/ibm_aml_sample_patterns.txt \
        --dataset-version synthetic-sample

Provenance (dataset version, download date, per-file row counts) is appended to
``backend/data/ibm_aml_manifest.json`` on every run.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

# Allow running as a plain script from backend/ (scripts/ is not a package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.tabular import TabularConfig, TabularDataType, build_tabular_system  # noqa: E402

_DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "data" / "ibm_aml_manifest.json"


def _progress(label: str):
    def on_batch(done: int) -> None:
        print(f"\r  {label}: {done:,} rows", end="", flush=True)

    return on_batch


def ingest(
    transactions: Optional[Path],
    accounts: Optional[Path],
    patterns: Optional[Path],
    dataset_version: str,
    download_date: str,
    db_url: Optional[str] = None,
    manifest_path: Path = _DEFAULT_MANIFEST,
) -> dict:
    """Ingest the given IBM AML files and append a provenance record to the manifest.

    Returns the manifest record written (also useful for tests). Reuses the existing
    ``app.ingestion.tabular`` path end-to-end — same loaders/tables the API uses.
    """
    config = TabularConfig(db_url=db_url) if db_url else TabularConfig()
    tabular = build_tabular_system(config)

    counts: dict[str, int] = {}
    jobs = (
        (TabularDataType.ACCOUNTS, accounts),
        (TabularDataType.TRANSACTIONS, transactions),
        (TabularDataType.PATTERNS, patterns),
    )
    for data_type, path in jobs:
        if path is None:
            continue
        if not path.is_file():
            raise FileNotFoundError(f"No such file for {data_type.value}: {path}")
        print(f"Ingesting {data_type.value} from {path} ...")
        counts[data_type.value] = tabular.ingest(
            data_type, str(path), source_file=path.name, on_batch=_progress(data_type.value)
        )
        print()

    record = {
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": "IBM Transactions for Anti Money Laundering (Kaggle)",
        "dataset_version": dataset_version,
        "download_date": download_date,
        "files": {dt.value: str(p) for dt, p in jobs if p is not None},
        "rows_inserted": counts,
        "db_url": config.db_url,
    }
    manifest = []
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.append(record)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest updated: {manifest_path}")
    return record


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--transactions", type=Path, help="Path to the transactions CSV (e.g. HI-Small_Trans.csv).")
    parser.add_argument("--accounts", type=Path, help="Path to the accounts CSV (e.g. HI-Small_accounts.csv).")
    parser.add_argument("--patterns", type=Path, help="Path to the labeled patterns TXT (e.g. HI-Small_Patterns.txt).")
    parser.add_argument("--dataset-version", required=True, help="Which Kaggle variant, e.g. HI-Small / LI-Large / synthetic-sample.")
    parser.add_argument("--download-date", default=date.today().isoformat(), help="When the dataset was downloaded (ISO date; default today).")
    parser.add_argument("--db-url", default=None, help="Override the SQLite URL (default: the app's tabular_data_db.sqlite).")
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST, help="Manifest JSON to append provenance to.")
    args = parser.parse_args(argv)

    if not any((args.transactions, args.accounts, args.patterns)):
        parser.error("nothing to do: pass at least one of --transactions/--accounts/--patterns")

    record = ingest(
        transactions=args.transactions,
        accounts=args.accounts,
        patterns=args.patterns,
        dataset_version=args.dataset_version,
        download_date=args.download_date,
        db_url=args.db_url,
        manifest_path=args.manifest,
    )
    print(json.dumps(record["rows_inserted"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
