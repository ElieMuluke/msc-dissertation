"""API tests for the tabular ingestion endpoints, with TabularSystem faked."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.deps import get_tabular
from app.ingestion.tabular import CsvValidationError
from app.main import app
from conftest import parse_sse_frames

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

    def ingest_text(self, data_type, text, source_file=None):
        self.calls.append((data_type, text, source_file))
        if text == "MALFORMED":
            raise CsvValidationError(["bad row: not-a-number"])
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
    assert res.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse_frames(res.text)

    statuses = [f["data"]["status"] for f in frames if f["event"] == "progress"]
    assert statuses[0] == "uploading"
    assert statuses[-1] == "completed"
    done = frames[-1]
    assert done["event"] == "done"
    assert done["data"] == {"ingested": 1, "data_type": "accounts"}


def test_ingest_rejects_wrong_extension(client):
    files = [("files", ("accounts.pdf", b"hello", "application/pdf"))]
    res = client.post("/tabular/ingest", files=files, data={"data_type": "accounts"})
    assert res.status_code == 200
    frames = parse_sse_frames(res.text)
    assert frames[0]["event"] == "error"
    assert "accounts.pdf" in frames[0]["data"]["message"]


def test_ingest_patterns_accepts_txt(client):
    files = [("files", ("patterns.txt", b"BEGIN LAUNDERING ATTEMPT - CYCLE\nEND LAUNDERING ATTEMPT - CYCLE\n", "text/plain"))]
    res = client.post("/tabular/ingest", files=files, data={"data_type": "patterns"})
    assert res.status_code == 200
    frames = parse_sse_frames(res.text)
    done = frames[-1]
    assert done["event"] == "done"
    assert done["data"] == {"ingested": 1, "data_type": "patterns"}


def test_ingest_local(client, tmp_path):
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)
    res = client.post("/tabular/ingest/local", json={"data_type": "accounts", "path": str(path)})
    assert res.status_code == 200
    frames = parse_sse_frames(res.text)
    done = frames[-1]
    assert done["event"] == "done"
    assert done["data"] == {"ingested": 1, "data_type": "accounts"}


def test_ingest_local_missing_file_reports_error(client, tmp_path):
    res = client.post(
        "/tabular/ingest/local", json={"data_type": "accounts", "path": str(tmp_path / "missing.csv")}
    )
    assert res.status_code == 200
    frames = parse_sse_frames(res.text)
    assert frames[0]["event"] == "error"


def test_ingest_text_valid_csv(client):
    res = client.post("/tabular/ingest/text", json={"data_type": "accounts", "csv_text": ACCOUNTS_CSV})
    assert res.status_code == 200
    assert res.json() == {"ingested": 1, "data_type": "accounts"}


def test_ingest_text_malformed_returns_422(client):
    res = client.post("/tabular/ingest/text", json={"data_type": "accounts", "csv_text": "MALFORMED"})
    assert res.status_code == 422
    assert res.json()["detail"] == ["bad row: not-a-number"]


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
