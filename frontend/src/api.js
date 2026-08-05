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

export const exportCsv = async (results) => {
  const response = await fetch('/api/export/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(results),
  })
  if (!response.ok) throw new Error('Export failed')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'enriched_catalog.csv'
  link.click()
  URL.revokeObjectURL(url)
}

export const downloadJson = (data, filename) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
