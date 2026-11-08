#!/usr/bin/env bash
# Builds the P1d revision 3 PROPOSED patch against the pushed REV2 tree. Applies nothing, commits nothing, pushes nothing.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
cd /home/claude/ocbrain-v4.1
BR=docs/g4-fts-errata-handoff-oct2026
R=$S/a7/rev3; rm -rf $R; mkdir -p $R/a $R/b
git fetch -q origin "+refs/heads/$BR:refs/remotes/origin/$BR"
git show origin/$BR:handoff.md > $R/a/handoff.md
python3 -I - $R/a/handoff.md $R/b/handoff.md $S/a7/verify_block_rev3.sh <<'PY'
import sys
t=open(sys.argv[1],encoding='utf-8',newline='').read()
block=open(sys.argv[3],encoding='utf-8').read().rstrip("\n").split("\n")
def rep(a,b):
    global t
    assert t.count(a)==1,(t.count(a),a[:70]); t=t.replace(a,b)
H="`51564e34c18e5cc908cf517000ebc9bd41eaf194`"; T="`eca2b96521fba8cf792ea16a58be997e4f949356`"
rep("- Handoff commit: the commit that adds this file (`git log --oneline -1 -- handoff.md` on the branch). Its own hash cannot be stored inside the file.",
    "- Handoff commit: "+H+" (parent "+T+"), the commit that adds this file. Find it with `git log --diff-filter=A --format='%H %P %s' -- handoff.md` on the branch (expected: that hash, then the transfer commit as its only parent). When this file was first written its own hash could not be stored inside it. A later documentation-only commit added the entry in section 16 (\"Related documents and earlier revision\"); `git log --oneline -1 -- handoff.md` therefore returns that later commit, not the handoff commit.")
old2="2. Verify the transfer commit is present and unchanged: `git cat-file -t eca2b96521fba8cf792ea16a58be997e4f949356` and `git ls-remote origin refs/heads/docs/g4-fts-errata-handoff-oct2026` (the branch must contain it; it should contain exactly one later commit, the handoff commit, whose parent is `eca2b96521fba8cf792ea16a58be997e4f949356`). If the branch tip is not the handoff commit or the handoff file is missing on the remote, **the transfer is INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED**: say so before doing anything else."
new2=("2. Verify the checkpoint against the **remote** branch, not against local objects. Run the block below as a script (`bash verify.sh`) from a clone whose `origin` is the canonical repository, `https://github.com/1h0lde4/ocbrain-v4.1` (the SSH forms and a trailing `.git` are accepted; credentials in the URL are ignored and never printed; a fork, mirror or proxy URL fails the identity check by design, in which case verify from a clone of the canonical URL). The block checks, in this order: the identity of `origin`; the fetched branch tip against the live remote tip (each `git ls-remote` must succeed and return exactly one ref with the exact branch name); that `handoff.md` is a regular file (mode 100644) in the remote tree; that the transfer commit and the handoff commit are ancestors of the remote tip and that the handoff commit's parent is exactly the transfer commit; commit by commit, that every later commit is a single-parent child of the previous one that changes `handoff.md` alone; and last, that the live remote tip is still the verified tip. It must print a `PASS` line with a UTC time. `PASS` means only that the remote tip was the verified tip at that final observation: it does not read what any later commit wrote inside `handoff.md`, and the remote cannot be locked afterwards. Any `FAIL` line, or no `PASS`, means **the transfer is INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED**: say so before doing anything else. Each follow-up commit it lists is a documentation-only change to `handoff.md`; report them.\n\n   ```bash\n"
      + "\n".join(("   "+l) if l else "" for l in block) + "\n   ```")
rep(old2,new2)
rep("The branch therefore holds two commits after the transfer commit `eca2b96521fba8cf792ea16a58be997e4f949356`: `51564e34…`, then the commit that adds this entry. The \"exactly one later commit\" of §18 step 2 and the `git log --oneline -1 -- handoff.md` of §7 refer to `51564e34…`; a branch tip that differs from it only for this reason does not make the transfer INCOMPLETE.",
    "This entry, and the corrections to section 7 and to step 2 of section 18 that accompany it, were added in later documentation-only commits. Section 7 and step 2 now identify the handoff commit by hash and check the later commits one by one (each must be a single-parent child of the previous one that changes `handoff.md` alone); they no longer depend on the number of commits after the transfer commit or on the path-filtered `git log`.")
rep("That set was not reviewed in the session that first wrote this file; a later audit session compared it with this REV2 set (evidence outside this repository).",
    "That set is not mentioned in, and was not reviewed for, this file as committed at `51564e34…`; a later audit session compared it with this REV2 set (evidence outside this repository).")
rep("(commit `2dd2e7bb05db949a6156266cfa3430c58de09922`, committed 2026-10-23T10:30:25Z)",
    "(commit `2dd2e7bb05db949a6156266cfa3430c58de09922`, committed 2026-10-23T10:30:25Z, the branch tip when this entry was prepared on 2026-10-31; the branch may have moved since)")
rep("failed attempts and verification evidence remain a valid historical record.",
    "failed attempts and verification evidence remain as a historical record, not endorsed or re-verified by this entry.")
open(sys.argv[2],'w',encoding='utf-8',newline='').write(t)
PY
OUT=$S/a5/proposed_diffs/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch
cd $R && diff -u --label a/handoff.md --label b/handoff.md a/handoff.md b/handoff.md > $OUT
cd /home/claude/ocbrain-v4.1
echo "pushed tip == HEAD: $([ "$(git rev-parse origin/$BR)" = "$(git rev-parse HEAD)" ] && echo yes || echo NO) ($(git rev-parse HEAD))"
git apply --check $OUT && echo "P1d-rev3 git apply --check exit 0 on the pushed tree (not applied)"
git apply --numstat $OUT; sha256sum $OUT
echo "proposed file: headings $(grep -c '^## ' $R/b/handoff.md); lines $(wc -l < $R/b/handoff.md); CR $(tr -cd '\r' < $R/b/handoff.md | wc -c)"
echo "== byte identity of the embedded block with the tested block file"
awk '/^\+   ```bash$/{f=1;next} /^\+   ```$/{f=0} f' $OUT | sed -e 's/^+   //' > $R/extracted_from_patch.sh
awk '/^   ```bash$/{f=1;next} /^   ```$/{f=0} f' $R/b/handoff.md | sed -e 's/^   //' > $R/extracted_from_proposed_file.sh
for f in extracted_from_patch.sh extracted_from_proposed_file.sh; do
  cmp $R/$f $S/a7/verify_block_rev3.sh && echo "$f: BYTE-IDENTICAL to a7/verify_block_rev3.sh (cmp exit 0); sha256 $(sha256sum < $R/$f | cut -d' ' -f1); $(wc -l < $R/$f) lines"
done
echo "tested file sha256: $(sha256sum < $S/a7/verify_block_rev3.sh | cut -d' ' -f1)"
echo "== the harness ran this text with only T=, H= and CANON= lines substituted:"
diff $S/a7/verify_block_rev3.sh $S/a7/neg3/s02.rev3/verify.sh | grep -c '^[<>]' | sed 's/^/differing lines (expect 6 = 3 lines x 2 sides): /'
diff $S/a7/verify_block_rev3.sh $S/a7/neg3/s02.rev3/verify.sh | grep '^<' | cut -c1-24
echo "== not applied: HEAD / status / remote tip"; git rev-parse HEAD; git status --porcelain | wc -l; git ls-remote origin refs/heads/$BR | cut -f1
