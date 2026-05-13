import re

import pandas as pd

_INVIS = "\u200e\u200f"  # LRM / RLM (common in WhatsApp exports)

def preprocess(data):
    # Message may span multiple lines; only lines starting a new message match this.
    pattern = re.compile(
        r"^\[(\d{2}/\d{2}/\d{4}),\s*(\d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$"
    )

    rows = []
    current = None  # [date, time, name, list of message line strings]

    def flush():
        nonlocal current
        if current:
            text = "\n".join(current[3]).replace("\u200e", "").strip()
            rows.append([current[0], current[1], current[2], text])
            current = None

    for raw_line in data.splitlines():
        line = raw_line.lstrip(_INVIS)
        match = pattern.match(line)
        if match:
            flush()
            date, time, name, message = match.groups()
            message = message.replace("\u200e", "").strip()
            current = [date, time, name, [message] if message else []]
        elif current is not None:
            current[3].append(raw_line.replace("\u200e", ""))

    flush()
    df = pd.DataFrame(rows, columns=["Date", "Time", "Name", "Message"])
    df["Datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], dayfirst=True)
    df["Year"] = df["Datetime"].dt.year
    df["Day"] = df["Datetime"].dt.day
    df["Month"] = df["Datetime"].dt.month_name()
    df["Hour"] = df["Datetime"].dt.hour
    df["Minute"] = df["Datetime"].dt.minute
    df.drop('Date',axis=1,inplace=True)
    df.drop('Time',axis=1,inplace=True)


    return df

