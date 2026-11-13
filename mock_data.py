"""
mock_data.py - Realistic 10-Coin Predictions and Market Data Generator
Aligned strictly with SHARED_DATA_FORMAT.md, UPGRADE_FUNDING_RADAR.md, and Person D's official table.

Official 10-Coin Universe (in exact order):
1. Bitcoin -> BTC (ccxt: BTC/USDT:USDT, binance: BTCUSDT)
2. Ethereum -> ETH (ccxt: ETH/USDT:USDT, binance: ETHUSDT)
3. BNB -> BNB (ccxt: BNB/USDT:USDT, binance: BNBUSDT)
4. Solana -> SOL (ccxt: SOL/USDT:USDT, binance: SOLUSDT)
5. XRP -> XRP (ccxt: XRP/USDT:USDT, binance: XRPUSDT)
6. Dogecoin -> DOGE (ccxt: DOGE/USDT:USDT, binance: DOGEUSDT)
7. Cardano -> ADA (ccxt: ADA/USDT:USDT, binance: ADAUSDT)
8. Avalanche -> AVAX (ccxt: AVAX/USDT:USDT, binance: AVAXUSDT)
9. Chainlink -> LINK (ccxt: LINK/USDT:USDT, binance: LINKUSDT)
10. Litecoin -> LTC (ccxt: LTC/USDT:USDT, binance: LTCUSDT)
"""

import os
import re
import numpy as np
import pandas as pd

COIN_ORDER = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC"]

SYMBOL_METADATA = {
    "BTC": {"name": "Bitcoin", "ccxt": "BTC/USDT:USDT", "binance": "BTCUSDT", "slash": "BTC/USDT", "base_price": 65000.0, "vol": 0.015, "funding_vol": 0.00012, "base_volume": 1.2e8, "beta": 1.0},
    "ETH": {"name": "Ethereum", "ccxt": "ETH/USDT:USDT", "binance": "ETHUSDT", "slash": "ETH/USDT", "base_price": 3400.0, "vol": 0.020, "funding_vol": 0.00015, "base_volume": 8.5e7, "beta": 1.15},
    "BNB": {"name": "BNB", "ccxt": "BNB/USDT:USDT", "binance": "BNBUSDT", "slash": "BNB/USDT", "base_price": 575.0, "vol": 0.018, "funding_vol": 0.00014, "base_volume": 3.0e7, "beta": 0.95},
    "SOL": {"name": "Solana", "ccxt": "SOL/USDT:USDT", "binance": "SOLUSDT", "slash": "SOL/USDT", "base_price": 145.0, "vol": 0.035, "funding_vol": 0.00028, "base_volume": 4.5e7, "beta": 1.60},
    "XRP": {"name": "XRP", "ccxt": "XRP/USDT:USDT", "binance": "XRPUSDT", "slash": "XRP/USDT", "base_price": 0.58, "vol": 0.028, "funding_vol": 0.00022, "base_volume": 2.5e7, "beta": 1.25},
    "DOGE": {"name": "Dogecoin", "ccxt": "DOGE/USDT:USDT", "binance": "DOGEUSDT", "slash": "DOGE/USDT", "base_price": 0.125, "vol": 0.045, "funding_vol": 0.00040, "base_volume": 3.5e7, "beta": 1.85},
    "ADA": {"name": "Cardano", "ccxt": "ADA/USDT:USDT", "binance": "ADAUSDT", "slash": "ADA/USDT", "base_price": 0.45, "vol": 0.030, "funding_vol": 0.00025, "base_volume": 2.0e7, "beta": 1.35},
    "AVAX": {"name": "Avalanche", "ccxt": "AVAX/USDT:USDT", "binance": "AVAXUSDT", "slash": "AVAX/USDT", "base_price": 28.5, "vol": 0.038, "funding_vol": 0.00030, "base_volume": 2.2e7, "beta": 1.65},
    "LINK": {"name": "Chainlink", "ccxt": "LINK/USDT:USDT", "binance": "LINKUSDT", "slash": "LINK/USDT", "base_price": 16.50, "vol": 0.026, "funding_vol": 0.00020, "base_volume": 2.1e7, "beta": 1.20},
    "LTC": {"name": "Litecoin", "ccxt": "LTC/USDT:USDT", "binance": "LTCUSDT", "slash": "LTC/USDT", "base_price": 82.50, "vol": 0.024, "funding_vol": 0.00024, "base_volume": 2.6e7, "beta": 1.10},
}

