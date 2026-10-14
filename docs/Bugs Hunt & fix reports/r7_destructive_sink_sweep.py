"""R7 destructive-sink sweep (Oct 2026) -- see R7_DESTRUCTIVE_SINK_SWEEP_OCT2026.md.

Usage (from the repo root):   python3 "docs/Bugs Hunt & fix reports/r7_destructive_sink_sweep.py" <git-ref> [all]

Enumerates filesystem-MUTATING call sites in production .py files at <git-ref>
(shutil.rmtree/move/copy*, os.remove/unlink/rename/makedirs..., Path.unlink/
write_text/mkdir/touch, open(..., "w"/"a"/"x"), extractall) and classifies where each
path argument comes from by resolving local assignments (depth <= 5):
  GUARDED  routed through module_child()/validate_module_name()
  PARAM    derives from a function parameter  -> needs a caller trace (the review queue)
  STATE    derives from self.<attr> (constructor/config state)
  CONST    constants / module globals only
LIMITS (it is a heuristic): intra-function only -- a parameter is "PARAM" whether the
caller is trusted or not; no dynamic dispatch (getattr, string-dispatch), no shell
strings / subprocess file ops, no cross-function taint beyond parameters; excludes
tests/, docs/, archives. Silence is weak evidence of safety: validate recall on a known-bad
site (privacy.py::wipe_module_data before PR #79) before trusting a clean result.
"""
import ast, subprocess, sys, collections
ref = sys.argv[1]; show_all = len(sys.argv) > 2
sh = lambda *a: subprocess.run(a, capture_output=True, text=True).stdout
files = [f for f in sh("git", "ls-tree", "-r", "--name-only", ref).splitlines()
         if f.endswith(".py") and not f.startswith(("tests/", "docs/", "archive/", "Archive/")) and f != "core/module_paths.py"]
FUNCS = {"shutil.rmtree", "shutil.move", "shutil.copytree", "shutil.copy", "shutil.copy2", "shutil.copyfile", "shutil.make_archive",
         "shutil.unpack_archive", "os.remove", "os.unlink", "os.rmdir", "os.removedirs", "os.rename", "os.replace", "os.makedirs", "os.mkdir", "os.truncate"}
METH = {"unlink", "rmdir", "write_text", "write_bytes", "touch", "mkdir", "extractall", "rmtree"}
ONE_ARG_METH = {"rename", "replace"}   # Path.rename/replace take 1 arg; str.replace takes 2+
dotted = lambda n: (dotted(n.value) + "." + n.attr) if isinstance(n, ast.Attribute) else (n.id if isinstance(n, ast.Name) else "?")
def origins(n, assigns, params, depth=0):
    t = set()
    if depth > 5 or n is None: return {"deep"}
    if isinstance(n, ast.Constant): return {"const"}
    if isinstance(n, ast.Name):
        if n.id in assigns:
            for v in assigns[n.id]: t |= origins(v, {k: x for k, x in assigns.items() if k != n.id}, params, depth + 1)
            return t or {"unknown"}
        if n.id in params: return {"param:" + n.id}
        return {"global"}
    if isinstance(n, ast.Call):
        fn = dotted(n.func)
        if fn.endswith("module_child") or fn.endswith("validate_module_name"): return {"module_child"}
        for a in list(n.args) + [k.value for k in n.keywords]: t |= origins(a, assigns, params, depth + 1)
        if isinstance(n.func, ast.Attribute): t |= origins(n.func.value, assigns, params, depth + 1)
        return t or {"call"}
    if isinstance(n, ast.Attribute):
        if isinstance(n.value, ast.Name) and n.value.id in ("self", "cls"): return {"state:" + n.attr}
        return origins(n.value, assigns, params, depth + 1)
    for c in ast.iter_child_nodes(n): t |= origins(c, assigns, params, depth + 1)
    return t or {"unknown"}
rows = []
def walk(node, fstack, assigns_stack, src, path):
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = {}
            for st in ast.walk(ch):
                if isinstance(st, ast.Assign):
                    for tg in st.targets:
                        if isinstance(tg, ast.Name): a.setdefault(tg.id, []).append(st.value)
                elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value: a.setdefault(st.target.id, []).append(st.value)
                elif isinstance(st, (ast.For, ast.AsyncFor)) and isinstance(st.target, ast.Name): a.setdefault(st.target.id, []).append(st.iter)
                elif isinstance(st, ast.With):
                    for it in st.items:
                        if isinstance(it.optional_vars, ast.Name): a.setdefault(it.optional_vars.id, []).append(it.context_expr)
            walk(ch, fstack + [ch], assigns_stack + [a], src, path)
        else:
            if isinstance(ch, ast.Call):
                fn = dotted(ch.func); targets = None
                if fn in FUNCS: targets = list(ch.args)
                elif isinstance(ch.func, ast.Attribute) and ch.func.attr in METH: targets = list(ch.args) if ch.func.attr == "extractall" else [ch.func.value]
                elif isinstance(ch.func, ast.Attribute) and ch.func.attr in ONE_ARG_METH and len(ch.args) == 1: targets = [ch.func.value] + list(ch.args)
                elif fn == "open" or (isinstance(ch.func, ast.Attribute) and ch.func.attr == "open"):
                    mode = ch.args[1] if (fn == "open" and len(ch.args) > 1) else (ch.args[0] if (fn != "open" and ch.args) else None)
                    for k in ch.keywords:
                        if k.arg == "mode": mode = k.value
                    if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wax+"):
                        targets = [ch.args[0]] if fn == "open" and ch.args else [ch.func.value]
                if targets:
                    assigns = {}
                    for a in assigns_stack: assigns.update(a)
                    params = {x.arg for f in fstack for x in f.args.args + f.args.kwonlyargs + f.args.posonlyargs} - {"self", "cls"}
                    tags = set()
                    for t in targets: tags |= origins(t, assigns, params)
                    if any(x.startswith("param:") for x in tags): cls = "PARAM"
                    elif "module_child" in tags: cls = "GUARDED"
                    elif any(x.startswith("state:") for x in tags): cls = "STATE"
                    else: cls = "CONST"
                    rows.append((cls, path, ch.lineno, fstack[-1].name if fstack else "<module>", (ast.unparse(ch)[:88]), sorted(tags)))
            walk(ch, fstack, assigns_stack, src, path)
for f in files:
    src = sh("git", "show", f"{ref}:{f}")
    try: tree = ast.parse(src)
    except SyntaxError: print("PARSE FAIL", f); continue
    walk(tree, [], [], src, f)
c = collections.Counter(r[0] for r in rows)
print(f"REF={ref}  files={len(files)}  filesystem-mutating call sites={len(rows)}  ", dict(c))
chk = [r for r in rows if r[1] == "core/privacy.py" and r[3] == "wipe_module_data"]
print("RECALL CHECK  privacy.py::wipe_module_data ->", [r[0] for r in chk] or "NOT FOUND (sweep missed it!)")
for cls in (("PARAM", "STATE") if not show_all else ("PARAM", "STATE", "GUARDED", "CONST")):
    q = [r for r in rows if r[0] == cls]
    print(f"\n--- {cls} ({len(q)}) ---")
    for _, p, l, fn, snip, tg in q[:70]: print(f"{p}:{l} in {fn}()  {snip}   <- {','.join(x for x in tg if x not in ('const','global','deep'))[:60]}")
