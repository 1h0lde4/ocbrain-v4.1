import subprocess, sys, importlib.util, dataclasses, hashlib
GATE_SRC = subprocess.run(["git","-C","/home/claude/audit/wt-base","show","HEAD:scripts/ci_test_gate.py"],capture_output=True,text=True,check=True).stdout
assert GATE_SRC, "empty gate source"
print("gate_blob_sha1:", subprocess.run(["git","-C","/home/claude/audit/wt-base","rev-parse","HEAD:scripts/ci_test_gate.py"],capture_output=True,text=True).stdout.strip())
open("/tmp/probe/gate_mod.py","w").write(GATE_SRC)
spec = importlib.util.spec_from_file_location("gate_mod","/tmp/probe/gate_mod.py")
m = importlib.util.module_from_spec(spec); sys.modules["gate_mod"]=m; spec.loader.exec_module(m)
assert hasattr(m,"evaluate")
def run(args):
    p = subprocess.run([sys.executable,"-m","pytest","-p","no:cacheprovider","--no-header","-q","--tb=line","-rf"]+args,capture_output=True,text=True,cwd="/tmp/probe")
    assert p.returncode in (0,1), (p.returncode,p.stdout,p.stderr)
    return p.stdout, p.returncode
o_i,r_i = run(["test_probe.py::test_p[a - b]","test_probe.py::test_ok"])
o_ii,r_ii = run(["test_probe.py","-k","test_env or test_ok"])
o_iii,r_iii = run(["test_probe.py"])
print("exit codes:",r_i,r_ii,r_iii)
print([l for l in o_i.splitlines() if l.startswith("FAILED")])
def show(name,out,rc,al):
    v = m.evaluate(out,rc,set(al)); d=dataclasses.asdict(v); print(name,"ok=",d["ok"],"new=",d["new_failures"],"reasons=",d["reasons"])
show("S1",o_i,r_i,["test_probe.py::test_p[a - b]"])
show("S2",o_i,r_i,["test_probe.py::test_p[a"])
show("S3",o_iii,r_iii,["test_probe.py::test_p[a","test_probe.py::test_env"])
show("S4",o_ii,r_ii,["test_probe.py::test_env"])
# long-ID check at default width and COLUMNS=80
import os
for cols in ("80","200"):
    p = subprocess.run([sys.executable,"-m","pytest","-p","no:cacheprovider","--no-header","-q","--tb=line","-rf","long_test.py"],capture_output=True,text=True,cwd="/tmp/probe",env={**os.environ,"COLUMNS":cols})
    print("LONG COLUMNS="+cols,"rc",p.returncode,[l for l in p.stdout.splitlines() if l.startswith("FAILED")])
