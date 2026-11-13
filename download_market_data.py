
import json
import csv
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

ASSETS = {
    "BTC": "data/bitcoin_funding.json",
    "ADA": "data/ada.json",
    "AVAX": "data/avax.json",
    "BNB": "data/bnb.json",
    "ETH": "data/eut.json",
    "SOL": "data/sol.json",
}

START = int(datetime(2026, 5, 30, 16, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2026, 9, 10, 8, tzinfo=timezone.utc).timestamp() * 1000)
INTERVAL = 8 * 60 * 60 * 1000

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "KRYPT"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def get_candles(base, symbol, start, end):
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "8h",
        "startTime": start,
        "endTime": end,
        "limit": 1000
    })
    return get_json(base + "?" + params)

output = []

for coin, path in ASSETS.items():
    print("Downloading:", coin)

    with open(path, encoding="utf-8") as f:
        funding = json.load(f)

    selected = []
    for record in funding:
        original = int(record["fundingTime"])
        aligned = round(original / INTERVAL) * INTERVAL
        if START <= aligned <= END:
            if abs(original - aligned) > 60000:
                raise ValueError("Unexpected timestamp: " + coin)
            selected.append((record, aligned - INTERVAL, aligned))

    if not selected:
        print("  No funding records in selected period")
        continue

    symbol = selected[0][0]["symbol"]
    first_open = min(x[1] for x in selected)
    last_open = max(x[1] for x in selected)

    spot = get_candles(
        "https://api.binance.com/api/v3/klines",
        symbol, first_open, last_open
    )
    perp = get_candles(
        "https://fapi.binance.com/fapi/v1/klines",
        symbol, first_open, last_open
    )

    spot_map = {int(x[0]): float(x[4]) for x in spot}
    perp_map = {int(x[0]): float(x[4]) for x in perp}

    matched = 0
    for record, candle_open, aligned in selected:
        if candle_open not in spot_map or candle_open not in perp_map:
            continue

        output.append({
            "coin": coin,
            "timestamp": datetime.fromtimestamp(
                aligned / 1000, timezone.utc
            ).isoformat(),
            "spot_close": spot_map[candle_open],
            "perp_close": perp_map[candle_open],
            "actual_future_funding": float(record["fundingRate"]),
            "mark_price": float(record["markPrice"]),
            "candle_open_time": candle_open
        })
        matched += 1

    print("  Matched:", matched, "/", len(selected))

if not output:
    raise RuntimeError("No matched data downloaded")

os.makedirs("outputs", exist_ok=True)

with open("outputs/historical_market_data_6_assets.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=output[0].keys())
    writer.writeheader()
    writer.writerows(output)

print("\nSUCCESS:", len(output), "rows saved")
