# ADR-CAP-03: Foundation Enablement Gate and the ADR-K4.2-H-13 Interaction

**Status:** DRAFT
**Date:** September 2026
**Author:** Capability Foundation mission ("mission 1"). Same branch and
review status as ADR-CAP-01/02 — **not reviewed, not merged.**
**Scope:** `main.py`, `config/settings.toml`,
`core/cognitive/planner.py` (discovery scoring — read, not modified by this
ADR's decision), `core/governance/orchestration_governor.py` (read only).

---

## 1. Context

ADR-K4.2-H-13 (`ADR_K4_2_H_13_GENERAL_PURPOSE_CLARIFICATION_EXEMPTION.md`,
ACCEPTED) fixed a real production bug: with only `LLM_COMPLETION`
registered, an ordinary request scores near-zero lexical overlap against
its own description (`"Generate text from a prompt via a language
model."`), and `ClarificationPolicy`'s `confidence >= 0.5` threshold
escalated almost anything. The fix: a plan whose every step's top candidate
is the general-purpose fallback (`is_general_purpose=True`) is exempt from
`ClarificationPolicy` — there is no *specific* alternative anywhere in the
plan to be genuinely uncertain among.

Registering a specific capability changes which candidate is "the top
candidate" for a step that lexically resembles it even slightly — which is
exactly what registering TEXT_GENERATION, STRUCTURED_REASONING and
FILE_READING does. This ADR is the decision this mission prompt's §33
explicitly required: verify and protect ADR-K4.2-H-13's actual behavior
before shipping anything that changes discovery's candidate set.

**Measured, not assumed** (`tests/capability_foundation/
test_discovery_and_k42.py::TestPhrasingDiversity`): with the foundation
registered, realistic phrasing (not the capabilities' own description text)
reaches its intended capability with a lexical score between roughly 0.05
and 0.11 — well above zero (so discovery *works*, mission §48's phrasing-
diversity requirement) but far below `ClarificationPolicy`'s `0.5`
threshold. Wording with no lexical overlap at all (e.g. "turn this into a
concise report") correctly still falls back to `LLM_COMPLETION` — the
matcher is unchanged (ADR-K4.2-H-04), and low-or-no overlap remains
low-or-no overlap.

**The hazard, verified end-to-end, unmocked, through the real
`Planner`/`Compiler`** (`TestGeneralPurposeExemptionProtected::
test_documented_hazard_enabling_changes_ordinary_chat_planning`): with the
foundation registered, an ordinary chat request such as "write me a haiku
about autumn" now lexically top-matches `TEXT_GENERATION` (weakly — score
well under 0.5) instead of `LLM_COMPLETION`. The plan is no longer
`general_purpose_only`. ADR-K4.2-H-13's exemption no longer applies. The
same low score that was previously exempt is now escalated by
`ClarificationPolicy`, exactly as it would have been for any request before
ADR-K4.2-H-13 shipped. **This is ADR-K4.2-H-13 working exactly as
specified — the exemption was never "low confidence is always fine", only
"low confidence against the sole general-purpose fallback is fine" — not a
bug introduced by this branch.** It is nonetheless a real behavioral
regression for ordinary chat if the foundation is enabled without further
work, and is the reason this ADR exists.

## 2. Decision

**Ship the foundation registered only behind a feature flag,
`[capabilities] foundation_enabled`, default `false`.**
`main.py` reads it as
`config.get("capabilities.foundation_enabled", False)` and gates *both*
`register_foundation_capabilities(capability_registry)` and
`register_foundation_workers(worker_registry, adapter_runtime)` on it —
nothing else in the composition root imports
`core.capabilities.foundation` (pinned by
`TestFeatureFlag::test_main_reads_the_flag_with_default_false_and_gates_
both_registrations`, which asserts on the literal source, not just observed
behavior, so a future edit that weakens the gate fails CI rather than
silently changing production behavior). Importing the foundation package
registers nothing by itself
(`test_registering_the_foundation_registers_nothing_else`,
`test_importing_the_foundation_registers_nothing`) — every effect is
explicit, at the one call site, under the one flag.

With the flag `false` (shipped default, and therefore production's actual
behavior on any merge of this branch as-is): `CapabilityRegistry` contains
only `LLM_COMPLETION`, exactly as before this branch.
`TestGeneralPurposeExemptionProtected::test_unchanged_without_the_
foundation` pins this directly. **Registering the three capabilities but
setting their lifecycle to `DISABLED` is not equivalent to the flag being
off** — a disabled-but-registered capability is invisible to *discovery*
(§ADR-CAP-02 §2.3) but is still a registered `CapabilityContract`, and this
branch does not certify that every other consumer of `CapabilityRegistry`
(present or future) treats "registered+disabled" identically to "never
registered" — pinned by `test_registered_but_disabled_capabilities_leave_
k42_untouched`, which is a narrower claim (discovery/planning is unaffected)
than "nothing is affected". The flag, not the lifecycle mechanism, is the
actual off-switch this ADR relies on.

**This ADR does not resolve the hazard — it fences it.** Turning the flag
on is a separate decision this branch does not make, gated on:

1. A decision — by whoever owns `ClarificationPolicy`/ADR-K4.2-H-13, not
   this mission — on whether the exemption should generalize (e.g. "exempt
   when a plan's low-confidence steps are uniformly weak against *every*
   candidate", rather than specifically "top candidate is the one flagged
   general-purpose") or whether registering more capabilities is simply
   expected to make more requests correctly seek clarification now that
   real alternatives exist to be uncertain among.
2. `Orchestrator.handle()` gaining an artifact-ingress path (ADR-CAP-01
   §2.6) — FILE_READING has no live caller without one, so enabling the
   flag today would register a capability discovery can find but the API
   can never actually route a file into.
3. Re-running `TestPhrasingDiversity`/`TestGeneralPurposeExemptionProtected`
   against whatever decision point 1 produces, since both are written to
   fail loudly if the interaction changes silently.

## 3. Consequences

- Merging this branch as-is changes zero observable production behavior
  (flag defaults false, nothing else references the foundation package).
- The three capabilities, their tests, and their conformance suite are
  fully exercisable in isolation and in CI (every
  `tests/capability_foundation/` test constructs its own
  `CapabilityRegistry` and registers the foundation directly — none depends
  on the flag or on `main.py`), so this branch's correctness is verifiable
  today independent of the enablement decision.
- Whoever makes the enablement decision inherits two pinned, currently-
  passing regression tests
  (`test_documented_hazard_enabling_changes_ordinary_chat_planning` and its
  siblings) that will fail the moment the interaction changes — by design,
  so the decision is forced to be a deliberate edit to those tests (and,
  implicitly, to this ADR) rather than a silent drift.
- `LLM_COMPLETION`-only behavior (today's production) has no expiry date
  tied to this branch; the flag can stay `false` indefinitely with zero
  cost, which is the intended fallback if point 1 above is never resolved.

## 4. Alternatives considered

- **Ship enabled by default, rely on the escalation being "more correct"
  clarification-seeking behavior rather than a regression** — rejected:
  this mission has no mandate to change `ClarificationPolicy`'s threshold
  or ADR-K4.2-H-13's exemption logic (mission §33 explicitly requires
  *protecting* the existing intent, not reinterpreting it), and shipping a
  user-visible behavior change to ordinary chat as a side effect of an
  unrelated capability-foundation mission is exactly the kind of
  undocumented, non-isolated change PROJECT_INSTRUCTIONS.md's engineering
  standards forbid.
- **Register the capabilities but mark them `is_general_purpose=True`** to
  avoid the interaction entirely — rejected: this is false metadata (none
  of the three is a general-purpose fallback; TEXT_GENERATION vs.
  LLM_COMPLETION would become indistinguishable to `general_purpose_only`
  logic) and would also silently widen ADR-K4.2-H-13's exemption to cover
  every request TEXT_GENERATION lexically matches, weakly or not — a worse,
  more hidden version of the same hazard.
- **Widen `ClarificationPolicy`'s threshold or special-case the three new
  capabilities inside it** — rejected as out of this mission's scope
  (mission §6: capabilities "must not absorb responsibilities belonging
  to... GovernanceKernel... general orchestration") and as a decision that
  belongs to whoever owns that governor, not to this branch.
- **A capability-count-based or registry-introspecting variant of the
  exemption** (e.g. "exempt if the plan's top candidate ties with the
  general-purpose fallback") — not designed or built; flagged in §2 point 1
  as the shape of decision needed, but making it is explicitly left to the
  ADR-K4.2-H-13 owner, consistent with the Architecture Freeze Principle
  (this mission may propose, not unilaterally re-decide, a K4.2-frozen
  governor's behavior).
