"""
core/module_paths.py -- the one place a module name becomes a filesystem path.

A module name is a logical identifier, never a path. Several subsystems used
to build paths by joining it onto a root (`DATA_RAW / module_name`,
`EVAL_DIR / f"{module_name}.json"`, ...), each relying on whoever called it
having validated the name first. `.isidentifier()` at the entry points
(module_factory.create, export/import, /distill) stays as the strict
*naming* rule for new modules; it is not a filesystem boundary, and static
analysis (CodeQL py/path-injection) does not treat it as one.

`module_child()` is the filesystem boundary. It requires the name to be one
path component and the final path, canonicalized with resolve() (symlinks
followed), to sit inside `root`:

  * Deliberately weaker than `.isidentifier()` on *what a name may be*: a
    registry entry is a directory basename (module_registry.load_all), and
    /train/{module_name} is guarded by registry membership, not by an
    identifier check. Those semantics are preserved -- a name such as
    "my-module" is accepted here.
  * Deliberately independent of it on *where the result may point*: nothing
    that is not a direct child of `root` comes back.

Consequence worth knowing: because resolve() follows symlinks, a module
directory that is itself a symlink to somewhere outside `root` is rejected.
Symlinks *below* the module directory (e.g. modules/<name>/weights) are not
inspected by this helper.

The error text is fixed and does not echo the input.
"""
from pathlib import Path


class InvalidModuleName(ValueError):
    """The module name is not a single path component inside the root."""


_MESSAGE = "Invalid module_name: must be a single path component."


def validate_module_name(module_name: str) -> str:
    """Return module_name if it is a plain, single path component."""
    if (
        not isinstance(module_name, str)
        or not module_name
        or "\x00" in module_name
        or module_name in (".", "..")
        or "/" in module_name
        or "\\" in module_name
        or Path(module_name).name != module_name  # drive-relative forms on Windows
    ):
        raise InvalidModuleName(_MESSAGE)
    return module_name


def module_child(root: Path, module_name: str, suffix: str = "") -> Path:
    """Return root/(module_name + suffix), canonicalized, or raise.

    `suffix` is code-controlled (".json", "_gaps.json", ...). It is part of
    the contained path, so a suffix cannot be used to climb out of `root`
    either.
    """
    validate_module_name(module_name)
    base = Path(root).resolve()
    try:
        child = (base / (module_name + suffix)).resolve()
    except (OSError, ValueError):
        raise InvalidModuleName(_MESSAGE) from None
    if child == base or not child.is_relative_to(base):
        raise InvalidModuleName(_MESSAGE)
    return child
