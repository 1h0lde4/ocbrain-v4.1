#!/usr/bin/env python3
"""Mechanical consistency check of the consolidated evidence report (read-only).
usage: python3 -I check_consolidated.py REPORT EVIDENCE_DIR REPO BUNDLE P1B ADDENDA_DIR_FILES...
Checks: placeholder tokens, level-2 headings 1..10, governing/final status lines, gate statuses and overall
consistency, evidence IDs cited have files (I29 = this check, allowed), 40-hex ids resolvable, 64-hex digests backed,
abbreviated ids are prefixes, section references exist, delivered-file hashes cited are the real ones,
and a list of numeric claims re-found in the evidence text.
"""
import re, sys, os, subprocess, hashlib
report, evdir, repo, bundle, p1b, *extra = sys.argv[1:]
txt = open(report, encoding="utf-8").read()
lines = txt.splitlines()
ok = True
def fail(m):
    global ok; ok = False; print("FAIL:", m)

for tok in ("PLACEHOLDER", "REVIEW_", "<FILL", "TODO", "TBD", "XXX", "lorem"):
    if tok in txt: fail(f"token present: {tok}")
print("placeholders: checked")

heads = [l for l in lines if l.startswith("## ")]
nums = [int(m.group(1)) for h in heads if (m := re.match(r"## (\d+)\. ", h))]
print("level-2 headings:", nums)
if nums != list(range(1, 11)): fail(f"section numbers not 1..10: {nums}")
refs = sorted({int(x) for x in re.findall(r"§(\d+)", txt)})
print("section references:", refs, "| missing targets:", [r for r in refs if r not in nums])
if [r for r in refs if r not in nums]: fail("reference to a section that does not exist (for this report)")

nonempty = [l for l in lines if l.strip()]
want = "G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
print("last non-empty line ok:", nonempty[-1] == want)
if nonempty[-1] != want: fail("final status line mismatch")
if "**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED." not in txt:
    fail("governing-status line missing")

in_gate = False; st = []
for l in lines:
    if l.startswith("| Gate | Status"): in_gate = True; continue
    if in_gate:
        if not l.startswith("|"): break
        c = [x.strip() for x in l.strip("|").split("|")]
        if c and not set(c[0]) <= set("-"): st.append((c[0].strip("*"), c[1].strip("*")))
print("gate rows:", len(st))
for g, s in st: print(f"   {s:8s} {g}")
bad = [g for g, s in st if s not in {"PASS", "FAIL", "BLOCKED", "NOT RUN"}]
if bad: fail(f"status word not allowed: {bad}")
nonpass = [g for g, s in st if g != "Overall result" and s != "PASS"]
ov = [s for g, s in st if g == "Overall result"]
print("non-PASS gates:", nonpass, "| overall:", ov)
if len(ov) != 1: fail("exactly one overall row required")
elif nonpass and ov[0] == "PASS": fail("overall PASS although a gate is not PASS")
elif not nonpass and ov[0] != "PASS": fail("overall not PASS although every gate passes")
# the held push must be shown as not done everywhere it is described
if not any(g.startswith("P1 pushed") and s == "BLOCKED" for g, s in st): fail("P1 push gate must be BLOCKED")

have = {f.split("_")[0] for f in os.listdir(evdir) if re.match(r"^[A-I]\d\d_", f)}
cited = {c for c in re.findall(r"\b([A-I]\d\d)\b", txt) if c[0] in "ABCDEFGHI"}
missing = sorted(cited - have - {"I29"})
print("ids cited:", len(cited), "| missing files:", missing)
if missing: fail("cited evidence id without file")

evtext = ""
for f in os.listdir(evdir):
    q = os.path.join(evdir, f)
    if os.path.isfile(q): evtext += open(q, encoding="utf-8", errors="replace").read()
for f in extra + [p1b]:
    evtext += open(f, encoding="utf-8", errors="replace").read()
def ev(name):
    for f in os.listdir(evdir):
        if f.startswith(name + "_"): return open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read()
    return ""

