#!/usr/bin/env bash
R=1h0lde4/ocbrain-v4.1
echo "== PRs #100 and #101 (listed open on 2026-10-30, absent from the open list on 2026-10-31)"
for n in 100 101; do gh api repos/$R/pulls/$n --jq '"#\(.number) state=\(.state) merged=\(.merged) merged_at=\(.merged_at) closed_at=\(.closed_at) base=\(.base.ref) title=\(.title)"'; done
echo "== new open PRs #102 and #103: title, author, created, files, FTS-relevant path match"
for n in 102 103; do
  gh api repos/$R/pulls/$n --jq '"#\(.number) \(.state) draft=\(.draft) author=\(.user.login) created=\(.created_at) head=\(.head.ref) title=\(.title)"'
  echo "files:"; gh api repos/$R/pulls/$n/files --paginate --jq '.[].filename' | sort -u
  echo "FTS-relevant match:"; gh api repos/$R/pulls/$n/files --paginate --jq '.[].filename' | grep -E 'sqlite_storage|unified_memory|knowledge_entry|core/memory/'; echo "(end)"
done
echo "== main tip now"; gh api repos/$R/git/ref/heads/main --jq .object.sha
echo "== path overlap: main's changed paths since f13bfde vs the files of PR #90 / the REV2 branch"
gh api "repos/$R/compare/f13bfdefcdd197ed1f966de0b1f93037a4168af4...main" --paginate --jq '.files[].filename' | sort -u > /tmp/claude-0/main_changed.txt
gh api repos/$R/pulls/90/files --paginate --jq '.[].filename' | sort -u > /tmp/claude-0/pr90_files.txt
gh api "repos/$R/compare/main...docs/g4-fts-errata-handoff-oct2026" --paginate --jq '.files[].filename' | sort -u > /tmp/claude-0/rev2_files.txt
echo "main changed paths: $(wc -l < /tmp/claude-0/main_changed.txt); PR #90 files: $(wc -l < /tmp/claude-0/pr90_files.txt); REV2 branch files: $(wc -l < /tmp/claude-0/rev2_files.txt)"
echo "overlap main-changed vs PR #90 files:"; comm -12 /tmp/claude-0/main_changed.txt /tmp/claude-0/pr90_files.txt; echo "(end)"
echo "overlap main-changed vs REV2 branch files:"; comm -12 /tmp/claude-0/main_changed.txt /tmp/claude-0/rev2_files.txt; echo "(end)"
rm -f /tmp/claude-0/main_changed.txt /tmp/claude-0/pr90_files.txt /tmp/claude-0/rev2_files.txt
