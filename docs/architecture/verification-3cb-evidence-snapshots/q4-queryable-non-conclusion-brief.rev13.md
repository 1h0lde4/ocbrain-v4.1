# Verification 3C-B: Q4 queryable non-conclusion brief

Oct 16, 2026 · @Moncif

**Status.** Analysis only; nothing here is accepted. Q2-a remains a candidate and Q2-g remains open. No enum, lifecycle, identity relationship, schema, contract, ADR or implementation change is authorized, and D1–D10 and ODI-3C-B-01/02/03 are unchanged.

**The answer in brief.** The repository's D6 requires only that a crash be recorded on two independent axes, kept distinguishable. It does not mention queries, result objects, attempts or runs, and the word “queryable” appears only in the pre-ratification wording kept in the project notes. What the sources do support is narrower and firmer: a non-conclusion may be asserted only from positive records, never from the absence of a result object, and a caller must be able to receive a distinct “cannot be established” answer when records are missing or incomplete.

**Five findings.**

1. **D6 has two wordings.** The tracker's D6 says a crash is “recorded on two independent axes, kept distinguishable”. The pre-ratification proposal adds “independently typed and queryable”. Which one was ratified is undecided (Q4-a), and the Q2/Q5 pack repeated the longer form as if it were D6.
2. **“Crash” is undefined.** D6 says “crash”; the built enum has four execution-failure causes; §85, §91 and §93 speak more broadly (Q4-b).
3. **Absence is not evidence.** §1 and §26 bar inferring a non-conclusion from a missing object unless the observation surface is complete.
4. **The unit of a non-conclusion is unresolved.** No source says whether it attaches to an attempt, a run, a result or a target. That is blocked by Q2-g.
5. **No target-level policy exists** for several attempts at one target. The pack's retry example assumed one and needs rewording.

---

## 0. Evidence basis and labels

- **Sources.** Tracker §10 on the Verification branch at `2221ac1` (D1–D10, ODIs, open items); frozen v1, v2 and v3; the master prompt §0–§117 as supplied (its file-level hash match is user-reported); `core/verification/`, unchanged since `fe338ed`; Runtime facts from the 2026-10-09 reconciliation report (a static read); the project notes for the pre-ratification wording (the original pasted analysis is not in the repository and was not re-inspected).
- **Labels.** **\[R\]** explicit normative requirement. **\[NI\]** necessary implication of a normative requirement. **\[A\]** interpretation requiring a decision. **\[P\]** implementation precedent or empirical observation. **\[K\]** proposed design choice, not accepted. **\[D\]** decision required from the owner.
- **Citations.** The master prompt has no paragraph numbers, so references give the section and the position, for example “§66, closing line”.
- **Rules applied.** No cardinality is inferred from singular nouns, headings, examples or object names. No semantics are accepted from a precedent. Where the text is ambiguous, both readings are kept. A candidate supported by the architecture is not an accepted decision. A representation that would make a requirement easier to query is not thereby required by the ratified text. An example does not determine lifecycle ownership, result precedence, target identity or retry semantics unless a cited contract already establishes that behavior.

---

## 1. Normative source reconstruction

