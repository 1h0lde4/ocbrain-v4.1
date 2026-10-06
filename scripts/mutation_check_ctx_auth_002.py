#!/usr/bin/env python3
"""Mutation check for the CTX-AUTH-002 replacement (core/cognitive/intent.py,
core/cognitive/planner.py).

Each mutant re-introduces one specific regression by an EXACT-string
replacement (asserted to match exactly once), runs the four test files that
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
TESTS = [
    "tests/core/cognitive/test_intent_security.py",
    "tests/core/cognitive/test_intent.py",
    "tests/core/cognitive/test_k42_completion.py",
    "tests/core/cognitive/test_planner.py",
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
]


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_tests() -> int:
    cmd = [sys.executable, "-m", "pytest", *TESTS, "-x", "-q",
           "-p", "no:cacheprovider", "--timeout=90"]
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def main() -> int:
    before = {p: sha(p) for p in (INTENT, PLANNER)}
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
        after = {p: sha(p) for p in (INTENT, PLANNER)}
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
