#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
BR=docs/g4-fts-errata-handoff-oct2026; H=51564e34c18e5cc908cf517000ebc9bd41eaf194; T=eca2b96521fba8cf792ea16a58be997e4f949356
mkdir -p $S/a6/p1d/a $S/a6/p1d/b
git show origin/$BR:handoff.md > $S/a6/p1d/a/handoff.md
python3 -I - $S/a6/p1d/a/handoff.md $S/a6/p1d/b/handoff.md <<'PY'
import sys
t=open(sys.argv[1],encoding='utf-8',newline='').read()
def rep(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a[:70]); t=t.replace(a,b)
H="`51564e34c18e5cc908cf517000ebc9bd41eaf194`"; T="`eca2b96521fba8cf792ea16a58be997e4f949356`"
# section 7: identify the handoff commit by hash, not by the path-filtered log
rep("- Handoff commit: the commit that adds this file (`git log --oneline -1 -- handoff.md` on the branch). Its own hash cannot be stored inside the file.",
    "- Handoff commit: "+H+", the commit that adds this file (find it with `git log --diff-filter=A --oneline -- handoff.md` on the branch). When this file was first written its own hash could not be stored inside it. A later documentation-only commit added the entry in section 16 (\"Related documents and earlier revision\"); `git log --oneline -1 -- handoff.md` therefore returns that later commit, not the handoff commit.")
# step 2 of section 18: hash-based, tolerant of later documentation-only commits that touch only handoff.md
rep("(the branch must contain it; it should contain exactly one later commit, the handoff commit, whose parent is `eca2b96521fba8cf792ea16a58be997e4f949356`). If the branch tip is not the handoff commit or the handoff file is missing on the remote, **the transfer is INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED**: say so before doing anything else.",
    "(the branch must contain it). Then verify the handoff commit "+H+": it must be on the branch and its parent must be "+T+" (`git rev-parse 51564e34c18e5cc908cf517000ebc9bd41eaf194^`). Commits after it are documentation-only follow-ups: list them with `git log --oneline 51564e34c18e5cc908cf517000ebc9bd41eaf194..origin/docs/g4-fts-errata-handoff-oct2026`, and `git diff --name-only 51564e34c18e5cc908cf517000ebc9bd41eaf194 origin/docs/g4-fts-errata-handoff-oct2026` must list only `handoff.md`; report each follow-up commit and its scope. If the handoff commit is not on the branch, its parent is not the transfer commit, a later commit changes any other path, or the handoff file is missing on the remote, **the transfer is INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED**: say so before doing anything else.")
# the entry added by P1/P1b: replace the count-based sentence with one that does not go stale
rep("The branch therefore holds two commits after the transfer commit `eca2b96521fba8cf792ea16a58be997e4f949356`: `51564e34…`, then the commit that adds this entry. The \"exactly one later commit\" of §18 step 2 and the `git log --oneline -1 -- handoff.md` of §7 refer to `51564e34…`; a branch tip that differs from it only for this reason does not make the transfer INCOMPLETE.",
    "This entry, and the corrections to section 7 and to step 2 of section 18 that accompany it, were added in later documentation-only commits. Section 7 and step 2 now identify the handoff commit by hash and accept later commits that change only `handoff.md`; they no longer depend on the number of commits after the transfer commit or on the path-filtered `git log`.")
rep("That set was not reviewed in the session that first wrote this file; a later audit session compared it with this REV2 set (evidence outside this repository).",
    "That set is not mentioned in, and was not reviewed for, this file as committed at `51564e34…`; a later audit session compared it with this REV2 set (evidence outside this repository).")
rep("(commit `2dd2e7bb05db949a6156266cfa3430c58de09922`, committed 2026-10-23T10:30:25Z)",
    "(commit `2dd2e7bb05db949a6156266cfa3430c58de09922`, committed 2026-10-23T10:30:25Z, the branch tip when this entry was prepared on 2026-10-31; the branch may have moved since)")
rep("failed attempts and verification evidence remain a valid historical record.",
    "failed attempts and verification evidence remain as a historical record, not endorsed or re-verified by this entry.")
open(sys.argv[2],'w',encoding='utf-8',newline='').write(t)
PY
cd $S/a6/p1d && diff -u --label a/handoff.md --label b/handoff.md a/handoff.md b/handoff.md > $S/a5/proposed_diffs/P1d_handoff_section7_18_and_wording_PROPOSED.patch
cd /home/claude/ocbrain-v4.1
git apply --check $S/a5/proposed_diffs/P1d_handoff_section7_18_and_wording_PROPOSED.patch && echo "P1d git apply --check exit 0 on the pushed tree (not applied)"
git apply --numstat $S/a5/proposed_diffs/P1d_handoff_section7_18_and_wording_PROPOSED.patch
sha256sum $S/a5/proposed_diffs/P1d_handoff_section7_18_and_wording_PROPOSED.patch
echo "proposed file: headings $(grep -c '^## ' $S/a6/p1d/b/handoff.md); lines $(wc -l < $S/a6/p1d/b/handoff.md); CR $(tr -cd '\r' < $S/a6/p1d/b/handoff.md | wc -c)"
echo "== dry run of the commands the proposed step 2 would give, on the CURRENT remote branch (before any P1d)"
echo "parent of handoff commit: $(git rev-parse $H^)  expected $T"
echo "commits after the handoff commit:"; git log --oneline $H..origin/$BR | cut -c1-90
echo "paths changed after the handoff commit:"; git diff --name-only $H origin/$BR
echo "== a section 7 and step 2 check stays true if one more handoff.md-only commit is added: simulated on a temp ref (no push, no branch change)"
git read-tree --empty 2>/dev/null; true
echo "== not applied: HEAD / status / remote tip"; git rev-parse HEAD; git status --porcelain | wc -l; git ls-remote origin refs/heads/$BR