| # | Source and position | Wording | Class | What it establishes for Q4 |
| --- | --- | --- | --- | --- |
| 1 | Tracker §10.2, D6 | “A crash is recorded on two independent axes, kept distinguishable: lifecycle/execution `FAILED` and the epistemic result `UNVERIFIABLE`; not ‘crash = semantic `FAILED`’.” | \[R\] | Two facts, both recorded, distinguishable. Silent on queries, objects, attempts, runs and retention. |
| 2 | Project notes, pre-ratification proposal for the same ruling | “both kept distinguishable (FAILED as lifecycle/execution failure, UNVERIFIABLE as the epistemic result, independently typed and queryable; not ‘crash = semantic FAILED’)” | \[A\] | Adds “independently typed and queryable”. The tracker omits both words. |
| 3 | Tracker §10.2, D7 | “A not-assessable execution is never forced into semantic `FAILED`; it yields no semantic binary conclusion plus `UNVERIFIABLE`/`INSUFFICIENT_EVIDENCE`/`ESCALATE` as appropriate; execution/lifecycle failure is recorded separately.” | \[R\] | A non-assessable execution has an epistemic outcome from the verdict vocabulary, and lifecycle failure is recorded separately. |
| 4 | Tracker §10.3, “Unresolved” | “representation of ‘no semantic conclusion’ (no result object, or a result with an explicit non-conclusion state; …)” | \[R\] that it is open | The ratified record itself leaves “no result object” as a live option. |
| 5 | Master §1, fifth “Never equate” block | Never equate “absence of evidence” with “evidence of absence” | \[R\] | Direct bar on inferring a non-conclusion from a missing object. |
| 6 | Master §26, closing lines | Distinguish “observation surface complete” from “observation surface incomplete”: “Only the former may justify strong absence conclusions.” | \[R\] | An absence claim needs a complete observation surface. |
| 7 | Master §42, closing sentence | “Never convert uncertainty into falsity.” | \[R\] | An unknown outcome is not a false one. |
| 8 | Master §43 | “I cannot establish this from available evidence.” “This should be a successful abstention behavior, not automatically a verifier failure.” | \[R\] | Abstention is not operational failure. |
| 9 | Master §66, title, list and closing line | Titled “Verification Result Lifecycle”; 15 states including FAILED, mixed with verdict-named states; “Cancellation/failure must never silently become PASS.” | \[R\] and \[A\] | The closing line is a requirement. The title and single list are contextual evidence only. |
| 10 | Master §68, paragraphs 1 and 2 | “Therefore support durable execution semantics: `VerificationRun`, `VerificationStep`, checkpoint, resume, retry, timeout, cancel”; “Reuse OCBrain's existing durable mechanisms rather than inventing another execution engine.” | \[R\] | Names run, step and operations. Gives no states and no cardinality. |
| 11 | Master §67 | “Verification must tolerate retries.” Lists partial persistence, crash recovery, duplicate receipt prevention and “deterministic result identity where possible”. | \[R\] | Names the hazards; defines no guarantee. |
| 12 | Master §69, closing sentence | “The system must mark such runs appropriately rather than treating old output as current truth.” | \[R\] | Stale output must be marked. |
| 13 | Master §85, sentences 1 and 3 | “Every non-definitive result must provide structured machine-readable reasons.” “Do not use generic `UNVERIFIABLE` without explanatory reason codes.” | \[R\] and \[A\] | Reasons are required. Whether “result” presupposes an object is ambiguous. |
| 14 | Master §93, §104-J, §98 | §93: “When verification cannot be completed: UNVERIFIABLE / INSUFFICIENT\_EVIDENCE / ESCALATE as appropriate.” §104-J: silent verifier crash, expected “FAILED / UNVERIFIABLE”, “never PASS”. §98: “Never allow infrastructure failure to masquerade as semantic success.” | \[R\] | Failure never becomes success. The crash case lists both outcomes. |
| 15 | Master §24, closing paragraphs | “10 obligations / 7 verified / 1 contradicted / 1 unsupported / 1 unverified … must remain explicit.” | \[R\] and \[A\] | “Unverified” is an explicit population disposition. How it relates to a non-conclusion is not stated. |
| 16 | v1 §23 | “`INSUFFICIENT_EVIDENCE` / `UNVERIFIABLE` / `ESCALATE` are successful abstention outcomes, not verifier failures” | \[R\] | Same as row 8, frozen. |
| 17 | v2 §30 | “Runtime owns the execution lifecycle; Verification owns the verification semantic lifecycle; a `VerificationRun` may execute *through* Runtime's durable-workflow machinery without Runtime owning verification semantics.” | \[R\] | Splits execution lifecycle from semantic lifecycle. |
| 18 | v2 §31 | Events `verification.requested`, `.started`, `.completed`, `.failed`, `.escalated`, `.invalidated`, `.superseded`; correlation metadata `event_id`, `correlation_id`, `parent_event_id`, `task_id`, `execution_id`, `attempt_id`, `verification_id`, `timestamp`. | \[R\] | An event history is designed, and `verification_id` is a shared correlation key. What it identifies is not stated. |
| 19 | v2 §40 | “original result immutable, new evaluation produces a new run/version”; cancellation or supersession keeps a reason code such as `task_mutated` or `budget_exhausted`. | \[R\] | Immutability, stated for escalation and supersession. A third cause vocabulary. |
| 20 | Built contracts | `VerificationResult` fields `verification_id`, `task_id`, `execution_id`, `attempt_id`, `verdict`, `assurance`, `confidence`, `execution_failure`; `execution_failure` is accepted only with UNVERIFIABLE; `VerificationReceipt` carries `verification_id`, `result`, `issued_at`, `replayability`, `supersedes_receipt_id`, `superseded_by_receipt_id`. No lifecycle type, no query interface, no `verification.*` event on `main`, and `VerificationRun` and `VerificationStep` are unbuilt. | \[P\] | The built form is result-scoped. It is not a decision. |

### D6: ratified wording versus pre-ratification proposal

**Source-established wording.** The tracker states that a crash is “recorded on two independent axes, kept distinguishable”. The handoff (§3, item 2) points to tracker §10 as the full text of D6–D10.

**Source limitation.** The tracker does not state that those axes must be “independently typed and queryable”. That stronger formulation appears in a pre-ratification proposal retained in the project notes. The notes record that the five proposed rulings were ratified as D6–D10, but not the final wording verbatim. The evidence identified so far does not establish that the stronger formulation was ratified, and it does not prove that no other ratification record exists.

**Consequence.** The phrase “independently typed and queryable” must not be attributed to D6 as an accepted requirement without a separate ratification record. It remains a proposal, not an established architectural invariant.

**Still unresolved.** D6's wording alone does not establish the representation, storage structure, query interface or query semantics needed to preserve the distinction between the two axes. Those need their own source evidence or an explicit design decision.

### 1.1 Ambiguities and what each reading would require

| # | Ambiguity | Reading 1 and what it requires | Reading 2 and what it requires |
| --- | --- | --- | --- |
| A1 | Which D6 wording governs | The tracker's: two recorded, distinguishable facts for a crash; no access requirement. | The pre-ratification wording: also independently typed values, each with a defined retrieval path. |
| A2 | What “crash” covers | Verifier crash only (§104-J: “silent verifier crash”). D7 governs the other failures. | Any execution failure: the four built causes (timeout, tool failure, verifier crash, budget exhaustion), or the broader §85 and §91 failures. D6's two-axis recording then applies to each. |
| A3 | What “recorded” implies | A durable record exists for each axis. | The facts are observable, for example in events, without a durability guarantee. |
| A4 | Whether §85's “non-definitive result” presupposes an object | A result object exists for every non-definitive outcome, so a no-object case arises only when a result was never produced. | “Result” is generic for the outcome of verification; no object is implied. |
| A5 | What §66's title and single list imply | Lifecycle and epistemic states share one vocabulary and one carrier, the result. | The list is a union of two axes that §42 and D6 keep separate. |
| A6 | Run and attempt cardinality in §68 | One run per attempt; a retry is a new run. A run's FAILED is then terminal. | Several attempts in one run. A run's FAILED is then non-terminal, or an attempt-level state is needed. (This is Q2-g.) |

**A7. Which result object.** The ratified open item (tracker §10.3) offers “no result object, or a result with an explicit non-conclusion state” and notes that D2's binary vocabulary rules out a third in-enum value. That option set appears to concern the process and outcome results, whose status is binary \[A: the tracker's sentence does not name the objects, and the D2 clause is the only pointer\]. The built crash rule instead concerns `VerificationResult` and `CriterionResult`, which carry the verdict UNVERIFIABLE with an `execution_failure`. “A result with an explicit non-conclusion state” therefore means different things for each, and every reference to “the result object” in this brief must be read against both (Q4-g).

---

## 2. Four analytical dimensions

