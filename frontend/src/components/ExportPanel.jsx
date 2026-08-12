import { useEffect, useState } from 'react'
import * as api from '../api.js'

const EXTENSION = { csv: 'csv', jsonld: 'jsonld', json: 'json' }

/**
 * Export as a choice of target schema rather than one hard-coded sheet.
 *
 * The output schema is data, not code — profiles live in data/export_profiles/
 * — so the customer's 252-column delivery format and schema.org come out of the
 * same machinery as our own catalogue sheet. Hiding that behind a single
 * "Download CSV" button made the most customer-specific work in the project
 * invisible from the product.
 */
export default function ExportPanel({ records, stem }) {
  const [profiles, setProfiles] = useState(null)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getExportProfiles()
      .then((r) => setProfiles(r.profiles))
      .catch(() => setProfiles([]))
  }, [])

  if (!records?.length) return null

  const run = async (profile) => {
    setBusy(profile.id)
    setError(null)
    try {
      const ext = EXTENSION[profile.format] || 'txt'
      await api.exportProfile(records, profile.id, `${stem}.${ext}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <h3>Export</h3>
        <div className="spacer" />
        <span className="pill">{records.length} record{records.length === 1 ? '' : 's'}</span>
      </div>

      <div className="card-body tight">
        {error && <div className="banner banner-error" style={{ marginBottom: 10 }}><span>{error}</span></div>}

        {(profiles ?? []).map((profile) => (
          <div className="gate-row" key={profile.id}>
            <div className="gate-row-head">
              <span className="gate-attr">{profile.label}</span>
              {/* .pill ellipsizes at max-width:100% so supplier text cannot set
                  the page width. A three-word format name is not that, and it
                  must not lose its last letter to a flex squeeze. */}
              <span className="pill" style={{ flexShrink: 0 }}>{profile.format}</span>
              <div className="spacer" />
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => run(profile)}
                disabled={busy !== null}
              >
                {busy === profile.id ? 'Rendering…' : 'Download'}
              </button>
            </div>
            <div className="gate-reason" style={{ marginTop: 4 }}>{profile.description}</div>
          </div>
        ))}

        {profiles?.length === 0 && (
          <div className="gate-reason">No export profiles are configured.</div>
        )}

        <div className="gate-row">
          <div className="gate-row-head">
            <span className="gate-attr">Raw record</span>
            <span className="pill" style={{ flexShrink: 0 }}>json</span>
            <div className="spacer" />
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => api.downloadJson(
                records.length === 1 ? records[0] : records, `${stem}.json`,
              )}
            >
              Download
            </button>
          </div>
          <div className="gate-reason" style={{ marginTop: 4 }}>
            Everything the pipeline produced, including the trace and every
            attribute's provenance, confidence and source.
          </div>
        </div>
      </div>
    </div>
  )
}
