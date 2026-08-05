import { useEffect, useMemo, useState } from 'react'
import * as api from './api.js'
import AttributeTable from './components/AttributeTable.jsx'
import BatchInput, { BatchEmpty, BatchSummary, BatchTable } from './components/BatchView.jsx'
import ContentPanel from './components/ContentPanel.jsx'
import DocumentInput, { IngestReport } from './components/DocumentPanel.jsx'
import InputPanel, { emptyProduct, fromProduct, toProduct } from './components/InputPanel.jsx'
import IssueList from './components/IssueList.jsx'
import ScoreCard from './components/ScoreCard.jsx'
import TraceTimeline from './components/TraceTimeline.jsx'
import { Empty } from './components/shared.jsx'

const BLANK_SPECS = [{ key: '', value: '' }]

export default function App() {
  const [health, setHealth] = useState(null)
  const [samples, setSamples] = useState(null)

  const [mode, setMode] = useState('demo')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  const [tab, setTab] = useState('single')
  const [form, setForm] = useState(emptyProduct())
  const [specs, setSpecs] = useState(BLANK_SPECS)
  const [activeSample, setActiveSample] = useState(null)

  const [result, setResult] = useState(null)
  const [batch, setBatch] = useState(null)
  const [selectedRow, setSelectedRow] = useState(0)
  const [ingest, setIngest] = useState(null)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
    api.getSamples().then(setSamples).catch(() => {})
  }, [])

  const loadSample = (sample) => {
    const { form: nextForm, specs: nextSpecs } = fromProduct(sample.product)
    setForm(nextForm)
    setSpecs(nextSpecs.length ? nextSpecs : BLANK_SPECS)
    setActiveSample(sample.id)
    setResult(null)
    setError(null)
  }

  const clearForm = () => {
    setForm(emptyProduct())
    setSpecs(BLANK_SPECS)
    setActiveSample(null)
    setResult(null)
    setError(null)
  }

  const runSingle = async () => {
    setLoading(true)
    setError(null)
    try {
      setResult(await api.enrich(toProduct(form, specs), mode, apiKey))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const runBatchDemo = async () => {
    if (!samples?.batch_demo) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.enrichBatch(samples.batch_demo, mode, apiKey)
      setBatch(response)
      setSelectedRow(0)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Document ingestion hands off to the same enrichment pipeline, so the
  // result renders through the identical detail panes as any other input.
  const runDocument = async (call) => {
    setLoading(true)
    setError(null)
    setIngest(null)
    try {
      const response = await call()
      setIngest({ report: response.ingest, extracted: response.extracted_input })
      setResult(response.result)
      if (!response.result) {
        setError('Nothing readable was found in that document.')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const runPdf = (file) => runDocument(() => api.ingestPdf(file, mode, apiKey))
  const runUrl = (url) => runDocument(() => api.ingestUrl(url, mode, apiKey))

  const runUpload = async (file) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.enrichCsv(file, mode, apiKey)
      setBatch(response)
      setSelectedRow(0)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // In batch mode the detail panes render whichever row is selected, so one set
  // of components serves both tabs.
  const detail = useMemo(() => {
    if (tab === 'batch') return batch?.results?.[selectedRow] ?? null
    return result
  }, [tab, result, batch, selectedRow])

  const liveWarning =
    mode === 'live' && !apiKey && !health?.server_key_fallback
      ? 'Live mode needs your own Anthropic API key. Without one the request runs on the demo engine.'
      : null

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">PI</div>
          <div className="brand-text">
            <h1>Product Intelligence</h1>
            <p>Sparse supplier data → validated, explainable catalog records</p>
          </div>
        </div>

        <div className="topbar-spacer" />

        <div className="tabs" style={{ width: 290 }}>
          <button
            className={`tab ${tab === 'single' ? 'active' : ''}`}
            onClick={() => setTab('single')}
          >
            Single Product
          </button>
          <button
            className={`tab ${tab === 'document' ? 'active' : ''}`}
            onClick={() => setTab('document')}
            title="Read a datasheet PDF or a supplier product page"
          >
            Document
          </button>
          <button
            className={`tab ${tab === 'batch' ? 'active' : ''}`}
            onClick={() => setTab('batch')}
          >
            Catalog
          </button>
        </div>

        <div className="tabs" style={{ width: 150 }}>
          <button
            className={`tab ${mode === 'demo' ? 'active' : ''}`}
            onClick={() => setMode('demo')}
            title="Deterministic engine — no API key, no cost, identical output every run."
          >
            Demo
          </button>
          <button
            className={`tab ${mode === 'live' ? 'active' : ''}`}
            onClick={() => setMode('live')}
            title="Calls the Claude API using a key you supply."
          >
            Live AI
          </button>
        </div>

        {mode === 'live' && (
          <div className="key-input" style={{ width: 250 }}>
            <input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="sk-ant-… (your key, never stored)"
              aria-label="Anthropic API key"
            />
            <button className="btn btn-sm" onClick={() => setShowKey((v) => !v)} type="button">
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
        )}

        {health && (
          <span
            className="pill"
            title={
              health.status === 'ok'
                ? `${health.categories} categories loaded · ${health.cache?.entries ?? 0} cached results`
                : 'The API is not reachable — start the backend on port 8000.'
            }
          >
            <span
              style={{
                display: 'inline-block',
                width: 6,
                height: 6,
                borderRadius: '50%',
                marginRight: 6,
                background: health.status === 'ok' ? 'var(--ok)' : 'var(--error)',
              }}
            />
            {health.status === 'ok' ? `${health.categories} categories` : 'API offline'}
          </span>
        )}
      </header>

      <div className="layout">
        <div className="col sticky-col">
          {liveWarning && <div className="banner banner-warn">{liveWarning}</div>}
          {error && <div className="banner banner-error">{error}</div>}

          {tab === 'single' ? (
            <>
              <InputPanel
                form={form}
                setForm={setForm}
                specs={specs}
                setSpecs={setSpecs}
                onRun={runSingle}
                onClear={clearForm}
                loading={loading}
              />

              {samples?.samples && (
                <div className="card">
                  <div className="card-head">
                    <h3>Demo Cases</h3>
                  </div>
                  <div className="card-body">
                    <div className="sample-list">
                      {samples.samples.map((sample) => (
                        <button
                          key={sample.id}
                          type="button"
                          className={`sample ${activeSample === sample.id ? 'active' : ''}`}
                          onClick={() => loadSample(sample)}
                        >
                          <div className="sample-label">{sample.label}</div>
                          <div className="sample-intent">{sample.intent}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : tab === 'document' ? (
            <>
              <DocumentInput onPdf={runPdf} onUrl={runUrl} loading={loading} />
              {ingest && (
                <IngestReport report={ingest.report} extracted={ingest.extracted} />
              )}
            </>
          ) : (
            <>
              <BatchInput
                onRunDemo={runBatchDemo}
                onUpload={runUpload}
                loading={loading}
                batchDemo={samples?.batch_demo}
              />
              {batch && (
                <div className="card">
                  <div className="card-head">
                    <h3>Export</h3>
                  </div>
                  <div className="card-body" style={{ display: 'flex', gap: 8 }}>
                    <button
                      className="btn"
                      style={{ flex: 1, justifyContent: 'center' }}
                      onClick={() => api.exportCsv(batch.results)}
                      type="button"
                    >
                      Download CSV
                    </button>
                    <button
                      className="btn"
                      style={{ flex: 1, justifyContent: 'center' }}
                      onClick={() => api.downloadJson(batch.results, 'enriched_catalog.json')}
                      type="button"
                    >
                      Download JSON
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="col">
          {tab === 'batch' && batch && (
            <>
              <BatchSummary summary={batch.summary} />
              <BatchTable
                results={batch.results}
                selected={selectedRow}
                onSelect={setSelectedRow}
              />
            </>
          )}

          {tab === 'batch' && !batch && <BatchEmpty />}

          {detail ? (
            <>
              <ScoreCard
                readiness={detail.readiness}
                category={detail.category}
                cached={detail.cached}
                mode={detail.mode}
              />
              <IssueList issues={detail.issues} />
              <AttributeTable attributes={detail.attributes} />
              <ContentPanel content={detail.content} />
              <TraceTimeline trace={detail.trace} />

              {tab !== 'batch' && (
                <div className="card">
                  <div className="card-head">
                    <h3>Export</h3>
                  </div>
                  <div className="card-body" style={{ display: 'flex', gap: 8 }}>
                    <button
                      className="btn"
                      onClick={() => api.exportCsv([detail])}
                      type="button"
                    >
                      Download CSV
                    </button>
                    <button
                      className="btn"
                      onClick={() => api.downloadJson(detail, 'enriched_product.json')}
                      type="button"
                    >
                      Download JSON
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : tab === 'single' ? (
            <div className="card">
              <Empty icon="◇" title="Nothing enriched yet">
                Pick a demo case on the left, or type in whatever sparse product data you
                have. Every value the engine produces comes back with its evidence,
                provenance and confidence attached.
              </Empty>
            </div>
          ) : tab === 'document' ? (
            <div className="card">
              <Empty icon="◫" title="No document read yet">
                Drop a supplier datasheet or paste a product page URL. The parser
                recovers the spec table, then the same pipeline classifies, validates
                and scores it — with every value traceable back to the source document.
              </Empty>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