These are analytical dimensions, not proposed enums or state machines.

| Dimension | Question it answers | Source anchors |
| --- | --- | --- |
| **A. Activity lifecycle** | What happened to the verification operation, attempt, run or other activity unit? | §66, §68, v2 §30, v2 §31. The unit itself is not established (A6). |
| **B. Epistemic outcome** | What was established about the target, and did the activity reach a conclusion? | §42, §43, §85, D6, D7, v1 §23. |
| **C. Publication and persistence** | Was a result constructed, emitted, recorded durably or made retrievable? | §67 names partial persistence and duplicate receipts as hazards. The sources define none of construct, emit, record or retrieve as separate steps. |
| **D. Query knowledge** | What can a caller establish from the available authoritative information, and how can it tell a known non-conclusion from missing information? | §1 and §26 only, by implication. No source defines a query. |

**Relationships the sources support.**

| Relationship | Support | Class |
| --- | --- | --- |
| A to B for a crash: the activity failed, and the epistemic outcome is UNVERIFIABLE | D6, §104-J, §93 | \[R\] |
| B does not imply A: abstention is not operational failure | §43, v1 §23 | \[R\] |
| Lifecycle FAILED and result-status FAILED are independent concepts | D2, ODI-3C-B-03 | \[R\] |
| The absence of an object tells nothing about B | §1, §26, §42 | \[NI\] |
| A present result with a verdict states B for that result | Built contracts | \[P\] |

**Relationships the sources do not establish.**

- Whether every outcome B produces an object (C). A4.
- Whether a published object is retained, and for how long. No retention requirement is set beyond §36's “enough evidence to inspect a verification decision”.
- How a caller reaches any of these records (D). No query interface is defined.
- Which of the four non-crash terminations map to which epistemic outcome. A2.

**Three things this brief does not assume:** that operational FAILED implies a particular verification outcome; that result-status FAILED means the same as lifecycle FAILED; and that a missing object implies no conclusion.

---

## 3. Scenario matrix

Each row reports what is known, what an observer may claim, what D6 as recorded requires, the governing clause, and the decision that blocks a definitive answer. “Silent” means D6 says nothing for that scenario, because no crash is involved. No status vocabulary is prescribed.

| # | Scenario | Known, and not established | Entitled claim | D6 as recorded requires | Governing clause | Blocking decision |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | No verification activity established | Known: no record of a request. Not established: whether none was made or the records are missing. | “No record is available.” Not “not verified” and not “non-conclusion”. | Silent | §1, §26 | Which records are authoritative and complete (Q4-f). |
| 2 | Requested, no attempt known to have started | Known: a request record. Not established: whether an attempt began unrecorded. | “Requested; no attempt recorded.” | Silent | §66 (REQUESTED, IN\_PROGRESS); v2 §31 (`requested`, `started`) | Q2-g: which unit REQUESTED and IN\_PROGRESS describe. |
| 3 | An attempt is running, no conclusion yet | Known: activity recorded as in progress. Not established: whether it will conclude or is still alive. | “No conclusion yet.” Not “non-conclusion”, which is a terminal assertion. | Silent | §66, §68 (checkpoint, timeout), §69 | When a stale in-progress record is resolved; §68 names timeout without semantics. Q2-g. |
| 4 | An attempt ends in operational failure | Known: that attempt failed, with a cause such as TIMEOUT, TOOL\_FAILURE, VERIFIER\_CRASH or BUDGET\_EXHAUSTED. Not established: partial evidence, retries, the target-level outcome. | “This attempt failed operationally and produced no semantic conclusion.” Not “the claim is false”. | For a crash: lifecycle failure and UNVERIFIABLE both recorded and distinguishable. Whether the non-crash causes count is A2. | D6, §104-J, §66, §93, built rule | Q2-a, Q2-g (unit), Q4-b, Q4-e. |
| 5 | An attempt completes without reaching a conclusion | Known: normal completion, with an outcome among UNVERIFIABLE, INSUFFICIENT\_EVIDENCE or ESCALATE. Not established: whether an object was published. | “Completed and abstained.” A successful abstention, not a failure. | Silent (not a crash); D7 applies | §43, §85, §86, v1 §23, D7 | How a non-conclusion is represented; A4. |
| 6 | A result is emitted with result-status FAILED | Known: a process or outcome status FAILED on one dimension. Not established: any attempt failure, or `failure_control`. | “Process or outcome status FAILED.” That is a semantic result for the dimension: not an attempt failure and not a non-conclusion. | Not conflated with lifecycle FAILED | D2, v1 §20, ODI-3C-B-03 | Q3 (names); Q6 for `failure_control`. |
| 7 | A conclusion may have been calculated, but publication or persistence failed | Known: perhaps a conclusion existed in memory. Not established: whether it did, what it was, or any durable record. | Only “no durable conclusion is recorded”. No claim about its content. Whether that is a non-conclusion assertion needs a complete observation surface. | If this is a crash (A2): both axes recorded despite the lost conclusion | §67 (partial persistence), §98, D6 | Publication and durability semantics are undefined; Q2-d. |
| 8 | A result was recorded but is temporarily unavailable to the caller | Known: nothing, to this caller. Not established: whether the record exists. | “Cannot be established.” Never “no result”. | Silent | §1, §26 | Whether a distinct third answer is normative (Q4-d). |
| 9 | The relevant history is incomplete, missing or gone | Known: nothing positive. Not established: anything about the period. | “Cannot be established; the surface is incomplete.” | Silent | §26; §36 (retain enough evidence to inspect a decision, no duration); v2 §41 (old receipts stay historical) | Retention and recovery requirements are not set (Q4-f). |
| 10 | One attempt is inconclusive, another concludes | Known: both attempt-level facts. Not established: which governs the target. | Each attempt's fact. A target-level claim only under a stated policy. | Silent | §45 (later observations may reverse a status), v2 §40, §66 (SUPERSEDED) | No target-level policy exists. Q5, Q2-g, aggregation. |
| 11 | Attempts produce different determinations | Known: each determination. Not established: which governs, or whether conflict resolution applies. | Report both. No merged claim. | Silent | §25 (do not blindly average contradictory evidence), §41 | As row 10, plus conflict rules for repeated attempts. |
| 12 | An attempt is retried, resumed or superseded | Known: retry, resume and cancel are named (§68); SUPERSEDED, INVALIDATED and EXPIRED are named (§66); original results are immutable (v2 §40). Not established: the transitions, identity effects, or which unit is retried. | “A retry, resume or supersession occurred” if recorded. Earlier result records are not rewritten \[NI from v2 §40\]. | Silent | §67, §68, §69, v2 §40; the Runtime's `resume()` is \[P\] only | Q2-g, Q2-d. |

