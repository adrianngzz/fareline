"""SQLite ledger. Balances survive restarts. Amounts are integer cents."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

ROSTER = ("Adrian", "Alex", "Sam", "Riley")


@dataclass(frozen=True)
class Net:
    debtor: str
    creditor: str
    cents: int


@dataclass(frozen=True)
class ChatMessage:
    id: int
    sender: str
    body: str
    kind: str
    source: str
    created_at: str


class Ledger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._depth = 0
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()
        self._seed_roster()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def transaction(self):
        with self._lock:
            self._depth += 1
            try:
                yield
                if self._depth == 1:
                    self._conn.commit()
            except Exception:
                if self._depth == 1:
                    self._conn.rollback()
                raise
            finally:
                self._depth -= 1

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rsvps (
                person_id INTEGER NOT NULL REFERENCES people(id),
                day TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('in', 'out')),
                PRIMARY KEY (person_id, day)
            );

            CREATE TABLE IF NOT EXISTS balances (
                debtor_id INTEGER NOT NULL REFERENCES people(id),
                creditor_id INTEGER NOT NULL REFERENCES people(id),
                cents INTEGER NOT NULL CHECK (cents > 0),
                PRIMARY KEY (debtor_id, creditor_id),
                CHECK (debtor_id != creditor_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                sender TEXT NOT NULL,
                body TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('rider', 'agent')),
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def _seed_roster(self) -> None:
        with self.transaction():
            for name in ROSTER:
                self._ensure_person(name)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_person(self, name: str) -> str:
        cleaned = " ".join(name.split())
        if not cleaned:
            raise ValueError("A rider needs a name.")
        row = self._conn.execute(
            "SELECT name FROM people WHERE name = ? COLLATE NOCASE",
            (cleaned,),
        ).fetchone()
        if row:
            return str(row["name"])
        self._conn.execute(
            "INSERT INTO people (name, created_at) VALUES (?, ?)",
            (cleaned, self._now()),
        )
        return cleaned

    def ensure_person(self, name: str) -> str:
        with self.transaction():
            return self._ensure_person(name)

    def _person_id(self, name: str) -> int:
        canonical = self._ensure_person(name)
        row = self._conn.execute(
            "SELECT id FROM people WHERE name = ?",
            (canonical,),
        ).fetchone()
        if row is None:
            raise KeyError(canonical)
        return int(row["id"])

    def list_people(self) -> list[str]:
        with self.transaction():
            rows = self._conn.execute(
                "SELECT name FROM people ORDER BY id"
            ).fetchall()
        return [str(row["name"]) for row in rows]

    def set_rsvp(self, name: str, status: str, day: date) -> str:
        if status not in {"in", "out"}:
            raise ValueError("RSVP must be in or out.")
        with self.transaction():
            canonical = self._ensure_person(name)
            person_id = self._person_id(canonical)
            self._conn.execute(
                """
                INSERT INTO rsvps (person_id, day, status) VALUES (?, ?, ?)
                ON CONFLICT(person_id, day) DO UPDATE SET status = excluded.status
                """,
                (person_id, day.isoformat(), status),
            )
        return canonical

    def rsvp_for(self, day: date) -> dict[str, str | None]:
        with self.transaction():
            people = [
                str(row["name"])
                for row in self._conn.execute(
                    "SELECT name FROM people ORDER BY id"
                ).fetchall()
            ]
            rows = self._conn.execute(
                """
                SELECT p.name, r.status
                FROM rsvps r
                JOIN people p ON p.id = r.person_id
                WHERE r.day = ?
                """,
                (day.isoformat(),),
            ).fetchall()
        status = {str(row["name"]): str(row["status"]) for row in rows}
        return {name: status.get(name) for name in people}

    def people_in(self, day: date) -> list[str]:
        with self.transaction():
            rows = self._conn.execute(
                """
                SELECT p.name
                FROM rsvps r
                JOIN people p ON p.id = r.person_id
                WHERE r.day = ? AND r.status = 'in'
                ORDER BY p.name COLLATE NOCASE
                """,
                (day.isoformat(),),
            ).fetchall()
        return [str(row["name"]) for row in rows]

    def _balance(self, debtor_id: int, creditor_id: int) -> int:
        row = self._conn.execute(
            """
            SELECT cents FROM balances
            WHERE debtor_id = ? AND creditor_id = ?
            """,
            (debtor_id, creditor_id),
        ).fetchone()
        return int(row["cents"]) if row else 0

    def _set_balance(self, debtor_id: int, creditor_id: int, cents: int) -> None:
        if cents <= 0:
            self._conn.execute(
                "DELETE FROM balances WHERE debtor_id = ? AND creditor_id = ?",
                (debtor_id, creditor_id),
            )
            return
        self._conn.execute(
            """
            INSERT INTO balances (debtor_id, creditor_id, cents) VALUES (?, ?, ?)
            ON CONFLICT(debtor_id, creditor_id) DO UPDATE SET cents = excluded.cents
            """,
            (debtor_id, creditor_id, cents),
        )

    def _add_debt(self, debtor: str, creditor: str, cents: int) -> None:
        if cents < 0:
            self._add_debt(creditor, debtor, -cents)
            return
        if cents == 0:
            return
        debtor_name = self._ensure_person(debtor)
        creditor_name = self._ensure_person(creditor)
        if debtor_name.casefold() == creditor_name.casefold():
            return
        debtor_id = self._person_id(debtor_name)
        creditor_id = self._person_id(creditor_name)
        opposite = self._balance(creditor_id, debtor_id)
        if opposite:
            if cents < opposite:
                self._set_balance(creditor_id, debtor_id, opposite - cents)
                return
            if cents == opposite:
                self._set_balance(creditor_id, debtor_id, 0)
                return
            self._set_balance(creditor_id, debtor_id, 0)
            cents -= opposite
        combined = self._balance(debtor_id, creditor_id) + cents
        self._set_balance(debtor_id, creditor_id, combined)

    def add_debt(self, debtor: str, creditor: str, cents: int) -> None:
        with self.transaction():
            self._add_debt(debtor, creditor, cents)

    def owed(self, debtor: str, creditor: str) -> int:
        """Positive when ``debtor`` owes ``creditor``."""
        with self.transaction():
            return self._owed(debtor, creditor)

    def _owed(self, debtor: str, creditor: str) -> int:
        debtor_name = self._ensure_person(debtor)
        creditor_name = self._ensure_person(creditor)
        if debtor_name.casefold() == creditor_name.casefold():
            return 0
        debtor_id = self._person_id(debtor_name)
        creditor_id = self._person_id(creditor_name)
        return self._balance(debtor_id, creditor_id) - self._balance(
            creditor_id, debtor_id
        )

    def nets(self) -> list[Net]:
        with self.transaction():
            rows = self._conn.execute(
                """
                SELECT d.name AS debtor, c.name AS creditor, b.cents
                FROM balances b
                JOIN people d ON d.id = b.debtor_id
                JOIN people c ON c.id = b.creditor_id
                WHERE b.cents > 0
                ORDER BY d.name COLLATE NOCASE, c.name COLLATE NOCASE
                """
            ).fetchall()
        return [
            Net(str(row["debtor"]), str(row["creditor"]), int(row["cents"]))
            for row in rows
        ]

    def snapshot(self) -> tuple[tuple[str, str, int], ...]:
        return tuple((net.debtor, net.creditor, net.cents) for net in self.nets())

    def add_message(
        self,
        sender: str,
        body: str,
        kind: str,
        source: str,
        created_at: datetime,
    ) -> ChatMessage:
        with self.transaction():
            return self._add_message(sender, body, kind, source, created_at)

    def _add_message(
        self,
        sender: str,
        body: str,
        kind: str,
        source: str,
        created_at: datetime,
    ) -> ChatMessage:
        stamp = created_at.isoformat()
        cursor = self._conn.execute(
            """
            INSERT INTO messages (sender, body, kind, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sender, body, kind, source, stamp),
        )
        return ChatMessage(
            id=int(cursor.lastrowid),
            sender=sender,
            body=body,
            kind=kind,
            source=source,
            created_at=stamp,
        )

    def messages(self) -> list[ChatMessage]:
        with self.transaction():
            rows = self._conn.execute(
                """
                SELECT id, sender, body, kind, source, created_at
                FROM messages
                ORDER BY id
                """
            ).fetchall()
        return [
            ChatMessage(
                id=int(row["id"]),
                sender=str(row["sender"]),
                body=str(row["body"]),
                kind=str(row["kind"]),
                source=str(row["source"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]
