from datetime import date

import pytest

from nse_mcp import analytics as a
from nse_mcp import sample_data as s


def chain(rows):
    """rows: (strike, ce_oi, pe_oi, ce_ltp, pe_ltp)"""
    data = []
    for k, ce, pe, cl, pl in rows:
        data.append({"strikePrice": k, "expiryDate": "30-Oct-2026", "optionType": "CE", "openInterest": ce, "lastPrice": cl,
                     "changeinOpenInterest": 10, "change": 1, "underlyingValue": 100})
        data.append({"strikePrice": k, "expiryDate": "30-Oct-2026", "optionType": "PE", "openInterest": pe, "lastPrice": pl,
                     "changeinOpenInterest": -5, "change": -1, "underlyingValue": 100})
    return {"data": data}


def test_option_chain_core_numbers():
    payload = chain([(90, 10, 300, 11, 1), (100, 100, 100, 3, 3), (110, 400, 20, 1, 11)])
    r = a.option_chain_analysis(payload, "test", today=date(2026, 10, 24))
    assert r["spot"] == 100 and r["atm_strike"] == 100
    assert r["pcr"] == round(420 / 510, 2)
    assert r["resistance"][0]["strike"] == 110   # biggest call OI above spot
    assert r["support"][0]["strike"] == 90       # biggest put OI below spot
    assert r["atm_straddle"] == 6 and r["expected_move_pct"] == 6.0
    assert r["rows"][1]["CE"]["buildup"] == "Long build-up"
    assert r["rows"][1]["PE"]["buildup"] == "Long unwinding"


def test_max_pain_matches_brute_force():
    payload = chain([(90, 10, 300, 0, 0), (100, 100, 100, 0, 0), (110, 400, 20, 0, 0)])
    chains, _, _ = a.normalize_option_chain(payload)
    # writers' payout at 100: calls 90*10, puts 110*20 -> 100+200 = 300; it's the minimum here
    assert a.max_pain(chains["30-Oct-2026"]) == 100


def test_option_chain_accepts_nested_and_legacy_shapes():
    nested = {"records": {"underlyingValue": 100, "data": [
        {"strikePrice": 100, "expiryDate": "30-Oct-2026", "CE": {"openInterest": 5, "lastPrice": 2}, "PE": {"openInterest": 7, "lastPrice": 2}}]}}
    r = a.option_chain_analysis(nested, "x", today=date(2026, 10, 24))
    assert r["pcr"] == 1.4


def test_expiries_sorted_upcoming_first():
    assert a.sorted_expiries(["25-Nov-2026", "21-Oct-2026", "28-Oct-2026"], date(2026, 10, 24)) == \
        ["28-Oct-2026", "25-Nov-2026", "21-Oct-2026"]


@pytest.mark.parametrize("p,oi,label", [(1, 1, "Long build-up"), (-1, 1, "Short build-up"), (1, -1, "Short covering"), (-1, -1, "Long unwinding")])
def test_buildup(p, oi, label):
    assert a.buildup(p, oi) == label


def test_fii_dii_summary_and_history():
    day = a.fii_dii_summary(s.fii_dii())
    assert day["fii"]["net"] == -2236.55 and day["dii"]["net"] == 3247.35
    assert "absorbed" in day["summary"][1]
    hist = a.merge_history([{"date": "23-Oct-2026", "fii_net": 1, "dii_net": 2}], day)
    assert [h["date"] for h in hist] == ["23-Oct-2026", "24-Oct-2026"]
    assert a.merge_history(hist, day) == hist  # same day is not duplicated


def test_volume_profile_puts_poc_where_volume_is():
    candles = [{"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000}] * 10 + \
              [{"open": 120, "high": 121, "low": 119, "close": 119.5, "volume": 50}] * 2
    vp = a.volume_profile(candles, bins=22)
    assert 99 <= vp["poc"] <= 101
    assert vp["value_area_low"] <= vp["poc"] <= vp["value_area_high"]
    total = sum(b["volume"] for b in vp["bins"])
    assert abs(total - 10_100) < 5
    assert "above the value area" in vp["summary"][2]


def test_analyst_view_and_scorecard():
    view = a.analyst_view(s.target_price("TCS"), price=3412.15)
    assert view["rating_label"] == "Outperform" and view["distribution"]["Buy"] == 9
    assert view["upside_pct"] > 0 and view["sentiment_trend"] == "improving"

    card = a.scorecard(price=3412.15, history=s.historical("TCS", "1yr"), analyst=view,
                       week52=s.nse_week52("TCS"), volume=s.volume_analysis("TCS"))
    assert card["available"] == 5
    assert {x["key"] for x in card["signals"]} == {"trend", "momentum", "range", "volume", "analysts"}
    assert card["overall"] in {"Mostly positive", "Mostly negative", "Mixed"}


def test_scorecard_without_data_is_honest():
    card = a.scorecard(price=None)
    assert card["overall"] == "Not enough data"
    assert all(x["tone"] == "unknown" for x in card["signals"])
