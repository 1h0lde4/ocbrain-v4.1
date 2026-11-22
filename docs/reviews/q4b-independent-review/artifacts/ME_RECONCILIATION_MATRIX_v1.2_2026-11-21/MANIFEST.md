# Q4B reconciliation matrix v1.2: point-in-time snapshot (2026-11-21)

**Status: record only.** The review disposition stays OPEN / NO PASS. This snapshot is a working draft, not an acceptance.
It adds new files only. Docs-only; no code, test, probe or workflow action was performed.

## What this is

- Source: a Claude Doc created in the review chat, "Q4B Independent Review: Decision & Evidence Reconciliation Matrix"
  (the Doc's own title still says v1.1; its text is v1.2). Link: https://claude.ai/artifact/KQ6hriHBnmEkHg8VVY4xQC
  (artifact slug `94fe1e39-ed0a-4b0a-9a24-6b05340c8c65`). Platform revision at export: 21.
- The Doc remains the editable source and may advance past revision 21. This directory is the repository copy of revision 21.
- v1.2 revises the owner's v1.0 draft (pasted in the chat, 2026-11-20) through v1.1, and adopts four findings of an external
  review of v1.1 (also pasted in the chat), each verified against the repository before adoption.

## How the files were produced (no retyping)

1. The Docs service created export copies of the tab at revision 21 and reported SHA-256 and size for each (below).
2. The files were copied from the Doc's asset store into the sandbox by the Artifact tool's asset read, not through the conversation.
3. SHA-256 and size were recomputed on the copied bytes and equal the service-reported values.
4. The files were then committed unchanged under the names below (the service's own names contain spaces and an ampersand).

| Repository file | Service asset id | Bytes | SHA-256 (service-reported and recomputed) |
|-----------------|------------------|-------|---------------------------------------------|
| `q4b-reconciliation-matrix-v1.2.rev21.md` | `02a709cccf898e8cbef34dd371696f2f` | 38214 | `92b10d5c6ded017b95c3d3d5bfcfddae7e5bccff3122c17c85fce2829917726b` |
| `q4b-reconciliation-matrix-v1.2.rev21.docx` | `469323f5a0425bc0d75d375c40294551` | 22598 | `3ed9c57451536b30656f664ce7bfc02145baea7763e8fcc1c915f2a4e72c5003` |

Export copies were attached to the Doc itself (two attached files at revision 21); the Doc's text was not changed by the export.

## Limits

- Provenance of the service-side export is what the Docs service reports; it was not independently corroborated beyond the hash and size match above.
- The matrix cites two inputs that exist only in the chat and are NOT stored here: the owner's v1.0 draft and the external review of v1.1
  (evidence item E23 rests on the latter). If they should be preserved, the owner must supply them as files; they will be hashed on receipt.
- Every repository-state statement in the matrix is point-in-time (checked 2026-11-21; `main` was `ef1351f`). Re-check before relying on it.
- A credential-pattern scan of the markdown flags the literal word `x-access-token` in evidence row E16, which describes the scan method. It is not a secret; no token-shaped string is present (checked 2026-11-21, also inside the docx).
- `SHA256SUMS.txt` covers the three other files in this directory. Check with `cd <this directory> && sha256sum -c SHA256SUMS.txt`.
