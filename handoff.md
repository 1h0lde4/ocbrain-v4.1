# Session Handoff — CTX-AUTH-002 / CTX-AUTH-001b (promotion phase)

Written for a session with **none** of the prior conversation. Read §6, §15 and §17 first.

## 1. Handoff Metadata

- Handoff version: 2. **It supersedes an earlier draft that described this work as lost and unbuilt. That draft was never pushed and was wrong** — other sessions had already rebuilt it (see §9). If you find a different handoff text anywhere, trust this file and the repository over it.
- Created: October 12, 2026
- Workstream: replace the merged ADR-KERNEL-06 §8 authority grant (finding **CTX-AUTH-002**), reopen **CTX-AUTH-001b**, and promote the fix to `main`.
- **Phase: implementation is done and approved; what remains is promotion, owner-side review, a real-model run, and a separate Option C study.**
- Transfer status: §19.

## 2. Original Starting Prompt

The workstream began from the decision-maker's review of the adversarial finding. Verbatim:

> What I would do next
> Do not patch the documentation first.
> The correct sequence is:
> 1. Freeze the finding as a regression/security finding.
> Preserve the exact attack, request-agnostic payloads, affected execution path, and observed constraint escalation.
> 2. Reopen CTX-AUTH-001b at the architectural level.
> I would explicitly state that the previous closure mechanism is rejected, not merely "needs strengthening."
> 3. Replace the authority rule, not the token threshold.
> Separate:
> `source reference verified`
> from
> `content grounded`
> from
> `authority`.
> 4. Make the selection boundary fail closed for model-authored hypotheses.
> A citation to the request should not by itself make a hypothesis USER-authoritative.
> 5. Add the regression harness you just demonstrated.
> The important test property is specifically:
> a payload independent of the request can never cause a model proposal to obtain USER authority.
> 6. Only after the new mechanism survives adversarial testing should ADR/CURRENT_STATE/KNOWN_ISSUES be updated back toward closure.
> One especially important point: the existing `verified_operative` name should itself be reconsidered. Under the present architecture it communicates a stronger guarantee than the implementation actually establishes.

**Earlier, larger task (faithful extraction, not verbatim):** an OCBrain "FINAL REM-004 / CTX-AUTH-001b KERNEL FREEZE-BLOCKER IMPLEMENTATION" brief. Requirements that still govern: dedicated branch, never modify or merge `main`; treat prior claims as hypotheses and verify against the live repo; never weaken, delete or xfail the failing test; no stopgap hacks (no keyword lists, no authority trusted from model output, no score-as-authority); authority comes from trusted origin, never from content; information authority is not action authorization and `GovernanceKernel` stays the only action authority; frozen K4.2 contracts change only additively and ADR status is never self-promoted; claim only what is evidenced ("the tested paths are closed", never "injection is impossible"); classify every failure as new regression / pre-existing / environmental. `PROJECT_INSTRUCTIONS.md` §18.4.8 defines this handoff format.

## 3. Subsequent Instructions / Rulings (chronological)