---

## 4. Queryability contract

### 4.1 The subject of the query

D6's grammatical subject is “a crash”, and the unit that carries the recording is not stated. Four readings are plausible, and the sources support none exclusively:

- **occurrence-scoped:** how one failure occurrence is recorded;
- **activity-scoped:** attached to an attempt or a run;
- **result-scoped:** fields on a result object;
- **target-scoped:** the state of the verified target.

The built contracts take a result-scoped form (\[P\]: `execution_failure` plus UNVERIFIABLE on `VerificationResult` and `CriterionResult`). That is a precedent, not a decision, and it does not by itself cover a crash that produces no result.

### 4.2 Three kinds of query

| Query | Minimum information the caller needs | Inferences permitted | Inferences not permitted |
| --- | --- | --- | --- |
| Historical, about a specific activity | The activity's identity; a positive record that it existed; its terminal condition, or an explicit “not terminal” or “unknown”; the cause, if it failed operationally; the epistemic outcome, or a positive statement that none was produced | Lifecycle facts. “This activity reached no conclusion” only when a record says so or the surface is complete (§26) | Claims about the target. “No conclusion” from a missing object |
| Current state, about a target | The activities and results recorded for the target; whether that set is known to be complete; the policy that relates them (not established, see rows 10 and 11 of §3) | “This is what is recorded.” Statements qualified by completeness | “The target has no conclusion” from absence. A target-level conclusion from one attempt |
| Unanswerable because records are unavailable or incomplete | The answer itself: “cannot be established”, with its reason class | None about the verification | Any default, whether PASS-like, “no conclusion” or “failed” |

### 4.3 Evaluating D6 without a result object

&#91;K, derived from §1 and §26; a test, not a mechanism.\] D6 is satisfied for a crash occurrence when positive records let a caller establish that:

1. the lifecycle or execution failure occurred;
2. the epistemic result for that occurrence is UNVERIFIABLE, and this is stated, not inferred from a missing object;
3. these are two separate answers, not one.

The test never relies on a missing record. A result object is one way to satisfy item 2, and the one the built contracts use, but the sources do not require it: the ratified record leaves “no result object” open (row 4 of §1). If neither a result nor another positive record states item 2, D6 cannot be shown to be satisfied, and the correct answer to a query is “cannot be established”, not “non-conclusion”.

### 4.4 What “queryable” is not assumed to mean

No source establishes that it means a new result object, a new terminal state, permanent retention, or any particular storage mechanism. Each remains unresolved (retention is Q4-f).

**Three levels that must stay distinct.** *Machine-readable*: consumers can read structured fields without parsing prose; §85 requires structured, machine-readable reasons for non-definitive results \[R\]. *Queryable*: consumers can retrieve results by relevant attributes or identifiers; no source defines this. *Independently typed*: the architecture defines separate type contracts for the concepts; ODI-3C-B-03 asks for distinct namespaced types for the two FAILED concepts, but no source requires them for every axis. One level does not establish the others, and D6 as recorded establishes only that the axes stay distinguishable.

---

## 5. Candidate sources of authoritative information

This brief proposes no storage architecture and no mandatory new record type. It compares what each source-supported alternative can and cannot show.

| Criterion | 1. Runtime and event history (v2 §30, §31) | 2. Run and step records (§68) | 3. Results and receipts (built) | 4. Derived view over 1 to 3 |
| --- | --- | --- | --- | --- |
| Positive evidence that the activity existed | `verification.requested` and `.started` events, if emitted. None exist on `main` \[P\]. | A run record created at request. Unbuilt. | The existence of a result or receipt only. An attempt that produced none leaves no trace here. | Only what the underlying sources show. |
| Lifecycle or terminal condition | `.completed`, `.failed`, `.escalated`, `.invalidated`, `.superseded` events. The terminal subject (attempt, run or verification) is unstated. | States unspecified (Q2-g). | None: there is no lifecycle field. A receipt shows issuance and supersession links only. | Whatever the join yields. |
| Non-conclusion versus missing information | An event states a failure positively. The absence of an event proves nothing: events can be missing, reordered or duplicated (§98). | Would state a terminal condition. Carries the epistemic outcome only if specified, which no source does. | UNVERIFIABLE with `execution_failure` marks a crash; UNVERIFIABLE without it marks an abstention \[P\]. Reason codes (§85) are not in the code. | Can express “cannot be established”. Cannot create information the sources lack. |
| Correlation to the subject | `verification_id` and `attempt_id` in the metadata. What they identify is not stated. | Run, attempt and step identities: undefined. | `verification_id`, `execution_id` and `attempt_id` on the result; the receipt carries `verification_id`. | Depends on the keys; a join on unclear keys can mislead. |
| Risk of a misleading answer | An event emitted without a persisted result; lost or reordered events (§98). | A stale in-progress record after a crash; a partial write at a checkpoint. | Failed publication leaves no record; a superseded result can look current if the links are not followed. | Inconsistent joins and stale caches (§98). |
| Authoritative or projection | Authoritative for runtime observation (v2 §30). Not for the epistemic outcome unless an event carries it. | Verification owns the semantic lifecycle (v2 §30). Unbuilt. | Authoritative for the content of one result. | A projection, never authoritative. |
| Retention, recovery or consistency requirements in the text | None stated. | Checkpoint and resume are named (§68), reusing Runtime mechanisms. No consistency rule. | Immutability (v2 §40); duplicate-receipt prevention (§67). No retention rule. | None. |

