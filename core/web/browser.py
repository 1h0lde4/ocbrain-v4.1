"""Read-only Playwright page rendering through the public egress client."""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from core.web.egress import (
    PublicWebClient,
    validate_public_url,
)

logger = logging.getLogger("ocbrain.web.browser")

_ALLOWED_RESOURCE_TYPES = {"document", "script", "stylesheet", "xhr", "fetch"}
_MAX_BROWSER_REQUESTS = 64
_MASKED_PATHS = (
    "/home",
    "/root",
    "/tmp",
    "/run",
    "/var",
    "/mnt",
    "/media",
    "/workspaces",
    "/workspace",
    "/opt",
    "/srv",
)
_STRIPPED_RESPONSE_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "transfer-encoding",
}


def _allows_browser_request(
    method: str, resource_type: str, request_number: int = 1
) -> bool:
    return (
        method == "GET"
        and resource_type in _ALLOWED_RESOURCE_TYPES
        and request_number <= _MAX_BROWSER_REQUESTS
    )


@dataclass(frozen=True)
class BrowserPage:
    url: str
    title: str
    text: str


class BrowserSandboxUnavailableError(RuntimeError):
    """Raised when the required OS-level browser sandbox is unavailable."""


async def _read_bounded_page_text(page, max_text_chars: int, timeout_seconds: float) -> str:
    return await asyncio.wait_for(
        page.locator("body").evaluate(
            "(body, limit) => body.innerText.slice(0, limit)",
            max_text_chars,
        ),
        timeout=timeout_seconds,
    )


async def _read_bounded_page_title(
    page, max_title_chars: int, timeout_seconds: float
) -> str:
    return await asyncio.wait_for(
        page.evaluate(
            "(limit) => document.title.slice(0, limit)",
            max_title_chars,
        ),
        timeout=timeout_seconds,
    )


async def render_page(
    url: str,
    client: PublicWebClient,
    *,
    timeout_seconds: float = 15.0,
    max_text_chars: int = 12_000,
    max_title_chars: int = 512,
) -> BrowserPage:
    """Render a public page without exposing click, form, or script APIs."""
    validated_url = validate_public_url(url)
    from playwright.async_api import async_playwright

    if not sys.platform.startswith("linux"):
        raise BrowserSandboxUnavailableError(
            "Read-only browser rendering requires Linux Bubblewrap isolation"
        )
    bubblewrap = shutil.which("bwrap")
    if bubblewrap is None:
        raise BrowserSandboxUnavailableError(
            "Read-only browser rendering requires Bubblewrap (bwrap)"
        )

    async with async_playwright() as playwright:
        chromium, chromium_root = _find_headless_chromium(
            playwright.chromium.executable_path
        )
        with tempfile.TemporaryDirectory(prefix="ocbrain-browser-sandbox-") as temp_dir:
            wrapper = Path(temp_dir) / "chromium-sandbox"
            wrapper.write_text(_sandbox_wrapper_source(sys.executable))
            wrapper.chmod(0o700)
            browser_env = {
                "PATH": "/usr/bin:/bin",
                "HOME": "/tmp",
                "TMPDIR": "/tmp",
                "LANG": "C.UTF-8",
                "OCBRAIN_BWRAP": bubblewrap,
                "OCBRAIN_CHROMIUM": str(chromium),
                "OCBRAIN_CHROMIUM_ROOT": str(chromium_root),
            }
            browser = await playwright.chromium.launch(
                executable_path=str(wrapper),
                env=browser_env,
                headless=True,
                chromium_sandbox=True,
                args=[
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-default-apps",
                    "--disable-extensions",
                    "--disable-sync",
                    "--no-first-run",
                ],
            )
            try:
                context = await browser.new_context(
                    accept_downloads=False,
                    service_workers="block",
                )
                request_count = 0

                async def fetch_request(route) -> None:
                    nonlocal request_count
                    request_count += 1
                    request = route.request
                    if not _allows_browser_request(
                        request.method, request.resource_type, request_count
                    ):
                        await route.abort()
                        return

                    try:
                        response = await client.get(
                            request.url,
                            headers=request.headers,
                            timeout=timeout_seconds,
                            follow_redirects=False,
                        )
                        response_headers = {
                            key: value
                            for key, value in response.headers.items()
                            if key.lower() not in _STRIPPED_RESPONSE_HEADERS
                        }
                        location = _header_value(response_headers, "location")
                        if location and 300 <= response.status < 400:
                            validate_public_url(urljoin(response.url, location))
                        if (
                            (_header_value(response_headers, "content-disposition") or "")
                            .lower()
                            .strip()
                            .startswith("attachment")
                        ):
                            await route.abort()
                            return
                        await route.fulfill(
                            status=response.status,
                            headers=response_headers,
                            body=response.body,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Blocked browser request to %s (%s)",
                            urlparse(request.url).hostname or "invalid",
                            type(exc).__name__,
                        )
                        await route.abort()

                async def block_websocket(websocket_route) -> None:
                    nonlocal request_count
                    request_count += 1
                    await websocket_route.close()

                await context.route("**/*", fetch_request)
                await context.route_web_socket("**/*", block_websocket)
                page = await context.new_page()
                await page.goto(
                    str(validated_url),
                    wait_until="domcontentloaded",
                    timeout=int(timeout_seconds * 1000),
                )
                text = await _read_bounded_page_text(
                    page, max_text_chars, timeout_seconds
                )
                title = await _read_bounded_page_title(
                    page, max_title_chars, timeout_seconds
                )
                return BrowserPage(
                    url=page.url,
                    title=title,
                    text=text[:max_text_chars],
                )
            finally:
                await browser.close()


