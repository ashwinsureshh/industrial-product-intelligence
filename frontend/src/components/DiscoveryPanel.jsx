import { useState } from 'react'
import { Badge, Empty } from './shared.jsx'

/**
 * Brand + part number in, manufacturer page out.
 *
 * The input is deliberately two fields. This is the organizers' stated core
 * problem — "take a manufacturer name and part number and search manufacturer
 * websites" — and anything more elaborate would obscure how little the engine
 * is being given to work with.
 */
export default function DiscoveryInput({ onDiscover, loading, sources }) {
  const [brand, setBrand] = useState('')
  const [mpn, setMpn] = useState('')

  const submit = () => {
    if (brand.trim() || mpn.trim()) onDiscover(brand.trim(), mpn.trim())
  }

  const examples = [
    { brand: 'FRIGIDAIRE', mpn: 'PDSH4816AF', note: 'the row from their own delivery format' },
    { brand: 'Milwaukee', mpn: '49-94-0107', note: 'publishes schema.org product markup' },
    { brand: 'SKF', mpn: '6205-2RS', note: 'renders client-side — the known wall' },
    { brand: 'Wumpus', mpn: 'X-1', note: 'not an approved manufacturer' },
  ]

  return (
    <>
      <div className="card">
        <div className="card-head">
          <h3>Find by Part Number</h3>
        </div>
        <div className="card-body">
          <div className="field">
            <label htmlFor="disc-brand">Manufacturer or brand</label>
            <input
              id="disc-brand"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder="FRIGIDAIRE"
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
          </div>

          <div className="field">
            <label htmlFor="disc-mpn">Manufacturer part number</label>
            <div className="key-input">
              <input
                id="disc-mpn"
                value={mpn}
                onChange={(e) => setMpn(e.target.value)}
                placeholder="PDSH4816AF"
                onKeyDown={(e) => e.key === 'Enter' && submit()}
              />
              <button
                className="btn btn-primary"
                type="button"
                onClick={submit}
                disabled={loading || (!brand.trim() && !mpn.trim())}
              >
                {loading ? <span className="spinner" /> : 'Discover'}
              </button>
            </div>
          </div>

          <p style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 4 }}>
            Searches the manufacturer's own site only. Marketplaces, retailers and
            distributors are refused rather than filtered out afterwards, and every
            source considered is listed with the reason it was used or rejected.
            Costs nothing — no API key, no search engine.
          </p>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Try these</h3>
        </div>
        <div className="card-body">
          <div className="sample-list">
            {examples.map((ex) => (
              <button
                key={ex.mpn}
                type="button"
                className="sample"
                onClick={() => {
                  setBrand(ex.brand)
                  setMpn(ex.mpn)
                  onDiscover(ex.brand, ex.mpn)
                }}
              >
                <div className="sample-label">{ex.brand} {ex.mpn}</div>
                <div className="sample-intent">{ex.note}</div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {sources && <SourcePolicy sources={sources} />}
    </>
  )
}

/** The rule, stated up front, so the refusals below are not a surprise. */
function SourcePolicy({ sources }) {
  const [open, setOpen] = useState(false)
  const byKind = {}
  for (const entry of sources.blocked ?? []) {
    byKind[entry.kind] = (byKind[entry.kind] ?? 0) + 1
  }

  return (
    <div className="card">
      <div className="card-head">
        <h3>Sourcing policy</h3>
        <div className="spacer" />
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => setOpen((v) => !v)}
          style={{ padding: '1px 8px' }}
        >
          {open ? 'hide' : 'show'}
        </button>
      </div>
      {open && (
        <div className="card-body tight">
          <div className="gate-intro">
            Product data must come from the manufacturer. Distributors and retailers
            are blocked alongside marketplaces, because a distributor listing is a
            second-hand copy of the manufacturer's data — which is exactly the copy
            this engine exists to correct.
          </div>
          <div className="tag-row" style={{ marginBottom: 10 }}>
            {Object.entries(byKind).map(([kind, count]) => (
              <span className="pill" key={kind}>{count} {kind}</span>
            ))}
            <span className="pill">{sources.brands?.length ?? 0} approved manufacturers</span>
          </div>
          <div className="gate-reason">
            Unknown domains are {sources.allow_unknown_domains ? 'permitted' : 'refused'}.
            {!sources.allow_unknown_domains && (
              <> A page can only be cited as manufacturer-provided if the domain is known
              to belong to that manufacturer, so an unrecognised site is never fetched.</>
            )}
            {sources.source === 'provisional' && (
              <> The manufacturer registry is a provisional stand-in for Unilog's
              27,000-row approved brand list.</>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Every source considered, refusals first.
 *
 * Same reasoning as the AI gate ledger: any crawler can list the page it used.
 * What it declined to read is the only evidence a reviewer has that the
 * manufacturer-only rule is enforced rather than asserted.
 */
export function SourceLedger({ discovery }) {
  if (!discovery) return null

  const sources = [...(discovery.sources ?? [])].sort(
    (a, b) => Number(a.accepted) - Number(b.accepted),
  )

  return (
    <div className="card">
      <div className="card-head">
        <h3>Sources</h3>
        <div className="spacer" />
        {discovery.refused > 0 && (
          <Badge kind="sev-error">{discovery.refused} refused</Badge>
        )}
        <Badge kind="prov-parsed">{discovery.accepted} used</Badge>
        <span className="pill" title="Discovery cost for this part">
          ${Number(discovery.spent_usd ?? 0).toFixed(4)}
        </span>
      </div>

      <div className="card-body tight">
        <div className="gate-intro">
          Searched via <strong>{discovery.backend}</strong> in {discovery.duration_ms}ms.
          {!discovery.found && (
            <> No page contributed anything, so <strong>any record below was built
            from the part number alone</strong> — decoded against published standards,
            not read off a manufacturer page.</>
          )}
        </div>

        {sources.length === 0 ? (
          <div className="gate-empty">
            No candidate source was produced, so nothing was fetched.
          </div>
        ) : (
          sources.map((source, index) => (
            <div
              className={`gate-row ${source.accepted ? 'gap_filled' : 'refused'}`}
              key={`${source.url}-${index}`}
            >
              <div className="gate-row-head">
                <Badge kind={source.accepted ? 'prov-parsed' : 'sev-error'}>
                  {source.accepted ? 'used' : 'refused'}
                </Badge>
                {source.kind && <span className="pill">{source.kind}</span>}
                {source.fetched && (
                  <span className="pill">
                    HTTP {source.status} · {source.specs_found} spec
                    {source.specs_found === 1 ? '' : 's'}
                  </span>
                )}
              </div>

              <div className="gate-values">
                <a
                  className="mono"
                  href={source.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  style={{ wordBreak: 'break-all' }}
                >
                  {source.url}
                </a>
              </div>

              <div className="gate-reason">{source.reason}</div>
            </div>
          ))
        )}

        {discovery.notes?.map((note, index) => (
          <div className="gate-reason" key={index} style={{ marginTop: 8 }}>
            {note}
          </div>
        ))}
      </div>
    </div>
  )
}

export function DiscoveryEmpty() {
  return (
    <div className="card">
      <Empty icon="◎" title="Nothing discovered yet">
        Give the engine only what a distributor actually has — a brand and a part
        number — and it will look for the manufacturer's own page. Every source it
        considers is listed with the reason it was used or refused, and any value it
        finds carries the URL it was read from.
      </Empty>
    </div>
  )
}
