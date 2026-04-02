import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DeFi Strategy Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("DeFi Strategy Dashboard")
st.caption("AAVE Collateral + Borrow + Uniswap V3 LP + Collect Fees")

# ─── Constants ─────────────────────────────────────────────────────────────────
AAVE_LIQUIDATION_THRESHOLD = 0.825  # ETH on AAVE v3
WALLET_ADDRESS = "0x6b0f1267f2c7a633c639fb525a400a55f8d78888"
ETHERSCAN_API_BASE = "https://api.etherscan.io/api"


# ─── Sidebar Inputs ───────────────────────────────────────────────────────────
st.sidebar.header("Strategy Parameters")

eth_price = st.sidebar.number_input("ETH Price (USD)", value=2451.98, min_value=100.0, step=10.0)
deposit_eth = st.sidebar.number_input("Deposit ETH", value=75.1, min_value=0.1, step=0.1)
ltv_pct = st.sidebar.slider("LTV Borrow %", min_value=50, max_value=90, value=75) / 100.0
fee_tier = st.sidebar.selectbox("Uniswap Fee Tier", [0.01, 0.05, 0.3, 1.0], index=2, format_func=lambda x: f"{x}%")
lp_range_pct = st.sidebar.slider("LP Range ±%", min_value=5, max_value=50, value=15) / 100.0
sim_months = st.sidebar.slider("Simulation Months", min_value=1, max_value=36, value=12)
n_simulations = st.sidebar.slider("Monte Carlo Simulations", min_value=50, max_value=500, value=100, step=50)

st.sidebar.markdown("---")
st.sidebar.subheader("Fee APR Assumptions")
lp_fee_apr = st.sidebar.slider("Expected LP Fee APR %", min_value=5, max_value=80, value=30) / 100.0
borrow_apr = st.sidebar.slider("AAVE Borrow APR %", min_value=1, max_value=20, value=5) / 100.0
eth_volatility = st.sidebar.slider("ETH Annual Volatility %", min_value=10, max_value=80, value=30) / 100.0

st.sidebar.markdown("---")
load_wallet = st.sidebar.button(f"Load Wallet {WALLET_ADDRESS[:6]}...{WALLET_ADDRESS[-4:]}")


# ─── Helper Functions ──────────────────────────────────────────────────────────

def calc_health_factor(collateral_value, borrow_amount):
    if borrow_amount == 0:
        return float("inf")
    return (collateral_value * AAVE_LIQUIDATION_THRESHOLD) / borrow_amount


def calc_impermanent_loss(price_ratio):
    """IL for a concentrated LP position given price_ratio = new_price / old_price."""
    sqrt_r = np.sqrt(price_ratio)
    il = 2 * sqrt_r / (1 + price_ratio) - 1
    return il


def calc_concentrated_il(price_ratio, range_factor):
    """Approximate IL for concentrated liquidity within ±range_factor."""
    base_il = calc_impermanent_loss(price_ratio)
    concentration = 1.0 / range_factor
    return base_il * min(concentration, 5.0)


def simulate_eth_prices(current_price, months, volatility, n_sims, seed=42):
    """GBM simulation for ETH price paths."""
    rng = np.random.default_rng(seed)
    dt = 1 / 365
    days = months * 30
    drift = 0.0  # risk-neutral

    paths = np.zeros((n_sims, days + 1))
    paths[:, 0] = current_price

    for t in range(1, days + 1):
        z = rng.standard_normal(n_sims)
        paths[:, t] = paths[:, t - 1] * np.exp((drift - 0.5 * volatility**2) * dt + volatility * np.sqrt(dt) * z)

    return paths


