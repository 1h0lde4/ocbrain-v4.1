#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
BR=docs/g4-fts-errata-handoff-oct2026; H=51564e34c18e5cc908cf517000ebc9bd41eaf194; T=eca2b96521fba8cf792ea16a58be997e4f949356
P=$S/a5/proposed_diffs/P1d_handoff_section7_18_and_wording_PROPOSED.patch
echo "== patch unchanged since I40 and still applies to the pushed tree"; sha256sum $P; git apply --check $P && echo "P1d git apply --check exit 0"
echo "== simulate: a dangling commit = pushed tip + P1d, built with a temporary index file (no ref, no real index, no working-tree change)"
export GIT_INDEX_FILE=$S/a6/p1d/tmp_index; rm -f $GIT_INDEX_FILE
git read-tree origin/$BR
B=$(git hash-object -w $S/a6/p1d/b/handoff.md)
git update-index --cacheinfo 100644,$B,handoff.md
TREE=$(git write-tree)
unset GIT_INDEX_FILE
SIM=$(GIT_AUTHOR_NAME=sim GIT_AUTHOR_EMAIL=sim@example.invalid GIT_COMMITTER_NAME=sim GIT_COMMITTER_EMAIL=sim@example.invalid git commit-tree $TREE -p origin/$BR -m "simulation only, not a branch")
echo "SIM commit (dangling, unreferenced): $SIM"
echo "== the proposed step 2 commands, run on the simulated tip"
echo "handoff commit parent: $(git rev-parse $H^)  expected $T: $([ "$(git rev-parse $H^)" = "$T" ] && echo OK || echo MISMATCH)"
echo "handoff commit is an ancestor of the simulated tip: $(git merge-base --is-ancestor $H $SIM && echo YES || echo NO)"
echo "commits after the handoff commit:"; git log --oneline $H..$SIM | cut -c1-80
echo "paths changed after the handoff commit (must be only handoff.md):"; git diff --name-only $H $SIM
echo "section 7 lookup by hash: $(git log --diff-filter=A --oneline $SIM -- handoff.md | cut -c1-60)"
echo "simulated tip differs from the pushed tip in: $(git diff --name-only origin/$BR $SIM)"
echo "== the proposed text of section 7 and step 2 as they would read"
git show $SIM:handoff.md | grep -n '^- Handoff commit:\|^2\. Verify the transfer commit' | cut -c1-700
echo "== nothing real changed"; echo "real status lines: $(git status --porcelain | wc -l); HEAD $(git rev-parse HEAD); remote tip $(git ls-remote origin refs/heads/$BR | cut -f1)"
rm -f $S/a6/p1d/tmp_index
