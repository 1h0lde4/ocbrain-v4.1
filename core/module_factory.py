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
    """
    name = name.strip().lower().replace(" ", "_")
    if not name.isidentifier():
        raise ValueError(f"Invalid module name: '{name}'. Use only letters, digits, underscores.")

    dest = MODULES_DIR / name
    if dest.exists():
        raise ValueError(f"Module '{name}' already exists at {dest}")

    # 1. Copy template folder
    shutil.copytree(TEMPLATE_DIR, dest)

    # 2. Substitute placeholders in module.py
    mod_file = dest / "module.py"
    text = mod_file.read_text()
    text = text.replace("{{NAME}}", name).replace("{{DESC}}", desc)
    mod_file.write_text(text)

    # 3. Create weights subdirs
    for sub in ["weights/active", "weights/previous", "weights/pending"]:
        (dest / sub).mkdir(parents=True, exist_ok=True)

    # 4. Register in all three config files
    config.register_module(name, model, keywords, sources)

    print(f"[factory] Created module '{name}' at {dest}")
    return dest
