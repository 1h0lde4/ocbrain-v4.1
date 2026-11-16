# GitHub governance snapshot, 2026-11-13 (read-only)

Review disposition remains OPEN - NO PASS. This is a governance record taken by authenticated read-only API calls at the owner's instruction (calls between 2026-11-13T09:02:13Z and 2026-11-13T09:02:19Z; call log: `../ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/logs/AUTH_API_CALLS.tsv`). It is **not** technical evidence recovery and does not authorize any implementation, ownership assignment or merge. Raw responses are in `raw/` (byte copies of the files in `../ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/api/`, which are untouched); `PR_INVENTORY_DERIVED.tsv` is a derivative table built from them.

| Item | Recorded state |
|---|---|
| `main` | `2491ae469edd6ef1267a14604c4f8f40d698f7ea` |
| PR #81 | state `open`, merged `False`, mergeable `False`, mergeable_state `dirty`, 13 commits, head `647b63e734792b8375c0f96593407ee651af5840`, 3 comments, 0 review comments. A dirty merge state is an integration fact, not an assignment of work. |
| Issue #105 | state `open`, assignees [], labels [], 1 comment (by `1h0lde4`, 2026-11-02T11:23:53Z), last update 2026-11-02T11:23:53Z. The API record does not establish practical ownership. |
| PR list (state=all, 105 PRs) | open 22, merged 65, closed unmerged 18 |
Merged-PR count: an earlier review reported 54 PRs merged into `main` (git ancestry, at that earlier date); the API reports 65 merged PRs across all base branches on this date. The two figures come from different methods and dates and are **not reconciled**; neither is declared erroneous.
Retrieval method: `curl` GET with a bearer credential (never stored; no token-shaped string exists in these files), `Accept: application/vnd.github+json`; no write calls. Pagination: `pulls?state=all&per_page=100`, pages 1 to 4 (pages 3 and 4 are empty if the list ended at page 2).
