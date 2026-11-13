"""
backtest.py - Production-Grade Quantitative Backtesting Engine
Problem Statement 20: Hybrid AI Funding-Rate Arbitrage & Risk Protection.

Implements:
1. Auto-normalization of any symbol format ('BTC', 'BTCUSDT', 'BTC/USDT', 'BTC/USDT:USDT').
2. Exact Delta-Neutral Cash-and-Carry Accounting (Long Spot + Short Perpetual Futures).
3. Spot + Perp Maker/Taker Fees and Dynamic Basis Slippage.
4. Hysteresis Fee-Hurdle State Machine (Churn Prevention).
5. Stage 1 Liquidity Squeeze Emergency Protection (Circuit Breaker).
6. Funding Radar Multi-Coin Uncertainty-Aware Ranking & Capital Allocation across 10 official assets.
"""

import numpy as np
import pandas as pd
from metrics import compute_full_performance_summary
from mock_data import normalize_symbol, get_coin_metadata, COIN_ORDER

class BacktestConfig:
    def __init__(
        self,
        initial_capital=100000.0,
        spot_taker_fee=0.0005,      # 5 bps
        perp_taker_fee=0.0003,      # 3 bps
        base_slippage_spot=0.00025, # 2.5 bps
        base_slippage_perp=0.00015, # 1.5 bps
        entry_margin=0.00008,       # Safety margin
        expected_holding_periods=6, # 48-hour expected campaign duration
        max_coin_weight=0.35,       # Max 35% capital per coin
        max_active_coins=4,         # Top K coins in portfolio
        squeeze_exit_thresh=0.40,   # Squeeze probability threshold for emergency exit
        spike_prob_thresh=0.45,     # Classifier threshold
    ):
        self.initial_capital = initial_capital
        self.spot_taker_fee = spot_taker_fee
        self.perp_taker_fee = perp_taker_fee
        self.total_entry_fee = spot_taker_fee + perp_taker_fee          # 8 bps one-way
        self.total_roundtrip_fee = 2 * self.total_entry_fee             # 16 bps round-trip
        self.base_slippage_spot = base_slippage_spot
        self.base_slippage_perp = base_slippage_perp
        self.total_base_slippage = base_slippage_spot + base_slippage_perp # 4 bps one-way
        self.total_roundtrip_slippage = 2 * self.total_base_slippage      # 8 bps round-trip
        self.entry_margin = entry_margin
        self.expected_holding_periods = expected_holding_periods
        
        self.per_period_hurdle = (self.total_roundtrip_fee + self.total_roundtrip_slippage) / expected_holding_periods + entry_margin
        
        self.max_coin_weight = max_coin_weight
        self.max_active_coins = max_active_coins
        self.squeeze_exit_thresh = squeeze_exit_thresh
        self.spike_prob_thresh = spike_prob_thresh

