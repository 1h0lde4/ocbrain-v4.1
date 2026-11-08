#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
G=/home/claude/ocbrain-v4.1; W=/home/claude/wt_rev3; R=1h0lde4/ocbrain-v4.1
B2=docs/g4-fts-errata-handoff-oct2026; B3=docs/g4-fts-correctness-handoff-rev3-oct2026
echo "== local refs"; git -C $G for-each-ref --format='%(refname:short) %(objectname)' refs/heads | grep -E "docs/g4|wip-backup|^main " 
echo "== local worktrees"; git -C $G worktree list
echo "== local status (clone / worktree): $(git -C $G status --porcelain --untracked-files=all | wc -l) / $(git -C $W status --porcelain --untracked-files=all | wc -l); stash entries: $(git -C $G stash list | wc -l)"
echo "== remote tips (git ls-remote)"; git -C $G ls-remote origin refs/heads/$B2 refs/heads/$B3 refs/heads/main
echo "== REV2 branch: local tip vs remote"; echo "ahead of remote tip: $(git -C $G rev-list --count origin/$B2..$B2) (unpushed); remote tip is the pre-existing 51564e34: $([ "$(git -C $G ls-remote origin refs/heads/$B2 | cut -f1)" = "51564e34c18e5cc908cf517000ebc9bd41eaf194" ] && echo YES || echo NO)"
echo "== commits made (final shas), with files and numstat"
for c in $(git -C $G rev-parse $B2) $(git -C $G rev-parse $B3~1) $(git -C $G rev-parse $B3); do echo "-- $c"; git -C $G show --no-patch --format='   parent %p | %an | %cI | %s' $c | cut -c1-200; git -C $G show --numstat --format= $c | sed 's/^/   /'; done
echo "== cumulative change on the REV3 branch relative to the pre-push tip 2dd2e7bb"; git -C $G diff --stat 2dd2e7bb05db949a6156266cfa3430c58de09922 $(git -C $G rev-parse $B3) | cat
echo "== remote REV3 tip equals local: $([ "$(git -C $G ls-remote origin refs/heads/$B3 | cut -f1)" = "$(git -C $G rev-parse $B3)" ] && echo YES || echo NO)"
echo "== PR #90 now"; gh api repos/$R/pulls/90 --jq '"state=\(.state) draft=\(.draft) head=\(.head.sha) base=\(.base.sha) commits=\(.commits) changed_files=\(.changed_files) mergeable_state=\(.mergeable_state) updated=\(.updated_at)"'
echo "== REV3 branch vs current main"; gh api "repos/$R/compare/main...$B3" --jq '"status=\(.status) ahead_by=\(.ahead_by) behind_by=\(.behind_by) merge_base=\(.merge_base_commit.sha)"'
echo "== main now, FTS source blobs, FTS-relevant changed paths since f13bfde"
gh api repos/$R/git/ref/heads/main --jq '"main tip " + .object.sha'
for p in core/memory/backends/sqlite_storage.py core/memory/knowledge_entry.py core/memory/unified_memory.py; do gh api "repos/$R/contents/$p?ref=main" --jq '"\(.path) \(.sha)"' 2>&1 | head -1; done
echo "changed paths on main since f13bfde matching FTS patterns:"; gh api "repos/$R/compare/f13bfdefcdd197ed1f966de0b1f93037a4168af4...main" --paginate --jq '.files[].filename' | sort -u | grep -E 'sqlite_storage|unified_memory|knowledge_entry|core/memory/'; echo "(end)"
echo "overlap of main-changed paths with PR #90 files:"; gh api "repos/$R/compare/f13bfdefcdd197ed1f966de0b1f93037a4168af4...main" --paginate --jq '.files[].filename' | sort -u > $S/a6/mc.txt; gh api repos/$R/pulls/90/files --paginate --jq '.[].filename' | sort -u > $S/a6/p90.txt; comm -12 $S/a6/mc.txt $S/a6/p90.txt; echo "(end)"
echo "== format-patch of the three final commits (for the evidence bundle)"
git -C $G format-patch -1 -o $S/a6/fp $(git -C $G rev-parse $B2) >/dev/null; git -C $G format-patch -2 -o $S/a6/fp $(git -C $G rev-parse $B3) >/dev/null; ls -l $S/a6/fp | tail -n +2 | awk '{print $5, $9}'
echo "== erratum file at the remote tip"; git -C $G show $B3:docs/reports/g4-fts-correctness/DIGEST_DISCREPANCY_ERRATUM_REV3.md | sha256sum
