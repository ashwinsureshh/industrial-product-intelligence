import { Badge } from './shared.jsx'

export default function IssueList({ issues }) {
  const errors = issues.filter((i) => i.severity === 'error').length
  const warnings = issues.filter((i) => i.severity === 'warning').length

  return (
    <div className="card">
      <div className="card-head">
        <h3>Validation</h3>
        <div className="spacer" />
        {errors > 0 && <Badge kind="sev-error">{errors} blocking</Badge>}
        {warnings > 0 && <Badge kind="sev-warning">{warnings} warning</Badge>}
        {issues.length === 0 && <Badge kind="verdict-publish">All checks passed</Badge>}
      </div>

      <div className="card-body tight">
        {issues.length === 0 ? (
          <div style={{ padding: '22px 15px', textAlign: 'center', color: 'var(--text-2)', fontSize: 13 }}>
            No range violations, vocabulary breaches or cross-field contradictions found.
          </div>
        ) : (
          issues.map((issue, index) => (
            <div className={`issue ${issue.severity}`} key={`${issue.code}-${issue.field}-${index}`}>
              <div className="issue-body">
                <div className="issue-title">
                  <Badge kind={`sev-${issue.severity}`}>{issue.severity}</Badge>
                  <span className="issue-code">{issue.code}</span>
                  {issue.field && <span className="mono" style={{ color: 'var(--text-3)' }}>· {issue.field}</span>}
                </div>
                <div className="issue-msg">{issue.message}</div>
                {issue.suggestion && <div className="issue-fix">{issue.suggestion}</div>}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
