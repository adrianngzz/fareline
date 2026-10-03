"""One inbound path for the test chat, Spectrum, and the Fetch.ai agent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from commute_split.asi import canonicalize
from commute_split.ledger import Ledger, Net
from commute_split.money import format_cents, split_cents
from commute_split.parse import Command, parse_message

NY = ZoneInfo("America/New_York")
AGENT_NAME = "Fareline"

HELP = (
    "I keep the carpool ledger. I don't book the car.\n"
    "I'm in — riding today.\n"
    "I'm out — not riding today.\n"
    "I paid $48, Alex and Sam rode.\n"
    "I paid $48 — split across whoever is in today.\n"
    "I just paid Alex $16.\n"
    "What do I owe?"
)


@dataclass(frozen=True)
class InboundResult:
    reply: str
    sender: str
    changed_balances: bool


def ny_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(NY)
    if now.tzinfo is None:
        return now.replace(tzinfo=NY)
    return now.astimezone(NY)


def day_label(day: date) -> str:
    return f"{day.strftime('%A, %B')} {day.day}"


def handle_inbound(
    ledger: Ledger,
    sender_name: str,
    text: str,
    *,
    source: str,
    now: datetime | None = None,
) -> InboundResult:
    moment = ny_now(now)
    day = moment.date()
    cleaned = " ".join(text.strip().split())
    command = parse_message(cleaned)
    heard_as: str | None = None
    if command is None and cleaned:
        heard_as = canonicalize(cleaned)
        if heard_as:
            command = parse_message(heard_as)

    with ledger.transaction():
        sender = ledger._ensure_person(sender_name)
        if command is None:
            reply = HELP if cleaned else "Say who paid, or ask what you owe."
            changed = False
        elif command.kind == "rsvp":
            reply, changed = _rsvp(ledger, sender, command, day)
        elif command.kind == "fare":
            reply, changed = _fare(ledger, sender, command, day)
        elif command.kind == "payback":
            reply, changed = _payback(ledger, sender, command)
        else:
            reply, changed = _balance(ledger, sender), False
        if heard_as and command is not None:
            reply = f'I read that as "{heard_as}".\n{reply}'
        ledger._add_message(sender, cleaned or text, "rider", source, moment)
        ledger._add_message(AGENT_NAME, reply, "agent", source, moment)
    return InboundResult(reply=reply, sender=sender, changed_balances=changed)


def _rsvp(ledger: Ledger, sender: str, command: Command, day: date) -> tuple[str, bool]:
    status = command.status or "out"
    ledger.set_rsvp(sender, status, day)
    word = "in" if status == "in" else "out"
    return (
        f"{sender} is {word} for {day_label(day)}. Balances are unchanged.",
        False,
    )


def _fare(
    ledger: Ledger, sender: str, command: Command, day: date
) -> tuple[str, bool]:
    assert command.amount_cents is not None
    if command.names:
        riders = _dedupe(ledger, [sender, *command.names])
    else:
        marked_in = ledger.people_in(day)
        others = [name for name in marked_in if name.casefold() != sender.casefold()]
        riders = _dedupe(ledger, [sender, *others])
        if len(riders) < 2:
            return (
                f"{sender} paid {format_cents(command.amount_cents)}, but nobody else "
                f"is in for {day_label(day)}, so I didn't split a charge.",
                False,
            )
    shares = split_cents(command.amount_cents, riders)
    for rider, share in shares.items():
        if rider.casefold() == sender.casefold() or share == 0:
            continue
        ledger._add_debt(rider, sender, share)
    reply = _fare_reply(
        sender,
        command.amount_cents,
        shares,
        ledger.nets(),
        ledger.list_people(),
    )
    return reply, True


def _payback(ledger: Ledger, sender: str, command: Command) -> tuple[str, bool]:
    assert command.amount_cents is not None
    payee = ledger._ensure_person(command.names[0])
    if payee.casefold() == sender.casefold():
        return ("You can't pay yourself back. Name the rider you paid.", False)
    before = ledger._owed(sender, payee)
    ledger._add_debt(payee, sender, command.amount_cents)
    after = ledger._owed(sender, payee)
    reply = _payback_reply(
        sender,
        payee,
        command.amount_cents,
        before,
        after,
        ledger.nets(),
        ledger.list_people(),
    )
    return reply, True


def _balance(ledger: Ledger, sender: str) -> str:
    owed_by_sender: list[Net] = []
    owed_to_sender: list[Net] = []
    for net in ledger.nets():
        if net.debtor.casefold() == sender.casefold():
            owed_by_sender.append(net)
        elif net.creditor.casefold() == sender.casefold():
            owed_to_sender.append(net)
    if not owed_by_sender and not owed_to_sender:
        return "You're even. Nobody owes you, and you don't owe anyone."
    lines: list[str] = []
    for net in owed_by_sender:
        lines.append(f"You owe {net.creditor} {format_cents(net.cents)}.")
    for net in owed_to_sender:
        lines.append(f"{net.debtor} owes you {format_cents(net.cents)}.")
    return "\n".join(lines)


def _dedupe(ledger: Ledger, names: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for name in names:
        canonical = ledger._ensure_person(name)
        key = canonical.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(canonical)
    return ordered


def _fare_reply(
    payer: str,
    total: int,
    shares: dict[str, int],
    nets: list[Net],
    people: list[str],
) -> str:
    parts = []
    for name, share in shares.items():
        if name.casefold() == payer.casefold():
            parts.append(f"{name} {format_cents(share)} (already paid)")
        else:
            parts.append(f"{name} {format_cents(share)}")
    lines = [
        f"{payer} paid {format_cents(total)}.",
        f"Split {len(shares)} ways: {', '.join(parts)}.",
        *_net_lines(nets, people),
    ]
    return "\n".join(lines)


def _payback_reply(
    payer: str,
    payee: str,
    amount: int,
    before: int,
    after: int,
    nets: list[Net],
    people: list[str],
) -> str:
    if before > 0 and after == 0:
        settlement = (
            f"That clears what {payer} owed {payee}. {payer} and {payee} are even."
        )
    elif before > 0 and after > 0:
        settlement = f"{payer} still owes {payee} {format_cents(after)}."
    elif before > 0 and after < 0:
        settlement = (
            f"{payer} only owed {format_cents(before)}, so "
            f"{format_cents(-after)} flips the other way. "
            f"{payee} now owes {payer} {format_cents(-after)}."
        )
    elif after == 0:
        settlement = f"{payer} and {payee} are even."
    elif after < 0:
        settlement = f"{payee} owes {payer} {format_cents(-after)}."
    else:
        settlement = f"{payer} owes {payee} {format_cents(after)}."
    lines = [
        f"{payer} just paid {payee} {format_cents(amount)}.",
        settlement,
        *_net_lines(nets, people),
    ]
    return "\n".join(lines)


def _net_lines(nets: list[Net], people: list[str]) -> list[str]:
    if not nets:
        return ["Everyone is even."]
    lines = [
        f"{net.debtor} owes {net.creditor} {format_cents(net.cents)}."
        for net in nets
    ]
    involved = {net.debtor for net in nets} | {net.creditor for net in nets}
    quiet = [name for name in people if name not in involved]
    if len(quiet) == 1:
        lines.append(f"{quiet[0]} is even with everyone.")
    elif len(quiet) > 1:
        lines.append(f"{_join(quiet)} are even with everyone.")
    return lines


def _join(names: list[str]) -> str:
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def public_state(ledger: Ledger, now: datetime | None = None) -> dict:
    moment = ny_now(now)
    day = moment.date()
    rsvps = ledger.rsvp_for(day)
    involved: set[str] = set()
    net_rows = []
    for net in ledger.nets():
        involved.add(net.debtor)
        involved.add(net.creditor)
        net_rows.append(
            {
                "debtor": net.debtor,
                "creditor": net.creditor,
                "cents": net.cents,
                "amount": format_cents(net.cents),
            }
        )
    people = []
    for name in ledger.list_people():
        people.append(
            {
                "name": name,
                "rsvp": rsvps.get(name),
                "even": name not in involved,
            }
        )
    return {
        "today": day.isoformat(),
        "today_label": day_label(day),
        "people": people,
        "messages": [
            {
                "id": message.id,
                "sender": message.sender,
                "body": message.body,
                "kind": message.kind,
                "source": message.source,
                "created_at": message.created_at,
            }
            for message in ledger.messages()
        ],
        "nets": net_rows,
    }
