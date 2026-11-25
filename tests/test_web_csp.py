"""
tests/test_web_csp.py -- the shipped pages run under ``script-src 'self'`` (DEBT-025 follow-up).

Until now the policy carried ``'unsafe-inline'`` for script because the pages used inline
``<script>`` blocks and ``onclick=`` attributes. The script now lives in ``interface/web/*.js`` and
events are wired by ``addEventListener`` and ``data-action``. With ``'unsafe-inline'`` gone a blocked
inline handler fails *silently*, so besides the policy these tests pin the three ways the pages
could slip back or break unnoticed:

* the policy itself (no ``'unsafe-inline'`` or ``'unsafe-eval'`` for script);
* no inline ``<script>`` block, ``on*=`` attribute or ``javascript:`` URL in any page, nor in the
  HTML templates inside the page scripts;
* every ``data-action`` a page can render has a handler in that page's script, so a typo cannot
  leave a button dead.

Static checks only; the real-browser run (no CSP violation, controls work) is separate evidence.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from interface.headers import CONTENT_SECURITY_POLICY

WEB = Path(__file__).resolve().parent.parent / "interface" / "web"
PAGES = sorted(WEB.glob("*.html"))
SCRIPTS = sorted(WEB.glob("*.js"))
INLINE_HANDLER = re.compile(r"""[\s"']on[a-z]{3,}\s*=\s*["']""", re.I)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc\s*=)[^>]*>", re.I)


def _directives() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in CONTENT_SECURITY_POLICY.split(";"):
        tokens = part.split()
        if tokens:
            out[tokens[0]] = tokens[1:]
    return out


def test_there_are_pages_and_scripts_to_check():
    # A glob that silently matches nothing would make every test below vacuous.
    assert {p.name for p in PAGES} >= {"index.html", "settings.html", "wizard.html"}
    assert {p.name for p in SCRIPTS} >= {"auth.js", "index.js", "settings.js", "wizard.js"}


class TestPolicy:
    def test_script_src_is_self_only(self):
        assert _directives()["script-src"] == ["'self'"]

    def test_no_unsafe_eval_anywhere(self):
        assert "'unsafe-eval'" not in CONTENT_SECURITY_POLICY

    def test_default_src_does_not_reopen_inline_script(self):
        # Without script-src, default-src would apply; neither may allow inline.
        for name in ("default-src", "script-src"):
            assert "'unsafe-inline'" not in _directives()[name]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
class TestPagesCarryNoInlineScript:
    def test_no_inline_script_block(self, page):
        assert not INLINE_SCRIPT.findall(page.read_text(encoding="utf-8"))

    def test_no_inline_event_handler_attribute(self, page):
        assert not INLINE_HANDLER.findall(page.read_text(encoding="utf-8"))

    def test_no_javascript_url(self, page):
        assert "javascript:" not in page.read_text(encoding="utf-8").lower()

    def test_every_script_src_is_a_local_static_file(self, page):
        for src in re.findall(r"""<script[^>]*\bsrc\s*=\s*["']([^"']+)["']""", page.read_text(encoding="utf-8"), re.I):
            assert src.startswith("/static/"), src
            assert (WEB / src.removeprefix("/static/")).is_file(), src


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
class TestScriptsDoNotEmitInlineHandlers:
    def test_no_inline_handler_in_an_html_template(self, script):
        # ``el.onclick = fn`` is fine (a property, not markup); ``<b onclick="...">`` in a template is not.
        assert not INLINE_HANDLER.findall(script.read_text(encoding="utf-8"))

    def test_no_eval_or_function_constructor(self, script):
        text = script.read_text(encoding="utf-8")
        assert not re.search(r"\beval\s*\(|new\s+Function\s*\(|document\.write\s*\(", text)


@pytest.mark.parametrize("name", ["index", "settings", "wizard"])
def test_every_rendered_data_action_has_a_handler(name):
    html = (WEB / f"{name}.html").read_text(encoding="utf-8")
    js = (WEB / f"{name}.js").read_text(encoding="utf-8")
    used = set(re.findall(r'data-action="([a-z-]+)"', html + js))
    assert used, f"{name}: no data-action found; the wiring check would be vacuous"
    # A handler names its action as a single-quoted literal (object key or comparison); markup uses double quotes.
    missing = sorted(a for a in used if f"'{a}'" not in js)
    assert not missing, f"{name}: data-action without a handler: {missing}"


@pytest.mark.parametrize("name", ["index", "settings", "wizard"])
def test_a_page_script_registers_its_delegated_listeners(name):
    js = (WEB / f"{name}.js").read_text(encoding="utf-8")
    assert "document.addEventListener('click'" in js
