
import { useEffect, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

function FundingChart({ history }) {
  if (!history?.length) {
    return <div className="chart-empty">Waiting for historical data...</div>;
  }

  const values = history.map((item) => item.funding_rate);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * 800;
      const y = 180 - ((value - min) / range) * 150;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="chart-wrap">
      <svg viewBox="0 0 800 210" preserveAspectRatio="none">
        {[30, 80, 130, 180].map((y) => (
          <line key={y} x1="0" y1={y} x2="800" y2={y} className="grid-line" />
        ))}
        <polyline points={points} className="chart-line" />
      </svg>
      <div className="chart-labels">
        <span>Earlier observations</span>
        <span>Latest observations</span>
      </div>
    </div>
  );
}

function App() {
  const [overview, setOverview] = useState(null);
  const [model, setModel] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [predictionLoading, setPredictionLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        const [overviewResponse, modelResponse] = await Promise.all([
          fetch(`${API}/api/overview`),
          fetch(`${API}/api/model`),
        ]);

        if (!overviewResponse.ok || !modelResponse.ok) {
          throw new Error("Could not load API data.");
        }

        const overviewData = await overviewResponse.json();
        const modelData = await modelResponse.json();

        setOverview(overviewData);
        setModel(modelData);
      } catch {
        setError(
          "Unable to connect to the KRYPT backend. Check that the Python server is running."
        );
      }
    }

    loadData();
  }, []);

  // Send latest historical features to the Random Forest model
  const runPrediction = async () => {
    if (!overview?.latest_features) return;

    setPredictionLoading(true);
    setError("");
    setPrediction(null);

    try {
      const response = await fetch(`${API}/api/predict`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(overview.latest_features),
      });

      if (!response.ok) {
        throw new Error("Prediction request failed.");
      }

      const result = await response.json();
      setPrediction(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setPredictionLoading(false);
    }
  };

  return (
    <main>
      <nav className="navbar">
        <a className="brand" href="#">KRYPT<span>.</span></a>
        <div className="nav-links">
          <a href="#research">Research</a>
          <a href="#model">Model</a>
          <a href="#about">About</a>
        </div>
        <div className="nav-status">
          <span className="status-dot"></span>
          Research preview
        </div>
      </nav>

      <section className="hero">
        <div className="eyebrow">
          <span></span> QUANTITATIVE CRYPTO RESEARCH
        </div>

        <h1>
          Reading the signals
          <br />
          <span>behind the market.</span>
        </h1>

        <p className="hero-description">
          A machine learning research platform designed to identify
          unusual cryptocurrency funding-rate activity using historical
          market data.
        </p>

        <div className="hero-meta">
          <span>BTCUSDT</span>
          <span className="meta-divider"></span>
          <span>Historical dataset</span>
          <span className="meta-divider"></span>
          <span>Machine learning</span>
        </div>
      </section>

      <section className="metrics" id="model">
        <div className="metric">
          <span className="metric-label">OBSERVATIONS</span>
          <strong>{overview?.observations ?? "—"}</strong>
          <span className="metric-note">Historical records</span>
        </div>

        <div className="metric">
          <span className="metric-label">TEST ACCURACY</span>
          <strong>
            {model ? `${(model.accuracy * 100).toFixed(1)}%` : "—"}
          </strong>
          <span className="metric-note">Chronological test set</span>
        </div>

        <div className="metric">
          <span className="metric-label">SPIKE RECALL</span>
          <strong>
            {model ? `${(model.recall * 100).toFixed(1)}%` : "—"}
          </strong>
          <span className="metric-note">Test-set recall</span>
        </div>

        <div className="metric">
          <span className="metric-label">MODEL</span>
          <strong className="model-name">Random Forest</strong>
          <span className="metric-note">Classification model</span>
        </div>
      </section>

      <section className="research-section" id="research">
        <div className="section-heading">
          <div>
            <span className="section-kicker">01 / MARKET RESEARCH</span>
            <h2>Funding rate history</h2>
          </div>
          <span className="section-tag">BTCUSDT</span>
        </div>

        <div className="chart-card">
          <div className="chart-top">
            <div>
              <span className="small-label">LATEST FUNDING RATE</span>
              <strong className="latest-value">
                {overview
                  ? `${(overview.latest_funding_rate * 100).toFixed(4)}%`
                  : "—"}
              </strong>
            </div>
            <span className="chart-caption">Last 100 observations</span>
          </div>

          <FundingChart history={overview?.history} />
        </div>
      </section>

      {/* MACHINE LEARNING PREDICTION */}
      <section className="research-section" id="prediction">
        <div className="section-heading">
          <div>
            <span className="section-kicker">02 / MODEL INFERENCE</span>
            <h2>Spike detection</h2>
          </div>
          <span className="section-tag">RANDOM FOREST</span>
        </div>

        <div className="chart-card">
          <div className="chart-top">
            <div>
              <span className="small-label">MODEL STATUS</span>
              <strong className="latest-value">
                {prediction ? "Prediction complete" : "Ready to analyse"}
              </strong>
            </div>

            <span className="chart-caption">BTCUSDT · Historical data</span>
          </div>

          <p className="hero-description">
            Run the trained Random Forest model on the latest four
            engineered BTC features to classify potential funding-rate
            spike activity.
          </p>

          <button
            className="prediction-button"
            onClick={runPrediction}
            disabled={!overview || predictionLoading}
          >
            {predictionLoading
              ? "Analysing..."
              : prediction
              ? "Run prediction again"
              : "Run spike detection"}
          </button>

          {prediction && (
            <div className="prediction-result">
              <span className="small-label">PREDICTION RESULT</span>

              <h3>
                {prediction.signal}
              </h3>

              <div className="prediction-probability">
                <span>Estimated spike probability</span>
                <strong>
                  {(prediction.spike_probability * 100).toFixed(2)}%
                </strong>
              </div>

              <div className="prediction-bar">
                <div
                  className="prediction-bar-fill"
                  style={{
                    width: `${prediction.spike_probability * 100}%`,
                  }}
                />
              </div>

              <p className="chart-caption">
                Model: {prediction.model}
              </p>
            </div>
          )}

          <p className="chart-caption">
            Educational simulation only. Model probability is a
            classification estimate, not a prediction of profit.
          </p>
        </div>
      </section>

      <section className="explanation-section" id="about">
        <div>
          <span className="section-kicker">03 / THE APPROACH</span>
          <h2>From market data<br />to model signals.</h2>
        </div>
        <p>
          KRYPT studies historical funding rates and related market
          features to classify whether the next observed funding rate
          may cross a defined spike threshold. The current research
          uses a Random Forest classifier trained on BTCUSDT data.
        </p>
      </section>

      <section className="method-grid">
        <article>
          <span>01</span>
          <h3>Historical data</h3>
          <p>Organised BTCUSDT funding-rate and market-price observations.</p>
        </article>
        <article>
          <span>02</span>
          <h3>Feature engineering</h3>
          <p>Funding-rate changes and market returns extracted as model inputs.</p>
        </article>
        <article>
          <span>03</span>
          <h3>Spike classification</h3>
          <p>A Random Forest model estimates the likelihood of a spike event.</p>
        </article>
      </section>

      {error && <p className="error-message">{error}</p>}

      <footer>
        <a className="brand" href="#">KRYPT<span>.</span></a>
        <p>Independent quantitative research · Educational simulation only</p>
      </footer>
    </main>
  );
}

export default App;
