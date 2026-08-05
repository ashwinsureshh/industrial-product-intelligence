import { useState } from 'react'

const BLANK = {
  sku: '',
  mpn: '',
  brand: '',
  name: '',
  description: '',
  category_hint: '',
  free_text: '',
}

/** Form state holds only the flat string fields; spec pairs live alongside it. */
export function emptyProduct() {
  return { ...BLANK }
}

/** Convert the form's editable pair list into the API's raw_specs object. */
export function toProduct(form, specs) {
  const product = {}
  for (const [key, value] of Object.entries(form)) {
    if (typeof value === 'string' && value.trim()) product[key] = value.trim()
  }
  const rawSpecs = {}
  for (const { key, value } of specs) {
    if (key.trim() && value.trim()) rawSpecs[key.trim()] = value.trim()
  }
  if (Object.keys(rawSpecs).length) product.raw_specs = rawSpecs
  return product
}

export function fromProduct(product) {
  const form = { ...BLANK }
  for (const key of Object.keys(BLANK)) {
    if (product[key]) form[key] = String(product[key])
  }
  const specs = Object.entries(product.raw_specs ?? {}).map(([key, value]) => ({
    key,
    value: String(value),
  }))
  return { form, specs }
}

export default function InputPanel({
  form,
  setForm,
  specs,
  setSpecs,
  onRun,
  onClear,
  loading,
}) {
  const [showSpecs, setShowSpecs] = useState(true)

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const updateSpec = (index, field) => (event) => {
    const next = [...specs]
    next[index] = { ...next[index], [field]: event.target.value }
    setSpecs(next)
  }

  const isEmpty =
    !Object.values(form).some((v) => typeof v === 'string' && v.trim()) &&
    !specs.some((s) => s.key.trim() && s.value.trim())

  return (
    <div className="card">
      <div className="card-head">
        <h3>Supplier Input</h3>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={onClear} type="button">
          Clear
        </button>
      </div>

      <div className="card-body">
        <div className="field-row">
          <div className="field">
            <label htmlFor="sku">SKU</label>
            <input id="sku" value={form.sku} onChange={update('sku')} placeholder="BRG-6205-2RS" />
          </div>
          <div className="field">
            <label htmlFor="mpn">Manufacturer Part Number</label>
            <input id="mpn" value={form.mpn} onChange={update('mpn')} placeholder="6205-2RS" />
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="brand">Brand</label>
            <input id="brand" value={form.brand} onChange={update('brand')} placeholder="skf" />
          </div>
          <div className="field">
            <label htmlFor="hint">Category Hint</label>
            <input
              id="hint"
              value={form.category_hint}
              onChange={update('category_hint')}
              placeholder="bearings"
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="name">Product Name</label>
          <input
            id="name"
            value={form.name}
            onChange={update('name')}
            placeholder="Deep groove ball bearing"
          />
        </div>

        <div className="field">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={form.description}
            onChange={update('description')}
            placeholder="Whatever prose the supplier gave you."
          />
        </div>

        <div className="field">
          <label htmlFor="free">Unstructured Text</label>
          <textarea
            id="free"
            value={form.free_text}
            onChange={update('free_text')}
            placeholder="Paste a catalog paragraph, a scraped table, or a datasheet extract."
          />
        </div>

        <div className="field">
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setShowSpecs((v) => !v)}
              style={{ padding: '2px 8px' }}
            >
              {showSpecs ? '−' : '+'}
            </button>
            Supplier Spec Table ({specs.filter((s) => s.key.trim()).length})
          </label>
        </div>

        {showSpecs && (
          <div style={{ marginBottom: 12 }}>
            {specs.map((spec, index) => (
              <div className="spec-row" key={index}>
                <input
                  value={spec.key}
                  onChange={updateSpec(index, 'key')}
                  placeholder="Bore"
                  aria-label={`Spec name ${index + 1}`}
                />
                <input
                  value={spec.value}
                  onChange={updateSpec(index, 'value')}
                  placeholder="25 mm"
                  aria-label={`Spec value ${index + 1}`}
                />
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setSpecs(specs.filter((_, i) => i !== index))}
                  aria-label="Remove this spec"
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setSpecs([...specs, { key: '', value: '' }])}
            >
              + Add spec field
            </button>
          </div>
        )}

        <button
          className="btn btn-primary btn-block"
          onClick={onRun}
          disabled={loading || isEmpty}
          type="button"
        >
          {loading ? (
            <>
              <span className="spinner" /> Enriching…
            </>
          ) : (
            'Enrich Product'
          )}
        </button>
      </div>
    </div>
  )
}
