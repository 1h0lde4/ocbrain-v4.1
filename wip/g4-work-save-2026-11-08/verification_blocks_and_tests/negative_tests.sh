#!/usr/bin/env bash
# Negative and positive tests of the proposed verification block, in throw-away synthetic repositories (no relation to the real repository).
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
W=$S/a7/neg; rm -rf $W; mkdir -p $W
REALGIT=$(command -v git); BR=docs/g4-fts-errata-handoff-oct2026
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
g() { "$REALGIT" "$@"; }
cm() { mkdir -p "$(dirname "$1")"; echo "$2" >> "$1"; g add -A; g commit -q -m "$3"; }
push_br() { g push -q origin HEAD:refs/heads/$BR; }
orig_p1d() { # what the checks of P1d as delivered (Addendum 2) would conclude
  local H=$1 T=$2 TIP=$3 ok=1
  [ "$(g rev-parse "$H^" 2>/dev/null)" = "$T" ] || ok=0
  [ "$(g diff --name-only "$H" "$TIP" 2>/dev/null)" = "handoff.md" ] || ok=0
  [ $ok = 1 ] && echo PASS || echo FAIL; }
s01() { push_br; }
s02() { cm handoff.md v2 "follow-up 1"; push_br; }
s03() { cm handoff.md v2 f1; cm handoff.md v3 f2; cm handoff.md v4 f3; push_br; }
s04() { cm handoff.md v2 f1; echo x > KNOWN_ISSUES.md; echo w >> handoff.md; g add -A; g commit -qm "f2 changes handoff.md and another file"; cm handoff.md v4 f3; push_br; }
s05() { echo x > KNOWN_ISSUES.md; echo w >> handoff.md; g add -A; g commit -qm "A: handoff.md and another file"; g rm -q KNOWN_ISSUES.md; g commit -qm "B: revert the other file"; cm handoff.md v3 "handoff-only commit"; push_br; }
s06() { g checkout -q -b alt $T; echo alt > handoff.md; g add -A; g commit -qm "X: a different handoff commit"; push_br; }
s07() { cm handoff.md v2 "follow-up"; push_br; g checkout -q -b extra; cm handoff.md v3 "commit the remote moves to after the fetch"; g push -q origin HEAD:refs/heads/extra; g rev-parse HEAD > $D/advance_after_fetch; }
s08() { g checkout -q -b side $H; sed -i '1i prepended' handoff.md; g commit -qam "side: handoff only"; g checkout -q main; echo more >> handoff.md; g commit -qam "main: handoff only"; g merge -q --no-ff side -m "merge commit"; push_br; }
s09() { g rm -q handoff.md; g commit -qm "follow-up deletes handoff.md"; push_br; }
s10() { push_br; touch $D/wrong_t; }
s11() { g push -q origin HEAD:refs/heads/main2; }
printf '%-44s %-8s %-6s %-8s %s\n' scenario expected got P1d-orig "first FAIL line / note"
mism=0; falsepass=0
run() { local n=$1 exp=$2 fn=$3; D=$W/$n; export D; mkdir -p $D/bin
  g init -q -b main $D/build; g init -q --bare -b main $D/remote.git
  ( cd $D/build; g remote add origin $D/remote.git
    printf 'a\nb\nc\nd\ne\nf\n' > handoff0.tmp; rm handoff0.tmp
    echo base > README; g add -A; g commit -qm T0; T0=$(g rev-parse HEAD)
    mkdir -p docs; echo s > docs/study.md; g add -A; g commit -qm transfer; T=$(g rev-parse HEAD)
    printf 'a\nb\nc\nd\ne\nf\n' > handoff.md; g add -A; g commit -qm handoff; H=$(g rev-parse HEAD)
    echo "T0=$T0 T=$T H=$H" > $D/ids; g push -q origin HEAD:refs/heads/main
    $fn ) >$D/build.log 2>&1
  . $D/ids; Tuse=$T; [ -f $D/wrong_t ] && Tuse=$T0
  g clone -q $D/remote.git $D/clone >/dev/null 2>&1
  sed -e "s/^T=[0-9a-f]\{40\}/T=$Tuse/" -e "s/^H=[0-9a-f]\{40\}/H=$H/" $S/a7/verify_block.sh > $D/verify.sh
  PX=$PATH
  if [ -f $D/advance_after_fetch ]; then printf '#!/usr/bin/env bash\n%s "$@"; rc=$?\nif [ "$1" = fetch ]; then %s --git-dir=%s/remote.git update-ref refs/heads/%s %s; fi\nexit $rc\n' "$REALGIT" "$REALGIT" "$D" "$BR" "$(cat $D/advance_after_fetch)" > $D/bin/git; chmod +x $D/bin/git; PX=$D/bin:$PATH; fi
  out=$( cd $D/clone && PATH=$PX bash $D/verify.sh 2>&1 ); rc=$?
  got=$([ $rc = 0 ] && echo PASS || echo FAIL); first=$(echo "$out" | grep -m1 '^FAIL' | cut -c1-62)
  TIPREF=$( cd $D/clone && g rev-parse -q --verify refs/remotes/origin/$BR 2>/dev/null || echo HEAD )
  orig=$( cd $D/clone && orig_p1d $H $Tuse $TIPREF )
  v=ok; [ "$got" = "$exp" ] || { v="** MISMATCH **"; mism=$((mism+1)); }
  note=""; [ "$exp" = FAIL ] && [ "$orig" = PASS ] && { note="[P1d as delivered would give a false PASS]"; falsepass=$((falsepass+1)); }
  printf '%-44s %-8s %-6s %-8s %s %s %s\n' "$n" "$exp" "$got" "$orig" "$first" "$v" "$note"; echo "$out" > $D/out.txt; }
run s01_original_transfer_and_handoff PASS s01
run s02_one_later_handoff_only_commit PASS s02
run s03_three_later_handoff_only_commits PASS s03
run s04_later_commit_changes_another_file FAIL s04
run s05_other_file_changed_then_reverted FAIL s05
run s06_handoff_commit_local_not_ancestor FAIL s06
run s07_remote_moves_after_fetch FAIL s07
run s08_merge_commit_in_sequence FAIL s08
run s09_handoff_file_missing_from_tree FAIL s09
run s10_wrong_expected_parent_of_handoff FAIL s10
run s11_remote_branch_missing FAIL s11
echo "scenarios: 11; mismatches with expectation: $mism; scenarios where P1d as delivered would give a false PASS: $falsepass"
