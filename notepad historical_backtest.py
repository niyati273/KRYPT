
import os
import numpy as np
import pandas as pd

# ============================================================
# KRYPT — HISTORICAL FUNDING BACKTEST
# Uses historical data only. No synthetic AI predictions.
# ============================================================

DATA_FILE = "outputs/historical_market_data_6_assets.csv"
OUTPUT_DIR = "outputs"

INITIAL_CAPITAL = 100_000.0
MAX_ACTIVE_COINS = 4
MAX_COIN_WEIGHT = 0.25
MAX_HOLD_PERIODS = 6

# Illustrative execution assumptions
SPOT_FEE = 0.0005
PERP_FEE = 0.0003
SPOT_SLIPPAGE = 0.00025
PERP_SLIPPAGE = 0.00015

# Entry signal: observed funding rate at the current settlement.
ENTRY_FUNDING_THRESHOLD = 0.00005

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------- LOAD AND VALIDATE --------------------

df = pd.read_csv(DATA_FILE)
required = [
    "coin", "timestamp", "spot_close", "perp_close",
    "actual_future_funding", "mark_price"
]

missing = set(required) - set(df.columns)
if missing:
    raise ValueError(f"Missing columns: {missing}")

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values(["timestamp", "coin"]).reset_index(drop=True)

if df.duplicated(["coin", "timestamp"]).any():
    raise ValueError("Duplicate coin/timestamp rows found.")

if df[required].isna().any().any():
    raise ValueError("Missing values found in required columns.")

coins = sorted(df["coin"].unique())
timestamps = sorted(df["timestamp"].unique())

counts = df.groupby("timestamp")["coin"].nunique()
if not (counts == len(coins)).all():
    raise ValueError("Assets do not share complete timestamps.")

print("DATA VALIDATED")
print("Assets:", coins)
print("Rows:", len(df))
print("Timestamps:", len(timestamps))
print("Spot/perp equal rows:", (df.spot_close == df.perp_close).sum())

# One row per timestamp/coin for quick access
data = df.set_index(["timestamp", "coin"]).sort_index()

# Both legs are charged on entry and exit.
ROUND_TRIP_COST = 2 * (
    SPOT_FEE + PERP_FEE +
    SPOT_SLIPPAGE + PERP_SLIPPAGE
)

def execution_cost(notional):
    return notional * (
        SPOT_FEE + PERP_FEE +
        SPOT_SLIPPAGE + PERP_SLIPPAGE
    )

# -------------------- FUNDING STRATEGY --------------------

capital = INITIAL_CAPITAL
positions = {}
trades = []
equity_rows = []

for i, ts in enumerate(timestamps):
    current = data.loc[ts]

    # 1. Update positions held from the previous timestamp.
    for coin in list(positions):
        pos = positions[coin]
        row = current.loc[coin]

        spot_now = float(row["spot_close"])
        perp_now = float(row["perp_close"])
        mark_now = float(row["mark_price"])
        funding = float(row["actual_future_funding"])

        spot_pnl = pos["spot_qty"] * (
            spot_now - pos["previous_spot"]
        )
        perp_pnl = -pos["perp_qty"] * (
            perp_now - pos["previous_perp"]
        )

        # Positive funding pays the short perpetual position.
        funding_pnl = pos["perp_qty"] * mark_now * funding

        period_pnl = spot_pnl + perp_pnl + funding_pnl
        capital += period_pnl
        pos["gross_pnl"] += period_pnl
        pos["periods"] += 1

        pos["previous_spot"] = spot_now
        pos["previous_perp"] = perp_now

        # Exit using only the funding settlement now observed.
        exit_reason = None

        if funding <= 0:
            exit_reason = "FUNDING_NON_POSITIVE"
        elif pos["periods"] >= MAX_HOLD_PERIODS:
            exit_reason = "MAX_HOLD_REACHED"

        if exit_reason:
            exit_cost = execution_cost(pos["allocation"])
            capital -= exit_cost

            net_pnl = pos["gross_pnl"] - pos["entry_cost"] - exit_cost

            trades.append({
                "coin": coin,
                "entry_time": pos["entry_time"],
                "exit_time": ts,
                "periods_held": pos["periods"],
                "allocation": pos["allocation"],
                "gross_pnl": pos["gross_pnl"],
                "entry_cost": pos["entry_cost"],
                "exit_cost": exit_cost,
                "net_pnl": net_pnl,
                "exit_reason": exit_reason
            })

            del positions[coin]

    # 2. Rank coins using funding rates already observed at this timestamp.
    candidates = []

    for coin in coins:
        if coin in positions:
            continue

        row = current.loc[coin]
        rate = float(row["actual_future_funding"])

        if rate > ENTRY_FUNDING_THRESHOLD:
            candidates.append((coin, rate))

    candidates.sort(key=lambda x: x[1], reverse=True)

    # 3. Enter new positions.
    available_slots = MAX_ACTIVE_COINS - len(positions)

    for coin, rate in candidates[:available_slots]:
        allocated = sum(
            p["allocation"] for p in positions.values()
        )
        free_cash = max(0.0, capital - allocated)

        allocation = min(
            capital * MAX_COIN_WEIGHT,
            free_cash * 0.90
        )

        if allocation < 1000:
            continue

        row = current.loc[coin]
        spot = float(row["spot_close"])
        perp = float(row["perp_close"])

        if spot <= 0 or perp <= 0:
            continue

        entry_cost = execution_cost(allocation)
        capital -= entry_cost

        positions[coin] = {
            "entry_time": ts,
            "allocation": allocation,
            "spot_qty": allocation / spot,
            "perp_qty": allocation / perp,
            "previous_spot": spot,
            "previous_perp": perp,
            "periods": 0,
            "gross_pnl": 0.0,
            "entry_cost": entry_cost
        }

    equity_rows.append({
        "timestamp": ts,
        "equity": capital,
        "active_positions": len(positions)
    })

