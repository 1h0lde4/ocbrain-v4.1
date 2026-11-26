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
from html.parser import HTMLParser
from pathlib import Path

import pytest

from interface.headers import CONTENT_SECURITY_POLICY

WEB = Path(__file__).resolve().parent.parent / "interface" / "web"
PAGES = sorted(WEB.glob("*.html"))
SCRIPTS = sorted(WEB.glob("*.js"))
# HTML pages are parsed (every attribute form: quoted, unquoted, slash-separated tags). Handlers that a page script
# writes into an HTML template string are found by regex, but only inside tag-shaped text (``<tag ... on<event>=``,
# quoted or not, after ``${...}`` expressions are neutralised), so ``el.onclick = fn`` (a property) and a variable
# such as ``online = true`` are not flagged.
TEMPLATE_HANDLER = re.compile(r"<[a-zA-Z][^<>]*?(?<![\w.$-])on[a-z]{3,}\s*=(?![=>])", re.I)
_TEMPLATE_EXPR = re.compile(r"\$\{[^{}]*\}")


class _Inline(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name.lower().startswith("on"):
                self.found.append(f"<{tag} {name}>")
            if (value or "").strip().lower().startswith("javascript:"):
                self.found.append(f"<{tag} {name}=javascript:>")
        if tag.lower() == "script" and not any(n.lower() == "src" for n, _ in attrs):
            self.found.append("<script> without src")


def inline_script_in_html(text: str) -> list[str]:
    parser = _Inline()
    parser.feed(text)
    parser.close()
    return parser.found


def handlers_in_templates(text: str) -> list[str]:
    return TEMPLATE_HANDLER.findall(_TEMPLATE_EXPR.sub("X", text))


def _directives() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in CONTENT_SECURITY_POLICY.split(";"):
        tokens = part.split()
        if tokens:
            out[tokens[0]] = tokens[1:]
    return out


def test_there_are_pages_and_scripts_to_check():
    # A glob that silently matches nothing would make every test below vacuous.
    assert {p.name for p in PAGES} >= {"index.html", "settings.html"}
    assert {p.name for p in SCRIPTS} >= {"auth.js", "index.js", "settings.js"}
    assert "wizard.html" not in {p.name for p in PAGES}, "the wizard targeted routes that do not exist (E7); it was removed"


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
    def test_no_inline_script_handler_or_javascript_url(self, page):
        assert inline_script_in_html(page.read_text(encoding="utf-8")) == []

    def test_every_script_src_is_a_local_static_file(self, page):
        for src in re.findall(r"""<script[^>]*\bsrc\s*=\s*["']([^"']+)["']""", page.read_text(encoding="utf-8"), re.I):
            assert src.startswith("/static/"), src
            assert (WEB / src.removeprefix("/static/")).is_file(), src


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
class TestScriptsDoNotEmitInlineHandlers:
    def test_no_inline_handler_in_an_html_template(self, script):
        # ``el.onclick = fn`` is fine (a property, not markup); ``<b onclick="...">`` in a template is not.
        assert not handlers_in_templates(script.read_text(encoding="utf-8"))

    def test_no_eval_or_function_constructor(self, script):
        text = script.read_text(encoding="utf-8")
        assert not re.search(r"\beval\s*\(|new\s+Function\s*\(|document\.write\s*\(", text)


@pytest.mark.parametrize("name", ["index", "settings"])
def test_every_rendered_data_action_has_a_handler(name):
    html = (WEB / f"{name}.html").read_text(encoding="utf-8")
    js = (WEB / f"{name}.js").read_text(encoding="utf-8")
    used = set(re.findall(r'data-action="([a-z-]+)"', html + js))
    assert used, f"{name}: no data-action found; the wiring check would be vacuous"
    # A handler names its action as a single-quoted literal (object key or comparison); markup uses double quotes.
    missing = sorted(a for a in used if f"'{a}'" not in js)
    assert not missing, f"{name}: data-action without a handler: {missing}"


@pytest.mark.parametrize("name", ["index", "settings"])
def test_a_page_script_registers_its_delegated_listeners(name):
    js = (WEB / f"{name}.js").read_text(encoding="utf-8")
    assert "document.addEventListener('click'" in js


class TestTheDetectorsThemselves:
    """A detector that cannot fail proves nothing: pin what each one catches and what it leaves alone."""

    @pytest.mark.parametrize("html", [
        '<button onclick="go()">x</button>',
        "<button onclick='go()'>x</button>",
        "<img src=x onerror=alert(1)>",
        "<img/onerror=alert(1) src=x>",
        '<BODY ONLOAD="x()">',
        '<a href="javascript:alert(1)">x</a>',
        "<script>alert(1)</script>",
        '<script type="module">alert(1)</script>',
    ])
    def test_html_detector_catches_every_attribute_form(self, html):
        assert inline_script_in_html(html), html

    @pytest.mark.parametrize("html", [
        '<script src="/static/auth.js"></script>',
        '<button data-action="go" class="one">x</button>',
        '<div data-online="1" title="on = off">x</div>',
    ])
    def test_html_detector_leaves_clean_markup_alone(self, html):
        assert inline_script_in_html(html) == [], html

    @pytest.mark.parametrize("js", [
        "`<b onclick=\"x()\">`", "`<b onclick='x()'>`", "`<img src=x onerror=alert(1)>`", "`<img/onerror=alert(1)>`",
        "`<b class=\"${a > b ? 1 : 2}\" onclick=x()>`", "`<div\n  class=\"c\"\n  ONCLICK=\"x()\">`",
    ])
    def test_template_detector_catches_quoted_and_unquoted(self, js):
        assert handlers_in_templates(js), js

    @pytest.mark.parametrize("js", [
        "button.onclick = () => run();", "el.onkeydown=fn;", "const online = true;", "if (once === 1) {}", "x => onload => y",
        "const a = 1; const onboard = 2;", "`<b data-x=\"${online = 1}\">ok</b>`",
    ])
    def test_template_detector_leaves_properties_and_words_alone(self, js):
        assert not handlers_in_templates(js), js


def test_the_stage_class_is_built_from_an_allowlist_not_from_data():
    js = (WEB / "index.js").read_text(encoding="utf-8")
    assert "stage-${info.stage" not in js, "raw data must not reach a class attribute"
    assert "STAGE_CLASSES.includes(stage)" in js
    defined = set(re.findall(r"\.stage-([a-z]+)\b", (WEB / "index.html").read_text(encoding="utf-8")))
    assert set(re.search(r"STAGE_CLASSES = \[([^\]]*)\]", js).group(1).replace("'", "").replace(" ", "").split(",")) == defined