No alternative can be selected without the unit of assertion (Q2-g) and the identity relationships (Q2-d).

---

## 6. Identity and cardinality

Only relationships supported by the governing clauses are traced.

| # | Relationship | Support | Status |
| --- | --- | --- | --- |
| 1 | Task, execution, attempt, step and worker of the execution being verified | §64 scoping list; DEBT-015 still open | Established as scoping fields. The built `attempt_id` is a bare `NewType` with no documented meaning \[P\]; reading it as the verified execution's attempt is \[A\]. |
| 2 | `verification_id` as a correlation key across events, results and receipts | v2 §31; built result and receipt | Established as a key. Whether it identifies the logical verification, a run or an attempt is not stated. |
| 3 | Target and verification | Receipt binds `target_id` (§59); built target snapshot and fingerprint | Binding established. Cardinality not stated. |
| 4 | Verification and run | §68 names `VerificationRun` | Open: one run or many per verification. |
| 5 | Run and attempt | §68 names retry and resume on run and step | Open (Q2-g). |
| 6 | Attempt and result | §64; §67 (“deterministic result identity where possible”) | Open. Zero or one result per attempt is not established. |
| 7 | Result and the current state of the target | §66 (SUPERSEDED, EXPIRED); v2 §40 | Not established. Results can be superseded, so a result is not by itself the current state. |
| 8 | Attempt-level non-conclusion and target-level non-conclusion | None | Not established. |

**Unsupported assumptions flagged, and not made here:** one run has exactly one attempt; one target has exactly one run or attempt; one attempt emits exactly one result; one result represents the current state of a target; an attempt-level non-conclusion establishes a target-level one.

**Determinable independently of Q2-g.**

- The absence of an object is never proof of a non-conclusion (§1, §26).
- A caller needs a distinct “cannot be established” answer when records are missing or incomplete \[NI\].
- For a crash, two facts are recorded and distinguishable (D6 as recorded).
- Operational failure is never a verdict and never a PASS (§66, §93, §104-J).
- Abstention is not operational failure (§43, v1 §23).
- Determinations from different activities are not merged implicitly.

**Constrained by Q2-g.**

- The unit to which a non-conclusion assertion attaches.
- Whether a run's FAILED is terminal.
- What the correlation keys identify.
- What REQUESTED and IN\_PROGRESS describe.
- How retry history is represented.

---

## 7. Consequences for Q2, Q5 and Q6

“Blocked” means the question cannot be decided until the named item is. “Partially constrained” means a decision remains possible but must respect the finding.

| Q4 finding | Q2 | Q5 | Q6 |
| --- | --- | --- | --- |
| F1. D6 has two wordings (A1) | Partially constrained: the longer wording would add typing and retrieval demands on any Q2-a carrier. | Unaffected. | Unaffected. |
| F2. Absence is not evidence (§1, §26) | Partially constrained: any no-object route under Q2-e needs positive records. | Partially constrained: an unverified target cannot be classified by absence alone. | Unaffected. |
| F3. The unit of assertion is unresolved | Blocked by Q2-g. | Partially constrained: target versus attempt as the unit. | Partially constrained: which failure occurrence is referenced. |
| F4. Three FAILED-like concepts stay independent | Q2-a stays a candidate; Q4 requires only that the concepts be separately determinable. | Unaffected. | Partially constrained: `failure_control` derives from the semantic chain (D9), not from attempt failure alone. |
| F5. No target-level policy for repeated attempts (rows 10 and 11 of §3) | Unaffected beyond Q2-g. | Blocked for repeated-attempt aggregation: no policy may be inferred from attempt records. | Unaffected. |
| F6. Three cause or reason vocabularies: `execution_failure` causes, §85 reason codes, v2 §40 cancellation reasons; `budget_exhausted` appears in two | Q2-c and Q2-h bear on it. | Unaffected. | Partially constrained: the derivation inputs depend on Q2-h. This brief does not resolve Q2-h. |

---

## 8. Candidate recommendations and the treatment of precedent

All are \[K\]: candidates, not accepted.

| # | Candidate | Support | Counter |
| --- | --- | --- | --- |
| C1 (A1) | Treat the tracker's D6 wording as the minimum invariant, and ask the owner to confirm whether “independently typed and queryable” was ratified. If it was, record it in the tracker (a docs-only change needing separate authorization). | The tracker is the repository-resident record. | The ratification note says the five rulings were ratified, so the longer text may have been intended. |
| C2 (A2) | Treat all four built causes alike for D6 recording until decided. | §93 and §98 cover any incomplete verification, and the built rule already treats them alike. | D6 says “crash”, and D7 already says other execution failures are “recorded separately”. |
| C3 | For any query about an activity or a target, require three distinguishable answers: a conclusion is recorded; a non-conclusion is recorded with a positive basis; it cannot be established. | §1 and §26 \[NI\]. | It adds a requirement the sources imply but do not state (Q4-d). This is not a type proposal. |
| C4 | Keep “result object or not” open. The D6 invariant is satisfiable either way (§4.3), so Q4 need not force Q2-e. | §10.3 of the tracker leaves it open. | The built contracts already take the result-scoped form. |
| C5 | Reword the Q2/Q5 pack's retry example so it does not assume the later conclusion governs the target, and replace its description of D6 with the tracker's wording plus a note on A1. | Rows 10 and 11 of §3; finding 1. | None. It corrects the pack. |

**Additional candidates from the review (C6 to C8).** All are \[K\]. C4 says D6 does not force the choice between a result object and none; C6 is a design preference within that open choice.

