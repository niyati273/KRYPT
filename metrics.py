"""
metrics.py - Institutional Quantitative Performance & Risk Analytics
Aligned with TASKS_AND_HANDOFF.md and ARCHITECTURE_AND_EQUATIONS.md.

Calculates:
- Net Profit ($), Gross ROI (%), Net ROI (%)
- Annualized Sharpe Ratio (8h periods = 1,095 settlements/yr)
- Sortino Ratio (downside risk-adjusted)
- Maximum Drawdown (MDD %) and Drawdown Duration
- Win Rate (%) and Profit Factor
- Calmar Ratio
- Fee Drag and Basis Slippage Drag breakdown
"""

import numpy as np
import pandas as pd

def calculate_sharpe_ratio(returns, periods_per_year=1095, risk_free_rate=0.0):
    """
    Computes annualized Sharpe ratio for 8-hour settlement intervals (1,095/year).
    """
    clean_rets = np.array(returns)
    clean_rets = clean_rets[~np.isnan(clean_rets)]
    if len(clean_rets) < 2:
        return 0.0
    rf_per_period = risk_free_rate / periods_per_year
    excess_returns = clean_rets - rf_per_period
    std = np.std(clean_rets, ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(np.mean(excess_returns) / std * np.sqrt(periods_per_year))

def calculate_sortino_ratio(returns, periods_per_year=1095, risk_free_rate=0.0):
    """
    Computes annualized Sortino ratio targeting downside semi-deviation.
    """
    clean_rets = np.array(returns)
    clean_rets = clean_rets[~np.isnan(clean_rets)]
    if len(clean_rets) < 2:
        return 0.0
    rf_per_period = risk_free_rate / periods_per_year
    excess_returns = clean_rets - rf_per_period
    downside_diff = np.minimum(0.0, excess_returns)
    downside_std = np.sqrt(np.mean(downside_diff**2))
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    return float(np.mean(excess_returns) / downside_std * np.sqrt(periods_per_year))

def calculate_max_drawdown(equity_series):
    """
    Computes Maximum Drawdown percentage and high-water mark series.
    Returns: (mdd_pct, peak_idx, trough_idx, drawdown_series)
    """
    eq = pd.Series(equity_series).values
    if len(eq) == 0:
        return 0.0, 0, 0, np.zeros(0)
    running_max = np.maximum.accumulate(eq)
    drawdowns = (eq - running_max) / running_max
    mdd = float(np.min(drawdowns))
    trough_idx = int(np.argmin(drawdowns))
    peak_idx = int(np.argmax(eq[:trough_idx + 1])) if trough_idx > 0 else 0
    return abs(mdd), peak_idx, trough_idx, drawdowns

def calculate_trade_metrics(trades_df):
    """
    Computes trade-level analytics: Win Rate, Profit Factor, Average Trade PnL.
    """
    if trades_df is None or len(trades_df) == 0 or "net_pnl" not in trades_df.columns:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "avg_trade_pnl": 0.0,
            "emergency_exits": 0
        }
    
    pnls = trades_df["net_pnl"].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    
    total_trades = len(pnls)
    win_rate = float(len(wins) / total_trades) if total_trades > 0 else 0.0
    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
    
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    avg_trade_pnl = float(np.mean(pnls)) if total_trades > 0 else 0.0
    
    emergency_count = 0
    if "exit_reason" in trades_df.columns:
        emergency_count = int((trades_df["exit_reason"] == "EMERGENCY_SQUEEZE_EXIT").sum())
        
    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "avg_trade_pnl": round(avg_trade_pnl, 2),
        "emergency_exits": emergency_count
    }

def compute_full_performance_summary(name, equity_series, initial_capital, trades_df=None, fee_total=0.0, slippage_total=0.0, gross_pnl=0.0):
    """
    Aggregates all quantitative metrics into a unified dictionary.
    """
    eq = np.array(equity_series)
    final_equity = eq[-1]
    net_profit = final_equity - initial_capital
    net_roi = (net_profit / initial_capital) * 100.0
    gross_profit = gross_pnl if gross_pnl != 0.0 else (net_profit + fee_total + slippage_total)
    gross_roi = (gross_profit / initial_capital) * 100.0
    
    returns = np.diff(eq) / eq[:-1]
    sharpe = calculate_sharpe_ratio(returns)
    sortino = calculate_sortino_ratio(returns)
    mdd, _, _, _ = calculate_max_drawdown(eq)
    mdd_pct = mdd * 100.0
    
    trade_stats = calculate_trade_metrics(trades_df)
    
    calmar = (net_roi / mdd_pct) if mdd_pct > 0 else 0.0
    fee_drag_pct = (fee_total / initial_capital) * 100.0
    slippage_drag_pct = (slippage_total / initial_capital) * 100.0
    
    summary = {
        "Strategy": name,
        "Initial Capital ($)": round(initial_capital, 2),
        "Final Equity ($)": round(final_equity, 2),
        "Gross Profit ($)": round(gross_profit, 2),
        "Net Profit ($)": round(net_profit, 2),
        "Gross ROI (%)": round(gross_roi, 2),
        "Net ROI (%)": round(net_roi, 2),
        "Annualized Sharpe Ratio": round(sharpe, 3),
        "Sortino Ratio": round(sortino, 3),
        "Max Drawdown (%)": round(mdd_pct, 2),
        "Calmar Ratio": round(calmar, 2),
        "Win Rate (%)": trade_stats["win_rate"],
        "Profit Factor": trade_stats["profit_factor"],
        "Total Trades": trade_stats["total_trades"],
        "Emergency Squeeze Exits": trade_stats["emergency_exits"],
        "Total Fee Drag ($)": round(fee_total, 2),
        "Fee Drag (%)": round(fee_drag_pct, 2),
        "Total Slippage Drag ($)": round(slippage_total, 2),
        "Slippage Drag (%)": round(slippage_drag_pct, 2)
    }
    return summary
