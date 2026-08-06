"""End-to-end test for scripts/ingest_ibm_aml.py over the shipped synthetic sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "scripts"))

from ingest_ibm_aml import ingest, main  # noqa: E402

SAMPLES = BACKEND / "data" / "samples"


def test_ingest_sample_end_to_end(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'ibm.sqlite'}"
    manifest_path = tmp_path / "manifest.json"

    record = ingest(
        transactions=SAMPLES / "ibm_aml_sample_transactions.csv",
        accounts=SAMPLES / "ibm_aml_sample_accounts.csv",
        patterns=SAMPLES / "ibm_aml_sample_patterns.txt",
        dataset_version="synthetic-sample",
        download_date="2026-08-05",
        db_url=db_url,
        manifest_path=manifest_path,
    )

    assert record["rows_inserted"] == {"accounts": 7, "transactions": 30, "patterns": 6}
    assert record["dataset_version"] == "synthetic-sample"
    assert record["download_date"] == "2026-08-05"

    manifest = json.loads(manifest_path.read_text())
    assert len(manifest) == 1 and manifest[0]["rows_inserted"]["transactions"] == 30

    # Data actually landed and is queryable through the shared tabular path.
    from app.ingestion.tabular import TabularConfig, build_tabular_system

    tabular = build_tabular_system(TabularConfig(db_url=db_url))
    assert tabular.counts() == {"accounts": 7, "transactions": 36}
    txns = tabular.query_transactions("100428660", direction="out", min_amount=9000)
    assert len(txns) >= 3  # the structuring pattern rows


def test_manifest_appends_on_second_run(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'ibm.sqlite'}"
    manifest_path = tmp_path / "manifest.json"
    for _ in range(2):
        ingest(
            transactions=None,
            accounts=SAMPLES / "ibm_aml_sample_accounts.csv",
            patterns=None,
            dataset_version="synthetic-sample",
            download_date="2026-08-05",
            db_url=db_url,
            manifest_path=manifest_path,
        )
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest) == 2
    # Accounts ingestion is idempotent on (bank_id, account_number).
    assert manifest[1]["rows_inserted"]["accounts"] == 0


def test_main_requires_at_least_one_file(capsys):
    import pytest

    with pytest.raises(SystemExit):
        main(["--dataset-version", "x"])
