import { useState } from 'react'
import { Empty, PROVENANCE, ProvenanceBadge, confidenceColor, formatValue } from './shared.jsx'

function AttributeRow({ attribute }) {
  const [open, setOpen] = useState(false)
  const meta = PROVENANCE[attribute.provenance] ?? {}

  return (
    <>
      <div
        className={`attr ${open ? 'open' : ''}`}
        onClick={() => setOpen((value) => !value)}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            setOpen((value) => !value)
          }
        }}
      >
        <div>
          <div className="attr-label">{attribute.label}</div>
          <div className="attr-key">{attribute.key}</div>
        </div>

        <div>
          <div className="attr-value">{formatValue(attribute)}</div>
          {attribute.normalized_value !== null &&
            attribute.normalized_value !== undefined &&
            attribute.normalized_unit &&
            `${attribute.value}` !== `${attribute.normalized_value}` && (
              <div className="attr-norm">
                = {attribute.normalized_value} {attribute.normalized_unit}
              </div>
            )}
        </div>

        <ProvenanceBadge provenance={attribute.provenance} />

        <div className="conf" title={`Confidence ${Math.round(attribute.confidence * 100)}%`}>
          <div className="conf-bar">
            <div
              className="conf-fill"
              style={{
                width: `${attribute.confidence * 100}%`,
                background: confidenceColor(attribute.confidence),
              }}
            />
          </div>
          <span className="conf-num">{Math.round(attribute.confidence * 100)}</span>
        </div>
      </div>

      {open && (
        <div className="evidence">
          <div className="evidence-row">
            <div className="evidence-key">Evidence</div>
            <div className="evidence-val">{attribute.evidence}</div>
          </div>
          <div className="evidence-row">
            <div className="evidence-key">Provenance</div>
            <div className="evidence-val">
              {meta.label} — {meta.hint}
            </div>
          </div>
          <div className="evidence-row">
            <div className="evidence-key">Method</div>
            <div className="evidence-val">
              <code>{attribute.method}</code>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default function AttributeTable({ attributes }) {
  if (!attributes?.length) {
    return (
      <div className="card">
        <div className="card-head">
          <h3>Attributes</h3>
        </div>
        <Empty icon="◌" title="No attributes resolved">
          The engine could not place this product in a category, so no attribute schema applied.
        </Empty>
      </div>
    )
  }

  const groups = attributes.reduce((accumulator, attribute) => {
    ;(accumulator[attribute.group] ||= []).push(attribute)
    return accumulator
  }, {})

  const enriched = attributes.filter(
    (a) => a.provenance !== 'supplied' && a.provenance !== 'parsed',
  ).length

  return (
    <div className="card">
      <div className="card-head">
        <h3>Attributes</h3>
        <div className="spacer" />
        <span className="pill">{attributes.length} resolved</span>
        <span className="pill">{enriched} added by enrichment</span>
      </div>

      <div className="card-body tight">
        {Object.entries(groups).map(([group, items]) => (
          <div key={group}>
            <div className="group-head">
              {group}
              <span className="count">{items.length}</span>
            </div>
            {items.map((attribute) => (
              <AttributeRow key={attribute.key} attribute={attribute} />
            ))}
          </div>
        ))}
      </div>

      <div className="legend">
        {Object.entries(PROVENANCE).map(([key, meta]) => (
          <div className="legend-item" key={key} title={meta.hint}>
            <span className="legend-swatch" style={{ background: meta.color }} />
            {meta.label}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div className="legend-item">Click any row for its full audit trail</div>
      </div>
    </div>
  )
}
