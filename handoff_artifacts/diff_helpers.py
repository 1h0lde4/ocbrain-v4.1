import os, sys, tempfile, importlib.util
from pathlib import Path
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
OLD, NEW = load(sys.argv[1], "old_mp"), load(sys.argv[2], "new_mp")
def verdict(mod, root, name, suffix, tmp):
    try:
        r = mod.module_child(root, name, suffix); return ("ok", os.path.relpath(r, tmp))
    except mod.InvalidModuleName: return ("InvalidModuleName",)
    except BaseException as e: return ("LEAK:" + type(e).__name__,)
L = lambda root, link, tgt, d=True: (root/link).symlink_to(tgt, target_is_directory=d)
def scenarios():
    yield "plain", None, {}, lambda r,t: None
    yield "plain-missing", None, {"name":"nope"}, lambda r,t: None
    yield "my-module", None, {"name":"my-module"}, lambda r,t: None
    yield "spaces+unicode", None, {"name":"a b Ünï"}, lambda r,t: None
    yield "alias->direct", None, {}, lambda r,t: L(r,"foo",r/"bar")
    yield "alias rel->direct", None, {}, lambda r,t: L(r,"foo","bar")
    yield "->nested", None, {}, lambda r,t: L(r,"foo",r/"nested"/"x")
    yield "->nested rel", None, {}, lambda r,t: L(r,"foo",Path("nested")/"x")
    yield "->outside", None, {}, lambda r,t: L(r,"foo",t/"outside")
    yield "->parent of root", None, {}, lambda r,t: L(r,"foo",t)
    yield "->root", None, {}, lambda r,t: L(r,"foo",r)
    yield "->sibling-prefix dir", None, {}, lambda r,t: L(r,"foo",t/"root_evil")
    yield "->sibling-prefix inner", None, {}, lambda r,t: L(r,"foo",t/"root_evil"/"inner")
    yield "self loop", None, {}, lambda r,t: L(r,"foo","foo")
    yield "2-cycle", None, {}, lambda r,t: (L(r,"foo","baz"), L(r,"baz","foo"))
    yield "3-cycle", None, {}, lambda r,t: (L(r,"foo","a1"), L(r,"a1","a2"), L(r,"a2","foo"))
    yield "->nested loop", None, {}, lambda r,t: (L(r,"foo",r/"nested"/"lp"), L(r/"nested","lp","lp"))
    yield "dangling in-root", None, {}, lambda r,t: L(r,"foo",r/"missing")
    yield "dangling outside", None, {}, lambda r,t: L(r,"foo",t/"outside"/"missing")
    yield "chain direct->direct", None, {}, lambda r,t: (L(r,"foo","baz"), L(r,"baz",r/"bar"))
    yield "chain direct->nested", None, {}, lambda r,t: (L(r,"foo","baz"), L(r,"baz",r/"nested"/"x"))
    yield "suffix plain", None, {"suffix":".json"}, lambda r,t: None
    yield "suffix ->nested", None, {"suffix":".json"}, lambda r,t: L(r,"foo.json",r/"nested"/"x.json",False)
    yield "suffix ->outside", None, {"suffix":".json"}, lambda r,t: L(r,"foo.json",t/"outside"/"x.json",False)
    yield "suffix loop", None, {"suffix":".json"}, lambda r,t: L(r,"foo.json","foo.json",False)
    yield "suffix ->direct file", None, {"suffix":".json"}, lambda r,t: ((r/"o.json").write_text("{}"), L(r,"foo.json",r/"o.json",False))
    yield "suffix descends", None, {"name":"bar","suffix":"/sub"}, lambda r,t: None
    yield "suffix climbs out", None, {"suffix":"/../../escaped"}, lambda r,t: None
    yield "suffix climbs to sibling-prefix", None, {"name":"bar","suffix":"/../../root_evil"}, lambda r,t: None
    yield "suffix stays in root", None, {"name":"bar","suffix":"/../zed"}, lambda r,t: None
    yield "suffix ->root", None, {"name":"bar","suffix":"/.."}, lambda r,t: None
    yield "root via symlink", "rootlink", {"name":"bar"}, lambda r,t: L(t,"rootlink",r)
    yield "root via symlink + alias", "rootlink", {}, lambda r,t: (L(t,"rootlink",r), L(r,"foo","bar"))
    yield "root is loop", "looproot", {"name":"bar"}, lambda r,t: L(t,"looproot","looproot")
    for hn in ["..", ".", "", "../x", "../../x", "a/b", "a\\b", "/etc/passwd", "x\x00y", "sub/../../up", "real/.."]:
        yield f"hostile {hn!r}", None, {"name":hn}, lambda r,t: None
div = 0; n = 0
for label, rootmode, kw, build in scenarios():
    with tempfile.TemporaryDirectory() as tt:
        t = Path(tt).resolve(); r = t/"root"; r.mkdir()
        for d in ["bar", "nested/x", "nested", "real"]: (r/d).mkdir(parents=True, exist_ok=True)
        (t/"outside").mkdir(); (t/"root_evil"/"inner").mkdir(parents=True)
        try: build(r, t)
        except (OSError, NotImplementedError) as e: print("SETUP-SKIP", label, e); continue
        root = t/rootmode if rootmode else r
        name, suffix = kw.get("name", "foo"), kw.get("suffix", "")
        a, b = verdict(OLD, root, name, suffix, t), verdict(NEW, root, name, suffix, t); n += 1
        flag = "" if a == b else "   <<<<<<<< DIVERGENCE"
        if a != b: div += 1
        if flag or "-v" in sys.argv: print(f"  {label:34s} old={a} new={b}{flag}")
print(f"python {sys.version.split()[0]}: {n} scenarios, {div} divergences")
