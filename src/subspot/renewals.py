"""Write expected renewals as an iCalendar (.ics) file."""

from __future__ import annotations

import datetime as dt
import hashlib

from .detect import Subscription

RULES = {
    "week": "FREQ=WEEKLY",
    "2 weeks": "FREQ=WEEKLY;INTERVAL=2",
    "month": "FREQ=MONTHLY",
    "3 months": "FREQ=MONTHLY;INTERVAL=3",
    "6 months": "FREQ=MONTHLY;INTERVAL=6",
    "year": "FREQ=YEARLY",
}

# Longer cycles get an earlier reminder, since those are the renewals people forget.
REMINDER_DAYS = {"3 months": 7, "6 months": 7, "year": 14}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Split lines longer than 75 bytes, as RFC 5545 asks."""
    out = []
    current = ""
    for char in line:
        limit = 75 if not out else 74
        if len((current + char).encode()) > limit:
            out.append(current)
            current = char
        else:
            current += char
    out.append(current)
    return "\r\n ".join(out)


def _uid(sub: Subscription) -> str:
    # Stable across runs, so importing a newer file updates events instead of duplicating them.
    digest = hashlib.sha1(f"{sub.name}|{sub.frequency.label}|{sub.first}".encode()).hexdigest()[:16]
    return f"{digest}@subscription-spotter"


def ics(subs: list[Subscription], symbol: str, now: dt.datetime | None = None) -> str:
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//subscription-spotter//subspot//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Subscription renewals",
    ]
    for sub in subs:
        if not sub.active:
            continue
        start = sub.next_expected
        amount = f"{symbol}{sub.amount:,.2f}"
        reminder = REMINDER_DAYS.get(sub.frequency.label, 1)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{_uid(sub)}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{start + dt.timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_escape(f'{sub.name} due ({amount})')}",
            f"DESCRIPTION:{_escape(f'Expected every {sub.frequency.label}. Last charged {sub.last}.')}",
            "TRANSP:TRANSPARENT",
        ]
        rule = RULES.get(sub.frequency.label)
        if rule and rule.startswith("FREQ=MONTHLY") and start.day > 28:
            # Without this, a renewal on the 31st would skip every shorter month.
            rule += f";BYMONTHDAY={start.day},-1;BYSETPOS=1"
        if rule:
            lines.append(f"RRULE:{rule}")
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(f'{sub.name} is due soon')}",
            f"TRIGGER:-P{reminder}D",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)
