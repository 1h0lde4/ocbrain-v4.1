#!/usr/bin/env python3
"""Mutation check for the CTX-AUTH-002 replacement (core/cognitive/intent.py,
core/cognitive/planner.py) and for the exit-code guards of the verification
harness live_citation_check.py.

Each mutant re-introduces one specific regression by an EXACT-string
replacement (asserted to match exactly once), runs the test files that
guard this mechanism with -x, and requires the run to FAIL ("caught"). A
mutant that leaves the tests green is a SURVIVOR and exits non-zero: either a
test gap or an equivalent mutant, to be investigated -- never waved through.

SAFETY: this script edits tracked source files in place and restores them in a
`finally`; it then verifies sha256 equality. Do not run it concurrently with
anything else touching those files, and `git status` afterwards.

Usage (from the repo root):  python3 scripts/mutation_check_ctx_auth_002.py
Exit: 0 all caught | 1 a survivor | 2 harness/anchor/baseline error.
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

INTENT = pathlib.Path("core/cognitive/intent.py")
PLANNER = pathlib.Path("core/cognitive/planner.py")
LIVE = pathlib.Path("live_citation_check.py")
TESTS = [
    "tests/core/cognitive/test_intent_security.py",
    "tests/core/cognitive/test_intent.py",
    "tests/core/cognitive/test_k42_completion.py",
    "tests/core/cognitive/test_planner.py",
    "tests/test_live_citation_check.py",
]
ELIGIBLE = 'if h.source == "request" and h.source_verified and h.content_grounded'

# (name, file, old, new)
MUTANTS = [
    ("planner mines semantic_description again", PLANNER,
     "text = description or raw_request",
     'text = goal.structured_form.get("semantic_description") or description or raw_request'),
    ("block grounding set True without checking the block", INTENT,
     "grounded = bool(label_tokens) and bool(label_tokens & _content_tokens(block.content))",
     "grounded = True"),
    ("request grounding set True without checking the request", INTENT,
     "grounded = bool(label_tokens) and bool(label_tokens & _content_tokens(raw_request_text))",
     "grounded = True"),
    ("out-of-range block index treated as verified", INTENT,
     "    if not (0 <= index < len(blocks)):\n        return False, False",
     "    if not (0 <= index < len(blocks)):\n        return True, False"),
    ("malformed source accepted", INTENT,
     "    if not match:\n        return False, False",
     "    if not match:\n        return True, True"),
    ("block citations eligible for selection", INTENT, ELIGIBLE,
     "if h.source is not None and h.source_verified and h.content_grounded"),
    ("selection drops the content_grounded requirement", INTENT, ELIGIBLE,
     'if h.source == "request" and h.source_verified'),
    ("selection drops the source_verified requirement", INTENT, ELIGIBLE,
     'if h.source == "request" and h.content_grounded'),
    ("no fail-closed default (returns hypotheses[0])", INTENT,
     'return IntentHypothesis(label="novel", score=0.1), "open_category_fallback"',
     'return hypotheses[0], "open_category_fallback"'),
    ("picks the LOWEST eligible score", INTENT,
     "max(eligible, key=lambda h: h.score)", "min(eligible, key=lambda h: h.score)"),
    ("selection ignores eligibility entirely", INTENT, ELIGIBLE, "if True"),
    ("rejected selection_gate key reappears", INTENT,
     '"selection_basis": selection_basis,',
     '"selection_basis": selection_basis,\n            "selection_gate": selection_basis,'),
    ("rejected authorities key reappears", INTENT,
     '"citation_grounding": [_describe_grounding(h) for h in hypotheses],',
     '"citation_grounding": [_describe_grounding(h) for h in hypotheses],\n            "authorities": [None for _ in hypotheses],'),
    ("selection_basis key dropped", INTENT, '"selection_basis": selection_basis,', ""),
    ("_describe_grounding ignores source_verified", INTENT,
     '    if not hypothesis.source_verified:\n        return "source_unresolved"',
     '    if False:\n        return "source_unresolved"'),
    ("authority field re-added to IntentHypothesis", INTENT,
     "    content_grounded: bool = False\n",
     "    content_grounded: bool = False\n    authority: Optional[AuthorityLevel] = None\n"),
    ("grounding never populated in generate_hypotheses", INTENT,
     "h.source_verified, h.content_grounded = _check_source_grounding(\n"
     "                h.label, h.source, raw_request.text, context.blocks,\n            )",
     "h.source_verified, h.content_grounded = False, False"),
    # -- exit-code guards of live_citation_check.py (ADR-KERNEL-08 section 8.1 item 1) --
    ("harness: run-count guard accepts zero", LIVE,
     "    if n < 1:\n        raise argparse.ArgumentTypeError", "    if n < 0:\n        raise argparse.ArgumentTypeError"),
    ("harness: zero runs exit 0", LIVE,
     "    elif not all_runs:\n        code = 2", "    elif not all_runs:\n        code = 0"),
    ("harness: an unexposed payload exits 0", LIVE,
     "    elif unexposed:\n        code = 2", "    elif unexposed:\n        code = 0"),
    ("harness: an unanswered payload exits 0", LIVE,
     "    elif unanswered:\n        code = 2", "    elif unanswered:\n        code = 0"),
    ("harness: exposure judged in aggregate, not per payload", LIVE,
     'unexposed = [n for n, st in per_payload.items() if st["exposed"] == 0]',
     'unexposed = list(per_payload) if all(st["exposed"] == 0 for st in per_payload.values()) else []'),
    ("harness: answering judged in aggregate, not per payload", LIVE,
     'unanswered = [n for n, st in per_payload.items() if st["exposed"] > 0 and st["answered"] == 0]',
     'unanswered = list(per_payload) if all(st["answered"] == 0 for st in per_payload.values()) else []'),
    ("harness: empty-goals guard removed", LIVE,
     "    if not goals:\n        return {", "    if False:\n        return {"),
    ("harness: run errors exit 0", LIVE,
     "    elif total_errors:\n        code = 2", "    elif total_errors:\n        code = 0"),
    ("harness: invariant failure exits 0", LIVE,
     "    if total_escalated:\n        code = 1", "    if total_escalated:\n        code = 0"),
    # -- self-coverage and provenance guards (CTX-AUTH-002 remediation, ADR-KERNEL-08 R6) --
    ("harness: self-coverage gap exits 0", LIVE,
     "    elif coverage_missing or coverage_undeclared:\n        code = 2",
     "    elif coverage_missing or coverage_undeclared:\n        code = 0"),
    ("harness: self-coverage compares against the measured set, not the declared one", LIVE,
     "    declared = set(PAYLOADS)\n", "    declared = set(per_payload)\n"),
    ("harness: prompt cache not cleared between trials", LIVE,
     "        try:\n            _clear_prompt_cache()\n", "        try:\n            pass\n"),
    ("harness: completions served from the cache exit 0", LIVE,
     "    elif prov_defects:\n        code = 2", "    elif prov_defects:\n        code = 0"),
    ("harness: a cache hit is not counted as a defect", LIVE,
     '        if answering["cache"] == "hit":\n            hits += 1',
     '        if answering["cache"] == "hit":\n            hits += 0'),
    ("harness: provider trace reports every attempt as a cache miss", LIVE,
     '            if hooked:\n                record["cache"] = "miss" if calls else "hit"\n            record["completion_nonblank"]',
     '            if hooked:\n                record["cache"] = "miss"\n            record["completion_nonblank"]'),
    ("harness: endpoint credentials recorded raw", LIVE,
     '    return f"{parts.scheme}://{parts.hostname}{port}"', "    return value"),
    ("harness: provider-name URLs are not scrubbed", LIVE,
     "    return _scrub_urls(name)\n", "    return name\n"),
    ("harness: URL matching in free text is case-sensitive", LIVE,
     r'_URL_IN_TEXT = re.compile(r"(?i)[a-z][a-z0-9+.\-]*://\S+")',
     r'_URL_IN_TEXT = re.compile(r"[a-z][a-z0-9+.\-]*://\S+")'),
    ("harness: the provider's own endpoint is not replaced literally", LIVE,
     '            name = name.replace(raw, _sanitize_endpoint(raw) or "<url>")\n', "            pass\n"),
    ("harness: exception text is not scrubbed", LIVE,
     "        return _scrub_urls(repr(exc))\n", "        return repr(exc)\n"),
    ("harness: an escaping exception is recorded raw", LIVE,
     'return {"request": text, "error": _safe_error(exc)}', 'return {"request": text, "error": repr(exc)}'),
    ("harness: provenance not attached to the run record", LIVE,
     '        "provenance": _provenance_of(real, trace),\n', ""),
    ("harness: stand-in run not labelled as non-real evidence", LIVE,
     " -- NOT real-provider evidence (scripted stand-in model)", " (scripted stand-in model)"),
    # -- coverage policy and trial accounting (independent-review finding, options A + B) --
    ("harness: the strict policy is ignored", LIVE,
     "    elif strict and non_answered:\n        code = 2", "    elif False and non_answered:\n        code = 2"),
    ("harness: strict incompleteness outranks an observed escalation", LIVE,
     "    if total_escalated:\n        code = 1",
     "    if total_escalated and not (strict and non_answered):\n        code = 1"),
    ("harness: blank trials are left out of the attempt accounting", LIVE,
     "    for r in ok:\n        if not real:\n            continue\n        trial_attempts",
     "    for r in ok:\n        if not real or r[\"empty_completion\"]:\n            continue\n        trial_attempts"),
    ("harness: provider errors are counted as blank responses", LIVE,
     "    if any(a.get(\"error\") for a in attempts):\n        return \"provider_error\"",
     "    if any(a.get(\"error\") for a in attempts):\n        return \"blank\""),
    ("harness: the effective coverage policy is not recorded", LIVE,
     '        "coverage_policy": POLICY_STRICT if getattr(args, "require_all_answered", False) else POLICY_DEFAULT,\n', ""),
    ("harness: the strict switch is not recorded in the arguments", LIVE,
     '                 "require_all_answered": bool(getattr(args, "require_all_answered", False))},',
     '                 "require_all_answered": False},'),
    ("harness: blank trials are not mentioned when the default policy passes", LIVE,
     '        if non_answered:\n            print(f"  note: {len(non_answered)}',
     '        if False and non_answered:\n            print(f"  note: {len(non_answered)}'),
    ("harness: a cached blank replay is not reported", LIVE,
     '            if a.get("cache") == "hit" and a.get("completion_nonblank") is False:\n                replay = True',
     '            if False:\n                replay = True'),
]


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_tests() -> int:
    cmd = [sys.executable, "-m", "pytest", *TESTS, "-x", "-q",
           "-p", "no:cacheprovider", "--timeout=90"]
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def main() -> int:
    before = {p: sha(p) for p in (INTENT, PLANNER, LIVE)}
    # Anchor check up front, so a drifted anchor is a harness error (2), not a survivor.
    for name, path, old, _ in MUTANTS:
        n = path.read_text().count(old)
        if n != 1:
            print(f"HARNESS ERROR: anchor for {name!r} matches {n} times in {path}")
            return 2
    if run_tests() != 0:
        print("HARNESS ERROR: baseline test run is not green; refusing to mutate")
        return 2
    survivors, rc = [], 0
    try:
        for i, (name, path, old, new) in enumerate(MUTANTS, 1):
            original = path.read_text()
            try:
                path.write_text(original.replace(old, new, 1))
                caught = run_tests() != 0
            finally:
                path.write_text(original)
            print(f"[{i:2d}/{len(MUTANTS)}] {'CAUGHT  ' if caught else 'SURVIVED'}  {name}")
            if not caught:
                survivors.append(name)
    finally:
        after = {p: sha(p) for p in (INTENT, PLANNER, LIVE)}
        if after != before:
            print("RESTORE ERROR: source files differ from their pre-run bytes!")
            rc = 2
    print(f"\n{len(MUTANTS) - len(survivors)}/{len(MUTANTS)} mutants caught; "
          f"files byte-identical after run: {after == before}")
    if survivors:
        print("SURVIVORS:", *survivors, sep="\n  - ")
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
