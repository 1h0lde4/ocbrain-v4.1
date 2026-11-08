#!/usr/bin/env bash
# Stage the curated work files for the temporary save branch. Copies only; modifies nothing in the sources.
set -euo pipefail
S=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad
ROOT=$S/save_stage/wip/g4-work-save-2026-11-08
rm -rf $S/save_stage; mkdir -p $ROOT/{reports,evidence_bundles,review_package,evidence_records,proposed_patches,verification_blocks_and_tests,tooling}
cp $S/deliver_a5/*.md $ROOT/reports/
cp $S/deliver_a5/final6/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_4_*.md $S/deliver_a5/final7/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_5_*.md $S/deliver_a5/final8/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_6_*.md $ROOT/reports/
cp $S/a5/OCBRAIN_G4_FTS_AUTHENTICATION_RECONCILIATION_REPORT.md $ROOT/reports/
for z in $S/deliver_a5/*.zip; do case "$z" in *delivery_all_files*) ;; *) cp "$z" $ROOT/evidence_bundles/;; esac; done
cp $S/deliver_a5/final6/g4_attachment_af046c14_p1d_rev3_block_tests_evidence_I51-I64.zip $S/deliver_a5/final7/g4_addendum_5_evidence_I68-I72.zip $S/deliver_a5/final8/g4_addendum_6_evidence_I76-I79.zip $ROOT/evidence_bundles/
cp $S/deliver_a5/final7/g4_rev3_independent_review_package.zip $ROOT/review_package/
cp $S/a5/evidence/*.txt $S/a5/evidence/*.md $ROOT/evidence_records/ 2>/dev/null || cp $S/a5/evidence/*.txt $ROOT/evidence_records/
cp -r $S/a5/proposed_diffs/. $ROOT/proposed_patches/
cp $S/a7/*.sh $ROOT/verification_blocks_and_tests/
for f in $S/a6_scripts/*; do case "$(basename $f)" in test_download_page.py|build_download_page.py|download_page_template.html) ;; *) cp "$f" $ROOT/tooling/;; esac; done
cp $S/a5/ev.sh $S/a5/prompt_fidelity.py $ROOT/tooling/
find $ROOT -type f -exec chmod 644 {} +
echo "staged files: $(find $ROOT -type f | wc -l); size: $(du -sh $ROOT | cut -f1)"
