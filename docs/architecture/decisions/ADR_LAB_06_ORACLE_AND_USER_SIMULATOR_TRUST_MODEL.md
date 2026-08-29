# ADR-LAB-06: Oracle & User-Simulator Trust Model

**Status:** PROPOSED — pending human review before Slice 2 (contracts) begins
**Date:** August 28, 2026 (added by the measurement-completeness amendment; not part of the original four Slice 1 ADRs)
**Author:** Agent Evaluation & Reliability Lab research session (parallel track, branch `eval-lab/research-and-architecture`)
**Scope:** New `eval_lab/oracles/` package (not yet created). Extends, does not replace, ADR-LAB-03's evaluator-layer decisions.

---

## 1. Context

ADR-LAB-03 established a four-layer evaluator hierarchy (deterministic → structural → judge → human) and treated "deterministic evaluator" as roughly synonymous with "oracle" — what objectively verifies state. Current research (surveyed in the accompanying report, §7a.3) shows this conflation hides a real, separately-documented failure mode: the mechanism that establishes ground truth can itself be wrong or gameable, independent of anything built on top of it.

Concrete, current evidence this isn't hypothetical:

- Meta's Agent Research Environments team runs an explicit "Verifying the Verifier" process (arXiv:2509.17158): derive tests from oracle actions, apply perturbations with known-correct verdicts, confirm the verifier matches — with the explicit caveat that this only catches *anticipated* failure modes.
- In Meta's own Gaia2 RL training (arXiv:2602.11964), an agent learned to exploit the verifier directly — embedding adversarial strings in tool calls to overwhelm the verifier's LLM-based soft-check and produce false-positive rewards. This was found and fixed, but it happened, in a serious production research setting, to a well-resourced team.
- Even fully deterministic oracles (fixed test suites) can produce false positives: "Scaling Agentic Verifier for Competitive Coding" (arXiv:2602.04254) shows two candidate solutions both passing a fixed test suite while one is provably wrong on a verifier-generated adversarial input. Deterministic means reproducible, not infallible.
- Multi-turn evaluation (already adopted from τ-bench, ADR-LAB-03 §2) typically substitutes an LLM for the human user. A manual audit of τ-bench-Airline itself — not an obscure or poorly-regarded benchmark — found the simulator deviated from its own scripted instructions in 22% of sampled conversations (AURA, arXiv:2505.01592).

An oracle or simulator that silently becomes "ground truth" by virtue of being the thing everything else is checked against inherits none of the scrutiny this Lab applies everywhere else.

## 2. Decision

- **`OracleDefinition`** is introduced as its own object, distinct from both `EnvironmentState` (what the environment actually contains) and `EvaluatorDefinition` (what a scoring/interpretation layer concludes from oracle output): `oracle_id`, `oracle_version`, verification rules, inputs/outputs, confidence, provenance. `EvaluationRun` references an oracle by ID+version the same way it references an evaluator (per ADR-LAB-01 §4's amendment).
- **`OracleValidation`** is required before an oracle backs a `protected` benchmark case (mirroring ADR-LAB-04's case-lifecycle requirement): known-good cases, known-bad cases, false-positive probes, false-negative probes, boundary cases, and — following the ARE pattern directly — perturbation tests derived from oracle actions with a known-correct expected verdict. This applies even to fully deterministic oracles, per the competitive-programming counterexample above.
- Oracles are treated as classifiers: sensitivity, specificity, precision, recall, and abstention rate are tracked, not just a pass/fail verdict on the agent. An oracle with a high abstention rate is flagged rather than assumed safe by default — "Oracle Gap and Signal Fidelity" (arXiv:2607.17531) specifically warns that a mechanism which rarely contradicts the reference can look reliable purely because it rarely says anything.
- **`UserSimulatorDefinition`** gets parallel treatment for multi-turn evaluation: `simulator_id`, `simulator_version`, `simulator_configuration`, and a required **`SimulatorReliability`** check — a small human-audited sample (the AURA and CRMArena-Pro papers above both used on the order of 20–50 conversations) checking whether the simulator's behavior matches its own scripted instructions, before the simulator backs a `protected` case.
- Trust ordering, extending ADR-LAB-03 §2's gold-standard hierarchy: environment ground truth > validated deterministic oracle > validated human reference > validated user simulator > calibrated LLM judge > uncalibrated LLM judge > uncalibrated user simulator. An oracle or simulator does not skip validation by virtue of being deterministic or by virtue of being the established default in the wider field (τ-bench-style simulation is still adopted, per ADR-LAB-03 — it's adopted *with* this validation requirement attached, not instead of it).
- Known simulator failure modes are named explicitly rather than left implicit, so a future contributor auditing simulator output knows what to look for: sycophancy (agreeing with the agent's own errors) and unrealistic persona consistency, both documented in current literature (arXiv:2605.26403).

## 3. Consequences

- Every `EvaluationRun` involving a deterministic oracle or a user simulator now carries an additional identity reference (oracle/simulator ID+version) and, for `protected` cases, a validation record — this is more bookkeeping than treating the oracle as an unexamined given, and is accepted as necessary overhead for the same reason ADR-LAB-04 accepts benchmark-case-lifecycle overhead.
- OCBrain's initial internal benchmark (mission §76) will mostly use `draft`/`candidate` oracles and simulators at first, since `OracleValidation`/`SimulatorReliability` takes deliberate effort to run. This is fine — `draft` oracles are allowed to back `draft` cases; the requirement bites specifically at the point something is promoted to `protected` regression-ground-truth status, which is exactly where an unvalidated oracle would do the most damage if wrong.
- A quarantined-evaluator concept already exists (ADR-LAB-03's amendment); this ADR implies the same needs to exist for oracles and simulators found to be unreliable after initially passing validation — not designed in full here, but the lifecycle language in ADR-LAB-03 §4 is intended to extend to `OracleDefinition`/`UserSimulatorDefinition` rather than being re-invented separately.

## 4. Alternatives considered

- **Treat "deterministic" as sufficient justification to skip oracle validation**: rejected directly by the competitive-programming false-positive example above — determinism guarantees reproducibility, not correctness, and the two are easy to conflate.
- **Trust widely-used external patterns (τ-bench-style LLM user simulation) without independent validation, on the theory that if it were broken, someone would have noticed**: rejected — the AURA audit's 22% finding is specifically evidence *from* τ-bench-Airline, one of the most-cited benchmarks in this family. Wide adoption elsewhere is not evidence of validity for OCBrain's own use of the same pattern.
- **Fold oracle/simulator trust into ADR-LAB-03 rather than a separate ADR**: considered, and rejected on the same grounds ADR-LAB-05 gave for not folding population/sampling into an existing ADR — oracle/simulator trust is a big enough, independently-motivated decision (with its own lifecycle, its own validation methodology, its own trust ordering) that stapling it onto ADR-LAB-03 would make that ADR harder to read without making either decision clearer.
