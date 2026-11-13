
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import pandas as pd
import joblib
import json
import math

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
MODEL_PATH = BASE_DIR / "models" / "astraquant_rf_model.pkl"

app = FastAPI(
    title="KRYPT API",
    description="Multi-asset cryptocurrency funding analytics and historical backtesting",
    version="2.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSETS = [
    {"id": "BTC", "name": "Bitcoin", "symbol": "BTCUSDT", "file": "bitcoin_funding.json"},
    {"id": "ETH", "name": "Ethereum", "symbol": "ETHUSDT", "file": "eut.json"},
    {"id": "BNB", "name": "BNB", "symbol": "BNBUSDT", "file": "bnb.json"},
    {"id": "SOL", "name": "Solana", "symbol": "SOLUSDT", "file": "sol.json"},
    {"id": "ADA", "name": "Cardano", "symbol": "ADAUSDT", "file": "ada.json"},
    {"id": "AVAX", "name": "Avalanche", "symbol": "AVAXUSDT", "file": "avax.json"},
    {"id": "XRP", "name": "XRP", "symbol": "XRPUSDT", "file": "xrp.json"},
    {"id": "DOGE", "name": "Dogecoin", "symbol": "DOGEUSDT", "file": "dodge.json"},
    {"id": "LINK", "name": "Chainlink", "symbol": "LINKUSDT", "file": "link.json"},
    {"id": "LTC", "name": "Litecoin", "symbol": "LTCUSDT", "file": "ltc.json"},
]

FEATURES = [
    "fundingRate",
    "markPrice",
    "funding_rate_change",
    "mark_price_return"
]

try:
    model = joblib.load(MODEL_PATH)
except Exception as exc:
    print(f"Warning: Random Forest model could not be loaded: {exc}")
    model = None


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def safe_float(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def load_asset(asset):
    path = DATA_DIR / asset["file"]

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {asset['file']}")

    with open(path, "r", encoding="utf-8") as file:
        raw = json.load(file)

    df = pd.DataFrame(raw)

    required = ["fundingTime", "fundingRate", "markPrice"]

    for column in required:
        if column not in df.columns:
            raise ValueError(f"{asset['file']} is missing {column}")

    df["fundingTime"] = pd.to_numeric(df["fundingTime"], errors="coerce")
    df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    df["markPrice"] = pd.to_numeric(df["markPrice"], errors="coerce")

    df["fundingTime"] = pd.to_datetime(
        df["fundingTime"], unit="ms", errors="coerce"
    )

    df = df.dropna(subset=["fundingTime", "fundingRate"])
    df = df.sort_values("fundingTime")
    df = df.drop_duplicates(subset=["fundingTime"], keep="last")
    df = df.reset_index(drop=True)

    df["funding_rate_change"] = df["fundingRate"].diff()
    df["mark_price_return"] = df["markPrice"].pct_change()

    return df


def asset_summary(asset, df):
    valid = df.dropna(subset=["fundingRate"])
    latest = valid.iloc[-1] if not valid.empty else None

    return {
        "id": asset["id"],
        "name": asset["name"],
        "symbol": asset["symbol"],
        "observations": int(len(df)),
        "latest_funding_rate": safe_float(latest["fundingRate"]) if latest is not None else None,
        "latest_mark_price": safe_float(latest["markPrice"]) if latest is not None else None,
        "start_date": df["fundingTime"].min().isoformat() if not df.empty else None,
        "end_date": df["fundingTime"].max().isoformat() if not df.empty else None,
        "missing_funding_rates": int(df["fundingRate"].isna().sum()),
        "missing_mark_prices": int(df["markPrice"].isna().sum()),
        "duplicate_timestamps_removed": 0
    }


def get_asset(asset_id):
    asset = next(
        (item for item in ASSETS if item["id"] == asset_id.upper()),
        None
    )

    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        df = load_asset(asset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read dataset: {exc}"
        )

    return asset, df


# =========================================================
# REQUEST MODEL
# =========================================================

class PredictionInput(BaseModel):
    fundingRate: float
    markPrice: float
    funding_rate_change: float
    mark_price_return: float


# =========================================================
# MAIN API ROUTES
# =========================================================

@app.get("/")
def home():
    return {
        "project": "KRYPT",
        "status": "API running",
        "assets_configured": len(ASSETS),
        "model": "Random Forest Classifier",
        "prediction_asset": "BTCUSDT",
        "simulation_only": True
    }


@app.get("/api/assets")
def list_assets():
    results = []

    for asset in ASSETS:
        try:
            df = load_asset(asset)
            results.append(asset_summary(asset, df))
        except Exception as exc:
            results.append({
                "id": asset["id"],
                "name": asset["name"],
                "symbol": asset["symbol"],
                "error": str(exc),
                "observations": 0,
                "latest_funding_rate": None,
                "latest_mark_price": None,
                "start_date": None,
                "end_date": None
            })

    return {
        "assets": results,
        "assets_configured": len(ASSETS),
        "simulation_only": True
    }


@app.get("/api/assets/{asset_id}")
def asset_detail(asset_id: str):
    asset, df = get_asset(asset_id)
    summary = asset_summary(asset, df)

    history = []

    for _, row in df.tail(300).iterrows():
        history.append({
            "time": row["fundingTime"].isoformat(),
            "funding_rate": safe_float(row["fundingRate"]),
            "mark_price": safe_float(row["markPrice"])
        })

    latest_features = None

    feature_rows = df.dropna(subset=[
        "fundingRate",
        "markPrice",
        "funding_rate_change",
        "mark_price_return"
    ])

    if not feature_rows.empty:
        row = feature_rows.iloc[-1]

        latest_features = {
            "fundingRate": safe_float(row["fundingRate"]),
            "markPrice": safe_float(row["markPrice"]),
            "funding_rate_change": safe_float(row["funding_rate_change"]),
            "mark_price_return": safe_float(row["mark_price_return"])
        }

    return {
        **summary,
        "history": history,
        "latest_features": latest_features,
        "data_mode": "Historical dataset",
        "simulation_only": True
    }


@app.get("/api/overview")
def overview():
    detail = asset_detail("BTC")

    if not detail["latest_features"]:
        raise HTTPException(
            status_code=400,
            detail="BTC features are not available"
        )

    return {
        "asset": "BTCUSDT",
        "observations": detail["observations"],
        "latest_funding_rate": detail["latest_funding_rate"],
        "latest_mark_price": detail["latest_mark_price"],
        "latest_features": detail["latest_features"],
        "history": [
            {
                "time": item["time"],
                "funding_rate": item["funding_rate"]
            }
            for item in detail["history"]
        ]
    }


# =========================================================
# RANDOM FOREST PREDICTION
# =========================================================

@app.post("/api/predict")
def predict(data: PredictionInput):
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Random Forest model is unavailable"
        )

    input_data = pd.DataFrame(
        [{
            "fundingRate": data.fundingRate,
            "markPrice": data.markPrice,
            "funding_rate_change": data.funding_rate_change,
            "mark_price_return": data.mark_price_return
        }],
        columns=FEATURES
    )

    probabilities = model.predict_proba(input_data)[0]

    if 1 not in list(model.classes_):
        raise HTTPException(
            status_code=500,
            detail="Model does not contain positive class 1"
        )

    positive_index = list(model.classes_).index(1)
    probability = float(probabilities[positive_index])
    prediction = int(model.predict(input_data)[0])

    return {
        "asset": "BTCUSDT",
        "spike_probability": probability,
        "prediction": prediction,
        "signal": "SPIKE FLAGGED" if prediction == 1 else "NO SPIKE FLAGGED",
        "model": "Random Forest Classifier",
        "simulation_only": True
    }


