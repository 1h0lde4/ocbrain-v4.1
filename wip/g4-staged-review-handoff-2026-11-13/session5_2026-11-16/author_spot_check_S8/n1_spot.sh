#!/usr/bin/env bash
# Author spot-check of S3-N1: after an identity FAIL the block still runs git fetch/ls-remote and URL credentials reach the non-canonical host.
# MUST run: env -i PATH=/usr/bin:/bin HOME=/tmp unshare -rn bash n1_spot.sh <WORKDIR> <BLOCK_SRC>   (loopback only; dummy token)
set -u; W="$1"; BLK="$2"; HERE="$(cd "$(dirname "$0")" && pwd)"; rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
python3 - <<'PY'
import fcntl, socket, struct
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
f = struct.unpack("16sH14s", fcntl.ioctl(s, 0x8913, struct.pack("16sH14s", b"lo", 0, b"")))[1]
fcntl.ioctl(s, 0x8914, struct.pack("16sH14s", b"lo", f | 1, b""))
try: socket.create_connection(("1.1.1.1", 443), timeout=3); print("LEAK"); raise SystemExit(9)
except OSError as e: print("leak guard ok:", type(e).__name__)
PY
[ $? = 0 ] || exit 9
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
T=$(printf '%040d' 1); H=$(printf '%040d' 2)
sed -e "6s/^T=[0-9a-f]\{40\}/T=$T/" -e "7s/^H=[0-9a-f]\{40\}/H=$H/" "$BLK" > block.sh   # CANON untouched
echo "block differs from pristine in $(diff "$BLK" block.sh | grep -c '^>') line(s)"
: > log.jsonl; python3 "$HERE/n1_server.py" 18401 "$W/log.jsonl" & P=$!; sleep 1
rm -rf cl; git init -q cl; ( cd cl && git remote add origin "http://dummyuser:DUMMYTOKEN-xyz@127.0.0.1:18401/1h0lde4/ocbrain-v4.1" )
( cd cl && bash "$W/block.sh" > "$W/out.txt" 2> "$W/err.txt"; echo "exit=$?" >> "$W/out.txt" )
echo "block stdout:"; cut -c1-150 "$W/out.txt" | head -14
echo "requests at the non-canonical listener 127.0.0.1:18401: $(wc -l < log.jsonl); with Authorization present: $(grep -c '"present"' log.jsonl)"; head -4 log.jsonl
echo "first stdout line is the identity FAIL: $(head -1 "$W/out.txt" | grep -c 'origin is not the canonical')"
kill $P 2>/dev/null; wait $P 2>/dev/null; true