- **C6. Preserve an explicit result record when an attempted verification cannot reach a conclusion.** Support: omission is ambiguous (rows 1 and 7 to 9 of §3), since it can mean no attempt, a blocked attempt, a crash, an unemitted record or lost data; §85 read as requiring an object (A4, reading 1); the built contracts take this form. Counter: tracker §10.3 leaves “no result object” open (C4); D2's binary vocabulary rules out a third value on the process and outcome results (A7); and a verifier that has crashed may be unable to write the record, so a second writer, such as the orchestrator or the activity record, would have to supply it. That depends on Q2-g and Q4-e (Q4-h).
- **C7. Treat structured reasons and sufficiency information as requirements, and the code list as unfinished.** §85 requires structured, machine-readable reasons for non-definitive results, and §86 asks for sufficiency information for insufficient evidence only. §85's 14 codes are introduced as “Examples”, so they are not a closed, ratified vocabulary, and §86's fields need not apply to every execution failure. Counter: some §85 codes (for example TOOL\_FAILURE and BUDGET\_EXHAUSTED) overlap the `execution_failure` causes, so the vocabulary question stays open (F6, Q2-h).
- **C8. Preserve attempt-specific results and provenance, and define target-level selection separately if it is needed.** Support: rows 10 and 11 of §3; §61 and §63 tie validity to artifact, environment and task versions and fingerprints, so a later result addresses the same target state only if those match. Counter: §45 allows a later observation to reverse an earlier status, so a selection rule may sometimes favor the later result. No source establishes a latest-attempt-wins rule.

**Layer note.** C6 is not bound to the process/outcome layer or to the verification/criterion layer until Q4-g names its object. The built form is a precedent at the verification/criterion layer only.

**`WorkflowRuntime.resume()` \[P\].** It belongs to the Runtime (v2 §30) and resets only RUNNING and CANCELLED nodes to PENDING (corrected 2026-10-19: COMPLETED and FAILED nodes are skipped and keep their cached results). FAILED is terminal and cached there, so it gives no support for a non-terminal FAILED. It therefore cannot support an interpretation of Verification semantics, and it does not override §24, §66 or §68. Whether the Runtime preserves failure history elsewhere was not verified.

**The title of §66.** It is contextual evidence for a result-level lifecycle vocabulary, not decisive. §42 and D6 separate the axes and the list mixes them, so the title alone does not establish one carrier.

**Convenience.** No candidate above was chosen for ease of implementation, and none introduces a new abstraction.

---

## 9. Acceptance criteria self-check

| # | Criterion | Where addressed |
| --- | --- | --- |
| 1 | Precise normative scope of D6's queryability requirement | Finding 1; §1 rows 1 and 2; A1; §10 |
| 2 | Four dimensions distinguished | §2 |
| 3 | Non-conclusion evaluable with no result object | §4.3 |
| 4 | No inference from object absence | §1 rows 5 and 6; §4.2; §3 rows 1 and 7 to 9 |
| 5 | Operational failure, result-status FAILED and non-conclusion kept apart | §2; §3 rows 4 to 6 |
| 6 | Absent, ongoing, incomplete, failed publication and multiple attempts covered | §3 rows 1 to 3 and 7 to 12 |
| 7 | Identity relationships and unsupported cardinality marked | §6 |
| 8 | Dependencies on Q2, Q5 and Q6 explained without deciding them | §7 |
| 9 | Recommendations labeled as candidates | §8 |
| 10 | Q2-a unaccepted and Q2-g open | Status; §6; §10 |

---

## 10. Conclusion

**The exact D6 invariant the evidence supports.** From the tracker's wording: for a crash, two facts are both recorded, on independent axes, and a reader can tell them apart: the lifecycle or execution failure, and the epistemic result UNVERIFIABLE. Neither is replaced by “crash = semantic FAILED”. The stronger form, that each is also independently typed and queryable, is supported only by the pre-ratification wording (A1).

**The minimum observable behavior this implies.**

1. From positive records alone, a caller can learn that a crash occurred and that the epistemic result is UNVERIFIABLE.
2. A caller can tell that apart from a result-status FAILED, from a successful abstention (no execution failure, with reason codes per §85), and from an operational failure with no recorded outcome.
3. When records are unavailable or incomplete, the answer is “cannot be established”, not “non-conclusion” \[NI from §1 and §26\].
4. No failure outcome reads as a PASS (§66, §93, §104-J).

**Still ambiguous in the sources.** A1 to A6 in §1.1; what “queryable” demands; retention and recovery; the target-level policy for several attempts.

**Conclusions that depend on Q2-g or other open questions.** The unit of a non-conclusion assertion; whether a run's FAILED is terminal; what the correlation keys identify; how retry history is represented; the choice among the sources in §5.

**Decisions required \[D\].**

- **Q4-a.** Which D6 wording is ratified: the tracker's, or the pre-ratification “independently typed and queryable”?
- **Q4-b.** Does “crash” cover all four execution-failure causes, or only the verifier crash (with D7 for the rest)?
- **Q4-c.** Does §85's “non-definitive result” presuppose a result object for every non-definitive outcome?
- **Q4-d.** Is a distinct “cannot be established” answer a normative requirement for queries about verification activity (derived from §1 and §26)?
- **Q4-e.** What is the unit of a non-conclusion assertion: attempt, run, result or target? (Depends on Q2-g.)
- **Q4-f.** What retention and recovery guarantees apply to the records D6 relies on?
- **Q4-g.** Which result object does an explicit non-conclusion attach to: the built `VerificationResult` and `CriterionResult` (verdict UNVERIFIABLE with `execution_failure`), or the unbuilt process and outcome results, whose status vocabulary D2 keeps binary? (A7.)
- **Q4-h.** If an explicit non-conclusion record is preferred (C6), who writes it when the verifier itself crashes, and what records the crash if no record is written? (Depends on Q2-g and Q4-e.)
- **Q4-i.** Adopt a definition of “non-conclusion”: verification did not establish a definitive semantic conclusion from the available evidence, and this is never silently read as false, contradicted or successful? (A candidate is given in §10.2.)
- Outside Q4, flagged: the target-level policy for several attempts belongs to Q5 and aggregation.

