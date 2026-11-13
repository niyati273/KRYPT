# Person C — Quantitative finance and backtesting

## Your job in simple words
You turn model forecasts into simulated trading decisions and test how the strategy would have performed historically, including costs and risk.

## First tasks
- [ ] Write down the trade: long spot and short a similar notional amount of perpetual futures.
- [ ] Confirm the exchange's actual funding settlement times and sign convention.
- [ ] Define position size and starting capital.
- [ ] Define entry and exit rules before looking at test results.
- [ ] Include spot and perpetual trading fees.
- [ ] Include estimated entry and exit slippage.
- [ ] Include spot P&L, perpetual P&L, funding cashflows and basis effects.
- [ ] Build an always-on carry baseline using the same cost and risk assumptions.
- [ ] Build the AI-driven strategy using only predictions available at decision time.
- [ ] Calculate net profit, ROI, Sharpe, maximum drawdown, win rate and profit factor.
- [ ] Run sensitivity checks with higher fees and slippage.

## Suggested output files
- `03_PERSON_C_Quant_Finance_Backtesting/backtest.py`
- `03_PERSON_C_Quant_Finance_Backtesting/metrics.py`
- `09_SHARED_Results/backtest_trades.csv`
- `09_SHARED_Results/backtest_summary.csv`
- `09_SHARED_Results/equity_curve.csv`
- `09_SHARED_Results/latency_report.md`

## Handoff to Person D
Provide:
- Actual backtest period.
- Number of trades.
- Gross and net P&L.
- Total fees and estimated slippage.
- ROI, Sharpe, maximum drawdown, win rate and profit factor.
- Baseline comparison.
- Clear assumptions and limitations.

## Done means
A reproducible backtest compares AI-driven carry with always-on carry using out-of-sample signals and consistent costs, and exports trade-level and summary results.

## Important
Do not treat funding income as the entire P&L. Include both legs' price P&L and basis changes. Do not present simulated returns as live trading results. This project is a research prototype, not a recommendation to trade.
