"""chromadb pin agreement (issue #65, DEBT-032).

The project deliberately pins ``chromadb==0.5.3`` (embedded-only boundary,
see DEBT-032 in KNOWN_ISSUES.md). The pin is declared in three places that
must never drift apart:

* ``requirements.txt``                 - the reference declaration
* ``pyproject.toml``                   - package metadata
* ``.github/workflows/release.yml``    - every ``pip install ... chromadb`` line

This test pins the *agreement* and the *exactness* of the pin. It does not
hard-code the version number, so the planned compatibility study can change
it by editing the three declarations together. It does not assert that the
pinned version is free of advisories; that is a separate decision (DEBT-032).

Not covered by design: the Android p4a ``--requirements`` list in
``release.yml`` names ``chromadb`` without a version and is not a pip pin.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXACT = re.compile(r"^chromadb\s*==\s*([0-9][0-9A-Za-z.\-+!]*)\s*$", re.IGNORECASE)
NAME = re.compile(r"^\s*chromadb\b", re.IGNORECASE)


def _requirements_specs() -> list[str]:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [ln.split("#", 1)[0].strip() for ln in lines if NAME.match(ln)]


def _pyproject_specs() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data.get("project", {})
    groups = [project.get("dependencies", [])]
    groups += list(project.get("optional-dependencies", {}).values())
    return [spec.strip() for group in groups for spec in group if NAME.match(spec)]


def _release_install_tokens() -> list[str]:
    """Every whitespace-separated token naming chromadb on a pip-install line."""
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    tokens: list[str] = []
    for line in text.splitlines():
        if "pip install" in line and re.search(r"\bchromadb\b", line, re.IGNORECASE):
            tokens += [t for t in line.split() if NAME.match(t)]
    return tokens


def _version(spec: str) -> str:
    match = EXACT.match(spec)
    assert match, f"not an exact chromadb==X pin: {spec!r}"
    return match.group(1)


def test_requirements_declares_exactly_one_exact_pin() -> None:
    specs = _requirements_specs()
    assert len(specs) == 1, f"expected one chromadb line in requirements.txt, got {specs!r}"
    _version(specs[0])


def test_pyproject_declares_exactly_one_exact_pin() -> None:
    specs = _pyproject_specs()
    assert len(specs) == 1, f"expected one chromadb entry in pyproject.toml, got {specs!r}"
    _version(specs[0])


def test_release_workflow_pins_every_chromadb_install() -> None:
    tokens = _release_install_tokens()
    assert tokens, "release.yml has no 'pip install ... chromadb' line (check would be vacuous)"
    for token in tokens:
        _version(token)


def test_all_declarations_agree() -> None:
    reference = _version(_requirements_specs()[0])
    assert _version(_pyproject_specs()[0]) == reference, "pyproject.toml disagrees with requirements.txt"
    for token in _release_install_tokens():
        assert _version(token) == reference, f"release.yml {token!r} disagrees with requirements.txt"
