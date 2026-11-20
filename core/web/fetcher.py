import asyncio
import logging
import aiohttp
from typing import Optional
from urllib.parse import urlparse

from core.web.egress import PublicEgressError, PublicWebClient, ResponseTooLargeError

logger = logging.getLogger("ocbrain.web.fetcher")

async def fetch_html(url: str, timeout_sec: int = 10, max_retries: int = 3) -> Optional[str]:
    """
    Fetch HTML content from a URL with retry and timeout handling.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with PublicWebClient() as client:
            for attempt in range(1, max_retries + 1):
                try:
                    response = await client.get(
                        url,
                        headers=headers,
                        timeout=timeout_sec,
                    )
                    if response.status == 200:
                        return response.text
                    logger.warning(
                        "[Fetcher] Attempt %s failed for %s with status %s",
                        attempt,
                        _hostname_for_log(url),
                        response.status,
                    )
                except (PublicEgressError, ResponseTooLargeError) as exc:
                    logger.warning(
                        "[Fetcher] Refused or oversized response from %s (%s)",
                        _hostname_for_log(url),
                        type(exc).__name__,
                    )
                    return None
                except asyncio.TimeoutError:
                    logger.warning(
                        "[Fetcher] Attempt %s timed out for %s",
                        attempt,
                        _hostname_for_log(url),
                    )
                except aiohttp.ClientError as exc:
                    logger.warning(
                        "[Fetcher] Attempt %s client error for %s (%s)",
                        attempt,
                        _hostname_for_log(url),
                        type(exc).__name__,
                    )

                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
    except asyncio.CancelledError:
        raise

    logger.error(
        "[Fetcher] All %s attempts failed for %s",
        max_retries,
        _hostname_for_log(url),
    )
    return None


def _hostname_for_log(url: str) -> str:
    try:
        return urlparse(url).hostname or "invalid"
    except (TypeError, ValueError):
        return "invalid"
