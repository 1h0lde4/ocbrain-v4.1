# Export call log (OPERATOR TRANSCRIPTION, not a byte-preserved response)

**Read this first.** The Docs `export` tool delivers its response only into the operator model's context. This environment provides no way to write a tool response to disk programmatically, so no response is preserved byte-for-byte. Everything below is the operator's transcription of fields it could see; any SHA-256 of this file would describe the transcription, never an export. The acquisition time of each Docs call was not recorded by the platform response; all calls occurred during this batch before 2026-11-08T20:17Z. Calls were read-only; no `create blob`, edit or suggestion was used.

| Call | Document (artifact; tab) | Format | Parameters | Observed result |
|---|---|---|---|---|
| E01 | Q4-b brief (`MpmCtTRoaiHKQiQkJNCJLG`; tab `746fc00f-f273`) | markdown | none besides container/file/format | verdict allow; export delivered inline as base64; platform-reported size **71,911 bytes**; revision at export **19**. The delivered payload was NOT written to disk (see below). Original filename, MIME and renderer fields were not preserved. |
| E02 | Q2/Q5 decision pack (`PNJZ381PjSfzMiKeYcaAvg`; tab `0c2d3cb2-caa3`) | markdown | maxBytes=1000 | deny `doc_too_large`, `was: doc_ceiling`; platform-reported size **26,238 bytes**; request id `req_011CgpH3bizw3Dkk4o8w4Csz` |
| E03 | Q4 brief (`HYVpzUxz9PspA4hmUcPLHS`; tab `abbce208-6540`) | markdown | maxBytes=1000 | deny `doc_too_large`; size **54,262 bytes**; `req_011CgpH3zGpP9i19jVq53Hr5` |
| E04 | Q4-b brief | docx | maxBytes=1000 | deny `doc_too_large`; size **36,774 bytes**; `req_011CgpH4BVVxMi2fF4Axoq4c` |
| E05 | Q4-b brief | pdf | maxBytes=1000 | deny `doc_too_large`; size **1,336,013 bytes**; `req_011CgpH4KCbhdZ3u9NKQeZjY` |
| E06 | pack | docx | maxBytes=1000 | deny; size **15,843 bytes**; `req_011CgpH4aZKN3C2XfUXKCXns` |
| E07 | Q4 brief | docx | maxBytes=1000 | deny; size **26,408 bytes**; `req_011CgpH4iCCfy6rLeomraAMD` |
| E08 | pack | pdf | maxBytes=1000 | deny; size **472,480 bytes**; `req_011CgpH4vEkvgMKUrNKDmNSg` |
| E09 | Q4 brief | pdf | maxBytes=1000 | deny; size **805,476 bytes**; `req_011CgpH55UdbVq8wCdoeqwVv` |

E02-E09 used `maxBytes=1000` deliberately, to learn each format's platform-reported size without pulling a payload that could not be preserved. They are size probes, not exports, and are never to be cited as exports. The pack and Q4 brief revisions at the time of those calls are not carried by the refusals; the revisions read earlier in this batch from each document's outline were 28 and 13.

## Why E01's delivered bytes are not in this package
1. The response is available only as text in the operator's context. Preserving it would require the operator to re-emit about 96,000 base64 characters through a tool call, which is transcription by a language model. That is retyping in the sense the assignment prohibits, and no independent copy exists to prove the transcription byte-identical. The only check available would be the byte count, which would not establish identity.
2. The platform's other route (create a blob inside the document so the file lives in the doc's files) writes to the source document and is outside this batch's authorization.
3. The `pictures: "fit"` route that lets a client save a large result as a file applies only when a refusal offers it or a docx note says the file was too large to deliver; no refusal offered it, and it concerns pictures in docx.

Result: no export bytes, no SHA-256 over delivered bytes, no decoded payload. Documents ME-01 to ME-03 are reported accordingly. What would resolve it, without this operator transcribing: an owner download from the claude.ai interface (Word, PDF or Markdown) uploaded unmodified, or a harness that saves tool results as files, or owner authorization of a platform-side write path.
