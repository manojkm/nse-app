"""Parse CSV files the user downloads from nseindia.com in their own browser.

- Option chain: the "Download (.csv)" button on https://www.nseindia.com/option-chain
- FII/DII: the download on NSE's FII/DII activity report page

Columns are found by header name, not position, so small layout changes on NSE's
side don't break the import. Every failure raises ImportProblem with a message
that says what was expected.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

from .analytics import num

MAX_BYTES = 3 * 1024 * 1024


class ImportProblem(ValueError):
    pass


def _rows(text: str) -> list[list[str]]:
    if len(text.encode("utf-8", "ignore")) > MAX_BYTES:
        raise ImportProblem("File is too large (max 3 MB).")
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), dialect)]


def _norm(h: str) -> str:
    return re.sub(r"[^a-z]", "", h.lower())


# ---------------------------------------------------------------- option chain

FIELD_ALIASES = {
    "openInterest": {"oi", "openinterest"},
    "changeinOpenInterest": {"chnginoi", "changeinoi", "chngoi", "oichange", "changeinopeninterest"},
    "totalTradedVolume": {"volume", "vol", "totaltradedvolume"},
    "impliedVolatility": {"iv", "impliedvolatility"},
    "lastPrice": {"ltp", "lastprice", "lasttradedprice"},
    "change": {"chng", "netchng", "change", "netchange"},
}


def _field(header: str) -> str | None:
    h = _norm(header)
    for prefix in ("calls", "call", "ce", "puts", "put", "pe"):
        if h.startswith(prefix) and len(h) > len(prefix):
            h = h[len(prefix):]
            break
    for field, names in FIELD_ALIASES.items():
        if h in names:
            return field
    return None


def parse_filename(filename: str) -> dict[str, str]:
    """option-chain-ED-NIFTY-28-Oct-2026.csv -> {'symbol': 'NIFTY', 'expiry': '28-Oct-2026'}"""
    out: dict[str, str] = {}
    base = re.sub(r"\.csv$", "", filename or "", flags=re.I)
    m = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4})", base)
    if m:
        out["expiry"] = m.group(1)
    m = re.search(r"option-chain-(?:ED|EQ|ID)?-?([A-Z0-9&]+)", base, flags=re.I)
    if m:
        out["symbol"] = m.group(1).upper()
    return out


def parse_option_chain_csv(text: str, filename: str = "", symbol: str = "", expiry: str = "",
                           spot: float | None = None) -> dict[str, Any]:
    rows = _rows(text)
    meta = parse_filename(filename)
    symbol = (symbol or meta.get("symbol") or "").upper()
    expiry = expiry or meta.get("expiry") or ""

    # Spot is sometimes printed above the table, e.g. "Underlying Index: NIFTY 24853.15 As on ..."
    if spot is None:
        for row in rows[:6]:
            line = " ".join(row)
            m = re.search(r"underlying[^0-9]*?([0-9][0-9,]*\.?[0-9]*)", line, flags=re.I)
            if m:
                spot = num(m.group(1))
                break

    hdr_i = next((i for i, r in enumerate(rows) if any(_norm(c) in ("strike", "strikeprice") for c in r)), None)
    if hdr_i is None:
        raise ImportProblem("Couldn't find a STRIKE column. Is this the option chain CSV from nseindia.com?")
    header = rows[hdr_i]
    strike_col = next(i for i, c in enumerate(header) if _norm(c) in ("strike", "strikeprice"))
    calls = {f: i for i, c in enumerate(header[:strike_col]) if (f := _field(c))}
    puts = {f: strike_col + 1 + i for i, c in enumerate(header[strike_col + 1:]) if (f := _field(c))}
    if "openInterest" not in calls or "openInterest" not in puts:
        raise ImportProblem("Couldn't find OI columns on both sides of STRIKE (calls left, puts right).")

    def cell(row: list[str], i: int) -> float | None:
        return num(row[i]) if i < len(row) else None

    data = []
    for row in rows[hdr_i + 1:]:
        if strike_col >= len(row):
            continue
        k = cell(row, strike_col)
        if k is None:
            continue
        for side, cols in (("CE", calls), ("PE", puts)):
            leg = {f: cell(row, i) or 0 for f, i in cols.items()}
            if not any(leg.values()):
                continue
            data.append({"strikePrice": k, "expiryDate": expiry or "Imported", "optionType": side,
                         **leg, **({"underlyingValue": spot} if spot else {})})
    if not data:
        raise ImportProblem("The file has a STRIKE column but no option rows with numbers.")
    return {"data": data, "symbol": symbol, "expiry": expiry or "Imported", "spot": spot, "rows": len(data)}


# ---------------------------------------------------------------- FII / DII

def _date(s: str) -> str:
    s = s.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d-%B-%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%d-%b-%Y")
        except ValueError:
            continue
    return s


def parse_fii_dii_csv(text: str) -> list[dict[str, Any]]:
    """Returns one dict per day: {date, fii: {buy, sell, net}, dii: {...}}, oldest first."""
    rows = _rows(text)
    hdr_i = next((i for i, r in enumerate(rows) if any("categ" in _norm(c) for c in r)
                  and any("date" in _norm(c) for c in r)), None)
    if hdr_i is None:
        raise ImportProblem("Couldn't find CATEGORY and DATE columns. Is this the FII/DII CSV from nseindia.com?")
    header = [_norm(c) for c in rows[hdr_i]]

    def col(*keys: str) -> int | None:
        return next((i for i, h in enumerate(header) if any(k in h for k in keys)), None)

    ci, di = col("categ"), col("date")
    bi, si, ni = col("buy"), col("sell"), col("net")
    if bi is None or si is None:
        raise ImportProblem("Couldn't find BUY and SELL value columns.")

    days: dict[str, dict[str, Any]] = {}
    for row in rows[hdr_i + 1:]:
        if len(row) <= max(i for i in (ci, di, bi, si) if i is not None):
            continue
        cat = row[ci].upper()
        key = "fii" if ("FII" in cat or "FPI" in cat) else "dii" if "DII" in cat else None
        if not key or not row[di]:
            continue
        buy, sell = num(row[bi]), num(row[si])
        net = num(row[ni]) if ni is not None and ni < len(row) else None
        if net is None and buy is not None and sell is not None:
            net = round(buy - sell, 2)
        day = days.setdefault(_date(row[di]), {"date": _date(row[di]), "fii": None, "dii": None})
        day[key] = {"buy": buy, "sell": sell, "net": net}
    if not days:
        raise ImportProblem("No FII or DII rows found in the file.")

    def when(d: str) -> datetime:
        try:
            return datetime.strptime(d, "%d-%b-%Y")
        except ValueError:
            return datetime.min

    return sorted(days.values(), key=lambda d: when(d["date"]))
