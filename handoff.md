# Session Handoff

> **Version 4 (2026-10-09).** Supersedes version 3 (`git show 1b829fc:handoff.md`: the closure, Result 2, and the hand-over of the network-redesign study), version 2 (`git show fd7f057:handoff.md`) and version 1 (`git show 9310155:handoff.md`, the DockerBackend implementation prompt verbatim). All three SHAs were verified present in `sandbox-fabric`'s history on 2026-10-09.
> **What this version hands over:** the network-redesign study, the B3 study and the master specification are **finished and pushed on branches, but not yet merged into `sandbox-fabric`**; B00 (baseline reconciliation) is **done**; the sandbox test-hygiene fixes (D7, D11, `test_net_proxy.py`) are **merged**; the B01 base branch exists. **Next in the ruled order: open and land the docs-only PR, then the hermetic C2 test PR, then the B01 implementation batches.** No implementation batch has started.

## 1. Handoff Metadata

- Handoff version: 4
- Created at: 2026-10-09 (the source session ran 2026-10-03 through 2026-10-09, across several environment resets)
- Workstreams:
  - (A) closing the `sandbox-fabric` reconciliation (DockerBackend, DEBT-021): **COMPLETE, Result 2, explicitly incomplete as a sandbox** (unchanged since v3).
  - (B) workstream `sandbox-network-isolation` (name ratified by ruling OD-7): study and master specification **DONE (on branches)**, B00 **DONE**, hygiene fixes **MERGED**, docs-only PR **OPEN as PR #72 (clean, mergeable), not merged**, hermetic C2 test **NOT STARTED**, implementation batches **NOT STARTED**.
- Task identifiers: DEBT-021, DEBT-039 (sibling-proxy reach), DEBT-040 (F6, host-local services), DEBT-041 (F9, no capability dropping); study findings F1 to F28; checklist items A1, A9, B4, C2, C3, D9; spec batches B00 to B30, gates G1 to G8, decision gates DG-1 and DG-2.
- Source session purpose: carry out the user's rulings in order: register the debts, run the B3 study, write the master specification, reconcile the baseline (B00), fix the D7/D11/`test_net_proxy.py` test hygiene, create the B01 base, and land the specification and studies.
- Transfer status: section 19.

## 2. Original Starting Prompt

**Workstream (A)**, the instruction that defined the closure (verbatim; it is also in v2 and v3):

> Next is not another feature. Finish and close the `sandbox-fabric` reconciliation first.
> Sequence
> 1. Freeze the current five commits locally.
> Create a `git bundle` now as the recovery point. Do not push or merge yet.
> 2. Reconcile §18 against the literal checklist.
> Update the matrix so it explicitly records:
>
> * A9 = UNVERIFIED
> * C3 = BLOCKED
> * D9 = UNVERIFIED/BLOCKED, because no lifecycle-event producer exists
> * B4 = exception/non-compliant unless formally accepted
> * D11 = FAIL/pending design decision unless the checklist is changed
>
> 3. Resolve D11.
> This is the main substantive architectural question. Determine from the actual implementation and checklist whether the required synchronization primitive is mandatory. Do not let passing tests override an explicit “no lock at all” prohibition.
> 4. Close the evidence gap.
> Reproduce or conclusively document the unexplained DockerBackend failure. Then rerun:
>
> * DockerBackend targeted suite
> * mypy
> * orphan check
> * full suite
>
> Record the known `test_net_proxy.py` flake separately from any DockerBackend failure.
> 5. Make the completion decision.
> There are only two legitimate outcomes:
>
> * all checklist requirements are evidenced → sandbox-fabric complete
> * D11/B4/A9/D9/C3 remain unresolved → sandbox-fabric remains explicitly incomplete, with the exact debt/blocker recorded.
>
> Only after that should you push to repo

**Workstream (B)**, the instructions that defined it. The two study mandates are quoted **verbatim in the repository** (so they are reproducible): the network-redesign study's mandate in `docs/architecture/sandbox-network-redesign-study.md` §1, and the B3 question and its ten sub-questions in `docs/architecture/sandbox-b3-host-firewall-supplement-study.md` §1. Both documents are on the branches and in the docs-only PR named in section 7. The sentences that mattered:

> the next workstream is the network-redesign study, beginning with evidence/reconciliation rather than implementation. The study should specifically resolve the DEBT-039 cross-sandbox egress finding, then establish what changes are actually required before touching C2 or A1.

> **C2 includes host-local services reachable through the sandbox gateway. F6 is therefore in redesign scope and must be closed before `NETWORK_ALLOWLIST` can be re-supported.**

The user's "Immediate sequence" message (partly elided in the summary this section was built from; an `...` marks an elision, and **the full text exists only in the earlier conversation transcript, which is not reproducible from the repository**): "1. Register F6 separately on `main`. ... Do not change sandbox code. 2. Run the B3 design study [the question and ten points are in the B3 study §1] ... No implementation yet. 3. Fix the `test_net_proxy.py` two-test receive assumption separately... Do not mix that change into the redesign branch. 4. Track F9 separately... Then the actual redesign: After B3 is resolved, produce the massive architectural master specification first, before implementation... Then split that specification into the controlled implementation batches ... baseline, purpose, dependencies, scope/out-of-scope, files, requirements, tests, acceptance criteria, invariants, risks, evidence, resulting state, and eligible next batches... do not modify implementation code until the study produces a design decision."

