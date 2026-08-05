export const PROVENANCE = {
  supplied: { label: 'Supplied', color: 'var(--supplied)', hint: 'Present verbatim in the supplier record.' },
  parsed: { label: 'Parsed', color: 'var(--parsed)', hint: 'Deconstructed from supplier text or a spec key.' },
  knowledge_base: { label: 'Standard', color: 'var(--kb)', hint: 'Fixed by a published dimensional standard.' },
  derived: { label: 'Derived', color: 'var(--derived)', hint: 'Computed from other known attributes.' },
  inferred: { label: 'Inferred', color: 'var(--inferred)', hint: 'Model inference from surrounding context.' },
  defaulted: { label: 'Default', color: 'var(--defaulted)', hint: 'Category-typical placeholder; needs confirmation.' },
}

export function Badge({ kind, children }) {
  return (
    <span className={`badge ${kind}`}>
      <span className="badge-dot" />
      {children}
    </span>
  )
}

export function ProvenanceBadge({ provenance }) {
  const meta = PROVENANCE[provenance] ?? { label: provenance }
  return <Badge kind={`prov-${provenance}`}>{meta.label}</Badge>
}

export function confidenceColor(value) {
  if (value >= 0.85) return 'var(--ok)'
  if (value >= 0.65) return 'var(--parsed)'
  if (value >= 0.5) return 'var(--warning)'
  return 'var(--error)'
}

export function scoreColor(value) {
  if (value >= 78) return 'var(--ok)'
  if (value >= 55) return 'var(--warning)'
  return 'var(--error)'
}

export function formatValue(attribute) {
  const { value, unit } = attribute
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return unit ? `${value} ${unit}` : String(value)
}

export function Empty({ icon, title, children }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}
