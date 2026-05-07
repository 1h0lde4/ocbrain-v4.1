import httpx

# Global AsyncClient for connection pooling and resource management
client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, read=60.0),
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
    headers={"User-Agent": "OCBrain/3.0.1 (Local AI Assistant)"}
)

async def close_client():
    await client.aclose()
