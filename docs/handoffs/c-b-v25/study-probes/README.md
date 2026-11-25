# Cancellation-study probes (NOT repository code)

Read-only experiments behind `docs/studies/OCBRAIN_CANCELLATION_FINAL_GAP_STUDY_OCT2026.md` (probes P1-P15, C1-C5, reason probe).
They run against a THROWAWAY COPY of the repository (DEBT-012: test runs rewrite tracked config files), never the checkout.
Set `OCROOT=<copy path>` (default `/tmp/probe/repo`) and `HOME=<temp dir>`. Required packages: aiofiles aiohttp beautifulsoup4 click datasketch fastapi
feedparser httpx pydantic pytest pytest-asyncio PyYAML requests rich scipy tomli tomli-w "uvicorn[standard]" keyboard (ChromaDB and sentence-transformers are not needed).
Raw outputs: `results_py311_ab.txt`, `results_py311_c.txt` (at ed3d141) and `results_py311_at_2491ae4.txt` (at 2491ae4, includes C5).
`probes_c.py` assumes today's `X-OCBrain-Local` CSRF-header gate; PR #94 (deferred) would add default-on bearer-token auth.
NOTE: the study text says the probes were "delivered outside the repository, not committed"; they are preserved here by the handoff commit.