# 4. Close any remaining positions at the final observation.
last_ts = timestamps[-1]
last_data = data.loc[last_ts]

for coin, pos in list(positions.items()):
    exit_cost = execution_cost(pos["allocation"])
    capital -= exit_cost

    net_pnl = pos["gross_pnl"] - pos["entry_cost"] - exit_cost

    trades.append({
        "coin": coin,
        "entry_time": pos["entry_time"],
        "exit_time": last_ts,
        "periods_held": pos["periods"],
        "allocation": pos["allocation"],
        "gross_pnl": pos["gross_pnl"],
        "entry_cost": pos["entry_cost"],
        "exit_cost": exit_cost,
        "net_pnl": net_pnl,
        "exit_reason": "BACKTEST_END"
    })

if equity_rows:
    equity_rows[-1]["equity"] = capital
    equity_rows[-1]["active_positions"] = 0

# -------------------- PERFORMANCE METRICS --------------------

equity = pd.DataFrame(equity_rows)
trade_df = pd.DataFrame(trades)

peak = equity["equity"].cummax()
drawdown = (equity["equity"] - peak) / peak

final_equity = float(equity["equity"].iloc[-1])
total_return = (final_equity / INITIAL_CAPITAL - 1) * 100

if len(trade_df):
    win_rate = (trade_df["net_pnl"] > 0).mean() * 100
    total_trades = len(trade_df)
    gross_profit = trade_df.loc[
        trade_df.net_pnl > 0, "net_pnl"
    ].sum()
    gross_loss = abs(trade_df.loc[
        trade_df.net_pnl < 0, "net_pnl"
    ].sum())
    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else np.nan
    )
else:
    win_rate = 0.0
    total_trades = 0
    profit_factor = np.nan

summary = pd.DataFrame([{
    "strategy": "Historical Funding Threshold",
    "initial_capital": INITIAL_CAPITAL,
    "final_equity": final_equity,
    "net_profit": final_equity - INITIAL_CAPITAL,
    "return_percent": total_return,
    "max_drawdown_percent": abs(float(drawdown.min())) * 100,
    "total_trades": total_trades,
    "win_rate_percent": win_rate,
    "profit_factor": profit_factor,
    "entry_threshold": ENTRY_FUNDING_THRESHOLD,
    "max_hold_periods": MAX_HOLD_PERIODS,
    "round_trip_cost_rate": ROUND_TRIP_COST
}])

# -------------------- EXPORT --------------------

equity.to_csv(
    f"{OUTPUT_DIR}/historical_equity_curve.csv",
    index=False
)
trade_df.to_csv(
    f"{OUTPUT_DIR}/historical_trades.csv",
    index=False
)
summary.to_csv(
    f"{OUTPUT_DIR}/historical_backtest_results.csv",
    index=False
)

print("\n========== HISTORICAL BACKTEST RESULTS ==========")
print(summary.to_string(index=False))
print("\nFiles saved:")
print("outputs/historical_equity_curve.csv")
print("outputs/historical_trades.csv")
print("outputs/historical_backtest_results.csv")
print("\nThis is a historical simulation, not a live trading signal.")
