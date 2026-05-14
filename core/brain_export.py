"""
core/brain_export.py — Export/import a module's brain as a .ocbrain bundle.
Portable across machines. Allows sharing domain-specific trained modules.

Bundle format (.ocbrain = zip):
    manifest.json        — metadata, versions, module name
    weights/             — LoRA adapter files
    knowledge/           — ChromaDB snapshot (SQLite files)
    evals/               — eval set JSON
    pairs_sample.jsonl   — 100 training pair samples (for inspection)
"""
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

ROOT    = Path(__file__).parent.parent
MODULES = ROOT / "modules"
DATA    = ROOT / "data"
EXPORTS = ROOT / "data" / "exports"


def _safe_read(path: Path, default: str) -> str:
    try:
        return path.read_text(encoding="utf-8").strip() or default
    except OSError:
        return default


def export_module(module_name: str, output_path: Optional[Path] = None) -> Path:
    """
    Export a module's brain to a .ocbrain bundle.
    Returns path to the created bundle.
    """
    from core.config import config
    from core.brain_version import brain_version_manager

    mod_dir = MODULES / module_name
    if not mod_dir.exists():
        raise ValueError(f"Module '{module_name}' not found.")

    EXPORTS.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = EXPORTS / f"{module_name}_{ts}.ocbrain"

    state      = config.get_module_state(module_name)
    brain_info = brain_version_manager.get_state().modules.get(module_name, {})

    manifest = {
        "format":          "ocbrain/1.0",
        "module_name":     module_name,
        "stage":           state.get("stage", "bootstrap"),
        "base_model":      state.get("base_model", ""),
        "lora_version":    brain_info.get("lora_version", 0),
        "training_pairs":  brain_info.get("total_training_pairs", 0),
        "kb_chunks":       brain_info.get("total_kb_chunks", 0),
        "exported_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "app_version":     _safe_read(ROOT / "version.txt", "0.0.0"),
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # 1. Manifest
        (tmp_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )

        # 2. LoRA weights (active only)
        weights_src = mod_dir / "weights" / "active"
        if weights_src.exists() and any(weights_src.iterdir()):
            shutil.copytree(weights_src, tmp_path / "weights")

        # 3. ChromaDB knowledge snapshot
        kb_src = mod_dir / "knowledge.db"
        if kb_src.exists():
            kb_dest = tmp_path / "knowledge"
            kb_dest.mkdir()
            # ChromaDB stores as a directory — copy the whole thing
            if kb_src.is_dir():
                shutil.copytree(kb_src, kb_dest / "knowledge.db")
            else:
                shutil.copy2(kb_src, kb_dest / "knowledge.db")

        # 4. Eval set
        eval_src = DATA / "evals" / f"{module_name}.json"
        if eval_src.exists():
            shutil.copy2(eval_src, tmp_path / "evals.json")

        # 5. Training pair sample (100 pairs max)
        raw_dir = DATA / "raw" / module_name
        if raw_dir.exists():
            pairs = []
            for f in sorted(raw_dir.glob("*.json"))[:100]:
                try:
                    pairs.append(json.loads(f.read_text()))
                except Exception:
                    continue
            if pairs:
                with open(tmp_path / "pairs_sample.jsonl", "w") as f:
                    for p in pairs:
                        f.write(json.dumps(p) + "\n")

        # 6. Zip everything
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in tmp_path.rglob("*"):
                if item.is_file():
                    zf.write(item, item.relative_to(tmp_path))

    print(f"[brain_export] Exported '{module_name}' → {output_path}")
    return output_path


def import_module(bundle_path: Path, overwrite: bool = False) -> str:
    """
    Import a .ocbrain bundle.
    Returns the module name that was imported.
    """
    from core.config import config

    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Extract bundle
        with zipfile.ZipFile(bundle_path, "r") as zf:
            zf.extractall(tmp_path)

        # Read manifest
        manifest_path = tmp_path / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("Invalid .ocbrain bundle — manifest.json missing.")
        manifest = json.loads(manifest_path.read_text())

        name    = manifest["module_name"]
        mod_dir = MODULES / name

        if mod_dir.exists() and not overwrite:
            raise ValueError(
                f"Module '{name}' already exists. "
                f"Use overwrite=True to replace it."
            )

        # Create/replace module directory
        if mod_dir.exists():
            shutil.rmtree(mod_dir)

        # Scaffold minimal module if no module.py in bundle
        from core.module_factory import create as factory_create
        try:
            factory_create(
                name=name,
                desc=manifest.get("desc", f"Imported module: {name}"),
                model=manifest.get("base_model", "mistral"),
                keywords=[],
                sources=[],
            )
        except ValueError:
            pass  # already registered during overwrite

        # Restore weights
        weights_src = tmp_path / "weights"
        if weights_src.exists():
            dest = mod_dir / "weights" / "active"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(weights_src, dest)

        # Restore ChromaDB
        kb_src = tmp_path / "knowledge" / "knowledge.db"
        if kb_src.exists():
            kb_dest = mod_dir / "knowledge.db"
            if kb_dest.exists():
                shutil.rmtree(kb_dest) if kb_dest.is_dir() else kb_dest.unlink()
            if kb_src.is_dir():
                shutil.copytree(kb_src, kb_dest)
            else:
                shutil.copy2(kb_src, kb_dest)

        # Restore eval set
        eval_src = tmp_path / "evals.json"
        if eval_src.exists():
            eval_dest = DATA / "evals" / f"{name}.json"
            eval_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(eval_src, eval_dest)

        # Update config stage
        config.set_module_state(name, "stage", manifest.get("stage", "bootstrap"))

    print(f"[brain_export] Imported '{name}' from {bundle_path}")
    return name
