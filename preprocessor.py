import re
from datetime import datetime, time as dt_time

import pandas as pd
from dateutil import parser as date_parser

_INVIS = "\u200e\u200f"  # LRM / RLM (common in WhatsApp exports)

# ---------------------------------------------------------------------------
# Line patterns
# ---------------------------------------------------------------------------
# Anything inside [...] is parsed as "date side, time side" (time matched from the end).
# Name/message after ``]``: see ``_split_bracket_rest`` (handles ``Name: msg`` and ``A: B: msg``).
PATTERN_BRACKET_LINE = re.compile(r"^\[([^\]\n]+)\]\s*(.+)$")

# Time suffix inside the bracket: ", H:MM[:SS] [AM|pm]" at end of the inner string.
_INNER_TIME_SUFFIX = re.compile(
    r",\s*(\d{1,2}):(\d{2})(?::(\d{2}))?(?:[\s\u202f\u00a0]*([AaPp][Mm]))?\s*$"
)

# iOS / US: M/D/YY, H:MM[:SS] [am|pm] - Name: message  (same separator between date parts)
PATTERN_DASH_NUMERIC = re.compile(
    r"^(\d{1,2})([./-])(\d{1,2})\2(\d{2,4}),\s*"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*"
    r"(?:([AaPp][Mm]))?"
    r"\s*-\s*"
    r"(.+)$"
)

# Rare: "May 7, 2024, 3:00 pm - Name: message" (comma before time, dash before name)
PATTERN_DASH_TEXTUAL_DATE = re.compile(
    r"^(.+),\s*"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*"
    r"(?:([AaPp][Mm]))?"
    r"\s*-\s*"
    r"(.+)$"
)


def _strip_leading_noise(raw_line: str) -> str:
    return raw_line.lstrip(_INVIS + "\ufeff")


def _split_bracket_rest(rest: str):
    """
    Split ``rest`` (everything after the closing ``]``) into sender name and message body.

    If there are several ``": "`` sequences (colon + ASCII space), the **last** one usually
    separates a multi-part display name from the message (e.g. ``John: Doe: hello``).
    If there is only one ``": "``, it separates ``Name`` from ``message`` as usual.
    If there is no ``": "``, split on the first bare ``:``.
    """
    rest = rest.strip()
    n = rest.count(": ")
    if n >= 2:
        return rest.rsplit(": ", 1)
    if n == 1:
        idx = rest.find(": ")
        return rest[:idx], rest[idx + 2 :]
    m = re.match(r"^([^:]+):(.*)$", rest)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _split_bracket_inner(inner: str):
    """
    Split ``inner`` (content between ``[`` and ``]``) into date text, time fields, meridiem.
    Handles commas inside textual dates (e.g. ``May 7, 2024, 3:00 pm``) by anchoring time at the end.
    """
    inner = inner.strip()
    m = _INNER_TIME_SUFFIX.search(inner)
    if not m:
        return None
    date_part = inner[: m.start()].strip().rstrip(",").strip()
    if not date_part:
        return None
    hh, mm, ss, meridiem = m.group(1), m.group(2), m.group(3), m.group(4)
    return date_part, hh, mm, ss, meridiem


def _year_4(y_raw):
    y = int(y_raw)
    if y >= 100:
        return y
    return 2000 + y


def _hour_12_to_24(hour, meridiem):
    """Convert clock hour to 24h when am/pm is present; otherwise pass through."""
    if not meridiem:
        return hour
    m = meridiem.strip().lower()
    h = hour
    if m == "am":
        if h == 12:
            return 0
        return h
    if m == "pm":
        if h == 12:
            return 12
        return h + 12
    return h


def _parse_date_part_to_ymd(date_part: str, dayfirst: bool):
    """Parse date-only text (numeric, ISO, dotted, dashed, many English month forms)."""
    s = date_part.strip()
    if not s:
        return None
    # Explicit ISO / year-first numeric (avoids dateutil quirks with dayfirst=True)
    m = re.match(r"^(\d{4})([./-])(\d{1,2})\2(\d{1,2})\s*$", s)
    if m:
        return int(m.group(1)), int(m.group(3)), int(m.group(4))
    try:
        dt = date_parser.parse(s, dayfirst=dayfirst, yearfirst=False)
        return dt.year, dt.month, dt.day
    except (ValueError, OverflowError, TypeError):
        return None


