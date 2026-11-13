import csv
import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

ASSETS = ["BTC", "ADA", "AVAX", "BNB", "ETH", "SOL", "DOGE", "LINK", "LTC", "XRP"]

START = int(datetime(2026, 5, 30, 16, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2026, 9, 10, 8, tzinfo=timezone.utc).timestamp() * 1000)
INTERVAL = 8 * 60 * 60 * 1000

def get_json(base, params):
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "KRYPT"})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.loads(response.read().decode("utf-8"))

def get_funding(symbol):
    records = []
    cursor = START
    while cursor <= END:
        batch = get_json(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": cursor, "endTime": END, "limit": 1000}
        )
        if not batch:
            break
        records.extend(batch)
        next_cursor = int(batch[-1]["fundingTime"]) + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if len(batch) < 1000:
            break
        time.sleep(0.15)
    return records

def get_candles(base, symbol, start, end):
    return get_json(base, {
        "symbol": symbol,
        "interval": "8h",
        "startTime": start,
        "endTime": end,
        "limit": 1000
    })

output = []

for coin in ASSETS:
    symbol = coin + "USDT"
    print("Downloading", coin, symbol, flush=True)

    funding = get_funding(symbol)
    selected = []

    for record in funding:
        original = int(record["fundingTime"])
        aligned = round(original / INTERVAL) * INTERVAL
        if START <= aligned <= END and abs(original - aligned) <= 60000:
            selected.append((record, aligned - INTERVAL, aligned))

    if not selected:
        raise RuntimeError("No funding records returned for " + symbol)

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
            "timestamp": datetime.fromtimestamp(aligned / 1000, timezone.utc).isoformat(),
            "spot_close": spot_map[candle_open],
            "perp_close": perp_map[candle_open],
            "actual_future_funding": float(record["fundingRate"]),
            "mark_price": float(record["markPrice"]),
            "candle_open_time": candle_open
        })
        matched += 1

    print(" Matched:", matched, "/", len(selected), flush=True)

counts = {coin: sum(1 for row in output if row["coin"] == coin) for coin in ASSETS}
print("\nROWS PER ASSET:")
for coin, count in counts.items():
    print(coin, count)

missing = [coin for coin, count in counts.items() if count == 0]
if missing:
    raise RuntimeError("Missing assets: " + ", ".join(missing))

os.makedirs("outputs", exist_ok=True)
path = "outputs/historical_market_data_10_assets.csv"

with open(path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=output[0].keys())
    writer.writeheader()
    writer.writerows(output)

print("\nSUCCESS:", len(output), "rows saved to", path)