@app.get("/api/model")
def model_info():
    return {
        "model": "Random Forest Classifier",
        "accuracy": 0.72,
        "precision": 0.5227,
        "recall": 0.7667,
        "f1_score": 0.6216,
        "features": FEATURES,
        "asset": "BTCUSDT",
        "evaluation_type": "Preliminary historical evaluation; verify against training code",
        "simulation_only": True
    }


# =========================================================
# QUANT SIGNALS
# =========================================================

@app.get("/api/signals")
def get_quant_signals():
    possible_paths = [
        OUTPUT_DIR / "ps20_live_signals.csv",
        BASE_DIR / "ps20_live_signals.csv"
    ]

    signal_file = next(
        (path for path in possible_paths if path.exists()),
        None
    )

    if signal_file is None:
        raise HTTPException(
            status_code=404,
            detail="ps20_live_signals.csv was not found in outputs or project root"
        )

    try:
        df = pd.read_csv(signal_file)

        required_columns = [
            "coin",
            "spot_close",
            "basis_bps",
            "spike_probability",
            "trade_signal",
            "action_reason"
        ]

        missing = [
            column for column in required_columns
            if column not in df.columns
        ]

        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing signal columns: {missing}"
            )

        display_data = df[required_columns].copy()
        display_data = display_data.replace({float("nan"): None})

        return display_data.to_dict(orient="records")

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load signals: {exc}"
        )


# =========================================================
# HISTORICAL HOLD / SELL BACKTEST
# =========================================================

