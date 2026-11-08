#!/usr/bin/env bash
# Unit test of the origin-identity lines. The tested text is extracted with grep from the block file itself (not retyped).
# SECRETTOKEN is a dummy string, not a credential.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
W=$S/a7/idunit; rm -rf $W; mkdir -p $W; git init -q $W/r
extract() { grep -E '^(CANON=|fail=0; bad\(\)|URL=|case "\$URL" in|\[ "\$\{URL%\.git\}")' "$1"; }
CASES=(
 "yes|https://github.com/1h0lde4/ocbrain-v4.1"
 "yes|https://github.com/1h0lde4/ocbrain-v4.1.git"
 "yes|git@github.com:1h0lde4/ocbrain-v4.1.git"
 "yes|ssh://git@github.com/1h0lde4/ocbrain-v4.1.git"
 "yes|https://x-access-token:SECRETTOKEN@github.com/1h0lde4/ocbrain-v4.1"
 "yes|https://SECRETTOKEN@github.com/1h0lde4/ocbrain-v4.1.git"
 "no|https://github.com/someone-else/ocbrain-v4.1"
 "no|https://github.com/1h0lde4/ocbrain-v4.1-fork"
 "no|https://x-access-token:SECRETTOKEN@github.com/someone-else/ocbrain-v4.1"
 "no|https://evil.example/@github.com/1h0lde4/ocbrain-v4.1"
 "no|https://github.com@evil.example/1h0lde4/ocbrain-v4.1"
 "no|https://SECRETTOKEN@evil.example/1h0lde4/ocbrain-v4.1"
 "no|git@evil.example:1h0lde4/ocbrain-v4.1.git"
 "no|https://github.com/1h0lde4/ocbrain-v4.1/"
 "no|/srv/mirror/ocbrain-v4.1"
)
for blk in verify_block_rev3_draft1.sh verify_block_rev3.sh; do
  echo "=== $blk"; code=$(extract $S/a7/$blk); bad=0
  for c in "${CASES[@]}"; do exp=${c%%|*}; url=${c#*|}
    ( cd $W/r; git remote remove origin 2>/dev/null; git remote add origin "$url" )
    out=$( cd $W/r && bash -c "$code" 2>&1 ); got=yes; echo "$out" | grep -q '^FAIL' && got=no
    leak=none; echo "$out" | grep -q SECRETTOKEN && leak=LEAKS-TOKEN
    v=ok; { [ "$got" = "$exp" ] && [ $leak = none ]; } || { v='** differs **'; bad=$((bad+1)); }
    printf '  canonical-expected=%-3s got=%-3s token-in-output=%-11s %-14s %s\n' $exp $got $leak "$v" "$(echo "$url" | sed 's#SECRETTOKEN#<dummy>#')"
  done; echo "  cases: ${#CASES[@]}; differing from expectation: $bad"
done
