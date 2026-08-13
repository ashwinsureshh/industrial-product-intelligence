import { Badge, scoreColor } from './shared.jsx'

const VERDICT_TEXT = {
  publish: 'Ready to publish',
  review: 'Needs review',
  blocked: 'Blocked',
}

function Gauge({ value }) {
  const radius = 40
  const circumference = 2 * Math.PI * radius
  const filled = (Math.max(0, Math.min(value, 100)) / 100) * circumference

  return (
    <div className="gauge">
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={radius} fill="none" stroke="var(--bg)" strokeWidth="8" />
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke={scoreColor(value)}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          style={{ transition: 'stroke-dasharray 0.5s ease' }}
        />
      </svg>
      <div className="gauge-center">
        <div className="gauge-value" style={{ color: scoreColor(value) }}>
          {Math.round(value)}
        </div>
        <div className="gauge-label">Readiness</div>
      </div>
    </div>
  )
}

function Metric({ label, value, hint }) {
  return (
    <div className="metric" title={hint}>
      <div className="metric-head">
        <span>{label}</span>
        <span>{value.toFixed(0)}%</span>
      </div>
      <div className="bar">
        <div
          className="bar-fill"
          style={{ width: `${Math.min(value, 100)}%`, background: scoreColor(value) }}
        />
      </div>
    </div>
  )
}

// Written when there were two engines, and hybrid fell into the else — so the
// project's best-measured result was labelled "demo engine" directly above a
// gate ledger showing the model being refused twice. A reviewer switching to
// Hybrid had every reason to conclude the toggle did nothing.
const ENGINE_LABEL = {
  demo: { text: 'demo engine', hint: 'Deterministic engine only — no model call.' },
  hybrid: {
    text: 'hybrid engine',
    hint: 'Deterministic engine plus a bounded AI contribution: it may fill a blank '
        + 'or replace an unbacked default, never overwrite evidence. See the gate '
        + 'ledger below for what was accepted and what was refused.',
  },
  live: { text: 'live model', hint: 'Every value proposed by the model.' },
}

export default function ScoreCard({ readiness, category, cached, mode }) {
  if (!readiness) return null

  return (
    <div className="card">
      <div className="card-head">
        <h3>Commerce Readiness</h3>
        <div className="spacer" />
        {cached && <span className="pill" title="Served from cache — no API call was made">cached</span>}
        <span className="pill" title={ENGINE_LABEL[mode]?.hint}>
          {ENGINE_LABEL[mode]?.text ?? 'demo engine'}
        </span>
        <Badge kind={`verdict-${readiness.verdict}`}>{VERDICT_TEXT[readiness.verdict]}</Badge>
      </div>

      <div className="card-body">
        <div className="score-grid">
          <Gauge value={readiness.overall} />
          <div>
            <Metric
              label="Completeness"
              value={readiness.completeness}
              hint="How much of the category schema is filled, weighted toward required fields."
            />
            <Metric
              label="Confidence"
              value={readiness.confidence}
              hint="Average attribute confidence, weighted by how strong each provenance class is."
            />
            <Metric
              label="Validity"
              value={readiness.validity}
              hint="Penalised for every validation error and warning found."
            />
          </div>
        </div>

        {category && (
          <div className="score-notes">
            <div className="content-label" style={{ marginBottom: 6 }}>
              Category — {Math.round(category.confidence * 100)}% confidence
            </div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{category.path.join(' › ')}</div>
            <div className="mono" style={{ color: 'var(--text-3)', marginTop: 2 }}>
              UNSPSC {category.code}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 6 }}>
              {category.rationale}
            </div>
            {category.alternatives?.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div className="content-label" style={{ marginBottom: 4 }}>
                  Alternatives considered
                </div>
                <div className="tag-row">
                  {category.alternatives.map((alt) => (
                    <span className="pill" key={alt.code}>
                      {alt.path[alt.path.length - 1]} · {Math.round(alt.confidence * 100)}%
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {readiness.notes?.length > 0 && (
          <div className="score-notes">
            {readiness.notes.map((note, index) => (
              <div className="score-note" key={index}>
                {note}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
