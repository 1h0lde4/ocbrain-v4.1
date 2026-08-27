import httpx
import os

_LLM_READ_TIMEOUT = float(os.getenv("OCBRAIN_LLM_TIMEOUT_SECONDS", "600"))

# Global AsyncClient for connection pooling and resource management
client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, read=_LLM_READ_TIMEOUT),
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
    headers={"User-Agent": "OCBrain/3.0.1 (Local AI Assistant)"}
)

async def close_client():
    await client.aclose()