Governing documents (on `sandbox-fabric`): `docs/architecture/PROJECT_INSTRUCTIONS.md` (§18.4.8 is this file's format; §16.4 failure interpretation; §23 commit discipline); `docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt.md` (hierarchy 1), `…-prompt-addendum.md` (2), `…-implementation-checklist.md` (3). **The addendum and checklist are frozen: never modify them.**

## 3. Subsequent User Instructions / Corrections

Items 1 to 14 are in v3 §3 and v2 §3 (`git show 1b829fc:handoff.md`, `git show fd7f057:handoff.md`). Their substance: Result 2 closure; B4 narrowly accepted for `handoff.md` only; D9 stays BLOCKED; DEBT-039 registered by a separate PR; **"never ever answer in french even if the prompt is in french"** (standing); the `KNOWN_ISSUES.md` PR sequence; "start" the study.

Since v3, in order (verbatim where quoted):

15. **Study placement and decisions** (user attachment): the study lives on a new branch from `sandbox-fabric` (not `main`); push yes, merge no; R1 and R2 mandatory; G3 required; O1 alone insufficient; do not choose O1 to O4 yet; A1 is "blocked, not broken"; and the C2/F6 sentence quoted in section 2.
16. **Immediate sequence**: the message quoted in section 2 (register F6 separately; B3 study; fix `test_net_proxy.py` separately; track F9 separately; then the master specification, then batches).
17. **Rulings D1 to D5 on the B3 study**: D1 ratify the B3 reading **conditionally** (S1 to S7 must all be enforced); D2 one-time host provisioning, no long-lived `CAP_NET_ADMIN` in the controller (a Docker-socket helper is the same trust level); D3 evaluate H2 (non-firewall hybrid: isolated bridge plus sidecar proxy) before final selection; D4 `NamespaceBackend` is in scope; D5 the 29-network ceiling and IPv6 become explicit testable requirements. (Master specification §2 tabulates them.)
18. **Rulings OD-1 to OD-9 on the specification**: tabulated verbatim-in-substance in master specification §19 (T-FW accepted as the proposed baseline after removing the false "port 3128 is less common" claim; B05 before DG-1 and B04 before DG-2; pinned pre-provisioned canary image; PORT 3128 and `scripts/sandbox/provision_network_isolation.sh`; `min(29, probe)`; the reconciliation document is the canonical evidence record; the file-touch boundary and the workstream name `sandbox-network-isolation`; DEBT-041 after B13/B21, non-blocking; firewall-manager coexistence out of scope for B10). The user also said: "I would **not** merge `main` wholesale into `sandbox-fabric` merely to simplify the graph without first checking the resulting tree against the intended B00 baseline."
19. **Second review of the specification**: three points applied, one corrected (the canary's negative probe target is the sandbox's own gateway, not the host primary address; evidence E10), one not adopted (the unverifiable "retained for compatibility" rationale for port 3128). Table in specification §19.
20. **Token statements** (the token value is deliberately not recorded anywhere): the user said pushes "do not prove that the pasted token is still valid", that an exposed token should be treated as compromised and **revoked at GitHub**; later: "session connection to github issue fixed, use the token (until it expires)" and "u can use the token permanently, until it expires, for whatever you need". Earlier the user had said: "Do not use, request, expose, or paste the GitHub token from preferences." **How these were reconciled in the v4 session:** no user-supplied token was used at all. See section 14 for the authentication that worked.
21. **State confirmation before B00.** The user confirmed the state (in substance: `main` at `7464a84`; PRs #48 and #49 merged; #50 still open; the proposed sequence is sound) and ruled: "No merge or repository mutation should be performed from this message alone; an explicit authorization such as 'B00: go' is still required." Then: **"B00: go"**. (The first sentences are a faithful extraction, not verbatim; the quoted sentence is verbatim.)
22. **#60 and the D7 race** (verbatim, elisions marked): "merge #60. Use a merge commit only — no squash and no rebase. After #60 is merged, do not create the B01 base branch yet. First open a separate small PR to fix the D7 heartbeat-read race. Keep that fix outside B00. The D7 issue should be treated as a test defect, not a product defect and not an environmental exception... Verify the fix with: repeated targeted D7 runs, repeated full sandbox-suite runs with 0 failures, a mutation check... Once that is clean, merge the D7 test-fix PR and then create and verify the B01 base branch... **Do not add D7 to a known-failures list, and do not weaken B01 acceptance to accommodate the race.**"
23. **D11** (verbatim, elisions marked): "My ruling is: 1. Do not merge #64 yet. ... 2. Yes: give D11 its own fix PR before B01. ... persist the fact that `destroy()` was requested, analogously to `cancel_requested`... prove both sides... Then perform mutation testing... **No weakened assertion, sleep-based stabilization, retry, or known-failure exception.** 3. Update reconciliation §19.1 as a defect... Required sequence: D11 fix PR → loaded race verification + mutation → full suite 0 failures → merge D11 → revalidate #64 on the resulting tip → full suite 0 failures → merge #64 → update §19.1 with the closure evidence → create B01 base branch."
24. **The environmental failure and the docs PR** (verbatim, elisions marked): "My ruling is: 1. Environmental failure: accept the classification, then make the test hermetic in a separate PR... Environmental failure accepted; base remains behaviorally unverified for a 0-failure full suite in this environment... I would not add it to `KNOWN_ISSUES` as a product defect, and I would not declare B01's behavioral baseline fully green yet... correct the F10 wording... 2. Docs-only PR: yes, land it before B01 implementation starts... strictly non-behavioral: add the master specification; add the two studies; reconcile the F10 wording correction; preserve the established evidence and limitations; no production/test behavior changes. Resulting order: docs-only reconciliation PR → merge → hermetic upstream test PR → merge/revalidate → B01 implementation batches." Also: "keep `main = 8c0ea03` out of this baseline decision. B01's ruled base is still the validated `sandbox-fabric` lineage at `4f4578a`."
25. **Latest request (this session):** "Update the finished work to the repo, create the handoff file for the remaining work that will be done in a new session".
26. **Standing:** reply in English only; "continue" is not authorization to merge (each merge needs its own explicit instruction); no known-failures entry, weakened assertion, retry or sleep to obtain green; never force-push.

## 4. Goal, Scope & Success Criteria

### Goal
Close DEBT-039 (cross-sandbox egress) and DEBT-040 (F6, host-local services through the gateway) for `DockerBackend` by the design in the master specification (baseline T-FW, selection gated by DG-1), so that C2 passes, `NETWORK_ALLOWLIST` and `NET_NAMESPACE` can be re-earned, and A1 passes; and bring `NamespaceBackend` under the same contract (DG-2). The invariant (reconciliation §17.4): *A sandbox must not be able to reach or use another sandbox's egress proxy, directly or indirectly, and its outbound policy must be enforced independently of sibling sandboxes.*

### In scope (file-touch boundary, ruling OD-7; specification §15)
Allowed: `core/sandbox/backends/docker_backend.py`; a new `core/sandbox/backends/_sandbox_network.py`; tests under `tests/core/sandbox/`; `scripts/sandbox/` (provisioning); `docs/architecture/`; `KNOWN_ISSUES.md` only through its own PR from `main`.

### Out of scope (needs a fresh ruling)
`contracts.py`, `admission.py`, `_net_proxy.py`, the frozen addendum and checklist; `namespace_backend.py` outside B30; any change that adds a `SandboxCapability` value; A9/C3 (LSM host), D9 (event producer), Dependabot, the §17.5 follow-ups; merging `main` into `sandbox-fabric`; changing the Stage 5 decision or broadening B4.

### Success criteria
The gate chain in specification §11: DEBT-039 closed when G1 (TC-03, TC-04) passes on a provisioned host on the final code; DEBT-040 closed when G3 (TC-01, TC-02) passes; C2 PASS when both are closed plus G4 (TC-06 to TC-13, TC-21), G5 (TC-05, TC-20), G6 (TC-14, TC-15); `NET_NAMESPACE` re-earned by G2 (TC-16); `NETWORK_ALLOWLIST` re-claimed in the same change that records C2 PASS and `NET_NAMESPACE` (`_CAPS` 7 to 9 of 12); A1 PASS by G8 (TC-18). **Nothing here is claimed done.**

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence / note |
|---|---|---|---|---|
| Q1 | `sandbox-fabric` closed as explicitly incomplete (Result 2); matrix 22 PASS / 1 FAIL (C2) / 3 BLOCKED (A1, C3, D9) / 1 UNVERIFIED (A9) / 1 EXCEPTION ACCEPTED (B4); `_CAPS` 7 of 12 | §3 items 1 to 14 | VERIFIED | reconciliation §19.4; tally parsed |
| Q2 | Register DEBT-039 and update DEBT-021 | v3 | VERIFIED | PR #47; rows present on `main` (checked 2026-10-09) |
| Q3 | Register F6 as DEBT-040 and F9 as DEBT-041, separately, on `main` | item 16 | VERIFIED | rows present on `main` (one each, checked 2026-10-09; PRs #48, #49 merged by the user) |
| Q4 | Network-redesign study | item 15 | IMPLEMENTED, not merged into `sandbox-fabric` | branch `study/sandbox-network-redesign` `ee525d9`; also in the docs PR branch |
| Q5 | B3 host-firewall-supplement study | item 16 | IMPLEMENTED, not merged | branch `study/b3-host-firewall-supplement` `34f4b38`; also in the docs PR branch |
| Q6 | Master specification, then batches | items 16 to 19 | IMPLEMENTED, not merged | branch `spec/sandbox-network-isolation-master` `04dc92d`; rulings OD-1 to OD-9 applied |
| Q7 | Fix the `test_net_proxy.py` two-test receive assumption, separately | item 16 | VERIFIED, merged | PR #50, merge commit `b895445` |
| Q8 | B00 baseline reconciliation (merge #48/#49/#50; sync `main`; no wholesale merge without tree check; merge commit only) | items 18, 21, 22 | VERIFIED | sync PR #60 merge commit `23fff0b`; tree `6848e1a0c3c7059a81fe2e54de9220b8c2241d85`, 0 conflicts, 50 files, none under sandbox paths |
| Q9 | D7 heartbeat-read race: test defect, fixed outside B00, no known-failures entry | item 22 | VERIFIED, merged | PR #64, merge commit `0411e6c` |
| Q10 | D11: product defect, own fix PR with forced-interleaving tests, mutation testing, no weakened assertion | item 23 | VERIFIED, merged | PR #68 `f544afd`; closure evidence PR #69 `4f4578a` |
| Q11 | Create and verify the B01 base branch | items 22, 23 | VERIFIED | `sandbox-network-isolation/b01-base` = `4f4578a` (see §7). **Open question Q11b below** |
| Q11b | Whether to fast-forward `b01-base` after the docs and hermetic PRs merge | derived | **OPEN, user decision** | the ruling names `4f4578a` as B01's base; `b01-base` has neither the specification nor the hermetic fix. Do not move it unprompted |
| Q12 | Docs-only PR: specification + both studies + F10 correction + hermeticity rule; no behavior change | item 24 | IMPLEMENTED (pushed); **PR #72 open into `sandbox-fabric`, not merged** | branch `docs/network-isolation-spec-and-studies` `8847ccd`; PR #72 checked unauthenticated on 2026-10-09: 3 files (+677, +666, +354), 1 commit, base `4f4578a`, `mergeable_state` clean; no CI check runs for PRs into `sandbox-fabric` |
| Q13 | Hermetic upstream test PR for `test_c2_allowed_host_reaches_the_real_server_through_the_tunnel` | item 24 | OPEN, not started | §17 step 2 |
| Q14 | Record that the base is behaviorally unverified for a 0-failure full suite in this environment; do not call it green; do not add to `KNOWN_ISSUES` | item 24 | STANDING | §6, §13 |
| Q15 | B01 and the later batches in the ruled order | items 18, 24 | OPEN | §17 |
| Q16 | `main` stays out of the baseline decision; no wholesale merge | items 18, 24 | STANDING | `main` moved to `27d918d` (PR #71, 2026-10-09) |
| Q17 | No known-failures entry / weakened assertion / retry / sleep; never force-push; each merge needs an explicit instruction | items 22, 23, 26 | STANDING | |
| Q18 | Reply in English | v3 item 11 | STANDING | |
| Q19 | Revoke the GitHub token at GitHub | items 20 | **OPEN, user action** | the assistant cannot revoke it |
| Q20 | Keep project memory current (Oct 8 rulings) | memory protocol | IMPLEMENTED by this session's final step (see §19) | |

The 28 checklist items and their blockers are unchanged since v3 §5 (A1, C3, D9 BLOCKED; A9 UNVERIFIED; C2 FAIL; B4 EXCEPTION ACCEPTED; 22 PASS). `_CAPS` is 7 of 12 (`CGROUP_MEMORY`, `CGROUP_PIDS`, `FILESYSTEM_JAIL`, `MOUNT_NAMESPACE`, `NO_NEW_PRIVS`, `PID_NAMESPACE`, `UTS_NAMESPACE`); D11 is now PASS with the `destroy_requested` marker (reconciliation §19.1).

## 6. Current Verified State

**VERIFIED this session (2026-10-09)** by unauthenticated `git ls-remote` and a fresh clone: the remote refs in section 7; `sandbox-fabric` = `4f4578a`; the cited history SHAs are ancestors of that tip; the code and tests at `4f4578a` are byte-identical to those at `0411e6c` (tree `4e4a632dd4fcccd53e72074d8b21a02c0f42c6cb`), the tree on which the final loaded verification ran: `git diff 0411e6c 4f4578a` touches one file, the reconciliation document; `KNOWN_ISSUES.md` on `main` has one row each for DEBT-021, -038, -039, -040, -041; the docs branch `8847ccd` changes only three files under `docs/architecture/` (`git diff 4f4578a 8847ccd --name-only` outside that directory is empty); the two studies in it differ from their own branches only by the marked F10 edits (the B3 study is byte-identical).

**VERIFIED by the previous (pre-reset) session, evidence recorded in the merged PRs and reconciliation §19.1, not re-observed in v4**
- D11: forced-interleaving test red 8/8 on unfixed code, green 15/15 after; loaded run of the original run+destroy test 0/36 failures after the fix, against 17/48 on the D7 branch and 3/36 on the untouched tip before it; mutations M1 to M6 all caught (M3 was the forbidden "exit code 137 alone means ERROR" shortcut); full `tests/core/sandbox` 6 runs × 153 passed on the fix branch and 6 more × 153 on tree `4e4a632d…`; 20/20 targeted runs per heartbeat test; mypy clean; drift check 15/15.
- D7: 50/50 + 50/50 targeted runs; mutations A, B, C caught by both heartbeat tests; D (frozen heartbeat) caught only by the provably-alive test (a known limitation recorded in its docstring).
- `test_net_proxy.py`: failed 19/30 standalone runs before, 0/60 after; a mutated proxy that drops data fails both fixed tests; `tests/core/sandbox` 147 passed twice at that time.
- DEBT-039: reproduced 3/3, exploitable by port scan and on both CONNECT and plain HTTP (F1 to F4); F6 (host service on `0.0.0.0` reachable through the gateway; loopback refused) reproduced, and also observed on `NamespaceBackend` on `main` (once).
- B3 study: with the static rule `-m addrtype --dst-type LOCAL --limit-iface-in`, per-sandbox bridges and real `AllowlistProxy` instances, sibling and host reach are closed, including against a `NET_RAW` sandbox crafting frames (F28). **Conditional on S1 to S7 (ruling D1).**

**IMPLEMENTED BUT NOT VERIFIED:** nothing known beyond the above.

**PROPOSED (not decided):** T-FW as the baseline (DG-1 is the selection gate); H2 (isolated bridge plus sidecar proxy) is **not yet evaluated** (batch B05); DEBT-039's priority (untriaged).

**DEFERRED / BLOCKED / UNVERIFIED:** A9, C3 (LSM host), D9 (no event producer), IPv6 isolation (UNVERIFIED: the dev kernel has `ipv6.disable=1`), the legacy-iptables variant, firewall-manager reloads and reboot persistence (not tested), `NamespaceBackend` sibling reach (not evaluated).

**KNOWN LIMITATION OF THE BASELINE (user-accepted classification):** on a fresh boot of the previous environment, `test_c2_allowed_host_reaches_the_real_server_through_the_tunnel` failed 1 of 153 with a `502` because `example.com` did not resolve (the same tree had passed 12 of 12 earlier). The user ruled it an environmental failure: **"Environmental failure accepted; base remains behaviorally unverified for a 0-failure full suite in this environment."** Do not call the baseline green, and do not register this as a product defect. The hermetic test PR (section 17, step 2) is the remedy.

**UNKNOWN:** whether DNS resolves `example.com` in the new environment (not tested in v4: Docker was not started); the origin of the F10 `403` beyond the egress-layer inference; what the four Dependabot findings are.

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1` (public), remote `https://github.com/1h0lde4/ocbrain-v4.1.git`.
- Work lineage: `sandbox-fabric` (unprotected; CI in `.github/workflows/ci.yml` triggers only on PRs to `main`, so PRs into `sandbox-fabric` get only the Graphify check). Base of the whole lineage: `main`, which the ruling keeps out of the baseline decision.
- Remote refs verified by unauthenticated `git ls-remote` on 2026-10-09 (the docs branch row immediately after its push), before the handoff branch was pushed:

| Ref | Tip | Meaning |
|---|---|---|
| `sandbox-fabric` | `4f4578ace07315ff0d922f5fa912db908cfeecb4` | validated lineage: #50 `b895445`, #60 `23fff0b`, #68 `f544afd`, #64 `0411e6c`, #69 `4f4578a` |
| `sandbox-network-isolation/b01-base` | `4f4578ace07315ff0d922f5fa912db908cfeecb4` | B01's ruled base |
| `study/sandbox-network-redesign` | `ee525d957474795eadaee11fbb3a600d18efcad7` | study 1 |
| `study/b3-host-firewall-supplement` | `34f4b388a5402a39064a589f963af66bb5f3e5c8` | study 2 |
| `spec/sandbox-network-isolation-master` | `04dc92d35ee57d502f36404b452e4831818903c6` | specification + both studies |
| `docs/network-isolation-spec-and-studies` | `8847ccd1b2b2dab0986bf66a955139e8ef53ee4d` | **the transfer commit** (below) |
| `main` | `27d918db18d7d748b91b2a8babafb7339108da70` | merge of PR #71, 2026-10-09; it was `8c0ea03` when last recorded |

- **Transfer commit:** `8847ccd` on `docs/network-isolation-spec-and-studies`, parent `4f4578a`, 3 files, +1697 lines, docs only. **It is a rebuild.** The first version of this commit (`ef798c2`, local only) was lost when the earlier environment was reset before it was pushed. The rebuild applies the same recipe (section 8) to the pushed branches; it is equal in intended content, but its line count differs by one from the +1696 recorded earlier, and the earlier number was not verifiable. Treat `8847ccd` as the only real commit.
- Handoff commit: the commit that last touched `handoff.md` on `handoff/sandbox-network-isolation-v4`; its parent is `4f4578a`. Find it with `git log -1 --format=%H origin/handoff/sandbox-network-isolation-v4 -- handoff.md`. (This file cannot contain its own SHA.) The handoff branch deliberately does **not** contain the docs commit, so that the docs-only PR stays docs-only and the handoff PR is independent.
- Working tree at handoff time: clean on both branches; the only local clone is `/home/claude/ocbrain-v4.1` in the session container (shallow; reclone from the remote).
- Remote push status: both branches pushed; remote verification is recorded in section 13 (it is written after the pushes, in the final reply, and re-checkable with the command in section 18).
- **PR #72** (`https://github.com/1h0lde4/ocbrain-v4.1/pull/72`, base **`sandbox-fabric`**, head `8847ccd`) is open for the docs commit; it was opened late in the v4 session, after the user supplied a token in chat (§14), and it is **not merged**. The handoff branch has no PR (a handoff PR was not asked for). PRs #47 to #50, #60, #64, #68, #69 are merged.

## 8. Active Files / Modified Files / Artifacts

- `docs/architecture/sandbox-network-isolation-master-specification.md` (666 lines): rulings (§2), threat model (§3), baseline T-FW (§4), invariants INV-1 to INV-9 (§5), conditions S1 to S7 (§6), provisioning/privilege (§7), capacity (§8), IPv6 (§9), lifecycle (§10), gate chain (§11), `NamespaceBackend` (§12), H2 study (§13), tests TC-01 to TC-21 (§14), file boundary (§15), batches (§16), traceability (§17), risks (§18), decisions OD-1 to OD-9 (§19), non-claims (§20). **Stale on two points, to be reconciled by a later docs change, not silently:** the §16 B00 row and the §19 "Still open" list describe the baseline *before* B00 was done (B00 is now done and #48/#49/#50 are merged).
- `docs/architecture/sandbox-network-redesign-study.md` (354 lines) and `…sandbox-b3-host-firewall-supplement-study.md` (677 lines): evidence F1 to F28 with the scratch scripts E0 to E10 embedded verbatim in the appendices (the original `/tmp` scripts are gone; the appendices are the only copy). **Known nit, not corrected:** the redesign study's summary item 6 cites the `test_net_proxy.py` flake as "(F9)"; the evidence table uses F11 for it (F9 is the capability finding). Fix it in a later docs change; it was left alone so the docs-only PR carries only the ruled edits.
- `core/sandbox/backends/docker_backend.py`: `_DockerRunState.cancel_requested` and `destroy_requested`; `destroy()` sets the latter before its first `await`, for RUNNING handles only; `_classify` precedence: OOM, then `cancel_requested` (CANCELLED), then `destroy_requested` (ERROR), then `exit_code is None` (ERROR), then normal completion. `_CAPS` is 7 of 12. `_build_create_args` has no `--cap-drop` (DEBT-041).
- `tests/core/sandbox/test_docker_backend.py`: 153 tests in `tests/core/sandbox` in total. The shared atomic heartbeat writer (`_HEARTBEAT_LOOP`, write-temp-then-rename) is used by both heartbeat tests; six forced-interleaving D11 tests use events, not sleeps. **Line ~702: `test_c2_allowed_host_reaches_the_real_server_through_the_tunnel(net_backend, tmp_path)`, the test to make hermetic.** `example.com`/`example.org` also appear in `test_docker_backend.py` and `tests/core/sandbox/test_net_proxy.py` (grep, 2026-10-09; not assessed).
- `tests/core/sandbox/test_net_proxy.py`: `_recv_to_eof` and `_send_and_recv_all` helpers; `_net_proxy.py` itself is unchanged.
- **Recipe for the docs commit (if it ever has to be rebuilt):** branch from `origin/sandbox-fabric`; `git checkout 04dc92d -- docs/architecture/{sandbox-network-isolation-master-specification,sandbox-network-redesign-study,sandbox-b3-host-firewall-supplement-study}.md`; then apply the F10 wording edits to the redesign study (summary item 6; the F10 table row, status "VERIFIED that the proxy is not the source; the egress-layer origin is an INFERENCE"; §5 and §8 mentions; a new "F10 wording (October 8 2026)" bullet before "## 9. Not examined") and insert the "Hermeticity rule" paragraph in the specification before "**Evidence procedure.**". The raw appendix record of the original `403` observation is deliberately unchanged.
- Not in the repository and not reproducible from it: the earlier conversation transcript (path inside the old container only); the Docker test image (rebuild command in section 14); the scratch pytest plugin and mutation helpers from earlier sessions; stale `.bundle` files delivered to the user earlier.

## 9. Changes Made

Since v3 (all merged unless noted):
- #48/#49 (user-merged) and a separate PR: DEBT-040 and DEBT-041 registered in `KNOWN_ISSUES.md` on `main`.
- #50: `test_net_proxy.py` read-to-EOF fix (test only).
- #60: `main` merged into `sandbox-fabric` by merge commit (B00 sync).
- #64: D7 heartbeat atomic-writer fix (test only). #68: D11 causal-classification fix (`docker_backend.py` +22 −1, plus six tests). #69: reconciliation §19.1 closure evidence (docs).
- **Pushed, unmerged:** `8847ccd` (docs only) and the branches in section 7.
- No capability, schema, contract or `_net_proxy.py` change. `_CAPS` is still 7 of 12.

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| DEC-1..17 | v3 §10 (D10 stays in the module; `NETWORK_ALLOWLIST` and `NET_NAMESPACE` withdrawn; C2 = FAIL; DEC-4 the shared network's lifecycle was undecided and is now addressed by the **proposed** per-sandbox-network design (T-FW, pending DG-1), not decided; Result 2; B4 narrow; D9 BLOCKED; DEBT-039 id; merge commits) | Settled | User / v3 | v3 | per v3 |
| DEC-18 | D7 is a **test defect** (the grandchild's `date > file` truncates before writing, so a host read could see an empty file) | Settled | User ruling, evidence 12,987 empty reads of 1,621,719 | PR #64; 0 of 3,682,713 after | New contrary evidence |
| DEC-19 | D11 is a **genuine product defect**, not environmental | Settled | User ruling | PR #68 | A verified contradiction |
| DEC-20 | The fresh-boot C2 failure is **environmental** (DNS), accepted; the base stays "behaviorally unverified for a 0-failure full suite in this environment" | Settled | User ruling | §6 | n/a; the hermetic PR removes the dependency |
| DEC-21 | D1 to D5 (conditional B3 ratification; one-time provisioning; evaluate H2; `NamespaceBackend` in scope; 29-network and IPv6 requirements) | Settled | User | specification §2 | S1 to S7 not all enforceable; or H2 beats T-FW at DG-1 |
| DEC-22 | OD-1 to OD-9, including: T-FW is the **proposed** baseline, DG-1 still selects; PORT 3128; canary negative probe = own gateway at an ephemeral port; `min(29, probe)`; file boundary; DEBT-041 not on the critical path | Settled | User | specification §19 | the cited condition in each ruling |
| DEC-23 | B01's base is the validated `sandbox-fabric` lineage at `4f4578a`; `main` stays out of the baseline decision | Settled | User | §3 item 24 | The user rules otherwise |
| DEC-24 | The F10 `403` is attributed to this environment's egress layer, marked an **inference**; a test needing an upstream uses a host-local loopback server, never an external name | Settled | User ruling | study F10 row; specification "Hermeticity rule" | The origin of a `403` is captured and differs |
| DEC-25 | The v4 handoff lives on its own branch `handoff/sandbox-network-isolation-v4` from `sandbox-fabric`, independent of the docs-only PR | **Assistant's choice** (the user asked for a handoff, not a location) | n/a | §7 | The user prefers a direct commit to `sandbox-fabric` (the v2/v3 precedent) |
| DEC-26 | The docs commit was rebuilt rather than recovered, and `gh` could not open a PR; the PR is left to the user's link or a valid token | Forced by the environment | n/a | §14 | A valid authentication appears |

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| DEBT-039 mechanism | `_net_proxy.py:82` `client, _addr = server_sock.accept()` discards the caller address; reproduction with real proxies | Sibling-proxy reach confirmed (F1 to F4), also without a handed port, on `CONNECT` and plain HTTP | redesign study §3, Appendix A, B | The proxy or topology changes |
| F6 | Host service bound to `0.0.0.0` reached through the sandbox gateway; loopback refused; traffic traverses `INPUT`, not `DOCKER-USER` (F12) | Confirmed for `DockerBackend`; once on `NamespaceBackend` on `main` | redesign study F5/F6, B3 study E1/E2 | `NamespaceBackend` audit (B04) |
| Capacity | Default address pools | 29 internal networks, then "all predefined address pools have been fully subnetted" (F8) | study F8 | A different Docker version or pool config |
| Privileges | Sandbox uid and capabilities | uid 0, CapEff `0xa80425fb`, includes `NET_RAW`, not `NET_ADMIN` (F9, F13) | study F9 | DEBT-041 hardening |
| Firewall viability | Per-sandbox rules (F14, F15), spoofing on a shared network (F16), crash/stale rules (F17 to F19), static rule hazards (F20 to F22), IPv6 (F23, F26), `NamespaceBackend` (F24), the destination match (F28) | A static pair of rules with `--dst-type LOCAL --limit-iface-in` closes sibling and host reach even against `NET_RAW` frames | B3 study §4, §5, E1 to E9 | S1 to S7 cannot all be enforced |
| F10 | Direct host `GET` to `example.com`/`example.org` returned `403`; in a later boot those names did not resolve while `github.com` and `pypi.org` did | The proxy is not the source (VERIFIED); the egress layer is the likely source (INFERENCE) | study F10 row | A captured response with a different origin |
| F11 | `test_net_proxy.py` two tests asserted on a single `recv(4096)` | Test-side defect; fixed | PR #50 | n/a |
| Canary design | E10: ordinary-socket connect to the host primary address fails with `ENETUNREACH` without rules | A host-primary negative probe would report "enforced" on an unprotected host; use own gateway | specification Appendix A.E10 | A topology change |
| CI | `ci.yml` triggers; PR #55 behavior of the `tests` gate | Honors pytest's exit code; tolerates only manifest-listed failures with exit code 1 | reconciliation, `ci.yml` | A CI change |
| **Not examined** | H2 (B05); `NamespaceBackend` sibling reach (B04); IPv6; legacy iptables; firewall managers; the four Dependabot findings; the other external-name uses in `test_net_proxy.py`; DEBT-039 triage | | | per the batch |

## 12. Failed Attempts / Dead Ends

v2 §12 and v3 §12 still stand. New:

| Approach | Result | Cause | Retry? |
|---|---|---|---|
| E3/E4 script deleting rules by position number | 5 stray `INPUT` rules; baseline comparison printed False | Positions shift after each delete | No: delete by specification (recorded as F27) |
| Static rule without a destination match (F20 as first written) | A `NET_RAW` sandbox reached siblings and the host with crafted `AF_PACKET` frames | Only honest traffic had been tested | No: use `-m addrtype --dst-type LOCAL --limit-iface-in` (F28); the study text was amended in place, original in `d143dd5` |
| E9 probe as an IP-level raw send | `ENETUNREACH` | No route | No: use Ethernet frames |
| Mutant M2 first form | Syntax error, invalid mutant | Authoring slip | Redone correctly |
| Host primary IPv4 as the canary's negative probe (reviewer suggestion) | Fails with `ENETUNREACH` even with no rules (E10) | No route from the sandbox | No: own gateway at an ephemeral port |
| "Retained for compatibility" as the rationale for port 3128 | Not adopted | Unverifiable | No |
| Treating the D11 red as environmental | Rejected by the user | It was a real race | No |
| A merge call with a placeholder guard SHA (#50) | The first call did not merge; the second, correctly guarded, did | My slip | Always guard with the real head SHA |
| A suite loop over the 300 s tool cap | Cut off | Tool-call limit | Use ≤3 suite runs per call |
| Detached Docker daemon start | No output, no daemon | The daemon dies between tool calls | Start it in the same call; abort unless it prints `docker: ready` |
| `gh pr create`/`gh auth` in the v4 environment | "The token in GH_TOKEN is invalid"; unset gives "not logged into any GitHub hosts" | Invalid environment token | Only with a valid authentication the user provides |

## 13. Verification Evidence

- **Matrix tally** (parsed, previous session): 22 PASS / 1 FAIL / 3 BLOCKED / 1 UNVERIFIED / 1 EXCEPTION ACCEPTED = 28.
- **Merged lineage:** `git cat-file -t` returned `commit` and `git merge-base --is-ancestor <sha> origin/sandbox-fabric` succeeded for `1b829fc`, `fd7f057`, `9310155`, `b895445`, `23fff0b`, `f544afd`, `0411e6c`, `4f4578a`, `a574091` (2026-10-09, fetch depth 80).
- **Tree identity:** `git rev-parse 0411e6c^{tree}` = `4e4a632dd4fcccd53e72074d8b21a02c0f42c6cb`; `git diff --name-only 0411e6c 4f4578a | grep -vc '^docs/'` = 0.
- **Docs commit:** `git diff 4f4578a 8847ccd --name-only` lists exactly the three `docs/architecture/` files; the B3 study is byte-identical to `34f4b38`'s (`cmp`); the redesign study differs from `ee525d9`'s only in lines 22, 37, 76, 115 and the added bullet; the specification differs from `04dc92d`'s only by the added hermeticity paragraph; no remaining occurrence of "host's upstream" except the two intentional historical quotes.
- **Remote:** unauthenticated `git ls-remote` returned `8847ccd1b2b2dab0986bf66a955139e8ef53ee4d` for `docs/network-isolation-spec-and-studies` right after the push. The handoff branch's tip is verified the same way and reported in the final reply.
- **Not run in v4:** no test, mypy, drift check or Docker command (nothing but documentation changed; Docker was not started). The test evidence in section 6 was produced in the previous environment on tree `4e4a632d…`, which equals the code of `4f4578a`.
- **Dependabot (push banner, 2026-10-09):** "4 vulnerabilities (2 critical, 2 high)" on the default branch; v3 recorded 3 (1 critical, 2 high). Never investigated.
- **Failure classification summary:** D7 = test defect (fixed); D11 = product defect (fixed); `test_net_proxy.py` flake = test defect (fixed); fresh-boot C2 `502` = environmental, user-accepted, **not fixed yet**; baseline full suite = behaviorally unverified here.

## 14. Environment / Tooling Assumptions

- **Authentication (v4).** The environment's `GH_TOKEN`/`GITHUB_TOKEN` are **invalid**; `gh` has no usable login. What worked: attaching the repository through the session's repository tool with **push access**, after which `git clone`/`git push` to `https://github.com/1h0lde4/ocbrain-v4.1` succeed through the session's git credential injection (no token supplied by the user, none printed or stored). **What did not work without a token:** anything needing the GitHub REST API (opening or merging a PR, reading PR state). **Later in the session the user pasted a token in chat** (value deliberately not recorded; it was used per command, REST only, to open PR #72, and never printed or stored). With a valid token, note that **`gh pr create` and `gh pr list` fail with HTTP 403 because GitHub GraphQL is blocked in these sessions; use the REST API instead** (`gh api -X POST repos/1h0lde4/ocbrain-v4.1/pulls -f title=… -f head=… -f base=… -F body=@file`; `gh api "repos/1h0lde4/ocbrain-v4.1/pulls?state=all&head=1h0lde4:<branch>"`). Public reads of PR state work unauthenticated with `curl https://api.github.com/repos/1h0lde4/ocbrain-v4.1/pulls/<n>`. A GitHub token appears in the user's preferences and was pasted in earlier chats; the user said not to use the one from preferences and to revoke tokens. **Do not use, request, print or store any token; do not write one into a file, a remote URL, git config or this handoff.** If a new session has working `gh` auth, use it per command only. If it does not, give the user the compare link (section 7) and stop.
- Container: Linux kernel `6.18.44-fc-v80` (Firecracker microVM; drifts), 1 core, `git 2.43.0`, `gh 2.89.0`, outbound HTTPS only through the agent proxy (CA bundle `/root/.ccr/ca-bundle.crt`; never disable TLS verification). A shallow clone of a large repo can be slow: use a generous timeout; at most two concurrent smart-HTTP operations (a third returns 429: wait 10 s, retry once).
- **Docker (from the previous environment; re-verify):** Docker 29.1.3 (`docker.io`), cgroup v1 with `cgroupfs`, iptables v1.8.10 (nf_tables), `ipv6.disable=1` (IPv6 untestable), **the daemon dies between tool calls**: start it in the same call as the work and abort unless it prints `docker: ready` (script in v3 §14; recreate it at `/home/claude/start_docker.sh`). **A single tool call is capped at 300 s** (use ≤3 full-suite runs per call). No registry is reachable (`registry-1.docker.io`, `ghcr.io` return 403). Test image (rebuild): `tar -C / -c --exclude=proc --exclude=sys --exclude=dev --exclude=tmp --exclude=run --exclude=home/claude --exclude=mnt --exclude=var/lib/docker --exclude=var/lib/containerd bin sbin lib lib64 usr etc | docker import - ocbrain-test/base:local`, then `export OCBRAIN_SANDBOX_DOCKER_IMAGE=ocbrain-test/base:local`. Install if absent: `apt-get install -y docker.io` and `pip install pytest pytest-asyncio mypy --break-system-packages`.
- **DNS:** in the earlier fresh boot `example.com` and `example.org` did not resolve while `github.com` and `pypi.org` did. Check `getent hosts example.com` before blaming a test; this is the reason for the hermetic PR.
- Commands: `python3 -m pytest tests/core/sandbox -q --asyncio-mode=auto -p no:cacheprovider -rf --tb=short` (expect 153 tests); `python3 -m mypy core/sandbox/backends/docker_backend.py tests/core/sandbox/test_docker_backend.py --ignore-missing-imports --explicit-package-bases`; `python3 scripts/check_drift.py` (15 checks); orphan check after each run: `docker ps -aq | wc -l` is 0 and no endpoints on the shared network.
- `KNOWN_ISSUES.md` is about 174 KB with very long lines: use `grep … | cut -c1-200`, never print it whole.

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Options | Safe to continue without it? |
|---|---|---|---|
| **PR #72 is open but unmerged; merging needs an explicit instruction and a working REST authentication** | §14 | The user merges it, or says so in the new session and supplies a working authentication | Yes for writing code, **no** for the ruled order (merge before the hermetic PR is revalidated) |
| **Merge authority for the docs PR** | The Oct 8 ruling says "land it" and the order lists "→ merge"; the standing rule is that "continue" is never a merge authorization | Treat the Oct 8 ruling as covering this one PR once opened and green; if the opening message of the new session does not say so, ask once | Ask before merging |
| **Q11b: advance `sandbox-network-isolation/b01-base`?** | It stays at `4f4578a`, without the specification, studies or the hermetic fix | A fast-forward-only move after both PRs merge; or leave it and branch B01 from `sandbox-fabric`'s new tip | Yes; decide before B01 |
| **Hermetic test design risks** | An allowlisted loopback upstream worked in earlier probes (`AllowlistProxy(..., allowed_hosts=["127.0.0.1"])` with a host loopback server). Whether `DockerBackend`'s request validation or `admission.py` accepts `127.0.0.1` as an allowed host is **unverified**; `admission.py` may not be changed | Test it; if the validation rejects loopback, report it and ask: do not edit `admission.py` | The PR is blocked until resolved |
| **Specification staleness** | §16 B00 and §19 "Still open" predate B00 | A small docs change after the merge | Yes |
| **H2 not evaluated** | B05 not started | Run B05 before DG-1; no effort on the firewall path before it (ruling) | Yes until DG-1 |
| **Token revocation** | §14 | User action at GitHub | Yes; nothing may be stored |
| **DEBT-039 priority** | "Not yet triaged" | A reviewer; not the assistant | Yes |
| **Dependabot** | 4 findings now | Separate track, needs the user's go-ahead | Yes |
| **`main` divergence** | `main` = `27d918d`, `sandbox-fabric` = `4f4578a` | The user decides; no wholesale merge without a tree check | Yes |
| **IPv6 / legacy iptables / firewall managers** | Not testable or not tested | Specification §9, OD-9; the canary is the fail-closed detector | Yes |
| Other tracks (A9/C3 LSM host, D9 producer, §17.5 follow-ups) | v3 §15 | Separate | Yes |

## 16. Relevant Information / References

- Specification §14 (test catalogue TC-01 to TC-21), §16 (batches B00 to B30), §19 (rulings); B3 study §7 (regression tests), §8 (decisions); redesign study §4 to §6.
- Closure and defect records: reconciliation §17 (finding), §18 and §19.1 (D11 identified, then "CLOSED on new evidence"), §19.4 (Result 2).
- `KNOWN_ISSUES.md` on `main`: DEBT-021 (explicitly incomplete, stays open, priority Low), DEBT-038 (a different item: `main`'s `/distill` traversal), DEBT-039, DEBT-040, DEBT-041.
- Upstream references (reconciliation §12): `moby/moby#52537` and `moby/moby#53551` (socketcall/`AF_VSOCK`; Engine 29.8.0). The installed Docker 29.1.3 predates both.
- Draft PR body for the docs PR (Appendix A below). Attribution lines for commits and PRs are set by the session environment; do not hand-copy session URLs from this file.
- Repository cautions: PR merges use a **merge commit** and a head-SHA guard; `sandbox-fabric` is unprotected (so a push can land without review: never force); the `tests` gate in CI tolerates only manifest-listed failures and the manifest must never be used to hide a gate.

## 17. Next Steps

In order. Steps 0 and 1 precede everything.

0. **Resume and verify** (section 18). Expected: the refs in section 7; no code changes needed.
1. **Land the docs PR: PR #72** (`docs/network-isolation-spec-and-studies` → `sandbox-fabric`; it already exists; if it was closed or replaced, recreate it from the compare link `https://github.com/1h0lde4/ocbrain-v4.1/compare/sandbox-fabric...docs/network-isolation-spec-and-studies?expand=1` with the body in Appendix A). Verify the PR's diff is exactly three files under `docs/architecture/` and base `4f4578a`. Merge **as a merge commit, guarded by the head SHA `8847ccd…`**, only on the user's explicit instruction (section 15). After the merge: `git ls-remote` shows `sandbox-fabric` beyond `4f4578a` and `git diff 4f4578a origin/sandbox-fabric --name-only` lists the three docs.
2. **Hermetic C2 test PR** (new branch from the merged `sandbox-fabric`, e.g. `fix/test-c2-hermetic-upstream`; its own PR; touches only `tests/core/sandbox/test_docker_backend.py`):
   a. Read the test at ~line 702 and its fixture `net_backend`; keep it exercising **the same tunnel and allowlist path** (CONNECT through the sandbox's `AllowlistProxy`), replacing only the external upstream with a deterministic host-local loopback server the test starts and stops itself.
   b. Prove: passes with DNS broken (for example, run it with `example.com` unresolvable, such as an invalid resolver or a hosts override, inside a scratch process, not committed); repeated runs (≥20); mutation check (reject the allowed host, break the tunnel, drop the data: the test must fail each time); the full `tests/core/sandbox` suite shows **153 passed**; mypy and `check_drift.py` clean.
   c. Do not add anything to the known-failures manifest, do not add retries or sleeps, do not touch `admission.py`/`_net_proxy.py`. Assess the other `example.com`/`example.org` uses in the two test files and **report** them; widen the PR only with the user's agreement.
   d. Merge (merge commit, guarded) only on an explicit instruction, then **revalidate the merged tip** (full suite, 0 failures, in an environment where Docker works) and record the exact commands and outcomes. Only then may anyone say the base is behaviorally verified, and only for that environment.
3. **Decide Q11b** (`b01-base`) with the user, then start **B01** (red contract-conformance suite, strict expected-failure markers naming DEBT-039 and DEBT-040; specification §16 B01) on its own branch and PR.
4. In the ruled order: **B02** (`NET_NAMESPACE` direct gate), **B03** (capacity and IPv6 guard primitives), **B05** (H2 comparative study), then **B04** (`NamespaceBackend` audit, after B01). **DG-1** after B01 and B05; **DG-2** after B04: both are user decisions.
5. Only if DG-1 selects T-FW: **B10** (provisioning script and verification), **B11**, **B12** (canary; pinned image digest), **B13**, **B21**, **B22**; B14 is optional and needs an IPv6-capable host; **B30** is gated by DG-2. DEBT-041 hardening is scheduled after B13 and B21 (OD-8). Every batch runs `python3 scripts/check_drift.py`, has its own branch, PR and evidence recorded in the reconciliation document (OD-6).
6. Docs housekeeping, separate small PRs: reconcile specification §16 B00 and §19 "Still open"; fix the "(F9)" cross-reference nit in the redesign study; register closures in `KNOWN_ISSUES.md` only through its own PR from `main`.

## 18. Resume Instructions

1. `git clone https://github.com/1h0lde4/ocbrain-v4.1.git` (public; reads need no token) or attach the repository with push access; `git fetch origin sandbox-fabric docs/network-isolation-spec-and-studies handoff/sandbox-network-isolation-v4`.
2. Verify the remote: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/sandbox-fabric refs/heads/docs/network-isolation-spec-and-studies refs/heads/sandbox-network-isolation/b01-base refs/heads/handoff/sandbox-network-isolation-v4 refs/heads/main`. Expect `sandbox-fabric` and `b01-base` at `4f4578a…` **or beyond** (if the docs PR was merged), the docs branch at `8847ccd…`, and `main` at `27d918d…` or beyond.
3. Verify this file against the repository (section 6 lists what is verifiable): `git merge-base --is-ancestor 4f4578a origin/sandbox-fabric`; `git diff 4f4578a 8847ccd --name-only`; `git diff 0411e6c 4f4578a --name-only | grep -v '^docs/'` is empty. **If anything contradicts this file, the repository wins: correct the handoff, then resume.**
4. Check whether a PR for the docs branch already exists (the user may have opened and merged it). If it is merged, skip step 1 of section 17.
5. Read the master specification §§2, 11, 14, 16, 19 before any implementation. Do not reopen settled decisions (section 10) without a reopen condition.
6. Before any push: `git fetch`; push only if the remote tip is an ancestor of `HEAD`; never force.
7. Reply in English. Do not use, request, print or store any token (section 14).
8. Begin at section 17, step 1 (or 2 if the docs PR is already merged). Do not reconstruct completed work.

## 19. Transfer Status

Transfer status is stated for the repository at the moment of the final reply (the branch tips there are authoritative).

- Implementation checkpoint (`8847ccd`, docs only): committed and pushed; remote verified (section 13).
- This handoff: committed and pushed on `handoff/sandbox-network-isolation-v4`; its remote tip is verified in the final reply.
- No secret is recorded in this file.
- Material work remaining is **only** work not yet done (section 17); no finished work exists solely outside Git, except the items listed as non-reproducible in section 8 (none of which is required to continue).
- Not done and not claimed: a pull request for the handoff branch; any merge (PR #72 is open, unmerged); the hermetic test; any implementation batch; a full-suite run in this session.

**TRANSFER READY**, conditioned on the final reply's remote verification of this branch's tip and with this state stated plainly: the docs-only PR is **open as PR #72 and not merged**. (It was first left unopened because `gh` had no valid authentication in the v4 environment; it was opened afterwards through the REST API once the user supplied a token.)

## Appendix A. Draft PR body for the docs-only PR

**Title:** `docs(sandbox): network-isolation master specification and both studies (docs only)`

**Base:** `sandbox-fabric`. **Head:** `docs/network-isolation-spec-and-studies` (`8847ccd`).

Docs only; no code, test, script or `KNOWN_ISSUES.md` change. Adds three documents under `docs/architecture/`: the master specification (666 lines), the network-redesign study (354) and the B3 host-firewall-supplement study (677), taken byte-for-byte from `spec/sandbox-network-isolation-master` (`04dc92d`), `study/sandbox-network-redesign` (`ee525d9`) and `study/b3-host-firewall-supplement` (`34f4b38`), with two marked, non-behavioral edits ruled on October 8 2026: (1) F10 wording: the plain-HTTP `403` is not from `AllowlistProxy`; its attribution to "the host's upstream" is refined to this environment's egress layer and marked an INFERENCE (the raw appendix record is unchanged); (2) a hermeticity rule in the specification: tests needing an upstream use a host-local loopback server, never an external name.

What this does not do: select a mechanism (DG-1 is open; H2 is unevaluated), change any status (`sandbox-fabric` stays explicitly incomplete, Result 2; DEBT-021 stays open), or declare the base behaviorally verified for a 0-failure full suite in the earlier environment (user-accepted environmental classification; the hermetic test PR follows).

Verification: `git diff --name-only` lists exactly the three files; the B3 study is byte-identical to its branch; the other two differ from their branches only by the edits above. Merge as a **merge commit** only, guarded by the head SHA.
