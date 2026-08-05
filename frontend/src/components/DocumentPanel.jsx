import { useRef, useState } from 'react'

/** What the parser found, shown so the extraction isn't a black box either. */
export function IngestReport({ report, extracted }) {
  const [showRaw, setShowRaw] = useState(false)
  if (!report) return null

  const specs = Object.entries(extracted?.raw_specs ?? {})

  return (
    <div className="card">
      <div className="card-head">
        <h3>Document Parsed</h3>
        <div className="spacer" />
        {report.pages > 0 && <span className="pill">{report.pages} page{report.pages === 1 ? '' : 's'}</span>}
        <span className="pill">{report.spec_pairs} spec pairs</span>
      </div>

      <div className="card-body">
        <div className="summary-grid" style={{ marginBottom: 14 }}>
          <div className="stat">
            <div className="stat-value">{report.spec_pairs}</div>
            <div className="stat-label">Specs read</div>
          </div>
          <div className="stat">
            <div className="stat-value">{report.tables_found}</div>
            <div className="stat-label">Tables found</div>
          </div>
          <div className="stat">
            <div className="stat-value">{(report.text_chars / 1000).toFixed(1)}k</div>
            <div className="stat-label">Chars of text</div>
          </div>
        </div>

        <div className="content-block">
          <div className="content-label">Extraction strategy</div>
          <div className="tag-row">
            {report.strategies_used?.length ? (
              report.strategies_used.map((s) => (
                <span className="pill" key={s} title="How this content was recovered">
                  {s}
                </span>
              ))
            ) : (
              <span className="pill">none matched</span>
            )}
          </div>
        </div>

        {report.notes?.length > 0 && (
          <div className="banner banner-warn" style={{ marginTop: 10 }}>
            {report.notes.join(' ')}
          </div>
        )}

        {specs.length > 0 && (
          <div className="content-block" style={{ marginTop: 14 }}>
            <div className="content-label">
              Raw fields read from the document
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => setShowRaw((v) => !v)}
                style={{ padding: '1px 8px' }}
              >
                {showRaw ? 'hide' : `show ${specs.length}`}
              </button>
            </div>
            {showRaw && (
              <div className="table-scroll" style={{ maxHeight: 260 }}>
                <table className="grid">
                  <thead>
                    <tr>
                      <th>Field in document</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {specs.map(([key, value]) => (
                      <tr key={key} style={{ cursor: 'default' }}>
                        <td className="mono">{key}</td>
                        <td>{String(value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function DocumentInput({ onPdf, onUrl, loading }) {
  const [dragging, setDragging] = useState(false)
  const [url, setUrl] = useState('')
  const fileRef = useRef(null)

  return (
    <div className="card">
      <div className="card-head">
        <h3>Technical Document</h3>
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
            const file = event.dataTransfer.files?.[0]
            if (file) onPdf(file)
          }}
        >
          <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.55 }}>◫</div>
          <p style={{ marginBottom: 10 }}>
            Drop a supplier datasheet PDF. Ruled tables, whitespace columns and
            dot-leader lists are all read; every value keeps a link back to the
            document it came from.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) onPdf(file)
            }}
          />
          <button
            className="btn"
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
          >
            Choose PDF
          </button>
        </div>

        <div className="field" style={{ marginTop: 16 }}>
          <label htmlFor="producturl">Or a product page URL</label>
          <div className="key-input">
            <input
              id="producturl"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://supplier.example.com/product/6205-2RS"
              onKeyDown={(event) => {
                if (event.key === 'Enter' && url.trim()) onUrl(url.trim())
              }}
            />
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => onUrl(url.trim())}
              disabled={loading || !url.trim()}
            >
              {loading ? <span className="spinner" /> : 'Fetch'}
            </button>
          </div>
        </div>

        <p style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 4 }}>
          Reads schema.org product markup when a page publishes it, then spec
          tables and definition lists. Private and loopback addresses are refused.
        </p>
      </div>
    </div>
  )
}
