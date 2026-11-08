#!/usr/bin/env bash
# Read-only checks of the independent-review package.
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad; Z=$S/deliver_a5/final7/g4_rev3_independent_review_package.zip; F=$S/deliver_a5/final6
W=$S/a7/pkgcheck2; rm -rf $W; mkdir -p $W/x; cd $W && python3 -I -c "import zipfile; z=zipfile.ZipFile('$Z'); print('integrity:', z.testzip() or 'OK'); z.extractall('x'); print('entries:', len(z.namelist()))"
P=$W/x/review_package; ( cd $P && sha256sum -c SHA256SUMS.txt 2>&1 | sed 's/^/  /' )
echo "== package files equal the delivered files"
cmp $P/rev3/verify_block_rev3.sh $F/verify_block_rev3.sh && echo "block == delivered block (sha256 $(sha256sum < $P/rev3/verify_block_rev3.sh | cut -d' ' -f1))"
cmp $P/rev3/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch $F/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch && echo "patch == delivered patch"
cmp $P/rev2/verify_block.sh $S/a7/verify_block.sh && echo "rev2 block == the revision 2 block of Addendum 3"
git -C $S/a7 --version >/dev/null 2>&1; export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
mkdir $W/s && cd $W/s && git init -q . && cp $P/base/handoff.md . && git add handoff.md && git -c user.name=t -c user.email=t@example.invalid commit -qm base && git apply --check $P/rev3/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch && echo "git apply --check exit 0 on base/handoff.md in a scratch repository (not applied)"
echo "base/handoff.md == handoff.md of the pushed REV2 tip: $(cd /home/claude/ocbrain-v4.1 && git show origin/docs/g4-fts-errata-handoff-oct2026:handoff.md | cmp - $P/base/handoff.md && echo yes || echo NO)"
echo "== independence: the brief must not carry the author's results"
for pat in '20 of 20' 'I60' 'I61' 'I59' 'e1ccd6a7' 'false PASS of revision 2' 'mismatches'; do printf '  brief contains %-26s %s\n' "'$pat':" "$(grep -c -- "$pat" $P/README_FIRST_REVIEW_BRIEF.md)"; done
echo "  files outside optional_item_I that mention results (grep 'I6[0-9]\|20 of 20'): $(grep -rlE 'I6[0-9]|20 of 20' $P --include='*' 2>/dev/null | grep -v optional_item_I | grep -v base/handoff.md | wc -l)"
echo "== secrets scan (ghp_, github_pat_, gho_, 'Bearer ', 'password='): $(grep -rEc 'ghp_|github_pat_|gho_|Bearer |password=' $P | awk -F: '{s+=$2} END{print s+0}') hits"
echo "== files in the package:"; (cd $W/x && find review_package -type f | sort)
