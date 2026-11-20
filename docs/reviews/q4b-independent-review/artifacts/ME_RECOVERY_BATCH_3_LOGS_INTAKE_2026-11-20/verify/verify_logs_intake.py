#!/usr/bin/env python3
"""Recompute the batch 3 intake checks recorded in ../README.md. Run from the repo root:
   python3 docs/reviews/q4b-independent-review/artifacts/ME_RECOVERY_BATCH_3_LOGS_INTAKE_2026-11-20/verify/verify_logs_intake.py
Reads received/*.zip in memory, the Batch 1 authenticated API captures and the Batch 2 intake package already in the
repo. Uses no network. Exits 1 if any check fails or fewer checks ran than expected."""
import datetime, hashlib, json, pathlib, re, struct, subprocess, sys, tempfile, zipfile
PKG = pathlib.Path(__file__).resolve().parent.parent
ART = PKG.parent
API = ART / "ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB" / "api"
B2_I001 = ART / "ME_RECOVERY_BATCH_2_INTAKE_2026-11-18" / "received" / "I001__ME07_CI_ARTIFACTS_PARTIAL_RECOVERY.zip"
RECOVER = PKG / "recover" / "recover_ps_redirect_members.py"
results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
rx = {p.name.split("__")[0]: p for p in sorted((PKG / "received").glob("*.zip"))}
print("== received files")
for k, p in rx.items(): b = p.read_bytes(); print(f"{k} {p.name.split('__',1)[1]} {len(b)}B sha256={hashlib.sha256(b).hexdigest()}")

print("\n== I005: damaged upload (PowerShell '>' re-encoding)")
raw = rx["I005"].read_bytes()
check("starts with the UTF-16LE byte-order mark FF FE", raw[:2] == b"\xff\xfe")
obs = raw[2:].decode("utf-16-le").encode("cp850")
check("every character maps back to one cp850 byte", True, f"{len(obs)} bytes")
check("not readable as a zip as delivered", not zipfile.is_zipfile(rx["I005"]))
cd = {}
for m in re.finditer(rb"PK\x01\x02", obs):
    o = m.start(); nl = struct.unpack("<H", obs[o+28:o+30])[0]
    cd[obs[o+46:o+46+nl].decode()] = (struct.unpack("<I", obs[o+16:o+20])[0], struct.unpack("<I", obs[o+24:o+28])[0])
z6 = zipfile.ZipFile(rx["I006"])
check("I005 central-directory CRC32 and size values equal I006's members", cd == {i.filename: (i.CRC, i.file_size) for i in z6.infolist()}, f"{len(cd)} members")
with tempfile.TemporaryDirectory() as td:
    r = subprocess.run([sys.executable, str(RECOVER), str(rx["I005"]), td, "--large-budget", "0"], capture_output=True, text=True)
    check("recovery script (fast mode) exits 0", r.returncode == 0)
    got = {f.name: f.read_bytes() for f in pathlib.Path(td).glob("VERIFIED_*")}
    check("exactly the two small members were derived", sorted(got) == ["VERIFIED_drift-and-ownership__system.txt", "VERIFIED_tests__system.txt"], str(sorted(got)))
    check("derived members are byte-identical to I006's clean members",
          got.get("VERIFIED_tests__system.txt") == z6.read("tests/system.txt") and got.get("VERIFIED_drift-and-ownership__system.txt") == z6.read("drift-and-ownership/system.txt"))

STRIP = lambda l: l[29:] if re.match(r"\d{4}-\d\d-\d\dT", l) else l
def text(z, n): return z.read(n).decode("utf-8").lstrip("\ufeff").replace("\r", "").split("\n")
expect = {"I006": ("40781867485", "tests", "0_tests.txt", "1_drift-and-ownership.txt", (2073, 14, 1)),
          "I007": ("39226693573", "tests", "1_tests.txt", "0_drift-and-ownership.txt", (2058, 14, 1))}
art_zip = zipfile.ZipFile(B2_I001)
for iid, (run, _, tests_n, drift_n, counts) in expect.items():
    print(f"\n== {iid}: run {run}")
    z = zipfile.ZipFile(rx[iid]); rd = json.loads((API / f"run_{run}_detail.body").read_text())
    jobs = {j["name"]: j for j in json.loads((API / f"run_{run}_jobs.body").read_text())["jobs"]}
    check("zip opens and every member's data matches its CRC32 (testzip)", zipfile.is_zipfile(rx[iid]) and z.testzip() is None, f"{len(z.namelist())} members")
    check("exactly four members: two job logs and two system logs", len(z.namelist()) == 4)
    for jobname, fn in (("tests", tests_n), ("drift-and-ownership", drift_n)):
        L = text(z, fn); body = "\n".join(STRIP(l) for l in L); stamps = [l[:27] for l in L if re.match(r"\d{4}-\d\d-\d\dT", l)]
        sysb = "\n".join(STRIP(l) for l in text(z, f"{jobname}/system.txt")); j = jobs[jobname]
        check(f"{jobname}: full head_sha {rd['head_sha'][:7]}... appears in the log", rd["head_sha"] in body)
        rid = re.findall(r"GitHub Actions (\d+)", sysb)
        check(f"{jobname}: runner in system.txt equals API runner_id {j['runner_id']}", rid and int(rid[0]) == j["runner_id"], f"log says {rid[:1]}")
        T = lambda x: datetime.datetime.strptime(x[:19], "%Y-%m-%dT%H:%M:%S")
        lo, hi = T(j["created_at"]), T(j["completed_at"]) + datetime.timedelta(seconds=5)
        check(f"{jobname}: log timestamps fall inside the API job window (created .. completed+5s)", lo <= T(stamps[0]) and T(stamps[-1]) <= hi, f"{stamps[0][:19]}..{stamps[-1][:19]} vs {j['created_at']}..{j['completed_at']}")
        if jobname == "tests":
            m = re.search(r"(\d+) passed, (\d+) skipped, (\d+) xfailed", body)
            check(f"pytest summary equals expected {counts}", m and tuple(map(int, m.groups())) == counts, m.group(0) if m else "none")
            check("test step is 'pytest tests/ -q --tb=short' (whole tests/ directory, quiet mode)", "pytest tests/ -q --tb=short" in body)
            check("CI gate reports it passed", "Test gate passed" in body)
            art = art_zip.read(f"ME07_CI_ACQUISITION/RUN_{run}_{rd['head_sha'][:7]}/extracted/pytest-output/pytest-output.txt").decode().replace("\r", "")
            al = [x for x in art.split("\n") if x.strip()]
            check("every non-empty line of the earlier pytest-output artifact appears verbatim in this log", al and all(x.strip() in body for x in al), f"{len(al)} lines")
            check("no per-file attestation: 'test_verification' never named, no PASSED/FAILED markers", "test_verification" not in body and not re.search(r"\bPASSED\b|\bFAILED\b", body))
n = len(results); print(f"\nchecks run: {n}; passed: {sum(results)}; failed: {n - sum(results)}")
assert n == 33, f"expected exactly 33 checks, ran {n}"
sys.exit(0 if all(results) else 1)
