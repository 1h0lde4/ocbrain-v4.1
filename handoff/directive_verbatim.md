# Owner directive — preserved verbatim (ADR-KERNEL-07 · DEBT-042 · DEBT-043)

> Preservation note (PROJECT_INSTRUCTIONS §18.4.8.3). The directive reached the session as **two messages**.
> **Part 1** ends mid-sentence ("Do not add") inside §3.4: the text of the first message was cut off.
> **Part 2** was sent afterwards by the owner with the words "this is the continuation to the prompt" and
> begins by completing §3.4. Both parts are reproduced below exactly as received. Nothing has been added,
> removed or reworded; only this note and the part headings are mine.
>
> Part 2 states that its **§5.4 is a proposed replacement specification** because the original §5.4 "was not
> preserved in the accessible records"; it must never be presented as recovered original wording.

---

## PART 1 (received first; truncated at the end of §3.4)

# OCBrain — Final Remediation Directive
## ADR-KERNEL-07 · DEBT-042 · DEBT-043

Repository: `1h0lde4/ocbrain-v4.1`

### 1. Mission and hard boundaries

Complete the narrow remediation of DEBT-042 and DEBT-043, reconcile the associated architecture and status records, and produce evidence sufficient for independent review and eventual closure.

This work has three initial deliverables:

1. An additive documentation/decision PR recording the current response-path disposition.
2. A separate DEBT-042 implementation and test PR.
3. A separate DEBT-043 implementation and test PR.

A separate closure-documentation PR may follow after authorized merges and post-merge verification. Do not merge anything in this task.

You may inspect the live repository, modify scoped local files, run tests, create branches and open PRs if the necessary access is available. Do not force-push, rewrite shared history, enable the detector by default, modify unrelated architecture, or declare the kernel freeze-ready. Never request or expose credentials.

If a remote write is unavailable, deliver the local patch, exact tested head SHA, test results, and the precise remaining remote steps. Never claim a branch or PR exists unless verified.

The guiding rule is: **prove the current state, make the smallest correct changes, verify behavior at the real integration boundary, and claim only what the evidence establishes.**

### 2. Live preflight — mandatory before editing

Latest known reference points:

- `main`: `f13bfdefcdd197ed1f966de0b1f93037a4168af4`
- PR #85 merge: `ef426e9d8fb14dae10c19c2344ceb24d0f04eb81`
- PR #82 merge: `f13bfdefcdd197ed1f966de0b1f93037a4168af4`

Fetch current refs before using these as a base. Do not assume the remote has not advanced.

Inspect:

- Current `main` SHA and relevant file/blob SHAs.
- Working-tree cleanliness, existing local branches, and remote branches.
- All open PRs, their head/base SHAs, changed files, CI checks, reviewer activity and ownership.
- Potential overlap with previously known PRs #86, #83, #81 and #79, verifying their current states instead of assuming them.
- Existing branches or PRs already addressing either debt.
- All callers of `SQLiteStorageBackend.search_text()` and `UnifiedMemory.search()`, their documented contracts, and relevant tests.
- Current feature-flag wiring and the actual Orchestrator escalation/return/event path.
- The relevant FTS5 implementation, test fixture setup, SQLite runtime version and configured CI checks.

Read the live source and decision records, especially:

- `docs/architecture/decisions/ADR_KERNEL_07_CREATIVE_CONTENT_ANCHOR_DETECTOR.md`
- `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md`
- `docs/studies/OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RESULT_OCT2026.md`
- `docs/studies/OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RUNBOOK_OCT2026.md`
- `docs/studies/OCBRAIN_LIVE_CHECK_REPEAT_RUNS_PROTOCOL_OCT2026.md`
- `KNOWN_ISSUES.md`
- `CURRENT_STATE.md`
- `core/cognitive/content_anchor.py`
- `core/cognitive/intent.py`
- `core/orchestrator.py`
- `core/memory/backends/sqlite_storage.py`
- `core/memory/unified_memory.py`
- `tests/core/cognitive/test_creative_content_anchor.py`

