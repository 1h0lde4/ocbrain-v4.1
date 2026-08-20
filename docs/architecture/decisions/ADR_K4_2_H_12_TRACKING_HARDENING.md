# ADR-K4.2-H-12: Tracking & Documentation Hardening — `IMPLEMENTATION_TRACKER.md` Disposition

**Status:** DRAFT (the disposition below is a decision; the scope-extension question
inside it is explicitly deferred — see §2)
**Date:** August 19, 2026
**Author:** K4.2-H2-D12 packet (Tracking & Documentation Hardening)
**Scope:** `docs/architecture/IMPLEMENTATION_TRACKER.md`; H2 parallel-packet tracking model

---

## 1. Context

This packet's brief (`docs/architecture/h2_packets/D12_TRACKING_HARDENING.md`, Job 1)
states that `IMPLEMENTATION_TRACKER.md` "is referenced by name in `PROJECT_INSTRUCTIONS.md`,
the original H1 implementation packet, and this task's own instructions — but it does not
exist in the repository," citing that "both the H1 completion report and an independent
freeze review already noticed this." That premise traces to two specific prior documents:

- `docs/Bugs Hunt & fix reports/K4_2_H1_COMPLETION_REPORT.md` (line 104): "does not exist
  in this repository (only `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`/
  `KNOWN_ISSUES.md`/`PROJECT_INDEX.md` do)."
- `docs/Bugs Hunt & fix reports/K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md` (line 245):
  "note: this file does not currently exist in the repository. Both the H1 completion
  report and this session's own repo search confirm it."

This packet's Phase 0 reality check (a direct `git clone` of the repository, per this
project's standing "the repository is ground truth" discipline) found this premise to be
**false**. `docs/architecture/IMPLEMENTATION_TRACKER.md` exists: 31,275 bytes, git history
from an initial upload through commit `a6b012e` ("Packet 09 — Integration: Full Cognitive
Pipeline", 2026-08-01). It is not a dormant artifact — `IMPLEMENTATION_ROADMAP.md` (line 99)
names it directly as *"the authoritative packet-level tracker,"* distinct from
`IMPLEMENTATION_ROADMAP.md`'s own purpose, and it is cited as the source of per-packet
status by the completion reports for Packets 02, 04, 06, 07, 08, and 09.

The most likely root cause: both prior sessions' searches did not use a direct repository
clone. This project's own known tooling limitation (`GitHub directory fetch quirk` —
automated fetching of GitHub directory-listing paths fails for subdirectory contents
without either API-with-auth calls or direct paste) would produce exactly this false
negative for a file that exists one level below the repository root rather than at it —
consistent with `h2_packet_ownership.json`'s own D12 manifest entry listing the file as
bare `IMPLEMENTATION_TRACKER.md`, with no `docs/architecture/` prefix, suggesting whoever
wrote that entry was also working from the "does not exist, would need creating at some
path" premise rather than from a located file.

## 2. Decision

Given the file already exists and is already the acknowledged authority for exactly the
kind of per-packet status this Job asks about, neither option this packet's brief offers
describes reality accurately:

- **Not (a) "create it":** creating a new file (at the manifest's implied root path or
  anywhere else) would produce two same-purpose, similarly-named artifacts, one of which
  is already the one every other document in this repository points to. That is a
  duplication risk, not a resolution.
- **Not (b) "formally decline, because `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`
  already serve this purpose":** this would misstate the actual, already-established file
  relationship. `IMPLEMENTATION_ROADMAP.md` itself defers to `IMPLEMENTATION_TRACKER.md`
  as the authoritative source for the thing Job 1 is asking about — declining on the
  grounds that the two higher-level files already cover it would contradict the repo's
  own existing cross-reference.

**What this packet decides, within its own narrow, parallel-safe mandate:**

1. `docs/architecture/IMPLEMENTATION_TRACKER.md` is recognized as the existing,
   already-authoritative packet-level tracker for the K4.2 Packet 01–09 ("Cognitive
   Front-End") implementation campaign it currently documents. This packet does not
   modify its content — that file is not in this packet's `allowed_files`, and any
   edit to it is itself the open question in point 2, not a foregone conclusion this
   packet can settle unilaterally.
2. **Explicitly deferred, not decided here:** whether `IMPLEMENTATION_TRACKER.md`'s
   coverage should be *extended* to also track the H2 sub-packet family (D3/D7/D10/D11/
   D12), or whether H2 tracking remains exclusively in `docs/architecture/h2_status/` plus
   the eventual `ADR_INDEX.md`/`CURRENT_STATE.md` consolidation the sequential integration
   packet performs. This is a real architectural/process decision with consequences for
   packets other than D12, which is precisely the kind of cross-packet judgment the
   zero-contact parallel design (`h2_packet_ownership.json`) reserves for the sequential
   integration step, not for any one of the four parallel sessions. Silently choosing
   either direction here would repeat, at one remove, the exact mistake this packet's
   brief already warns against for D3/D7/D11's completion status: attesting to something
   a zero-contact session cannot fully evaluate alone.
3. Both prior sessions' "does not exist" conclusion is recorded here as independently
   verified incorrect, so a future reader does not re-inherit it as settled fact.

## 3. Consequences

- No new duplicate tracker file is created by this packet.
- The sequential integration packet inherits an explicit, evidenced question (§2, point 2)
  rather than a false "the file doesn't exist" premise or a silently-made scope call.
- `KNOWN_ISSUES.md` currently has no entry for this discrepancy (checked directly — zero
  matches for "tracker", case-insensitive). `KNOWN_ISSUES.md` is outside this packet's
  `allowed_files` (it is in `shared_files_deferred_to_integration`), so this packet cannot
  add one; recorded here and in `docs/architecture/h2_status/D12_STATUS.md` as something
  the integration step should add a DEBT entry for.
- This ADR itself is the durable record Job 1 requires ("silence is not" an acceptable
  outcome) — the decision made is narrower than a simple create/decline binary, but it is
  not silence.

## 4. Alternatives considered

- **Create a new root-level `IMPLEMENTATION_TRACKER.md`**, matching the ownership
  manifest's bare filename literally: rejected — see §2, point 1.
- **Formally decline, citing existing-file coverage**: rejected — see §2, point 1; would
  misstate the repository's own existing documentation relationships.
- **Silently extend the existing tracker to add an H2 section**, treating that as a
  reasonable reading of the brief's "create it, scoped narrowly" option: rejected — this
  packet cannot honestly attest to D3/D7/D11's status (the same reasoning
  `h2_packet_ownership.json`'s own D12 note already applies to `CURRENT_STATE.md`/
  `IMPLEMENTATION_ROADMAP.md`), and unilaterally deciding the *scope* question in §2 point
  2 exceeds a single parallel packet's mandate even where the mechanical edit would be easy.

