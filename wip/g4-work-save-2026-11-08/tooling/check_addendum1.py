#!/usr/bin/env python3
"""Mechanical consistency check of Addendum 1 to the consolidated report (read-only).
usage: python3 -I check_addendum1.py ADDENDUM EVIDENCE_DIR REPO BUNDLE_ZIP P1C_PATCH REPORT [EXTRA_TEXT...]
"""
import re, sys, os, subprocess, hashlib, zipfile
add, evdir, repo, bundle, p1c, report, *extra = sys.argv[1:]
txt = open(add, encoding="utf-8").read(); lines = txt.splitlines(); ok = True
def fail(m):
    global ok; ok = False; print("FAIL:", m)
def git(*a):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True); return r.returncode, r.stdout.strip()
for tok in ("PLACEHOLDER", "REVIEW_", "<FILL", "TODO", "TBD", "XXX", "lorem", "about fifty"):
    if tok in txt: fail(f"token present: {tok}")
nums = [int(m.group(1)) for h in lines if (m := re.match(r"## (\d+)\. ", h))]
print("level-2 headings:", nums)
if nums != list(range(1, 9)): fail(f"section numbers not 1..8: {nums}")
refs = sorted({int(x) for x in re.findall(r"§(\d+)", txt)}); print("section references:", refs, "(some name the report's sections)")
if [r for r in refs if r not in nums]: fail("reference number outside 1..8")
want = "G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
ne = [l for l in lines if l.strip()]
print("last non-empty line ok:", ne[-1] == want)
if ne[-1] != want: fail("final line")
if "**Governing statuses, unchanged:** " + want not in txt: fail("governing-status line missing")
in_gate = False; st = []
for l in lines:
    if l.startswith("| Gate | Status"): in_gate = True; continue
    if in_gate:
        if not l.startswith("|"): break
        c = [x.strip() for x in l.strip("|").split("|")]
        if c and not set(c[0]) <= set("-"): st.append((c[0].strip("*"), c[1].strip("*")))
for g, s in st: print(f"   {s:8s} {g}")
if [g for g, s in st if s not in {"PASS", "FAIL", "BLOCKED", "NOT RUN"}]: fail("status word not allowed")
non = [g for g, s in st if not g.startswith("Overall") and s != "PASS"]; ov = [s for g, s in st if g.startswith("Overall")]
if len(ov) != 1: fail("one overall row required")
elif non and ov[0] == "PASS": fail("overall PASS with a non-PASS gate")
elif not non and ov[0] != "PASS": fail("overall not PASS with all gates PASS")
print("non-PASS gates:", non, "| overall:", ov)
have = {f.split("_")[0] for f in os.listdir(evdir) if re.match(r"^[A-I]\d\d_", f)}
cited = {c for c in re.findall(r"\b([A-I]\d\d)\b", txt) if c[0] in "ABCDEFGHI"}
miss = sorted(cited - have - {"I37"}); print("ids cited:", sorted(cited), "| missing files:", miss)
if miss: fail("cited evidence id without file")
evtext = "".join(open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read() for f in os.listdir(evdir) if os.path.isfile(os.path.join(evdir, f)))
for f in extra + [p1c, report]: evtext += open(f, encoding="utf-8", errors="replace").read()
def ev(n): 
    for f in os.listdir(evdir):
        if f.startswith(n + "_"): return open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read()
    return ""
f40 = sorted(set(re.findall(r"\b[0-9a-f]{40}\b", txt)))
unres = [s for s in f40 if git("cat-file", "-t", s)[0] != 0 and s not in evtext]; print("40-hex ids:", len(f40), "| unresolved:", unres)
if unres: fail("unresolved 40-hex")
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
deliv = {sha(bundle), sha(p1c), sha(report)}
f64 = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", txt))); nf = [s for s in f64 if s not in evtext and s not in deliv]
print("64-hex digests:", len(f64), "| not backed:", nf)
if nf: fail("digest not backed")
for n, f in (("bundle", bundle), ("P1c", p1c), ("report", report)):
    print(f"   {n}: {sha(f)} cited: {sha(f) in txt}")
    if sha(f) not in txt: fail(f"{n} hash not cited or stale")
alld = set(re.findall(r"\b[0-9a-f]{64}\b", evtext)) | deliv | set(re.findall(r"\b[0-9a-f]{40}\b", evtext))
pre = sorted(set(re.findall(r"(?<!…)\b([0-9a-f]{8,16})…", txt)))
unp = [p for p in pre if not any(d.startswith(p) for d in alld) and git("cat-file", "-t", p)[0] != 0]
print("abbreviated hex ids:", len(pre), "| not a prefix of any id seen:", unp)
if unp: fail("abbreviated id with no source")
# bundle: manifest matches contents, read without extracting
z = zipfile.ZipFile(bundle); man = z.read("MANIFEST.sha256").decode().splitlines(); bad = 0
for l in man:
    h, p = l.split(None, 1); p = p.strip().lstrip("./")
    if hashlib.sha256(z.read(p)).hexdigest() != h: bad += 1