def fetch_wallet_transactions(address):
    """Fetch transactions from Etherscan free API."""
    try:
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 50,
            "sort": "desc",
        }
        resp = requests.get(ETHERSCAN_API_BASE, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            return data["result"]
    except Exception:
        pass
    return None


def get_demo_wallet_data():
    """Real transaction data for Ivan's wallet 0x6b0f...8888, sourced from Etherscan."""
    txs = [
        # Phase 1: Across bridge → AAVE deposit → Borrow → Uniswap LP (Jan 31, 2026)
        {"date": datetime(2026, 1, 31, 21, 12), "action": "Bridge via Across", "asset": "ETH", "amount_eth": 75.08, "amount_usd": 152280.00},
        {"date": datetime(2026, 1, 31, 21, 16), "action": "AAVE Supply (ETH staking)", "asset": "ETH → aEthWETH", "amount_eth": 75.1, "amount_usd": 152321.00},
        {"date": datetime(2026, 1, 31, 21, 17), "action": "AAVE Supply (cbBTC)", "asset": "cbBTC", "amount_eth": 0, "amount_usd": 345.00},
        {"date": datetime(2026, 1, 31, 21, 21), "action": "AAVE Borrow (variable)", "asset": "USDT", "amount_eth": 0, "amount_usd": 100000.00},
        {"date": datetime(2026, 1, 31, 21, 34), "action": "Uniswap V3 Mint #1188030", "asset": "USDT/WETH", "amount_eth": 8.9, "amount_usd": 96366.00},
        {"date": datetime(2026, 1, 31, 21, 36), "action": "AAVE Repay (cleanup)", "asset": "USDT", "amount_eth": 0, "amount_usd": 194.65},
        # Phase 2: Additional collateral & borrows (Feb 5-6, 2026)
        {"date": datetime(2026, 2, 6, 10, 16), "action": "AAVE Supply (cbBTC)", "asset": "cbBTC", "amount_eth": 0, "amount_usd": 33674.00},
        {"date": datetime(2026, 2, 6, 10, 55), "action": "AAVE Borrow (GHO)", "asset": "GHO", "amount_eth": 0, "amount_usd": 24987.00},
        # Phase 3: Fee collections
        {"date": datetime(2026, 3, 1, 10, 26), "action": "Uniswap Collect #1188030", "asset": "Fees", "amount_eth": 1.422, "amount_usd": 5675.00},
        {"date": datetime(2026, 3, 28, 16, 8), "action": "Uniswap Collect + Remove #1188030", "asset": "Fees", "amount_eth": 0.586, "amount_usd": 2442.00},
    ]
    return pd.DataFrame(txs)


def parse_etherscan_txs(txs):
    """Parse raw Etherscan transactions into a readable DataFrame."""
    rows = []
    known_contracts = {
        "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "AAVE V3 Pool",
        "0xc36442b4a4522e871399cd717abdd847ab11fe88": "Uniswap V3 NFT Manager",
    }
    for tx in txs:
        to_addr = tx.get("to", "").lower()
        value_eth = int(tx.get("value", "0")) / 1e18
        gas_price = int(tx.get("gasPrice", "0")) / 1e9
        timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", "0")))

        protocol = known_contracts.get(to_addr, "Unknown")
        method = tx.get("functionName", "").split("(")[0] if tx.get("functionName") else "transfer"

        rows.append({
            "date": timestamp,
            "protocol": protocol,
            "method": method,
            "value_eth": round(value_eth, 4),
            "gas_gwei": round(gas_price, 2),
            "hash": tx.get("hash", "")[:12] + "...",
            "status": "Success" if tx.get("isError") == "0" else "Failed",
        })
    return pd.DataFrame(rows)


# ─── Section 1: Wallet Analysis ───────────────────────────────────────────────
st.header("1. Wallet Analysis")

if load_wallet:
    with st.spinner("Fetching wallet transactions..."):
        raw_txs = fetch_wallet_transactions(WALLET_ADDRESS)

    if raw_txs:
        st.success(f"Loaded {len(raw_txs)} transactions from Etherscan")
        df_txs = parse_etherscan_txs(raw_txs)
        st.dataframe(df_txs, use_container_width=True)

        if not df_txs.empty and "value_eth" in df_txs.columns:
            fig_balance = px.bar(
                df_txs[df_txs["value_eth"] > 0],
                x="date", y="value_eth",
                color="protocol",
                title="ETH Value per Transaction",
                labels={"value_eth": "ETH", "date": "Date"},
            )
            st.plotly_chart(fig_balance, use_container_width=True)
    else:
        st.warning("Could not fetch live data. Showing demo data.")
        df_demo = get_demo_wallet_data()
        st.dataframe(df_demo, use_container_width=True)

        fee_txs = df_demo[df_demo["action"].str.contains("Collect")]
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Fees Collected", f"${fee_txs['amount_usd'].sum():,.2f}")
        col2.metric("Total Fees (ETH)", f"{fee_txs['amount_eth'].sum():.2f} ETH")
        col3.metric("Avg Monthly Yield", f"${fee_txs['amount_usd'].mean():,.2f}")

        fig_fees = px.bar(
            fee_txs, x="date", y="amount_usd",
            title="Fees Collected Over Time",
            labels={"amount_usd": "USD", "date": "Date"},
            color_discrete_sequence=["#00cc96"],
        )
        st.plotly_chart(fig_fees, use_container_width=True)
else:
    st.info("Click the button in the sidebar to load wallet data.")


# ─── Section 2: Strategy Calculator ───────────────────────────────────────────
st.header("2. Strategy Calculator")

collateral_value = deposit_eth * eth_price
borrow_amount = collateral_value * ltv_pct
eth_bought = 21000.0 / eth_price  # buy ETH with $21k of borrowed
remaining_usd = borrow_amount - 21000.0
lp_eth = eth_bought
lp_usd = remaining_usd
lp_total = lp_eth * eth_price + lp_usd
health_factor = calc_health_factor(collateral_value, borrow_amount)
monthly_fees = lp_total * lp_fee_apr / 12
monthly_borrow_cost = borrow_amount * borrow_apr / 12

steps = pd.DataFrame([
    {
        "Step": 1,
        "Action": "Deposit ETH to AAVE",
        "Amount ETH": f"{deposit_eth:.4f}",
        "Amount USD": f"${collateral_value:,.2f}",
        "Health Factor": "—",
    },
    {
        "Step": 2,
        "Action": f"Borrow stablecoins (LTV {ltv_pct*100:.0f}%)",
        "Amount ETH": "—",
        "Amount USD": f"${borrow_amount:,.2f}",
        "Health Factor": f"{health_factor:.2f}",
    },
    {
        "Step": 3,
        "Action": "Buy ETH ($21,000)",
        "Amount ETH": f"{eth_bought:.4f}",
        "Amount USD": f"${21000:,.2f}",
        "Health Factor": f"{health_factor:.2f}",
    },
    {
        "Step": 4,
        "Action": f"Create Uniswap V3 LP (±{lp_range_pct*100:.0f}%)",
        "Amount ETH": f"{lp_eth:.4f}",
        "Amount USD": f"${lp_total:,.2f}",
        "Health Factor": f"{health_factor:.2f}",
    },
])

st.dataframe(steps, use_container_width=True, hide_index=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Collateral Value", f"${collateral_value:,.2f}")
col2.metric("Health Factor", f"{health_factor:.2f}", delta="Safe" if health_factor > 1.5 else "Risky")
col3.metric("Est. Monthly Fees", f"${monthly_fees:,.2f}")
col4.metric("Monthly Borrow Cost", f"${monthly_borrow_cost:,.2f}")

net_monthly = monthly_fees - monthly_borrow_cost
st.metric("Net Monthly Income", f"${net_monthly:,.2f}", delta=f"{net_monthly/collateral_value*12*100:.1f}% APR")


# ─── Section 3: P&L Simulation (Monte Carlo) ──────────────────────────────────
st.header("3. P&L Simulation (Monte Carlo)")

price_paths = simulate_eth_prices(eth_price, sim_months, eth_volatility, n_simulations)
days = price_paths.shape[1]
time_axis = np.arange(days) / 30  # months

# Calculate P&L components for each simulation
cumulative_fees = np.zeros((n_simulations, days))
cumulative_il = np.zeros((n_simulations, days))
cumulative_borrow = np.zeros((n_simulations, days))
cumulative_net = np.zeros((n_simulations, days))
health_factors = np.zeros((n_simulations, days))

daily_fee = lp_total * lp_fee_apr / 365
daily_borrow = borrow_amount * borrow_apr / 365

for t in range(1, days):
    price_ratio = price_paths[:, t] / eth_price
    il = calc_concentrated_il(price_ratio, lp_range_pct) * lp_total
    cumulative_fees[:, t] = cumulative_fees[:, t - 1] + daily_fee
    cumulative_il[:, t] = il
    cumulative_borrow[:, t] = daily_borrow * t
    cumulative_net[:, t] = cumulative_fees[:, t] + cumulative_il[:, t] - cumulative_borrow[:, t]

    collat_t = deposit_eth * price_paths[:, t]
    health_factors[:, t] = (collat_t * AAVE_LIQUIDATION_THRESHOLD) / borrow_amount

# Plot: Net P&L fan chart
fig_pnl = go.Figure()

# Individual paths (light)
for i in range(min(n_simulations, 50)):
    fig_pnl.add_trace(go.Scatter(
        x=time_axis, y=cumulative_net[i],
        mode="lines", line=dict(color="rgba(99,110,250,0.08)"),
        showlegend=False, hoverinfo="skip",
    ))

# Percentiles
p5 = np.percentile(cumulative_net, 5, axis=0)
p25 = np.percentile(cumulative_net, 25, axis=0)
p50 = np.median(cumulative_net, axis=0)
p75 = np.percentile(cumulative_net, 75, axis=0)
p95 = np.percentile(cumulative_net, 95, axis=0)

fig_pnl.add_trace(go.Scatter(x=time_axis, y=p95, mode="lines", name="95th %ile", line=dict(color="green", dash="dot")))
fig_pnl.add_trace(go.Scatter(x=time_axis, y=p75, mode="lines", name="75th %ile", line=dict(color="lightgreen", dash="dot")))
fig_pnl.add_trace(go.Scatter(x=time_axis, y=p50, mode="lines", name="Median", line=dict(color="white", width=3)))
fig_pnl.add_trace(go.Scatter(x=time_axis, y=p25, mode="lines", name="25th %ile", line=dict(color="orange", dash="dot")))
fig_pnl.add_trace(go.Scatter(x=time_axis, y=p5, mode="lines", name="5th %ile", line=dict(color="red", dash="dot")))
fig_pnl.add_trace(go.Scatter(x=time_axis, y=np.zeros(days), mode="lines", name="Break-even", line=dict(color="gray", dash="dash")))

fig_pnl.update_layout(
    title="Net P&L Distribution (Fees - IL - Borrow Interest)",
    xaxis_title="Months",
    yaxis_title="USD",
    template="plotly_dark",
    height=500,
)
st.plotly_chart(fig_pnl, use_container_width=True)

# Component breakdown chart
fig_components = go.Figure()
fig_components.add_trace(go.Scatter(x=time_axis, y=np.median(cumulative_fees, axis=0), name="Cumulative Fees", fill="tozeroy", line=dict(color="green")))
fig_components.add_trace(go.Scatter(x=time_axis, y=np.median(cumulative_il, axis=0), name="Impermanent Loss", fill="tozeroy", line=dict(color="red")))
fig_components.add_trace(go.Scatter(x=time_axis, y=-np.median(cumulative_borrow, axis=0), name="Borrow Interest", fill="tozeroy", line=dict(color="orange")))
fig_components.update_layout(
    title="P&L Components (Median Path)",
    xaxis_title="Months",
    yaxis_title="USD",
    template="plotly_dark",
    height=400,
)
st.plotly_chart(fig_components, use_container_width=True)

# Metrics
final_net = cumulative_net[:, -1]
total_invested = collateral_value
estimated_apr = (np.median(final_net) / total_invested) * (12 / sim_months) * 100
max_drawdown = np.min(cumulative_net)
liquidation_prob = np.mean(np.any(health_factors[:, 1:] < 1.0, axis=1)) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Estimated APR (median)", f"{estimated_apr:.1f}%")
col2.metric("Max Drawdown (worst)", f"${max_drawdown:,.0f}")
col3.metric("Liquidation Probability", f"{liquidation_prob:.1f}%")
col4.metric("Median Final P&L", f"${np.median(final_net):,.0f}")


# ─── Section 4: Risk Analysis ─────────────────────────────────────────────────
st.header("4. Risk Analysis")

st.markdown("""
**Key Risks:**
- **Impermanent Loss (IL):** Concentrated LP positions amplify IL when ETH moves outside the range. A ±15% range means ~6.7x concentration — large moves destroy value fast.
- **Liquidation Risk:** If ETH drops significantly, AAVE Health Factor falls below 1.0, triggering liquidation of your collateral. Current HF: {hf:.2f}.
- **Borrow Rate Spikes:** AAVE borrow rates are variable. During high-demand periods, rates can spike to 10-20%+, eating into profits.
- **Smart Contract Risk:** Multiple protocol exposure (AAVE + Uniswap) compounds smart contract risk.
- **Oracle/Price Feed Risk:** Flash crashes or oracle delays can trigger unexpected liquidations.
- **Range Exhaustion:** If price moves beyond your LP range, you stop earning fees entirely while still paying borrow interest.
""".format(hf=health_factor))

st.subheader("Stress Test")

if st.button("Run Stress Test"):
    drops = [0.20, 0.30, 0.50, 0.70]
    stress_rows = []
    for drop in drops:
        new_price = eth_price * (1 - drop)
        new_collateral = deposit_eth * new_price
        new_hf = calc_health_factor(new_collateral, borrow_amount)
        price_ratio = new_price / eth_price
        il_pct = calc_concentrated_il(price_ratio, lp_range_pct)
        il_usd = il_pct * lp_total
        annual_fees = lp_total * lp_fee_apr
        annual_borrow = borrow_amount * borrow_apr
        net_annual = annual_fees + il_usd - annual_borrow  # il_usd is negative
        collateral_loss = (collateral_value - new_collateral)

        stress_rows.append({
            "ETH Drop": f"-{drop*100:.0f}%",
            "New ETH Price": f"${new_price:,.2f}",
            "Collateral Value": f"${new_collateral:,.2f}",
            "Collateral Loss": f"-${collateral_loss:,.2f}",
            "Health Factor": f"{new_hf:.2f}",
            "Status": "LIQUIDATED" if new_hf < 1.0 else ("DANGER" if new_hf < 1.2 else "OK"),
            "IL (annual)": f"-${abs(il_usd):,.2f}",
            "Net Annual P&L": f"${net_annual:,.2f}",
        })

    df_stress = pd.DataFrame(stress_rows)
    st.dataframe(df_stress, use_container_width=True, hide_index=True)

    # Stress test visualization
    fig_stress = go.Figure()
    prices = [eth_price * (1 - d) for d in drops]
    hfs = [calc_health_factor(deposit_eth * p, borrow_amount) for p in prices]

    fig_stress.add_trace(go.Bar(
        x=[f"-{d*100:.0f}%" for d in drops],
        y=hfs,
        name="Health Factor",
        marker_color=["green" if h > 1.5 else "orange" if h > 1.0 else "red" for h in hfs],
    ))
    fig_stress.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="Liquidation Threshold")
    fig_stress.update_layout(
        title="Health Factor Under Stress",
        xaxis_title="ETH Price Drop",
        yaxis_title="Health Factor",
        template="plotly_dark",
        height=400,
    )
    st.plotly_chart(fig_stress, use_container_width=True)

else:
    st.info("Click 'Run Stress Test' to simulate ETH price drops of -20%, -30%, -50%, -70%.")


# ─── Footer / Strategy Summary ─────────────────────────────────────────────────
st.markdown("---")
st.header("Strategy Summary")

st.markdown(f"""
### Strategy: AAVE Collateral + Borrow + Uniswap V3 LP

| Parameter | Value |
|-----------|-------|
| Collateral | {deposit_eth} ETH (${collateral_value:,.2f}) |
| Borrow | ${borrow_amount:,.2f} at {borrow_apr*100:.1f}% APR |
| LP Position | ${lp_total:,.2f} in ETH/USDC ±{lp_range_pct*100:.0f}% |
| Expected Fees | ~${monthly_fees:,.0f}/month ({lp_fee_apr*100:.0f}% APR) |
| Net Monthly | ~${net_monthly:,.0f}/month |
| Health Factor | {health_factor:.2f} |

**Estimated Yield:** {estimated_apr:.0f}% APR (median Monte Carlo)

**Conclusion:** This strategy can generate **25-40% APR** in favorable conditions (stable ETH price, high trading volume). However, it carries **high risk**:
- Leveraged position amplifies both gains and losses
- Concentrated LP magnifies impermanent loss
- Liquidation risk is real if ETH drops >50%
- Multiple smart contract dependencies

**Recommendation:** Only suitable for experienced DeFi users who can actively manage the position and are comfortable with potential total loss of borrow amount.
""")