def _find_headless_chromium(executable_path: str) -> tuple[Path, Path]:
    chromium_path = Path(executable_path).resolve()
    chromium_install = next(
        (parent for parent in chromium_path.parents if parent.name.startswith("chromium-")),
        None,
    )
    if chromium_install is None:
        raise BrowserSandboxUnavailableError(
            "Could not locate Playwright's Chromium installation"
        )

    revision = chromium_install.name.removeprefix("chromium-")
    headless_install = chromium_install.parent / f"chromium_headless_shell-{revision}"
    candidates = sorted(
        headless_install.glob("chrome-headless-shell-*/chrome-headless-shell")
    )
    if not candidates:
        raise BrowserSandboxUnavailableError(
            "Playwright Chromium headless shell is missing; install it with "
            "`python -m playwright install --only-shell chromium`"
        )
    executable = candidates[0].resolve()
    return executable, executable.parent


def _sandbox_wrapper_source(python_executable: str) -> str:
    return f"""#!{python_executable}
import os
import sys
from pathlib import Path

bwrap = os.environ["OCBRAIN_BWRAP"]
chromium = Path(os.environ["OCBRAIN_CHROMIUM"])
chromium_root = Path(os.environ["OCBRAIN_CHROMIUM_ROOT"])
chromium_fd = os.open(chromium_root, os.O_RDONLY | os.O_DIRECTORY)
os.set_inheritable(chromium_fd, True)

args = [
    bwrap,
    "--unshare-net",
    "--unshare-pid",
    "--die-with-parent",
    "--new-session",
    "--ro-bind", "/", "/",
]
for path in {_MASKED_PATHS!r}:
    if Path(path).is_dir():
        args.extend(["--tmpfs", path])

args.extend(["--dev", "/dev", "--proc", "/proc"])

masked_root = next(
    (Path(path) for path in {_MASKED_PATHS!r}
     if chromium_root == Path(path) or Path(path) in chromium_root.parents),
    None,
)
if masked_root is not None:
    target = masked_root
    for part in chromium_root.relative_to(masked_root).parts:
        target /= part
        args.extend(["--dir", str(target)])
    args.extend(["--ro-bind-fd", str(chromium_fd), str(chromium_root)])

profile = next(
    (arg.split("=", 1)[1] for arg in sys.argv[1:]
     if arg.startswith("--user-data-dir=")),
    None,
)
if profile and Path(profile).is_relative_to("/tmp"):
    profile_path = Path(profile)
    target = Path("/tmp")
    for part in profile_path.relative_to("/tmp").parts:
        target /= part
        args.extend(["--dir", str(target)])

args.extend(["--chdir", "/tmp", "--", str(chromium), *sys.argv[1:]])
os.execvpe(bwrap, args, os.environ)
"""


def _header_value(headers: dict[str, str], name: str) -> str | None:
    normalized_name = name.lower()
    return next(
        (value for key, value in headers.items() if key.lower() == normalized_name),
        None,
    )
