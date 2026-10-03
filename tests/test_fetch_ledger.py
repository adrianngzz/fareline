"""ASI:One turns go through SQLite, not a canned reply."""

from datetime import datetime
from zoneinfo import ZoneInfo

from commute_split.fetch_bridge import apply_fetch_text
from commute_split.ledger import Ledger

NY = datetime(2026, 10, 3, 15, 0, tzinfo=ZoneInfo("America/New_York"))
MAP = {
    "agent1qadrian": "Adrian",
    "agent1qsam": "Sam",
}


def test_fetch_fare_writes_sqlite(tmp_path):
    path = tmp_path / "commute.db"
    ledger = Ledger(path)
    outcome = apply_fetch_text(
        ledger,
        "agent1qadrian",
        "I paid $48, Alex and Sam rode.",
        MAP,
        now=NY,
    )
    assert outcome.applied is True
    assert outcome.sender == "Adrian"
    assert "Alex owes Adrian $16.00." in outcome.reply
    ledger.close()

    reopened = Ledger(path)
    assert reopened.owed("Alex", "Adrian") == 1600
    assert reopened.owed("Sam", "Adrian") == 1600
    assert reopened.messages()[-1].source == "fetch"
    reopened.close()


def test_fetch_balance_reads_sqlite(tmp_path):
    ledger = Ledger(tmp_path / "commute.db")
    apply_fetch_text(
        ledger,
        "agent1qadrian",
        "I paid $48, Alex and Sam rode.",
        MAP,
        now=NY,
    )
    outcome = apply_fetch_text(
        ledger,
        "agent1qsam",
        "What do I owe?",
        MAP,
        now=NY,
    )
    assert outcome.applied is True
    assert outcome.reply == "You owe Adrian $16.00."
    assert ledger.owed("Sam", "Adrian") == 1600


def test_unmapped_fetch_sender_does_not_touch_the_ledger(tmp_path):
    ledger = Ledger(tmp_path / "commute.db")
    before = ledger.snapshot()
    count = len(ledger.messages())
    outcome = apply_fetch_text(
        ledger,
        "agent1qstranger",
        "I paid $48, Alex and Sam rode.",
        MAP,
        now=NY,
    )
    assert outcome.applied is False
    assert "didn't change the ledger" in outcome.reply
    assert ledger.snapshot() == before
    assert len(ledger.messages()) == count
