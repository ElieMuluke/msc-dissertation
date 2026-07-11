"""API tests for the tabular ingestion endpoints, with TabularSystem faked."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.deps import get_tabular
from app.main import app

ACCOUNTS_CSV = (
    "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\n"
    "Portugal Bank #500,240522,82655C500,2AA04EEC5D0,Corporation #82502\n"
)


class FakeTabular:
    def __init__(self):
        self.calls: list[tuple] = []
        self.cleared = False

    def ingest(self, data_type, path, source_file=None, on_batch=None):
        self.calls.append((data_type, path, source_file))
        if on_batch is not None:
            on_batch(1)
        return 1

    def counts(self):
        return {"accounts": 3, "transactions": 5}

    def clear(self):
        self.cleared = True


@pytest.fixture
def client():
    fake = FakeTabular()
    app.dependency_overrides[get_tabular] = lambda: fake
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ingest_accounts_csv(client):
    files = [("files", ("accounts.csv", ACCOUNTS_CSV.encode(), "text/csv"))]
    res = client.post("/tabular/ingest", files=files, data={"data_type": "accounts"})
    assert res.status_code == 200
    assert res.json() == {"ingested": 1, "data_type": "accounts"}


def test_ingest_rejects_wrong_extension(client):
    files = [("files", ("accounts.pdf", b"hello", "application/pdf"))]
    res = client.post("/tabular/ingest", files=files, data={"data_type": "accounts"})
    assert res.status_code == 400


def test_ingest_patterns_accepts_txt(client):
    files = [("files", ("patterns.txt", b"BEGIN LAUNDERING ATTEMPT - CYCLE\nEND LAUNDERING ATTEMPT - CYCLE\n", "text/plain"))]
    res = client.post("/tabular/ingest", files=files, data={"data_type": "patterns"})
    assert res.status_code == 200
    assert res.json() == {"ingested": 1, "data_type": "patterns"}


def test_counts(client):
    res = client.get("/tabular/counts")
    assert res.status_code == 200
    assert res.json() == {"accounts": 3, "transactions": 5}


def test_clear_data(client):
    fake = app.dependency_overrides[get_tabular]()
    res = client.delete("/tabular/data")
    assert res.status_code == 200
    assert res.json() == {"status": "cleared"}
    assert fake.cleared is True
