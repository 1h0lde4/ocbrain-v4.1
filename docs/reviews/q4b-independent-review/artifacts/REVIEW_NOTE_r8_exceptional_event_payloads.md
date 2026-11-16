# OCBrain Q4-b review note r8: exceptional-path event payloads, and scope of the r7 assessment

**INTERIM. Evidence only, read-only, no remediation, no PASS, mission not closed.** Baseline `main` `2491ae469edd` (re-verified at the end). r1-r7 untouched. r7 zip SHA-256: `3200544661e6dd553fb08730d768c9fd21b04d99d422fb70c2f7eeb2e28ca847`.

## 1. Exceptional-path events, now triggered (probe L; outputs/out_rev_l.txt)
| Event | How triggered | Actual payload keys | Joins carried |
|---|---|---|---|
| `cognitive.planner_impasse_terminal` | the repo's own fixture (`tests/test_orchestrator_recovery.py`: mocked planner returning an impasse, mocked event stream, budget of 1) | `trace_id, operation_id, interaction_id, goal_id, impasse_detail, recovery_budget_state` | `trace_id` + `operation_id` + `interaction_id` + `goal_id`; no `execution_id`, `workflow_id` or `instance_id` (no workflow exists at this point) |
| `orchestrator.response_incomplete` | K4.2 runtime-integration stack; the real `WorkflowRuntime.execute` result with `constraint_violations` overwritten by a reviewer-supplied list, so the Orchestrator's own emission code ran | `interaction_id, execution_id, constraint_violations` | `interaction_id` + `execution_id`; no `instance_id` or `workflow_id` |
Both match the source reading in r7 s5; r7's "NOT EXECUTED" for these two events is now closed. Limits: neither trigger is naturally occurring (a mocked planner; a reviewer-supplied violation list), so these are payload-shape confirmations, not reproduction of a real impasse or a real constraint failure. In the second run `orchestrator.query_completed` with `outcome: "success"` was also emitted for the same query; their relative order was not asserted. So even the path that detects an incomplete response still reports success in the completion event, consistent with the unconditional success in the K4.2 branch (FZ-01, already registered). On neither exceptional path is the interaction/execution identity joined to `instance_id`.

## 2. Scope notes on the latest assessment
- Its priority list items 1-3 (correct FZ-01 reporting, propagate `root_operation_id`, propagate worker identity at the capability bridge) are remediation. They are outside this review's read-only mandate and I am neither recommending a design nor authorizing implementation; what each would have to demonstrate is an owner decision. The evidence record keeps the two propagation gaps separately testable, as r7 s4 already states.
- "Workflow failure detection is working" is accurate only for the tested adapter-failure path. Elsewhere workflow-level outcomes can be wrong in both directions: false success at a hard deadline (T1/T3) and false failure when a progress-event write fails (F-15), both on the workflow layer independent of the K4.2 flag.
- "Concurrent identical requests must keep distinct interaction identities" is a proposed future acceptance criterion, not current behavior: K1 shows they share one `interaction_id` by design (FZ-06). Whether that must change is an owner decision.
- Voice (shipped off) was not exercised: it needs a real listener thread and audio/hotkey stack that I did not attempt. The real `ModelRouter`/provider path and `main.py`'s real composition also remain NOT EXECUTED.
- The assessment could not see the archives; their hashes are listed in r7 and above so they can be verified independently.

## 3. Boundaries
No repository, branch, PR or register change; PR #81 and #105 untouched. The GitHub token in the user's preferences was not used or stored; revoke it, replace it with a minimally scoped token, and keep it out of reports, commits and evidence archives.