class DeltaNeutralPosition:
    def __init__(self, coin, entry_timestamp, allocated_capital, spot_entry_price, perp_entry_price, config):
        self.coin = normalize_symbol(coin)
        self.meta = get_coin_metadata(self.coin)
        self.symbol = self.meta["slash"]
        self.ccxt_symbol = self.meta["ccxt"]
        self.binance_symbol = self.meta["binance"]
        
        self.entry_timestamp = entry_timestamp
        self.allocated_capital = allocated_capital
        self.spot_entry_price = spot_entry_price
        self.perp_entry_price = perp_entry_price
        self.config = config
        
        # Position sizing: Delta-neutral setup
        self.spot_qty = allocated_capital / spot_entry_price
        self.perp_qty = allocated_capital / perp_entry_price
        
        self.entry_basis = (perp_entry_price - spot_entry_price) / spot_entry_price
        
        self.entry_fee = allocated_capital * config.total_entry_fee
        self.entry_slippage = allocated_capital * config.total_base_slippage
        
        self.cumulative_funding = 0.0
        self.cumulative_spot_pnl = 0.0
        self.cumulative_perp_pnl = 0.0
        self.cumulative_fees = self.entry_fee
        self.cumulative_slippage = self.entry_slippage
        self.periods_held = 0
        self.is_open = True
        
        self.exit_timestamp = None
        self.exit_basis = None
        self.exit_fee = 0.0
        self.exit_slippage = 0.0
        self.exit_reason = None
        self.net_pnl = 0.0
        self.gross_pnl = 0.0

    def update_period(self, spot_price_prev, spot_price_curr, perp_price_prev, perp_price_curr, funding_rate):
        if not self.is_open:
            return 0.0, 0.0, 0.0
            
        spot_pnl = self.spot_qty * (spot_price_curr - spot_price_prev)
        perp_pnl = - self.perp_qty * (perp_price_curr - perp_price_prev)
        funding_cashflow = self.perp_qty * perp_price_curr * funding_rate
        
        self.cumulative_spot_pnl += spot_pnl
        self.cumulative_perp_pnl += perp_pnl
        self.cumulative_funding += funding_cashflow
        self.periods_held += 1
        
        gross_step_pnl = spot_pnl + perp_pnl + funding_cashflow
        return gross_step_pnl, funding_cashflow, (spot_pnl + perp_pnl)

    def close_position(self, exit_timestamp, spot_exit_price, perp_exit_price, exit_reason, dynamic_slippage_mult=1.0):
        self.exit_timestamp = exit_timestamp
        self.exit_basis = (perp_exit_price - spot_exit_price) / spot_exit_price
        self.exit_reason = exit_reason
        self.is_open = False
        
        exit_notional = 0.5 * (self.spot_qty * spot_exit_price + self.perp_qty * perp_exit_price)
        self.exit_fee = exit_notional * self.config.total_entry_fee
        self.exit_slippage = exit_notional * (self.config.total_base_slippage * dynamic_slippage_mult)
        
        self.cumulative_fees += self.exit_fee
        self.cumulative_slippage += self.exit_slippage
        
        self.gross_pnl = self.cumulative_funding + self.cumulative_spot_pnl + self.cumulative_perp_pnl
        self.net_pnl = self.gross_pnl - self.cumulative_fees - self.cumulative_slippage
        return self.net_pnl

    def to_dict(self):
        return {
            "coin": self.coin,
            "symbol": self.symbol,
            "ccxt_symbol": self.ccxt_symbol,
            "binance_symbol": self.binance_symbol,
            "entry_time": self.entry_timestamp,
            "exit_time": self.exit_timestamp,
            "periods_held": self.periods_held,
            "duration_hours": self.periods_held * 8,
            "allocated_capital": round(self.allocated_capital, 2),
            "entry_basis_bps": round(self.entry_basis * 10000, 2),
            "exit_basis_bps": round(self.exit_basis * 10000, 2) if self.exit_basis is not None else 0.0,
            "basis_change_bps": round(((self.exit_basis or 0) - self.entry_basis) * 10000, 2),
            "funding_collected": round(self.cumulative_funding, 2),
            "price_delta_pnl": round(self.cumulative_spot_pnl + self.cumulative_perp_pnl, 2),
            "gross_pnl": round(self.gross_pnl, 2),
            "total_fees": round(self.cumulative_fees, 2),
            "total_slippage": round(self.cumulative_slippage, 2),
            "net_pnl": round(self.net_pnl, 2),
            "net_roi_pct": round((self.net_pnl / self.allocated_capital) * 100.0, 3),
            "exit_reason": self.exit_reason
        }

