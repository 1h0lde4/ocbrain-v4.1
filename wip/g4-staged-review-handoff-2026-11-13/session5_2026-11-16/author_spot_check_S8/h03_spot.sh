#!/usr/bin/env bash
# Author spot-check of S6-H-03 (block run from a clone subdirectory). Local-path origin, no network. Own construction.
# usage: env -i PATH=/usr/bin:/bin HOME=/tmp bash h03_spot.sh <WORKDIR> <BLOCK_SRC>
set -u; W="$1"; BLK="$2"; rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
export GIT_AUTHOR_NAME=a GIT_AUTHOR_EMAIL=a@x GIT_COMMITTER_NAME=a GIT_COMMITTER_EMAIL=a@x
BR=docs/g4-fts-errata-handoff-oct2026; n=0
ct() { n=$((n+1)); export GIT_AUTHOR_DATE="2026-01-01T00:00:0${n}Z" GIT_COMMITTER_DATE="2026-01-01T00:00:0${n}Z"; }
git init -q -b "$BR" seed; cd seed
ct; echo t > src.txt; git add .; git commit -qm T; T=$(git rev-parse HEAD)
ct; echo h > handoff.md; mkdir docs; echo hd > docs/handoff.md; git add .; git commit -qm H; H=$(git rev-parse HEAD)
ct; chmod +x handoff.md; git add handoff.md; git commit -qm "root handoff.md made executable"
cd ..; git clone -q --bare seed origin.git
echo "tip root handoff.md entry: $(git -C origin.git ls-tree "$BR" -- handoff.md | cut -c1-40); docs/handoff.md entry: $(git -C origin.git ls-tree "$BR" -- docs/handoff.md | cut -c1-40)"
sed -e "4s#^CANON=[^ ]*#CANON=$W/origin#" -e "6s/^T=[0-9a-f]\{40\}/T=$T/" -e "7s/^H=[0-9a-f]\{40\}/H=$H/" "$BLK" > block.sh
echo "block differs from pristine in $(diff "$BLK" block.sh | grep -c '^>') line(s) (CANON, T, H)"
git clone -q origin.git cl
echo "== from clone root (contract violated: root handoff.md is 100755) expected FAIL"
( cd cl && env -i PATH=/usr/bin:/bin HOME="$W" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 bash "$W/block.sh" 2>&1 | cut -c1-170; echo "exit=${PIPESTATUS[0]}" )
echo "== from clone/docs (subdirectory)"
( cd cl/docs && env -i PATH=/usr/bin:/bin HOME="$W" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 bash "$W/block.sh" 2>&1 | cut -c1-170; echo "exit=${PIPESTATUS[0]}" )
