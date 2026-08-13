/* Session persistence — the guarantees, not the plumbing.
 *
 *   cd frontend && node test_session.mjs
 *
 * No framework and no dependency on purpose: the project has no JS test runner,
 * and adding one to protect ninety lines would cost more than it defends. Costs
 * $0 and touches no network.
 */

let checks = 0
let failures = 0

function check(label, condition) {
  checks += 1
  if (!condition) {
    failures += 1
    console.log(`  FAIL  ${label}`)
  } else {
    console.log(`  ok    ${label}`)
  }
}

// A localStorage that behaves like the real one, including throwing when full —
// which is the case the save path exists to survive.
function installStorage({ quota = Infinity } = {}) {
  const map = new Map()
  globalThis.localStorage = {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => {
      if (v.length > quota) {
        const err = new Error('QuotaExceededError')
        err.name = 'QuotaExceededError'
        throw err
      }
      map.set(k, v)
    },
    removeItem: (k) => map.delete(k),
    get length() { return map.size },
  }
  return map
}

installStorage()
const { loadSession, saveSession, clearSession, hasContent } =
  await import('./src/session.js')

console.log('\nSESSION PERSISTENCE\n')

// [1] The key must never reach disk. The field promises "never stored" and a
// shared machine makes that promise load-bearing.
installStorage()
saveSession({
  tab: 'single', mode: 'live', form: { mpn: '6205-2RS' }, specs: [],
  apiKey: 'sk-ant-api03-CANARY', result: { readiness: { overall: 93 } },
})
const raw = localStorage.getItem('pi-session')
check('[1] the API key is not written to storage', !raw.includes('CANARY'))
check('[1] no sk-ant fragment survives anywhere in the payload', !/sk-ant/.test(raw))

// [2] A round trip returns the same screen.
const back = loadSession()
check('[2] the result comes back', back.result.readiness.overall === 93)
check('[2] the engine choice comes back', back.mode === 'live')
check('[2] the key is absent on the way back too', back.apiKey === undefined)

// [3] A payload written by older code must not be rehydrated into components
// that no longer understand its shape.
installStorage()
localStorage.setItem('pi-session', JSON.stringify({ version: 0, state: { result: {} } }))
check('[3] a stale version is dropped, not restored', loadSession() === null)

installStorage()
localStorage.setItem('pi-session', '{"version":2,"state":{"result"')
check('[3] a truncated entry degrades to no session', loadSession() === null)

// [4] When the two compete, the batch is what gets dropped: it is the largest
// thing here and the cheapest to get back.
installStorage()
const bigBatch = { results: Array.from({ length: 400 }, (_, i) => ({ i, blob: 'x'.repeat(3000) })) }
saveSession({ tab: 'batch', result: { readiness: { overall: 93 } }, batch: bigBatch })
const trimmed = loadSession()
check('[4] the oversized batch is dropped', trimmed !== null && trimmed.batch === undefined)
check('[4] the single-product record is kept', trimmed?.result?.readiness?.overall === 93)

// [5] A store that throws is not an error anyone should see.
installStorage({ quota: 10 })
let threw = false
try { saveSession({ result: { readiness: { overall: 93 } } }) } catch { threw = true }
check('[5] a full quota does not throw', !threw)
check('[5] and reports that it did not save', saveSession({ result: {} }) === false)

installStorage()
delete globalThis.localStorage.getItem
globalThis.localStorage.getItem = () => { throw new Error('disabled') }
check('[5] an unreadable store loads as no session', loadSession() === null)

// [6] "Restored" is only worth announcing when something was.
installStorage()
check('[6] a tab choice alone is not a restored session', hasContent({ tab: 'batch' }) === false)
check('[6] null is not a restored session', hasContent(null) === false)
check('[6] a result is', hasContent({ result: {} }) === true)
check('[6] so is a discovery run that found nothing', hasContent({ discovery: {} }) === true)

// [7] Start fresh actually removes it.
installStorage()
saveSession({ result: { readiness: { overall: 93 } } })
clearSession()
check('[7] clearSession leaves nothing behind', loadSession() === null)

console.log(`\n${checks - failures}/${checks} checks passed`)
process.exit(failures ? 1 : 0)