def _pair_for_dayfirst_inference(date_part: str):
    """
    Return (a, b) as first two *day/month* numbers for ambiguous ordering, or None if not applicable.
    ISO ``YYYY-MM-DD`` / ``YYYY/MM/DD`` and month-name dates are skipped (ordering is explicit or different).
    """
    s = date_part.strip()
    if re.match(r"^\d{4}([./-])\d{1,2}\1\d{1,2}\s*$", s):
        return None
    if re.search(r"[A-Za-z]{3,}", s):
        return None
    m = re.match(r"^(\d{1,2})([./-])(\d{1,2})\2(\d{2,4})\s*$", s)
    if m:
        return int(m.group(1)), int(m.group(3))
    return None


def _gather_date_pairs(data, fmt):
    """Collect (first, second) numeric date parts from every matching line in the export."""
    pairs = []
    for raw in data.splitlines():
        line = _strip_leading_noise(raw).strip()
        if not line:
            continue
        if fmt == "bracket":
            m = PATTERN_BRACKET_LINE.match(line)
            if not m:
                continue
            split = _split_bracket_inner(m.group(1))
            if not split:
                continue
            date_part = split[0]
            pr = _pair_for_dayfirst_inference(date_part)
            if pr is None:
                continue
            a, b = pr
        elif fmt == "dash_text":
            m = PATTERN_DASH_TEXTUAL_DATE.match(line)
            if not m:
                continue
            pr = _pair_for_dayfirst_inference(m.group(1))
            if pr is None:
                continue
            a, b = pr
        else:
            m = PATTERN_DASH_NUMERIC.match(line)
            if not m:
                continue
            a, b = int(m.group(1)), int(m.group(3))
        pairs.append((a, b))
    return pairs


def _infer_dayfirst_from_samples(pairs, default):
    """
    Decide whether ambiguous numeric dates are day-first (dd/mm/...) or month-first (mm/dd/...),
    using every collected (day-or-month, month-or-day) pair from the export.

    When the first number is > 12 it cannot be a month in mm/dd → day-first.
    When the second number is > 12 it cannot be a month in dd/mm → month-first.
    """
    dm_votes = 0
    md_votes = 0
    for a, b in pairs:
        if a > 12:
            dm_votes += 1
        elif b > 12:
            md_votes += 1
    if dm_votes > md_votes:
        return True
    if md_votes > dm_votes:
        return False
    return default


def _detect_format(data):
    """
    Prefer bracket exports when present; else iOS-style dash (numeric or textual date).
    Scans the entire export.
    """
    saw_bracket = False
    saw_dash_num = False
    saw_dash_text = False
    for raw in data.splitlines():
        line = _strip_leading_noise(raw).strip()
        if not line:
            continue
        mb = PATTERN_BRACKET_LINE.match(line)
        if mb and _split_bracket_inner(mb.group(1)):
            saw_bracket = True
        if PATTERN_DASH_NUMERIC.match(line):
            saw_dash_num = True
        if PATTERN_DASH_TEXTUAL_DATE.match(line) and not PATTERN_DASH_NUMERIC.match(line):
            saw_dash_text = True
    if saw_bracket:
        return "bracket"
    if saw_dash_num:
        return "dash_num"
    if saw_dash_text:
        return "dash_text"
    return "bracket"


def _build_datetime_from_date_and_clock(ymd, hh, mm, ss, meridiem):
    y, mo, d = ymd
    hour = _hour_12_to_24(int(hh), meridiem)
    sec = int(ss) if ss else 0
    return datetime(y, mo, d, hour, int(mm), sec)


def _row_from_dt(dt: datetime, name: str, message: str):
    date_str = dt.strftime("%d/%m/%Y")
    time_str = dt.strftime("%H:%M:%S")
    return [date_str, time_str, name, message.replace("\u200e", "").strip()]


