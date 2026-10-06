"""
tests/test_module_factory_error_disclosure.py -- install path in a 400 body.

core/module_factory.create() raised
ValueError(f"Module '{name}' already exists at {dest}") and POST /modules/new
returns str(e) as the 400 detail, so the response carried the absolute install
path of the modules directory. CodeQL does not flag it. Reachable only when the
factory has been deliberately re-enabled (global.module_factory_enabled; it is
disabled by default as the RCE-001 containment), so low severity -- fixed
because it is the same class as the other response-text leaks and the message
loses nothing by dropping the path.

The path is not logged either: the caller needs the name, an operator can find
the directory from it.
"""
import pytest
from fastapi import HTTPException

import core.module_factory as mf
import interface.api as api_module


@pytest.fixture
def existing_module(tmp_path, monkeypatch):
    modules_dir = tmp_path / "private_install_root" / "modules"
    (modules_dir / "dup_mod").mkdir(parents=True)
    monkeypatch.setattr(mf, "MODULES_DIR", modules_dir)
    # Open the RCE-001 gate for this test only; nothing is created because the
    # duplicate check fires before any scaffolding.
    monkeypatch.setattr(
        mf.config, "get",
        lambda key, default=None: True if key == "global.module_factory_enabled" else default,
    )
    return modules_dir


def test_duplicate_error_names_the_module_but_not_the_path(existing_module):
    with pytest.raises(ValueError, match="already exists") as exc:
        mf.create("dup_mod", "d", "m", [], [])
    msg = str(exc.value)
    assert "dup_mod" in msg
    assert "private_install_root" not in msg
    assert str(existing_module) not in msg


@pytest.mark.asyncio
async def test_modules_new_400_body_has_no_install_path(existing_module):
    req = api_module.NewModuleRequest(
        name="dup_mod", desc="d", model="m", keywords=[], sources=[]
    )
    with pytest.raises(HTTPException) as exc:
        await api_module.new_module(req)
    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail
    assert "private_install_root" not in exc.value.detail
