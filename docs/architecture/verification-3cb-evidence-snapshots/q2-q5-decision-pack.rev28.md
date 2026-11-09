# Verification 3C-B: Q2 and Q5 decision pack

Prepared 2026-10-16. Analysis only.

**Status.** Nothing in this pack is an accepted decision. No code, enum, placeholder or contract is authorized. 3C-B stays design-blocked. D1–D10 and ODI-3C-B-01/02/03 are not changed. Integration of the Verification branch (the two unpublished docs commits and the divergence from `main`) is a separate problem and is not touched here.

**Revision 2 (2026-10-16).** After a review of the first version: lifecycle FAILED is now framed as attempt-scoped, not "run-owned"; the attempt/run relationship is a new open decision (Q2-g); the cause vocabulary is separated from the cause record (Q2-h); D6's queryable non-conclusion is stated as a hard constraint on Q4; and Q5 counts verification targets, not retry attempts. Everything remains a candidate; nothing is accepted. Correction from the Q4 brief: the phrase “independently typed and queryable” attributed to D6 in this pack is the pre-ratification wording, not the tracker's, so read “D6's queryable non-conclusion” below with that caveat; and the retry examples assume the later conclusion governs the target, which no source establishes.

**Evidence basis.** `core/verification/` is unchanged since `fe338ed` (checked at `dbdfcb7`); frozen architecture v1, v2 and v3; the Phase C tracker (§10 and §10.6); the master prompt §0–§117 as supplied by the user (its file-level hash match with the earlier-session file is user-reported, not computed by any session).

**Labels.** **\[S\]** source text checked directly. **\[C\]** code checked directly. **\[I\]** interpretation, not ratified. **\[K\]** candidate design, not accepted. **\[D\]** decision required from the owner.

---

## 1. Constraints already in force