def _finalize_dataframe(rows):
    df = pd.DataFrame(rows, columns=["Date", "Time", "Name", "Message"])
    df["Datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], dayfirst=True)
    df["Year"] = df["Datetime"].dt.year
    df["Day"] = df["Datetime"].dt.day
    df["Month"] = df["Datetime"].dt.month_name()
    df["Hour"] = df["Datetime"].dt.hour
    df["Minute"] = df["Datetime"].dt.minute
    df.drop("Date", axis=1, inplace=True)
    df.drop("Time", axis=1, inplace=True)
    return df


def _preprocess_bracket(data, dayfirst):
    rows = []
    current = None

    def flush():
        nonlocal current
        if current:
            text = "\n".join(current[2]).replace("\u200e", "").strip()
            rows.append(_row_from_dt(current[0], current[1], text))
            current = None

    for raw_line in data.splitlines():
        line = _strip_leading_noise(raw_line)
        m = PATTERN_BRACKET_LINE.match(line)
        if m:
            inner, rest = m.groups()
            split = _split_bracket_inner(inner)
            if not split:
                if current is not None:
                    current[2].append(raw_line.replace("\u200e", ""))
                continue
            date_part, hh, mm, ss, meridiem = split
            ymd = _parse_date_part_to_ymd(date_part, dayfirst)
            if ymd is None:
                if current is not None:
                    current[2].append(raw_line.replace("\u200e", ""))
                continue
            try:
                dt = _build_datetime_from_date_and_clock(ymd, hh, mm, ss, meridiem)
            except ValueError:
                if current is not None:
                    current[2].append(raw_line.replace("\u200e", ""))
                continue
            name, message = _split_bracket_rest(rest)
            if name is None:
                if current is not None:
                    current[2].append(raw_line.replace("\u200e", ""))
                continue
            flush()
            message = (message or "").replace("\u200e", "").strip()
            current = [dt, name, [message] if message else []]
            continue
        if current is not None:
            current[2].append(raw_line.replace("\u200e", ""))

    flush()
    return _finalize_dataframe(rows)


def _preprocess_dash_numeric(data, dayfirst):
    rows = []
    current = None

    def flush():
        nonlocal current
        if current:
            text = "\n".join(current[8]).replace("\u200e", "").strip()
            first, second, y_raw = current[0], current[1], current[2]
            if dayfirst:
                d, m = int(first), int(second)
            else:
                m, d = int(first), int(second)
            y = _year_4(y_raw)
            try:
                t = dt_time(
                    _hour_12_to_24(int(current[3]), current[6]),
                    int(current[4]),
                    int(current[5]) if current[5] else 0,
                )
                dt = datetime.combine(datetime(y, m, d).date(), t)
            except ValueError:
                current = None
                return
            row = _row_from_dt(dt, current[7], text)
            msg = row[3]
            if msg and msg.strip().upper() != "NULL":
                rows.append(row)
            current = None

    for raw_line in data.splitlines():
        line = _strip_leading_noise(raw_line)
        m = PATTERN_DASH_NUMERIC.match(line)
        if m:
            flush()
            p1, _sep, p2, y, hh, mm, ss, meridiem, tail = m.groups()
            name, message = _split_bracket_rest(tail)
            if name is None:
                continue
            message = (message or "").replace("\u200e", "").strip()
            current = [p1, p2, y, hh, mm, ss, meridiem, name, [message] if message else []]
        elif current is not None:
            current[8].append(raw_line.replace("\u200e", ""))

    flush()
    return _finalize_dataframe(rows)


def _preprocess_dash_textual(data, dayfirst):
    """Dash lines whose leading segment is a textual or mixed date (often includes a comma in the date)."""
    rows = []
    current = None

    def flush():
        nonlocal current
        if current:
            text = "\n".join(current[6]).replace("\u200e", "").strip()
            date_part, hh, mm, ss, meridiem, name = (
                current[0],
                current[1],
                current[2],
                current[3],
                current[4],
                current[5],
            )
            ymd = _parse_date_part_to_ymd(date_part, dayfirst)
            if ymd is None:
                current = None
                return
            try:
                dt = _build_datetime_from_date_and_clock(ymd, hh, mm, ss, meridiem)
            except ValueError:
                current = None
                return
            row = _row_from_dt(dt, name, text)
            if row[3] and row[3].strip().upper() != "NULL":
                rows.append(row)
            current = None

    for raw_line in data.splitlines():
        line = _strip_leading_noise(raw_line)
        m = PATTERN_DASH_TEXTUAL_DATE.match(line)
        if m and not PATTERN_DASH_NUMERIC.match(line):
            flush()
            date_part, hh, mm, ss, meridiem, tail = m.groups()
            name, message = _split_bracket_rest(tail)
            if name is None:
                continue
            message = (message or "").replace("\u200e", "").strip()
            current = [date_part, hh, mm, ss, meridiem, name, [message] if message else []]
        elif current is not None:
            current[6].append(raw_line.replace("\u200e", ""))

    flush()
    return _finalize_dataframe(rows)


def preprocess(data):
    fmt = _detect_format(data)
    pairs = _gather_date_pairs(data, fmt)
    default_dayfirst = fmt == "bracket"
    dayfirst = _infer_dayfirst_from_samples(pairs, default=default_dayfirst)
    if fmt == "dash_num":
        return _preprocess_dash_numeric(data, dayfirst)
    if fmt == "dash_text":
        return _preprocess_dash_textual(data, dayfirst)
    return _preprocess_bracket(data, dayfirst)
