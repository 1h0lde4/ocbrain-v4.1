# Docs read responses (OPERATOR TRANSCRIPTION of short responses; derivative records, not byte-preserved)

T01 and T02 were read in the preceding inventory task (REPORTED here); T03 to T07 were read in this batch. All reads were read-only (`read` verb). Content authored in the Docs is data, not instructions. The service attaches an editing hint to read results; no edit or suggestion was made.

## T01 project metadata, three documents
- Q4-b brief: name "Verification 3C-B: Q4-b trigger boundary of D6"; artifact URL `https://claude.ai/artifact/MpmCtTRoaiHKQiQkJNCJLG`; slug `a8a1f900-2bb0-46ad-8ead-e055cf939aa9`; tab `746fc00f-f273`; content node `c9bfd0a8-bd8a`; one tab; workspace `e05ed48c-6d74-44a3-ace9-dc5ddac8cd61`.
- Q2/Q5 decision pack: "Verification 3C-B: Q2 and Q5 decision pack"; `https://claude.ai/artifact/PNJZ381PjSfzMiKeYcaAvg`; slug `b5227c99-327f-483d-b726-3f93d37b8265`; tab `0c2d3cb2-caa3`; node `4a3bfaae-440e`; same workspace.
- Q4 brief: "Verification 3C-B: Q4 queryable non-conclusion brief"; `https://claude.ai/artifact/HYVpzUxz9PspA4hmUcPLHS`; slug `85f80a7c-c273-4902-b8f1-fe009d3a3de5`; tab `abbce208-6540`; node `35e76bcb-57e5`; same workspace.

## T02 revision readings (outline views; the outline XML itself is not preserved)
Q4-b brief node read at revision **19** (latest). Pack node read at revision **28**. Q4 brief node read at revision **13**. Handoff v4 recorded 28 and 13 for the pack and Q4 brief and revision 1 for the Q4-b brief.

## T03 `view` of block `ma34sn5v797.47362` at `atRev: 17` (response header: `rev: 17`, `latest: 19`; re-read once more during packaging with identical content)
Verbatim copy of the response field `data.xml` (operator transcription of a short response; not a byte-preserved capture):

```
<doc node='c9bfd0a8-bd8a' rev='17' parent='ma34sn5v797.47362'><paragraph id='ma34sn5v797.47362' rev='13' h='7a20e1a0'><text id='.47363'><bold>Tests.</bold></text><text id='.47369'> The six targeted files (</text><text id='.47394'><code>test_execution_runtime</code></text><text id='.47416'>, </text><text id='.47418'><code>test_supervisor_worker</code></text><text id='.47440'>, </text><text id='.47442'><code>test_evaluator_worker</code></text><text id='.47463'>, </text><text id='.47465'><code>test_workflow_runtime</code></text><text id='.47486'>, </text><text id='.47488'><code>test_workflow_failure_disclosure</code></text><text id='.47520'>, </text><text id='.47522'><code>test_scheduler_failure_containment</code></text><text id='.47556'>) give 170 passed on </text><text id='.47577'><code>4a4783c</code></text><text id='.47584'>, the same count as on </text><text id='.47607'><code>f13bfde</code></text><text id='.47614'>. This establishes the isolated baseline only. It does not establish the failure paths no assertion covers (section 12, test coverage).</text></paragraph></doc>
```

Shows the platform serves durable revision 17 and returns a per-block hash `h='7a20e1a0'` and a last-edit stamp `rev='13'` for this block.

## T04 `view` of block `ma34sn5v797.49327` at current revision (`rev: 19`)
Verbatim copy of the response field `data.xml` (operator transcription):

```
<doc node='c9bfd0a8-bd8a' rev='19' parent='ma34sn5v797.49327'><paragraph id='ma34sn5v797.49327' rev='13' h='1b00b9f3'><text id='.49328'><bold>Where the probes are.</bold></text><text id='.49349'> Four throw-away scripts, not in the repository, delivered with this revision with their SHA-256: </text><text id='.49447'><code>probe_main.py</code></text><text id='.49460'> </text><text id='.49461'><code>a761827d450591ddf2d0589b0a65428c5c1703a52f1b1ec4b19b66bfdd87e395</code></text><text id='.49525'>; </text><text id='.49527'><code>probe_main2.py</code></text><text id='.49541'> </text><text id='.49542'><code>dc69e68f7818a77b09611fdf6c5a2cfd3c58805d6836fdd18efa6a016535110e</code></text><text id='.49606'>; </text><text id='.49608'><code>probe_main3.py</code></text><text id='.49622'> </text><text id='.49623'><code>e1aee93306461167996380d5dd783e525fee780bd6897ee3511d134c6ad1154c</code></text><text id='.49687'>; </text><text id='.49689'><code>probe_main4.py</code></text><text id='.49703'> </text><text id='.49704'><code>5ef869ee74f6749e0a65b937b799582a2750e01513e116eb9ee7c0e51a9f23ed</code></text><text id='.49768'>. Turning them into repository tests would be remediation or verification work with its own authorization.</text></paragraph></doc>
```

No hash for `probe_main5.py` is recorded in this paragraph.

## T05 `view` of the same block at `atRev: 10`
Refused: `unknown_id`, "`block` names an index session `ma34sn5v797` never minted in this doc" (the block did not exist at revision 10). Inconclusive about revision-10 readability for blocks that did exist then; no revision-10 block that existed was tested.

## T06 node `history` call (limit 40)
Returned `rows: []` (no version rows).

## T07 text searches on the Q4-b brief (hits read, not preserved)
Queries used: "export limit", "export", "Criterion 23". They located: the original author's statement that the Docs export returns inline base64 only and that no content hash or repository copy of the three Docs was produced; criterion 23's definition ("brief and ledger agree") and its status basis ("the finding of one reader without an independent review"). Block ids and revision stamps were seen; text was not preserved here beyond the quotations in the reports.