- **D2.** FAILED is a process/outcome *result status*, never a `VerificationVerdict` member, and is never silently mapped to CONTRADICTED, UNSUPPORTED, CONDITIONAL or UNVERIFIABLE.
- **D6.** A crash is recorded on two independent axes, kept distinguishable: lifecycle/execution FAILED and the epistemic result UNVERIFIABLE (the tracker's wording). The pre-ratification proposal added “independently typed and queryable”; which wording is ratified is open (Q4-a in the Q4 brief).
- **D7.** A not-assessable execution is never forced into semantic FAILED (master §42: uncertainty must never become falsity). It yields no semantic binary conclusion plus UNVERIFIABLE, INSUFFICIENT\_EVIDENCE or ESCALATE as appropriate.
- **D9.** `failure_control` is a field on the process/outcome result, derived from the evidence/finding chain. Its derivation rule, cause vocabulary and reference shape are unresolved.
- **D10.** `CoverageResult` is a sibling of `ProcessVerificationResult` and `OutcomeVerificationResult`; all feed `VerificationResult`.
- **ODI-3C-B-02 / 03.** Do not put lifecycle FAILED on `CriterionResult` or `VerificationResult` merely because they carry `execution_failure`; the two FAILED concepts need distinct, namespaced types (D-17 precedent).
- **3B.** The five coverage types are independent. No container, aggregate, minimum, average or "overall" coverage. `fraction=None` means unknown. `scope` is required. `VerificationAssurance.coverage` is unchanged with no implied equivalence.
- **No invented vocabulary.** Gap-filling is labeled IMPLEMENTATION JUDGMENT. Anything below that goes beyond source vocabulary is marked \[K\].

---

## 2. Q2: where lifecycle FAILED lives

### 2.1 The real question

What exactly has failed, and what can the system truthfully conclude?

| Situation | What failed | What the system knows | Conclusion allowed |
| --- | --- | --- | --- |
| An attempt times out before concluding | The execution attempt | Nothing new about the claim | No semantic conclusion; a non-conclusion with the cause (TIMEOUT). Never CONTRADICTED. |
| Evidence contradicts the claim | Nothing | The claim is contradicted | CONTRADICTED verdict |
| Evidence is inadequate | Nothing operationally | The claim is not assessable from the evidence | INSUFFICIENT\_EVIDENCE or UNVERIFIABLE with reasons (master §85, §86) |
| Attempt 1 times out, attempt 2 verifies | Attempt 1 | Attempt 2 produced its own VERIFIED result | Attempt 2's own result is VERIFIED; which conclusion governs the target is not established. Attempt 1's failure still on the record |

Treating all four as FAILED collapses operational reliability into epistemic judgment. D6 and D7 already forbid that; the open part is *which contract owns the operational fact*.

**Three concepts share the word FAILED.** Keeping them apart is the point of D2, D6 and ODI-3C-B-02/03.

| Concept | What it answers | What it must not imply |
| --- | --- | --- |
| Attempt lifecycle FAILED | Did this execution attempt fail? | That the claim is false, or that the whole logical verification cannot recover |
| Process/outcome result status FAILED (D2) | What status does the process/outcome result report? | That it is the record of an attempt's lifecycle |
| Epistemic verdict or non-conclusion | What does the evidence establish? | That operational failure proves a substantive conclusion |

Terms used below: a *logical verification* is the thing requested; an *attempt* is one execution try; *run* and *step* are the durable records named in §68. §68 does not say a run holds exactly one attempt, so the attempt/run relationship is an open decision (Q2-g). A run-level terminal state, if one is ever needed, must be defined explicitly and not borrowed from attempt-level FAILED.

### 2.2 Source evidence

- **\[S\] Master §66**, titled "Verification Result Lifecycle", lists 15 states: REQUESTED, IN\_PROGRESS, VERIFIED, PARTIALLY\_VERIFIED, CONTRADICTED, UNSUPPORTED, INSUFFICIENT\_EVIDENCE, UNVERIFIABLE, ESCALATED, INVALIDATED, SUPERSEDED, EXPIRED, REQUIRES\_REVERIFICATION, CANCELLED, FAILED. It says to "define canonical lifecycle semantics" and that cancellation or failure must never silently become PASS. The list mixes verdict-named and lifecycle states.
- **\[S\] Master §42** verdict list has no FAILED, and separates truth, verification and decision status.
- **\[S\] Master §68** gives `VerificationRun` and `VerificationStep` the durable operations checkpoint, resume, retry, timeout and cancel, and says to reuse OCBrain's existing durable mechanisms. §67 requires tolerance of retries: idempotency, duplicate-receipt prevention, crash recovery, deterministic result identity where possible. §64 requires isolation by task, execution, attempt, step and worker.
- **\[S\] Master §74 and v2 §31** list or restore `verification.failed` as a lifecycle event, without defining a state.
- **\[S\] Master §104-J and §93:** a silent verifier crash is expected to be "FAILED / UNVERIFIABLE", never PASS.
- **\[S\] v1 §11** has no FAILED state and its terminal states reuse verdict names. v2 §7 says the state machine is unchanged (its pointer to §17 for events is stale; events are in §31).
- **\[S\] v2 §30:** Runtime owns the execution lifecycle; Verification owns the verification semantic lifecycle.
- **\[S\] v2 §40:** the original result is immutable and a new evaluation produces a new run or version (stated for escalation and supersession, not for retry after execution failure).

**Runtime precedent \[S\].** In the reconciliation report (§6), `WorkflowRuntime.resume()` is described as resetting interrupted or failed nodes to PENDING. Correction (2026-10-19): the code on main resets only RUNNING and CANCELLED nodes, while COMPLETED and FAILED nodes are skipped and their cached results reused, so FAILED is terminal and cached there. It is not a precedent for a non-terminal FAILED, and it is not a ruling on the verification model.

### 2.3 Existing contracts

- **\[C\]** `VerificationResult.execution_failure` and `CriterionResult.execution_failure` use the cause enum `VerificationExecutionFailure` (TIMEOUT, TOOL\_FAILURE, VERIFIER\_CRASH, BUDGET\_EXHAUSTED). A declared execution failure is accepted only with ATTEMPTED and UNVERIFIABLE (tracker rule 7, an implementation judgment, open, to be revisited when FAILED is reconciled).
- **\[C\]** `MethodExecutionState.EXECUTION_FAILED` exists at method level.
- **\[C\]** `AttemptId` is a bare `NewType` with no documented meaning; `VerificationResult` carries optional `execution_id` and `attempt_id`. **\[I\]** By master §64 and DEBT-015 these identify the OCBrain execution being verified, not a verification retry. DEBT-015 (execution identity) is still open.
- **\[C\]** There is no lifecycle type in `core/verification/`; `VerificationRun` and `VerificationStep` are unbuilt.
- **\[S\]** The Runtime's `WorkflowRuntime` has node-boundary checkpointing and `resume()` but no hook API, persistent node cache, replay or partial execution (reconciliation report §6).

### 2.4 Options

| Criterion | A. Result lifecycle owns FAILED (§66 literal) | B. Attempt/run/step model records FAILED (§68) | C. Both, with a stated relation |
| --- | --- | --- | --- |
| Source support | §66 names FAILED in the result lifecycle | §68 gives the run the operational verbs; `verification.failed` is a lifecycle event | Both passages are honored |
| D2 / D6 / D7 | Compatible if kept off the verdict | Compatible; keeps the operational fact off the result | Compatible |
| No silent PASS | Yes, if FAILED is terminal | Yes, a failed run has no PASS | Yes |
| Retry history | Weak: a retry would need a new result per attempt or an overwrite | Strong: each attempt is its own record | Strong |
| Relation to existing `execution_failure` fields | Overlaps them: two records of one failure | Must be stated | Must be stated, but it is explicit by construction |
| Identity | Needs a result identity per attempt | Needs a run/attempt identity distinct from `attempt_id` | Both |
| Build footprint | Small now; large later when runs exist | Needs `VerificationRun`/`VerificationStep` first | Largest, but staged |
| Main gap | §66 mixes axes, so it cannot be built as written | §68 lists no states and never names FAILED | Whether the sources intend layers is not stated |

### 2.5 Recommended direction \[K, not accepted\]

**Option C with attempt-scoped FAILED.** This revises the first version of this pack, which said "run-owned": a run may hold several attempts (section 2.1), so FAILED is attributed to the attempt and the run's own terminal semantics stay open.

1. **FAILED describes an execution attempt, not a durable result.** A candidate partition of §66's 15 states, using only source vocabulary \[K\]:
   - Operational (carrier unresolved: attempt, run or step): REQUESTED, IN\_PROGRESS, FAILED, CANCELLED. FAILED is attempt-scoped; it is not established that the other three share its owner.
   - Result (assessment): VERIFIED, PARTIALLY\_VERIFIED, CONTRADICTED, UNSUPPORTED, INSUFFICIENT\_EVIDENCE, UNVERIFIABLE.
   - Result validity (after the fact): INVALIDATED, SUPERSEDED, EXPIRED, REQUIRES\_REVERIFICATION.
   - ESCALATED is ambiguous: it could be a result outcome or a run outcome. Unresolved.
2. **Invariants** \[K\], all traceable to §66, §93, §104-J, D6 and D7:
   - A FAILED attempt never yields a PASS-like verdict by itself, and a CANCELLED run never does; a later attempt may legitimately verify the claim.
   - An execution failure never becomes a semantic conclusion.
   - A retry never overwrites an earlier attempt; every attempt keeps its own record, and a later result links to the earlier failed attempts.
   - Results are immutable (v2 §40 extended from escalation and supersession to retries, which the frozen text does not state).
3. **Relation to the built fields** \[K\]. Keep `VerificationExecutionFailure` as the single cause vocabulary. An attempt record that carries a cause uses this vocabulary and does not redefine it. This fixes the vocabulary only: whether a failure occurrence has one authoritative record that results reference, or duplicated cause values, is open (Q2-h). The existing rule that a declared failure rides only on ATTEMPTED/UNVERIFIABLE stays until D6's reopen point, which is exactly this reconciliation.
4. **Retry identity** \[K\]. Each verification attempt needs its own identity, distinct from the execution `attempt_id` that DEBT-015 governs. The name is Q3's decision.
5. **Events** \[K\]. `verification.failed` is emitted when an attempt fails, correlated to its run and step, not when a verdict is recorded. Whether a run-level terminal failure needs its own event is open. The event contracts are unbuilt.
6. **Runtime boundary.** Reuse the Runtime's durable mechanisms (§68) and do not duplicate its execution lifecycle (v2 §30).

### 2.6 Worked examples

**Crash with the built fields.** A verifier crashes while checking criterion C. Built: `CriterionResult` is ATTEMPTED, UNVERIFIABLE, `execution_failure=VERIFIER_CRASH`. Under the recommended direction the failed attempt is also recorded as FAILED with the same cause. Whether the attempt record references one authoritative failure record or holds its own copy of the cause value is open (Q2-h); matching enum labels alone would not make the link traceable.

**Retry.** One logical verification, two attempts. Attempt 1 times out: that attempt is FAILED with cause TIMEOUT and yields no semantic conclusion. Whether the enclosing run stays active for the retry or a new run starts is open (Q2-g). A subsequent attempt may produce a conclusion, but the available sources do not establish whether, or under what rule, that conclusion becomes authoritative for the original target. The example therefore establishes only that the subsequent attempt can have its own result; it does not establish target-level result selection, supersession or overwrite semantics. A later query, "why did this take two tries?", is answerable from the records if the earlier attempt's record is retained; whether it must be retained is not established (Q2-d, Q4-f).

**No result object.** If a failed execution emits no result object, D6's epistemic non-conclusion (UNVERIFIABLE) must still be queryable, as a full result, another durable representation or a defined projection (the sources do not say which), and a consumer must still be able to tell "failed" from "never requested" without the run record. Q2 decides what FAILED means; Q4 decides how the non-conclusion is represented and exposed.

### 2.7 Decisions required \[D\]

- **Q2-a.** Does lifecycle FAILED describe an execution attempt or a durable result object?
- **Q2-b.** Does the candidate partition of §66's 15 states hold, and where does ESCALATED sit?
- **Q2-c.** Is `VerificationExecutionFailure` the single cause vocabulary, referenced by runs and steps?
- **Q2-d.** What identity do verification attempts get, and what are the retry-history and immutability rules?
- **Q2-e.** Does a failed execution emit a result object, and if not, how does D6's queryable non-conclusion stay exposed (Q4)?
- **Q2-f.** Where is `verification.failed` emitted, and what correlation metadata does it carry?
- **Q2-g.** How does an attempt relate to a run: one attempt per run, or several attempts in one run? If several, is run-level failure non-terminal while retries remain, or does a retry start a new run? What terminal state does a run have when recovery is exhausted? (§68 names retry on the run and step without fixing the relation; the Runtime's `resume()` skips FAILED nodes and reuses their cached results; corrected 2026-10-19).)
- **Q2-h.** For one failure occurrence, is there one authoritative record that attempts and results reference, duplicated cause values, or fields with deliberately different meanings? One cause vocabulary does not give one stored record, and the failure-to-result link must stay traceable (it matters for Q6).

**Q2-a candidate disposition \[K, not accepted\].** Lifecycle FAILED describes the operational failure of one verification execution attempt, not the lifecycle of a durable verification result. The attempt and its failure stay durably traceable through the run/step model, with identity and ownership resolved under Q2-d. A logical run is not assumed to hold exactly one attempt: failure of one attempt does not by itself make the enclosing run terminally failed, and any run-level terminal state needs its own definition (Q2-g). This does not remove the distinct process/outcome result status FAILED retained by D2. Lifecycle failure, process/outcome result status and epistemic conclusion stay independently typed and queryable, and operational failure is never a substantive verdict. Not settled: the carrier contract for a failed attempt, cause-record ownership (Q2-h), retry identity, event correlation, and whether a failed execution emits a full result object (Q4), which must still preserve D6's queryable non-conclusion. Cost of this reading: it departs from the literal title of §66 (Verification Result Lifecycle) by treating FAILED as an attempt state, and it requires splitting §66's list.

---

## 3. Q5: the canonical `CoverageResult`

### 3.1 Four separate questions

The single question "per-verdict breakdown or status?" hides four:

1. **Coverage domain.** Which entities or obligations are counted?
2. **Measurement.** What is the denominator, and what counts as covered, assessed or unverified?
3. **Breakdown.** Which dispositions are counted, and how do they reconcile?
4. **Summary status.** Is a derived status needed, and by what explicit rule?

A fraction alone cannot show whether a low figure comes from missing, contradictory or incomplete evidence. A status alone cannot preserve a distribution.

### 3.2 Source evidence

- **\[S\] Master §24** tracks requirement, obligation, criterion, claim and evidence coverage, and says a breakdown such as "10 obligations: 7 verified, 1 contradicted, 1 unsupported, 1 unverified" must stay explicit and not collapse into one confidence number.
- **\[S\] Frozen v2 §13** says coverage is five separate fields, `TaskCoverage`, `VerificationCoverage`, `CriterionCoverage`, `EvidenceCoverage` and `ObservationCoverage`, which coexist independently, so `TaskCoverage=100%` with `VerificationCoverage=40%` must be representable.
- **\[S\]** Only Criterion and Evidence appear in both lists.
- **\[S\] Master §99** shows COVERAGE VERIFY beside PROCESS VERIFY and OUTCOME VERIFY (consistent with D10). §59 lists coverage in the receipt. §46 defines deterministic aggregation, criterion results to rubric, obligation, target and task results, and says a model must not improvise it.
- **\[S\]** `CoverageResult` appears in v1's contract list and in master §100 with no fields. No source defines a status vocabulary for it.

### 3.3 Existing contracts

- **\[C\]** The five coverage types follow v2 §13. Each holds only `fraction: Optional[float]` in \[0,1\] and `scope: str`. They provide no container, aggregate, minimum, average or overall value.
- **\[C\]** `CriterionResult` already carries `attempt_state` (NOT\_ATTEMPTED, BLOCKED, ATTEMPTED) and, when attempted, a `VerificationVerdict`. It stores what a later layer produced and must not aggregate.
- **\[C\]** Four observation-absence states exist (NOT\_OBSERVED, OBSERVED\_ABSENT, OBSERVATION\_INCOMPLETE, OBSERVATION\_COVERAGE\_UNKNOWN).
- **\[I\]** The built types cannot express a per-verdict distribution. That follows from the 3B design and is not a defect.

### 3.4 Decision A: the coverage ontology

| Option | What it means | Cost or risk |
| --- | --- | --- |
| A1. Adopt §24's five | Coverage over requirement, obligation, criterion, claim and evidence populations | Requirement has no built type; replaces the built v2 types |
| A2. Keep v2 §13's five | Coverage quantities as built: task, verification, criterion, evidence, observation | §24's population breakdown has no home |
| A3. Layered | v2 §13's fractions stay as coverage quantities, and `CoverageResult` carries §24-style breakdowns over named populations | Needs a stated relation between the two; the sources do not say whether they are layers or alternatives |

### 3.5 Decision B: measurement rules to define \[D\]

- The **population** behind each dimension and what makes an item a member.
- The **classification** of each member into a disposition. \[K\] Use existing vocabularies, `CriterionResult.attempt_state` combined with `VerificationVerdict`, and do not collapse §24's four illustrative buckets into new categories.
- **Unknown denominators.** They must stay representable; `fraction=None` is unknown, never zero.
- **Invalidated or superseded items.** Whether they stay in the population.
- **Failed attempts (Q2) and non-conclusions (Q4).** Coverage counts verification targets (the population members), not retry attempts: a target verified on its second attempt counts once, as verified. Attempt-level failures belong to execution-reliability telemetry, not to the coverage breakdown. How a target whose retries are exhausted without a result is represented depends on Q4.

**Different units answer different questions.**

| Measurement | Correct unit |
| --- | --- |
| Verification coverage | The defined verification population |
| Per-disposition breakdown | Each member of that population, classified under the accepted measurement rules |
| Execution reliability | Verification attempts and their operational outcomes |
| Retry history | Individual attempts linked to the logical verification |

Mixing these units would make coverage depend on how many retries ran: two identical final assessments would show different coverage because one needed more attempts. This follows from §24's example, which counts population members (obligations), not attempts \[I\].

### 3.6 Decision C: representation

| Option | Preserves a distribution | Preserves unknown | Risk |
| --- | --- | --- | --- |
| R1. Status only | No | Only by convention | Hides why coverage is low |
| R2. Fraction and scope only (as built) | No | Yes | Same fraction can hide very different profiles |
| R3. Per-disposition counts over a stated population, with population size and scope | Yes | Yes | Needs the Decision B rules first |
| R4. R3 plus a derived summary status | Yes | Yes | A summary can become the "overall" coverage that 3B refused |

### 3.7 Recommended direction \[K, not accepted\]

1. Decide the ontology (A) first, then the measurement rules (B), then the representation (C).
2. Prefer **R3** as the base. Dispositions are keyed by existing vocabularies. Population size and scope are explicit, and unknown stays representable.
3. **Do not adopt a summary status now.** If one is adopted later, it must be separate, derived by a documented rule, never replace the counts, and be tested so it cannot be consumed as "overall coverage".
4. Keep the built v2 §13 types as they are until Decision A is accepted. No code change follows from this pack.

### 3.8 Worked examples

**§24's illustration.** 10 obligations: 7 verified, 1 contradicted, 1 unsupported, 1 unverified. R3 keeps this explicit. R2 would only say 0.7.

**Same fraction, different profile.** Evaluation X: 6 of 10 verified and 4 never attempted. Evaluation Y: 6 of 10 verified and 4 contradicted. A fraction or a status treats them alike; R3 does not.

**Unknown denominator.** Verification stopped before the population was enumerated. R3 reports the population as unknown, not 0 of N.

**v2's guard.** `TaskCoverage=1.0` with `VerificationCoverage=0.4` stays representable because each dimension keeps its own population and scope.

### 3.9 Decisions required \[D\]

- **Q5-a.** Which five dimensions are canonical, or what is the stated relation between §24's and v2 §13's lists?
- **Q5-b.** What are the populations, the classification rules and the denominators?
- **Q5-c.** Does `CoverageResult` use a per-disposition breakdown, a status, or both as distinct concepts?
- **Q5-d.** If a summary status is ever adopted, by what explicit rule, and how does it relate to 3B's refusal of an "overall" metric?
- **Q5-e.** How are non-conclusions (Q4) counted in the breakdown, given that coverage counts targets and attempt failures are counted separately as execution telemetry?

---

## 4. Dependencies across Q1–Q6

| Question | Depends on | Constrains | Can it stand alone? |
| --- | --- | --- | --- |
| **Q1** how a `CriterionResult` gets process/outcome scope | Q4 (no-finding results); Q6 (evidence chain) | Q5 (per-dimension populations) | Partly: the derive-from-findings choice is independent, the no-finding and mixed cases are not |
| **Q2** where FAILED lives | DEBT-015 identity; Runtime boundary; attempt/run relationship (Q2-g) | Q3, Q4, Q6 | Yes, and it should go first |
| **Q3** type and value names | Q2, Q4 | Nothing else | No, it should come last (D-17 namespacing precedent) |
| **Q4** representation of "no conclusion" | Q2 (does a failed execution emit a result; D6 requires a queryable non-conclusion either way) | Q5, Q6 | No |
| **Q5** `CoverageResult` | Q4 for how non-conclusions are counted; Q2 only for the target-versus-attempt distinction | Receipt contents | The ontology (A) can stand alone; B and C cannot |
| **Q6** `failure_control` | Q1, Q2 (cause vocabulary), Q4 | Q3 | No |

**Recommended resolution order \[K\]:** Q2, then Q4, then Q5 (A, then B, then C), then Q1, then Q6, then Q3.

---

## 5. Boundaries

- No implementation. 3C-B stays design-blocked until these questions have explicit dispositions.
- A recommendation is not an accepted decision. Each question needs an explicit disposition, its supporting evidence and the consequences of choosing it.
- The tracker records a decision only after it is accepted.
- Branch integration (publishing, rebasing or merging the Verification branch) is a separate task and is not authorized by this pack.
- This pack was not committed to the repository.

## 6. What was not verified

- The original 3C-A brief, the numbered claim C3 and the verbatim S13 row.
- Sections of the "Parallel Implementation Mission" prompt past §13.
- The file-level hash match of the master prompt (user-reported, not computed here).
- Code-level names beyond those cited above; the `WorkflowRuntime` description comes from a static read.
- DEBT-015's content beyond what the 2026-10-09 reconciliation recorded.
