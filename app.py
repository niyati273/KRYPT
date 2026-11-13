
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import pandas as pd
import joblib
import json

# -----------------------------
# KRYPT API
# -----------------------------

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="KRYPT API",
    description="Cryptocurrency Funding Rate Prediction API",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to frontend domain before production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# LOAD TRAINED MODEL
# -----------------------------

model = joblib.load(
    BASE_DIR / "models" / "KRYPT_rf_model.pkl"
)

# -----------------------------
# LOAD HISTORICAL DATA
# -----------------------------

with open(
    BASE_DIR / "data" / "bitcoin_funding.json",
    "r",
    encoding="utf-8"
) as file:
    raw_data = json.load(file)

df = pd.DataFrame(raw_data)

df["fundingRate"] = pd.to_numeric(df["fundingRate"])
df["markPrice"] = pd.to_numeric(df["markPrice"])
df["fundingTime"] = pd.to_datetime(
    df["fundingTime"], unit="ms"
)

df["funding_rate_change"] = df["fundingRate"].diff()
df["mark_price_return"] = df["markPrice"].pct_change()

clean = df.dropna(
    subset=["funding_rate_change", "mark_price_return"]
).reset_index(drop=True)

FEATURES = [
    "fundingRate",
    "markPrice",
    "funding_rate_change",
    "mark_price_return"
]

# -----------------------------
# REQUEST FORMAT
# -----------------------------

class PredictionInput(BaseModel):
    fundingRate: float
    markPrice: float
    funding_rate_change: float
    mark_price_return: float

# -----------------------------
# API ROUTES
# -----------------------------

@app.get("/")
def home():
    return {
        "project": "KRYPT",
        "status": "API running",
        "model": "Random Forest Classifier"
    }


@app.get("/api/overview")
def overview():
    latest = clean.iloc[-1]

    return {
        "asset": "BTCUSDT",
        "observations": len(clean),
        "latest_funding_rate": float(latest["fundingRate"]),
        "latest_mark_price": float(latest["markPrice"]),
        "history": [
            {
                "time": row["fundingTime"].isoformat(),
                "funding_rate": float(row["fundingRate"])
            }
            for _, row in clean.tail(100).iterrows()
        ]
    }


@app.post("/api/predict")
def predict(data: PredictionInput):
    input_data = pd.DataFrame([{
        "fundingRate": data.fundingRate,
        "markPrice": data.markPrice,
        "funding_rate_change": data.funding_rate_change,
        "mark_price_return": data.mark_price_return
    }], columns=FEATURES)

    probability = model.predict_proba(input_data)[0][1]
    prediction = int(model.predict(input_data)[0])

    return {
        "spike_probability": float(probability),
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
        "features": FEATURES
    }
