#!/usr/bin/env bash
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
G=/home/claude/ocbrain-v4.1; B2=docs/g4-fts-errata-handoff-oct2026; B3=docs/g4-fts-correctness-handoff-rev3-oct2026
cd $G
echo "== local clone"; git rev-parse --abbrev-ref HEAD; git rev-parse HEAD; echo "status lines: $(git status --porcelain --untracked-files=all | wc -l); stash: $(git stash list | wc -l)"
echo "origin url (credentials masked): $(git remote get-url origin | sed -E 's#//[^@/]*@#//***@#')"
echo "git user: $(git config user.name) <$(git config user.email)>"
echo "== remote tips (git ls-remote, read-only)"; git ls-remote origin "refs/heads/$B2" "refs/heads/$B3" refs/heads/main
echo "== ZIP re-measured at execution time"; Z=/mnt/user-data/attachments/d441201d-0373-573d-8f64-186072f858d3/b5f4720b-fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip
wc -c < $Z; H=$(sha256sum $Z | cut -d' ' -f1); echo $H
B=f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc; A=f9ee626551e5175a7ba0893c336a77917b8be1b4078903cc6ac5853ad7e509cc
echo "equals B: $([ "$H" = "$B" ] && echo YES || echo NO); equals A: $([ "$H" = "$A" ] && echo YES || echo NO)"
echo "== P1 against the live REV2 handoff.md"; git apply --check $S/a5/proposed_diffs/P1_handoff_provenance_note.patch && echo "P1 git apply --check exit 0"; git apply --stat $S/a5/proposed_diffs/P1_handoff_provenance_note.patch
echo "== P1 factual anchors"
echo "-- NEXT_SESSION_PROMPT_REV3.md line 12:"; git show origin/$B3:docs/reports/g4-fts-correctness/NEXT_SESSION_PROMPT_REV3.md | sed -n 12p | cut -c1-260
echo "-- continuation line 24:"; git show origin/$B3:docs/reports/g4-fts-correctness/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md | sed -n 24p
echo "-- quoted strings in the older handoff scratch copy (count):"; OH=$S/a4/final/handoff.md
for s in "TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED" "the repository contains no work of this workstream"; do printf "%s: %s\n" "$s" "$(grep -c -F "$s" $OH)"; done
echo "older handoff lines: $(wc -l < $OH); level-2 headings: $(grep -c '^## ' $OH); repo handoff level-2 headings: $(grep -c '^## ' handoff.md)"
echo "-- REV3 tip commit date: $(git log -1 --format=%cI origin/$B3)  sha $(git rev-parse origin/$B3)"
echo "== P3 against the live REV3 files (scratch copies from the REV3 tip)"
W=$S/a6/pf_p3; rm -rf $W; mkdir -p $W; ( git archive origin/$B3 IMPLEMENTATION_ROADMAP.md docs/reports/g4-fts-correctness/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md docs/reports/g4-fts-correctness/NEXT_SESSION_PROMPT_REV3.md | tar -x -C $W ) && ( cd $W && git apply --check $S/a5/proposed_diffs/P3_rev3_digest_value_A_to_B.patch && echo "P3 git apply --check exit 0" )
echo "== is the erratum target path free on the REV3 branch?"; git cat-file -e origin/$B3:docs/reports/g4-fts-correctness/DIGEST_DISCREPANCY_ERRATUM_REV3.md 2>&1 | head -1; echo "(exit shows absence if non-zero)"
