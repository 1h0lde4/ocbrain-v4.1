"""
scripts/check_packet_ownership.py — K4.2-H2 parallel-packet ownership enforcement.

Four Claude sessions implement D3/D7/D11/D12 concurrently with zero contact
with each other (docs/architecture/h2_packet_ownership.json explains why and
how). Each session is *told*, in its own packet brief, which files it may
touch. This script checks that mechanically, against the branch's actual
diff from `main`, instead of trusting that the telling worked — the same
reasoning that put DRIFT-01..09 in scripts/check_drift.py rather than only
in a docstring.

Run with:
    python3 scripts/check_packet_ownership.py                 # infer packet from current branch
    python3 scripts/check_packet_ownership.py --packet D3      # explicit
    python3 scripts/check_packet_ownership.py --base main      # diff base (default: main)

Exit code: 0 if every changed file is in that packet's `allowed_files`
(or is a *documented* `allowed_files_conditional` entry — those print a
reminder to verify the condition was actually met and recorded in the
packet's status stub, but do not fail the check on their own, since this
script can't read intent). 1 if any changed file is outside the packet's
scope, or touches a file `shared_files_deferred_to_integration` names, or
touches a file explicitly owned by a *different* packet.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "docs" / "architecture" / "h2_packet_ownership.json"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _infer_packet(manifest: dict, branch: str) -> str | None:
    for packet_id, entry in manifest["packets"].items():
        if entry["branch"] == branch:
            return packet_id
    return None


def _changed_files(base: str) -> list[str]:
    """Files changed on HEAD relative to `base`'s merge-base (three-dot diff:
    what this branch actually adds, robust even if `base` has moved on)."""
    result = subprocess.run(
        ["git", "diff", f"{base}...HEAD", "--name-only"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def check_ownership(packet_id: str, base: str = "main") -> tuple[bool, list[str]]:
    """Returns (ok, messages)."""
    manifest = _load_manifest()
    if packet_id not in manifest["packets"]:
        return False, [f"Unknown packet '{packet_id}'. Known packets: {sorted(manifest['packets'])}"]

    entry = manifest["packets"][packet_id]
    allowed = set(entry.get("allowed_files", []))
    conditional = {c["path"]: c["condition"] for c in entry.get("allowed_files_conditional", [])}
    shared = set(manifest.get("shared_files_deferred_to_integration", []))

    other_owned: dict[str, str] = {}
    for other_id, other_entry in manifest["packets"].items():
        if other_id == packet_id:
            continue
        for f in other_entry.get("allowed_files", []):
            other_owned[f] = other_id
        for c in other_entry.get("allowed_files_conditional", []):
            other_owned[c["path"]] = other_id

    changed = _changed_files(base)
    messages: list[str] = []
    ok = True

    if not changed:
        return True, [f"No changes on this branch relative to {base} yet — nothing to check."]

    for f in changed:
        if f in allowed:
            messages.append(f"  OK          {f}")
        elif f in conditional:
            messages.append(
                f"  CONDITIONAL {f}\n"
                f"              -- allowed only if: {conditional[f]}\n"
                f"              -- verify this is recorded, with justification, in {entry['status_stub']}"
            )
        elif f in shared:
            ok = False
            messages.append(
                f"  VIOLATION   {f}\n"
                f"              -- this file is deferred to the sequential integration packet for ALL "
                f"four parallel packets, not just this one. See h2_packet_ownership.json's "
                f"'design_principle'."
            )
        elif f in other_owned:
            ok = False
            messages.append(
                f"  VIOLATION   {f}\n"
                f"              -- this file is owned by packet {other_owned[f]}, not {packet_id}. "
                f"A cross-packet edit here is exactly the collision this manifest exists to prevent."
            )
        else:
            ok = False
            messages.append(
                f"  VIOLATION   {f}\n"
                f"              -- not listed anywhere in {packet_id}'s manifest entry. "
                f"If this file genuinely needs to change, STOP: this is new scope, not a silent addition."
            )

    return ok, messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--packet", default=None, help="Packet ID (D3/D7/D11/D12). Inferred from the current git branch if omitted.")
    parser.add_argument("--base", default="main", help="Diff base branch (default: main)")
    args = parser.parse_args(argv)

    manifest = _load_manifest()
    packet_id = args.packet
    if packet_id is None:
        branch = _current_branch()
        packet_id = _infer_packet(manifest, branch)
        if packet_id is None:
            print(
                f"Could not infer a packet from branch '{branch}'. Pass --packet explicitly, "
                f"or check out one of: {[p['branch'] for p in manifest['packets'].values()]}",
                file=sys.stderr,
            )
            return 2

    ok, messages = check_ownership(packet_id, base=args.base)
    print(f"Ownership check for packet {packet_id} (diff against {args.base}):")
    for m in messages:
        print(m)
    print("PASS" if ok else "FAIL — see VIOLATION lines above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
