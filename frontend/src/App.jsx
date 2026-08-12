import { useEffect, useMemo, useState } from 'react'
import * as api from './api.js'
import AttributeTable from './components/AttributeTable.jsx'
import BatchInput, { BatchEmpty, BatchSummary, BatchTable } from './components/BatchView.jsx'
import CompliancePanel from './components/CompliancePanel.jsx'
import ContentPanel from './components/ContentPanel.jsx'
import ExportPanel from './components/ExportPanel.jsx'
import DiscoveryInput, { DiscoveryEmpty, SourceLedger } from './components/DiscoveryPanel.jsx'
import GateLedger from './components/GateLedger.jsx'
import DocumentInput, { IngestReport } from './components/DocumentPanel.jsx'
import InputPanel, { emptyProduct, fromProduct, toProduct } from './components/InputPanel.jsx'
import IssueList from './components/IssueList.jsx'
import ScoreCard from './components/ScoreCard.jsx'
import TaxonomyInput, { ProposalList, TaxonomyEmpty } from './components/TaxonomyPanel.jsx'
import TraceTimeline from './components/TraceTimeline.jsx'
import { Empty } from './components/shared.jsx'

const BLANK_SPECS = [{ key: '', value: '' }]

// Inline so the icons cannot fail to load; the project ships no icon library.
const SUN_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4.2" />
    <path d="M12 2.4v2.2M12 19.4v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.4 12h2.2M19.4 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" />
  </svg>
)

