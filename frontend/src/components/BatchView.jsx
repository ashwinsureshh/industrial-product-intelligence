import { useRef, useState } from 'react'
import { Badge, Empty, scoreColor } from './shared.jsx'

const SAMPLE_CSV = `sku,mpn,brand,name,Bore,Outer Diameter,Width
BRG-6204,6204,NSK,Deep groove ball bearing,20 mm,47 mm,14 mm
BRG-6207,6207,FAG,Ball bearing,,,
VLV-050,BV-316-050,Swagelok,1/2 inch stainless ball valve,,,
`

export function BatchSummary({ summary }) {
  if (!summary) return null

  return (
    <div className="card">
      <div className="card-head">
        <h3>Run Summary</h3>
        <div className="spacer" />
        <span className="pill">{summary.elapsed_ms} ms</span>
        {summary.cached > 0 && <span className="pill">{summary.cached} from cache</span>}
      </div>
      <div className="card-body">
        <div className="summary-grid">
          <div className="stat">
            <div className="stat-value">{summary.count}</div>
            <div className="stat-label">Products</div>
          </div>
          <div className="stat">
            <div className="stat-value" style={{ color: 'var(--ok)' }}>
              {summary.verdicts.publish}
            </div>
            <div className="stat-label">Publishable</div>
          </div>
          <div className="stat">
            <div className="stat-value" style={{ color: 'var(--warning)' }}>
              {summary.verdicts.review}
            </div>
            <div className="stat-label">Need review</div>
          </div>
          <div className="stat">
            <div className="stat-value" style={{ color: 'var(--error)' }}>
              {summary.verdicts.blocked}
            </div>
            <div className="stat-label">Blocked</div>
          </div>
          <div className="stat">
            <div className="stat-value" style={{ color: scoreColor(summary.avg_readiness) }}>
              {summary.avg_readiness}
            </div>
            <div className="stat-label">Avg readiness</div>
          </div>
          <div className="stat">
            <div className="stat-value">+{summary.attributes_added}</div>
            <div className="stat-label">Attributes added</div>
          </div>
          <div className="stat">
            <div className="stat-value">{summary.issues}</div>
            <div className="stat-label">Issues found</div>
          </div>
          <div className="stat">
            <div className="stat-value">
              {Math.round(summary.elapsed_ms / Math.max(summary.count, 1))}
            </div>
            <div className="stat-label">ms / product</div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function BatchTable({ results, selected, onSelect }) {
  if (!results?.length) return null

  return (
    <div className="card">
      <div className="card-head">
        <h3>Catalog Results</h3>
        <div className="spacer" />
        <span className="pill">select a row to inspect it</span>
      </div>
      <div className="card-body tight">
        <div className="table-scroll">
          <table className="grid">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Part Number</th>
                <th>Category</th>
                <th>Attrs</th>
                <th>Issues</th>
                <th>Score</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result, index) => {
                const errors = result.issues.filter((i) => i.severity === 'error').length
                const warnings = result.issues.filter((i) => i.severity === 'warning').length
                return (
                  <tr
                    key={index}
                    className={selected === index ? 'selected' : ''}
                    onClick={() => onSelect(index)}
                  >
                    <td className="mono">{result.input.sku || '—'}</td>
                    <td className="mono">{result.identity.mpn || result.input.mpn || '—'}</td>
                    <td>{result.category ? result.category.path[result.category.path.length - 1] : '—'}</td>
                    <td>{result.attributes.length}</td>
                    <td>
                      {errors > 0 && <span style={{ color: 'var(--error)' }}>{errors}E </span>}
                      {warnings > 0 && <span style={{ color: 'var(--warning)' }}>{warnings}W</span>}
                      {errors === 0 && warnings === 0 && <span style={{ color: 'var(--text-3)' }}>—</span>}
                    </td>
                    <td
                      style={{
                        fontWeight: 700,
                        color: scoreColor(result.readiness?.overall ?? 0),
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {Math.round(result.readiness?.overall ?? 0)}
                    </td>
                    <td>
                      <Badge kind={`verdict-${result.readiness?.verdict}`}>
                        {result.readiness?.verdict}
                      </Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function BatchInput({ onRunDemo, onUpload, loading, batchDemo }) {
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef(null)

  const handleFile = (file) => {
    if (file) onUpload(file)
  }

  const downloadTemplate = () => {
    const blob = new Blob([SAMPLE_CSV], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'catalog_template.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card">
      <div className="card-head">
        <h3>Catalog Ingest</h3>
      </div>
      <div className="card-body">
        <div
          className={`dropzone ${dragging ? 'over' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            handleFile(event.dataTransfer.files?.[0])
          }}
        >
          <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.55 }}>⇪</div>
          <p style={{ marginBottom: 10 }}>
            Drop a supplier CSV here, or pick a file. Unrecognised columns are kept as
            supplier spec fields rather than discarded.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.txt"
            style={{ display: 'none' }}
            onChange={(event) => handleFile(event.target.files?.[0])}
          />
          <button
            className="btn"
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
          >
            Choose CSV
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button
            className="btn btn-primary"
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={onRunDemo}
            disabled={loading}
            type="button"
          >
            {loading ? (
              <>
                <span className="spinner" /> Processing…
              </>
            ) : (
              `Run ${batchDemo?.length ?? 10}-product demo catalog`
            )}
          </button>
          <button className="btn" onClick={downloadTemplate} type="button">
            Template
          </button>
        </div>
      </div>
    </div>
  )
}

export function BatchEmpty() {
  return (
    <div className="card">
      <Empty icon="▤" title="No catalog processed yet">
        Run the demo catalog or upload a CSV to see the engine work at scale — every row
        classified, enriched, validated and scored independently.
      </Empty>
    </div>
  )
}
