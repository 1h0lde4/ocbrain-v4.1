#!/usr/bin/env bash
# Read-only: confirm from the scenario directories left by negative_tests_rev3.sh that each shim/marker really engaged.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad; W=$S/a7/neg3; BR=docs/g4-fts-errata-handoff-oct2026
tip() { git --git-dir=$1/remote.git rev-parse -q --verify refs/heads/$BR || echo none; }
for blk in rev2 rev3; do
  echo "== $blk"
  d=$W/s12.$blk; echo "s12 ls-remote calls=$(cat $d/lsr_count) remote tip now == advance commit: $([ "$(tip $d)" = "$(cat $d/adv_after_first_lsr)" ] && echo yes || echo NO); advance commit touches: $(git --git-dir=$d/remote.git diff-tree --no-commit-id --name-only -r $(cat $d/adv_after_first_lsr)) ; first line of out: $(grep -m1 -E '^(PASS|FAIL)' $d/out.txt | cut -c1-90)"
  d=$W/s07.$blk; echo "s07 remote tip now == advance commit: $([ "$(tip $d)" = "$(cat $d/adv_after_fetch)" ] && echo yes || echo NO)"
  d=$W/s13.$blk; echo "s13 ls-remote calls=$(cat $d/lsr_count); marker lsr_fail_all present: $([ -f $d/lsr_fail_all ] && echo yes || echo NO)"
  d=$W/s17.$blk; echo "s17 ls-remote calls=$(cat $d/lsr_count); marker lsr_fail_second present: $([ -f $d/lsr_fail_second ] && echo yes || echo NO)"
  d=$W/s14.$blk; echo "s14 remote tree entry for handoff.md: $(git --git-dir=$d/remote.git ls-tree refs/heads/$BR -- handoff.md | cut -c1-12)"
  d=$W/s15.$blk; echo "s15 remote tree entry for handoff.md: $(git --git-dir=$d/remote.git ls-tree refs/heads/$BR -- handoff.md | cut -c1-12); first FAIL: $(grep -m1 '^FAIL' $d/out.txt | cut -c1-80)"
  d=$W/s19.$blk; echo "s19 remote tree entry for handoff.md: $(git --git-dir=$d/remote.git ls-tree refs/heads/$BR -- handoff.md | cut -c1-12)"
  d=$W/s16.$blk; echo "s16 clone origin == fork: $([ "$(git -C $d/clone remote get-url origin)" = "$d/fork.git" ] && echo yes || echo NO); fork refs equal canonical: $([ "$(git --git-dir=$d/fork.git rev-parse refs/heads/$BR)" = "$(tip $d)" ] && echo yes || echo NO)"
  d=$W/s18.$blk; echo "s18 refs on remote matching the branch name: $(git --git-dir=$d/remote.git for-each-ref --format='%(refname)' | grep -c "refs/heads/$BR\$")"
  d=$W/s20.$blk; echo "s20 real branch present on remote: $(git --git-dir=$d/remote.git rev-parse -q --verify refs/heads/$BR >/dev/null && echo yes || echo no); refs: $(git --git-dir=$d/remote.git for-each-ref --format='%(refname)' | grep -c "refs/heads/$BR\$")"
done
echo "== rev2 s15 (why it already failed):"; grep -m2 '^FAIL' $W/s15.rev2/out.txt | cut -c1-100
echo "== rev2 s13 output:"; tail -2 $W/s13.rev2/out.txt | cut -c1-140
echo "== rev3 s12 output:"; tail -3 $W/s12.rev3/out.txt | cut -c1-140
