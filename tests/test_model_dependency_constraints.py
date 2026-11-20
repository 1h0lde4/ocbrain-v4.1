"""Keep security-sensitive model dependency bounds aligned across installers."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SECURITY_BOUNDS = {
    "sentence-transformers": ">=6.0.0,<7.0.0",
    "transformers": ">=5.10.0,<6.0.0",
}


def _project_specs(package: str) -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data.get("project", {})
    groups = [project.get("dependencies", [])]
    groups += list(project.get("optional-dependencies", {}).values())
    return [
        spec
        for group in groups
        for spec in group
        if re.match(rf"^{re.escape(package)}(?=[<>=!~])", spec, re.IGNORECASE)
    ]


def _requirements_specs(package: str) -> list[str]:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [
        line.split("#", 1)[0].strip()
        for line in lines
        if re.match(
            rf"^\s*{re.escape(package)}(?=[<>=!~])",
            line.split("#", 1)[0],
            re.IGNORECASE,
        )
    ]


def _setup_specs(package: str) -> list[str]:
    text = (ROOT / "setup.sh").read_text(encoding="utf-8")
    quoted_args = [
        arg
        for line in text.splitlines()
        for arg in re.findall(r'"([^"\n]+)"', line)
    ]
    return [
        arg
        for arg in quoted_args
        if re.match(rf"^{re.escape(package)}(?=[<>=!~])", arg, re.IGNORECASE)
    ]


@pytest.mark.parametrize(("package", "expected"), SECURITY_BOUNDS.items())
def test_model_dependency_bounds_match_across_installers(
    package: str, expected: str
) -> None:
    expected_spec = f"{package}{expected}"
    assert _project_specs(package), f"{package} is missing from pyproject.toml"
    assert set(_project_specs(package)) == {expected_spec}
    assert _requirements_specs(package) == [expected_spec]
    setup_specs = _setup_specs(package)
    assert setup_specs, f"{package} is missing from setup.sh"
    assert set(setup_specs) == {expected_spec}
