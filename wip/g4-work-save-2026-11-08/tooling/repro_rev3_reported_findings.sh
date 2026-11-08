#!/usr/bin/env bash
# Reproduction of two findings REPORTED by the fifth reviewer launch (partial report). Loopback only; no real repository touched; the delivered block is run unmodified.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
BLOCK=$S/a7/verify_block_rev3.sh
echo "block sha256: $(sha256sum $BLOCK | cut -d' ' -f1)"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_AUTHOR_NAME=a GIT_AUTHOR_EMAIL=a@a GIT_COMMITTER_NAME=a GIT_COMMITTER_EMAIL=a@a
NOPROXY=(env -u HTTPS_PROXY -u https_proxy -u HTTP_PROXY -u http_proxy -u ALL_PROXY -u all_proxy NO_PROXY=127.0.0.1)

echo; echo "== R1: the block's own identity line (line 15), applied verbatim to look-alike URLs =="
LINE15=$(sed -n 15p "$BLOCK")
for U in 'https://127.0.0.1:18443?@github.com/1h0lde4/ocbrain-v4.1' 'https://evil.example#@github.com/1h0lde4/ocbrain-v4.1' 'https://evil.example/@github.com/1h0lde4/ocbrain-v4.1' 'https://evil.example/x?@github.com/1h0lde4/ocbrain-v4.1' 'https://github.com/1h0lde4/ocbrain-v4.1'; do
  out=$( URL="$U"; eval "$LINE15"; echo "$URL" )
  [ "${out%.git}" = "https://github.com/1h0lde4/ocbrain-v4.1" ] && v="ACCEPTED as canonical" || v="rejected"
  printf '%-62s -> %-10s (%s)\n' "$U" "$v" "$out"
done

echo; echo "== R2: which host does git/libcurl contact for the '?@' form (dead loopback port, no proxy) =="
"${NOPROXY[@]}" env GIT_CURL_VERBOSE=1 git ls-remote 'https://127.0.0.1:1?@github.com/1h0lde4/ocbrain-v4.1' 2>&1 | grep -E "Trying|Connected to|Failed to connect|Could not resolve" | head -4

echo; echo "== R3: block run end to end; dummy token in a query string, dead loopback port =="
W=$(mktemp -d $S/a5/repro_w.XXXXXX); git init -q $W/r && cd $W/r && git commit -q --allow-empty -m x
git remote add origin 'https://127.0.0.1:1/org/repo?token=DUMMYTOKENQ'
"${NOPROXY[@]}" bash $BLOCK >$W/o3.txt 2>&1; echo "block exit: $?"
echo "lines containing DUMMYTOKENQ: $(grep -c DUMMYTOKENQ $W/o3.txt)"; grep DUMMYTOKENQ $W/o3.txt | head -2
echo "control (token string absent from output): $(grep -c NOSUCHSTRINGZZ $W/o3.txt)"

echo; echo "== R4: block run end to end; token as the user name, local server answering 401 =="
python3 -I $S/a6_scripts/srv401.py 18401 & SP=$!; sleep 1
git remote set-url origin 'http://DUMMYTOKENU@127.0.0.1:18401/org/repo'
"${NOPROXY[@]}" bash $BLOCK >$W/o4.txt 2>&1; echo "block exit: $?"
echo "lines containing DUMMYTOKENU: $(grep -c DUMMYTOKENU $W/o4.txt)"; grep DUMMYTOKENU $W/o4.txt | head -2
kill $SP 2>/dev/null; wait $SP 2>/dev/null
echo; echo "== R5: git alone, same local 401 server, canonical-style username-only URL form =="
python3 -I $S/a6_scripts/srv401.py 18402 & SP=$!; sleep 1
"${NOPROXY[@]}" git ls-remote 'http://DUMMYTOKENU@127.0.0.1:18402/org/repo' 2>&1 | head -2
kill $SP 2>/dev/null; wait $SP 2>/dev/null
cd /; rm -rf "$W"; echo; echo "scratch removed"