def objtype(sha):
    r = subprocess.run(["git", "-C", repo, "cat-file", "-t", sha], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None
f40 = sorted(set(re.findall(r"\b[0-9a-f]{40}\b", txt)))
unres = [s for s in f40 if not objtype(s) and s not in evtext]
print("40-hex ids:", len(f40), "| unresolved (not a repo object, not in evidence text):", unres)
if unres: fail("unresolved 40-hex ids")

def sha(f): return hashlib.sha256(open(f, "rb").read()).hexdigest()
deliv = {sha(f) for f in (bundle, p1b) + tuple(extra)}
f64 = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", txt)))
nf = [s for s in f64 if s not in evtext and s not in deliv]
print("64-hex digests:", len(f64), "| not in evidence text or deliverable hashes:", nf)
if nf: fail("digest not backed")
for name, f in (("bundle", bundle), ("P1b", p1b)):
    h = sha(f); print(f"   {name}: {h}  cited in report: {h in txt}")
    if h not in txt: fail(f"{name} hash not cited or stale")

alld = set(re.findall(r"\b[0-9a-f]{64}\b", evtext)) | deliv | set(re.findall(r"\b[0-9a-f]{40}\b", evtext))
pre = sorted(set(re.findall(r"\b([0-9a-f]{8,16})…", txt)))
unp = [p for p in pre if not any(d.startswith(p) for d in alld) and not objtype(p)]
print("abbreviated hex ids:", len(pre), "| not a prefix of any id seen:", unp)
if unp: fail(f"abbreviated id with no source: {unp}")

# numeric claims re-found in the evidence they cite (evidence id, regex that must match its text)
claims = [
 ("+57/−3 lines on REV3 (I28)", "I28", r"4 files changed, 57 insertions\(\+\), 3 deletions\(-\)"),
 ("erratum 54 lines (I28)", "I28", r"\b54\s+0\s+docs/reports/g4-fts-correctness/DIGEST_DISCREPANCY_ERRATUM_REV3\.md"),
 ("3 ahead / 96 behind (I28)", "I28", r"ahead_by=3 behind_by=96"),
 ("PR #90 open draft 3 commits 7 files behind (I28)", "I28", r"state=open draft=true head=9407db5a01acea9684f158caa8107fb71611a102 .*commits=3 changed_files=7 mergeable_state=behind"),
 ("stash 0 and clean 0/0 (I28)", "I28", r"local status \(clone / worktree\): 0 / 0; stash entries: 0"),
 ("REV2 remote tip unchanged, P1 one ahead (I28)", "I28", r"ahead of remote tip: 1 \(unpushed\); remote tip is the pre-existing 51564e34: YES"),
 ("no FTS-pattern paths and no overlap (I28)", "I28", r"matching FTS patterns:\n\(end\)\noverlap of main-changed paths with PR #90 files:\n\(end\)"),
 ("P1 +5 lines, 19 headings, CR 0 (I22)", "I22", r"1 file changed, 5 insertions\(\+\)[\s\S]*level-2 headings: 19; lines: 546; CR: 0"),
 ("P1 apply-check exit 0 and P3 apply-check exit 0 (I21)", "I21", r"P1 git apply --check exit 0[\s\S]*P3 git apply --check exit 0"),
 ("ZIP 254581 bytes = B before execution (I21)", "I21", r"254581\nf9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc"),
 ("P3 3 files 3 insertions 3 deletions (I24)", "I24", r"3 files changed, 3 insertions\(\+\), 3 deletions\(-\)"),
 ("P3 conditions C2-C4 (I24)", "I24", r"equals B: YES[\s\S]*C3 git apply --check exit 0[\s\S]*C4 tree clean before: 0 lines"),
 ("P3 A count 1 -> 0 in each of three files (I24)", "I24", r"A in old: 1 A in new: 0 B in new: 1[\s\S]*A in old: 1 A in new: 0 B in new: 1[\s\S]*A in old: 1 A in new: 0 B in new: 1"),
 ("rebuild changed only the erratum, 6/6 lines (I25)", "I25", r"1 file changed, 6 insertions\(\+\), 6 deletions\(-\)"),
 ("P1 amend left the tree unchanged (I27)", "I27", r"f3995bdc9c484bb43119440603c6cbe1aa70fb03 parent 51564e34c18e5cc908cf517000ebc9bd41eaf194; tree unchanged: YES"),
 ("push notice 7 vulnerabilities (3 critical, 4 high) (I26)", "I26", r"7 vulnerabilities .*\(3 critical, 4 high\)"),
 ("I28 time 14:14Z", "I28", r"started-utc: 2026-11-01T14:14:03Z"),
 ("I21 time 15:15Z", "I21", r"started-utc: 2026-10-31T15:15:53Z"),
]
for label, eid, rx in claims:
    found = re.search(rx, ev(eid)) is not None
    print(f"   claim {'FOUND ' if found else 'MISSING'} {label}")
    if not found: fail(f"numeric claim not found in {eid}: {label}")
# prose claims that must be present in the report exactly as numbers
for s in ("+57/−3", "54 lines", "3 ahead and 96 behind", "7 vulnerabilities (3 critical, 4 high)", "254,581", "(0 matches)"):
    if s not in txt: fail(f"expected figure not in report: {s}")
# statements that must NOT be in the report because they have no source in this run
for s in ("about fifty", "checks b, c, d, e, g", "Severity (reviewer)", "MAJOR", "MINOR"):
    if s in txt: fail(f"unsourced phrase present: {s}")
print("RESULT:", "ALL MECHANICAL CHECKS PASSED" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
