"""Turn a group-chat line into a ledger command."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from commute_split.money import parse_dollars

CommandKind = Literal["rsvp", "fare", "payback", "balance"]

_RSVP = re.compile(
    r"^(?:i'm|im|i am)\s+(in|out)(?:\s+today)?\s*\.?$",
    re.IGNORECASE,
)
_BALANCE = re.compile(r"^what do i owe\s*\??\s*$", re.IGNORECASE)
_PAYBACK = re.compile(
    r"^(?:i\s+)?just\s+paid\s+(?P<name>.+?)\s+\$?(?P<amount>\d[\d,]*(?:\.\d{1,2})?)\s*\.?$",
    re.IGNORECASE,
)
_FARE = re.compile(
    r"^(?:i\s+)?paid\s+\$?(?P<amount>\d[\d,]*(?:\.\d{1,2})?)"
    r"(?:\s*[,:]?\s*(?P<riders>.+?)\s+rode)?"
    r"\s*\.?$",
    re.IGNORECASE,
)
_AND = re.compile(r",?\s+\band\b\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    status: str | None = None
    amount_cents: int | None = None
    names: tuple[str, ...] = ()


def split_rider_names(text: str) -> list[str]:
    cleaned = text.strip().strip(".")
    cleaned = cleaned.replace("&", " and ")
    cleaned = _AND.sub(", ", cleaned)
    names: list[str] = []
    for part in cleaned.split(","):
        part = " ".join(part.split())
        if part and part.casefold() != "and":
            names.append(part)
    return names


def parse_message(text: str) -> Command | None:
    raw = " ".join(text.strip().split())
    if not raw:
        return None

    rsvp = _RSVP.match(raw)
    if rsvp:
        return Command(kind="rsvp", status=rsvp.group(1).lower())

    if _BALANCE.match(raw):
        return Command(kind="balance")

    payback = _PAYBACK.match(raw)
    if payback:
        cents = parse_dollars(payback.group("amount"))
        name = " ".join(payback.group("name").split())
        if cents is None or cents <= 0 or not name:
            return None
        return Command(kind="payback", amount_cents=cents, names=(name,))

    fare = _FARE.match(raw)
    if fare:
        cents = parse_dollars(fare.group("amount"))
        if cents is None or cents <= 0:
            return None
        riders_raw = fare.group("riders")
        names = tuple(split_rider_names(riders_raw)) if riders_raw else ()
        return Command(kind="fare", amount_cents=cents, names=names)

    return None
