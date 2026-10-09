import subprocess, sys, shutil, re
from pathlib import Path
CASES = [
 ("M1 naive prefix, no separator", "core/brain_export.py", "candidate.startswith(root.rstrip(os.sep) + os.sep)", "candidate.startswith(root)"),
 ("M2 containment check removed", "core/brain_export.py", "if not candidate.startswith(root.rstrip(os.sep) + os.sep):", "if False:"),
 ("M3 suffix check removed (D3)", "core/brain_export.py", "if not candidate.endswith(_BUNDLE_SUFFIX):", "if False:"),
 ("M4 relative path taken from CWD (D2)", "core/brain_export.py", "os.path.join(root, os.fspath(bundle_path))", "os.path.abspath(os.fspath(bundle_path))"),
 ("M5 implicit data/exports fallback (D1)", "core/brain_export.py", "    if not isinstance(configured, str) or not configured.strip():\n        return None", "    if not isinstance(configured, str) or not configured.strip():\n        return os.path.realpath(EXPORTS)"),
 ("M6 no symlink resolution (abspath)", "core/brain_export.py", "candidate = os.path.realpath(os.path.join(root, os.fspath(bundle_path)))", "candidate = os.path.abspath(os.path.join(root, os.fspath(bundle_path)))"),
 ("M7 existence checked before containment", "core/brain_export.py", "    bundle_path = resolve_bundle_path(bundle_path)\n    if not bundle_path.exists():", "    if not bundle_path.exists():\n        raise FileNotFoundError('x')\n    bundle_path = resolve_bundle_path(bundle_path)\n    if False:"),
 ("M8 root itself accepted", "core/brain_export.py", "if not candidate.startswith(root.rstrip(os.sep) + os.sep):", "if candidate != root and not candidate.startswith(root.rstrip(os.sep) + os.sep):"),
 ("M9 suffix checked on the requested name, not canonical", "core/brain_export.py", "if not candidate.endswith(_BUNDLE_SUFFIX):", "if not os.fspath(bundle_path).endswith(_BUNDLE_SUFFIX):"),
 ("M10 /import handler does not map the refusal", "interface/api.py", "    except BundlePathError as e:\n        raise HTTPException(400, str(e))\n", "    except BundlePathError as e:\n        raise\n"),
]
survived = []
for name, f, old, new in CASES:
    p = Path(f); good = p.read_bytes().decode()
    crlf = "\r\n" in good
    o, n = (old.replace("\n", "\r\n"), new.replace("\n", "\r\n")) if crlf else (old, new)
    assert good.count(o) == 1, f"{name}: anchor not found/unique"
    p.write_bytes(good.replace(o, n, 1).encode())
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "-W", "ignore", "-x" if False else "-q",
                            "tests/test_import_bundle_boundary.py"], capture_output=True, text=True, env={**__import__('os').environ, "PYTHONPATH": "."})
    finally:
        p.write_bytes(good.encode())
    tail = [l for l in r.stdout.strip().splitlines() if "passed" in l or "failed" in l or "error" in l][-1:]
    failed = re.findall(r"FAILED [^:]+::(\S+)", r.stdout)
    caught = r.returncode != 0
    clean = "INTERNALERROR" not in r.stdout + r.stderr
    print(f"{'CAUGHT  ' if caught else 'SURVIVED'} {'clean' if clean else 'CRASHED-REPORTER'} {name:52s} {tail[0] if tail else ''}")
    if not caught: survived.append(name)
print("\nsurvivors:", survived or "none")
