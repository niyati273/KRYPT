
import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

const money = (value) =>
  value == null ? "—" : Number(value).toLocaleString("en-US", {
    maximumFractionDigits: 4,
  });

const rate = (value) =>
  value == null ? "—" : `${(Number(value) * 100).toFixed(4)}%`;

const date = (value) =>
  value ? new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }) : "—";

function FundingChart({ history, field = "funding_rate", percent = false }) {
  const values = (history || [])
    .map((item) => item[field])
    .filter((value) => value != null && Number.isFinite(Number(value)))
    .map(Number);

  if (values.length < 2) {
    return <div className="chart-empty">Not enough historical data to draw this chart.</div>;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((value, index) => {
    const x = (index / (values.length - 1)) * 900;
    const y = 185 - ((value - min) / range) * 155;
    return `${x},${y}`;
  }).join(" ");

  const last = values[values.length - 1];

  return (
    <div className="chart-wrap">
      <div className="chart-value-row">
        <span>MIN {percent ? rate(min) : money(min)}</span>
        <span>MAX {percent ? rate(max) : money(max)}</span>
      </div>
      <svg viewBox="0 0 900 210" preserveAspectRatio="none" role="img" aria-label="Historical data line chart">
        {[30, 80, 130, 185].map((y) => (
          <line key={y} x1="0" y1={y} x2="900" y2={y} className="grid-line" />
        ))}
        <polyline points={points} className="chart-area" />
        <polyline points={points} className="chart-line" />
        <circle cx="900" cy={185 - ((last - min) / range) * 155} r="5" className="chart-point" />
      </svg>
      <div className="chart-labels">
        <span>Oldest observation</span>
        <span>Latest observation</span>
      </div>
    </div>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <strong>{value}</strong>
      <span className="stat-note">{note}</span>
    </div>
  );
}

function App() {
  const [assets, setAssets] = useState([]);
  const [selectedId, setSelectedId] = useState("BTC");
  const [detail, setDetail] = useState(null);
  const [model, setModel] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loadingAssets, setLoadingAssets] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [predictionLoading, setPredictionLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [assetResponse, modelResponse] = await Promise.all([
          fetch(`${API}/api/assets`),
          fetch(`${API}/api/model`),
        ]);

        if (!assetResponse.ok || !modelResponse.ok) {
          throw new Error("The backend returned an error.");
        }

        const assetData = await assetResponse.json();
        const modelData = await modelResponse.json();

        setAssets(assetData.assets || []);
        setModel(modelData);
      } catch (err) {
        setError(`Could not connect to the backend: ${err.message}`);
      } finally {
        setLoadingAssets(false);
      }
    }

    loadInitialData();
  }, []);

  useEffect(() => {
    async function loadSelectedAsset() {
      setLoadingDetail(true);
      setDetail(null);
      setPrediction(null);
      setError("");

      try {
        const response = await fetch(`${API}/api/assets/${selectedId}`);
        if (!response.ok) {
          throw new Error("Could not load this asset's dataset.");
        }
        setDetail(await response.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoadingDetail(false);
      }
    }

    loadSelectedAsset();
  }, [selectedId]);

  const sortedAssets = useMemo(() => {
    return [...assets].sort((a, b) => {
      if (a.id === "BTC") return -1;
      if (b.id === "BTC") return 1;
      return (b.observations || 0) - (a.observations || 0);
    });
  }, [assets]);

  const totalRecords = assets.reduce(
    (sum, asset) => sum + (asset.observations || 0), 0
  );

  const runPrediction = async () => {
    if (selectedId !== "BTC" || !detail?.latest_features) return;

    setPredictionLoading(true);
    setError("");
    setPrediction(null);

    try {
      const response = await fetch(`${API}/api/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(detail.latest_features),
      });

      if (!response.ok) throw new Error("Prediction request failed.");

      setPrediction(await response.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setPredictionLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <nav className="navbar">
        <a className="brand" href="#">KRYPT<span>.</span></a>
        <div className="nav-links">
          <a href="#markets">Markets</a>
          <a href="#explorer">Explorer</a>
          <a href="#intelligence">Intelligence</a>
        </div>
        <div className="nav-status">
          <span className="status-dot" />
          HISTORICAL RESEARCH
        </div>
      </nav>

      <section className="hero">
        <div className="eyebrow"><span /> QUANTITATIVE CRYPTO RESEARCH</div>
        <h1>Understand the market.<br /><span>Read the funding signals.</span></h1>
        <p className="hero-description">
          A multi-asset research dashboard exploring cryptocurrency
          perpetual-futures funding rates, market data and machine-learning
          classification.
        </p>
        <div className="hero-meta">
          <span>10 ASSETS</span><i />
          <span>HISTORICAL DATASETS</span><i />
          <span>ML RESEARCH</span>
        </div>
      </section>

      <section className="overview-grid" id="markets">
        <Stat label="ASSETS TRACKED" value={assets.length || "—"} note="Configured datasets" />
        <Stat label="TOTAL RECORDS" value={totalRecords.toLocaleString("en-IN")} note="Across available datasets" />
        <Stat label="SELECTED ASSET" value={detail?.symbol || "—"} note="Historical explorer" />
        <Stat label="MODEL" value="Random Forest" note="BTCUSDT classification" />
      </section>

      <section className="section" id="explorer">
        <div className="section-heading">
          <div>
            <span className="section-kicker">01 / MULTI-ASSET COVERAGE</span>
            <h2>Market universe</h2>
            <p className="section-subtitle">Choose an asset to explore its historical funding data.</p>
          </div>
          <span className="section-tag">{assets.length} DATASETS</span>
        </div>

        {loadingAssets ? (
          <div className="loading-panel">Loading asset datasets...</div>
        ) : (
          <div className="asset-grid">
            {sortedAssets.map((asset) => (
              <button
                className={`asset-card ${selectedId === asset.id ? "selected" : ""}`}
                key={asset.id}
                onClick={() => setSelectedId(asset.id)}
              >
                <div className="asset-card-top">
                  <span className="asset-symbol">{asset.id.slice(0, 1)}</span>
                  <span className="asset-pair">{asset.symbol}</span>
                </div>
                <strong className="asset-name">{asset.name}</strong>
                <span className="asset-rate">{rate(asset.latest_funding_rate)}</span>
                <span className="asset-card-footer">
                  {Number(asset.observations || 0).toLocaleString("en-IN")} observations
                  <span>{selectedId === asset.id ? "SELECTED" : "EXPLORE →"}</span>
                </span>
                {asset.error && <span className="asset-error">Dataset unavailable</span>}
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="section">
        <div className="section-heading">
          <div>
            <span className="section-kicker">02 / HISTORICAL ANALYTICS</span>
            <h2>{detail?.name || "Asset"} explorer</h2>
            <p className="section-subtitle">
              {detail?.symbol || "Select an asset"} · Historical dataset, not a live market feed
            </p>
          </div>
          <span className="section-tag">{detail?.symbol || "LOADING"}</span>
        </div>

        {loadingDetail ? (
          <div className="loading-panel">Loading historical observations...</div>
        ) : detail ? (
          <>
            <div className="detail-stats">
              <Stat label="LATEST FUNDING RATE" value={rate(detail.latest_funding_rate)} note="Most recent available record" />
              <Stat label="LATEST MARK PRICE" value={money(detail.latest_mark_price)} note="Dataset mark price" />
              <Stat label="OBSERVATIONS" value={Number(detail.observations).toLocaleString("en-IN")} note="Available records" />
              <Stat label="DATA COVERAGE" value={`${date(detail.start_date)} – ${date(detail.end_date)}`} note="Recorded date range" />
            </div>

            <div className="chart-card">
              <div className="chart-heading">
                <div>
                  <span className="small-label">FUNDING RATE</span>
                  <h3>Historical funding activity</h3>
                </div>
                <span className="chart-caption">Latest {detail.history?.length || 0} observations</span>
              </div>
              <FundingChart history={detail.history} field="funding_rate" percent />
            </div>

            <div className="chart-card">
              <div className="chart-heading">
                <div>
                  <span className="small-label">MARK PRICE</span>
                  <h3>Historical mark-price movement</h3>
                </div>
                <span className="chart-caption">Dataset observations</span>
              </div>
              <FundingChart history={detail.history} field="mark_price" />
            </div>

            <div className="data-note">
              <strong>Dataset coverage</strong>
              <span>From {date(detail.start_date)} to {date(detail.end_date)}. Different assets have different historical date ranges.</span>
            </div>
          </>
        ) : (
          <div className="loading-panel">No asset selected.</div>
        )}
      </section>

      <section className="section">
        <div className="section-heading">
          <div>
            <span className="section-kicker">03 / CROSS-ASSET RESEARCH</span>
            <h2>Funding-rate comparison</h2>
            <p className="section-subtitle">Compare each dataset's latest available funding-rate observation.</p>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ASSET</th>
                <th>FUNDING RATE</th>
                <th>MARK PRICE</th>
                <th>RECORDS</th>
                <th>DATA END</th>
              </tr>
            </thead>
            <tbody>
              {[...assets]
                .filter((asset) => !asset.error)
                .sort((a, b) => (b.latest_funding_rate ?? -Infinity) - (a.latest_funding_rate ?? -Infinity))
                .map((asset) => (
                  <tr key={asset.id} onClick={() => setSelectedId(asset.id)}>
                    <td><strong>{asset.id}</strong><span className="table-muted"> {asset.name}</span></td>
                    <td className="green-text">{rate(asset.latest_funding_rate)}</td>
                    <td>{money(asset.latest_mark_price)}</td>
                    <td>{Number(asset.observations).toLocaleString("en-IN")}</td>
                    <td>{date(asset.end_date)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p className="chart-caption table-caption">These are each dataset's latest available observations, not necessarily measurements from the same date.</p>
      </section>

      <section className="section" id="intelligence">
        <div className="section-heading">
          <div>
            <span className="section-kicker">04 / MACHINE LEARNING</span>
            <h2>Model intelligence</h2>
            <p className="section-subtitle">The current trained classifier is configured for BTCUSDT.</p>
          </div>
          <span className="section-tag">BTC ONLY</span>
        </div>

        <div className="model-panel">
          <div>
            <span className="small-label">ACTIVE CLASSIFIER</span>
            <h3>Random Forest</h3>
            <p>
              Uses four engineered historical features to classify whether
              the next funding-rate observation crosses the project's
              defined spike threshold.
            </p>
            <div className="feature-pills">
              {(model?.features || []).map((feature) => <span key={feature}>{feature}</span>)}
            </div>
          </div>
          <div className="model-metrics">
            <div><span>Accuracy*</span><strong>{model ? `${(model.accuracy * 100).toFixed(1)}%` : "—"}</strong></div>
            <div><span>Precision*</span><strong>{model ? `${(model.precision * 100).toFixed(1)}%` : "—"}</strong></div>
            <div><span>Recall*</span><strong>{model ? `${(model.recall * 100).toFixed(1)}%` : "—"}</strong></div>
            <div><span>F1 score*</span><strong>{model ? `${(model.f1_score * 100).toFixed(1)}%` : "—"}</strong></div>
          </div>
        </div>
        <p className="chart-caption">*Preliminary evaluation figures from the existing API. Verify the training and test procedure before presenting these as final validated results.</p>

        <div className="prediction-panel">
          <div className="chart-heading">
            <div>
              <span className="small-label">BTC MODEL INFERENCE</span>
              <h3>Funding-rate spike detection</h3>
            </div>
            <span className="section-tag">RANDOM FOREST</span>
          </div>

          {selectedId !== "BTC" ? (
            <p className="data-note">Select BTC in the market universe to use the current Random Forest prediction feature. Other assets are available for historical analysis only.</p>
          ) : (
            <>
              <p className="section-subtitle">
                Run the saved classifier on the latest available BTC historical features.
              </p>
              <button
                className="primary-button"
                onClick={runPrediction}
                disabled={!detail?.latest_features || predictionLoading}
              >
                {predictionLoading ? "ANALYSING..." : "RUN SPIKE DETECTION"}
              </button>
              {prediction && (
                <div className="prediction-result">
                  <span className="small-label">MODEL OUTPUT</span>
                  <h3>{prediction.signal}</h3>
                  <div className="probability-row">
                    <span>Estimated spike-class probability</span>
                    <strong>{(prediction.spike_probability * 100).toFixed(2)}%</strong>
                  </div>
                  <div className="probability-track">
                    <div style={{ width: `${prediction.spike_probability * 100}%` }} />
                  </div>
                  <p className="chart-caption">A classification estimate, not model accuracy or a probability of profit.</p>
                  {/* --- PERSON C QUANTITATIVE EXECUTION SIGNAL --- */}
          {quantData && (
            <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#111', borderRadius: '8px', border: '1px solid #333' }}>
              <p style={{ fontSize: '12px', color: '#888', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                Quant Risk Execution
              </p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ 
                  margin: 0, 
                  color: quantData.trade_signal === 'HOLD' ? '#00ff88' : '#ff4444',
                  fontSize: '24px' 
                }}>
                  {quantData.trade_signal}
                </h3>
                <span style={{ fontSize: '14px', color: '#bbb' }}>
                  Basis: {quantData.basis_bps} bps
                </span>
              </div>
              <p style={{ fontSize: '13px', color: '#999', marginTop: '10px', fontStyle: 'italic' }}>
                {quantData.action_reason}
              </p>
            </div>
          )}
          {/* ---------------------------------------------- */}
                </div>
              )}
            </>
          )}
        </div>
      </section>

      <section className="method-section">
        <span className="section-kicker">05 / RESEARCH METHODOLOGY</span>
        <h2>From raw observations<br />to useful signals.</h2>
        <div className="method-grid">
          <article><span>01</span><h3>Data collection</h3><p>Historical funding-rate and mark-price datasets across ten cryptocurrency assets.</p></article>
          <article><span>02</span><h3>Feature engineering</h3><p>Funding-rate changes and mark-price returns calculated from chronological observations.</p></article>
          <article><span>03</span><h3>Classification</h3><p>A Random Forest model currently performs BTCUSDT funding-spike classification.</p></article>
        </div>
      </section>

      {error && <div className="error-message">{error}</div>}

      <footer className="footer">
        <a className="brand" href="#">KRYPT<span>.</span></a>
        <p>Independent quantitative research · Historical data · Educational simulation only</p>
      </footer>
    </main>
  );
}

export default App;

