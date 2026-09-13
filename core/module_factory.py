"""
core/module_factory.py — Scaffolds a new custom module from the template.
Called by CLI wizard and Web UI form.
"""
import shutil
from pathlib import Path
from core.config import config

TEMPLATE_DIR = Path(__file__).parent.parent / "modules" / "_template"
MODULES_DIR  = Path(__file__).parent.parent / "modules"


def create(
    name: str,
    desc: str,
    model: str,
    keywords: list[str],
    sources: list[str],
) -> Path:
    """
    Scaffold a new module. Returns the path to the new module folder.
    Raises ValueError on invalid name or duplicate.

    SECURITY (RCE-001, see KNOWN_ISSUES.md DEBT-021): disabled by default as
    an emergency containment measure. Set global.module_factory_enabled =
    true in settings.toml to re-enable. This gate sits here, in the one
    function every entry point (the /modules/new route, both bundle-import
    routers, and the local CLI wizard) converges on, rather than in any
    individual caller, so no entry point can bypass it by omission.
    """
    if not config.get("global.module_factory_enabled", False):
        raise RuntimeError(
            "Module creation is temporarily disabled (RCE-001 containment, "
            "see KNOWN_ISSUES.md DEBT-021). Set "
            "global.module_factory_enabled = true in settings.toml to "
            "re-enable once the fix in this file's placeholder-substitution "
            "step is confirmed deployed."
        )

    name = name.strip().lower().replace(" ", "_")
    if not name.isidentifier():
        raise ValueError(f"Invalid module name: '{name}'. Use only letters, digits, underscores.")

    dest = MODULES_DIR / name
    if dest.exists():
        raise ValueError(f"Module '{name}' already exists at {dest}")

    # 1. Copy template folder
    shutil.copytree(TEMPLATE_DIR, dest)

    # 2. Substitute placeholders in module.py
    #
    # SECURITY (RCE-001, KNOWN_ISSUES.md DEBT-021): name/desc are embedded
    # as CODE here, not merely as data -- the substituted text becomes part
    # of a Python source file that gets imported. repr() is the only
    # substitution that is safe for this by construction: it always
    # produces a syntactically valid Python string literal that evaluates
    # back to the exact original string, for any input whatsoever,
    # regardless of quotes/newlines/backslashes/unicode it contains. This
    # does not depend on name's .isidentifier() check above, or on desc
    # being validated at all -- that's deliberate. Validation is
    # defense-in-depth here, not the security mechanism; do not replace
    # this with a character blacklist.
    mod_file = dest / "module.py"
    text = mod_file.read_text()
    text = text.replace("{{NAME}}", repr(name)).replace("{{DESC}}", repr(desc))
    mod_file.write_text(text)

    # 3. Create weights subdirs
    for sub in ["weights/active", "weights/previous", "weights/pending"]:
        (dest / sub).mkdir(parents=True, exist_ok=True)

    # 4. Register in all three config files
    config.register_module(name, model, keywords, sources)

    print(f"[factory] Created module '{name}' at {dest}")
    return dest
