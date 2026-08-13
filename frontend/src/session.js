/* Keep the last screen across a page refresh.
 *
 * The engine is deliberately stateless — a row goes in, an enriched row comes
 * out, and the customer's PIM stays the system of record. That is the right
 * architecture and it is not what this file changes. What it fixes is a smaller
 * thing that reads like a fault: a reviewer enriches a product, refreshes, and
 * the screen is blank, as though the work had been thrown away. It had not
 * been — the server's content-addressed cache still holds the result — but the
 * only copy of *which* product they were looking at lived in React state.
 *
 * Three rules this file exists to hold:
 *
 * - **The API key is never written.** The field says "your key, never stored"
 *   and that has to stay literally true, so the key is not part of the saved
 *   shape at all rather than being stripped on the way out.
 * - **A stored screen may not outlive the code that renders it.** VERSION is
 *   bumped whenever the record shape changes; an older payload is dropped
 *   rather than rehydrated into components that no longer understand it.
 * - **Failing to save is never an error.** Private browsing, a full quota and a
 *   disabled store all throw, and none of them are worth interrupting someone's
 *   work over.
 */

const KEY = 'pi-session'
const VERSION = 2

// localStorage is ~5 MB per origin, but the whole budget is not ours to spend
// and the failure mode is a thrown exception mid-write. A catalog run of a
// dozen records with full attribute trails is the only thing here big enough to
// approach it.
const LIMIT = 900_000

// Everything the screen needs to look the way it did. `apiKey` is conspicuously
// absent and must stay that way.
const FIELDS = [
  'tab', 'mode', 'form', 'specs', 'activeSample',
  'result', 'batch', 'selectedRow', 'ingest', 'discovery',
]

export function loadSession() {
  let raw
  try {
    raw = localStorage.getItem(KEY)
  } catch {
    return null
  }
  if (!raw) return null

  try {
    const saved = JSON.parse(raw)
    if (saved?.version !== VERSION) return null
    return saved.state ?? null
  } catch {
    // A truncated or hand-edited entry is not worth recovering from.
    return null
  }
}

export function saveSession(state) {
  const picked = {}
  for (const field of FIELDS) {
    if (state[field] !== undefined) picked[field] = state[field]
  }

  let payload = JSON.stringify({ version: VERSION, state: picked })

  // The batch is both the largest thing here and the cheapest to get back —
  // one click re-runs it — so it is what gets dropped when the two compete.
  // Losing the single-product record instead would discard the more considered
  // piece of work to keep the more disposable one.
  if (payload.length > LIMIT) {
    delete picked.batch
    delete picked.selectedRow
    payload = JSON.stringify({ version: VERSION, state: picked })
    if (payload.length > LIMIT) return false
  }

  try {
    localStorage.setItem(KEY, payload)
    return true
  } catch {
    return false
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* nothing to clean up if the store was never reachable */
  }
}

// True when there is something on screen worth telling the visitor was
// restored. A tab choice alone is not — announcing "restored" over an empty
// form is noise, and it would appear on a first visit that only touched a tab.
export function hasContent(state) {
  return Boolean(state && (state.result || state.batch || state.discovery))
}
