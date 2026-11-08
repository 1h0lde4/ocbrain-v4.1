# Verify the REV2 checkpoint against the REMOTE branch. Run as a script (bash verify.sh) from a clone of the repository.
BR=docs/g4-fts-errata-handoff-oct2026
T=eca2b96521fba8cf792ea16a58be997e4f949356   # transfer commit
H=51564e34c18e5cc908cf517000ebc9bd41eaf194   # handoff commit
fail=0; bad() { echo "FAIL: $*"; fail=1; }
git fetch origin "+refs/heads/$BR:refs/remotes/origin/$BR" || bad "fetch of the remote branch failed"
LIVE=$(git ls-remote origin "refs/heads/$BR" | cut -f1)
TIP=$(git rev-parse --verify -q "refs/remotes/origin/$BR") || bad "no fetched remote-tracking ref"
[ -n "$LIVE" ] || bad "the remote branch does not exist"
[ "$LIVE" = "$TIP" ] || bad "live remote tip ($LIVE) differs from the fetched tip ($TIP)"
git cat-file -e "$TIP:handoff.md" 2>/dev/null || bad "handoff.md is not in the remote tree"
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
[ "$fail" = 0 ] && { echo "PASS: handoff commit $H on $BR; $(git rev-list --count "$H..$TIP") follow-up(s), each a single-parent child changing handoff.md alone"; exit 0; }
echo "TRANSFER INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED"; exit 1
