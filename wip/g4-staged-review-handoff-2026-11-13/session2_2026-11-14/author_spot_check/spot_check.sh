#!/usr/bin/env bash
# Author spot-check of S6 findings S6-H-01/02 (replace ref, graft false PASS) and S6-G4-01 (git prints token).
# Synthetic local repositories only; loopback only; dummy token only. Reads the block copy, never runs it in place.
set -u
SP=/tmp/claude-0/-home-claude/3adcc49e-2c16-5b57-97ab-65b038335fc4/scratchpad
BLOCK_SRC="$SP/a9/stage_S6/pkg2/review_package/rev3/verify_block_rev3.sh"
W="$SP/author_check/w"; rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
export GIT_AUTHOR_NAME=a GIT_AUTHOR_EMAIL=a@x GIT_COMMITTER_NAME=a GIT_COMMITTER_EMAIL=a@x
export GIT_AUTHOR_DATE='2026-01-01T00:00:00Z' GIT_COMMITTER_DATE='2026-01-01T00:00:00Z'
BR=docs/g4-fts-errata-handoff-oct2026
g() { git "$@"; }

echo "== build: T -> H -> P -> M(merge of P and side)"
g init -q seed && cd seed && g checkout -q -b "$BR"
echo 1 > a.txt; g add .; g commit -q -m T;               T=$(g rev-parse HEAD)
echo h > handoff.md; g add .; g commit -q -m H;           H=$(g rev-parse HEAD)
echo h2 > handoff.md; g commit -q -am P;                  P=$(g rev-parse HEAD)
g checkout -q -b side; echo s > other.txt; g add .; g commit -q -m S
g checkout -q "$BR"; g merge -q --no-ff --no-commit -s ours side; echo h4 > handoff.md; g add handoff.md; g commit -q -m merge; M=$(g rev-parse HEAD)
# benign twin X: parent P, only handoff.md changed
g checkout -q -b twin "$P"; echo h3 > handoff.md; g commit -q -am twin; X=$(g rev-parse HEAD)
g checkout -q "$BR"; cd ..
g clone -q --bare seed origin.git
echo "T=$T H=$H P=$P M=$M X=$X"
echo "remote tip parents: $(g -C origin.git cat-file -p "$M" | grep -c '^parent') (2 = merge commit)"

mkblock() { # copy of block with ONLY CANON, T, H lines substituted
  sed -e "s|^CANON=[^ ]*|CANON=$W/origin|" -e "s|^T=[0-9a-f]*|T=$T|" -e "s|^H=[0-9a-f]*|H=$H|" "$BLOCK_SRC" > "$1"
  echo "  block copy differs from original in $(diff "$BLOCK_SRC" "$1" | grep -c '^>') line(s) (expect 3)"; }
mkblock "$W/block.sh"

run() { # label dir
  echo "--- $1"; ( cd "$2" && bash "$W/block.sh" > "$W/out.$1" 2> "$W/err.$1"; echo "exit=$?" >> "$W/out.$1" )
  grep -v '^hint' "$W/out.$1" | cut -c1-200; }

g clone -q -b "$BR" origin.git c_control;  run control_clean  c_control
g clone -q -b "$BR" origin.git c_graft;    echo "$M $P" > c_graft/.git/info/grafts; run graft c_graft
g clone -q -b "$BR" origin.git c_replace
( cd c_replace && g fetch -q ../seed "$X:refs/tmp/x" && g replace "$M" "$X" ); run replace_ref c_replace
g clone -q -b "$BR" origin.git c_replace_ctl
( cd c_replace_ctl && g fetch -q ../seed "$X:refs/tmp/x" && g replace "$M" "$X" ); echo "--- replace_ref_control (GIT_NO_REPLACE_OBJECTS=1)"
( cd c_replace_ctl && GIT_NO_REPLACE_OBJECTS=1 bash "$W/block.sh" 2>/dev/null | tail -2 | cut -c1-160 )

echo; echo "== token print by git itself (loopback 401 server, dummy token)"
cat > "$SP/author_check/srv401.py" <<'PY'
import http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(401); self.send_header("WWW-Authenticate",'Basic realm="x"'); self.send_header("Content-Length","0"); self.end_headers()
    def log_message(self,*a): pass
http.server.HTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()
PY
PORT=18401
python3 -I "$SP/author_check/srv401.py" $PORT & SRV=$!
sleep 1
g init -q c_tok && ( cd c_tok && g remote add origin "http://DUMMYTOKEN-xyz@127.0.0.1:$PORT/org/repo.git"
  env -u HTTPS_PROXY -u https_proxy -u HTTP_PROXY -u http_proxy -u ALL_PROXY -u all_proxy NO_PROXY=127.0.0.1 git ls-remote origin refs/heads/x > "$W/tok.out" 2> "$W/tok.err"; echo "git exit=$?" )
echo "[git stderr]"; cat "$W/tok.err"
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
echo "token occurrences in git stderr: $(grep -c DUMMYTOKEN-xyz "$W/tok.err")"
