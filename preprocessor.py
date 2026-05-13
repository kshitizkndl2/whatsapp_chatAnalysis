import re
from datetime import datetime

import pandas as pd

_INVIS = "\u200e\u200f"  # LRM / RLM (common in WhatsApp exports)

# [DD/MM/YYYY, HH:MM:SS] Name: message
PATTERN_BRACKET = re.compile(
    r"^\[(\d{2}/\d{2}/\d{4}),\s*(\d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$"
)

# M/D/YY, H:MM[:SS] - Name: message  (WhatsApp export without brackets)
PATTERN_DASH = re.compile(
    r"^(\d{1,2})/(\d{1,2})/(\d{2,4}),\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*-\s*([^:]+):\s*(.*)$"
)


def _detect_format(data):
    """Use dash parser only when the chat looks like the unbracketed export."""
    sample = data.splitlines()[:800]
    saw_bracket = False
    saw_dash = False
    for raw in sample:
        line = raw.lstrip(_INVIS + "\ufeff").strip()
        if not line:
            continue
        if PATTERN_BRACKET.match(line):
            saw_bracket = True
        if PATTERN_DASH.match(line):
            saw_dash = True
    if saw_bracket:
        return "bracket"
    if saw_dash:
        return "dash"
    return "bracket"


def _year_4(y_raw):
    y = int(y_raw)
    if y >= 100:
        return y
    return 2000 + y


def _dash_groups_to_row(month, day, y_raw, hour, minute, sec, name, message):
    month, day = int(month), int(day)
    hour, minute = int(hour), int(minute)
    sec = int(sec) if sec else 0
    year = _year_4(y_raw)
    dt = datetime(year, month, day, hour, minute, sec)
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


def _preprocess_bracket(data):
    rows = []
    current = None

    def flush():
        nonlocal current
        if current:
            text = "\n".join(current[3]).replace("\u200e", "").strip()
            rows.append([current[0], current[1], current[2], text])
            current = None

    for raw_line in data.splitlines():
        line = raw_line.lstrip(_INVIS + "\ufeff")
        match = PATTERN_BRACKET.match(line)
        if match:
            flush()
            date, time, name, message = match.groups()
            message = message.replace("\u200e", "").strip()
            current = [date, time, name, [message] if message else []]
        elif current is not None:
            current[3].append(raw_line.replace("\u200e", ""))

    flush()
    return _finalize_dataframe(rows)


def _preprocess_dash(data):
    rows = []
    current = None

    def flush():
        nonlocal current
        if current:
            text = "\n".join(current[7]).replace("\u200e", "").strip()
            row = _dash_groups_to_row(
                current[0],
                current[1],
                current[2],
                current[3],
                current[4],
                current[5],
                current[6],
                text,
            )
            msg = row[3]
            if msg and msg.strip().upper() != "NULL":
                rows.append(row)
            current = None

    for raw_line in data.splitlines():
        line = raw_line.lstrip(_INVIS + "\ufeff")
        match = PATTERN_DASH.match(line)
        if match:
            flush()
            m, d, y, hh, mm, ss, name, message = match.groups()
            message = message.replace("\u200e", "").strip()
            current = [m, d, y, hh, mm, ss, name, [message] if message else []]
        elif current is not None:
            current[7].append(raw_line.replace("\u200e", ""))

    flush()
    return _finalize_dataframe(rows)


def preprocess(data):
    fmt = _detect_format(data)
    if fmt == "dash":
        return _preprocess_dash(data)
    return _preprocess_bracket(data)
