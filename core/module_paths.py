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
path component and the final path, canonicalized with os.path.realpath()
(symlinks followed), to be a *direct child* of `root` -- not merely somewhere
below it. Containment is decided on those canonical strings: normalize the
base, normalize the candidate, require candidate.startswith(base + os.sep),
then require exactly one component below the base:

  * Deliberately weaker than `.isidentifier()` on *what a name may be*: a
    registry entry is a directory basename (module_registry.load_all), and
    /train/{module_name} is guarded by registry membership, not by an
    identifier check. Those semantics are preserved -- a name such as
    "my-module" is accepted here.
  * Deliberately independent of it on *where the result may point*: nothing
    that is not a direct child of `root` comes back.

Consequences worth knowing, all decided on the canonical (symlink-resolved)
path:

  * A name that is a symlink to somewhere outside `root`, or to a descendant
    of a sibling (root/nested/x), is rejected: the result is not a direct
    child of `root`.
  * A name that is a symlink to *another direct child* (root/alias ->
    root/real) is accepted and the canonical target (root/real) is returned.
    Two names can therefore address one directory; both stay inside `root`.
  * A symlink loop is rejected with the same fixed error on every Python
    version. realpath() never raises on a loop (and Path.resolve() stopped
    raising in 3.13), so loops are detected by asking the OS: stat() on the
    validated canonical path reports ELOOP (POSIX; Windows loop behaviour is
    untested). A path that merely does not exist yet is fine: callers create
    it. Only ELOOP is a verdict; any other stat() error says nothing about
    containment.
  * Symlinks *below* the module directory (e.g. modules/<name>/weights) are
    not inspected by this helper.
  * The check is a point-in-time answer about the returned path; it does not
    hold a handle, so it does not defend against the path being swapped
    afterwards.

The error text is fixed and does not echo the input.
"""
import errno
import os
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
    try:
        base = os.path.realpath(os.fspath(root))
        candidate = os.path.realpath(os.path.join(base, module_name + suffix))
    except (OSError, ValueError):
        raise InvalidModuleName(_MESSAGE) from None
    # Strictly below the base. The separator keeps a sibling such as
    # "<base>_evil" out; stripping first keeps a base of "/" working.
    if not candidate.startswith(base.rstrip(os.sep) + os.sep):
        raise InvalidModuleName(_MESSAGE)
    # Exactly one component below it (also excludes the base itself, which
    # only matters for "/": every other base fails the check above).
    if candidate == base or os.path.dirname(candidate) != base:
        raise InvalidModuleName(_MESSAGE)
    # Loop probe, on the validated path only. realpath() hands a loop back
    # unresolved, so the OS has to be asked; ELOOP is the only verdict, a
    # path that does not exist yet (ENOENT) is legitimate.
    try:
        os.stat(candidate)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise InvalidModuleName(_MESSAGE) from None
    return Path(candidate)
