#!/usr/bin/env bash
# v2 of the origin-identity tests (a7/identity_unit_tests.sh and its evidence I53 are kept unchanged).
# Part 1: the identity lines, extracted with grep from each block file (not retyped), over more URL forms.
# Part 2: the WHOLE block run end to end against dead loopback ports (no traffic leaves the machine), all output searched for the dummy token.
# SECRETTOKEN is a dummy string, not a credential.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
W=$S/a7/idunit2; rm -rf $W; mkdir -p $W; git init -q $W/r
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
 "no|ssh://user:SECRETTOKEN@github.com/1h0lde4/ocbrain-v4.1"
 "no|ssh://SECRETTOKEN@github.com/1h0lde4/ocbrain-v4.1"
 "no|http://SECRETTOKEN@github.com/1h0lde4/ocbrain-v4.1"
 "no|git+ssh://git:SECRETTOKEN@github.com/1h0lde4/ocbrain-v4.1"
 "no|https://github.com/1h0lde4/ocbrain-v4.1?token=SECRETTOKEN"
)
echo "##### Part 1: identity lines extracted from each block file"
for blk in verify_block_rev3_candidateA.sh verify_block_rev3.sh; do
  echo "=== $blk"; code=$(extract $S/a7/$blk); bad=0; leaks=0
  for c in "${CASES[@]}"; do exp=${c%%|*}; url=${c#*|}
    ( cd $W/r; git remote remove origin 2>/dev/null; git remote add origin "$url" )
    out=$( cd $W/r && bash -c "$code" 2>&1 ); got=yes; echo "$out" | grep -q '^FAIL' && got=no
    leak=none; echo "$out" | grep -q SECRETTOKEN && { leak=LEAKS-TOKEN; leaks=$((leaks+1)); }
    v=ok; { [ "$got" = "$exp" ] && [ $leak = none ]; } || { v='** differs **'; bad=$((bad+1)); }
    printf '  canonical-expected=%-3s got=%-3s token-in-output=%-11s %-14s %s\n' $exp $got $leak "$v" "$(echo "$url" | sed 's#SECRETTOKEN#<dummy>#')"
  done; echo "  cases: ${#CASES[@]}; differing from expectation: $bad; cases whose output contained the dummy token: $leaks"
done
echo; echo "##### Part 2: whole block end to end, dead loopback ports, proxies disabled; all stdout+stderr searched for the dummy token"
E2E=( "https://x-access-token:SECRETTOKEN@127.0.0.1:1/1h0lde4/ocbrain-v4.1" "http://SECRETTOKEN@127.0.0.1:1/1h0lde4/ocbrain-v4.1" "ssh://user:SECRETTOKEN@127.0.0.1:1/1h0lde4/ocbrain-v4.1" )
for blk in verify_block_rev3_candidateA.sh verify_block_rev3.sh; do
  echo "=== $blk"; leaks=0; n=0
  for url in "${E2E[@]}"; do n=$((n+1))
    D=$W/e2e_$n; rm -rf $D; git init -q $D; ( cd $D; git remote add origin "$url" )
    out=$( cd $D && env -u HTTPS_PROXY -u https_proxy -u HTTP_PROXY -u http_proxy -u ALL_PROXY -u all_proxy NO_PROXY='*' GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=5' timeout 60 bash $S/a7/$blk 2>&1 ); rc=$?
    leak=none; echo "$out" | grep -q SECRETTOKEN && { leak=LEAKS-TOKEN; leaks=$((leaks+1)); }
    pass=$(echo "$out" | grep -c '^PASS')
    printf '  origin form %-6s exit=%s PASS-lines=%s token-in-output=%s\n' "${url%%:*}" $rc $pass $leak
    [ $leak = LEAKS-TOKEN ] && echo "$out" | grep SECRETTOKEN | sed 's#SECRETTOKEN#<dummy>#g' | cut -c1-150 | sed 's/^/      leaked line: /'
  done; echo "  end-to-end runs: $n; runs whose output contained the dummy token: $leaks"
done
