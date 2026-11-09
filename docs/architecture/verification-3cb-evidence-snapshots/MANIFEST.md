# Manifest: Verification 3C-B evidence snapshots

Exported 2026-11-09 by the Docs service. "Platform revision" is the Docs service's revision counter at
export time; the content label of a Doc is stated in the Doc itself.

## Source Docs

| Doc | claude.ai Doc id | Tab file id | Content node | Platform revision at export |
| --- | --- | --- | --- | --- |
| Verification 3C-B: Q2 and Q5 decision pack | `b5227c99-327f-483d-b726-3f93d37b8265` | `0c2d3cb2-caa3` | `4a3bfaae-440e` | 28 |
| Verification 3C-B: Q4 queryable non-conclusion brief | `85f80a7c-c273-4902-b8f1-fe009d3a3de5` | `abbce208-6540` | `35e76bcb-57e5` | 13 |
| Verification 3C-B: Q4-b trigger boundary of D6 | `a8a1f900-2bb0-46ad-8ead-e055cf939aa9` | `746fc00f-f273` | `c9bfd0a8-bd8a` | 19 |

The Q4-b Doc's content label at export is "revision 3" (sections 1 to 22 plus a late note), status
REVISION PREPARED, not validated. Earlier revisions 1 and 2 are not archived separately; revision 3 keeps
sections 1 to 16 as written.

## Files

| File | Format | Renderer | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `q2-q5-decision-pack.rev28.md` | Markdown | md-v1 | 26238 | `cff38e1da17d67c0fda0bdcf8c68d2d6a787b31a107b2828991a525aa698f2b2` |
| `q2-q5-decision-pack.rev28.docx` | DOCX | docx-w9 | 15843 | `4ed5c2c6433693fc79f0492a79112ad609d3de5f16099b2343213620c4b721da` |
| `q4-queryable-non-conclusion-brief.rev13.md` | Markdown | md-v1 | 54262 | `cb171f72ef0c0df24379de353095235b4314f110b8f787ceda7fa56777c29641` |
| `q4-queryable-non-conclusion-brief.rev13.docx` | DOCX | docx-w9 | 26408 | `e92ab6f67efcbc9a1920f19bb0c8e495134ca2e55b225e3461a46f37dd5e72b9` |
| `q4b-trigger-boundary-of-d6.rev19.md` | Markdown | md-v1 | 71911 | `886a208246dd3f8319c4cc4fc1d5a46f147eb3e2fd9c8bd76769cabb7445ef4a` |
| `q4b-trigger-boundary-of-d6.rev19.docx` | DOCX | docx-w9 | 36774 | `3d849bd8c0e94a885d6179b25fc5f89e6b1f672cb60e3dbc2fe3476175dfaed1` |

## Method

1. The Docs service created each export inside its own Doc and reported its size and SHA-256.
2. The export was copied into the working container by the Artifact tool, without passing through the
   conversation, so nothing was retyped.
3. The SHA-256 and byte size of every copy were recomputed and matched the service's values; each DOCX
   passed a zip integrity test; the Markdown files are valid UTF-8 and contain no line-ending bytes
   other than LF.
4. A pattern scan for credentials and e-mail addresses over all six files found nothing.
5. The files were committed unchanged, with line-ending normalization disabled.

## Limits

- The three Docs now also hold the service-side copies of these exports as attached files. No Doc content
  or revision counter changed when they were created.
- This manifest cannot contain its own hash. `SHA256SUMS` covers the six snapshot files only.
- A snapshot proves what the Doc said at that revision. It does not prove the Doc's statements are true.
