"""Proof that the cost guarantees hold. Makes no API calls and costs nothing.

Verifies the two things that failed last time:
  1. A second concurrent run refuses to start (the actual cause of the overspend).
  2. The spend ceiling aborts mid-run, not after, and completed work is cached.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from app.models import Attribute, CommerceContent, RawProduct
from app.providers.base import InferenceResult, Provider
from benchmark.corpus import build_corpus
from benchmark.evaluate import BudgetExceeded, evaluate
from run_benchmark import LOCK, RunLock, cost_usd

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}: {message}")
    if not condition:
        FAILURES.append(message)


class ExpensiveProvider(Provider):
    """Stands in for the real API and reports a large, fixed token spend."""

    name = "live"

    def __init__(self, per_call_input: int = 200_000, per_call_output: int = 200_000):
        self._usage = {"input_tokens": per_call_input, "output_tokens": per_call_output}

    def infer_attributes(self, raw, category, known) -> InferenceResult:
        return InferenceResult(attributes=[])

    def generate_content(self, raw, category, attributes, identity) -> InferenceResult:
        return InferenceResult(content=CommerceContent(
            title="x", short_description="x", long_description="x"))


def test_lock_blocks_concurrent_run() -> None:
    print("\n[1] A second run must refuse to start while one holds the lock")

    # Hold the lock with a PID that is genuinely alive for the whole check.
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(25)"])
    try:
        LOCK.write_text(f"{holder.pid}|{time.time()}", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "run_benchmark.py"],
            capture_output=True, text=True, timeout=90,
        )
        combined = result.stdout + result.stderr
        check("REFUSING TO START" in combined,
              "second run refused while the first is alive")
        check(result.returncode != 0, "refusal exits non-zero")
    finally:
        holder.kill()
        holder.wait()
        LOCK.unlink(missing_ok=True)


def test_stale_lock_is_cleared() -> None:
    print("\n[2] A lock left by a killed run must not block forever")
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    LOCK.write_text(f"{dead.pid}|{time.time()}", encoding="utf-8")
    try:
        with RunLock():
            check(True, "stale lock cleared and run allowed to proceed")
    except SystemExit:
        check(False, "stale lock wrongly blocked a new run")
    finally:
        LOCK.unlink(missing_ok=True)


def test_ceiling_aborts_mid_run() -> None:
    print("\n[3] The spend ceiling must abort DURING the run, not after")
    cases = build_corpus()
    cap = 5.00
    providers: list[ExpensiveProvider] = []

    def factory() -> ExpensiveProvider:
        p = ExpensiveProvider()
        providers.append(p)
        return p

    def spent() -> float:
        return cost_usd(
            sum(p._usage["input_tokens"] for p in providers),
            sum(p._usage["output_tokens"] for p in providers),
        )

    def guard(completed: int) -> None:
        if spent() > cap:
            raise BudgetExceeded(spent(), cap, completed, len(cases))

    # Each simulated case costs 200k in + 200k out = $0.40 + $2.00 = $2.40,
    # so the ceiling must trip on the third case, not at the end of 102.
    try:
        evaluate(cases, factory, label="test", mode="test-never-cached",
                 use_cache=False, spend_guard=guard)
        check(False, "ceiling did not abort at all")
    except BudgetExceeded as exc:
        check(exc.completed < 5,
              f"aborted after {exc.completed} cases, not all {len(cases)}")
        check(exc.spent <= cap + 2.40,
              f"stopped at ${exc.spent:.2f}, within one case of the ${cap:.2f} cap")
        overshoot = exc.spent - cap
        print(f"       stopped at ${exc.spent:.2f} (cap ${cap:.2f}, "
              f"overshoot ${overshoot:.2f} = at most one case)")


def test_cache_makes_reruns_free() -> None:
    print("\n[4] A completed case must never be paid for twice")
    from app import cache

    cases = build_corpus()[:3]
    calls = {"n": 0}

    class CountingProvider(ExpensiveProvider):
        def infer_attributes(self, raw, category, known):
            calls["n"] += 1
            return super().infer_attributes(raw, category, known)

    mode = f"cachetest-{os.getpid()}"
    evaluate(cases, CountingProvider, label="a", mode=mode, use_cache=True)
    first = calls["n"]
    evaluate(cases, CountingProvider, label="b", mode=mode, use_cache=True)
    second = calls["n"] - first

    check(first > 0, f"first pass made {first} provider call(s)")
    check(second == 0, f"second pass made {second} provider calls (must be 0)")

    for case in cases:  # leave no test entries behind
        cache.put(dict(case.product), mode, {})


def main() -> int:
    print("=" * 62)
    print("  COST GUARANTEE TESTS - no API calls, $0.00")
    print("=" * 62)

    test_lock_blocks_concurrent_run()
    test_stale_lock_is_cleared()
    test_ceiling_aborts_mid_run()
    test_cache_makes_reruns_free()

    print("\n" + "=" * 62)
    if FAILURES:
        print(f"{len(FAILURES)} GUARANTEE(S) NOT MET:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL COST GUARANTEES HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
