#!/usr/bin/env python3
"""Mechanical check of Addendum 2 (read-only).
usage: python3 -I check_addendum2.py ADDENDUM EVIDENCE_DIR REPO BUNDLE_ZIP P1D P1C ATTACHMENT ADD1 REPORT
"""
import re, sys, os, subprocess, hashlib, zipfile
add, evdir, repo, bundle, p1d, p1c, att, add1, report = sys.argv[1:]
txt = open(add, encoding="utf-8").read(); lines = txt.splitlines(); ok = True
def fail(m):
    global ok; ok = False; print("FAIL:", m)
def git(*a):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True); return r.returncode, r.stdout
for tok in ("PLACEHOLDER", "REVIEW_", "<FILL", "TODO", "TBD", "XXX", "lorem"):
    if tok in txt: fail(f"token present: {tok}")
nums = [int(m.group(1)) for h in lines if (m := re.match(r"## (\d+)\. ", h))]
print("level-2 headings:", nums)
if nums != list(range(1, 8)): fail(f"section numbers not 1..7: {nums}")
refs = sorted({int(x) for x in re.findall(r"§(\d+)", txt)}); print("section references:", refs)
if [r for r in refs if r not in nums]: fail("reference number outside 1..7")
want = "G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
ne = [l for l in lines if l.strip()]; print("last non-empty line ok:", ne[-1] == want)
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
for needle in ("F7", "OPEN"):
    if needle not in txt: fail(f"missing {needle}")
have = {f.split("_")[0] for f in os.listdir(evdir) if re.match(r"^[A-I]\d\d_", f)}
cited = {c for c in re.findall(r"\b([A-I]\d\d)\b", txt) if c[0] in "ABCDEFGHI"}
miss = sorted(cited - have - {"I43"}); print("ids cited:", sorted(cited), "| missing files:", miss)
if miss: fail("cited evidence id without file")
evtext = "".join(open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read() for f in os.listdir(evdir) if os.path.isfile(os.path.join(evdir, f)))
for f in (p1d, p1c, att, add1, report): evtext += open(f, encoding="utf-8", errors="replace").read()
def ev(n):
    for f in os.listdir(evdir):
        if f.startswith(n + "_"): return open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read()
    return ""
f40 = sorted(set(re.findall(r"\b[0-9a-f]{40}\b", txt)))
unres = [s for s in f40 if git("cat-file", "-t", s)[0] != 0 and s not in evtext]; print("40-hex ids:", len(f40), "| unresolved:", unres)
if unres: fail("unresolved 40-hex")
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
deliv = {sha(f) for f in (bundle, p1d, p1c, att, add1, report)}
f64 = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", txt))); nf = [s for s in f64 if s not in evtext and s not in deliv]
print("64-hex digests:", len(f64), "| not backed:", nf)
if nf: fail("digest not backed")
for n, f in (("bundle", bundle), ("P1d", p1d), ("attachment", att), ("addendum1", add1), ("report", report)):
    print(f"   {n}: {sha(f)} cited: {sha(f) in txt}")
    if sha(f) not in txt: fail(f"{n} hash not cited or stale")
if str(os.path.getsize(att)) not in txt.replace(",", ""): fail("attachment size not cited")
print("attachment bytes:", os.path.getsize(att))
alld = set(re.findall(r"\b[0-9a-f]{64}\b", evtext)) | deliv | set(re.findall(r"\b[0-9a-f]{40}\b", evtext))
pre = sorted(set(re.findall(r"(?<!…)\b([0-9a-f]{8,16})…", txt)))
unp = [p for p in pre if not any(d.startswith(p) for d in alld) and git("cat-file", "-t", p)[0] != 0]
print("abbreviated hex ids:", len(pre), "| not a prefix of any id seen:", unp)
if unp: fail("abbreviated id with no source")
z = zipfile.ZipFile(bundle); man = z.read("MANIFEST.sha256").decode().splitlines(); bad = 0
for l in man:
    h, p = l.split(None, 1)
    if hashlib.sha256(z.read(p.strip().lstrip("./"))).hexdigest() != h: bad += 1