const MOON_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20.5 14.6A8.6 8.6 0 1 1 9.4 3.5a6.8 6.8 0 0 0 11.1 11.1z" />
  </svg>
)

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
  const [discovery, setDiscovery] = useState(null)
  const [discoverySources, setDiscoverySources] = useState(null)
  const [proposals, setProposals] = useState(null)
  const [proposalSummary, setProposalSummary] = useState(null)
  const [proposalCounts, setProposalCounts] = useState(null)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // null means "follow the operating system". Only an explicit choice is
  // stored, so a visitor who never touches the toggle keeps tracking their
  // OS setting instead of being frozen at whatever it was on first visit.
  const [theme, setTheme] = useState(() => localStorage.getItem('pi-theme'))

  useEffect(() => {
    if (theme) {
      document.documentElement.setAttribute('data-theme', theme)
      localStorage.setItem('pi-theme', theme)
    } else {
      document.documentElement.removeAttribute('data-theme')
      localStorage.removeItem('pi-theme')
    }
  }, [theme])

  // Re-render when the OS theme changes, but only while following it.
  const [osDark, setOsDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e) => setOsDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const isDark = theme ? theme === 'dark' : osDark

  // Both bars get out of the way while you read down a long result and come
  // back on the way up. One piece of state drives both, so the header and the
  // nav can never disagree about whether the chrome is retreating. Two guards
  // matter: a threshold, or sub-pixel scroll jitter flickers them; and a
  // bottom check, or reaching the end of the page leaves them hidden with
  // nothing left to scroll up.
  const [chromeHidden, setChromeHidden] = useState(false)
  useEffect(() => {
    let last = window.scrollY
    let lastRun = 0

    // Deliberately not requestAnimationFrame: the work is three property reads
    // and a setState, and a plain time throttle stays testable in environments
    // where rAF does not run.
    const decide = () => {
      const y = window.scrollY
      const atBottom = window.innerHeight + y >= document.documentElement.scrollHeight - 8
      if (atBottom) {
        setChromeHidden(false)
        last = y
      } else if (Math.abs(y - last) > 6) {
        setChromeHidden(y > last && y > 80)
        last = y
      }
    }

    const onScroll = () => {
      const now = Date.now()
      if (now - lastRun < 60) return
      lastRun = now
      decide()
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

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

  // Discovery returns a record either way. Finding nothing is a legitimate,
  // informative outcome — the source ledger explains which pages were refused
  // and why — so an empty result is not treated as an error.
  const runDiscover = async (brand, mpn) => {
    setLoading(true)
    setError(null)
    setDiscovery(null)
    setResult(null)
    try {
      const response = await api.discover(brand, mpn, mode, apiKey)
      setDiscovery(response.discovery)
      setResult(response.result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const refreshProposals = async () => {
    try {
      const response = await api.listProposals()
      setProposals(response.proposals)
      setProposalCounts(response.counts)
    } catch (err) {
      setError(err.message)
    }
  }

  const runPropose = async () => {
    if (!samples?.learning_demo) return
    setLoading(true)
    setError(null)
    try {
      const response = await api.proposeCategories(samples.learning_demo, mode, apiKey)
      setProposalSummary(response)
      await refreshProposals()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const reviewProposal = async (id, decision) => {
    setLoading(true)
    setError(null)
    try {
      await api.reviewProposal(id, decision)
      await refreshProposals()
      // An approval changes the live taxonomy, so the header count is stale.
      api.getHealth().then(setHealth).catch(() => {})
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

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

  // Hybrid is not simply "live with a gate" from the user's side: the demo
  // products ship stored AI proposals, so it costs nothing and needs no key.
  // Only a product the app has never seen requires one, and even then it
  // degrades to the deterministic record rather than failing.
  const liveWarning = !apiKey && !health?.server_key_fallback
    ? mode === 'live'
      ? 'Live mode needs your own Anthropic API key. Without one the request runs on the demo engine.'
      : mode === 'hybrid'
        ? 'Hybrid replays AI proposals that ship with the demo products, so it costs you nothing and needs no key here. To run it on a product of your own, enter a key under Live AI first — it carries over. Without one there is no proposal to gate, so you get the deterministic record.'
        : null
    : null

  return (
    <div className="app">
      <header className={`topbar ${chromeHidden ? 'chrome-hidden' : ''}`}>
        <div className="brand">
          <div className="brand-mark">PI</div>
          <div className="brand-text">
            <h1>Product Intelligence</h1>
            <p>Sparse supplier data → validated, explainable catalog records</p>
          </div>
        </div>

        <div className="topbar-spacer" />

        <nav className={`tabs main-nav ${chromeHidden ? 'nav-hidden' : ''}`} aria-label="Sections">
          <button
            className={`tab ${tab === 'single' ? 'active' : ''}`}
            onClick={() => setTab('single')}
            aria-current={tab === 'single' ? 'page' : undefined}
          >
            Single Product
          </button>
          <button
            className={`tab ${tab === 'document' ? 'active' : ''}`}
            onClick={() => setTab('document')}
            title="Read a datasheet PDF or a supplier product page"
            aria-current={tab === 'document' ? 'page' : undefined}
          >
            Document
          </button>
          <button
            className={`tab ${tab === 'discover' ? 'active' : ''}`}
            onClick={() => {
              setTab('discover')
              if (discoverySources === null) {
                api.getDiscoverySources().then(setDiscoverySources).catch(() => {})
              }
            }}
            title="Find a part on its manufacturer's site from a brand and a part number"
            aria-current={tab === 'discover' ? 'page' : undefined}
          >
            Discover
          </button>
          <button
            className={`tab ${tab === 'batch' ? 'active' : ''}`}
            onClick={() => setTab('batch')}
            aria-current={tab === 'batch' ? 'page' : undefined}
          >
            Catalog
          </button>
          <button
            className={`tab ${tab === 'taxonomy' ? 'active' : ''}`}
            onClick={() => {
              setTab('taxonomy')
              if (proposals === null) refreshProposals()
            }}
            title="Propose and approve categories the engine has never seen"
            aria-current={tab === 'taxonomy' ? 'page' : undefined}
          >
            Learning
          </button>
        </nav>

        <div className="tabs engine-toggle">
          <button
            className={`tab ${mode === 'demo' ? 'active' : ''}`}
            onClick={() => setMode('demo')}
            title="Deterministic engine — no API key, no cost, identical output every run."
          >
            Demo
          </button>
          <button
            className={`tab ${mode === 'hybrid' ? 'active' : ''}`}
            onClick={() => setMode('hybrid')}
            title="Deterministic engine plus a bounded AI contribution: it may fill a
                   blank or replace a default, never overwrite evidence. Best measured
                   result. Free on the demo products."
          >
            Hybrid
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

        <button
          className="theme-toggle"
          onClick={() => setTheme(isDark ? 'light' : 'dark')}
          title={`Switch to ${isDark ? 'light' : 'dark'} theme`}
          aria-label={`Switch to ${isDark ? 'light' : 'dark'} theme`}
        >
          {isDark ? SUN_ICON : MOON_ICON}
        </button>
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
          ) : tab === 'taxonomy' ? (
            <TaxonomyInput
              onPropose={runPropose}
              onRefresh={refreshProposals}
              loading={loading}
              summary={proposalSummary}
              counts={proposalCounts}
              demoSize={samples?.learning_demo?.length}
            />
          ) : tab === 'discover' ? (
            <DiscoveryInput
              onDiscover={runDiscover}
              loading={loading}
              sources={discoverySources}
            />
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
                <ExportPanel records={batch.results} stem="enriched_catalog" />
              )}
            </>
          )}
        </div>

        <div className="col">
          {tab === 'taxonomy' && (
            proposals?.length ? (
              <ProposalList
                proposals={proposals}
                onReview={reviewProposal}
                busy={loading}
              />
            ) : (
              <TaxonomyEmpty />
            )
          )}

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

          {tab === 'discover' && discovery && <SourceLedger discovery={discovery} />}

          {tab !== 'taxonomy' && detail ? (
            <>
              <ScoreCard
                readiness={detail.readiness}
                category={detail.category}
                cached={detail.cached}
                mode={detail.mode}
              />
              <GateLedger gate={detail.gate} />
              <IssueList issues={detail.issues} />
              <AttributeTable attributes={detail.attributes} />
              <ContentPanel content={detail.content} />
              <CompliancePanel compliance={detail.compliance} />
              <TraceTimeline trace={detail.trace} />

              {tab !== 'batch' && (
                <ExportPanel records={[detail]} stem="enriched_product" />
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
          ) : tab === 'discover' ? (
            !discovery && <DiscoveryEmpty />
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