Identify additional relevant tests by searching the live repository. Do not assume the two named test files are the complete suite.

Report the starting SHA, observed open-PR overlaps, relevant baseline behaviors, and planned file scopes. Then proceed with the scoped implementation; do not ask the owner to repeat decisions already contained in this directive.

A GitHub status response with no returned checks is **not** proof of green CI. Capture the actual checks and conclusions, with links where available.

### 3. Architectural invariants and response disposition

#### 3.1 Preserve the existing architectural D-5 decision

ADR-KERNEL-07 §10.3 records the September 29, 2026 architectural decision as Option C:

- The content-anchor detector is a pure, non-governing observation before planning.
- Its result is carried through planning.
- The existing `OrchestrationGovernor` evaluates it at the existing Plan Compilation boundary alongside `ClarificationPolicy`.
- There is no dedicated clarification gate or new governance boundary.
- K4.2 is not superseded.

This architectural Option C is not containment Option C. Keep the names and decisions distinct.

Do not add a new gate, move the governance boundary, change detector placement, alter the established compilation sequence, or change K4.2 to make implementation easier.

#### 3.2 Response-path disposition for this remediation

For this remediation, retain the K4.2 pairing requirement: **a detector-specific clarification question may be surfaced only when it is accompanied by a concrete, truthful representation of the interpreted intent and a genuine provisional plan.**

Implement the C-plus response design:

- **Option A:** not selected; it removes the plan.
- **Option B:** not selected; it removes the plan and echoed interpretation.
- **Option C-plus:** selected for implementation; it displays no more than three genuine plan steps, corrects formatting, represents the intent honestly, and asks an artifact-appropriate question.
- **Option D:** not selected; it leaves the response defects in place.

C-plus is an owner-directed implementation disposition for this remediation. It extends historical containment candidate C; it was not selected by the historical experiment. Record its provenance and actual decision date accurately. Do not backdate it, imply it was part of Moncif's September 29 architectural decision, or claim that the entire ADR has been accepted.

A missing or unusable plan must not result in an unpaired detector-specific question. In that case use the defined safe failure response in §5.4.

#### 3.3 Reconcile all active documentation, including the debt register

The existing October 17 correction withdrawing the unsupported A/B claim must remain intact.

In the decision-record PR:

- Add the current response-path disposition and cross-reference it from the relevant ADR/result-record sections.
- Explicitly mark the old “remaining owner decision is whether pairing applies” passage as historical and superseded for this response path. Do not leave it as an unqualified active statement.
- Preserve the original experimental evidence, thresholds, individual criteria and verdicts.
- Update the DEBT-043 description/disposition text in `KNOWN_ISSUES.md` so it no longer says the A–D choice is undecided.
- Keep **DEBT-043 status OPEN** in this PR. Recording a selected remediation is not the same as verifying the implementation or closing the debt.
- Add a concise current-state synchronization note in `CURRENT_STATE.md` if needed, without rewriting unrelated historical material.

Keep DEBT-042 open as well.

The product implementation PRs must leave debt-status bookkeeping unchanged. The later closure-documentation PR is responsible for changing statuses only when the merge and acceptance evidence justify closure.

The ADR remains **PROPOSED**. D-1 through D-4 and all unrelated dispositions retain their current states. Do not declare freeze readiness.

#### 3.4 Record the residual product risk honestly

The repeated-run experiment observed generic and occasionally over-assumptive planning steps. C-plus reduces what is displayed; it does **not** prove the remaining steps are semantically appropriate, nor establish that users benefit from seeing them.

The response must label the plan as provisional. Record the remaining risk: a genuine planner-generated step can still contain generic, unsuitable or unrequested process assumptions. Do not describe the plan as independently verified, semantically validated, or user-approved.

Do not add

*(Part 1 ends here, mid-sentence.)*

---