names = {n for n in z.namelist() if not n.endswith("/")}; listed = {l.split(None, 1)[1].strip().lstrip("./") for l in man}
print("bundle manifest entries:", len(man), "| mismatches:", bad, "| unlisted:", sorted(names - listed - {"MANIFEST.sha256"}))
if bad or (names - listed - {"MANIFEST.sha256"}): fail("bundle manifest")
claims = [
 ("I39 history: tip parent 51564e3, handoff commit parent eca2b96", "I39", r"d963daa parent=51564e3[\s\S]*51564e3 parent=eca2b96"),
 ("I39 step 2 text line 526 and rule line 545", "I39", r"526:2\. Verify the transfer commit[\s\S]*545:If step 2 of §18 fails"),
 ("I39 literal section-7 lookup prints d963daa, diff-filter=A prints 51564e3", "I39", r"git log --oneline -1 -- handoff\.md  ->  d963daa[\s\S]*diff-filter=A --oneline -- handoff\.md  ->  51564e3"),
 ("I39 tip parent 51564e34 vs expected eca2b96", "I39", r"parent of the tip: 51564e34c18e5cc908cf517000ebc9bd41eaf194  \(section 18 step 2 expects eca2b96521fba8cf792ea16a58be997e4f949356\)"),
 ("I39 P1c has a single hunk @@ -504,9 +504,9", "I39", r"3:@@ -504,9 \+504,9 @@"),
 ("I39 PR #90 3/96, 7 files", "I39", r"ahead_by=3 behind_by=96[\s\S]*"),
 ("I39 PR #90 commits=3 changed_files=7", "I39", r"commits=3 changed_files=7"),
 ("I39 28 files on main, 7 PR files, overlap 0", "I39", r"since the shared base f13bfde: 28\nPR #90 files: 7\noverlap count: 0"),
 ("I39 DEBT-042 lines 15 and 68, OPEN", "I39", r"15:\*\*Last synchronized:[\s\S]*68:\| DEBT-042 \| Memory[\s\S]*OPEN, reproduced, not fixed"),
 ("I38 first run: paths unset (No such file)", "I38", r"/a5/proposed_diffs/P1c_handoff_review_wording_PROPOSED\.patch: No such file or directory"),
 ("I40 apply-check exit 0, numstat 5 5", "I40", r"P1d git apply --check exit 0[\s\S]*5\t5\thandoff\.md"),
 ("I40 19 headings 547 lines CR 0", "I40", r"proposed file: headings 19; lines 547; CR 0"),
 ("I40 stray status count 600", "I40", r"HEAD / status / remote tip\nd963daa502de4220411d0d0c2f19f67b3ec2682b\n600\n"),
 ("I41 index restored, 0 lines, 0 missing, blobs equal", "I41", r"read-tree HEAD exit 0[\s\S]*status lines: 0[\s\S]*tracked files missing from the working tree: 0[\s\S]*f3434b71516445856e106b5e12d48801b643d057 f3434b71516445856e106b5e12d48801b643d057"),
 ("I42 simulation commit 8c15739a and checks", "I42", r"8c15739ad3e3792008b5bb0fd795e17a09889b62[\s\S]*: OK\nhandoff commit is an ancestor of the simulated tip: YES[\s\S]*paths changed after the handoff commit \(must be only handoff\.md\):\nhandoff\.md"),
 ("I42 hash lookup returns 51564e3", "I42", r"section 7 lookup by hash: 51564e3"),
 ("I42 nothing real changed", "I42", r"real status lines: 0; HEAD d963daa502de4220411d0d0c2f19f67b3ec2682b; remote tip d963daa502de4220411d0d0c2f19f67b3ec2682b"),
]
for label, eid, rx in claims:
    f = re.search(rx, ev(eid)) is not None; print(f"   claim {'FOUND ' if f else 'MISSING'} {label}")
    if not f: fail(f"claim not found in {eid}: {label}")
# line numbers cited for the pushed file, and P1c hunks inside the entry
rc, body = git("show", "origin/docs/g4-fts-errata-handoff-oct2026:handoff.md"); hl = body.split("\n")
print("line 359 starts:", hl[358][:20], "| line 526 starts:", hl[525][:30], "| line 545 starts:", hl[544][:30])
if not hl[358].startswith("- Handoff commit:"): fail("line 359 is not the handoff-commit line")
if not hl[525].startswith("2. Verify the transfer commit"): fail("line 526 is not step 2")
if not hl[544].startswith("If step 2 of §18 fails"): fail("line 545 is not the rule")
start = next(i for i, l in enumerate(hl, 1) if l.startswith("- **Related documents and earlier revision")); end = next(i for i, l in enumerate(hl, 1) if "*Not decided by this entry:*" in l)
ch = []; old_ln = 0
for l in open(p1c, encoding="utf-8").read().splitlines():
    m = re.match(r"@@ -(\d+),\d+ \+\d+,\d+ @@", l)
    if m: old_ln = int(m.group(1)); continue
    if l.startswith(("---", "+++")) or not old_ln: continue
    if l.startswith("-"): ch.append(old_ln); old_ln += 1
    elif l.startswith("+"): pass
    else: old_ln += 1
print("entry lines", start, "-", end, "| P1c changed old lines:", ch)
if not ch or not all(start <= n <= end for n in ch): fail("P1c changes a line outside the entry")
rc, out = git("ls-remote", "origin", "refs/heads/docs/g4-fts-errata-handoff-oct2026"); print("live REV2 tip:", out.strip())
if not out.startswith("d963daa502de4220411d0d0c2f19f67b3ec2682b"): fail("REV2 remote tip moved or differs")
print("RESULT:", "ALL MECHANICAL CHECKS PASSED" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
