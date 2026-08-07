import { Badge } from './shared.jsx'

const ACTION_META = {
  refused: { badge: 'sev-error', label: 'refused', order: 0 },
  displaced_default: { badge: 'prov-inferred', label: 'replaced a default', order: 1 },
  gap_filled: { badge: 'prov-inferred', label: 'filled a gap', order: 2 },
}

/**
 * What the AI proposed, and what the gate did about it.
 *
 * Refusals sort first on purpose. Every catalog tool can list what a model
 * added; the interesting column is what it was stopped from overwriting, and
 * burying that under the accepted values would waste the only evidence a
 * reviewer has that the guardrail is real rather than claimed.
 */
export default function GateLedger({ gate }) {
  if (!gate) return null

  const actions = [...(gate.actions ?? [])].sort(
    (a, b) => ACTION_META[a.action].order - ACTION_META[b.action].order,
  )
  const contributed = gate.gap_filled + gate.displaced_defaults

  return (
    <div className="card">
      <div className="card-head">
        <h3>AI gate</h3>
        <div className="spacer" />
        {gate.refused > 0 && <Badge kind="sev-error">{gate.refused} refused</Badge>}
        <Badge kind="prov-inferred">{contributed} accepted</Badge>
      </div>

      <div className="card-body tight">
        <div className="gate-intro">
          The deterministic engine stays authoritative. The AI may fill a blank or
          replace an unconfirmed category default — it may never overwrite a value
          backed by the supplier, the part number, a published standard or a
          calculation.
          {gate.live_source === 'precomputed' && (
            <> These AI proposals were computed in advance and ship with the app, so
            this runs at no cost and with no API key.</>
          )}
        </div>

        {actions.length === 0 ? (
          <div className="gate-empty">
            The AI proposed nothing this record did not already have.
          </div>
        ) : (
          actions.map((action, index) => (
            <div className={`gate-row ${action.action}`} key={`${action.key}-${index}`}>
              <div className="gate-row-head">
                <Badge kind={ACTION_META[action.action].badge}>
                  {ACTION_META[action.action].label}
                </Badge>
                <span className="gate-attr">{action.label}</span>
              </div>

              <div className="gate-values">
                <span className="gate-proposed">
                  AI proposed <strong>{action.proposed}</strong>
                </span>
                {action.kept && (
                  <span className="gate-kept">
                    {action.action === 'refused' ? 'kept' : 'replaced'}{' '}
                    <strong>{action.kept}</strong>
                    <span className="gate-prov"> · {action.kept_provenance}</span>
                  </span>
                )}
              </div>

              <div className="gate-reason">{action.reason}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
