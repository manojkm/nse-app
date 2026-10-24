# NSE · BSE Live

An **MCP server** and a **web dashboard** for Indian stock market data (NSE & BSE).

- Ask Claude (or VS Code / Cursor) things like *"What does the NIFTY option chain say?"*, *"Did FIIs buy or sell today?"* or *"Give me a scorecard for TCS"*.
- Open the dashboard for five views:
  - **Market**: indices, market breadth, FII/DII snapshot, movers, most active, 52-week highs/lows, price shockers, commodities, mutual funds.
  - **Stock**: price chart with 50/200-day averages, scorecard, analyst ratings and target-price upside, volume profile, peer comparison, corporate actions, news.
  - **Options**: put-call ratio, max pain, OI support/resistance, expected move, OI build-up per strike, for NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY and F&O stocks.
  - **FII / DII**: daily institutional flows with a running history chart.
  - **IPO & News**: open, upcoming and listed IPOs, plus market news.

Based on [GirishKumarDV/Live-NSE-BSE-MCP](https://github.com/GirishKumarDV/Live-NSE-BSE-MCP), rebuilt on the official MCP Python SDK (v2) and extended from 14 to 26 tools.

## Data sources

| Source | Used for | Key needed |
|---|---|---|
| [IndianAPI](https://indianapi.in/) | Quotes, company details, price history, analyst ratings, indices, IPOs, news, mutual funds | Yes (`ISE_API_KEY`) |
| [NSE official MCP](https://www.nseindia.com/nse-mcp) | Market breadth, end-of-day history, volume analysis, peer comparison, corporate actions | No |
| nseindia.com website | FII/DII flows, option chains | No, but usually blocked (see below) |

## Getting FII/DII and option-chain data

NSE has no official API for FII/DII or option chains, and nseindia.com blocks automated requests with bot protection. This app makes plain, honestly identified requests and **does not try to get around that protection**. So with live data, the Options and FII/DII tabs will usually show "unavailable". All the analytics (PCR, max pain, OI build-up, flow summaries) are built and tested, and work in demo mode (`--demo`).

Official ways to get this data:

- **Option chains:** broker APIs give option chains to their account holders, e.g. Upstox, Dhan, Zerodha Kite Connect, Angel One SmartAPI. A broker adapter can plug into `nse_mcp/nse_site.py`, since the analytics already accept the standard strike / CE / PE format.
- **FII/DII:** NSE publishes the daily figures on its website for people to read; NSDL publishes FPI flows at fpi.nsdl.co.in.

**About footprint charts:** true footprint charts need tick-by-tick trades with buyer/seller side. That data isn't publicly available from any of these sources. The **volume profile** is the closest honest alternative: it shows where volume traded by price (point of control, value area), with volume split into up-day vs down-day.

![Market view](docs/dashboard.png)

![Option chain analytics](docs/options.png)

![Stock scorecard and analyst ratings](docs/stock-insights.png)

---

## 1. Install

Requires Python 3.10+.

```bash
git clone https://github.com/manojkm/nse-app.git
cd nse-app
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -e .
```

## 2. Add your API key

```bash
cp env.example .env      # Windows: copy env.example .env
```

Open `.env` and set:

```
ISE_API_KEY=your_indianapi_key
```

`.env` is git-ignored, so your key is never committed. **Without a key the app runs in demo mode** with sample data (marked "Demo data" in the UI).

## 3. Run the dashboard

```bash
python -m nse_mcp http
```

Open <http://127.0.0.1:8000>. The same process also serves MCP over HTTP at `http://127.0.0.1:8000/mcp`.

Options: `--port 9000`, `--host 0.0.0.0`, `--demo` (force sample data).

---

## Use it from Claude Desktop

Edit the config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "nse-bse": {
      "command": "/full/path/to/nse-app/.venv/bin/python",
      "args": ["-m", "nse_mcp"],
      "env": { "ISE_API_KEY": "your_indianapi_key" }
    }
  }
}
```

On Windows the command is `C:\\path\\to\\nse-app\\.venv\\Scripts\\python.exe`. Restart Claude Desktop afterwards.

## Use it from Claude Code

```bash
claude mcp add nse-bse --env ISE_API_KEY=your_indianapi_key -- /full/path/to/nse-app/.venv/bin/python -m nse_mcp
```

## Use it from VS Code / Cursor (HTTP)

Start `python -m nse_mcp http`, then add the server:

**VS Code** (`.vscode/mcp.json`):

```json
{ "servers": { "nse-bse": { "type": "http", "url": "http://127.0.0.1:8000/mcp" } } }
```

**Cursor** (`~/.cursor/mcp.json`):

```json
{ "mcpServers": { "nse-bse": { "url": "http://127.0.0.1:8000/mcp" } } }
```

---

## Tools

| Tool | What it returns |
|---|---|
| `get_option_chain` | PCR, max pain, OI support/resistance, build-up per strike, expected move |
| `get_fii_dii` | FII/FPI and DII buy/sell/net with summary and saved history |
| `get_stock_scorecard` | Trend, momentum, 52-week position, volume and analyst signals, each explained |
| `get_analyst_view` | Consensus rating, rating breakdown, target price range and upside |
| `get_volume_profile` | Point of control, value area, buy/sell volume by price |
| `get_market_breadth` | Advances vs declines and A/D ratio |
| `compare_stocks` | Return and max drawdown for up to 10 symbols |
| `get_corporate_actions` | Dividends, bonuses, splits |
| `get_indices` / `get_ipos` / `get_market_news` / `get_api_usage` | Index levels, IPOs, news, your IndianAPI quota |
| `get_trending_stocks` | Top gainers and losers |
| `get_nse_most_active` / `get_bse_most_active` | Most traded stocks by volume |
| `get_52_week_high_low` | Stocks near their 52-week high/low |
| `get_price_shockers` | Sharp short-term price moves |
| `get_commodities` | Commodity futures (gold, silver, crude…) |
| `get_stock_data` | Full company details by name or symbol |
| `search_industry` | Companies in an industry/sector |
| `get_historical_data` | Price history with 50/200-day averages |
| `get_historical_stats` | Results, balance sheet, cash flow, ratios, shareholding |
| `get_analyst_recommendations` | Target prices and buy/hold/sell breakdown |
| `get_stock_forecasts` | Forecasts/actuals for EPS, revenue, ROE… |
| `get_mutual_funds` | Mutual fund NAVs and returns by category |
| `search_mutual_funds` | Search fund schemes |

The dashboard uses the same tools through `GET /api/tools/<name>?param=value`.

## API quota

IndianAPI plans have request limits. To save quota:

- Identical requests are cached for 60 seconds (`ISE_CACHE_TTL`).
- Dashboard sections load only when you scroll to them.
- Auto-refresh is **off** by default and only runs while the market is open.
- The NSE sources (breadth, options, FII/DII, history) don't use your IndianAPI quota at all.

## FII/DII history

NSE publishes only the latest day's FII/DII numbers. Each time you open the FII/DII view, that day is saved to `data/fii_dii_history.json` (git-ignored), so the chart grows day by day.

## Configuration

| Variable | Default | |
|---|---|---|
| `ISE_API_KEY` | – | IndianAPI key. Empty = demo mode |
| `ISE_API_BASE_URL` | `https://stock.indianapi.in` | |
| `ISE_HTTP_HOST` / `ISE_HTTP_PORT` | `127.0.0.1` / `8000` | |
| `ISE_REQUEST_TIMEOUT` | `30` | Seconds |
| `ISE_CACHE_TTL` | `60` | Seconds, `0` disables |
| `ISE_DEMO_MODE` | – | `1` forces sample data |
| `ISE_LOG_LEVEL` | `INFO` | |

## Project layout

```
nse_mcp/
  tools.py        the 26 tools (single source of truth for MCP + REST)
  analytics.py    option chain, FII/DII, volume profile, analyst, scorecard maths
  server.py       MCP server, REST API, static hosting
  sources.py      bundles the three data sources
  api.py          IndianAPI client (+ cache) and demo source
  nse_official.py client for NSE's official MCP servers
  nse_site.py     nseindia.com client (FII/DII, option chain)
  sample_data.py  demo-mode data
  config.py       settings from env / .env
web/              dashboard (plain HTML/CSS/ES modules, no build step)
  js/views/       one module per tab: market, stock, options, flows, ipo
tests/            pytest suite
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

The dashboard has no build step: edit files in `web/` and reload the page.

## Disclaimer

Market data may be delayed. Nothing here is investment advice.