def normalize_symbol(raw_sym):
    """
    Robust symbol normalizer:
    Accepts 'BTC', 'BTCUSDT', 'BTC/USDT', 'BTC/USDT:USDT' and maps to ('BTC', 'BTC/USDT:USDT', 'BTCUSDT')
    """
    s = str(raw_sym).strip().upper()
    for coin, meta in SYMBOL_METADATA.items():
        if s in [coin, meta["ccxt"], meta["binance"], meta["slash"], f"{coin}/USDT", f"{coin}-USDT"]:
            return coin
    for coin in COIN_ORDER:
        if s.startswith(coin):
            return coin
    return s

def get_coin_metadata(coin):
    norm_coin = normalize_symbol(coin)
    return SYMBOL_METADATA.get(norm_coin, SYMBOL_METADATA["BTC"])

def generate_realistic_crypto_series(n_periods=540, seed=42):
    """
    Generates realistic 8-hour intervals (540 steps = 180 days) for the 10 coins.
    Simulates spot prices, perp prices, basis blowouts, volume collapses, funding rates,
    quantile forecasts (q10, q50, q90), squeeze risks, and spike probabilities.
    """
    np.random.seed(seed)
    timestamps = pd.date_range(start="2026-05-15 00:00:00", periods=n_periods, freq="8h", tz="UTC")
    
    all_data = []
    
    for coin in COIN_ORDER:
        cfg = SYMBOL_METADATA[coin]
        base_p = cfg["base_price"]
        p_vol = cfg["vol"]
        f_vol = cfg["funding_vol"]
        base_v = cfg["base_volume"]
        beta = cfg["beta"]
        ccxt_sym = cfg["ccxt"]
        binance_sym = cfg["binance"]
        slash_sym = cfg["slash"]
        
        # Spot price simulation
        daily_drift = 0.0001
        price_returns = np.random.normal(loc=daily_drift, scale=p_vol, size=n_periods)
        
        # Market regime price impacts
        price_returns[61:115] += 0.005 * beta
        price_returns[116:145] += 0.015 * beta   # Sharp speculative pump
        price_returns[146:265] += 0.004 * beta
        price_returns[266:380] -= 0.009 * beta   # Extended bear flush
        price_returns[381:410] += 0.016 * beta   # Short squeeze surge
        price_returns[411:540] += 0.002
        
        spot_prices = base_p * np.exp(np.cumsum(price_returns))
        
        # Basis simulation: B_t = (P_perp - P_spot)/P_spot
        base_basis = np.random.normal(loc=0.0004, scale=0.00015, size=n_periods)
        
        squeeze_active = np.zeros(n_periods, dtype=int)
        squeeze_probs = np.random.uniform(0.02, 0.08, size=n_periods)
        
        # Squeeze #1 (intervals 118 to 142)
        for t in range(118, 143):
            if t < 124:
                squeeze_probs[t] = np.random.uniform(0.42, 0.58)
                base_basis[t] += 0.003 * beta
            else:
                squeeze_active[t] = 1
                squeeze_probs[t] = np.random.uniform(0.72, 0.96)
                blowout = 0.012 * beta + np.random.uniform(0.004, 0.008)
                base_basis[t] += blowout
                
        # Squeeze #2 (intervals 385 to 408)
        for t in range(385, 409):
            if t < 390:
                squeeze_probs[t] = np.random.uniform(0.44, 0.60)
                base_basis[t] += 0.003 * beta
            else:
                squeeze_active[t] = 1
                squeeze_probs[t] = np.random.uniform(0.70, 0.95)
                blowout = 0.010 * beta + np.random.uniform(0.003, 0.007)
                base_basis[t] += blowout

        # Bear winter: negative basis
        base_basis[266:380] -= np.random.uniform(0.0008, 0.0020, size=380-266)
        
        perp_prices = spot_prices * (1.0 + base_basis)
        
        volumes_spot = base_v * np.exp(np.random.normal(0, 0.25, size=n_periods))
        volumes_perp = volumes_spot * np.random.uniform(2.2, 3.6, size=n_periods)
        
        for sp in np.where(squeeze_active == 1)[0]:
            volumes_spot[sp] *= 0.35
            volumes_perp[sp] *= 2.40
            
        funding = np.zeros(n_periods)
        for t in range(n_periods):
            if squeeze_active[t] == 1:
                funding[t] = np.random.uniform(0.0008, 0.0020)
            elif (61 <= t <= 115) or (146 <= t <= 265):
                funding[t] = np.random.uniform(0.00045, 0.00160)
            elif (266 <= t <= 380):
                funding[t] = np.random.uniform(-0.00050, -0.00010)
            elif (0 <= t <= 60):
                funding[t] = np.random.normal(0.00012, f_vol)
            else:
                funding[t] = np.random.normal(0.00015, f_vol)

        funding_series = pd.Series(funding)
        funding_lag_1 = funding_series.shift(1).fillna(0.0001)
        funding_mean = funding_series.shift(1).rolling(window=30, min_periods=5).mean().fillna(0.0001)
        funding_volatility = funding_series.shift(1).rolling(window=30, min_periods=5).std().fillna(f_vol)
        
        spot_series = pd.Series(spot_prices)
        log_ret = np.log(spot_series / spot_series.shift(1)).fillna(0.0)
        realised_volatility = log_ret.rolling(window=30, min_periods=5).apply(lambda x: np.sqrt(np.sum(x**2))).fillna(p_vol)
        
        vol_spot_series = pd.Series(volumes_spot)
        volume_change = ((vol_spot_series - vol_spot_series.shift(1)) / vol_spot_series.shift(1)).fillna(0.0)
        
        theta_t = funding_series.shift(1).rolling(window=60, min_periods=10).quantile(0.90).fillna(0.0003)
        spike_label = (funding >= theta_t).astype(int)
        
        spike_prob_raw = (funding > 0.00035).astype(float) * 0.65 + 0.18 + (base_basis > 0.0008).astype(float) * 0.12
        spike_prob = np.clip(spike_prob_raw + np.random.normal(0, 0.05, size=n_periods), 0.01, 0.99)
        sq_prob = np.clip(squeeze_probs + np.random.normal(0, 0.03, size=n_periods), 0.01, 0.99)
        
        q50 = funding_mean + 0.72 * (funding - funding_mean) + np.random.normal(0, 0.00004, size=n_periods)
        band_width = 0.00012 + 0.0020 * realised_volatility + 0.00015 * sq_prob
        q10 = q50 - band_width
        q90 = q50 + band_width
        
        regime = np.zeros(n_periods, dtype=int)
        for t in range(n_periods):
            if sq_prob[t] > 0.40 or squeeze_active[t] == 1:
                regime[t] = 2
            elif spike_prob[t] > 0.50 or realised_volatility[t] > 0.035:
                regime[t] = 1
            else:
                regime[t] = 0
                
        trade_flag = (q50 > 0.00025).astype(int)
        actual_future_funding = funding
        
        for t in range(n_periods):
            all_data.append({
                "timestamp": timestamps[t].strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": slash_sym,
                "coin": coin,
                "ccxt_symbol": ccxt_sym,
                "binance_symbol": binance_sym,
                "funding_rate": round(float(funding[t]), 6),
                "spot_close": round(float(spot_prices[t]), 4),
                "perp_close": round(float(perp_prices[t]), 4),
                "spot_volume": round(float(volumes_spot[t]), 2),
                "perp_volume": round(float(volumes_perp[t]), 2),
                "basis": round(float(base_basis[t]), 6),
                "funding_lag_1": round(float(funding_lag_1.iloc[t]), 6),
                "funding_mean": round(float(funding_mean.iloc[t]), 6),
                "funding_volatility": round(float(funding_volatility.iloc[t]), 6),
                "volume_change": round(float(volume_change.iloc[t]), 4),
                "realised_volatility": round(float(realised_volatility.iloc[t]), 6),
                "spike_label": int(spike_label.iloc[t]),
                "squeeze_label": int(squeeze_active[t]),
                "q10_funding": round(float(q10[t]), 6),
                "q50_funding": round(float(q50[t]), 6),
                "q90_funding": round(float(q90[t]), 6),
                "regime": int(regime[t]),
                "spike_probability": round(float(spike_prob[t]), 4),
                "squeeze_probability": round(float(sq_prob[t]), 4),
                "trade_flag": int(trade_flag[t]),
                "actual_future_funding": round(float(actual_future_funding[t]), 6)
            })

    df = pd.DataFrame(all_data)
    df["dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by=["symbol", "dt"]).drop(columns=["dt"]).reset_index(drop=True)
    return df

def ensure_predictions_csv(output_path, force_regenerate=False):
    if os.path.exists(output_path) and not force_regenerate:
        print(f"[MOCK_DATA] Using existing predictions at: {output_path}")
        return pd.read_csv(output_path)
    
    print(f"[MOCK_DATA] Generating realistic 10-coin dataset (with LTC, matching Person D's table) at {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df = generate_realistic_crypto_series(n_periods=540, seed=42)
    df.to_csv(output_path, index=False)
    print(f"[MOCK_DATA] Successfully generated {len(df)} rows across {df['coin'].nunique()} assets.")
    return df

if __name__ == "__main__":
    test_path = os.path.join("..", "09_SHARED_Results", "predictions.csv")
    df = ensure_predictions_csv(test_path, force_regenerate=True)
    print(df.head())
