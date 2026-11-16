#!/usr/bin/env bash
# Author spot-check of S3-F14 (false PASS with host?@github.com origin) over loopback TLS.
# MUST run inside a loopback-only network namespace and a clean environment:
#   env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp unshare -rn bash tls_spot.sh <WORKDIR> <BLOCK_SRC>
# Dummy values only. The block is the pristine package copy with ONLY the T= and H= lines substituted.
set -u
W="$1"; BLOCK_SRC="$2"; HERE="$(cd "$(dirname "$0")" && pwd)"
rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
python3 - <<'PY'
import fcntl, socket, struct
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
f = struct.unpack("16sH14s", fcntl.ioctl(s, 0x8913, struct.pack("16sH14s", b"lo", 0, b"")))[1]
fcntl.ioctl(s, 0x8914, struct.pack("16sH14s", b"lo", f | 1, b""))
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3); print("LEAK: reached 1.1.1.1"); raise SystemExit(9)
except OSError as e: print("leak guard ok: 1.1.1.1:443 ->", type(e).__name__)
PY
[ $? = 0 ] || { echo "ABORT: isolation check failed"; exit 9; }
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
export GIT_AUTHOR_NAME=a GIT_AUTHOR_EMAIL=a@x GIT_COMMITTER_NAME=a GIT_COMMITTER_EMAIL=a@x
export GIT_AUTHOR_DATE='2026-01-01T00:00:00Z' GIT_COMMITTER_DATE='2026-01-01T00:00:00Z'
BR=docs/g4-fts-errata-handoff-oct2026
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 2 -subj /CN=spot \
  -addext "subjectAltName=DNS:github.com,DNS:evil.example,IP:127.0.0.1" 2>/dev/null
# good.git: T -> H (adds handoff.md) -> F1 (changes handoff.md alone)
git init -q seed && cd seed && git checkout -q -b "$BR"
echo 1 > a.txt; git add .; git commit -q -m T;  T=$(git rev-parse HEAD)
echo h > handoff.md; git add .; git commit -q -m H; H=$(git rev-parse HEAD)
echo h2 > handoff.md; git commit -q -am F1
cd .. && mkdir srv && git clone -q --bare seed srv/good.git
echo "T=$T H=$H tip=$(git -C srv/good.git rev-parse "$BR")"
sed -e "s|^T=[0-9a-f]*|T=$T|" -e "s|^H=[0-9a-f]*|H=$H|" "$BLOCK_SRC" > block.sh
echo "block copy differs from pristine in $(diff "$BLOCK_SRC" block.sh | grep -c '^>') line(s) (expect 2: T and H only); CANON line unchanged: $(grep -c '^CANON=https://github.com/1h0lde4/ocbrain-v4.1 ' block.sh)"

run_case() { # label canon_repo evil_repo url
  local label="$1" canon_repo="$2" evil_repo="$3" url="$4"
  rm -f log.jsonl; : > log.jsonl
  python3 "$HERE/server2.py" CANON443 443  cert.pem key.pem "$PWD/srv" "$canon_repo" "$PWD/log.jsonl" & P1=$!
  python3 "$HERE/server2.py" EVIL8443 8443 cert.pem key.pem "$PWD/srv" "$evil_repo"  "$PWD/log.jsonl" & P2=$!
  sleep 1
  rm -rf client && git init -q client && ( cd client && git remote add origin "$url" )
  echo; echo "=== $label"; echo "(a) url: $(git -C client remote get-url origin)"
  echo "(b) block line 15+16 parse: $(bash -c "URL='$(git -C client remote get-url origin)'; $(sed -n 15p block.sh); echo \"parsed=\$URL\"; [ \"\${URL%.git}\" = https://github.com/1h0lde4/ocbrain-v4.1 ] && echo ACCEPT || echo REJECT" | tr '\n' ' ')"
  ( cd client && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.curloptResolve GIT_CONFIG_VALUE_0=github.com:443:127.0.0.1 \
      GIT_SSL_CAINFO="$W/cert.pem" bash "$W/block.sh" > "$W/out.$label" 2> "$W/err.$label"; echo "exit=$?" >> "$W/out.$label" )
  echo "(c) server log (who answered):"; python3 -c "
import json
for l in open('log.jsonl'):
    r=json.loads(l); print('   ',r['server'],r['listen'],'Host:',r['host_header'],'|',r['request_line'][:95],'| authz',r['authorization'],'|',r['status'])" | head -4
echo "    requests: CANON443=$(grep -c CANON443 log.jsonl) EVIL8443=$(grep -c EVIL8443 log.jsonl)"
  echo "(d) block stdout (last 2 lines):"; tail -2 "$W/out.$label" | cut -c1-210
  echo "    block stderr:"; head -2 "$W/err.$label" | cut -c1-150
  kill $P1 $P2 2>/dev/null; wait $P1 $P2 2>/dev/null
}
tok() { echo "    token occurrences: block stdout=$(grep -c DUMMYTOKEN-xyz "$W/out.$1") stderr=$(grep -c DUMMYTOKEN-xyz "$W/err.$1")"; grep -h DUMMYTOKEN-xyz "$W/err.$1" "$W/out.$1" | sort | uniq -c | cut -c1-200 | head -4; }
# F15 (i): canonical username-token form, github.com mapped to a server that answers 401 Basic
run_case F15a_tokenuser_401   UNAUTH NONE "https://DUMMYTOKEN-xyz@github.com/1h0lde4/ocbrain-v4.1"; tok F15a_tokenuser_401
# F15 (ii): same URL against a server that accepts it (a PASS run)
run_case F15b_tokenuser_ok    good   NONE "https://DUMMYTOKEN-xyz@github.com/1h0lde4/ocbrain-v4.1"; tok F15b_tokenuser_ok
# F15 (iv): token in the query string, server answers
run_case F15c_query_token_ok  good   NONE "https://github.com/1h0lde4/ocbrain-v4.1?token=DUMMYTOKEN-xyz"; tok F15c_query_token_ok
# control: user:token form against 401 (git strips the userinfo in its own messages)
run_case F15d_userpass_401    UNAUTH NONE "https://dummyuser:DUMMYTOKEN-xyz@github.com/1h0lde4/ocbrain-v4.1"; tok F15d_userpass_401
