"""The demo script, plus the cent split and the flip."""

from datetime import datetime
from zoneinfo import ZoneInfo

from commute_split.handle import handle_inbound
from commute_split.ledger import Ledger
from commute_split.money import split_cents

NY = datetime(2026, 10, 3, 15, 0, tzinfo=ZoneInfo("America/New_York"))


def book(tmp_path):
    return Ledger(tmp_path / "commute.db")


def say(ledger, sender, text):
    return handle_inbound(ledger, sender, text, source="test_chat", now=NY)


def test_demo_script(tmp_path):
    ledger = book(tmp_path)

    fare = say(ledger, "Adrian", "I paid $48, Alex and Sam rode.")
    assert ledger.owed("Alex", "Adrian") == 1600
    assert ledger.owed("Sam", "Adrian") == 1600
    assert ledger.owed("Adrian", "Riley") == 0
    assert ledger.owed("Riley", "Alex") == 0
    assert "Adrian paid $48.00." in fare.reply
    assert "Alex $16.00" in fare.reply
    assert "Sam $16.00" in fare.reply
    assert "Alex owes Adrian $16.00." in fare.reply
    assert "Sam owes Adrian $16.00." in fare.reply
    assert "Riley is even with everyone." in fare.reply

    payback = say(ledger, "Alex", "I just paid Adrian $16.")
    assert ledger.owed("Alex", "Adrian") == 0
    assert ledger.owed("Adrian", "Alex") == 0
    assert ledger.owed("Sam", "Adrian") == 1600
    assert "Alex and Adrian are even." in payback.reply
    assert "Sam owes Adrian $16.00." in payback.reply

    before = ledger.snapshot()
    balance = say(ledger, "Sam", "What do I owe?")
    assert balance.reply == "You owe Adrian $16.00."
    assert ledger.snapshot() == before
    assert balance.changed_balances is False

    out = say(ledger, "Alex", "I'm out.")
    inn = say(ledger, "Riley", "I'm in.")
    assert ledger.snapshot() == before
    assert "Alex is out for Saturday, October 3." in out.reply
    assert "Balances are unchanged." in out.reply
    assert "Riley is in for Saturday, October 3." in inn.reply
    assert "Balances are unchanged." in inn.reply
    assert ledger.rsvp_for(NY.date())["Alex"] == "out"
    assert ledger.rsvp_for(NY.date())["Riley"] == "in"


def test_payback_over_debt_flips_the_net(tmp_path):
    ledger = book(tmp_path)
    say(ledger, "Adrian", "I paid $48, Alex and Sam rode.")
    flipped = say(ledger, "Alex", "I just paid Adrian $45.")
    assert ledger.owed("Adrian", "Alex") == 2900
    assert ledger.owed("Alex", "Adrian") == -2900
    assert ledger.owed("Sam", "Adrian") == 1600
    assert "flips the other way" in flipped.reply
    assert "Adrian now owes Alex $29.00." in flipped.reply
    assert "Sam owes Adrian $16.00." in flipped.reply


def test_fifty_dollar_three_way_split_uses_cents(tmp_path):
    ledger = book(tmp_path)
    fare = say(ledger, "Adrian", "I paid $50, Alex and Sam rode.")
    assert ledger.owed("Alex", "Adrian") == 1667
    assert ledger.owed("Sam", "Adrian") == 1666
    assert ledger.owed("Alex", "Adrian") + ledger.owed("Sam", "Adrian") == 3333
    shares = split_cents(5000, ["Adrian", "Alex", "Sam"])
    assert sum(shares.values()) == 5000
    assert max(shares.values()) - min(shares.values()) <= 1
    assert "$16.67" in fare.reply
    assert "$16.66" in fare.reply


def test_names_dedup_and_match_case_insensitively(tmp_path):
    ledger = book(tmp_path)
    say(ledger, "adrian", "I paid $30, alex and Alex and sam rode.")
    assert ledger.owed("Alex", "Adrian") == 1000
    assert ledger.owed("Sam", "Adrian") == 1000
    assert ledger.owed("Riley", "Adrian") == 0
    people = ledger.list_people()
    assert people.count("Alex") == 1
    assert "alex" not in people

    fresh = book(tmp_path / "two")
    say(fresh, "Adrian", "I paid $30, Alex and alex rode.")
    assert fresh.owed("Alex", "Adrian") == 1500
    assert fresh.owed("Sam", "Adrian") == 0


def test_new_name_is_added(tmp_path):
    ledger = book(tmp_path)
    say(ledger, "Adrian", "I paid $20, Jordan rode.")
    assert "Jordan" in ledger.list_people()
    assert ledger.owed("Jordan", "Adrian") == 1000


def test_unnamed_fare_uses_today_rsvp(tmp_path):
    ledger = book(tmp_path)
    say(ledger, "Alex", "I'm in.")
    say(ledger, "Sam", "I'm in.")
    say(ledger, "Riley", "I'm out.")
    fare = say(ledger, "Adrian", "I paid $30.")
    assert ledger.owed("Alex", "Adrian") == 1000
    assert ledger.owed("Sam", "Adrian") == 1000
    assert ledger.owed("Riley", "Adrian") == 0
    assert "didn't split" not in fare.reply


def test_unnamed_fare_with_nobody_else_in_does_not_charge(tmp_path):
    ledger = book(tmp_path)
    fare = say(ledger, "Adrian", "I paid $48.")
    assert ledger.snapshot() == ()
    assert "didn't split a charge" in fare.reply
    assert fare.changed_balances is False


def test_balances_survive_restart(tmp_path):
    path = tmp_path / "commute.db"
    first = Ledger(path)
    say(first, "Adrian", "I paid $48, Alex and Sam rode.")
    first.close()
    second = Ledger(path)
    assert second.owed("Alex", "Adrian") == 1600
    assert second.owed("Sam", "Adrian") == 1600
    second.close()


def test_largest_remainder_one_dollar(tmp_path):
    del tmp_path
    shares = split_cents(100, ["Adrian", "Alex", "Sam"])
    assert shares == {"Adrian": 34, "Alex": 33, "Sam": 33}
    assert sum(shares.values()) == 100
