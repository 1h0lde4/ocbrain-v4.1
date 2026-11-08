#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
BLOCK=$S/a7/rev2/extracted_block.sh
echo "block sha256 (as extracted from the proposed patch): $(sha256sum $BLOCK | cut -c1-64)"
echo "== 1. unmodified block, run in the working clone against the live remote branch (it only updates the remote-tracking ref)"
( cd /home/claude/ocbrain-v4.1 && bash $BLOCK; echo "exit: $?" )
echo "== 2. unmodified block, run in a fresh no-checkout clone of the remote (the attachment's condition for closing F7)"
D=$S/a7/fresh_clone; rm -rf $D
URL=$(git -C /home/claude/ocbrain-v4.1 remote get-url origin)
echo "clone source: $URL"
if git clone -q --no-checkout "$URL" $D 2>$S/a7/fresh_clone.err; then echo "fresh clone from the remote: OK"; else echo "fresh clone from the remote FAILED: $(head -c 300 $S/a7/fresh_clone.err)"; fi
if [ -d $D/.git ]; then ( cd $D && bash $BLOCK; echo "exit: $?" ); fi
echo "== state of the real clone afterwards"; cd /home/claude/ocbrain-v4.1; echo "HEAD $(git rev-parse HEAD); status lines $(git status --porcelain | wc -l); remote tip $(git ls-remote origin refs/heads/docs/g4-fts-errata-handoff-oct2026 | cut -f1)"
