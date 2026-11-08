#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
P=$S/a5/proposed_diffs/P1d_handoff_section7_18_and_wording_PROPOSED.patch
cd /home/claude/ocbrain-v4.1
echo "== claim: P1d proves ancestry only with 'git rev-parse H^' and 'git cat-file -t T' (local-object checks)"
echo "P1d added/removed lines mentioning the checks:"; grep -n '^[-+].*\(rev-parse\|cat-file\|merge-base\|is-ancestor\|ls-remote\|diff --name-only\|diff-tree\)' $P | cut -c1-120
echo "merge-base/is-ancestor occurrences in P1d: $(grep -c 'merge-base\|is-ancestor' $P)   diff-tree occurrences: $(grep -c 'diff-tree' $P)"
echo "== claim: P1d verifies scope only by one cumulative 'git diff --name-only H tip'"
grep -o 'git diff --name-only [^`]*' $P | sort -u | cut -c1-200
echo "== claim: P1d's step 2 never compares the fetched ref with the live remote, nor tests the remote tree for handoff.md"
echo "cat-file -e occurrences: $(grep -c 'cat-file -e' $P); 'live' occurrences in added lines: $(grep '^+' $P | grep -ci 'live remote\|ls-remote.*differ')"
echo "== claim: section 7 should print full SHA and parent (P1d used --oneline)"; grep -o 'git log --diff-filter=A[^`]*' $P | sort -u
echo "== claim: REV3 reached 9407db5a through P3, committed November 1"
git -C /home/claude/wt_rev3 log -1 --format='%H committer-date=%cI subject=%s' 9407db5a01acea9684f158caa8107fb71611a102 | cut -c1-160
echo "== the attachment's labels F3-F5 versus mine (Addendum 1 table)"
grep -n '^| F[1-6] ' $S/deliver_a5/final3/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_1_P1_PUSHED_2026-11-01.md | cut -c1-150
echo "== index incident: what is recorded about the state BEFORE the stray read-tree"
echo "last recorded clean statuses (I35, I36):"; grep -h 'status' $S/a5/evidence/I35_*.txt | grep 'local status'; grep -h -A1 'not applied: working tree status' $S/a5/evidence/I36_*.txt | head -3; grep -h 'started-utc' $S/a5/evidence/I36_*.txt $S/a5/evidence/I40_*.txt
echo "commands between I36 and the stray command that can write the index: none recorded as such. Recorded steps in between: I37 (python read-only), I38/I39 (git fetch of remote-tracking refs, gh api), I40 apply --check/--numstat (no index write)."
echo "== what the post-repair state proves: the working tree equals HEAD"
echo "tracked files in HEAD: $(git ls-tree -r HEAD | wc -l); status lines: $(git status --porcelain | wc -l); 'git diff HEAD --stat' lines: $(git diff HEAD --stat | wc -l); staged-vs-HEAD lines: $(git diff --cached --stat | wc -l)"
echo "pre-repair counts in I41 (from the evidence file):"; grep -h -A3 'before repair' $S/a5/evidence/I41_*.txt | head -4
