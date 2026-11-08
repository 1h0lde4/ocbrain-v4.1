#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
git show HEAD:handoff.md > $S/a6/p1c/handoff_before.md
python3 -I - $S/a6/p1c/handoff_before.md $S/a6/p1c/handoff_after.md <<'PY'
import sys
t=open(sys.argv[1],encoding='utf-8',newline='').read()
def rep(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a[:70]); t=t.replace(a,b)
# finding 1 and 2: the section-7 lookup and the staleness of the two-commit statement
rep("The branch therefore holds two commits after the transfer commit `eca2b96521fba8cf792ea16a58be997e4f949356`: `51564e34…`, then the commit that adds this entry. The \"exactly one later commit\" of §18 step 2 and the `git log --oneline -1 -- handoff.md` of §7 refer to `51564e34…`; a branch tip that differs from it only for this reason does not make the transfer INCOMPLETE.",
    "As of the commit that adds this entry, the branch holds two commits after the transfer commit `eca2b96521fba8cf792ea16a58be997e4f949356`: `51564e34…`, then the commit that adds this entry. The \"exactly one later commit\" of §18 step 2 and the `git log --oneline -1 -- handoff.md` of §7 refer to `51564e34…`; run literally, that `git log` command now prints the commit that adds this entry, while `git log --diff-filter=A --oneline -- handoff.md` prints `51564e34…`, and the parent of `51564e34…` is `eca2b96…`. A branch tip that differs from `51564e34…` only for this reason does not make the transfer INCOMPLETE; to check, `git diff 51564e34..<tip> -- handoff.md` should show only this entry.")
# finding 3: which event 'first wrote' points at
rep("That set was not reviewed in the session that first wrote this file; a later audit session compared it with this REV2 set (evidence outside this repository).",
    "That set is not mentioned in, and was not reviewed for, this file as committed at `51564e34…`; a later audit session compared it with this REV2 set (evidence outside this repository).")
# finding 4: pinned commit versus the moving branch tip
rep("(commit `2dd2e7bb05db949a6156266cfa3430c58de09922`, committed 2026-10-23T10:30:25Z)",
    "(commit `2dd2e7bb05db949a6156266cfa3430c58de09922`, committed 2026-10-23T10:30:25Z, the branch tip when this entry was prepared on 2026-10-31; the branch may have moved since)")
# finding 5: 'valid' may read as endorsement
rep("failed attempts and verification evidence remain a valid historical record.",
    "failed attempts and verification evidence remain as a historical record, not endorsed or re-verified by this entry.")
open(sys.argv[2],'w',encoding='utf-8',newline='').write(t)
PY
cd $S/a6/p1c && cp handoff_before.md a_handoff.md && cp handoff_after.md b_handoff.md
mkdir -p a b && cp handoff_before.md a/handoff.md && cp handoff_after.md b/handoff.md
diff -u --label a/handoff.md --label b/handoff.md a/handoff.md b/handoff.md > $S/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED.patch
cd /home/claude/ocbrain-v4.1
echo "== P1c: lines changed (all inside the entry added by P1/P1b)"; grep -c '^[-+][^-+]' $S/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED.patch
git apply --check $S/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED.patch && echo "P1c git apply --check exit 0 on the pushed tree"
git apply --numstat $S/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED.patch
sha256sum $S/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED.patch
echo "== not applied: working tree status / HEAD / remote tip"; git status --porcelain | wc -l; git rev-parse HEAD; git ls-remote origin refs/heads/docs/g4-fts-errata-handoff-oct2026
echo "== CR check of the proposed file"; tr -cd '\r' < $S/a6/p1c/handoff_after.md | wc -c