**Q4-a, in two parts.** The source question is: what wording does the available ratification evidence establish? Conservatively, the tracker's. The design question is: should OCBrain require independently typed, queryable axes? That needs an explicit decision and cannot be settled by retroactively strengthening D6's wording.

**Next permissible decision.** In the existing order (Q2, Q4, Q5, Q1, Q6, Q3) and the review sequence you set, Q4-a to Q4-d can be decided now, because none depends on Q2-g. Q4-e waits for Q2-g, and Q4-f needs an owner position. Nothing here is accepted until you record it, and Q2-a stays a candidate.

### 10.1 Representation and queryability of a non-conclusion: design recommendations

**Status.** Analysis and design recommendations only. Nothing here is accepted by appearing here.

**Source boundary.** D6's ratified wording, as evidenced by the tracker, is that a crash is “recorded on two independent axes, kept distinguishable”. “Independently typed and queryable” belongs to a pre-ratification proposal and is not attributed to D6 without separate ratification evidence.

**Semantic invariant \[K, consistent with D6, D7 and §66\].** Execution lifecycle, semantic conclusion and the reasons for a non-conclusion are not conflated. A crash that prevents verification establishes an execution failure; it does not by itself establish a negative semantic verdict.

**Representation \[K\].** Prefer an explicit result record for an attempted verification that cannot reach a conclusion (C6), without a new canonical verdict and without treating missing output as an explanation. Which result object carries it (Q4-g), who writes it when the verifier crashes (Q4-h), the exact type and field layout, and lifecycle ownership stay with their own decisions.

**Reasons and sufficiency \[K\].** Non-definitive results should expose structured, machine-readable reasons, and insufficient-evidence cases should carry sufficiency information (C7). Neither requirement ratifies an example code list as exhaustive or forces sufficiency fields onto every execution failure.

**Queryability \[K\].** If adopted, retrieval and filtering is an explicit consumer-facing requirement with the smallest contract that serves real use cases. Independent types, separate tables, a particular index or a query API are not inferred from D6.

**Retry and authority \[K\].** A later attempt may produce a conclusion, but no source identified here establishes that it supersedes an earlier result or governs the target (C8). Preserve attempt-level provenance and define target-level selection separately if required.

**Decision discipline.** Ratified requirements, source-supported interpretations, design recommendations and unresolved choices stay visibly separate. This section does not close Q2-a, authorize implementation or modify the repository.

### 10.2 Reconciliation of the latest review with this brief's decision IDs

The review used its own labels Q4-a to Q4-d, which differ from this brief's. To avoid two meanings for one label, they are mapped here, and the brief's labels stay as defined in §10.

| Review label | Subject | Where it sits in this brief |
| --- | --- | --- |
| Q4-a | Meaning of a non-conclusion | New decision Q4-i |
| Q4-b | Structured reasons | C7 and Q4-c |
| Q4-c | Queryability | §4.4 and §10.1 (Queryability) |
| Q4-d | Dedicated result object | C6 and Q4-g |
| Q4-g, Q4-h | Object ambiguity, writer | Q4-g, Q4-h |

All dispositions below are \[K\]: candidates, not accepted.

**Q4-i, meaning of a non-conclusion.** Verification did not establish a definitive semantic conclusion from the available evidence. It is not silently read as false, contradicted or successful (§42, §43). Defining it does not create a third process/outcome status and does not imply that any particular result object exists.

**C7, refined.** `execution_failure` identifies an execution-failure condition; it is not a complete explanation of every non-conclusion. A missing evidence requirement and a verifier crash are different reasons, even though both prevent a definitive conclusion. §86's sufficiency information is relevant to insufficient evidence, and the sources do not place all of it on every result object.

**Queryability, refined.** A design preference, not a D6 requirement: stable, structured, independently retrievable reason and provenance information. Machine readability is supported by §85, and tracing why a result was produced by the provenance and receipt requirements (§57, §59). Neither shows that the information needs a dedicated object, indexed columns or a query API.

**C6, identified by role.** An explicit record must say which of four roles it plays before it is recommended: a process/outcome semantic result; an existing verification or criterion result; an execution or activity record of what happened; or a separate provenance record. A recommendation is incomplete until it names the owning contract and what that contract is authoritative for.

**Q4-g, revised candidate.** The choice between omitting a result object and producing a result with an explicit non-conclusion state is evaluated at the process/outcome layer that the tracker's D2 clause points to. D2's binary vocabulary is preserved: no epistemic non-conclusion is added as a third process/outcome status. When no semantic conclusion can be established, no process/outcome result is manufactured to assert one. The attempted verification, its non-conclusion and the execution-failure evidence are preserved through the verification and criterion contracts and through an execution or activity record. Whether an additional durable record is needed, and which contract owns it, stays open.

| Contract | Candidate treatment |
| --- | --- |
| Process and outcome results | Keep D2's binary vocabulary. Do not manufacture a conclusion when none was established. |
| `VerificationResult` and `CriterionResult` | Retain the existing crash representation when these results are produced. Do not infer that both must always exist. A crash representation on a constructed result does not prove that an abrupt crash leaves that result durably available. |
| Execution or activity record | A candidate place to preserve an independently observed crash when the verifier cannot produce its own record. The owning component is undecided. |
| An additional C6 record | Not justified merely because an explicit record seems desirable. First show what information the existing contracts cannot carry. |

**Precedent \[P\].** An object can exist without a conclusion by using a separate state axis, not a third verdict value: `CriterionResult` with NOT\_ATTEMPTED or BLOCKED carries no verdict. That shows a form, not a decision for the process and outcome results.

**Q4-h, considerations.** A verifier that terminates before producing a record cannot be relied on to persist its own termination. The supervising execution boundary, or an activity or event mechanism under its control, is a plausible writer, but it must record an observed execution fact and never fabricate a semantic conclusion. The contract must still say who owns that write, what happens if persistence fails, and how the record is linked to the correct verification and attempt. Recommending an orchestrator does not settle these.

### 10.3 Candidate decision ledger (all candidates; none accepted)

