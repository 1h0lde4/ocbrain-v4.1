#!/usr/bin/env bash
# read-only repository state inventory (GitHub REST GETs only)
R=1h0lde4/ocbrain-v4.1
M=main; B3=docs/g4-fts-correctness-handoff-rev3-oct2026; B2=docs/g4-fts-errata-handoff-oct2026
echo "== branch tips"
for b in $M $B3 $B2; do printf "%-48s %s\n" "$b" "$(gh api repos/$R/git/ref/heads/$b --jq .object.sha)"; done
echo
for b in $B3 $B2; do
  echo "== compare main...$b"
  gh api "repos/$R/compare/main...$b" --jq '"status=\(.status) ahead_by=\(.ahead_by) behind_by=\(.behind_by) total_commits=\(.total_commits) merge_base=\(.merge_base_commit.sha)"'
  echo "-- changed paths relative to merge base ($b vs main, three-dot):"
  gh api "repos/$R/compare/main...$b" --paginate --jq '.files[] | "\(.status)\t\(.filename)\t+\(.additions)/-\(.deletions)"' | sort
  echo "-- commits on $b beyond the merge base (sha, author login, committer date, title):"
  gh api "repos/$R/compare/main...$b" --paginate --jq '.commits[] | "\(.sha)\t\(.author.login // "none")\t\(.commit.committer.date)\t\(.commit.message|split("\n")[0])"' | tail -n 8
  echo
done
echo "== relation REV2 branch vs REV3 branch"
gh api "repos/$R/compare/$B2...$B3" --jq '"status=\(.status) ahead_by=\(.ahead_by) behind_by=\(.behind_by) merge_base=\(.merge_base_commit.sha)"'
echo
echo "== PR #90"
gh api repos/$R/pulls/90 --jq '"state=\(.state) draft=\(.draft) author=\(.user.login) head_ref=\(.head.ref) head_sha=\(.head.sha) base_ref=\(.base.ref) base_sha=\(.base.sha) mergeable_state=\(.mergeable_state) commits=\(.commits) changed_files=\(.changed_files) created=\(.created_at) updated=\(.updated_at)"'
echo "-- any PR (any state) whose head is the REV2 branch:"
gh api "repos/$R/pulls?state=all&head=1h0lde4:$B2&per_page=20" --jq 'if length==0 then "none" else .[] | "#\(.number) \(.state) \(.title)" end'
echo "-- any other PR (any state) whose head is the REV3 branch:"
gh api "repos/$R/pulls?state=all&head=1h0lde4:$B3&per_page=20" --jq '.[] | "#\(.number) \(.state) \(.title)"'
echo
echo "== open PRs whose files include any target of P1/P2/P3 (handoff.md, IMPLEMENTATION_ROADMAP.md, docs/reports/g4-fts-correctness/)"
for n in $(gh api "repos/$R/pulls?state=open&per_page=100" --jq '.[].number' | sort -n); do
  hits=$(gh api "repos/$R/pulls/$n/files" --paginate --jq '.[].filename' | grep -E '^(handoff\.md|IMPLEMENTATION_ROADMAP\.md|docs/reports/g4-fts-correctness/)' | tr '\n' ' ')
  printf "#%s: %s\n" "$n" "${hits:-none}"
done
echo "(end)"
echo
echo "== targets on main (blob sha or 404)"
for p in IMPLEMENTATION_ROADMAP.md handoff.md docs/reports/g4-fts-correctness; do printf "%s: " $p; gh api "repos/$R/contents/$p?ref=main" --jq 'if type=="array" then "directory with \(length) entries" else .sha end' 2>&1 | head -1 | cut -c1-90; done
