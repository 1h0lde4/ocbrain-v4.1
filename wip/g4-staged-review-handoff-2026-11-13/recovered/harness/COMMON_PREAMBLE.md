# Common rules for every reviewer stage (read completely before starting)

You are an independent, adversarial reviewer in a fresh context. You are performing ONE STAGE of a staged, complete A-I review of "REV3", a ~38-line bash verification block (plus the patch that embeds it in a handoff document) from the OCBrain G4 documentation workstream. Your prompt gives your stage id, your working directory and your scope.

## Role and limits
- Review only. Do not implement corrections; do not edit any repository; do not alter the package; do not create commits, push branches or modify pull requests. Do not write or propose a rewritten block or patch. If you find a substantive weakness: record it, preserve the evidence, do not work on any fix, and keep evaluating the remaining items of YOUR stage so that the owner gets a complete matrix.
- This grants no implementation authority. Do not change or imply any governance status.

## Package
- Package: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/deliver_a5/final7/g4_rev3_independent_review_package.zip
- Its authoritative full SHA-256 is 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286. Compute the full SHA-256 yourself and compare the full value (not a filename, not a truncated prefix). Preserve the original zip byte for byte: copy it, never modify it.
- Extract the copy into pkg/ inside YOUR working directory only. Check SHA256SUMS.txt inside the package. Run Python with -I when it reads package files. Never execute anything from the package directly; copy files out to a work directory first.
- Read pkg/README_FIRST_REVIEW_BRIEF.md completely. It defines the contract, items A to I and how to work. "Criterion X exactly as specified in the original package" means the brief's item X as written; do not substitute a narrower reading. Open pkg/optional_item_I/ only if your stage is item I.

## Independence (Phase A stages)
- Work only from the package and the excerpts in your prompt. Do NOT read: anything else in the scratchpad directory, any other stage directory, anything under /home/claude, any repository, any report, addendum, evidence record, README or branch of the author, or any text about earlier reviews. If you accidentally see an author result, say so in your report.
- Do not assume anyone's earlier findings are correct. Test everything yourself.

## Safety
- Use throw-away synthetic repositories (a bare repository as origin plus a clone) built in your own directory. To run the block, copy it and substitute ONLY the CANON=, T= and H= lines (CANON must equal the synthetic origin without the .git suffix; T and H are synthetic commit hashes) unless your scope says otherwise; leave every other line unchanged.
- Dummy credentials only (for example DUMMYTOKEN-xyz). Never send anything to a public endpoint: no traffic to github.com or any host outside the machine. The sandbox has proxy variables: for any test that touches the network stack run it as `env -u HTTPS_PROXY -u https_proxy -u HTTP_PROXY -u http_proxy -u ALL_PROXY -u all_proxy NO_PROXY=127.0.0.1 ...` and use loopback addresses/ports only (dead ports such as 127.0.0.1:1 are fine; local servers you start yourself are fine; stop them when done).
- Use GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null, fixed author and committer variables, GIT_TERMINAL_PROMPT=0.
- A wrapper named git placed first in PATH and calling the real git by absolute path can simulate transport behaviour.

## Evidence rules
- Save raw (or minimally transformed) outputs of each test under evidence/ in your directory, with a short index. Capture stdout and stderr separately where it matters, and also combined.
- Every substantive finding needs: (1) finding id, (2) exact source location (file and line), (3) reproduction conditions, (4) commands and inputs, (5) raw or minimally transformed output, (6) expected versus actual behaviour, (7) severity and impact, (8) classification OBSERVED (you ran it), REPORTED or DERIVED (reasoning only), (9) reproduction limitations, (10) whether it is substantive under the package's acceptance contract. Substantive means: any reproduced false PASS of the REV3 block; any reproduced output of a credential or URL; any claim in the patch prose that the block does not satisfy. A false FAIL alone is minor.
- Do not claim a property holds universally because selected cases passed. Do not present reasoning as observation. Do not silently omit failed, incomplete or inconclusive tests; list them.

## Report
- Write a running report to REPORT_<stage id>.md in your directory as you go. Its first line must always be `STAGE <id>: IN PROGRESS` until you are finished, then `STAGE <id>: COMPLETE`.
- Include a criteria table for your scope: each criterion has exactly ONE status from PASS, FAIL, BLOCKED, NOT RUN, with evidence references and reasoning. A criterion is FAIL if a substantive finding applies to it, PASS only if every required check ran and held, BLOCKED if something prevented you, NOT RUN if you did not run it.
- Then: findings register for your stage (using the fields above); list of anything unreviewed or unverified; environment and tool versions (git, bash, python, curl as relevant); a declaration of who you are (human or which model and version), your tools, your execution environment, and whether you had any contact with the author's results; the date; reproducibility instructions (the exact commands or scripts, saved in your directory).
- Keep command output compact (head/tail) so that you finish. If you run low on budget, write what you have and mark unfinished criteria NOT RUN or BLOCKED rather than guessing.
- Your final message must be the complete final report.
- End the report with exactly: G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.

## Budget (important)
Earlier reviewer runs were cut off by a usage limit after roughly 10 to 13 minutes of work, usually before the final report was written. Therefore: (1) within your first few minutes write REPORT_<stage id>.md with the criteria table in a provisional form (every criterion in your scope set to NOT RUN with a one-line plan) and the package-integrity result; (2) update the table and the findings register each time you finish a block of tests, not only at the end; (3) put the reproducible harness and its raw outputs in your directory as you go; (4) do not spend more than a few minutes building infrastructure before producing first results. Never overwrite a previous REPORT file; if one exists, rename it to REPORT_<stage id>_prior_N.md first.
