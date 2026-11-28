"""DEBT-012B attribution: print the first call stack that opens data/context.sqlite during `import interface.api`.
Run from the repo root; afterwards `git checkout -- data config` to revert the tracked-file side effect."""
import sqlite3, traceback, logging, os, hashlib
logging.disable(logging.CRITICAL)
DB = "data/context.sqlite"
sha = lambda: hashlib.sha256(open(DB, "rb").read()).hexdigest()
print("sha256 before import:", sha())
orig, seen = sqlite3.connect, []
def spy(database, *a, **k):
    if "context.sqlite" in str(database) and not seen:
        seen.append(1)
        print("FIRST OPEN of", database)
        for f in [f for f in traceback.extract_stack()[:-1] if os.sep + "core" + os.sep in f.filename or "interface" in f.filename][-6:]:
            print("   ", os.path.relpath(f.filename), f.lineno, f.name, "|", (f.line or "")[:80])
    return orig(database, *a, **k)
sqlite3.connect = spy
import interface.api  # noqa: E402
print("sha256 after import: ", sha())
