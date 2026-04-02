# CLAUDE.md — DeFi Strategy Dashboard

## What is this project

Interactive dashboard for analyzing a specific DeFi strategy: **deposit ETH as collateral on AAVE v3 → borrow USDT → buy ETH + create Uniswap V3 concentrated LP position → collect trading fees**. The dashboard calculates Health Factor, liquidation risk, runs Monte Carlo P&L simulations, and stress-tests the position under ETH price drops.

The real-world reference is wallet `0x6b0f1267f2c7a633c639fb525a400a55f8d78888`.

## Architecture

Two independent implementations of the same dashboard:

### `index.html` (primary — production)
Single-file static HTML/CSS/JS app. Runs entirely in the browser, no server needed. Deployed on **GitHub Pages** at `https://maslovsa.github.io/defi-strategy-dashboard/`.

- **Plotly.js** (CDN) for all charts
- Pure vanilla JS — no build step, no bundler, no framework
- Dark theme with CSS custom properties (`--bg`, `--surface`, `--accent`, etc.)
- Layout: CSS flexbox — `.sidebar` (300px fixed) + `.main` (flex: 1), responsive stacking below 900px
- All DeFi math is in JS functions at the top of the `<script>` block
- Charts render into `<div>` containers by ID (`#feesChart`, `#pnlChart`, `#componentsChart`, `#stressChart`)
- `runDashboard()` is the main entry point — reads all inputs, calls render functions in sequence

### `app.py` (legacy — local dev)
Streamlit + Plotly Python app. Same logic but server-side. Requires `venv/` with Python 3.12+.
**Not deployed.** Kept as reference / for users who prefer Streamlit locally.

## AAVE v3 Risk Model (critical)

These constants MUST stay accurate — they drive Health Factor and liquidation calculations:

```
AAVE_LT = 0.83           # Liquidation Threshold for ETH on AAVE v3 mainnet
AAVE_MAX_LTV = 0.805     # Max Loan-to-Value for ETH
AAVE_LIQ_PENALTY = 0.05  # 5% liquidation penalty
```

Key formulas:
- `Health Factor = (collateral_value × LT) / borrow_amount`
- `Liquidation Price = borrow_amount / (eth_amount × LT)`
- HF < 1.0 = liquidation triggered

With default params (75.1 ETH at $2,451.98, $100k borrow):
- Starting HF = 1.528
- Liquidation at $1,604.29 (−34.6%)
- At −30% drop: HF ≈ 1.07 (danger zone)
- At −35% drop: HF ≈ 0.99 (liquidated)

**The borrow amount is a separate input (default $100,000), NOT derived from LTV.** The old Streamlit version incorrectly used `collateral × LTV_slider` which gave wrong HF at entry. Don't reintroduce this.

## Dev commands

```bash
# Static version (index.html) — just open in browser
open index.html
# or serve locally:
python3 -m http.server 8501

# Streamlit version (legacy)
source venv/bin/activate
streamlit run app.py

# Deploy — push to main, GitHub Pages auto-deploys
git push origin main
```

No tests, no build step, no CI.

## Dangerous places / easy to break

1. **AAVE constants** — if these change (governance vote), all risk calcs become wrong. Verify at app.aave.com before modifying.
2. **Monte Carlo seed** — `app.py` uses `seed=42` for reproducibility; `index.html` uses `Math.random()` (no seed). Results differ between the two.
3. **`runDashboard()`** — render functions must execute in order: `renderWallet()` → `renderStrategy()` → `renderSimulation()` → `renderRisk()` → `renderSummary()`. Each depends on output of the previous.
4. **Plotly CDN** — `index.html` loads Plotly from CDN. If CDN is down or version breaks, nothing renders. Pin version in the script tag.
5. **Concentrated IL formula** — `calcConcentratedIL()` is an approximation (base IL × concentration factor, capped at 5x). Not exact Uniswap v3 math, but good enough for dashboard purposes.
6. **Demo wallet data** — hardcoded in both files. Not fetched live (Etherscan API has CORS issues from browser, and rate limits without API key).

## Conventions

- Single-file approach: all logic in one file per implementation
- Dark theme (Plotly `plotly_dark` template, matching CSS)
- All monetary values formatted with `$` and commas
- Health Factor shown to 3 decimal places
- Stress test levels: −10%, −20%, −25%, −30%, −35%, −40%, −50%, −70% (granular around the ~35% liquidation zone)

## GitHub

- Repo: `maslovsa/defi-strategy-dashboard`
- GitHub Pages: enabled, deploys from `main` branch root
- Live URL: `https://maslovsa.github.io/defi-strategy-dashboard/`
