
import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

const money = (value) =>
  value == null
    ? "—"
    : Number(value).toLocaleString("en-US", {
        maximumFractionDigits: 4,
      });

const rate = (value) =>
  value == null ? "—" : `${(Number(value) * 100).toFixed(4)}%`;

const date = (value) =>
  value
    ? new Date(value).toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "—";

function FundingChart({ history, field = "funding_rate", percent = false }) {
  const values = (history || [])
    .map((item) => item[field])
    .filter((value) => value != null && Number.isFinite(Number(value)))
    .map(Number);

  if (values.length < 2) {
    return (
      <div className="chart-empty">
        Not enough historical data to draw this chart.
      </div>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 900;
      const y = 185 - ((value - min) / range) * 155;
      return `${x},${y}`;
    })
    .join(" ");

  const last = values[values.length - 1];

  return (
    <div className="chart-wrap">
      <div className="chart-value-row">
        <span>MIN {percent ? rate(min) : money(min)}</span>
        <span>MAX {percent ? rate(max) : money(max)}</span>
      </div>

      <svg
        viewBox="0 0 900 210"
        preserveAspectRatio="none"
        role="img"
        aria-label="Historical data line chart"
      >
        {[30, 80, 130, 185].map((y) => (
          <line
            key={y}
            x1="0"
            y1={y}
            x2="900"
            y2={y}
            className="grid-line"
          />
        ))}
        <polyline points={points} className="chart-area" />
        <polyline points={points} className="chart-line" />
        <circle
          cx="900"
          cy={185 - ((last - min) / range) * 155}
          r="5"
          className="chart-point"
        />
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

  // Backtesting state
  const [backtest, setBacktest] = useState(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestError, setBacktestError] = useState("");

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
    (sum, asset) => sum + (asset.observations || 0),
    0
  );

  // Run Random Forest inference
  const runPrediction = async () => {
    if (!detail?.latest_features) {
      setError("Features are not available for this asset.");
      return;
    }

    setPredictionLoading(true);
    setError("");
    setPrediction(null);

    try {
      const response = await fetch(`${API}/api/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(detail.latest_features),
      });

      if (!response.ok) {
        throw new Error(`Prediction failed for ${selectedId}.`);
      }

      setPrediction(await response.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setPredictionLoading(false);
    }
  };

  // Run historical HOLD / SELL backtest
  const runBacktest = async () => {
    setBacktestLoading(true);
    setBacktestError("");
    setBacktest(null);

    try {
      const response = await fetch(`${API}/api/backtest`);

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not run historical backtest.");
      }

      setBacktest(data);
    } catch (err) {
      setBacktestError(err.message);
    } finally {
      setBacktestLoading(false);
    }
  };

  // Filter backtest decisions for selected asset
  const selectedBacktestDecisions = useMemo(() => {
    if (!backtest?.decisions) return [];

    return backtest.decisions
      .filter((item) => item.coin === selectedId)
      .slice()
      .reverse();
  }, [backtest, selectedId]);

  const selectedBacktestSummary = useMemo(() => {
    if (!backtest?.summary) return null;

    return backtest.summary.find((item) => item.coin === selectedId);
  }, [backtest, selectedId]);

  const decisionCounts = useMemo(() => {
    const decisions = selectedBacktestDecisions;

    return {
      hold: decisions.filter((item) => item.action === "HOLD").length,
      sell: decisions.filter((item) => item.action === "SELL").length,
      wait: decisions.filter((item) => item.action === "WAIT").length,
    };
  }, [selectedBacktestDecisions]);

  return (
    <main className="app-shell">
      <nav className="navbar">
        <a className="brand" href="#">
          KRYPT<span>.</span>
        </a>

        <div className="nav-links">
          <a href="#markets">Markets</a>
          <a href="#explorer">Explorer</a>
          <a href="#intelligence">Intelligence</a>
          <a href="#backtesting">Backtesting</a>
        </div>

        <div className="nav-status">
          <span className="status-dot" />
          HISTORICAL RESEARCH
        </div>
      </nav>

      <section className="hero">
        <div className="eyebrow">
          <span /> QUANTITATIVE CRYPTO RESEARCH
        </div>

        <h1>
          Understand the market.
          <br />
          <span>Read the funding signals.</span>
        </h1>

        <p className="hero-description">
          A multi-asset research dashboard exploring cryptocurrency
          perpetual-futures funding rates, market data and machine-learning
          classification.
        </p>

        <div className="hero-meta">
          <span>10 ASSETS</span>
          <i />
          <span>HISTORICAL DATASETS</span>
          <i />
          <span>ML RESEARCH</span>
        </div>
      </section>

      <section className="overview-grid" id="markets">
        <Stat
          label="ASSETS TRACKED"
          value={assets.length || "—"}
          note="Configured datasets"
        />
        <Stat
          label="TOTAL RECORDS"
          value={totalRecords.toLocaleString("en-IN")}
          note="Across available datasets"
        />
        <Stat
          label="SELECTED ASSET"
          value={detail?.symbol || "—"}
          note="Historical explorer"
        />
        <Stat
          label="MODEL"
          value="Random Forest"
          note="Experimental classifier"
        />
      </section>

      {/* MULTI-ASSET COVERAGE */}
      <section className="section" id="explorer">
        <div className="section-heading">
          <div>
            <span className="section-kicker">01 / MULTI-ASSET COVERAGE</span>
            <h2>Market universe</h2>
            <p className="section-subtitle">
              Choose an asset to explore its historical funding data.
            </p>
          </div>
          <span className="section-tag">{assets.length} DATASETS</span>
        </div>

        {loadingAssets ? (
          <div className="loading-panel">Loading asset datasets...</div>
        ) : (
          <div className="asset-grid">
            {sortedAssets.map((asset) => (
              <button
                className={`asset-card ${
                  selectedId === asset.id ? "selected" : ""
                }`}
                key={asset.id}
                onClick={() => setSelectedId(asset.id)}
              >
                <div className="asset-card-top">
                  <span className="asset-symbol">{asset.id.slice(0, 1)}</span>
                  <span className="asset-pair">{asset.symbol}</span>
                </div>

                <strong className="asset-name">{asset.name}</strong>
                <span className="asset-rate">
                  {rate(asset.latest_funding_rate)}
                </span>

                <span className="asset-card-footer">
                  {Number(asset.observations || 0).toLocaleString("en-IN")}{" "}
                  observations
                  <span>
                    {selectedId === asset.id ? "SELECTED" : "EXPLORE →"}
                  </span>
                </span>

                {asset.error && (
                  <span className="asset-error">Dataset unavailable</span>
                )}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* HISTORICAL ANALYTICS */}
      <section className="section">
        <div className="section-heading">
          <div>
            <span className="section-kicker">02 / HISTORICAL ANALYTICS</span>
            <h2>{detail?.name || "Asset"} explorer</h2>
            <p className="section-subtitle">
              {detail?.symbol || "Select an asset"} · Historical dataset, not a
              live market feed
            </p>
          </div>

          <span className="section-tag">{detail?.symbol || "LOADING"}</span>
        </div>

        {loadingDetail ? (
          <div className="loading-panel">
            Loading historical observations...
          </div>
        ) : detail ? (
          <>
            <div className="detail-stats">
              <Stat
                label="LATEST FUNDING RATE"
                value={rate(detail.latest_funding_rate)}
                note="Most recent available record"
              />
              <Stat
                label="LATEST MARK PRICE"
                value={money(detail.latest_mark_price)}
                note="Dataset mark price"
              />
              <Stat
                label="OBSERVATIONS"
                value={Number(detail.observations).toLocaleString("en-IN")}
                note="Available records"
              />
              <Stat
                label="DATA COVERAGE"
                value={`${date(detail.start_date)} – ${date(detail.end_date)}`}
                note="Recorded date range"
              />
            </div>

            <div className="chart-card">
              <div className="chart-heading">
                <div>
                  <span className="small-label">FUNDING RATE</span>
                  <h3>Historical funding activity</h3>
                </div>
                <span className="chart-caption">
                  Latest {detail.history?.length || 0} observations
                </span>
              </div>

              <FundingChart
                history={detail.history}
                field="funding_rate"
                percent
              />
            </div>

            <div className="chart-card">
              <div className="chart-heading">
                <div>
                  <span className="small-label">MARK PRICE</span>
                  <h3>Historical mark-price movement</h3>
                </div>
                <span className="chart-caption">Dataset observations</span>
              </div>

              <FundingChart
                history={detail.history}
                field="mark_price"
              />
            </div>

            <div className="data-note">
              <strong>Dataset coverage</strong>
              <span>
                From {date(detail.start_date)} to {date(detail.end_date)}.
                Different assets have different historical date ranges.
              </span>
            </div>
          </>
        ) : (
          <div className="loading-panel">No asset selected.</div>
        )}
      </section>

      {/* CROSS-ASSET COMPARISON */}
      <section className="section">
        <div className="section-heading">
          <div>
            <span className="section-kicker">03 / CROSS-ASSET RESEARCH</span>
            <h2>Funding-rate comparison</h2>
            <p className="section-subtitle">
              Compare each dataset's latest available funding-rate observation.
            </p>
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
                .sort(
                  (a, b) =>
                    (b.latest_funding_rate ?? -Infinity) -
                    (a.latest_funding_rate ?? -Infinity)
                )
                .map((asset) => (
                  <tr
                    key={asset.id}
                    onClick={() => setSelectedId(asset.id)}
                  >
                    <td>
                      <strong>{asset.id}</strong>
                      <span className="table-muted"> {asset.name}</span>
                    </td>
                    <td className="green-text">
                      {rate(asset.latest_funding_rate)}
                    </td>
                    <td>{money(asset.latest_mark_price)}</td>
                    <td>
                      {Number(asset.observations).toLocaleString("en-IN")}
                    </td>
                    <td>{date(asset.end_date)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <p className="chart-caption table-caption">
          These are each dataset's latest available observations, not
          necessarily measurements from the same date.
        </p>
      </section>

      {/* MACHINE LEARNING */}
      <section className="section" id="intelligence">
        <div className="section-heading">
          <div>
            <span className="section-kicker">04 / MACHINE LEARNING</span>
            <h2>Model intelligence</h2>
            <p className="section-subtitle">
              Random Forest spike detection interface.
            </p>
          </div>

          <span className="section-tag">EXPERIMENTAL</span>
        </div>

        <div className="model-panel">
          <div>
            <span className="small-label">ACTIVE CLASSIFIER</span>
            <h3>Random Forest</h3>
            <p>
              Uses four engineered historical features to classify funding-rate
              spike patterns. The existing saved model was configured for
              BTCUSDT; other asset outputs are experimental.
            </p>

            <div className="feature-pills">
              {(model?.features || []).map((feature) => (
                <span key={feature}>{feature}</span>
              ))}
            </div>
          </div>

          <div className="model-metrics">
            <div>
              <span>Accuracy*</span>
              <strong>
                {model ? `${(model.accuracy * 100).toFixed(1)}%` : "—"}
              </strong>
            </div>
            <div>
              <span>Precision*</span>
              <strong>
                {model ? `${(model.precision * 100).toFixed(1)}%` : "—"}
              </strong>
            </div>
            <div>
              <span>Recall*</span>
              <strong>
                {model ? `${(model.recall * 100).toFixed(1)}%` : "—"}
              </strong>
            </div>
            <div>
              <span>F1 score*</span>
              <strong>
                {model ? `${(model.f1_score * 100).toFixed(1)}%` : "—"}
              </strong>
            </div>
          </div>
        </div>

        <p className="chart-caption">
          *Preliminary BTC model evaluation figures. They do not represent
          validated performance on every asset.
        </p>

        <div className="prediction-panel">
          <div className="chart-heading">
            <div>
              <span className="small-label">{selectedId} MODEL INFERENCE</span>
              <h3>Funding-rate spike detection</h3>
            </div>
            <span className="section-tag">RANDOM FOREST</span>
          </div>

          <p className="section-subtitle">
            Run the existing classifier using the selected asset's latest
            available features.
          </p>

          <button
            type="button"
            className="primary-button"
            onClick={runPrediction}
            disabled={
              !detail?.latest_features ||
              predictionLoading ||
              loadingDetail
            }
          >
            {predictionLoading
              ? "ANALYSING..."
              : `⚡ RUN ${selectedId} SPIKE DETECTION`}
          </button>

          {!detail?.latest_features && !loadingDetail && (
            <p className="chart-caption">
              Feature data is unavailable for this asset.
            </p>
          )}

          {prediction && (
            <div className="prediction-result">
              <span className="small-label">{selectedId} MODEL OUTPUT</span>
              <h3>{prediction.signal}</h3>

              <div className="probability-row">
                <span>Estimated spike-class probability</span>
                <strong>
                  {(Number(prediction.spike_probability) * 100).toFixed(2)}%
                </strong>
              </div>

              <div className="probability-track">
                <div
                  style={{
                    width: `${Math.max(
                      0,
                      Math.min(
                        100,
                        Number(prediction.spike_probability) * 100
                      )
                    )}%`,
                  }}
                />
              </div>

              <p className="chart-caption">
                Experimental output. The existing model was configured for
                BTCUSDT; results for other assets are not validated.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* HISTORICAL BACKTESTING */}
      <section className="section" id="backtesting">
        <div className="section-heading">
          <div>
            <span className="section-kicker">05 / STRATEGY EVALUATION</span>
            <h2>Historical backtesting</h2>
            <p className="section-subtitle">
              Simulate historical HOLD, SELL and WAIT decisions using the
              funding-threshold baseline strategy.
            </p>
          </div>

          <span className="section-tag">HISTORICAL SIMULATION</span>
        </div>

        <div className="prediction-panel">
          <div className="chart-heading">
            <div>
              <span className="small-label">BACKTEST CONFIGURATION</span>
              <h3>Funding threshold strategy</h3>
            </div>
            <span className="section-tag">6 HISTORICAL ASSETS</span>
          </div>

          <p className="section-subtitle">
            The backend evaluates historical observations and records
            simulated entry, holding and exit decisions. This is a
            rule-based baseline, not an ML model backtest.
          </p>

          <button
            type="button"
            className="primary-button"
            onClick={runBacktest}
            disabled={backtestLoading}
          >
            {backtestLoading
              ? "RUNNING HISTORICAL BACKTEST..."
              : "RUN HISTORICAL BACKTEST"}
          </button>

          {backtestError && (
            <div className="error-message">{backtestError}</div>
          )}

          {backtest && (
            <>
              <div className="data-note">
                <strong>Backtest completed</strong>
                <span>
                  {backtest.strategy} · {backtest.total_observations} historical
                  observations · {backtest.assets_tested} assets evaluated
                </span>
              </div>

              <div className="detail-stats">
                <Stat
                  label="SELECTED ASSET"
                  value={selectedId}
                  note="Current asset filter"
                />

                <Stat
                  label="FINAL EQUITY"
                  value={
                    selectedBacktestSummary
                      ? money(selectedBacktestSummary.final_equity)
                      : "—"
                  }
                  note="Simulated portfolio value"
                />

                <Stat
                  label="TOTAL RETURN"
                  value={
                    selectedBacktestSummary
                      ? `${selectedBacktestSummary.return_percent}%`
                      : "—"
                  }
                  note="Historical simulated return"
                />

                <Stat
                  label="TOTAL TRADES"
                  value={
                    selectedBacktestSummary
                      ? selectedBacktestSummary.total_trades
                      : "—"
                  }
                  note="Completed simulated positions"
                />
              </div>

              <div className="detail-stats">
                <Stat
                  label="HOLD OBSERVATIONS"
                  value={decisionCounts.hold}
                  note="Position remained open"
                />

                <Stat
                  label="SELL DECISIONS"
                  value={decisionCounts.sell}
                  note="Position closed"
                />

                <Stat
                  label="WAIT OBSERVATIONS"
                  value={decisionCounts.wait}
                  note="Entry condition not met"
                />

                <Stat
                  label="WIN RATE"
                  value={
                    selectedBacktestSummary
                      ? `${selectedBacktestSummary.win_rate_percent}%`
                      : "—"
                  }
                  note="Profitable completed trades"
                />
              </div>

              <div className="chart-card">
                <div className="chart-heading">
                  <div>
                    <span className="small-label">ASSET PERFORMANCE</span>
                    <h3>Backtest summary across assets</h3>
                  </div>
                </div>

                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>ASSET</th>
                        <th>INITIAL CAPITAL</th>
                        <th>FINAL EQUITY</th>
                        <th>RETURN</th>
                        <th>TRADES</th>
                        <th>WIN RATE</th>
                      </tr>
                    </thead>

                    <tbody>
                      {backtest.summary.map((item) => (
                        <tr
                          key={item.coin}
                          onClick={() => setSelectedId(item.coin)}
                        >
                          <td>
                            <strong>{item.coin}</strong>
                          </td>
                          <td>{money(item.initial_capital)}</td>
                          <td>{money(item.final_equity)}</td>
                          <td
                            className={
                              item.return_percent >= 0
                                ? "green-text"
                                : "negative-text"
                            }
                          >
                            {item.return_percent}%
                          </td>
                          <td>{item.total_trades}</td>
                          <td>{item.win_rate_percent}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <p className="chart-caption table-caption">
                  Select an asset row to view its individual historical
                  decisions.
                </p>
              </div>

              <div className="chart-card">
                <div className="chart-heading">
                  <div>
                    <span className="small-label">
                      {selectedId} / HISTORICAL DECISIONS
                    </span>
                    <h3>HOLD / SELL / WAIT decision history</h3>
                  </div>
                  <span className="section-tag">
                    {selectedBacktestDecisions.length} RECORDS
                  </span>
                </div>

                {selectedBacktestDecisions.length === 0 ? (
                  <div className="chart-empty">
                    No backtest decisions available for {selectedId}.
                  </div>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>TIMESTAMP</th>
                          <th>FUNDING RATE</th>
                          <th>MARK PRICE</th>
                          <th>DECISION</th>
                          <th>TRADE RETURN</th>
                          <th>PORTFOLIO VALUE</th>
                          <th>REASON</th>
                        </tr>
                      </thead>

                      <tbody>
                        {selectedBacktestDecisions
                          .slice(0, 50)
                          .map((item, index) => (
                            <tr
                              key={`${item.timestamp}-${index}`}
                            >
                              <td>
                                {new Date(item.timestamp).toLocaleString(
                                  "en-IN"
                                )}
                              </td>

                              <td>{rate(item.funding_rate)}</td>

                              <td>{money(item.mark_price)}</td>

                              <td>
                                <strong
                                  className={
                                    item.action === "HOLD"
                                      ? "green-text"
                                      : item.action === "SELL"
                                      ? "negative-text"
                                      : ""
                                  }
                                >
                                  {item.action}
                                </strong>
                              </td>

                              <td>
                                {item.realized_trade_return_percent == null
                                  ? "—"
                                  : `${item.realized_trade_return_percent}%`}
                              </td>

                              <td>{money(item.portfolio_value)}</td>

                              <td>{item.reason}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <p className="chart-caption table-caption">
                  Showing the latest 50 decisions for the selected asset.
                  The complete decision history is saved by the backend as a
                  CSV file.
                </p>
              </div>

              <div className="data-note">
                <strong>Backtesting methodology</strong>
                <span>
                  Entry threshold: {backtest.threshold} · Transaction cost per
                  side: {(backtest.transaction_cost_per_side * 100).toFixed(2)}
                  % · Initial simulated capital per asset:{" "}
                  {money(backtest.initial_capital_per_asset)}
                </span>
              </div>

              <div className="data-note">
                <strong>Research limitation</strong>
                <span>{backtest.disclaimer}</span>
              </div>
            </>
          )}
        </div>
      </section>

      {/* METHODOLOGY */}
      <section className="method-section">
        <span className="section-kicker">06 / RESEARCH METHODOLOGY</span>
        <h2>
          From raw observations
          <br />
          to useful signals.
        </h2>

        <div className="method-grid">
          <article>
            <span>01</span>
            <h3>Data collection</h3>
            <p>
              Historical funding-rate and mark-price datasets across
              cryptocurrency assets.
            </p>
          </article>

          <article>
            <span>02</span>
            <h3>Feature engineering</h3>
            <p>
              Funding-rate changes and mark-price returns calculated from
              chronological observations.
            </p>
          </article>

          <article>
            <span>03</span>
            <h3>Classification</h3>
            <p>
              A Random Forest model currently performs BTCUSDT funding-spike
              classification. Other asset outputs are experimental.
            </p>
          </article>

          <article>
            <span>04</span>
            <h3>Historical evaluation</h3>
            <p>
              A separate rule-based baseline simulates historical HOLD, SELL
              and WAIT decisions and calculates portfolio performance.
            </p>
          </article>
        </div>
      </section>

      {error && <div className="error-message">{error}</div>}

      <footer className="footer">
        <a className="brand" href="#">
          KRYPT<span>.</span>
        </a>
        <p>
          Independent quantitative research · Historical data · Educational
          simulation only
        </p>
      </footer>
    </main>
  );
}

export default App;
