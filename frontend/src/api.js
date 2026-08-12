const json = async (response) => {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      /* the response had no JSON body; keep the status message */
    }
    throw new Error(detail)
  }
  return response.json()
}

export const getHealth = () => fetch('/api/health').then(json)
export const getSamples = () => fetch('/api/samples').then(json)
export const getTaxonomy = () => fetch('/api/taxonomy').then(json)

export const enrich = (product, mode, apiKey) =>
  fetch('/api/enrich', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product, mode, api_key: apiKey || null }),
  }).then(json)

export const enrichBatch = (products, mode, apiKey) =>
  fetch('/api/enrich/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ products, mode, api_key: apiKey || null }),
  }).then(json)

export const enrichCsv = (file, mode, apiKey) => {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', mode)
  if (apiKey) form.append('api_key', apiKey)
  return fetch('/api/enrich/csv', { method: 'POST', body: form }).then(json)
}

export const ingestPdf = (file, mode, apiKey) => {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', mode)
  if (apiKey) form.append('api_key', apiKey)
  return fetch('/api/ingest/pdf', { method: 'POST', body: form }).then(json)
}

export const ingestUrl = (url, mode, apiKey) =>
  fetch('/api/ingest/url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, mode, api_key: apiKey || null }),
  }).then(json)

export const discover = (brand, mpn, mode, apiKey) =>
  fetch('/api/discover', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brand, mpn, mode, api_key: apiKey || null }),
  }).then(json)

export const getDiscoverySources = () => fetch('/api/discover/sources').then(json)

export const getExportProfiles = () => fetch('/api/export/profiles').then(json)

/** Render records into a named output schema and download the result. */
export const exportProfile = async (results, profile, filename) => {
  const response = await fetch(`/api/export?profile=${encodeURIComponent(profile)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(results),
  })
  if (!response.ok) throw new Error(`Export failed (${response.status})`)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const proposeCategories = (products, mode, apiKey) =>
  fetch('/api/taxonomy/propose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ products, mode, api_key: apiKey || null }),
  }).then(json)

export const listProposals = () => fetch('/api/taxonomy/proposals').then(json)

export const reviewProposal = (id, decision, note) =>
  fetch(`/api/taxonomy/proposals/${id}/${decision}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note: note || null }),
  }).then(json)

export const revokeLearned = (code) =>
  fetch(`/api/taxonomy/learned/${code}`, { method: 'DELETE' }).then(json)

// The fixed /api/export/csv shape is now reached as the `catalog_csv` profile,
// so the UI has one export path and the target schema stays data.

export const downloadJson = (data, filename) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
