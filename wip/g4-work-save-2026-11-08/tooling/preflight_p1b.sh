#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
echo "== branch / HEAD / status"; git rev-parse --abbrev-ref HEAD; git rev-parse HEAD; git status --porcelain | wc -l; git stash list | wc -l
echo "== remote tip of the REV2 branch (live)"; git ls-remote origin refs/heads/docs/g4-fts-errata-handoff-oct2026
echo "== local is exactly one commit ahead of the remote tip and its parent is the remote tip"; git rev-parse HEAD^; git log --oneline origin/docs/g4-fts-errata-handoff-oct2026..HEAD
echo "== commits after the transfer commit eca2b96 (before)"; git rev-list --count eca2b96521fba8cf792ea16a58be997e4f949356..HEAD
echo "== P1b apply check on the current tree"; git apply --check $S/a5/proposed_diffs/P1b_handoff_consistency_sentence_PROPOSED.patch && echo "P1b git apply --check exit 0"
sha256sum $S/a5/proposed_diffs/P1b_handoff_consistency_sentence_PROPOSED.patch
echo "== REV3 branch remote tip unchanged"; git ls-remote origin refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026
echo "== main tip"; git ls-remote origin refs/heads/main
echo "== backup of the P1 commit before any amend"; git branch -f wip-backup-rev2-local-f3995bd f3995bdc9c484bb43119440603c6cbe1aa70fb03 && git rev-parse wip-backup-rev2-local-f3995bd
