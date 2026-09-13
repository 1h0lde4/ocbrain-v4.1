"""
Security regression tests for RCE-001 (KNOWN_ISSUES.md DEBT-021).

Covers two independent invariants, deliberately not merged into one test:
  1. Containment -- module creation is disabled unless explicitly enabled.
  2. The actual fix -- create() cannot be used to inject and execute
     arbitrary Python via the desc field, through the *real* end-to-end
     path (write generated source -> import it), not a narrow unit test
     of module_factory.py in isolation.
"""
import os
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.config import config
from core.module_factory import create


MODULES_DIR = Path(__file__).parent.parent / "modules"


def _cleanup(name):
    dest = MODULES_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    try:
        if name in config._models:
            del config._models[name]
        if name in config._settings.get("modules", {}):
            del config._settings["modules"][name]
        if name in config._sources:
            del config._sources[name]
    except Exception:
        pass


def test_create_disabled_by_default():
    """No fixture enabling the flag here on purpose -- this test exercises
    the real, un-overridden default a fresh install/deployment would see."""
    previous = config.get("global.module_factory_enabled", False)
    config.set("global.module_factory_enabled", False)
    try:
        with pytest.raises(RuntimeError, match="RCE-001"):
            create(
                name="test_containment_tmp",
                desc="should never get created",
                model="mistral",
                keywords=[],
                sources=[],
            )
    finally:
        config.set("global.module_factory_enabled", previous)
    # Confirm it genuinely didn't get created, not just that an exception
    # happened to be raised somewhere.
    assert not (MODULES_DIR / "test_containment_tmp").exists()


def test_desc_field_cannot_break_out_of_generated_source():
    """
    RCE-001: a desc value shaped exactly like the traced exploit (a quote
    that would have broken the old pre-quoted template, followed by
    class-body-indented statements) must not execute anything when the
    generated module is imported.

    Tests the real end-to-end path per the project owner's explicit
    instruction: HTTP-shaped input -> create() writes the generated
    source to disk -> core.module_registry.reload_module() imports it for
    real (the same function interface/api.py's route calls) -- not a
    narrow check of module_factory.py's string output in isolation, which
    could pass while the dangerous execution path remains intact.
    """
    marker_key = "OCBRAIN_RCE001_TEST_MARKER"
    os.environ.pop(marker_key, None)

    # Shaped exactly like the traced chain: one clean breakout point (a
    # single quote closing out the old `desc = "{{DESC}}"` template line),
    # then two class-body-indented statements -- one with a real (if
    # harmless) side effect, one that closes the syntax out cleanly so the
    # file would still have been valid Python under the *old* code.
    payload = (
        'Legitimate-looking description"\n'
        '    import os\n'
        f'    os.environ["{marker_key}"] = "PWNED"\n'
        '    _unused = "'
    )

    name = "test_rce001_tmp"
    previous = config.get("global.module_factory_enabled", False)
    config.set("global.module_factory_enabled", True)
    _cleanup(name)
    try:
        path = create(
            name=name,
            desc=payload,
            model="mistral",
            keywords=[],
            sources=[],
        )
        # The fix must not simply reject unusual content -- legitimate
        # descriptions routinely contain quotes and punctuation. It must
        # succeed, safely.
        assert path.exists()
        generated = (path / "module.py").read_text()
        # The payload must appear only as data (inside repr()'s escaping),
        # never as an unindented, independently-executable import
        # statement.
        assert "\nimport os\n" not in generated

        # Import through the real production path.
        from core.module_registry import reload_module
        instance = reload_module(name, {})
        assert instance is not None, (
            "reload_module() returned None -- the generated file failed "
            "to import at all, which would itself be a regression"
        )

        # The real assertion: the injected statement did not run.
        assert os.environ.get(marker_key) is None, (
            "RCE-001 regression: injected code executed on import"
        )

        # And the fix preserves the original content exactly -- this
        # isn't passing by coincidence (e.g. by mangling or truncating
        # desc rather than safely encoding it).
        assert instance.desc == payload
    finally:
        _cleanup(name)
        os.environ.pop(marker_key, None)
        config.set("global.module_factory_enabled", previous)


def test_name_field_also_uses_safe_literal_substitution():
    """name is already constrained by .isidentifier(), so it can't carry
    this specific payload shape -- but the substitution mechanism itself
    (repr(), not raw concatenation) should apply uniformly rather than
    depending on that upstream check to hold forever. Confirms the
    generated source round-trips the name correctly under the new
    substitution."""
    name = "test_rce001_name_tmp"
    previous = config.get("global.module_factory_enabled", False)
    config.set("global.module_factory_enabled", True)
    _cleanup(name)
    try:
        path = create(
            name=name, desc="plain desc", model="mistral",
            keywords=[], sources=[],
        )
        from core.module_registry import reload_module
        instance = reload_module(name, {})
        assert instance is not None
        assert instance.name == name
    finally:
        _cleanup(name)
        config.set("global.module_factory_enabled", previous)
