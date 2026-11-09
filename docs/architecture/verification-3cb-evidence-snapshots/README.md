# Verification 3C-B evidence snapshots

Revision-pinned exports of the three analysis Docs that the 3C-B work rests on. They were kept only in
claude.ai until now, which left the Verification handoff marked "transfer incomplete". This directory
preserves them next to the code and the other Verification documents they assess.

## What these files are

| Snapshot | Role |
| --- | --- |
| `q2-q5-decision-pack.rev28` | Candidate decisions and dependencies for Q2 and Q5 |
| `q4-queryable-non-conclusion-brief.rev13` | Q4 candidates and the decision ledger (section 10.3) |
| `q4b-trigger-boundary-of-d6.rev19` | Q4-b: the trigger boundary of D6, with the runtime audit (sections 11 to 22) |

Each exists as Markdown (searchable) and DOCX (preserved layout). `MANIFEST.md` records the Doc id,
revision, export format, size and SHA-256 of every file. `SHA256SUMS` lets anyone re-check them:

    cd docs/architecture/verification-3cb-evidence-snapshots && sha256sum -c SHA256SUMS

## What these files are not

- They are not decisions. The Docs are analysis only; their own status lines say nothing in them is
  accepted. Archiving them changes none of that.
- They are not the working copies. The Docs in claude.ai stay editable; a later revision needs a new
  snapshot with its own revision in the file name. These files are never updated in place.
- The Q4-b snapshot is not validated. As its section 22 states, it is prepared (revision 3) and has had no
  independent review.
- They do not change code, tests, schema, contracts or ADRs.

## Provenance

The files are exports made by the Docs service itself (Markdown renderer `md-v1`, DOCX renderer
`docx-w9`) on 2026-11-09 and copied unchanged into this directory. The SHA-256 and size of each were
reported by the service when it created the export and were recomputed on the copies here; they match.
No file was retyped or edited. The service kept date and mention chips as plain text. Whether comments or
revision history are included in the exports was not checked.

`.gitattributes` in this directory switches off line-ending normalization so the committed bytes stay
identical to the exports, whatever the repository default says.

The Markdown byline names the author handle, and the repository is public.