## PART 2 (received second: "this is the continuation to the prompt")

### Completion of §3.4 — Residual product risk

Do not add a new semantic-validation subsystem, claim that the detector validates planner-step quality, or treat a successful response-rendering test as evidence that the proposed plan is appropriate. Keep the implementation narrow and preserve this residual risk in the decision record.

### 4. DEBT-042 — FTS5 query-syntax correction

Implement DEBT-042 in its own implementation and test PR, based on the freshly verified live `main`.

#### 4.1 Required behavior

Correct `SQLiteStorageBackend.search_text()` query construction so that user-supplied search text is treated as literal search content rather than partially interpreted FTS5 query syntax.

Inspect `_fts_escape()` and the complete query path before modifying it. Use the actual SQLite FTS5 grammar and tokenizer behavior to select a correct quoting and escaping strategy. The earlier investigation found that quoting tokens and doubling embedded double quotes eliminated syntax errors across 14 representative queries; treat this as a useful starting point, not a substitute for validating the final implementation.

Requirements:

- Handle FTS5 syntax characters, embedded quotes, whitespace, punctuation, Unicode, and combinations of these without producing malformed MATCH expressions.
- Keep SQL parameter binding. FTS5 query escaping and SQL injection prevention are separate requirements; neither may be substituted for the other.
- Preserve the documented search contract, including the existing term-matching semantics to the extent possible. Document any unavoidable semantic change rather than silently introducing phrase-search or operator behavior.
- Handle empty and punctuation-only inputs according to the established caller contract.
- Preserve the existing memory-retrieval architecture, result structure, ranking behavior, and vector-retrieval fallback. Do not modify unrelated database schemas, FTS triggers, migrations, or indexing policies.
- Do not hide unrelated database failures behind broad exception handling. Preserve the existing failure and fallback behavior except where a narrow change is demonstrated to be necessary.
- Do not modify DEBT-042's status in the implementation PR.

#### 4.2 Required tests

Add regression tests at the lowest useful layer and at the relevant integration boundary.

Cover ordinary terms and multiword queries; quotation marks; parentheses; colons; asterisks; carets; hyphens; Boolean keywords; NEAR expressions; punctuation; Unicode; empty input; punctuation-only input; and realistic combinations of special characters.

For each test, assert the expected search behavior, not merely the absence of an exception. Where applicable, establish that a literal-looking query cannot turn into an unintended FTS5 operator or broaden the search unexpectedly.

Re-run the previously documented 14-query reproduction set against the final implementation and record the SQLite runtime version. Add cases where needed to close gaps identified by the new implementation.

Verify all relevant callers of `SQLiteStorageBackend.search_text()` and `UnifiedMemory.search()`. Confirm that repairing the FTS5 path does not suppress failures, change the vector-retrieval leg, or introduce regressions into the combined retrieval path.

Keep test fixtures hermetic, use the existing test conventions, and record any tracked-file mutations caused by tests.

### 5. DEBT-043 — Truthful, bounded clarification response

Implement DEBT-043 in a separate implementation and test PR. Keep this work independent of the DEBT-042 implementation branch and do not rely on merging either PR first.

#### 5.1 Preserve K4.2 and C-plus

Implement the response-path disposition established in §3.2 without modifying ADR-KERNEL-07's architectural D-5 decision.

The response must contain a truthful representation of the interpreted intent, a genuine provisional plan, and an artifact-appropriate clarification question. Do not present a raw echo of the user's request as though it were an independent interpretation.

Derive displayed content from the actual available intent and plan data. Do not invent an interpretation, introduce a subject or premise the user did not provide, fabricate plan steps, or make another model call merely to produce more persuasive response text.

#### 5.2 Display no more than three genuine plan steps

Use C-plus for presentation:

- Display at most three steps that genuinely exist in the planner-produced plan.
- Preserve their order.
- Correct the current punctuation and formatting defect. Prefer separate numbered lines or another unambiguous structured representation over joining numbered sentences into malformed punctuation such as `step.; 2. step`.
- Preserve the distinction between an execution plan and its presentation. Do not mutate the underlying execution plan or silently change runtime behavior simply to limit the response text.
- Label the displayed plan explicitly as **provisional**.
- Do not imply that the plan has been independently verified, semantically validated, or approved by the user.
- Never pad a short plan to reach three steps, fabricate missing steps, or describe omitted steps as though they were displayed.
- Do not describe generic workflow steps as though they established a concrete artifact subject, genre, setting, premise, or other intent not actually supported by the request.

The existing planner and governance sequence must remain intact. The implementation must not introduce an additional governance evaluation, clarification gate, or execution boundary.

#### 5.3 Ask an artifact-appropriate question

Replace the universal, story-specific example with wording appropriate to the recognized artifact type. Examples of intended behavior include:

- Story: ask what the story should be about, optionally inviting a genre or tone.
- Poem: ask for a subject, theme, or mood.
- Essay: ask which topic or question the essay should address.
- Song: ask about its subject or desired mood.
- Joke: ask about a topic or whether the user would like the system to choose one.

These are behavioral examples, not a requirement for a new hard-coded artifact taxonomy. Follow the existing intent and artifact-recognition capabilities where possible. Include a generic fallback for other supported artifact types.

Questions must remain neutral and must not presuppose an unrequested subject, setting, research requirement, genre, process, or other substantive choice. Do not promise a quality or result that the current system cannot establish.

#### 5.4 Safe failure when the required pairing cannot be produced

**This subsection is a proposed replacement specification because the original §5.4 was not preserved in the accessible records. It must not be represented as recovered original wording.**

The implementation must fail safely if it cannot produce a usable, truthful representation of the interpreted intent and at least one genuine, displayable plan step.

In that case:

- Do not return the normal C-plus response with its detector-specific clarification question.
- Do not display a fabricated, empty, malformed, or misleading plan.
- Do not fall back to the existing defective response simply to preserve output availability.
- Do not alter the underlying task, execute an unverified substitute plan, or introduce another governance decision.
- Return a stable, generic failure response that does not falsely claim to have interpreted the request or constructed a valid plan.

Proposed generic wording:

> I couldn't form a reliable draft plan for this request. Please restate what you'd like me to create and include any details you already know.

Treat this as a safe presentation failure, not successful completion of the clarification workflow. Keep the response bounded, avoid leaking internal exception details, and preserve the existing outcome and event contracts.

If the real integration path has no suitable way to represent this outcome, inspect the relevant contract and make the smallest justified change. Document and test any contract change rather than silently converting failure into success or adding a new governance gate.

#### 5.5 Required regression and integration tests

Test at least:

1. A normal plan with more than three steps: only the first three genuine steps appear in order.
2. Plans containing one, two, and three steps: no padding or fabricated content.
3. An empty plan and a missing plan: safe failure with no detector-specific question.
4. Malformed or unusable step data: no unhandled formatting failure and no unpaired question.
5. An absent, empty, or unusable intent representation: safe failure rather than a fabricated interpretation.
6. Each supported artifact kind: question wording follows the actual artifact without inventing a premise.
7. Missing or generic interpretation data: no claim that an echoed raw request constitutes an independently interpreted intent.
8. Step formatting and punctuation: no duplicated separators, malformed numbering, or empty entries.
9. Feature flag disabled: existing flag-off behavior remains unchanged.
10. Feature flag enabled: C-plus follows the established Orchestrator path and retains the original governance boundary.
11. Other escalation causes: they do not accidentally produce a content-anchor-specific question.
12. Event emission and terminal outcome: remain consistent with the actual result and existing contracts.

Use the real Orchestrator response path in integration tests. Unit tests of a response-formatting helper alone are insufficient. Use controlled test doubles for model-dependent behavior; do not require a live model or external provider for ordinary CI.