names = {n for n in z.namelist() if not n.endswith("/")}
listed = {l.split(None, 1)[1].strip().lstrip("./") for l in man}
print("bundle manifest entries:", len(man), "| mismatches:", bad, "| unlisted files:", sorted(names - listed - {"MANIFEST.sha256"}))
if bad or (names - listed - {"MANIFEST.sha256"}): fail("bundle manifest")
claims = [
 ("I32 P1b apply-check exit 0", "I32", r"P1b git apply --check exit 0"),
 ("I32 live remote tip 51564e34 before", "I32", r"51564e34c18e5cc908cf517000ebc9bd41eaf194\trefs/heads/docs/g4-fts-errata-handoff-oct2026"),
 ("I32 backup branch made", "I32", r"wip-backup-rev2-local-f3995bd.*|f3995bdc9c484bb43119440603c6cbe1aa70fb03\n# ---- end output"),
 ("I33 amended to d963daa with parent 51564e34", "I33", r"amended -> d963daa502de4220411d0d0c2f19f67b3ec2682b parent 51564e34c18e5cc908cf517000ebc9bd41eaf194"),
 ("I33 numstat 6 0 handoff.md", "I33", r"6\t0\thandoff\.md"),
 ("I33 19 headings 547 lines CR 0", "I33", r"headings: 19; lines: 547; CR: 0"),
 ("I33 diff --check clean and two commits after eca2b96", "I33", r"git diff --check clean[\s\S]*now\n2\n"),
 ("I34 fast-forward and push exit 0", "I34", r"fast-forward YES[\s\S]*51564e3\.\.d963daa[\s\S]*push exit: 0"),
 ("I34 flawed block: stale blob mismatch present", "I34", r"remote handoff\.md equals local handoff\.md \(blob\)\n05296d7339e7565116156cecaf047961c51b75ea\nf3434b71516445856e106b5e12d48801b643d057"),
 ("I34 flawed block: no 'origin/... == HEAD: YES' line", "I34", r"^(?![\s\S]*== HEAD: YES)[\s\S]*$"),
 ("I34 no PR for REV2 branch (0)", "I34", r"no PR was opened for the REV2 branch \(read-only API\)\n0\n"),
 ("I35 tip == HEAD YES", "I35", r"origin/docs/g4-fts-errata-handoff-oct2026 == HEAD: YES"),
 ("I35 three equal blobs", "I35", r"remote: f3434b71516445856e106b5e12d48801b643d057\nlocal:  f3434b71516445856e106b5e12d48801b643d057\nwork:   f3434b71516445856e106b5e12d48801b643d057"),
 ("I35 two commits, parent 51564e34, handoff.md only", "I35", r"count: 2[\s\S]*51564e34c18e5cc908cf517000ebc9bd41eaf194\nM\thandoff\.md"),
 ("I35 REV3 tip and main unchanged, 0 remote backups", "I35", r"9407db5a01acea9684f158caa8107fb71611a102\trefs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026\n2491ae469edd6ef1267a14604c4f8f40d698f7ea\trefs/heads/main\n0\n"),
 ("I35 PR #90 unchanged", "I35", r"state=open draft=true head=9407db5a01acea9684f158caa8107fb71611a102 commits=3 changed_files=7"),
 ("I35 clean tree, stash 0", "I35", r"local status: 0 changed, stash: 0"),
 ("I36 P1c apply-check exit 0, 3/3 lines, not applied", "I36", r"P1c git apply --check exit 0 on the pushed tree\n3\t3\thandoff\.md[\s\S]*3dabe97140b9b39f576592cea99bc8397406884055227de7cf97498eab279d5d[\s\S]*\n0\nd963daa502de4220411d0d0c2f19f67b3ec2682b\nd963daa502de4220411d0d0c2f19f67b3ec2682b\trefs/heads/docs/g4-fts-errata-handoff-oct2026"),
 ("I34 vulnerabilities notice 7 (3 critical, 4 high)", "I34", r"7 vulnerabilities .*\(3 critical, 4 high\)"),
]
for label, eid, rx in claims:
    f = re.search(rx, ev(eid), flags=re.M) is not None; print(f"   claim {'FOUND ' if f else 'MISSING'} {label}")
    if not f: fail(f"claim not found in {eid}: {label}")
rc, out = git("log", "-1", "--format=%aI|%cI", "d963daa502de4220411d0d0c2f19f67b3ec2682b"); print("live commit dates:", out)
if out != "2026-10-31T15:16:16+00:00|2026-11-01T23:47:48+00:00": fail("commit dates differ from the addendum")
rc, out = git("ls-remote", "origin", "refs/heads/docs/g4-fts-errata-handoff-oct2026")
print("live remote tip:", out)
if not out.startswith("d963daa502de4220411d0d0c2f19f67b3ec2682b"): fail("live remote tip differs (moved since the report, or push not present)")
print("RESULT:", "ALL MECHANICAL CHECKS PASSED" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
