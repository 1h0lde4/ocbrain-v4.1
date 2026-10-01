#!/usr/bin/env python3
"""Live check for ADR-KERNEL-07's [PENDING] risk: do the draft plan steps shown
next to a clarification question add useful context, or introduce speculation?

The concern (ADR-KERNEL-07 §10.4): for a request the detector says lacks a content
anchor, the model still decomposes it into steps, and those steps are then shown to
the user. If a step contains content the user never supplied, the response says
"content is missing" while displaying invented content.

WHAT THIS MEASURES (one mechanical thing, deliberately not a quality judgment):
for each request the detector would escalate, it runs the same two model calls the
pipeline makes -- interpretation (interpret_request) and the planner's decomposition
prompt -- and reports, per step, the content-bearing words the step introduces that
appear in NEITHER the request NOR the interpretation ("novel content tokens"), using
the detector's own lexicon. Labels:
    redundant    single step that just restates the interpretation (adds nothing)
    generic      adds no novel content words (harmless, but may add little)
    speculative  introduces >= 1 novel content word (candidate speculation)
This is a proxy: a word-level screen, not a semantic judgment. Read the printed
steps yourself. The script recommends nothing; the disposition is Moncif's.

USAGE
    python scripts/live_check_draft_plan.py                 # LIVE: uses your configured providers
    python scripts/live_check_draft_plan.py --json out.json # also write raw results
    python scripts/live_check_draft_plan.py --offline single|generic|speculative
        # OFFLINE: synthetic canned model output to self-test THIS SCRIPT. It is NOT
        # evidence about any real model and is labeled as such in its output.

Live mode makes real model calls (2 per escalating request; ~11 requests). It does
not touch the capability registry, memory, or the real event log. Exit code 2 means
every live call degraded (provider unavailable) -- the run is then NOT evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.cognitive import content_anchor as ca  # noqa: E402

# Requests the detector should escalate (form-only), plus long-form ones chosen because
# they tempt a model to split into multiple, more speculative steps.
SAMPLE: List[str] = [
    "write a 1000 words story",
    "write a story",
    "write a poem",
    "write me an essay",
    "tell me a joke",
    "write a long story please",
    "Write a 500 word story.",
    "compose a song",
    # adversarial: long-form invites multi-step decomposition
    "write a novel",
    "write a 5000 word story",
    "write a 10000 word essay",
]

_TOKEN = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower())


def content_tokens(text: str) -> List[str]:
    """Content-bearing tokens by the detector's own definition."""
    return [
        t for t in _tokens(text)
        if t not in ca._FILLER and t not in ca._GENERATIVE_VERBS
        and t not in ca._ARTIFACTS and not ca._NUMERIC.fullmatch(t)
    ]


# Authoring-PROCESS vocabulary: words that describe how work is done, not what the
# piece is about. Without this list every multi-step plan ("draft", "revise",
# "polish") is flagged, which a self-test of this script caught. The list is a
# judgment call and a first-pass proxy; it is deliberately short and explicit, and
# the printed steps remain the primary evidence. Subject/genre/character/setting/
# tone words are NOT here, so invented premise content is still flagged.
_PROCESS_WORDS = frozenset("""
draft drafting draftable revise revising revision edit editing review reviewing
proofread proofreading polish polishing refine refining outline outlining
brainstorm brainstorming plan planning structure structuring finalize finalise
final finish finishing complete completing deliver delivering iterate iterating
version versions piece text content output result results section sections part
parts chapter chapters step steps first next then initial full whole entire
check checking ensure ensuring deliverable submit submitting present presenting
""".split())


def novel_content_tokens(step: str, sources: Sequence[str]) -> List[str]:
    """Content tokens in `step` present in none of `sources` (all tokens, unfiltered),
    excluding generic authoring-process words."""
    seen = {t for s in sources for t in _tokens(s)}
    return sorted({t for t in content_tokens(step)
                   if t not in seen and t not in _PROCESS_WORDS})


def classify_step(step: str, request: str, interpretation: str) -> Dict[str, Any]:
    novel = novel_content_tokens(step, [request, interpretation])
    restates = sorted(_tokens(step)) == sorted(_tokens(interpretation)) and bool(step.strip())
    label = "redundant" if restates and not novel else ("speculative" if novel else "generic")
    return {"step": step, "label": label, "novel_content_tokens": novel}


def classify_plan(steps: Sequence[str], request: str, interpretation: str) -> str:
    per = [classify_step(s, request, interpretation) for s in steps]
    if any(p["label"] == "speculative" for p in per):
        return "speculative"
    if len(per) == 1 and per[0]["label"] == "redundant":
        return "redundant"
    return "generic"


