#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
git apply $S/a5/proposed_diffs/P1b_handoff_consistency_sentence_PROPOSED.patch && echo "P1b applied (exit 0)"
git diff --check && echo "git diff --check clean"
git add handoff.md && git commit -q --amend -F $S/a6/msgs/p1_commit_v3.txt && echo "amended -> $(git rev-parse HEAD) parent $(git rev-parse HEAD^)"
echo "== diff of the final commit against the remote tip (must be handoff.md only, +6/-0)"; git diff --numstat 51564e34c18e5cc908cf517000ebc9bd41eaf194 HEAD; git diff --stat 51564e34c18e5cc908cf517000ebc9bd41eaf194 HEAD | tail -1
echo "== handoff.md after: level-2 headings / lines / CR / trailing-whitespace check"; echo "headings: $(grep -c '^## ' handoff.md); lines: $(wc -l < handoff.md); CR: $(tr -cd '\r' < handoff.md | wc -c)"
echo "== commits after the transfer commit eca2b96 now"; git rev-list --count eca2b96521fba8cf792ea16a58be997e4f949356..HEAD; git log --format='%h %an <%ae> %s' eca2b96521fba8cf792ea16a58be997e4f949356..HEAD | cut -c1-150
echo "== the added lines (full text, for the record)"; git diff 51564e34c18e5cc908cf517000ebc9bd41eaf194 HEAD | grep '^+' | grep -v '^+++'
echo "== tree compare with the P1+P1b expectation: commit tree equals the backup commit's tree except handoff.md only"; git diff --name-only wip-backup-rev2-local-f3995bd HEAD
echo "== status"; git status --porcelain | wc -l
