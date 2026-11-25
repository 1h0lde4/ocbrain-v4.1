# C-b design-validation prototypes (NOT production code)

Stdlib-only toys used as **algorithm evidence** for the `GraphExecutionWatchdog` stop()/supervision design. They are not repository code,
not the C-b implementation, and are never production or integration evidence. No toy has been run against the real watchdog.

| File | Purpose |
|---|---|
| `toy_v24.py` | v2.3 defects (IDLE local-assignment bug; caller cancellation bypassing escalation) vs the v2.4 timer-driven contract (B2); abandoned-child lifecycle. Contains the **known v2.4 defects** F-01/F-02/F-03, annotated with `NOTE` comments. |
| `clock_probe.py` | the early-timer defect (clock resolution emulated by patching the loop's private `_clock_resolution`) and the Model-A tolerance fix |

**Lost in a sandbox reset (not preserved):** the earlier toys `toy.py`, `toy_v2.py`, `toy_v21.py`, `toy_v22.py`, `toy_v221.py`, `review_probe.py`, `demo_extra.py`.
Their findings are summarised in `handoff.md` section 13 and in `C-B_DESIGN_V2.4.md`; reproduce them by re-implementing from those descriptions if needed.
Run: `python <file>` with CPython 3.11 and 3.12 (`PYTHONASYNCIODEBUG=1 python -W error <file>` for the debug leg).
The versions here were re-typed after the reset from the authoring record and sanity-run on one interpreter only (see handoff section 13).