class BacktestEngine:
    def __init__(self, data_df, config=None):
        self.df = data_df.copy()
        self.config = config or BacktestConfig()
        
        # Ensure 'coin' column is normalized
        if "coin" not in self.df.columns and "symbol" in self.df.columns:
            self.df["coin"] = self.df["symbol"].apply(normalize_symbol)
        elif "coin" in self.df.columns:
            self.df["coin"] = self.df["coin"].apply(normalize_symbol)
            
        # Ensure 'ccxt_symbol' and 'binance_symbol' are present
        self.df["ccxt_symbol"] = self.df["coin"].apply(lambda c: get_coin_metadata(c)["ccxt"])
        self.df["binance_symbol"] = self.df["coin"].apply(lambda c: get_coin_metadata(c)["binance"])
        
        self.timestamps = sorted(self.df["timestamp"].unique())
        self.coins = [c for c in COIN_ORDER if c in self.df["coin"].unique()]
        
        # Index by (timestamp, coin)
        self.indexed_data = self.df.set_index(["timestamp", "coin"]).sort_index()

    def run_funding_radar_strategy(self):
        capital = self.config.initial_capital
        equity_curve = []
        closed_trades = []
        active_positions = {}
        prev_prices = {}
        
        total_fees = 0.0
        total_slippage = 0.0
        total_gross_pnl = 0.0
        
        for t_idx, ts in enumerate(self.timestamps):
            current_slice = self.indexed_data.loc[ts]
            
            # Step 1: Update active positions with latest market prices & funding
            for coin in list(active_positions.keys()):
                pos = active_positions[coin]
                row = current_slice.loc[coin]
                s_prev, p_prev = prev_prices[coin]
                s_curr = row["spot_close"]
                p_curr = row["perp_close"]
                f_rate = row["actual_future_funding"]
                
                gross_step, fund_cash, price_pnl = pos.update_period(s_prev, s_curr, p_prev, p_curr, f_rate)
                capital += gross_step
                total_gross_pnl += gross_step
                
                # Check Exit Conditions:
                sq_prob = row.get("squeeze_probability", 0.0)
                sq_label = row.get("squeeze_label", 0)
                rv = row.get("realised_volatility", 0.02)
                q50 = row.get("q50_funding", 0.0)
                
                exit_triggered = False
                exit_reason = ""
                dynamic_slip = 1.0
                
                # 1. Stage 1 Emergency Squeeze Exit
                if sq_prob >= self.config.squeeze_exit_thresh or sq_label == 1:
                    exit_triggered = True
                    exit_reason = "EMERGENCY_SQUEEZE_EXIT"
                    dynamic_slip = 1.0 + 2.5 * (rv / 0.02) + 2.0
                # 2. Funding Inversion or Bear Flush
                elif q50 <= 0.00005 or f_rate < -0.00005:
                    exit_triggered = True
                    exit_reason = "FUNDING_INVERSION_OR_DECAY"
                    dynamic_slip = 1.0 + (rv / 0.02)
                # 3. Hysteresis Target Reached
                elif pos.periods_held >= 5 and q50 < 0.00015:
                    exit_triggered = True
                    exit_reason = "HYSTERESIS_TARGET_REACHED"
                # 4. Stop-Loss Circuit Breaker
                elif (pos.cumulative_spot_pnl + pos.cumulative_perp_pnl) / pos.allocated_capital < -0.012:
                    exit_triggered = True
                    exit_reason = "BASIS_STOP_LOSS"
                    dynamic_slip = 1.5
                    
                if exit_triggered:
                    pos.close_position(ts, s_curr, p_curr, exit_reason, dynamic_slippage_mult=dynamic_slip)
                    capital -= (pos.exit_fee + pos.exit_slippage)
                    total_fees += (pos.entry_fee + pos.exit_fee)
                    total_slippage += (pos.entry_slippage + pos.exit_slippage)
                    closed_trades.append(pos)
                    del active_positions[coin]
            
            # Step 2: Rank opportunities across coins using Funding Radar Score
            candidates = []
            for coin in self.coins:
                if coin in active_positions:
                    continue
                row = current_slice.loc[coin]
                q10 = row["q10_funding"]
                q50 = row["q50_funding"]
                q90 = row["q90_funding"]
                p_spike = row.get("spike_probability", 0.0)
                p_squeeze = row.get("squeeze_probability", 0.0)
                rv = row.get("realised_volatility", 0.02)
                
                uncertainty_band = max(0.00005, q90 - q10)
                
                if (q10 >= self.config.per_period_hurdle) and (p_spike >= self.config.spike_prob_thresh) and (p_squeeze < 0.35):
                    expected_net_edge = max(0.0, q10 - self.config.per_period_hurdle)
                    risk_penalty = 1.0 + 3.0 * p_squeeze + 1.5 * (rv / 0.02)
                    radar_score = (expected_net_edge / uncertainty_band) / risk_penalty
                    candidates.append((coin, radar_score, row))
                    
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            # Step 3: Capital Allocation for new entrants
            available_slots = self.config.max_active_coins - len(active_positions)
            if available_slots > 0 and len(candidates) > 0:
                top_picks = candidates[:available_slots]
                total_score = sum(c[1] for c in top_picks)
                
                allocated_now = sum(p.allocated_capital for p in active_positions.values())
                free_cash = max(0.0, capital - allocated_now)
                
                for coin, score, row in top_picks:
                    if total_score > 0 and free_cash > 8000:
                        weight = min(self.config.max_coin_weight, score / total_score)
                        trade_alloc = min(capital * weight, free_cash * 0.90)
                        
                        if trade_alloc >= 8000:
                            s_price = row["spot_close"]
                            p_price = row["perp_close"]
                            new_pos = DeltaNeutralPosition(coin, ts, trade_alloc, s_price, p_price, self.config)
                            capital -= (new_pos.entry_fee + new_pos.entry_slippage)
                            active_positions[coin] = new_pos
                            free_cash -= trade_alloc

            for coin in self.coins:
                row = current_slice.loc[coin]
                prev_prices[coin] = (row["spot_close"], row["perp_close"])
                
            equity_curve.append({
                "timestamp": ts,
                "strategy": "Funding_Radar_AI",
                "equity": capital,
                "active_positions_count": len(active_positions)
            })

        last_ts = self.timestamps[-1]
        last_slice = self.indexed_data.loc[last_ts]
        for coin, pos in list(active_positions.items()):
            row = last_slice.loc[coin]
            pos.close_position(last_ts, row["spot_close"], row["perp_close"], "BACKTEST_END_CLOSE")
            capital -= (pos.exit_fee + pos.exit_slippage)
            total_fees += (pos.entry_fee + pos.exit_fee)
            total_slippage += (pos.entry_slippage + pos.exit_slippage)
            closed_trades.append(pos)
            
        trades_df = pd.DataFrame([p.to_dict() for p in closed_trades])
        eq_df = pd.DataFrame(equity_curve)
        eq_df.loc[eq_df.index[-1], "equity"] = capital
        
        summary = compute_full_performance_summary(
            "Funding Radar (Hybrid AI)",
            eq_df["equity"].values,
            self.config.initial_capital,
            trades_df,
            fee_total=total_fees,
            slippage_total=total_slippage,
            gross_pnl=total_gross_pnl
        )
        return eq_df, trades_df, summary

    def run_point_forecast_strategy(self):
        capital = self.config.initial_capital
        equity_curve = []
        closed_trades = []
        active_positions = {}
        prev_prices = {}
        
        total_fees = 0.0
        total_slippage = 0.0
        total_gross_pnl = 0.0
        
        for t_idx, ts in enumerate(self.timestamps):
            current_slice = self.indexed_data.loc[ts]
            
            for coin in list(active_positions.keys()):
                pos = active_positions[coin]
                row = current_slice.loc[coin]
                s_prev, p_prev = prev_prices[coin]
                s_curr = row["spot_close"]
                p_curr = row["perp_close"]
                f_rate = row["actual_future_funding"]
                
                gross_step, _, _ = pos.update_period(s_prev, s_curr, p_prev, p_curr, f_rate)
                capital += gross_step
                total_gross_pnl += gross_step
                
                q50 = row.get("q50_funding", 0.0)
                sq_label = row.get("squeeze_label", 0)
                
                if q50 < 0.00030:
                    slip_mult = 1.0 + (3.0 if sq_label == 1 else 0.5)
                    pos.close_position(ts, s_curr, p_curr, "Q50_THRESHOLD_EXIT", dynamic_slippage_mult=slip_mult)
                    capital -= (pos.exit_fee + pos.exit_slippage)
                    total_fees += (pos.entry_fee + pos.exit_fee)
                    total_slippage += (pos.entry_slippage + pos.exit_slippage)
                    closed_trades.append(pos)
                    del active_positions[coin]

            candidates = []
            for coin in self.coins:
                if coin in active_positions:
                    continue
                row = current_slice.loc[coin]
                q50 = row["q50_funding"]
                if q50 >= 0.00030:
                    candidates.append((coin, q50, row))
                    
            candidates.sort(key=lambda x: x[1], reverse=True)
            available_slots = self.config.max_active_coins - len(active_positions)
            if available_slots > 0 and len(candidates) > 0:
                top_picks = candidates[:available_slots]
                free_cash = max(0.0, capital - sum(p.allocated_capital for p in active_positions.values()))
                alloc_each = free_cash / len(top_picks) if len(top_picks) > 0 else 0
                alloc_each = min(alloc_each, capital * self.config.max_coin_weight)
                
                for coin, q50, row in top_picks:
                    if alloc_each >= 8000:
                        s_price = row["spot_close"]
                        p_price = row["perp_close"]
                        new_pos = DeltaNeutralPosition(coin, ts, alloc_each, s_price, p_price, self.config)
                        capital -= (new_pos.entry_fee + new_pos.entry_slippage)
                        active_positions[coin] = new_pos

            for coin in self.coins:
                row = current_slice.loc[coin]
                prev_prices[coin] = (row["spot_close"], row["perp_close"])
                
            equity_curve.append({
                "timestamp": ts,
                "strategy": "Point_Forecast_Only",
                "equity": capital,
                "active_positions_count": len(active_positions)
            })

        last_ts = self.timestamps[-1]
        last_slice = self.indexed_data.loc[last_ts]
        for coin, pos in list(active_positions.items()):
            row = last_slice.loc[coin]
            pos.close_position(last_ts, row["spot_close"], row["perp_close"], "BACKTEST_END_CLOSE")
            capital -= (pos.exit_fee + pos.exit_slippage)
            total_fees += (pos.entry_fee + pos.exit_fee)
            total_slippage += (pos.entry_slippage + pos.exit_slippage)
            closed_trades.append(pos)
            
        trades_df = pd.DataFrame([p.to_dict() for p in closed_trades])
        eq_df = pd.DataFrame(equity_curve)
        eq_df.loc[eq_df.index[-1], "equity"] = capital
        
        summary = compute_full_performance_summary(
            "Point Forecast Only",
            eq_df["equity"].values,
            self.config.initial_capital,
            trades_df,
            fee_total=total_fees,
            slippage_total=total_slippage,
            gross_pnl=total_gross_pnl
        )
        return eq_df, trades_df, summary

    def run_naive_always_on_strategy(self):
        capital = self.config.initial_capital
        equity_curve = []
        n_coins = len(self.coins)
        alloc_per_coin = capital / n_coins
        
        first_ts = self.timestamps[0]
        first_slice = self.indexed_data.loc[first_ts]
        
        positions = {}
        total_fees = 0.0
        total_slippage = 0.0
        total_gross_pnl = 0.0
        
        for coin in self.coins:
            row = first_slice.loc[coin]
            pos = DeltaNeutralPosition(coin, first_ts, alloc_per_coin, row["spot_close"], row["perp_close"], self.config)
            capital -= (pos.entry_fee + pos.entry_slippage)
            total_fees += pos.entry_fee
            total_slippage += pos.entry_slippage
            positions[coin] = pos
            
        prev_prices = {coin: (first_slice.loc[coin]["spot_close"], first_slice.loc[coin]["perp_close"]) for coin in self.coins}
        
        for t_idx, ts in enumerate(self.timestamps):
            current_slice = self.indexed_data.loc[ts]
            
            for coin in self.coins:
                pos = positions[coin]
                row = current_slice.loc[coin]
                s_prev, p_prev = prev_prices[coin]
                s_curr = row["spot_close"]
                p_curr = row["perp_close"]
                f_rate = row["actual_future_funding"]
                
                gross_step, fund_cash, price_pnl = pos.update_period(s_prev, s_curr, p_prev, p_curr, f_rate)
                capital += gross_step
                total_gross_pnl += gross_step
                prev_prices[coin] = (s_curr, p_curr)
                
            equity_curve.append({
                "timestamp": ts,
                "strategy": "Naive_Always_On",
                "equity": capital,
                "active_positions_count": n_coins
            })

        last_ts = self.timestamps[-1]
        last_slice = self.indexed_data.loc[last_ts]
        closed_trades = []
        for coin in self.coins:
            pos = positions[coin]
            row = last_slice.loc[coin]
            pos.close_position(last_ts, row["spot_close"], row["perp_close"], "BACKTEST_END_CLOSE")
            capital -= (pos.exit_fee + pos.exit_slippage)
            total_fees += pos.exit_fee
            total_slippage += pos.exit_slippage
            closed_trades.append(pos)
            
        trades_df = pd.DataFrame([p.to_dict() for p in closed_trades])
        eq_df = pd.DataFrame(equity_curve)
        eq_df.loc[eq_df.index[-1], "equity"] = capital
        
        summary = compute_full_performance_summary(
            "Naive Always-On Carry",
            eq_df["equity"].values,
            self.config.initial_capital,
            trades_df,
            fee_total=total_fees,
            slippage_total=total_slippage,
            gross_pnl=total_gross_pnl
        )
        return eq_df, trades_df, summary