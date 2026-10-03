"""Map an ASI:One sender onto the shared ledger. No canned balance replies."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime

from commute_split.handle import handle_inbound
from commute_split.ledger import Ledger

UNMAPPED_REPLY = (
    "I don't know which rider this ASI:One identity is. "
    "Add the address to FETCH_SENDER_MAP, then send that again. "
    "I didn't change the ledger."
)


@dataclass(frozen=True)
class FetchOutcome:
    reply: str
    applied: bool
    sender: str | None


def load_sender_map(raw: str | None = None) -> dict[str, str]:
    text = os.environ.get("FETCH_SENDER_MAP", "") if raw is None else raw
    text = text.strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(
            "FETCH_SENDER_MAP must be a JSON object of agent address to rider name."
        )
    return {str(key): str(value) for key, value in data.items()}


def resolve_sender(address: str, sender_map: dict[str, str]) -> str | None:
    for key, name in sender_map.items():
        if key.casefold() == address.casefold():
            return name
    return None


def apply_fetch_text(
    ledger: Ledger,
    sender_address: str,
    text: str,
    sender_map: dict[str, str],
    *,
    now: datetime | None = None,
) -> FetchOutcome:
    """Run one ASI:One text turn against SQLite.

    Unmapped senders get an explanation and do not write. Mapped senders use
    the same handler as the test chat, so a fare or payback updates the file.
    """
    rider = resolve_sender(sender_address, sender_map)
    if rider is None:
        return FetchOutcome(reply=UNMAPPED_REPLY, applied=False, sender=None)
    result = handle_inbound(ledger, rider, text, source="fetch", now=now)
    return FetchOutcome(reply=result.reply, applied=True, sender=result.sender)
