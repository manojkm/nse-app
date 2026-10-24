from pathlib import Path

import pytest
from starlette.testclient import TestClient

from nse_mcp import analytics, imports
from nse_mcp.api_errors import APIError
from nse_mcp.config import Settings
from nse_mcp.server import build_http_app
from nse_mcp.sources import demo_sources
from nse_mcp.tools import TOOLS

FIX = Path(__file__).parent / "fixtures"
OC_NAME = "option-chain-ED-NIFTY-28-Oct-2026.csv"
OC = (FIX / OC_NAME).read_text(encoding="utf-8")
FII = (FIX / "fii-dii.csv").read_text(encoding="utf-8")


def test_filename_gives_symbol_and_expiry():
    assert imports.parse_filename(OC_NAME) == {"symbol": "NIFTY", "expiry": "28-Oct-2026"}
    assert imports.parse_filename("option-chain-EQ-RELIANCE-27-Nov-2026 (1).csv")["symbol"] == "RELIANCE"


def test_option_chain_csv_parses_nse_layout():
    parsed = imports.parse_option_chain_csv(OC, filename=OC_NAME)
    assert parsed["symbol"] == "NIFTY" and parsed["expiry"] == "28-Oct-2026"
    legs = {(d["strikePrice"], d["optionType"]): d for d in parsed["data"]}
    assert legs[(24900.0, "CE")]["openInterest"] == 240000      # Indian grouping "2,40,000"
    assert legs[(24600.0, "PE")]["openInterest"] == 195000
    assert legs[(24900.0, "PE")]["changeinOpenInterest"] == -2000
    assert (25100.0, "CE") not in legs                          # row of dashes is skipped

    r = analytics.option_chain_analysis({"data": parsed["data"]}, "NIFTY")
    assert r["resistance"][0]["strike"] == 24900                # biggest call OI
    assert r["support"][0]["strike"] == 24600                   # biggest put OI
    assert 24800 <= r["spot"] <= 24900                          # estimated from where CE and PE premiums cross


def test_option_chain_csv_uses_given_spot():
    parsed = imports.parse_option_chain_csv(OC, filename=OC_NAME, spot=24853.15)
    r = analytics.option_chain_analysis({"data": parsed["data"]}, "NIFTY")
    assert r["spot"] == 24853.15 and r["atm_strike"] == 24850


@pytest.mark.parametrize("bad,msg", [("a,b\n1,2", "STRIKE"), ("STRIKE,LTP\n100,2", "OI columns")])
def test_option_chain_csv_errors_are_clear(bad, msg):
    with pytest.raises(imports.ImportProblem, match=msg):
        imports.parse_option_chain_csv(bad)


def test_fii_dii_csv():
    days = imports.parse_fii_dii_csv(FII)
    assert [d["date"] for d in days] == ["23-Oct-2026", "24-Oct-2026"]
    assert days[1]["fii"] == {"buy": 12876.4, "sell": 15112.95, "net": -2236.55}
    with pytest.raises(imports.ImportProblem, match="CATEGORY"):
        imports.parse_fii_dii_csv("x,y\n1,2")


class BlockedNSE:
    demo = False

    async def fii_dii(self):
        raise APIError("blocked")

    async def option_chain(self, symbol):
        raise APIError("blocked")

    async def aclose(self):
        return None


def blocked_sources():
    src = demo_sources()
    src.nse = BlockedNSE()
    src._fii_history = []
    return src


def test_upload_endpoints_and_fallback():
    src = blocked_sources()
    settings = Settings.from_env()
    with TestClient(build_http_app(settings, src), base_url="http://127.0.0.1:8000") as http:
        # Nothing imported yet: a helpful message, not a crash.
        r = http.get("/api/tools/get_option_chain?symbol=NIFTY")
        assert r.status_code == 404 and "import" in r.json()["error"].lower()

        r = http.post(f"/api/import/option-chain?filename={OC_NAME}", content=OC.encode())
        assert r.status_code == 200, r.text
        assert r.json()["data"]["symbol"] == "NIFTY" and r.json()["data"]["spot_estimated"] is True

        # The tool (and so Claude) now falls back to the import.
        r = http.get("/api/tools/get_option_chain?symbol=NIFTY").json()["data"]
        assert r["source"].startswith("Imported CSV") and r["resistance"][0]["strike"] == 24900

        assert http.post("/api/import/option-chain?filename=x.csv", content=b"a,b\n1,2").status_code == 400

        r = http.post("/api/import/fii-dii", content=FII.encode())
        assert r.status_code == 200 and r.json()["data"]["imported_days"] == 2
        r = http.get("/api/tools/get_fii_dii").json()["data"]
        assert r["source"] == "Imported CSV" and r["date"] == "24-Oct-2026" and r["fii"]["net"] == -2236.55
        assert [h["date"] for h in r["history"]] == ["23-Oct-2026", "24-Oct-2026"]


async def test_tool_message_when_nothing_imported():
    with pytest.raises(APIError, match="import"):
        await TOOLS["get_fii_dii"].fn(blocked_sources())
