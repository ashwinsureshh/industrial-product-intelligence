export default function TraceTimeline({ trace }) {
  const total = trace.reduce((sum, stage) => sum + (stage.duration_ms || 0), 0)

  return (
    <div className="card">
      <div className="card-head">
        <h3>Pipeline Trace</h3>
        <div className="spacer" />
        <span className="pill">{trace.length} stages</span>
        <span className="pill">{total} ms</span>
      </div>

      <div className="card-body tight">
        <div className="trace">
          {trace.map((stage, index) => (
            <div className="trace-item" key={`${stage.stage}-${index}`}>
              <div className="trace-marker">
                <div className="trace-dot" />
                {index < trace.length - 1 && <div className="trace-line" />}
              </div>
              <div className="trace-body">
                <div className="trace-head">
                  <span className="trace-stage">{stage.stage}</span>
                  <span className="trace-ms">{stage.duration_ms} ms</span>
                </div>
                <div className="trace-summary">{stage.summary}</div>

                {stage.added?.length > 0 && (
                  <div className="trace-chips">
                    {stage.added.slice(0, 12).map((key) => (
                      <span className="chip" key={key}>
                        +{key}
                      </span>
                    ))}
                    {stage.added.length > 12 && (
                      <span className="chip">+{stage.added.length - 12} more</span>
                    )}
                  </div>
                )}

                {stage.details?.conflicts?.length > 0 && (
                  <div className="trace-chips">
                    {stage.details.conflicts.map((conflict, i) => (
                      <span className="chip" key={i} style={{ color: 'var(--warning)' }}>
                        {conflict}
                      </span>
                    ))}
                  </div>
                )}

                {stage.details?.unmapped_supplier_fields?.length > 0 && (
                  <div className="trace-chips">
                    {stage.details.unmapped_supplier_fields.map((field) => (
                      <span
                        className="chip"
                        key={field.key}
                        title="No taxonomy attribute matched this supplier field, so it was preserved rather than dropped."
                      >
                        unmapped: {field.key}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
