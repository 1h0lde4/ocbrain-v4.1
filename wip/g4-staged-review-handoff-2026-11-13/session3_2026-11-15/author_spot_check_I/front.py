#!/usr/bin/env python3
"""Mechanical check of Addendum 4 (read-only).
usage: python3 -I check_addendum4.py ADDENDUM EVIDENCE_DIR REPO BUNDLE_ZIP REV3_PATCH REV2_PATCH ATTACHMENT ADD1 ADD2 ADD3 REPORT
"""
import re, sys, os, subprocess, hashlib, zipfile
add, evdir, repo, bundle, rev3, rev2, att, add1, add2, add3, report = sys.argv[1:]
txt = open(add, encoding="utf-8").read(); lines = txt.splitlines(); ok = True
def fail(m):
    global ok; ok = False; print("FAIL:", m)
def git(*a):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True); return r.returncode, r.stdout
def ev(n):
    for f in os.listdir(evdir):
        if f.startswith(n + "_"): return open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read()
    return ""
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
for tok in ("PLACEHOLDER", "REVIEW_", "<FILL", "TODO", "TBD", "XXX", "lorem"):
    if tok in txt: fail(f"token present: {tok}")
if "§" in txt: fail("section sign present (use 'section N')")
nums = [int(m.group(1)) for h in lines if (m := re.match(r"## (\d+)\. ", h))]
print("level-2 headings:", nums)
if nums != list(range(1, 9)): fail(f"section numbers not 1..8: {nums}")
want = "G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
ne = [l for l in lines if l.strip()]; print("last non-empty line ok:", ne[-1] == want)
if ne[-1] != want: fail("final line")
if "**Governing statuses, unchanged:** " + want not in txt: fail("governing-status line missing")
# ---- gate table
in_gate = False; st = []
for l in lines:
    if l.startswith("| Gate | Status"): in_gate = True; continue
    if in_gate:
        if not l.startswith("|"): break
        c = [x.strip() for x in l.strip("|").split("|")]
        if c and not set(c[0]) <= set("-"): st.append((c[0].strip("*"), c[1].strip("*"), l))
for g, s, _ in st: print(f"   {s:8s} {g}")
if [g for g, s, _ in st if s not in {"PASS", "FAIL", "BLOCKED", "NOT RUN"}]: fail("status word not allowed")
non = [g for g, s, _ in st if not g.startswith("Overall") and s != "PASS"]; ov = [(s, l) for g, s, l in st if g.startswith("Overall")]
if len(ov) != 1: fail("one overall row required")
elif non and ov[0][0] == "PASS": fail("overall PASS with a non-PASS gate")
elif not non and ov[0][0] != "PASS": fail("overall not PASS with all gates PASS")
elif "SELF-REVIEW ONLY" not in ov[0][1]: fail("overall row must say SELF-REVIEW ONLY")
print("non-PASS gates:", non, "| overall:", [s for s, _ in ov])
for needle in ("F7", "F8", "F9", "F10", "F11", "F12", "OPEN", "not VERIFIED", "not done"):
    if needle not in txt: fail(f"missing {needle}")
sys.exit(0 if ok else 1)
