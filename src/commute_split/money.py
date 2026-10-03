"""Integer-cent money helpers. Shares always sum to the fare."""

from __future__ import annotations


def parse_dollars(raw: str) -> int | None:
    """Parse a dollar amount into cents. Rejects more than two decimal places."""
    text = raw.strip().replace("$", "").replace(",", "")
    if not text or text.startswith("-"):
        return None
    if "." in text:
        dollars, fraction = text.split(".", 1)
        if not dollars.isdigit() or not fraction.isdigit() or len(fraction) > 2:
            return None
        return int(dollars) * 100 + int(fraction.ljust(2, "0"))
    if not text.isdigit():
        return None
    return int(text) * 100


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    dollars, remainder = divmod(cents, 100)
    return f"{sign}${dollars:,}.{remainder:02d}"


def split_cents(total: int, people: list[str]) -> dict[str, int]:
    """Split ``total`` cents evenly.

    Uses the largest-remainder method. Equal fractional parts are broken by
    list order: earlier people receive the extra cent. Shares differ by at
    most one cent and sum to ``total``.
    """
    if total < 0:
        raise ValueError("total must be non-negative")
    count = len(people)
    if count == 0:
        raise ValueError("nobody to split across")
    base, remainder = divmod(total, count)
    return {
        person: base + (1 if index < remainder else 0)
        for index, person in enumerate(people)
    }
