#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
BR=docs/g4-fts-errata-handoff-oct2026; OLD=51564e34c18e5cc908cf517000ebc9bd41eaf194
echo "== just before the push: remote tip (live) and fast-forward test"
git ls-remote origin refs/heads/$BR
git merge-base --is-ancestor $OLD HEAD && echo "remote tip is an ancestor of HEAD: fast-forward YES"
echo "== push (no force flag)"
git push origin $BR 2>&1; echo "push exit: $?"
echo "== verify: remote tip equals local HEAD"
git ls-remote origin refs/heads/$BR; git rev-parse HEAD
git fetch origin $BR 2>&1 | tail -2
[ "$(git rev-parse origin/$BR)" = "$(git rev-parse HEAD)" ] && echo "origin/$BR == HEAD: YES"
echo "== remote handoff.md equals local handoff.md (blob)"; git rev-parse origin/$BR:handoff.md HEAD:handoff.md
echo "== remote history after the transfer commit"; git log --format='%H %s' eca2b96521fba8cf792ea16a58be997e4f949356..origin/$BR | cut -c1-140
echo "== other refs untouched: REV3 branch, main"; git ls-remote origin refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026 refs/heads/main
echo "== no PR was opened for the REV2 branch (read-only API)"; gh api "repos/1h0lde4/ocbrain-v4.1/pulls?head=1h0lde4:$BR&state=all" --jq 'length' 2>&1 | head -2