1. Chose to re-implement against the **accepted** ADR-KERNEL-06 (the owner's design) rather than an earlier self-drafted one.
2. Asked for an independent check of the merged work → CTX-AUTH-002.
3. The six-step plan above.
4. **Oct 6, 2026 — Moncif's rulings on Q1–Q6**, recorded in `ADR_KERNEL_08_…` §8 (the verbatim, authoritative text — this file does not restate them; read §8 and §8.1 yourself). The ADR is now **APPROVED, not IMPLEMENTED**.
5. Latest instruction: push the done work and leave a handoff for a fresh session, because the sandbox can reset at any time.

## 4. Goal, Scope & Success Criteria

**Goal:** get the approved fix onto `main` through review, with evidence that holds on `main` itself.
**In scope:** the branch's existing change set (§9); the conditions in ADR-KERNEL-08 §8.1; merging `main` **into the branch**; re-running the gates; preparing the PR.
**Out of scope:** merging to `main`, deleting remote branches, implementing Option C (it is a *study*, not an implementation), changing capability discovery (Q4 was ruled on), reintroducing any authority field or selection gate on grounding.
**Success:** `main` contains the fix; gates re-verified **on the merged result**; ADR-KERNEL-08 moves to IMPLEMENTED only after that; CTX-AUTH-001b closure is *reconsidered on that evidence*, not assumed.

## 5. Requirement Ledger

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| R1 | Freeze the finding | **VERIFIED present** | threat-model doc, CTX-AUTH-002 |
| R2 | Reject (not tune) the closure; reopen 001b | **DONE, APPROVED** | ADR-KERNEL-08; status docs withdrawn Sept 23 claim |
| R3 | Separate verified / grounded / authority | **IMPLEMENTED, tested** | `intent.py` |
| R4 | Selection fails closed; request citation ≠ USER | **IMPLEMENTED, ruled on** | `_select_hypothesis`; Q2 |
| R5 | Regression harness + the step-5 property | **IMPLEMENTED, tested** | `test_intent_security.py`, `live_citation_check.py`, mutation script |
| R6 | Rename `verified_operative` | **IMPLEMENTED** | `citation_grounding`, `selection_basis` |
| R7 | Docs back toward closure only after adversarial testing | **PARTIAL** — withdrawn/reopened and reconciled; closure deliberately **not** claimed | CURRENT_STATE / KNOWN_ISSUES |
| R8 | Owner's independent review of the rewritten `live_citation_check.py` | **OPEN (owner)** | ADR §8.1 |
| R9 | Real-model run of the harness | **OPEN (needs a provider)** | ADR §8.1 |
| R10 | Merge `main` into branch, recheck ADR number, re-run gates | **OPEN** | §15 |
| R11 | Option C study | **OPEN, separate, evaluation only** | none exists |
| R12 | Trace the downstream compile-time gate for the Q4 ruling | **OPEN** | ADR §8 (Q4 note) |

## 6. Current Verified State

Measured **today (Oct 12, 2026)** on the branch tip `18d2705`, in a fresh sandbox:
- Full suite: **2041 passed, 1 xfailed, 0 failed.**
- `scripts/check_drift.py`: **15 / 15 PASS.**
- `scripts/mutation_check_ctx_auth_002.py`: **26 / 26 mutants caught; files byte-identical afterwards.** (17 target the intent/planner logic, 9 the harness.)
- `main` is `4b90ed9`; the branch is **20 commits behind and 14 ahead**.
- A throwaway dry-run merge of `main` into the branch: **one real conflict, `CURRENT_STATE.md`** (`KNOWN_ISSUES.md` auto-merged but must be re-read for semantics).
- ADR number `KERNEL-08` is **still free on `main`** (`01,02,03,04,06,07` are taken; `07` is an unrelated "creative content anchor detector").
- **Nothing from this workstream is on `main`.**

**Not re-run today (the commit messages claim them; re-run before relying on them):** mypy comparison against `main`; the six `live_citation_check.py --dry-run` modes; the A/B/C differential against `main`.

## 7. Git / Repository Checkpoint

- Repo: `github.com/1h0lde4/ocbrain-v4.1` (public; cloning needs no token, **pushing needs one the user supplies**).
- Branch: `fix/ctx-auth-002-reject-content-corroboration-authority-sep2026`
- Implementation tip before this file: `18d2705`. This handoff is the next commit on top of it (`git log -- handoff.md`).
- **Other sessions have pushed to this branch.** Always `git fetch` and rebase/merge before pushing; never force-push. A push of mine was rejected for exactly this reason today.
- **Superseded, do not merge:** `fix/ctx-auth-001b-rem004-authority-boundary-sep2026` @ `cab3c7a`. Deleting it is the owner's call.

## 8. Active Files

`core/cognitive/intent.py`, `core/cognitive/planner.py`, `tests/core/cognitive/test_intent.py`, `test_intent_security.py`, `test_k42_completion.py`, `live_citation_check.py` (the **owner's** file, rewritten), a test file for that harness, `scripts/mutation_check_ctx_auth_002.py`, `docs/architecture/decisions/ADR_KERNEL_08_REJECT_CONTENT_CORROBORATION_AUTHORITY.md`, `ADR_KERNEL_06_…` (reconsideration notice only; §§1–8 untouched), `ADR_INDEX.md`, `KNOWN_ISSUES.md`, `CURRENT_STATE.md`, the remediation register, and the threat-model doc.

## 9. Changes Made (summary; the git log is authoritative)

`IntentHypothesis` lost its `authority` field (now `source`, `source_verified`, `content_grounded`; a model-authored hypothesis is constantly `AuthorityLevel.GENERATED`). `_resolve_source` → `_check_source_grounding`; `_select_operative_hypothesis` removed; new `_select_hypothesis` is a fail-closed, authority-free default (eligible only if it cites `request`, is verified and content-grounded; **never via a block citation**; otherwise the trusted `novel` default). `planner._extract_constraints` reads `description`/`raw_request` only. Events renamed (`citation_grounding`, `selected_citation_grounding`, `selection_basis`); `verified_operative`/`selection_gate`/`authorities` are gone. `live_citation_check.py` measures an end-to-end escalation invariant and fails loudly instead of reporting zeros; the sessions after mine hardened it against vacuous passes and made it judge completeness per declared payload. Status documents withdraw the Sept 23 closure.

## 10. Decisions & Rationale

| ID | Decision | Status | Reopen only if |
|---|---|---|---|
| D1 | Reject the authority grant; do not tune a threshold | **approved** | Moncif overrules |
| D2 | No per-instance authority on a model-authored hypothesis | implemented | an unforgeable mechanism exists |
| D3 | Constraint extraction reads only the verbatim request | implemented | never |
| D4 | Keep a fail-closed, authority-free selection default | ruled on (Q2) | Moncif changes the ruling |
| D5 | Option C is studied, not adopted | ruled on (Q3) | the study recommends it and Moncif approves |

**Why a rejection and not a threshold change:** for `request`, "the cited source exists" is true of every citation, so a lookup verifies nothing; the substitute (token overlap) is a lexical heuristic of the kind ADR-KERNEL-06 §2 forbids; any "N tokens of length ≥ K" test is satisfiable by a longer padded label; and it conflated grounding with authority — a model's classification of the request is a model artifact however well grounded.

## 11. Investigation Already Performed

The vulnerability, its executed reproduction (a request-agnostic padded label obtaining USER authority and a fabricated HARD constraint), why the original verification could not have caught it, and the consumers of the label-derived fields are recorded in the threat-model doc under CTX-AUTH-002 and in ADR-KERNEL-08. **Do not re-derive; read them.**

## 12. Failed Attempts / Dead Ends

Raising the overlap threshold or adding stopwords (only raises attacker cost); removing the selection gate entirely (regressed two payload classes `main` protected); collapsing multiple uncited candidates to `novel` (breaks pinned `test_uses_provider_completion`); label-shape rules (forbidden by ADR-KERNEL-06); "always fall back to novel" (disables inference). Process dead ends: blanket regex renames can turn a deliberately-malformed test value into a valid one; `fold`/`rev` on very long table rows hangs the shell (use Python); a verification script once ran against the wrong tree because `PYTHONPATH` was unset.

## 13. Verification Evidence

Commands used: `python3 -m pytest tests -q -p no:cacheprovider --timeout=90 -rfE`; `python3 scripts/check_drift.py --out X.json`; `python3 scripts/mutation_check_ctx_auth_002.py`. For mypy, compare **error sets** against a pristine `main` worktree ignoring line numbers (`--follow-imports=silent --ignore-missing-imports --no-error-summary --python-version 3.12 --explicit-package-bases`, `MYPYPATH=.`, then `sed -E 's/:[0-9]+: /: /' | sort` and `comm -13`). Results: §6.

## 14. Environment / Tooling Assumptions

- **The sandbox is ephemeral and has reset once already, destroying an unpushed branch.** Push after every meaningful step.
- Install: `pip install --break-system-packages pytest pytest-asyncio pytest-timeout chromadb pyyaml httpx aiofiles aiohttp pydantic requests rich click fastapi scipy datasketch beautifulsoup4 feedparser trafilatura mypy tomli tomli-w`.
- **Running the tests modifies tracked files** (`config/*.toml`, `data/context.sqlite`, `modules/*/knowledge.db/chroma.sqlite3`). Run `git checkout -- config data modules` before committing.
- Every tool call starts in a fresh cwd: `cd /home/claude/ocbrain &&` each time.
- **Secrets:** none are recorded here. The push token was pasted into chat and the project file `github.env` holds another; **both should be rotated.** Use a token via an env var, redact output, unset it afterwards.

## 15. Unresolved Questions / Risks / Blockers

- **Promotion is blocked on the owner and on a real model**, not on code: the rewritten harness needs Moncif's independent review (R8), and a real-provider run (R9) needs a machine with a configured `intent_interpreter` provider (not available in the sandbox). Do not claim either is done.
- **R12:** the Q4 ruling kept capability discovery as is; the downstream compile-time gate that makes that safe was **not traced** — ADR §8 says so.
- **Residual risk to keep stating:** a label padded with common words can still win the *advisory* category hint (consumers: the `novel` planner hint and capability-discovery text). It cannot reach a user-authority field or an EXPLICIT constraint.
- `main` moves quickly and the shared docs conflict (see §6). The ADR number can be taken by another session at any time.
- Risk of concurrent sessions on one branch: duplicated or clobbered work.

## 16. Relevant Information / References

ADR-KERNEL-08 §8 (rulings) and §8.1 (conditions for promotion); ADR-KERNEL-06 §§2, 6, 8; the CTX-AUTH-002 entry in `docs/research/context-engineering/context-authority-threat-model.md`; `live_citation_check.py`; `scripts/mutation_check_ctx_auth_002.py`; `PROJECT_INSTRUCTIONS.md`.

## 17. Next Steps (in order; push after each)

1. **Verify** the checkout: `git fetch`; confirm `18d2705` is an ancestor of the remote branch; reinstall dependencies; reproduce the §6 numbers (2041 passed / 1 xfailed, drift 15/15, mutation 26/26).
2. **Merge `main` INTO the branch** (never the reverse). Expect a conflict in `CURRENT_STATE.md`: take `main`'s text and re-apply only this workstream's entries; re-read `KNOWN_ISSUES.md` for semantic conflicts. First re-check that `ADR_KERNEL_08` is still free; renumber **before** merging if not.
3. **Re-run every gate on the merged result**: full suite (and compare to a freshly measured pristine-`main` baseline), drift, mypy error-set comparison, the mutation script, all six `live_citation_check.py --dry-run` modes (a regressed planner must exit 1, a renamed event field exit 2), and the A/B/C differential against `main`. Update the evidence statements in ADR-KERNEL-08 and `CURRENT_STATE.md` with **new** numbers, never copied ones.
4. **Tell the user** what is blocked on them: the harness review (R8) and a real-model run (R9, with the exact command `python3 live_citation_check.py --requests 10 --trials 3 --json out.json` and how to read it: `ESCALATED` must be 0; exit 1 = invariant failed, exit 2 = results incomplete).
5. **PR:** open one only when asked. Do not merge it.
6. **R12 and R11** can proceed independently: trace the compile-time gate; write the Option C *study* (cost in N+1 completions, latency, what unforgeability it would actually buy). Evaluation only.
7. After merge to `main` (by the owner): re-verify on `main`, then — and only then — propose ADR-KERNEL-08 → IMPLEMENTED and a reconsideration of CTX-AUTH-001b closure, as proposals.

## 18. Resume Instructions

Fetch, verify the tip, read ADR-KERNEL-08 §8/§8.1 yourself, then start at step 2. Do not rebuild anything that exists. Do not reintroduce `IntentHypothesis.authority`, a gate on grounding, `verified_operative`, or a threshold tweak. Do not mark ADR-KERNEL-08 implemented or CTX-AUTH-001b closed.

## 19. Transfer Status

**TRANSFER READY** — all implementation work is committed and on the remote, this file included once it is pushed (confirm with `git ls-remote`). The *workstream* is not finished: §15 lists what is blocked on the owner, a real model, and the promotion process.
