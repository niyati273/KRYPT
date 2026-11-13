import pandas as pd
from backtest import BacktestEngine, BacktestConfig

print("Loading Main Market Data...")
# 1. Load the main dataset that has 'coin', 'timestamp', 'spot_close', etc.
# ---> Change this to the actual name of your historical data file!
df = pd.read_csv('YOUR_MAIN_DATA_FILE.csv') 

print("Loading Niyati's ML predictions...")
# 2. Load Niyati's AI outputs
preds = pd.read_csv('../outputs/model_predictions.csv')

print("Merging AI predictions into Quantitative Engine...")
# 3. Stitch Niyati's probabilities into your main dataframe
df['spike_probability'] = preds['spike_probability']
df['predicted_spike'] = preds['predicted_spike']

print("Initializing Quantitative Engine...")
config = BacktestConfig()
engine = BacktestEngine(df, config=config)

print("Executing Delta-Neutral Strategy...")
eq_df, trades_df, summary = engine.run_funding_radar_strategy()

print("\n=== REVIEW 2: PERFORMANCE SUMMARY ===")
for key, value in summary.items():
    print(f"{key}: {value}")