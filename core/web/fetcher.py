import asyncio
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger("ocbrain.web.fetcher")

async def fetch_html(url: str, timeout_sec: int = 10, max_retries: int = 3) -> Optional[str]:
    """
    Fetch HTML content from a URL with retry and timeout handling.
    """
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    
    # Use a dummy headers dict to impersonate a standard browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.warning(f"[Fetcher] Attempt {attempt} failed for {url} with status {response.status}")
        except asyncio.TimeoutError:
            logger.warning(f"[Fetcher] Attempt {attempt} timed out for {url}")
        except aiohttp.ClientError as e:
            logger.warning(f"[Fetcher] Attempt {attempt} client error for {url}: {e}")
        except Exception as e:
            logger.error(f"[Fetcher] Attempt {attempt} unexpected error for {url}: {e}")
            
        if attempt < max_retries:
            await asyncio.sleep(2 ** attempt) # Exponential backoff
            
    logger.error(f"[Fetcher] All {max_retries} attempts failed for {url}")
    return None
