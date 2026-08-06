"""Journal durability, torn-line tolerance, resume keys, and progress file."""

import json
from pathlib import Path

import pytest

from experiments.harness.journal import (
    Journal,
    completed_keys,
    journal_path,
    read_journal,
    run_key,
    write_progress,
)


def _record(case_id: str, arm: str = "single", condition: str = "t0-fixed",
            repeat_idx: int = 0, **extra) -> dict:
    return {
        "run_id": f"{arm}:{case_id}:{condition}:{repeat_idx}",
        "case_id": case_id,
        "arm": arm,
        "condition": condition,
        "repeat_idx": repeat_idx,
        "started_at": "2026-08-06T00:00:00Z",
        "wall_clock_s": 1.5,
        **extra,
    }


def test_append_and_read_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "journal-single.jsonl"
    with Journal(path) as journal:
        journal.append(_record("C1"))
        journal.append(_record("C2", repeat_idx=1))
    records = read_journal(path)
    assert [r["case_id"] for r in records] == ["C1", "C2"]


def test_read_missing_file_is_empty(tmp_path: Path) -> None:
    assert read_journal(tmp_path / "nope.jsonl") == []


def test_torn_final_line_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "journal-single.jsonl"
    with Journal(path) as journal:
        journal.append(_record("C1"))
    with open(path, "a") as fh:
        fh.write('{"run_id": "single:C2:t0-f')  # simulated crash mid-write
    records = read_journal(path)
    assert len(records) == 1
    assert completed_keys(path) == {("C1", "single", "t0-fixed", 0)}


def test_kill_mid_write_then_restart_append_heals(tmp_path: Path) -> None:
    """F1: a torn tail must not merge with the next append after restart."""
    path = tmp_path / "journal-single.jsonl"
    with Journal(path) as journal:
        journal.append(_record("C1"))
    # kill -9 mid-write: partial record, no trailing newline
    with open(path, "a") as fh:
        fh.write('{"run_id": "single:C2:t0-fixed:0", "case_id": "C2"')
    # restart: a new Journal appends the re-run of C2
    with Journal(path) as journal:
        journal.append(_record("C2"))
    records = read_journal(path)  # must not raise, no merged corrupt line
    assert [r["case_id"] for r in records] == ["C1", "C2"]
    assert completed_keys(path) == {
        ("C1", "single", "t0-fixed", 0),
        ("C2", "single", "t0-fixed", 0),
    }
    # every line on disk is valid JSON (the partial tail was dropped)
    for line in path.read_text().splitlines():
        json.loads(line)


def test_heal_preserves_intact_journal(tmp_path: Path) -> None:
    path = tmp_path / "journal-single.jsonl"
    with Journal(path) as journal:
        journal.append(_record("C1"))
    before = path.read_bytes()
    with Journal(path) as journal:  # reopen: heal must be a no-op
        journal.append(_record("C2"))
    assert path.read_bytes().startswith(before)
    assert len(read_journal(path)) == 2


def test_corrupt_middle_line_raises(tmp_path: Path) -> None:
    path = tmp_path / "journal-single.jsonl"
    path.write_text('not json\n' + json.dumps(_record("C1")) + "\n")
    with pytest.raises(json.JSONDecodeError):
        read_journal(path)


def test_resume_keys_distinguish_condition_and_repeat(tmp_path: Path) -> None:
    path = tmp_path / "journal-single.jsonl"
    with Journal(path) as journal:
        journal.append(_record("C1", condition="t0-fixed", repeat_idx=0))
        journal.append(_record("C1", condition="t0-fixed", repeat_idx=1))
        journal.append(_record("C1", condition="t07-varied", repeat_idx=0))
    keys = completed_keys(path)
    assert len(keys) == 3
    planned = [
        _record("C1", condition="t0-fixed", repeat_idx=0),
        _record("C1", condition="t0-fixed", repeat_idx=2),  # not yet run
        _record("C2", condition="t0-fixed", repeat_idx=0),  # not yet run
    ]
    todo = [r for r in planned if run_key(r) not in keys]
    assert [(r["case_id"], r["repeat_idx"]) for r in todo] == [("C1", 2), ("C2", 0)]


def test_write_progress(tmp_path: Path) -> None:
    manifest = {"totals": {"single": 4, "mas": 4}}
    with Journal(journal_path(tmp_path, "single")) as journal:
        journal.append(_record("C1"))
        journal.append(_record("C2"))
    progress = write_progress(tmp_path, manifest)
    assert progress["done"] == 2 and progress["total"] == 8
    assert progress["arms"]["single"]["done"] == 2
    assert progress["arms"]["single"]["eta_s"] == pytest.approx(1.5 * 2)
    assert progress["arms"]["mas"]["done"] == 0
    on_disk = json.loads((tmp_path / "progress.json").read_text())
    assert on_disk["arms"]["single"]["total"] == 4


def test_write_progress_concurrent_writers(tmp_path: Path) -> None:
    """F2: two runners hammering write_progress must never crash a writer."""
    import concurrent.futures

    manifest = {"totals": {"single": 100, "mas": 100}}
    with Journal(journal_path(tmp_path, "single")) as journal:
        journal.append(_record("C1"))

    def hammer(worker: int) -> int:
        for _ in range(50):
            write_progress(tmp_path, manifest)
        return worker

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(hammer, [0, 1])) == [0, 1]  # no FileNotFoundError
    final = json.loads((tmp_path / "progress.json").read_text())
    assert final["done"] == 1 and final["total"] == 200
    assert not list(tmp_path.glob(".progress-*.tmp"))  # no leaked tmp files
