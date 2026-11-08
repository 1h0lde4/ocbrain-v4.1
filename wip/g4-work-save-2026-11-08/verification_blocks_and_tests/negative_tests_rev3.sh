#!/usr/bin/env bash
# Extended positive and negative tests, in throw-away synthetic repositories (no relation to the real repository).
# Runs BOTH blocks over every scenario, each on a freshly built remote:
#   rev2 = a7/verify_block.sh        rev3 = a7/verify_block_rev3.sh
# The harness substitutes only the T=, H= (and, for rev3, CANON=) lines of the block text; the logic lines are untouched.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
W=$S/a7/neg3; rm -rf $W; mkdir -p $W
REALGIT=$(command -v git); BR=docs/g4-fts-errata-handoff-oct2026
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
g() { "$REALGIT" "$@"; }
cm() { mkdir -p "$(dirname "$1")"; echo "$2" >> "$1"; g add -A; g commit -q -m "$3"; }
push_br() { g push -q origin HEAD:refs/heads/$BR; }
mkextra() { g checkout -q -b extra; echo x > KNOWN_ISSUES.md; g add -A; g commit -qm "out-of-scope commit (changes KNOWN_ISSUES.md)"; g push -q origin HEAD:refs/heads/extra; g rev-parse HEAD; }
# ---- original 11 (same construction as a7/negative_tests.sh) ----
s01() { push_br; }
s02() { cm handoff.md v2 "follow-up 1"; push_br; }
s03() { cm handoff.md v2 f1; cm handoff.md v3 f2; cm handoff.md v4 f3; push_br; }
s04() { cm handoff.md v2 f1; echo x > KNOWN_ISSUES.md; echo w >> handoff.md; g add -A; g commit -qm "f2 changes handoff.md and another file"; cm handoff.md v4 f3; push_br; }
s05() { echo x > KNOWN_ISSUES.md; echo w >> handoff.md; g add -A; g commit -qm "A: handoff.md and another file"; g rm -q KNOWN_ISSUES.md; g commit -qm "B: revert the other file"; cm handoff.md v3 "handoff-only commit"; push_br; }
s06() { g checkout -q -b alt $T; echo alt > handoff.md; g add -A; g commit -qm "X: a different handoff commit"; push_br; }
s07() { cm handoff.md v2 "follow-up"; push_br; g checkout -q -b extra; cm handoff.md v3 "commit the remote moves to after the fetch"; g push -q origin HEAD:refs/heads/extra; g rev-parse HEAD > $D/adv_after_fetch; }
s08() { g checkout -q -b side $H; sed -i '1i prepended' handoff.md; g commit -qam "side: handoff only"; g checkout -q main; echo more >> handoff.md; g commit -qam "main: handoff only"; g merge -q --no-ff side -m "merge commit"; push_br; }
s09() { g rm -q handoff.md; g commit -qm "follow-up deletes handoff.md"; push_br; }
s10() { push_br; touch $D/wrong_t; }
s11() { g push -q origin HEAD:refs/heads/main2; }
# ---- new, from the third attached review (F9-F11, s12-s16) ----
s12() { cm handoff.md v2 "follow-up"; push_br; mkextra > $D/adv_after_first_lsr; }   # remote moves right after the first ls-remote
s13() { push_br; touch $D/lsr_fail_all; }                                           # ls-remote prints the correct ref, then exits 7
s14() { cm handoff.md v2 f1; rm handoff.md; ln -s README handoff.md; g add -A; g commit -qm "handoff.md becomes a symbolic link"; push_br; }
s15() { g rm -q handoff.md; mkdir handoff.md; echo x > handoff.md/a; g add -A; g commit -qm "handoff.md replaced by a directory"; push_br; }
s16() { push_br; touch $D/fork; }                                                   # clone's origin is a fork with identical history
# ---- additional, mine ----
s17() { push_br; touch $D/lsr_fail_second; }                                        # ls-remote fails only on the final observation
s18() { push_br; g push -q origin HEAD:refs/heads/zz/refs/heads/$BR; }              # stray extra ref that ends with the branch ref
s19() { g update-index --chmod=+x handoff.md; g commit -qm "handoff.md becomes executable"; push_br; }
s20() { g push -q origin HEAD:refs/heads/zz/refs/heads/$BR; }                       # real branch missing; only a tail-matching ref exists
SC="s01:PASS s02:PASS s03:PASS s04:FAIL s05:FAIL s06:FAIL s07:FAIL s08:FAIL s09:FAIL s10:FAIL s11:FAIL s12:FAIL s13:FAIL s14:FAIL s15:FAIL s16:FAIL s17:FAIL s18:FAIL s19:FAIL s20:FAIL"
shim() { # $1 = dir. A git wrapper placed first in PATH; behaviour is switched on by marker files in the scenario dir.
  cat > $1/bin/git <<SHIM
#!/usr/bin/env bash
REAL="$REALGIT"; D="$1"; BR="$BR"
case "\$1" in
  fetch) "\$REAL" "\$@"; rc=\$?
         [ -f \$D/adv_after_fetch ] && "\$REAL" --git-dir=\$D/remote.git update-ref refs/heads/\$BR "\$(cat \$D/adv_after_fetch)"
         exit \$rc;;
  ls-remote) n=\$(cat \$D/lsr_count 2>/dev/null || echo 0); n=\$((n+1)); echo \$n > \$D/lsr_count
         "\$REAL" "\$@"; rc=\$?
         [ \$n = 1 ] && [ -f \$D/adv_after_first_lsr ] && "\$REAL" --git-dir=\$D/remote.git update-ref refs/heads/\$BR "\$(cat \$D/adv_after_first_lsr)"
         [ -f \$D/lsr_fail_all ] && exit 7
         [ -f \$D/lsr_fail_second ] && [ \$n = 2 ] && exit 7
         exit \$rc;;
  *) exec "\$REAL" "\$@";;
