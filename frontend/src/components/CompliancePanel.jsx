import { Badge } from './shared.jsx'

/**
 * The customer's content standard, made visible.
 *
 * Readiness asks whether the data is right; this asks whether it is written the
 * way the customer requires — and the two fail independently, which is why they
 * are scored and shown separately. The same product is written five times at
 * five lengths, and getting those formats right is most of the delivery task.
 *
 * The dropped-token list is the part worth reading. Cutting a 40-character line
 * at 40 characters gives a truncated part number, which is unsearchable; the
 * engine drops whole low-priority facts instead and says which ones went.
 */
export default function CompliancePanel({ compliance }) {
  if (!compliance?.fields?.length) return null

  const { fields, standards, breaches, lov, vocabulary_mappings: mappings } = compliance
  const provisional = Object.entries(standards || {}).filter(([, v]) => v === 'provisional')

  return (
    <div className="card">
      <div className="card-head">
        <h3>Content Standard</h3>
        <div className="spacer" />
        <Badge kind={compliance.compliant ? 'prov-supplied' : 'sev-error'}>
          {compliance.compliant ? 'within limits' : `${breaches.length} breach`}
        </Badge>
      </div>

      <div className="card-body tight">
        {fields.map((field) => (
          <ComplianceField key={field.id} field={field} />
        ))}

        {mappings?.length > 0 && (
          <div className="content-block" style={{ marginTop: 12 }}>
            <div className="content-label">Vocabulary mapped</div>
            {mappings.map((m, i) => (
              <div className="gate-reason" key={i}>
                {m.from} → {m.to}{m.reason ? ` — ${m.reason}` : ''}
              </div>
            ))}
          </div>
        )}

        {/* A stub rule book must never read as verified compliance. */}
        {provisional.length > 0 && (
          <div className="banner banner-warn" style={{ marginTop: 12 }}>
            <span>
              Checked against a provisional stand-in for{' '}
              {provisional.map(([k]) => LABELS[k] || k).join(' and ')}. The
              customer's own tables have not been supplied yet, so this is house
              style as we understand it — not certified compliance.
            </span>
          </div>
        )}

        {lov && lov.applicable === false && (
          <div className="gate-reason" style={{ marginTop: 10 }}>
            No list of values covers this category, so no controlled-vocabulary
            check applies. That is not the same as passing one.
          </div>
        )}
      </div>
    </div>
  )
}

const LABELS = {
  uom: 'the units and abbreviations table',
  content_formats: 'the content formulas',
  lov: 'the list of values',
}

function ComplianceField({ field }) {
  const { length, min_length: min, max_length: max } = field
  // A bare number next to a ceilingless field reads as a score out of nothing.
  const limit = max ? `${length} / ${max}` : `${length} chars`
  const range = min ? `${min}–${max}` : max ? `max ${max}` : null

  // Fills as the text approaches its ceiling. A field with no ceiling has no
  // bar to fill: showing one at 100% would read as a breach.
  const pct = max ? Math.min((length / max) * 100, 100) : null
  const tone = !field.compliant
    ? 'var(--error)'
    : min && length < min
      ? 'var(--warning)'
      : 'var(--ok)'

  return (
    <div className="gate-row">
      <div className="gate-row-head">
        <span className="gate-attr">{field.label}</span>
        {range && <span className="pill">{range} chars</span>}
        <div className="spacer" />
        <span
          className="pill"
          style={{ color: tone, fontVariantNumeric: 'tabular-nums' }}
        >
          {limit}
        </span>
      </div>

      <div className="content-text" style={{ marginTop: 5 }}>
        {field.text || <em style={{ color: 'var(--text-3)' }}>(empty — nothing to write)</em>}
      </div>

      {pct !== null && (
        <div className="bar" style={{ marginTop: 6 }}>
          <div className="bar-fill" style={{ width: `${pct}%`, background: tone }} />
        </div>
      )}

      {field.dropped?.length > 0 && (
        <div className="gate-reason" style={{ marginTop: 5 }}>
          Dropped whole to fit:{' '}
          <span style={{ color: 'var(--warning)' }}>{field.dropped.join(', ')}</span>
          {' — '}the part number is never cut mid-code.
        </div>
      )}

      {field.notes?.filter((n) => !n.startsWith('Dropped to fit')).map((note, i) => (
        <div className="gate-reason" key={i} style={{ marginTop: 5 }}>{note}</div>
      ))}
    </div>
  )
}
