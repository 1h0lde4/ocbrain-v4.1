import os, sys, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("module_paths", sys.argv[1]); mp = importlib.util.module_from_spec(spec); spec.loader.exec_module(mp)
def run(label, build, name="foo", suffix=""):
    with tempfile.TemporaryDirectory() as t:
        root = Path(t).resolve() / "root"; root.mkdir(); (root/"bar").mkdir(); (root/"nested").mkdir(); (root/"nested"/"actual_foo").mkdir()
        (Path(t)/"outside").mkdir()
        build(root, Path(t)/"outside")
        try:
            r = mp.module_child(root, name, suffix)
            rel = os.path.relpath(r, root)
            print(f"  {label:44s} ACCEPTED -> {rel}  (direct child: {r.parent == root})")
        except mp.InvalidModuleName as e: print(f"  {label:44s} InvalidModuleName")
        except BaseException as e: print(f"  {label:44s} LEAKED {type(e).__name__}: {str(e)[:50]}")
S = lambda root, link, tgt: (root/link).symlink_to(tgt, target_is_directory=True)
print("python", sys.version.split()[0])
run("plain child (no symlink)",             lambda r,o: None)
run("registry-style 'my-module'",           lambda r,o: None, name="my-module")
run("foo -> bar (other direct child)",       lambda r,o: S(r,"foo",r/"bar"))
run("foo -> nested/actual_foo (descendant)", lambda r,o: S(r,"foo",r/"nested"/"actual_foo"))
run("foo -> outside",                        lambda r,o: S(r,"foo",o))
run("foo -> foo (self loop)",                lambda r,o: S(r,"foo","foo"))
run("foo <-> baz (2-cycle)",                 lambda r,o: (S(r,"foo","baz"), S(r,"baz","foo")))
run("foo -> nested/lp, lp -> lp",            lambda r,o: (S(r,"foo",r/"nested"/"lp"), (r/"nested"/"lp").symlink_to("lp")))
run("foo -> missing (dangling, in root)",    lambda r,o: S(r,"foo",r/"missing"))
run("foo.json -> nested/x.json  (suffix)",   lambda r,o: (r/"foo.json").symlink_to(r/"nested"/"x.json"), suffix=".json")
run("foo.json -> foo.json (suffix self loop)", lambda r,o: (r/"foo.json").symlink_to("foo.json"), suffix=".json")
