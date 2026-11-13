
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
MODEL_PATH = BASE_DIR / "models" / "astraquant_rf_model.pkl"

app = FastAPI(
    title="KRYPT API",
    description="Multi-asset cryptocurrency funding analytics",
    version="2.0"
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
    asset = next((item for item in ASSETS if item["id"] == asset_id.upper()), None)

    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        df = load_asset(asset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read dataset: {exc}")

    return asset, df


class PredictionInput(BaseModel):
    fundingRate: float
    markPrice: float
    funding_rate_change: float
    mark_price_return: float


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
    asset, df = get_asset("BTC")
    detail = asset_detail("BTC")

    if not detail["latest_features"]:
        raise HTTPException(status_code=400, detail="BTC features are not available")

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


@app.post("/api/predict")
def predict(data: PredictionInput):
    if model is None:
        raise HTTPException(status_code=503, detail="Random Forest model is unavailable")

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
