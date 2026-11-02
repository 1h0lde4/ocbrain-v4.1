# OCBrain — Live Debt, PR and Branch Ownership Register

**Snapshot time:** 2026-11-02 (GitHub API snapshot)
**Canonical baseline:** `main` @ `2491ae469edd6ef1267a14604c4f8f40d698f7ea` (merge PR #106)
**Inventory:** 111 remote branches; 19 open PRs; 3 open non-PR issues.
**Purpose:** one operational map of debt status, active review targets, preserved work and ownership gaps. This is a documentation/governance record, not implementation authorization.

## 1. Ownership rules

1. **Main is the only implementation baseline.** A branch, green CI run, PR description or local review report does not constitute merged product behavior.
2. **PR author is provenance, not owner assignment.** GitHub showed zero assignees on all 19 open PRs in this snapshot. Most implementation PRs were authored by `1h0lde4`; that does not, by itself, assign implementation ownership.
3. **No inference from branch names or last committers.** An unassigned branch remains UNASSIGNED until an explicit person is named in the PR/issue or this register.
4. **One canonical implementation candidate per debt.** Parallel repair branches are preserved but cannot all be treated as active. Select one exact head, owner and review target before new work proceeds.
5. **Decision owner and implementation owner are distinct.** The repository owner is the decision authority for owner-level design choices. Implementation ownership remains UNASSIGNED where no explicit assignment exists.
6. **No implicit cleanup.** This record does not delete branches, close PRs, rebase branches, alter assignees, accept ADRs, or authorize merges.

## 2. Current debt/workstream ownership map

| Workstream / debt | Live state on main | Canonical PR / branch | Implementation owner | Next control point |
|---|---|---|---|---|
| FZ-01 | OPEN; K4.2/API failure channel not implemented | PR #83 is decision documentation only; no implementation PR | UNASSIGNED | Carry D1 result contract into main documentation, then authorize separate implementation batch |
| FZ-02 | PARTIAL; #67 provider failure, #71 stall/deadline and #104 router cleanup merged; residual outcome/cancellation semantics remain | Issue #105; unreviewed branch `follow-up/fz02-b2d-latent-token-cancellation-oct2026`; no PR | UNASSIGNED | Owner must decide Worker cancellation contract; do not equate router cleanup with workflow cancellation |
| FZ-05 | OPEN; registry eviction and EventStream retention unresolved | No canonical branch or PR | UNASSIGNED | D3/retention decision before implementation |
| FZ-06 / DEBT-030 | OPEN; identity not joinable across event/capability boundaries | PR #87 is documentation-only; no implementation PR | UNASSIGNED | Define canonical identity contract and reconcile D1/FZ-01 dependency |
| FZ-07 / R-1 | Core CI gate FIXED; R-1 OPEN | PR #107 diagnostic-only; NOT FOR MERGE | UNASSIGNED | Preserve NOT APPROVED attestation for original Batch 1; resolve R-1 independently |
| G4 / DEBT-042 | G4 OPEN, High, freeze-blocking; FTS query escaping issue also OPEN | REV2 `docs/g4-fts-errata-handoff-oct2026` is current handoff/report-of-record branch for Addendum 1; REV3 PR #90 is a separate doc checkpoint | Decision owner: repository owner; implementation owner UNASSIGNED | D1-D11 remain OPEN; no product fix authorized; reconcile REV3 with REV2 before selecting one continuation entry point |
| DEBT-012 | OPEN; test config/root isolation and test-side-effect guard not merged | PR #91 is the only open PR candidate; three competing `repair/debt-012-*` branches also exist | UNASSIGNED | PR #91 is 90 ahead / 96 behind main, exact-head CI green, no human approval; select/rebuild one canonical head before review |
| DEBT-014 | OPEN; DRIFT-10 Learning-boundary remediation not merged | PR #102 / `fix/debt-014-consolidated-oct2026` is sole current candidate | UNASSIGNED | Head is 7 ahead / 37 behind main; checks green, mergeable=false, no human approval/assignee; reconcile/rebase before review |
| DEBT-025 | OPEN on main; API still unauthenticated | PR #94 / `fix/debt-025-api-auth-boundary-oct2026` | UNASSIGNED | Current with main (17 ahead / 0 behind); checks green except neutral Graphify; no human review/assignee; PR explicitly says merge not requested; authorization remains open after authentication |
| DEBT-028 | OPEN / DEFERRED; deployment-boundary locking requirement remains | PR #81 / `fix/debt-028-workflow-runtime-concurrency-lock-3172688588772460252` | UNASSIGNED | PR is 13 ahead / 96 behind and non-mergeable; an in-process lock alone does not settle cross-process coordination |
| DEBT-043 | OPEN; owner selected C-plus, implementation absent | PR #88 is documentation-only decision record | UNASSIGNED | C-plus recorded 2026-10-19; implementation and verification require a separate authorized branch |
| DEBT-018 | OPEN / non-integrated Verification/Critic/Evidence Phase C contracts | `feature/verification-critic-evidence-phase-c`, no PR | UNASSIGNED | Current tip 61 ahead / 267 behind main; package is not a production verification engine; Batch 3C-B remains design-blocked |
| DEBT-021/039/040/041 | OPEN; Sandbox Fabric incomplete; B03 primitives inert | PR #86 / `sandbox-network-isolation/b03-capacity-ipv6-guards`; target is B01 base, not main | UNASSIGNED | B03 does not wire guards into DockerBackend or close network-isolation findings; no main integration authorization |
| Issue #105 | OPEN; task cancellation is converted into ordinary failure and retried | `follow-up/fz02-b2d-latent-token-cancellation-oct2026`, no PR | UNASSIGNED | Cancellation contract not decided; issue has no assignee |
| Issue #65 | OPEN; Chroma dependency declaration compatibility | No active implementation PR selected | `1h0lde4` (issue assignee) | Retain 0.5.3 owner boundary pending compatibility study; PR #33 is not approved |
| Issue #70 | OPEN; sentence-transformers advisory exposure assessment | PR #32 is not a sufficient fix/decision | `1h0lde4` (issue assignee) | Complete compatibility/exposure study; advisory status remains open |
| CTX-AUTH-001b / REM-004 | OPEN; separate authority-boundary decision after qualified CTX-AUTH-002 closure | Historical branches are preserved; no accepted active implementation PR | Decision owner: repository owner; implementation owner UNASSIGNED | Do not infer closure from PR #93/#106; separate owner decision required |

## 3. Open PR inventory and disposition

All listed PRs were open at snapshot time. Assignees were empty in GitHub for every PR. Exact-head check states are included only where read in this pass; checks are not human review.

| PR | Head / base | Current disposition | Owner / review |
|---|---|---|---|
| #107 | `fix/ci-gate-r1a-hardening-oct2026` → main | DRAFT; diagnostic CI only; NOT FOR MERGE; original Batch 1 attestation NOT APPROVED | Author `1h0lde4`; no assignee or human review |
| #103 | `architecture/ocbrain-v2-unified-cognitive-runtime-roadmap-oct2026` → main | Architecture proposal, not a debt fix; 1 ahead / 37 behind | Author `1h0lde4`; no assignee |
| #102 | `fix/debt-014-consolidated-oct2026` → main | DEBT-014 canonical candidate; 7 ahead / 37 behind; 5/5 checks success; GitHub mergeable=false | Author `1h0lde4`; no assignee, no human review |
| #94 | `fix/debt-025-api-auth-boundary-oct2026` → main | DEBT-025 candidate; 17 ahead / 0 behind; 6 checks success + 1 neutral; PR says merge not requested | Author `1h0lde4`; no assignee, no human review |
| #92 | Dependabot setup-python 7.1.0 → main | Open automation PR on old base; re-evaluate against current CI/runtime policy | Dependabot bot; no human assignee |
| #91 | `fix/debt-012-test-config-isolation-oct2026-16508008999830840178` → main | DEBT-012 candidate; 90 ahead / 96 behind; 5/5 checks success; stale base | Author `1h0lde4`; no assignee, no human approval |
| #90 | `docs/g4-fts-correctness-handoff-rev3-oct2026` → main | DRAFT documentation-only REV3 checkpoint; 3 ahead / 96 behind; reconcile with REV2 Addendum 1 | Author `1h0lde4`; no assignee/review |
| #88 | `docs/response-path-disposition-c-plus-oct2026` → main | DEBT-043 C-plus decision record only; 1 ahead / 96 behind; stale base | Author `1h0lde4`; no assignee/review |
| #87 | `docs/register-debt033-debt030-oct2026` → main | DEBT-030/033 documentation-only corrections; 1 ahead / 96 behind | Author `1h0lde4`; no assignee/review; enforce_admins assertion needs fresh independent check |
| #86 | `sandbox-network-isolation/b03-capacity-ipv6-guards` → `sandbox-network-isolation/b01-base` | Inert B03 primitives; 72 ahead / 146 behind main; not integrated into product | Author `1h0lde4`; no assignee/review |
| #83 | `docs/fz-freeze-decision-register-oct2026` → main | FZ-D1/D2 decision documentation; 2 ahead / 104 behind; not merged to main | Author `1h0lde4`; no assignee/review |
| #81 | `fix/debt-028-workflow-runtime-concurrency-lock-3172688588772460252` → main | DEBT-028 stale proposal; 13 ahead / 96 behind; mergeable=false; not cleared for merge | Author `1h0lde4`; no assignee/review |
| #79 | `security/privacy-wipe-containment-oct2026` → main | Latent wipe sink hardening; 4 ahead / 104 behind; mergeable=false; no production caller identified | Author `1h0lde4`; no assignee/review |
| #77 | Dependabot upload-artifact 7.0.2 → main | Open automation PR on old base; reevaluate before merge | Dependabot bot; no human assignee |
| #76 | Dependabot download-artifact 8.0.2 → main | Open automation PR on old base; reevaluate before merge | Dependabot bot; no human assignee |
| #33 | Dependabot ChromaDB 1.5.9 → main | Conflicts with current owner decision to retain 0.5.3 pending compatibility study; do not merge | Dependabot bot; no human assignee |
| #32 | Dependabot sentence-transformers range → main | Does not close issue #70 or establish a tested compatible release; do not treat as security closure | Dependabot bot; no human assignee |
| #30 | Dependabot checkout 7.0.1 → main | Open automation PR on old base; reevaluate before merge | Dependabot bot; no human assignee |
| #27 | Dependabot release-action 3.0.3 → main | Open automation PR on old base; reevaluate before merge | Dependabot bot; no human assignee |

## 4. Open non-PR issues

| Issue | Status | Assignment | Branch / PR relationship |
|---|---|---|---|
| #105 — Worker cancellation is retried | OPEN | No assignee | Follow-up B2d branch exists, no PR; contract undecided |
| #70 — sentence-transformers advisory | OPEN | `1h0lde4` | PR #32 does not close assessment |
| #65 — Chroma dependency contract | OPEN | `1h0lde4` | PR #33 conflicts with 0.5.3 owner decision |

## 5. Complete remote-branch inventory

Every branch returned by GitHub's two-page branch listing is included below. The owner field distinguishes a real GitHub assignee from authorship or mere retention. A retained ref is not an active task.

| Branch | Head | Disposition | Owner / assignment |
|---|---|---|---|
| `architecture/ocbrain-v2-unified-cognitive-runtime-roadmap-oct2026` | `b83d9da9` | Open PR #103; [Proposal] OCBrain v2 unified cognitive runtime and roadmap. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `archive/fix-debt-020-completion-semantics-sep2026` | `fcd3700f` | Archived historical branch; no active work owner. | UNASSIGNED / NOT RECORDED |
| `archive/pr-03-fix-adaptive-semaphore-instability-jun2026` | `601b833e` | Archived historical branch; no active work owner. | UNASSIGNED / NOT RECORDED |
| `archive/pr-04-systematic-audit-jul2026` | `7150a4ba` | Archived historical branch; no active work owner. | UNASSIGNED / NOT RECORDED |
| `archive/pr-05-bug-research-hardening-jul2026` | `3da834e6` | Archived historical branch; no active work owner. | UNASSIGNED / NOT RECORDED |
| `archive/pr-06-github-release-automation-aug2026` | `6e718580` | Archived historical branch; no active work owner. | UNASSIGNED / NOT RECORDED |
| `audit/freeze-remediation-batch0-oct2026` | `51318e40` | Audit evidence/reference branch; no active implementation owner recorded. | UNASSIGNED / NOT RECORDED |
| `audit/kernel-v1-0-definitive-freeze-sep2026` | `94b4eef6` | Audit evidence/reference branch; no active implementation owner recorded. | UNASSIGNED / NOT RECORDED |
| `audit/kernel-v1-freeze-blockers-12407359760497844566` | `abe37264` | PR #22 closed unmerged; retained reference only; not an active work owner. | UNASSIGNED / NOT RECORDED |
| `audit/kernel-v1-remaining-freezing-blockers-486744888107768061` | `57f053f3` | PR #25 closed unmerged; retained reference only; not an active work owner. | UNASSIGNED / NOT RECORDED |
| `chore/live-check-runbook` | `4e0bb9d3` | Merged through PR #45 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `dependabot/github_actions/actions/checkout-7.0.1` | `fe93a400` | Open PR #30; build(deps): bump actions/checkout from 4.4.0 to 7.0.1. | Dependabot bot; human assignee: NONE |
| `dependabot/github_actions/actions/download-artifact-8.0.2` | `1291f992` | Open PR #76; build(deps): bump actions/download-artifact from 4.3.0 to 8.0.2. | Dependabot bot; human assignee: NONE |
| `dependabot/github_actions/actions/setup-python-7.1.0` | `2f074910` | Open PR #92; build(deps): bump actions/setup-python from 5.6.0 to 7.1.0. | Dependabot bot; human assignee: NONE |
| `dependabot/github_actions/actions/upload-artifact-7.0.2` | `53a6e821` | Open PR #77; build(deps): bump actions/upload-artifact from 4.6.2 to 7.0.2. | Dependabot bot; human assignee: NONE |
| `dependabot/github_actions/softprops/action-gh-release-3.0.3` | `bfa83b44` | Open PR #27; build(deps): bump softprops/action-gh-release from 2.6.2 to 3.0.3. | Dependabot bot; human assignee: NONE |
| `dependabot/pip/chromadb-1.5.9` | `c0da559b` | Open PR #33; build(deps): bump chromadb from 0.5.3 to 1.5.9. | Dependabot bot; human assignee: NONE |
| `dependabot/pip/sentence-transformers-gte-3.0.0-and-lt-7.0` | `0c5817d2` | Open PR #32; build(deps): update sentence-transformers requirement from <4.0,>=3.0.0 to >=3.0.0,<7.0. | Dependabot bot; human assignee: NONE |
| `docs/adr-kernel-07-state-reconciliation-oct2026` | `6ce4e837` | PR #82 merged; documentation record. | UNASSIGNED / NOT RECORDED |
| `docs/b10-fz-remediation-reconcile-oct2026` | `5e173d4a` | PR #57 merged; documentation record. | UNASSIGNED / NOT RECORDED |
| `docs/codeql-clean-import-boundary-oct2026` | `40bbfff6` | Merged through PR #58 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `docs/ctx-auth-002-closure-oct2026` | `8ceadd18` | PR #106 merged; CTX-AUTH-002 qualified closure. | UNASSIGNED / NOT RECORDED |
| `docs/d11-closure-evidence` | `602d4755` | Merged through PR #69 into sandbox-fabric; retained reference only. | UNASSIGNED / NOT RECORDED |
| `docs/debt-020-prior-art-ref-correction-oct2026` | `6d8980ca` | Merged through PR #52 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `docs/debt-038-status-sep2026` | `c1126137` | Merged through PR #38 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `docs/debt-044-resolution-oct2026` | `c228f169` | PR #96 merged; DEBT-044 record. | UNASSIGNED / NOT RECORDED |
| `docs/debt-register-live-reconciliation-nov2026` | `2491ae46` | Current documentation-reconciliation branch; proposed PR #108; no product implementation. | UNASSIGNED / NOT RECORDED |
| `docs/debt037-closure-debt032-boundary-oct2026` | `8284149e` | PR #66 merged; documentation record. | UNASSIGNED / NOT RECORDED |
| `docs/exception-redaction-register-oct2026` | `cc01a619` | PR #43 merged; documentation record. | UNASSIGNED / NOT RECORDED |
| `docs/fz-freeze-decision-register-oct2026` | `dda84f29` | PR #83; FZ-D1/D2 decision record only; not merged to main. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `docs/g4-fts-correctness-handoff-rev3-oct2026` | `9407db5a` | PR #90 documentation snapshot; preserve as evidence, reconcile with REV2/Addendum 1 before choosing a single continuation entry point; not implementation. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `docs/g4-fts-errata-handoff-oct2026` | `d963daa5` | Current REV2 documentation/handoff branch; latest owner-directed Addendum 1 is the report of record for this step; D1-D11 remain OPEN; no implementation authorization. | UNASSIGNED / NOT RECORDED |
| `docs/known-issues-debt-039-debt-021` | `d379352e` | PR #47 merged; documentation record. | UNASSIGNED / NOT RECORDED |
| `docs/known-issues-debt-040-host-local-services` | `cf68b5a0` | PR #48 merged; documentation record. | UNASSIGNED / NOT RECORDED |
| `docs/known-issues-debt-041-capability-dropping` | `fa6afcc8` | PR #49 merged; documentation record. | UNASSIGNED / NOT RECORDED |
| `docs/network-isolation-spec-and-studies` | `8847ccd1` | Merged through PR #72 into sandbox-fabric; retained reference only. | UNASSIGNED / NOT RECORDED |
| `docs/register-65-70-decisions-oct2026` | `35693996` | PR #74 merged; record of owner decisions on dependency pins/advisory. | UNASSIGNED / NOT RECORDED |
| `docs/register-debt033-debt030-oct2026` | `917bb373` | PR #87; documentation-only; branch-protection state needs fresh maintainer verification. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `docs/response-path-disposition-c-plus-oct2026` | `e634c410` | PR #88; records C-plus selection for DEBT-043; no product implementation. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `docs/result-record-compare-json-wording` | `9491fb90` | Merged through PR #80 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `docs/withdraw-d5-ab-conformance-claim-oct2026` | `788acd19` | PR #85 merged; historical decision correction. | UNASSIGNED / NOT RECORDED |
| `eval-lab/research-and-architecture` | `c2189adf` | Retained/unclassified branch; no active owner or PR mapping recorded. Do not delete without owner decision. | UNASSIGNED / NOT RECORDED |
| `feature/capability-foundation-mission1` | `307cf63e` | Feature/proposal branch without an open PR mapping; not considered integrated; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `feature/intent-sufficiency-slice1` | `7acbf3ce` | Merged through PR #41 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `feature/verification-critic-evidence-phase-c` | `3ba858a2` | DEBT-018 / Phase C contracts; unmerged, no PR; 61 ahead / 267 behind main; package-level work, not production integration. | UNASSIGNED / NOT RECORDED |
| `fix/answer-text-error-redaction-sep2026` | `8cae589c` | Merged through PR #39 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/chromadb-pin-oct2026` | `c9662cd0` | Merged through PR #73 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/ci-gate-r1-structured-report-oct2026` | `667cb94d` | Retained fix branch with no current open PR mapping; check merged/closed lineage before reuse; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `fix/ci-gate-r1a-hardening-oct2026` | `a0c12b58` | PR #107; diagnostic only; NOT FOR MERGE. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `fix/codeql-remaining-stack-trace-flows-sep2026` | `e19d2e3e` | Merged through PR #36 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/ctx-auth-001-ctx-delete-001-sep2026` | `a4206423` | Retained fix branch with no current open PR mapping; check merged/closed lineage before reuse; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `fix/ctx-auth-001b-rem004-authority-boundary-sep2026` | `cab3c7a4` | Retained fix branch with no current open PR mapping; check merged/closed lineage before reuse; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `fix/ctx-auth-002-reconciled-remediation-oct2026` | `396e3745` | PR #93 merged; ADR-KERNEL-08 remediation baseline. | UNASSIGNED / NOT RECORDED |
| `fix/ctx-auth-002-reject-content-corroboration-authority-sep2026` | `91d338ff` | Retained fix branch with no current open PR mapping; check merged/closed lineage before reuse; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `fix/ctx-scope-001-packet-b-sep2026` | `e1a5b4dd` | Retained fix branch with no current open PR mapping; check merged/closed lineage before reuse; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `fix/d11-destroy-causal-classification` | `62ffbd04` | Merged through PR #68 into sandbox-fabric; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/debt-003-crash-restart-evidence-oct2026` | `e721960e` | Merged through PR #97 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/debt-012-test-config-isolation-oct2026-16508008999830840178` | `68cc469a` | PR #91 candidate, but stale. Three competing repair/* branches exist; no canonical repair selection; no owner assignment. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `fix/debt-014-consolidated-oct2026` | `74e6f0d6` | PR #102; current canonical DEBT-014 review target, but stale/non-mergeable and unassigned. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `fix/debt-014-drift10-learning-boundary-oct2026` | `45633637` | Earlier DEBT-014 candidate; PR #98 closed unmerged; superseded by consolidated PR #102. | UNASSIGNED / NOT RECORDED |
| `fix/debt-014-drift10-learning-boundary-oct2026-5777447058067279164` | `41bc4ad2` | Earlier DEBT-014 candidate; PR #99 closed unmerged; superseded by consolidated PR #102. | UNASSIGNED / NOT RECORDED |
| `fix/debt-014-final-deep-review-oct2026` | `268c1c41` | Earlier DEBT-014 candidate; PR #101 closed unmerged; superseded by consolidated PR #102. | UNASSIGNED / NOT RECORDED |
| `fix/debt-014-final-review-handoff-oct2026` | `0a9a67d2` | Earlier DEBT-014 candidate; PR #100 closed unmerged; superseded by consolidated PR #102. | UNASSIGNED / NOT RECORDED |
| `fix/debt-025-api-auth-boundary-oct2026` | `3300f937` | PR #94; current DEBT-025 candidate, current with main; no assignee or human approval; merge not requested. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `fix/debt-028-workflow-runtime-concurrency-lock-3172688588772460252` | `647b63e7` | PR #81; stale/non-mergeable; no merge until deployment-boundary contract and cross-process implications are resolved. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `fix/debt-029-context-persistence-failure-isolation-oct2026-4372039021546723617` | `36b3f01e` | PR #89 merged; implementation later separated into DEBT-044/DEBT-029 records. | UNASSIGNED / NOT RECORDED |
| `fix/debt-029-resolution-oct2026` | `d7c983d3` | PR #95 merged; DEBT-029 resolution review record. | UNASSIGNED / NOT RECORDED |
| `fix/distill-module-name-validation-sep2026` | `74359847` | Merged through PR #37 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/fz02-b2b-stalled-deadline-oct2026` | `31d77457` | PR #71 merged; provider-stall/deadline work. | UNASSIGNED / NOT RECORDED |
| `fix/fz02-b2c-cancellation-terminal-oct2026` | `4891756b` | PR #104 merged; router cleanup only; does not close workflow cancellation semantics. | UNASSIGNED / NOT RECORDED |
| `fix/fz02-provider-failure-oct2026` | `371b7eda` | PR #67 merged; provider-failure false-completion work. | UNASSIGNED / NOT RECORDED |
| `fix/fz03-scheduler-loop-containment-oct2026` | `0ff09374` | Merged through PR #53 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/fz04-adaptive-semaphore-permit-conservation-oct2026` | `c4d62b3c` | Merged through PR #51 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/fz07-ci-gate-exit-code-oct2026` | `7cefd6de` | Merged through PR #55 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/import-bundle-boundary-oct2026` | `f43df2e6` | Merged through PR #56 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/import-root-containment-oct2026` | `9264408e` | PR #44 closed unmerged; retained reference only; not an active work owner. | UNASSIGNED / NOT RECORDED |
| `fix/module-factory-path-in-error-sep2026` | `57dde358` | Merged through PR #42 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/module-name-path-containment-oct2026` | `30b584a6` | Merged through PR #46 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/test-c2-hermetic-upstream` | `172b17e2` | Merged through PR #75 into sandbox-fabric; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/test-d7-heartbeat-read-race` | `990feb6f` | Merged through PR #64 into sandbox-fabric; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/test-net-proxy-read-to-eof` | `970840d3` | Merged through PR #50 into sandbox-fabric; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/updater-check-error-redaction-sep2026` | `3fa6befd` | Merged through PR #40 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `fix/workflow-failure-answer-redaction-oct2026` | `7e4ac1b4` | Merged through PR #63 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `follow-up/fz02-b2d-latent-token-cancellation-oct2026` | `b44bddf5` | Unreviewed FZ-02 cancellation follow-up; no PR; issue #105 contract decision OPEN; not canonical implementation target until reviewed. | UNASSIGNED / NOT RECORDED |
| `handoff/adr-kernel-07-live-check-oct2026` | `6e2485ae` | Preserved handoff branch; no current implementation owner recorded. | UNASSIGNED / NOT RECORDED |
| `handoff/codeql-remediation-sep2026` | `20ad523d` | Preserved handoff branch; no current implementation owner recorded. | UNASSIGNED / NOT RECORDED |
| `handoff/sandbox-network-isolation-v4` | `7b99cbb7` | Preserved handoff branch; no current implementation owner recorded. | UNASSIGNED / NOT RECORDED |
| `handoff/security-remediation-oct2026` | `aa7b4924` | Preserved handoff branch; no current implementation owner recorded. | UNASSIGNED / NOT RECORDED |
| `integration/capability-foundation-mission1` | `6748469e` | Integration experiment branch; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `lost-work` | `b97a7f94` | Retained/unclassified branch; no active owner or PR mapping recorded. Do not delete without owner decision. | UNASSIGNED / NOT RECORDED |
| `main` | `2491ae46` | Canonical product baseline; source of truth for implemented behavior. | Repository maintainer controls baseline |
| `preserve/ctx-auth-002-verified-99875d0-oct2026` | `99875d05` | Preserved remediation/evidence branch; no current PR owner mapping. | UNASSIGNED / NOT RECORDED |
| `remediate/ctx-auth-002-from-f13bfde-local-oct2026` | `7b57cf13` | Preserved remediation/evidence branch; no current PR owner mapping. | UNASSIGNED / NOT RECORDED |
| `repair/debt-012-codeql-and-side-effects-oct2026` | `32918673` | Competing DEBT-012 repair candidate; no PR; not selected as canonical. | UNASSIGNED / NOT RECORDED |
| `repair/debt-012-codeql-current-oct2026` | `3e4a146b` | Competing DEBT-012 repair candidate; no PR; not selected as canonical. | UNASSIGNED / NOT RECORDED |
| `repair/debt-012-root-isolation-coherent-oct2026` | `33d96c67` | Competing DEBT-012 repair candidate; no PR; not selected as canonical. | UNASSIGNED / NOT RECORDED |
| `revise/ctx-auth-002-evidence-from-7b57cf1-oct2026` | `7a2c7d61` | Preserved remediation/evidence branch; no current PR owner mapping. | UNASSIGNED / NOT RECORDED |
| `sandbox-fabric` | `d5de7baf` | Sandbox Fabric workstream branch; not main; DEBT-021/039/040/041 remain open. | UNASSIGNED / NOT RECORDED |
| `sandbox-network-isolation/b01-base` | `e2266603` | Sandbox integration branch; not main; sandbox workstream is not product-integrated. | UNASSIGNED / NOT RECORDED |
| `sandbox-network-isolation/b01-contract-suite` | `d3af4eff` | PR #78 merged into B01 branch, not main. | UNASSIGNED / NOT RECORDED |
| `sandbox-network-isolation/b02-net-namespace-gate` | `9e4f429e` | PR #84 merged into B01 branch, not main. | UNASSIGNED / NOT RECORDED |
| `sandbox-network-isolation/b03-capacity-ipv6-guards` | `19b8538b` | PR #86; B03 primitives inert; integration target is B01 base, not main. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `security/codeql-findings-sep2026` | `2d03b703` | Security evidence/remediation reference; no active PR owner recorded. | UNASSIGNED / NOT RECORDED |
| `security/freeze-reconciliation-sep2026` | `ccb7e19d` | Security evidence/remediation reference; no active PR owner recorded. | UNASSIGNED / NOT RECORDED |
| `security/privacy-wipe-containment-oct2026` | `bcbe574d` | PR #79; stale/non-mergeable latent-sink fix; no production caller recorded; do not treat as live exploitable path. | PR author 1h0lde4; assignee: NONE (author is not an assignment) |
| `spec/sandbox-network-isolation-master` | `04dc92d3` | Specification branch; not an implementation authorization; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `study/b3-host-firewall-supplement` | `34f4b388` | Research/study branch; not an implementation authorization; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `study/sandbox-network-redesign` | `ee525d95` | Research/study branch; not an implementation authorization; owner not recorded. | UNASSIGNED / NOT RECORDED |
| `sync/main-into-sandbox-fabric-b00` | `3dc7b816` | Merged through PR #60 into sandbox-fabric; retained reference only. | UNASSIGNED / NOT RECORDED |
| `tools/live-check-repeat-runs` | `7044fdb2` | Merged through PR #61 into main; retained reference only. | UNASSIGNED / NOT RECORDED |
| `wip/fz02-b2c-cancellation-checkpoint-oct2026` | `a83f3ac6` | Historical WIP checkpoint; PR #104's narrowed B2c implementation is merged; preserve, do not treat as current candidate. | UNASSIGNED / NOT RECORDED |

## 6. Explicit non-decisions and safe next actions

- Do not merge PRs #94, #102, #91, #81, #86, #90 or #107 by inference from this register.
- Do not close PRs or delete branches merely because they are stale, duplicated or superseded. Preserve refs until the repository owner explicitly authorizes cleanup.
- Do not assign an implementation owner from the PR author field. Name an accountable implementation owner for each active debt before starting another parallel implementation.
- Before new DEBT-012 work, choose one of PR #91 or the three competing repair branches, then rebuild/rebase a single exact review target from current main.
- Before DEBT-014 review, reconcile #102 with current main and obtain an independent review on its final head.
- For DEBT-025, keep the PR open pending human security review and explicit merge authorization; separately track authorization/governance residuals.
- For FZ-02, decide and record the Worker cancellation contract before implementing #105; keep router cleanup and workflow cancellation as distinct properties.
- For G4, resume from REV2/Addendum 1, preserve all D1-D11 as OPEN until the maintainer decides them, and do not start product work without explicit implementation authorization.
- Update this register and both authoritative state documents together whenever a debt's status, canonical branch, assignee, or PR changes.

**End of snapshot.** Any status after this date must be checked against live GitHub refs and current main before reuse.
