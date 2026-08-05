import { Badge, Empty } from './shared.jsx'

const TYPE_COLOR = {
  number: 'var(--parsed)',
  enum: 'var(--kb)',
  text: 'var(--text-2)',
  boolean: 'var(--derived)',
}

/** One proposed attribute, with the evidence that produced it. */
function AttributeRow({ attribute }) {
  const detail = []
  if (attribute.unit) detail.push(attribute.unit)
  if (attribute.range) detail.push(`${attribute.range[0]} – ${attribute.range[1]}`)

  return (
    <tr style={{ cursor: 'default' }}>
      <td>
        <div style={{ fontWeight: 500 }}>{attribute.label}</div>
        <div className="attr-key">{attribute.key}</div>
      </td>
      <td>
        <span
          className="badge"
          style={{
            background: 'var(--bg)',
            color: TYPE_COLOR[attribute.type] ?? 'var(--text-2)',
          }}
        >
          <span className="badge-dot" />
          {attribute.type}
        </span>
        {detail.length > 0 && (
          <div className="attr-norm" style={{ marginTop: 3 }}>{detail.join('  ·  ')}</div>
        )}
      </td>
      <td>
        {attribute.values ? (
          <div className="tag-row">
            {attribute.values.map((v) => (
              <span className="pill" key={v}>{v}</span>
            ))}
          </div>
        ) : (
          <span className="mono" style={{ color: 'var(--text-3)' }}>
            {attribute.sample_values?.slice(0, 3).join(', ') || '—'}
          </span>
        )}
      </td>
      <td style={{ whiteSpace: 'nowrap' }}>
        {attribute.required && <Badge kind="sev-error">required</Badge>}
      </td>
      <td className="mono" style={{ color: 'var(--text-3)' }}>
        {attribute.observed_in}
      </td>
    </tr>
  )
}

function ProposalCard({ proposal, onReview, busy }) {
  const pending = proposal.status === 'pending'

  return (
    <div className="card">
      <div className="card-head">
        <h3>{proposal.noun}</h3>
        <div className="spacer" />
        <span className="pill">{proposal.sample_count} products</span>
        <span className="pill">{Math.round(proposal.confidence * 100)}% confidence</span>
        <Badge
          kind={
            proposal.status === 'approved'
              ? 'verdict-publish'
              : proposal.status === 'rejected'
                ? 'verdict-blocked'
                : 'verdict-review'
          }
        >
          {proposal.status}
        </Badge>
      </div>

      <div className="card-body">
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 10 }}>
          {proposal.rationale}
        </div>

        <div className="content-block">
          <div className="content-label">Proposed placement</div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{proposal.path.join(' › ')}</div>
          <div className="mono" style={{ color: 'var(--text-3)', marginTop: 2 }}>
            code {proposal.code} · learned
          </div>
        </div>

        <div className="content-block">
          <div className="content-label">Matched from</div>
          <div className="tag-row">
            {proposal.sample_skus.map((sku) => (
              <span className="pill" key={sku}>{sku}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="group-head">
        Inferred schema
        <span className="count">{proposal.attributes.length} attributes</span>
      </div>

      <div className="table-scroll" style={{ maxHeight: 320 }}>
        <table className="grid">
          <thead>
            <tr>
              <th>Attribute</th>
              <th>Type</th>
              <th>Vocabulary / samples</th>
              <th></th>
              <th>Seen</th>
            </tr>
          </thead>
          <tbody>
            {proposal.attributes.map((attribute) => (
              <AttributeRow key={attribute.key} attribute={attribute} />
            ))}
          </tbody>
        </table>
      </div>

      {pending && (
        <div className="card-body" style={{ display: 'flex', gap: 8, borderTop: '1px solid var(--border)' }}>
          <button
            className="btn btn-primary"
            style={{ flex: 1, justifyContent: 'center' }}
            disabled={busy}
            onClick={() => onReview(proposal.id, 'approve')}
            type="button"
          >
            Approve — add to taxonomy
          </button>
          <button
            className="btn"
            disabled={busy}
            onClick={() => onReview(proposal.id, 'reject')}
            type="button"
          >
            Reject
          </button>
        </div>
      )}

      {proposal.status === 'approved' && (
        <div className="card-body" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="banner banner-info">
            Live in the taxonomy. Products of this kind now classify, validate and
            score like any curated category.
          </div>
        </div>
      )}
    </div>
  )
}

export function ProposalList({ proposals, onReview, busy }) {
  if (!proposals?.length) return null
  return (
    <>
      {proposals.map((proposal) => (
        <ProposalCard
          key={proposal.id}
          proposal={proposal}
          onReview={onReview}
          busy={busy}
        />
      ))}
    </>
  )
}

export function TaxonomyEmpty() {
  return (
    <div className="card">
      <Empty icon="⌘" title="No proposals yet">
        Run the unknown-category demo on the left. Products that fit no existing
        category are clustered, and each cluster produces a full schema proposal —
        attributes, types, units, vocabularies and ranges — inferred from the
        products themselves.
      </Empty>
    </div>
  )
}

export default function TaxonomyInput({ onPropose, onRefresh, loading, summary, counts, demoSize }) {
  return (
    <div className="card">
      <div className="card-head">
        <h3>Taxonomy Learning</h3>
        <div className="spacer" />
        {counts && (
          <span className="pill">
            {counts.pending} pending · {counts.approved} approved
          </span>
        )}
      </div>
      <div className="card-body">
        <p style={{ fontSize: 12.5, color: 'var(--text-2)', marginBottom: 12 }}>
          A fixed taxonomy cannot cover a real catalog. When products arrive that
          fit no known category, the engine infers a schema for them and asks a
          human to approve it — so the catalog grows without hand-curation.
        </p>

        <button
          className="btn btn-primary btn-block"
          onClick={onPropose}
          disabled={loading}
          type="button"
        >
          {loading ? (
            <>
              <span className="spinner" /> Analysing…
            </>
          ) : (
            `Analyse ${demoSize ?? 9} unknown products`
          )}
        </button>

        <button
          className="btn btn-block"
          style={{ marginTop: 8 }}
          onClick={onRefresh}
          disabled={loading}
          type="button"
        >
          Refresh proposals
        </button>

        {summary && (
          <div className="summary-grid" style={{ marginTop: 14 }}>
            <div className="stat">
              <div className="stat-value">{summary.examined}</div>
              <div className="stat-label">Examined</div>
            </div>
            <div className="stat">
              <div className="stat-value" style={{ color: 'var(--ok)' }}>
                {summary.classified}
              </div>
              <div className="stat-label">Already known</div>
            </div>
            <div className="stat">
              <div className="stat-value" style={{ color: 'var(--warning)' }}>
                {summary.unclassified}
              </div>
              <div className="stat-label">No category</div>
            </div>
            <div className="stat">
              <div className="stat-value" style={{ color: 'var(--kb)' }}>
                {summary.proposals?.length ?? 0}
              </div>
              <div className="stat-label">Proposed</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