esac
SHIM
  chmod +x $1/bin/git; }
run1() { # $1 scenario  $2 block-name (rev2|rev3)  -> prints "PASS|FAIL<TAB>first FAIL line"
  local n=$1 blk=$2 fn; fn=$n; D=$W/$n.$blk; export D; mkdir -p $D/bin
  g init -q -b main $D/build; g init -q --bare -b main $D/remote.git
  ( cd $D/build; g remote add origin $D/remote.git
    echo base > README; g add -A; g commit -qm T0; T0=$(g rev-parse HEAD)
    mkdir -p docs; echo s > docs/study.md; g add -A; g commit -qm transfer; T=$(g rev-parse HEAD)
    printf 'a\nb\nc\nd\ne\nf\n' > handoff.md; g add -A; g commit -qm handoff; H=$(g rev-parse HEAD)
    echo "T0=$T0 T=$T H=$H" > $D/ids; g push -q origin HEAD:refs/heads/main
    $fn ) >$D/build.log 2>&1
  . $D/ids; Tuse=$T; [ -f $D/wrong_t ] && Tuse=$T0
  if [ -f $D/fork ]; then g clone -q --bare $D/remote.git $D/fork.git >/dev/null 2>&1; g clone -q $D/fork.git $D/clone >/dev/null 2>&1
  else g clone -q $D/remote.git $D/clone >/dev/null 2>&1; fi
  local blockfile=$S/a7/verify_block.sh; [ $blk = rev3 ] && blockfile=$S/a7/verify_block_rev3.sh
  sed -e "s/^T=[0-9a-f]\{40\}/T=$Tuse/" -e "s/^H=[0-9a-f]\{40\}/H=$H/" -e "s#^CANON=[^ ]*#CANON=$D/remote#" $blockfile > $D/verify.sh
  shim $D
  out=$( cd $D/clone && PATH=$D/bin:$PATH bash $D/verify.sh 2>&1 ); rc=$?
  echo "$out" > $D/out.txt
  printf '%s\t%s\n' "$([ $rc = 0 ] && echo PASS || echo FAIL)" "$(echo "$out" | grep -m1 '^FAIL' | cut -c1-76)"; }
printf '%-5s %-8s %-6s %-6s %s\n' scen required rev2 rev3 "first FAIL line of rev3"
m2=0; m3=0; fp2=0; fp3=0; ff2=0; ff3=0; n=0
for pair in $SC; do s=${pair%%:*}; req=${pair##*:}; n=$((n+1))
  r2=$(run1 $s rev2); r3=$(run1 $s rev3); g2=${r2%%$'\t'*}; g3=${r3%%$'\t'*}; f3=${r3#*$'\t'}
  [ "$g2" = "$req" ] || { m2=$((m2+1)); [ "$req" = FAIL ] && fp2=$((fp2+1)) || ff2=$((ff2+1)); }
  [ "$g3" = "$req" ] || { m3=$((m3+1)); [ "$req" = FAIL ] && fp3=$((fp3+1)) || ff3=$((ff3+1)); }
  printf '%-5s %-8s %-6s %-6s %s\n' $s $req "$g2$([ "$g2" = "$req" ] || echo ' *')" "$g3$([ "$g3" = "$req" ] || echo ' *')" "$f3"
done
echo "scenarios: $n; rev2: mismatches $m2 (false PASS $fp2, false FAIL $ff2); rev3: mismatches $m3 (false PASS $fp3, false FAIL $ff3)   [* = result differs from the required one]"