Do not weaken, delete, broadly skip, or reclassify existing tests to obtain a passing result. Preserve the existing strict D-4 `xfail` and drift-check requirements.

Do not modify DEBT-043's status in this implementation PR.

### 6. Cross-PR boundaries and architecture reconciliation

Keep the three initial deliverables separate:

1. **Documentation/decision PR:** record the C-plus disposition and correct the applicable ADR, result-record, `KNOWN_ISSUES.md`, and `CURRENT_STATE.md` statements.
2. **DEBT-042 PR:** implement and test the FTS5 correction only.
3. **DEBT-043 PR:** implement and test the response correction only.

The two code PRs must not depend on the documentation PR having been merged. Branch from the verified current base, keep each diff within its declared scope, and do not combine debt fixes merely to reduce PR count.

Before completing each PR, verify that the changes do not overlap unexpectedly with open PRs, particularly PRs #86, #83, #81, and #79. Check their live states and changed files rather than assuming the historical overlap remains current.

Reconcile documentation against actual code and test evidence. Keep prior experimental observations and verdicts intact. Distinguish explicitly between:

- Historical observations.
- The September 29 architectural decision.
- The later owner-directed C-plus implementation disposition.
- Implemented behavior.
- Verified behavior.
- Unresolved residual risk.

The code PRs must not edit unrelated status records or claim debt closure. The ADR remains **PROPOSED**, both debts remain **OPEN** until independently verified and authorized for closure, and kernel freeze readiness remains undeclared.

### 7. Verification and evidence requirements

For each deliverable, record the exact base SHA, tested head SHA, changed-file list, and commands with actual exit codes and test counts.

At minimum, perform:

- Focused regression tests for the relevant debt.
- Relevant integration tests, including the actual response or retrieval boundary.
- The complete applicable project test suite and its CI failure-classification procedure.
- `scripts/check_drift.py`.
- Any repository-required static checks and PR-specific validation.
- A before/after worktree check, including untracked files and tracked-file hashes when tests may mutate fixtures.

Report skipped tests, expected failures, environmental exceptions, and discrepancies between local and CI results. Do not claim that a suite passed when it has untriaged failures or when only targeted tests ran.

A GitHub status response with no checks returned is not evidence of passing CI. Link the actual check runs where available, and distinguish completed local tests from completed remote CI.

Use immutable candidate SHAs for evidence. If source changes after testing, repeat affected tests. If source changes after independent review, obtain another review of the changed candidate.

### 8. Independent review and delivery

Prepare each PR for independent review by a session that did not author the implementation. Supply the exact diff and SHA, governing contract, failure reproduced before the fix, acceptance criteria, test results, environment, residual risks, and any unresolved decisions.

Do not merge any PR in this task. Do not modify `main`, force-push, rewrite shared history, enable the detector by default, or declare the kernel freeze-ready.

After the initial PRs are ready, report:

- The live repository baseline and exact candidate SHAs.
- Links to any branches and PRs actually verified to exist.
- Per-PR scope and changed files.
- Pre-fix reproduction and post-fix regression evidence.
- Local versus remote CI results.
- Independent-review status and any findings still open.
- Known limitations and residual product risk.
- The precise remaining steps for authorized review, merge, post-merge verification, and eventual closure.

A separate closure-documentation PR may be prepared only after the relevant merges have been explicitly authorized and post-merge verification has been completed. Do not close either debt on the strength of a selected design, a passing unit test, or an unmerged implementation.

If a remote write, test environment, or required evidence is unavailable, report the exact limitation and deliver the verified local artifacts and remaining steps. Never claim an operation succeeded unless the result has been observed.

### 9. Final acceptance principle

The remediation is complete for review only when all three initial deliverables have separately scoped, reproducible evidence; the implementation behavior matches the recorded disposition; the real integration boundaries have been exercised; the documentation no longer presents superseded decisions as current; and all remaining limitations are explicit.

Implementation, verification, architectural acceptance, debt closure, and freeze readiness are separate states. Do not infer one from another.
