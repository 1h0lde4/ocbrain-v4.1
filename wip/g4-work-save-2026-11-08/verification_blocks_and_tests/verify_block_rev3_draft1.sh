# Verify the REV2 checkpoint against the REMOTE branch. Run as a script (bash verify.sh) from a clone of the repository.
# PASS means only this: at the final live observation below, the remote tip was the verified tip. It does not read what later commits write inside handoff.md.
set -o pipefail
CANON=https://github.com/1h0lde4/ocbrain-v4.1   # the canonical repository
BR=docs/g4-fts-errata-handoff-oct2026
T=eca2b96521fba8cf792ea16a58be997e4f949356   # transfer commit
H=51564e34c18e5cc908cf517000ebc9bd41eaf194   # handoff commit
fail=0; bad() { echo "FAIL: $*"; fail=1; }
live() { # prints the live tip; fails unless ls-remote succeeds and returns exactly one ref with the exact name
  local out; out=$(git ls-remote origin "refs/heads/$BR") || return 1
  [ "$(printf '%s\n' "$out" | grep -c .)" = 1 ] || return 1
  set -- $out; [ "$2" = "refs/heads/$BR" ] || return 1
  echo "$1"; }
URL=$(git remote get-url origin 2>/dev/null)
case "$URL" in git@github.com:*) URL=https://github.com/${URL#git@github.com:};; ssh://git@github.com/*) URL=https://github.com/${URL#ssh://git@github.com/};; esac
[ "${URL%.git}" = "$CANON" ] || bad "origin ($URL) is not the canonical repository ($CANON)"
git fetch origin "+refs/heads/$BR:refs/remotes/origin/$BR" || bad "fetch of the remote branch failed"
LIVE=$(live) || bad "git ls-remote failed or did not return exactly one matching ref"
TIP=$(git rev-parse --verify -q "refs/remotes/origin/$BR") || bad "no fetched remote-tracking ref"
[ -n "$LIVE" ] && [ "$LIVE" = "$TIP" ] || bad "live remote tip (${LIVE:-none}) differs from the fetched tip (${TIP:-none})"
set -- $(git ls-tree "$TIP" -- handoff.md)
[ "$#" = 4 ] && [ "$1 $2" = "100644 blob" ] && [ "$4" = handoff.md ] || bad "handoff.md is not a regular file (mode 100644, blob) in the remote tree"
git merge-base --is-ancestor "$T" "$TIP" || bad "the transfer commit is not an ancestor of the remote tip"
git merge-base --is-ancestor "$H" "$TIP" || bad "the handoff commit is not an ancestor of the remote tip"
[ "$(git show -s --format=%P "$H")" = "$T" ] || bad "the parents of the handoff commit are not exactly the transfer commit"
[ "$(git log --diff-filter=A --format='%H %P' "$TIP" -- handoff.md)" = "$H $T" ] || bad "handoff.md was not added by the handoff commit"
prev=$H
for c in $(git rev-list --reverse --topo-order "$H..$TIP"); do
  [ "$(git show -s --format=%P "$c")" = "$prev" ] || bad "$c is not a single-parent child of $prev"
  [ "$(git diff-tree --no-commit-id --name-only -r "$prev" "$c")" = "handoff.md" ] || bad "$c does not change handoff.md alone"
  echo "follow-up: $(git log -1 --format='%H %s' "$c")"
  prev=$c
done
[ "$prev" = "$TIP" ] || bad "the follow-up sequence does not end at the remote tip"
LIVE2=$(live) || bad "the final git ls-remote failed or did not return exactly one matching ref"
[ "$LIVE2" = "$TIP" ] || bad "the remote branch moved during verification (now ${LIVE2:-unknown})"
[ "$fail" = 0 ] && { echo "PASS at $(date -u +%Y-%m-%dT%H:%M:%SZ): remote tip $TIP; handoff commit $H on $BR; $(git rev-list --count "$H..$TIP") follow-up(s), each a single-parent child changing handoff.md alone"; exit 0; }
echo "TRANSFER INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED"; exit 1
