#!/usr/bin/env bash
# Runs the revision-3 block, taken from the PROPOSED handoff.md (a7/rev3/extracted_from_proposed_file.sh), on the REAL remote branch.
# Read-only against the remote. Nothing is applied, committed or pushed.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
BLK=$S/a7/rev3/extracted_from_proposed_file.sh
CANON=https://github.com/1h0lde4/ocbrain-v4.1; BR=docs/g4-fts-errata-handoff-oct2026
echo "block sha256: $(sha256sum < $BLK | cut -d' ' -f1)  (tested file: $(sha256sum < $S/a7/verify_block_rev3.sh | cut -d' ' -f1))"
cd /home/claude/ocbrain-v4.1
echo "== A. working clone, block unmodified; origin = $(git remote get-url origin)"
bash $BLK; echo "exit status: $?"
echo "== B. fresh clone of the canonical URL (no checkout), block unmodified"
F=$S/a7/fresh3; rm -rf $F
git clone -q --no-checkout $CANON $F; echo "clone exit status: $?"
( cd $F && echo "origin = $(git remote get-url origin); branches fetched: $(git branch -r | wc -l)" && bash $BLK; echo "exit status: $?" )
echo "== C. negative controls on the real remote (modified COPIES of the block, run in the fresh clone; expected: FAIL, exit 1)"
mk() { sed -e "$1" $BLK > $S/a7/rev3/ctl_$2.sh; ( cd $F && bash $S/a7/rev3/ctl_$2.sh > $S/a7/rev3/ctl_$2.out 2>&1; rc=$?; printf '%-34s exit %s; first FAIL: %s\n' "$3" $rc "$(grep -m1 '^FAIL' $S/a7/rev3/ctl_$2.out | cut -c1-110)"; grep -c '^PASS' $S/a7/rev3/ctl_$2.out | sed 's/^/   PASS lines printed: /' ); }
mk 's/^H=[0-9a-f]\{40\}/H=d963daa502de4220411d0d0c2f19f67b3ec2682b/' C1 "C1 H set to the REV2 tip"
mk 's/^T=[0-9a-f]\{40\}/T=9407db5a01acea9684f158caa8107fb71611a102/' C2 "C2 T set to the REV3 tip"
mk "s#^BR=.*#BR=$BR-does-not-exist#" C3 "C3 branch name does not exist"
mk "s#^CANON=[^ ]*#CANON=$CANON-fork#" C4 "C4 canonical URL set to a fork name"
echo "== D. state after: nothing changed"
cd /home/claude/ocbrain-v4.1
echo "working clone HEAD: $(git rev-parse HEAD); status lines: $(git status --porcelain | wc -l)"
echo "remote REV2 tip : $(git ls-remote origin refs/heads/$BR | cut -f1)"
echo "remote REV3 tip : $(git ls-remote origin refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026 | cut -f1)"
echo "remote main     : $(git ls-remote origin refs/heads/main | cut -f1)"
gh pr view 90 --repo 1h0lde4/ocbrain-v4.1 --json state,isDraft,headRefOid,commits,changedFiles --jq '"PR #90: state=\(.state) draft=\(.isDraft) head=\(.headRefOid) commits=\(.commits|length) files=\(.changedFiles)"' 2>&1 | head -2