This consolidates the dispositions from §10.1, §10.2 and the latest review under this brief's own labels. The reviewer withdrew the earlier answers given under the review's labels Q4-b and Q4-d, because those labels did not match this brief. This brief's own Q4-b and Q4-d are shown below with their actual questions.

| ID | Question (this brief) | Candidate disposition | Remaining boundary |
| --- | --- | --- | --- |
| Q4-a | Which D6 wording is ratified? | The tracker's: a crash is recorded on two independent axes, kept distinguishable. The source question is answered conservatively; the design question (typed, queryable axes) is separate. | D6 is not claimed to mandate independent queryability, separate types or an object type. Not inferred from D6 alone: the scope of a crash (Q4-b), the owner or concrete representation of either axis, or any mapping beyond what its text states. Its text does name UNVERIFIABLE as the epistemic result of a crash and lifecycle/execution FAILED as the failure fact, so that pairing is part of D6 for a crash. “Independent axes” describes separated dimensions, not statistical independence. A ratification record elsewhere is not excluded. |
| Q4-b | Does “crash” cover all four execution-failure causes, or only the verifier crash? | C2, refined in the separate Q4-b brief: do not extend D6's pairing to timeout, tool failure and budget exhaustion by assumption. Record the settled core (a crash is both a lifecycle failure and UNVERIFIABLE; no failure becomes PASS), govern the other causes by D7, and mark the built rule's UNVERIFIABLE-only extension as an implementation judgment pending Q4-b1 to Q4-b5. | D6 says “crash” and D7 says other execution failures are “recorded separately”. Owner decision, and the next dependency: it fixes which events the D6 distinction applies to, so later decisions must not apply it to the wrong set. |
| Q4-c | Does §85's “non-definitive result” presuppose a result object? | Keep both readings. Separately, accept as a candidate the requirement for structured, machine-readable reasons (C7). | Reason catalogue, schema, cardinality and evidence linkage are undecided. |
| Q4-d | Is a distinct “cannot be established” answer a normative requirement? | C3: three distinguishable answers (a conclusion is recorded; a non-conclusion is recorded with a positive basis; it cannot be established). Derived from §1 and §26 \[NI\]. | Owner to confirm it as normative. It is not a type proposal. |
| Q4-e | What is the unit of a non-conclusion assertion? | None. | Depends on Q2-g. |
| Q4-f | What retention and recovery guarantees apply? | None. | Needs an owner position; the sources set none. |
| Q4-g | Which result object carries an explicit non-conclusion? | Latest review, conditional. (1) Where a process/outcome assessment is produced but cannot establish a conclusion, represent the non-conclusion explicitly in the relevant result contract, with structured reasons. (2) Where no such assessment is produced, preserve the operational state in the activity and verification records without manufacturing an aggregate result. (3) Where criterion results exist but aggregation is unresolved, preserve them and the execution history, and do not assume that mixed states imply a non-conclusion (a failed required criterion could still establish a negative conclusion under a future rule). This assigns the two earlier candidates to different conditions. The earlier review's candidate was to preserve the non-conclusion through the verification and criterion contracts and an execution or activity record, with no process/outcome result manufactured. | This decides the representational capability preferred, not aggregation (master §46), discriminator semantics, publication conditions or schema. What counts as a produced assessment is itself undefined until aggregation is, so conditions (1) and (2) cannot yet be applied mechanically. The premise that the tracker's option set concerns process/outcome results is inferred \[A\]. No generic extra object without further justification. |
| Q4-h | Who writes the record when the verifier crashes? | The supervising execution boundary, or an activity or event mechanism under its control, is plausible; it records an observed execution fact only. | Owner, persistence-failure handling and linkage are unspecified. |
| Q4-i | What does “non-conclusion” mean? | Verification did not establish a definitive semantic conclusion from the available evidence; never silently read as false, contradicted or successful. | Must stay distinct from lifecycle failure, semantic verdicts and existing abstention values. |
| §4.4 and §10.1 | Queryability | A separate design preference. | Define the query contract and field placement only after the representation is settled. |

### 10.4 Conceptual model for discussion (not a specification)

```
ProcessVerificationResult
  process conclusion: conclusive or non-conclusive
  semantic result: present only when conclusive
  non-conclusion reasons: required when non-conclusive
  references to supporting findings and evidence

OutcomeVerificationResult
  outcome conclusion: conclusive or non-conclusive
  semantic result: present only when conclusive
  non-conclusion reasons: required when non-conclusive
  failure_control: placement and derivation unresolved
  references to supporting findings and evidence

Verification execution lifecycle
  a separate operational record or contract;
  FAILED ownership and state vocabulary remain open
```

The model omits field names, cardinalities, identifiers and enum values. Its invariants, all \[K\]:

- A non-conclusion is explicit; it cannot be inferred only from a missing result.
- A non-conclusion cannot carry a semantic verdict that purports to have been established.
- An execution failure cannot silently become a positive semantic conclusion.
- A semantic non-conclusion does not by itself establish an execution failure.
- Process and outcome stay independently representable: a known process result does not force an equally definitive outcome result, or the reverse (v1 §20 keeps them separate objects).

**Caveats on the model.**

1. The conclusive/non-conclusive discriminator is a conceptual device, not an enum. It mirrors the separate attempt-state axis of `CriterionResult`, not a third value in D2's binary status, and must not enter code before acceptance.
2. Its meaning depends on aggregation from criterion results (master §46), which is unbuilt and undecided. A process or outcome built from some conclusive and some non-conclusive criteria could be conclusive (a failed required criterion) or non-conclusive. Until that rule exists, the discriminator cannot be defined.
3. `failure_control` is drawn under outcome only because the v1 §20 example places it beside the outcome status. D9 says only “a field on the process/outcome result”. Placement on process, outcome or both is Q6.
4. “References to supporting findings and evidence” is a placeholder; the reference shape and derivation are Q6.
5. `CoverageResult` (the D10 sibling) and the verdict-bearing `VerificationResult` are not drawn.
6. The lifecycle record is shown separately; FAILED ownership (Q2-a, Q2-g) stays open.
