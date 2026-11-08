#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
R=1h0lde4/ocbrain-v4.1; BR=docs/g4-fts-errata-handoff-oct2026; T=eca2b96521fba8cf792ea16a58be997e4f949356
git fetch -q origin "+refs/heads/$BR:refs/remotes/origin/$BR"
echo "== attachment claim 1: REV2 history is eca2b96 -> 51564e34 -> d963daa5 (parents, live remote branch)"
git log --format='%h parent=%p %s' $T..origin/$BR | cut -c1-110
echo "tip: $(git rev-parse origin/$BR)"; echo "live: $(git ls-remote origin refs/heads/$BR)"
echo "== claim 2: section 18 step 2 text on the pushed branch (quoted from the file)"
git show origin/$BR:handoff.md | grep -n 'exactly one later commit' | cut -c1-420
echo "== claim 2b: section 7 lookup and the section-19 rule, run literally on the pushed branch"
echo "git log --oneline -1 -- handoff.md  ->  $(git log --oneline -1 origin/$BR -- handoff.md | cut -c1-80)"
echo "git log --diff-filter=A --oneline -- handoff.md  ->  $(git log --diff-filter=A --oneline origin/$BR -- handoff.md | cut -c1-80)"
echo "parent of the tip: $(git rev-parse origin/$BR^)  (section 18 step 2 expects $T)"
git show origin/$BR:handoff.md | grep -n 'If step 2 of §18 fails' | cut -c1-200
echo "== does P1c (as built) change section 7 or section 18 text? (lines touched by the patch)"
grep -c '^[-+].*§18 step 2\|^[-+].*Parent commit of the handoff commit' $S/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED.patch
grep -n '^@@' $S/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED.patch
echo "section 18 step 2 line numbers in the file (P1c hunks must not include them):"; git show origin/$BR:handoff.md | grep -n 'exactly one later commit\|^## 18\|^## 7\.' | cut -c1-80
echo "== claim 4: PR #90 against current main"
gh api repos/$R/pulls/90 --jq '"pr90: state=\(.state) draft=\(.draft) base=\(.base.sha) head=\(.head.sha) commits=\(.commits) changed_files=\(.changed_files)"'
gh api "repos/$R/compare/main...docs/g4-fts-correctness-handoff-rev3-oct2026" --jq '"pr-branch vs main: status=\(.status) ahead_by=\(.ahead_by) behind_by=\(.behind_by) merge_base=\(.merge_base_commit.sha)"'
echo "main tip: $(git ls-remote origin refs/heads/main)"
gh api "repos/$R/compare/f13bfdefcdd197ed1f966de0b1f93037a4168af4...main" --paginate --jq '.files[].filename' > $S/a6/main_changed_since_base.txt 2>/dev/null
echo "files changed on main since the shared base f13bfde: $(sort -u $S/a6/main_changed_since_base.txt | wc -l)"
gh api repos/$R/pulls/90/files --paginate --jq '.[].filename' | sort -u > $S/a6/pr90_files.txt
echo "PR #90 files: $(wc -l < $S/a6/pr90_files.txt)"; echo "overlap count: $(sort -u $S/a6/main_changed_since_base.txt | comm -12 - $S/a6/pr90_files.txt | wc -l)"
echo "== claim 5: DEBT-042 in KNOWN_ISSUES.md on main"
gh api "repos/$R/contents/KNOWN_ISSUES.md?ref=main" --jq '.content' 2>/dev/null | base64 -d 2>/dev/null | grep -n 'DEBT-042' | cut -c1-260 | head -5
