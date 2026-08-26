"""
validate_live.py — direct live validation of the K4.4 execution-budget fix.

Run from the repo root inside the codespace, once Ollama is installed and
`mistral` (or whatever model config/models.toml's [coding] section names as
bootstrap_model) has been pulled. Does not require the full 4-process app to
be running -- calls ModelRouter directly, which is what interface/api.py's
/query endpoint does under the hood.

    python validate_live.py
"""
import asyncio
import time

from core.model_router import ModelRouter


async def main():
    router = ModelRouter()

    print("=== Short request ('Hi') — must stay fast, unchanged behavior ===")
    t0 = time.monotonic()
    result = await router.route("coding", "Hi", None)
    elapsed = time.monotonic() - t0
    print(f"  answer: {result.answer[:80]!r}")
    print(f"  elapsed: {elapsed:.1f}s")
    print(f"  execution_detail: {result.execution_detail}  (should be None -- short path, unchanged)")

    print("\n=== The original bug report, verbatim ===")
    t0 = time.monotonic()
    result = await router.route(
        "coding", "write a short story of 1000 words, fantasy type", None
    )
    elapsed = time.monotonic() - t0
    print(f"  elapsed: {elapsed:.1f}s")
    print(f"  output length: {len(result.answer)} chars")

    if result.execution_detail is None:
        print("  !! execution_detail is None -- this means _estimate_long_form()")
        print("     did NOT classify the request as long-form, so it went through")
        print("     the old short path instead of the new monitored one. Worth")
        print("     checking before trusting the timing below.")
    else:
        print(f"  failure_type: {result.execution_detail.failure_type.value}")
        print(f"  watchdog_verdict: {result.execution_detail.watchdog_verdict}")
        if result.execution_detail.failure_type.value != "success":
            print(f"  retryable: {result.execution_detail.retryable}")
            print(f"  partial_output length: {len(result.execution_detail.partial_output or '')}")

    print("\n=== Before/after this fix, for reference ===")
    print("  Before: this request would hang until asyncio.wait_for's flat")
    print("  60.0s timeout, then surface as 'No response'.")
    print(f"  Just now: {elapsed:.1f}s elapsed, {len(result.answer)} chars returned.")


if __name__ == "__main__":
    asyncio.run(main())