@app.get("/api/backtest")
def get_historical_backtest():

    file_path = OUTPUT_DIR / "historical_market_data_10_assets.csv"

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Historical market dataset not found in outputs folder"
        )

    try:
        df = pd.read_csv(file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read historical dataset: {exc}"
        )

    required_columns = {
        "coin",
        "timestamp",
        "mark_price",
        "actual_future_funding"
    }

    if not required_columns.issubset(df.columns):
        raise HTTPException(
            status_code=400,
            detail=f"Dataset must contain: {sorted(required_columns)}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce"
    )

    df["mark_price"] = pd.to_numeric(
        df["mark_price"],
        errors="coerce"
    )

    df["actual_future_funding"] = pd.to_numeric(
        df["actual_future_funding"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "coin",
            "timestamp",
            "mark_price",
            "actual_future_funding"
        ]
    )

    df = df[df["mark_price"] > 0]
    df = df.sort_values(["coin", "timestamp"])

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No valid historical rows available for backtesting"
        )

    # Strategy configuration
    FUNDING_THRESHOLD = 0.00005
    TRANSACTION_COST_PER_SIDE = 0.0012
    INITIAL_CAPITAL = 100000.0

    all_decisions = []
    summaries = []

    for coin, group in df.groupby("coin"):

        group = group.sort_values("timestamp").reset_index(drop=True)

        capital = INITIAL_CAPITAL
        in_position = False

        entry_price = None
        entry_time = None

        total_trades = 0
        winning_trades = 0

        decisions = []

        for _, row in group.iterrows():

            funding = float(row["actual_future_funding"])
            price = float(row["mark_price"])
            timestamp = row["timestamp"]

            action = "WAIT"
            reason = "Entry condition not met"
            realized_return = None

            # ENTER A SIMULATED POSITION
            if not in_position and funding > FUNDING_THRESHOLD:

                in_position = True
                entry_price = price
                entry_time = timestamp

                # Deduct entry transaction cost once
                capital *= (1 - TRANSACTION_COST_PER_SIDE)

                action = "HOLD"
                reason = "Entry threshold crossed; simulated position opened"

            # EXIT AN EXISTING POSITION
            elif in_position and funding <= FUNDING_THRESHOLD:

                price_return = (price / entry_price) - 1

                # Apply exit transaction cost once.
                # Entry cost was already deducted when opening.
                realized_return = (
                    (1 + price_return) *
                    (1 - TRANSACTION_COST_PER_SIDE)
                ) - 1

                capital *= (1 + realized_return)

                total_trades += 1

                if realized_return > 0:
                    winning_trades += 1

                action = "SELL"
                reason = "Funding rate reached or fell below exit threshold"

                in_position = False

            elif in_position:

                action = "HOLD"
                reason = "Position remains open; exit condition not met"

            decisions.append({
                "coin": str(coin),
                "timestamp": timestamp.isoformat(),
                "funding_rate": round(funding, 8),
                "mark_price": round(price, 6),
                "action": action,
                "reason": reason,
                "entry_price": round(entry_price, 6) if in_position else None,
                "entry_timestamp": entry_time.isoformat() if entry_time else None,
                "realized_trade_return_percent": (
                    round(realized_return * 100, 4)
                    if realized_return is not None else None
                ),
                "portfolio_value": round(capital, 2)
            })

        # Close any remaining position at the final historical observation.
        if in_position and len(group) > 0:

            final_price = float(group.iloc[-1]["mark_price"])

            price_return = (final_price / entry_price) - 1

            final_trade_return = (
                (1 + price_return) *
                (1 - TRANSACTION_COST_PER_SIDE)
            ) - 1

            capital *= (1 + final_trade_return)

            total_trades += 1

            if final_trade_return > 0:
                winning_trades += 1

            # Update the final decision row to show the simulated exit.
            decisions[-1]["action"] = "SELL"
            decisions[-1]["reason"] = (
                "Backtest ended; remaining position closed at final historical price"
            )
            decisions[-1]["realized_trade_return_percent"] = round(
                final_trade_return * 100, 4
            )
            decisions[-1]["portfolio_value"] = round(capital, 2)

            in_position = False

        final_return = (
            (capital / INITIAL_CAPITAL) - 1
        ) * 100

        summaries.append({
            "coin": str(coin),
            "initial_capital": INITIAL_CAPITAL,
            "final_equity": round(capital, 2),
            "return_percent": round(final_return, 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate_percent": round(
                (winning_trades / total_trades) * 100, 2
            ) if total_trades else 0
        })

        all_decisions.extend(decisions)

    # Save results for reviewer inspection
    OUTPUT_DIR.mkdir(exist_ok=True)

    decisions_file = OUTPUT_DIR / "hold_sell_backtest_decisions.csv"
    summary_file = OUTPUT_DIR / "hold_sell_backtest_summary.csv"

    pd.DataFrame(all_decisions).to_csv(
        decisions_file,
        index=False
    )

    pd.DataFrame(summaries).to_csv(
        summary_file,
        index=False
    )

    return {
        "strategy": "Historical Funding Threshold Baseline",
        "strategy_type": "Rule-based historical simulation",
        "threshold": FUNDING_THRESHOLD,
        "transaction_cost_per_side": TRANSACTION_COST_PER_SIDE,
        "initial_capital_per_asset": INITIAL_CAPITAL,
        "assets_tested": len(summaries),
        "total_observations": len(all_decisions),
        "summary": summaries,
        "decisions": all_decisions,
        "saved_files": {
            "decisions": str(decisions_file),
            "summary": str(summary_file)
        },
        "disclaimer": (
            "Experimental rule-based simulation, not a validated Random Forest "
            "or XGBoost backtest. Results depend on the historical dataset, "
            "funding timestamp alignment, execution assumptions and costs."
        )
    }


# =========================================================
# END OF KRYPT API
# =========================================================