async def _live_pair(request: str) -> Dict[str, Any]:
    """The same two model calls the pipeline makes, without registry/memory/events."""
    import core.cognitive.intent as intent_mod
    import core.cognitive.planner as planner_mod

    class _NullStream:
        async def append(self, *a: Any, **k: Any) -> None:
            return None

    degraded: List[str] = []
    interpretation = ""
    try:
        goals = await intent_mod.interpret_request(request, event_stream=_NullStream())
        interpretation = str((goals[0].structured_form or {}).get("description") or "")
    except Exception as exc:  # provider down, etc.
        degraded.append(f"interpret: {type(exc).__name__}")
    interpretation = interpretation or request

    steps: List[str] = []
    try:
        prompt = planner_mod._DECOMPOSITION_PROMPT_TEMPLATE.format(description=interpretation)
        completion = await planner_mod.generate_with_fallback(
            planner_mod.resolve_provider("planner_decompose"), prompt)
        steps = planner_mod._parse_decomposition(completion)
    except Exception as exc:
        degraded.append(f"decompose: {type(exc).__name__}")
    if not steps:                       # mirror plan()'s degrade path
        degraded.append("decompose: empty -> single-step fallback")
        steps = [interpretation]
    return {"interpretation": interpretation, "steps": steps, "degraded": degraded}


_OFFLINE = {   # SYNTHETIC canned decompositions, to self-test this script only
    "single": lambda interp: [interp],
    "generic": lambda interp: ["Draft the piece", "Revise and polish the draft"],
    "speculative": lambda interp: [
        "Invent a detective protagonist and a rain-soaked city setting",
        "Write the story with a betrayal twist",
    ],
}


async def _offline_pair(request: str, profile: str) -> Dict[str, Any]:
    interp = request[:1].upper() + request[1:].rstrip(".")
    return {"interpretation": interp, "steps": _OFFLINE[profile](interp),
            "degraded": []}


async def run(requests: Sequence[str], offline: str = "") -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for req in requests:
        assessment = ca.detect_creative_content_anchors(req)
        row: Dict[str, Any] = {"request": req,
                               "would_escalate": ca.anchor_missing(assessment)}
        if row["would_escalate"]:
            pair = await (_offline_pair(req, offline) if offline else _live_pair(req))
            row.update(pair)
            row["steps_detail"] = [classify_step(s, req, pair["interpretation"])
                                   for s in pair["steps"]]
            row["plan_label"] = classify_plan(pair["steps"], req, pair["interpretation"])
            row["shown_to_user"] = ca.build_clarification_response(
                assessment, interpretation=pair["interpretation"],
                plan_steps=pair["steps"])
        rows.append(row)
    esc = [r for r in rows if r["would_escalate"]]
    counts: Dict[str, int] = {}
    for r in esc:
        counts[r["plan_label"]] = counts.get(r["plan_label"], 0) + 1
    live_all_degraded = bool(esc) and not offline and all(r["degraded"] for r in esc)
    return {"mode": f"OFFLINE-SYNTHETIC:{offline}" if offline else "LIVE",
            "rows": rows, "escalated": len(esc), "label_counts": counts,
            "not_evidence": bool(offline) or live_all_degraded}


def render(result: Dict[str, Any]) -> str:
    out = [f"MODE: {result['mode']}"]
    if result["not_evidence"]:
        out.append("*** NOT EVIDENCE: "
                   + ("synthetic offline output for self-testing this script."
                      if result["mode"].startswith("OFFLINE")
                      else "every live call degraded (provider unavailable).") + " ***")
    for r in result["rows"]:
        out.append(f"\n> {r['request']!r}  would_escalate={r['would_escalate']}")
        if not r["would_escalate"]:
            continue
        out.append(f"  interpretation: {r['interpretation']!r}")
        for d in r["steps_detail"]:
            nov = f"  novel={d['novel_content_tokens']}" if d["novel_content_tokens"] else ""
            out.append(f"  [{d['label']:11}] {d['step']}{nov}")
        if r["degraded"]:
            out.append(f"  degraded: {r['degraded']}")
        out.append(f"  => plan label: {r['plan_label']}")
    out.append(f"\nSUMMARY: {result['escalated']} escalating requests; "
               f"plan labels {result['label_counts'] or '{}'}")
    out.append("Read the steps above yourself; the label is a word-level proxy. "
               "Disposition (keep / drop plan_steps) is Moncif's.")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--offline", choices=sorted(_OFFLINE), default="",
                    help="synthetic self-test mode (NOT evidence)")
    ap.add_argument("--json", metavar="PATH", help="write raw results as JSON")
    ap.add_argument("--prompts", metavar="FILE", help="one request per line (default: built-in sample)")
    args = ap.parse_args(argv)
    reqs = ([l.strip() for l in Path(args.prompts).read_text().splitlines() if l.strip()]
            if args.prompts else SAMPLE)
    result = asyncio.run(run(reqs, offline=args.offline))
    print(render(result))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return 2 if (result["not_evidence"] and not args.offline) else 0


if __name__ == "__main__":
    raise SystemExit(main())
