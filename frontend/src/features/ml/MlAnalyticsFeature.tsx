import { useState } from "react";
import { runMLAnalyticsDemo, type MLAnalyticsDemo } from "../../api";
import { MetricCard } from "../../components/MetricCard";
import { errorMessage } from "../../lib/format";

function percentage(value: number | null): string {
  return value === null ? "Unavailable" : `${(value * 100).toFixed(2)}%`;
}

function score(value: number): string {
  return value.toFixed(6);
}

export function MlAnalyticsFeature() {
  const [data, setData] = useState<MLAnalyticsDemo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runDemo() {
    setLoading(true);
    setError("");
    try {
      setData(await runMLAnalyticsDemo());
    } catch (cause) {
      setError(errorMessage(cause, "Unable to run the synthetic ML demonstration."));
    } finally {
      setLoading(false);
    }
  }

  const benchmark = data?.benchmark_evaluation;
  const metrics = benchmark?.metrics;

  return (
    <div className="page-stack ml-analytics-page">
      <section className="inline-message inline-message--info ml-synthetic-banner" role="note">
        <div><strong>Offline synthetic experiment</strong><span> This page uses the bundled generated fixture only. It does not read live events or create operational alerts.</span></div>
      </section>

      <section className="surface-card ml-launch-card">
        <header className="surface-card__header">
          <div>
            <div className="eyebrow">EXPERIMENTAL MODEL WORKSPACE</div>
            <h2>UEBA Isolation Forest demonstration</h2>
            <p>Run the existing deterministic demonstration and the held-out evaluation against the checked-in synthetic benchmark.</p>
          </div>
          <button type="button" className="button button--primary" onClick={() => void runDemo()} disabled={loading}>
            {loading ? "Running offline demo…" : data ? "Run demonstration again" : "Run offline demonstration"}
          </button>
        </header>
        {loading && <p className="ml-state-note" role="status">Fitting on the synthetic chronological training split and scoring the demo cases…</p>}
        {error && <div className="inline-message inline-message--error ml-state-message" role="alert"><span>{error}</span><button className="text-button" type="button" onClick={() => void runDemo()} disabled={loading}>Retry</button></div>}
        {!data && !loading && !error && <p className="ml-empty-state">No demonstration has been run in this session. Select “Run offline demonstration” to calculate the model scores and synthetic benchmark metrics.</p>}
      </section>

      {data && <>
        <section className="surface-card ml-model-card">
          <header className="surface-card__header surface-card__header--compact">
            <div><div className="eyebrow">MODEL AND FEATURE CONTRACT</div><h2>{data.model.name}</h2><p>{data.model.implementation} · feature specification <code>{data.model.feature_specification_version}</code></p></div>
          </header>
          <div className="ml-model-facts">
            <div><span>Contamination</span><strong>{data.model.configuration.contamination}</strong></div>
            <div><span>Random state</span><strong>{data.model.configuration.random_state}</strong></div>
            <div><span>Estimators</span><strong>{data.model.configuration.n_estimators}</strong></div>
            <div><span>Training rows</span><strong>{data.model.training.records.toLocaleString()}</strong></div>
            <div><span>Fit partition</span><strong>{data.model.training.partition}</strong></div>
            <div><span>Scenario labels in fit</span><strong>{data.model.training.scenario_labels_used_for_fit ? "Yes" : "No"}</strong></div>
            <div><span>Decision rule</span><strong className="mono">{data.threshold}</strong></div>
            <div><span>Fixture SHA-256</span><strong className="mono ml-hash">{data.fixture_sha256}</strong></div>
          </div>
          <div className="ml-feature-contract"><strong>Seven features</strong><span>{data.features.join(" · ")}</span></div>
        </section>

        {benchmark && metrics && <section className="page-stack ml-benchmark-section">
          <header className="ml-section-heading">
            <div><div className="eyebrow">SYNTHETIC BENCHMARK · HELD-OUT TEST SPLIT</div><h2>Evaluation results</h2><p>{benchmark.test_records.toLocaleString()} test records · {benchmark.evaluation_split} · {benchmark.label_source}</p></div>
          </header>
          <div className="metric-grid ml-metric-grid" aria-label="Synthetic benchmark metrics">
            <MetricCard label="Precision" value={percentage(metrics.precision)} helper="Synthetic test labels only" tone="accent" symbol="P" />
            <MetricCard label="Recall" value={percentage(metrics.recall)} helper="Synthetic test labels only" tone="warning" symbol="R" />
            <MetricCard label="F1 score" value={percentage(metrics.f1)} helper="Synthetic test labels only" tone="neutral" symbol="F1" />
            <MetricCard label="False-positive rate" value={percentage(metrics.false_positive_rate)} helper="Normal test scenarios flagged" tone="danger" symbol="FP" />
          </div>

          <div className="ml-evaluation-grid">
            <section className="surface-card">
              <header className="surface-card__header surface-card__header--compact"><div><div className="eyebrow">CONFUSION MATRIX</div><h2>Actual vs predicted</h2><p>Rows are actual labels; columns are model predictions.</p></div></header>
              <div className="table-scroll-region">
                <table className="data-table ml-confusion-table">
                  <thead><tr><th scope="col">Actual \ Predicted</th><th scope="col">{metrics.confusion_matrix.labels[0]}</th><th scope="col">{metrics.confusion_matrix.labels[1]}</th></tr></thead>
                  <tbody>{metrics.confusion_matrix.values.map((row, index) => <tr key={metrics.confusion_matrix.labels[index]}><th scope="row">{metrics.confusion_matrix.labels[index]}</th>{row.map((value, column) => <td className="mono" key={`${index}-${column}`}>{value}</td>)}</tr>)}</tbody>
                </table>
              </div>
              <p className="ml-panel-note">Threshold: <code>{benchmark.threshold}</code>. Confusion counts are from this synthetic fixture only.</p>
            </section>

            <section className="surface-card">
              <header className="surface-card__header surface-card__header--compact"><div><div className="eyebrow">SCENARIO BREAKDOWN</div><h2>Held-out synthetic scenarios</h2><p>Generated scenario labels are used for evaluation only.</p></div></header>
              <div className="table-scroll-region">
                <table className="data-table">
                  <thead><tr><th scope="col">Scenario</th><th scope="col">Test records</th><th scope="col">Flagged</th><th scope="col">Flagged rate</th></tr></thead>
                  <tbody>{Object.entries(benchmark.scenario_results).map(([name, value]) => <tr key={name}><td>{name.replaceAll("_", " ")}</td><td className="mono">{value.support}</td><td className="mono">{value.predicted_anomalies}</td><td className="mono">{percentage(value.predicted_anomaly_rate)}</td></tr>)}</tbody>
                </table>
              </div>
            </section>
          </div>
          <p className="ml-disclaimer">{benchmark.warning}</p>
        </section>}

        <section className="page-stack ml-scenarios-section">
          <header className="ml-section-heading"><div><div className="eyebrow">IN-MEMORY DEMONSTRATION EVENTS</div><h2>Normal versus anomalous examples</h2><p>Each case is scored by the same fitted model using the shared <code>ueba-seven-v2</code> feature engine. These examples are separate from the benchmark's test-set metric counts.</p></div></header>
          <div className="ml-scenario-grid">
            {data.results.map((item) => <article className="surface-card ml-scenario-card" key={item.scenario}>
              <header className="ml-scenario-card__header"><div><div className="eyebrow">CONTROLLED SCENARIO</div><h3>{item.scenario.replaceAll("_", " ")}</h3></div><span className={`ml-prediction ${item.prediction === "ANOMALY" ? "ml-prediction--anomaly" : "ml-prediction--normal"}`}>{item.prediction}</span></header>
              <div className="ml-event-facts">
                <div><span>User</span><strong className="mono">{item.input_event.user_id}</strong></div>
                <div><span>Event type</span><strong>{item.input_event.event_type}</strong></div>
                <div><span>Event time (UTC)</span><strong className="mono">{item.input_event.event_time_utc}</strong></div>
                <div><span>Source IP</span><strong className="mono">{item.input_event.source_ip}</strong></div>
              </div>
              <div className="ml-score-line"><span>Decision score <small>(not a probability)</small></span><strong className="mono">{score(item.decision_score)}</strong></div>
              <p className="ml-scenario-context">{item.context}</p>
              <details className="ml-feature-details"><summary>Inspect seven extracted features</summary>
                <dl>{data.features.map((feature) => <div key={feature}><dt className="mono">{feature}</dt><dd className="mono">{item.features[feature]?.toFixed(6) ?? "Unavailable"}</dd></div>)}</dl>
              </details>
              <p className="ml-interpretation">{item.interpretation}</p>
            </article>)}
          </div>
          <p className="ml-disclaimer">{data.warning}</p>
        </section>
      </>}
    </div>
  );
}
