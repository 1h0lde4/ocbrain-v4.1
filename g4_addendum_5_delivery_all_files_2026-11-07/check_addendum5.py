#!/usr/bin/env python3
"""Mechanical check of Addendum 5 (read-only), with the hardened status rules of check_addendum4_v2.py.
usage: python3 -I check_addendum5.py ADDENDUM5 EVIDENCE_DIR REPO BUNDLE5 PACKAGE_ZIP ADD4 ADD4_DELIVERY_ZIP V2_CHECKER MUTATION_SCRIPT
"""
import re, sys, os, subprocess, hashlib, zipfile, io
add, evdir, repo, bundle, pkg, add4, add4zip, v2, mut = sys.argv[1:]
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
outside_code = re.sub(r"`[^`\n]*`", "", txt)   # template-token scan outside code spans (file names such as ..._REVIEW_AND_... are legitimate)
for tok in ("PLACEHOLDER", "REVIEW_", "<FILL", "TODO", "TBD", "XXX", "lorem"):
    if tok in outside_code: fail(f"token present: {tok}")
if "§" in txt: fail("section sign present")
nums = [int(m.group(1)) for h in lines if (m := re.match(r"## (\d+)\. ", h))]; print("level-2 headings:", nums)
if nums != list(range(1, 9)): fail("section numbers not 1..8")
want = "G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
ne = [l for l in lines if l.strip()]
if ne[-1] != want: fail("final line")
if "**Governing statuses, unchanged:** " + want not in txt: fail("governing-status line missing")
# hardened status rules (same as check_addendum4_v2.py)
if txt.count("**Governing statuses, unchanged:**") != 1: fail("governing line must occur exactly once")
if txt.count(want) != 2: fail(f"status sentence must occur exactly twice (found {txt.count(want)})")
BAD = [
 (r"\bG4\b[^.\n|]{0,40}\b(CLOSED|RESOLVED|FIXED|VERIFIED|CLEARED|DONE|COMPLETED?|PASSED?)\b", "G4 status other than OPEN"),
 (r"\bG[5-8]\b(?:\s*[–-]\s*G?[5-8])?[^.\n|;]{0,30}\b(RELEASED|UNHELD|OPEN|ACTIVE|STARTED|AUTHORIZED|UNBLOCKED)\b", "G5-G8 status other than HELD"),
 (r"(?i)freeze readiness[^.\n|;]{0,30}\b(?<!NOT )(DECLARED|READY|ACHIEVED|GRANTED)\b", "freeze readiness declared"),
 (r"(?i)\bfreeze[- ]ready\b", "freeze-ready"),
 (r"(?i)(?<!no )(?<!not )\bimplementation (is |has been |now )?(authorized|approved)\b", "implementation authorized"),
]
n_bad = 0
for rx, what in BAD:
    for m in re.finditer(rx, txt): n_bad += 1; fail(f"conflicting status text ({what}): {txt[max(0, m.start()-20):m.end()+10]!r}")
print("hardened status rules: conflicting matches:", n_bad)
# gates
in_g = False; st = []
for l in lines:
    if l.startswith("| Gate | Status"): in_g = True; continue
    if in_g:
        if not l.startswith("|"): break
        c = [x.strip() for x in l.strip("|").split("|")]
        if c and not set(c[0]) <= set("-"): st.append((c[0].strip("*"), c[1].strip("*")))
for g, s in st: print(f"   {s:8s} {g[:90]}")
if [g for g, s in st if s not in {"PASS", "FAIL", "BLOCKED", "NOT RUN"}]: fail("status word not allowed")
non = [g for g, s in st if not g.startswith("Overall") and s != "PASS"]; ov = [s for g, s in st if g.startswith("Overall")]
if len(ov) != 1: fail("one overall row required")
elif non and ov[0] == "PASS": fail("overall PASS with a non-PASS gate")
elif non and ov[0] != "BLOCKED": fail("this addendum's overall must be BLOCKED (a gate is BLOCKED)")
print("non-PASS gates:", len(non), "| overall:", ov)
for needle in ("F13", "SELF-REVIEW ONLY", "PROPOSED", "not VERIFIED", "SUBSTANTIVE FINDINGS"):
    if needle not in txt: fail(f"missing {needle}")
# ids and hashes
have = {f.split("_")[0] for f in os.listdir(evdir) if re.match(r"^[A-I]\d\d_", f)}
cited = set(re.findall(r"\b([HI]\d\d)\b", txt)); miss = sorted(cited - have - {"I73", "I74", "I75"}); print("ids cited:", sorted(cited), "| missing:", miss)
if miss: fail("cited evidence id without file")
evtext = "".join(open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read() for f in os.listdir(evdir) if os.path.isfile(os.path.join(evdir, f))) + open(add4, encoding="utf-8").read()
f40 = sorted(set(re.findall(r"\b[0-9a-f]{40}\b", txt))); unres = [s for s in f40 if git("cat-file", "-t", s)[0] != 0 and s not in evtext]
print("40-hex ids:", len(f40), "| unresolved:", unres)
if unres: fail("unresolved 40-hex")
deliv = {sha(f) for f in (bundle, pkg, add4, add4zip, v2, mut)}
f64 = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", txt))); nf = [s for s in f64 if s not in evtext and s not in deliv]; print("64-hex digests:", len(f64), "| not backed:", nf)
if nf: fail("digest not backed")
for n, f in (("bundle 5", bundle), ("package zip", pkg), ("addendum 4", add4), ("addendum 4 delivery zip", add4zip)):
    print(f"   {n}: {sha(f)} cited: {sha(f) in txt}")
    if sha(f) not in txt: fail(f"{n} hash not cited or stale")
pre = sorted(set(re.findall(r"(?<!…)\b([0-9a-f]{8,16})…", txt)))
alld = set(re.findall(r"\b[0-9a-f]{64}\b", evtext)) | set(re.findall(r"\b[0-9a-f]{40}\b", evtext)) | deliv
unp = [p for p in pre if not any(d.startswith(p) for d in alld) and git("cat-file", "-t", p)[0] != 0]; print("abbreviated hex:", pre, "| unsourced:", unp)
if unp: fail("abbreviated id with no source")
# bundle 5
z = zipfile.ZipFile(bundle); man = z.read("MANIFEST.sha256").decode().splitlines(); bad = sum(hashlib.sha256(z.read(l.split(None, 1)[1].strip())).hexdigest() != l.split()[0] for l in man)
print("bundle 5 entries:", len(man), "| mismatches:", bad)
if bad: fail("bundle 5 manifest")
for n in z.namelist():
    if n.startswith("evidence/") and z.read(n) != open(os.path.join(evdir, os.path.basename(n)), "rb").read(): fail(f"bundle evidence differs: {n}")
if z.read("scripts/check_addendum4_v2.py") != open(v2, "rb").read() or z.read("scripts/check_status_mutations.py") != open(mut, "rb").read(): fail("scripts in bundle differ from delivered scripts")
# package zip
pz = zipfile.ZipFile(pkg); print("package zip integrity:", pz.testzip() or "OK", "| entries:", len(pz.namelist()))
if pz.testzip() or len(pz.namelist()) != 8: fail("package zip")
sums = pz.read("review_package/SHA256SUMS.txt").decode().splitlines(); pbad = 0
for l in sums:
    h, p = l.split(None, 1); p = p.strip().lstrip("./")
    if hashlib.sha256(pz.read("review_package/" + p)).hexdigest() != h: pbad += 1
print("package inner checksum list:", len(sums), "files | mismatches:", pbad)
if pbad or len(sums) != 7: fail("package inner checksums")
brief = pz.read("review_package/README_FIRST_REVIEW_BRIEF.md").decode()
for pat in ("20 of 20", "I60", "I61", "I59", "e1ccd6a7", "mismatches"):
    if pat in brief: fail(f"brief carries a result marker: {pat}")
if hashlib.sha256(pz.read("review_package/rev3/verify_block_rev3.sh")).hexdigest() != "e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53": fail("package block is not the tested block")
print("package block sha256 is the tested block: True")
# mutation table in the addendum == I69
def p69():
    d = {}
    for l in ev("I69").splitlines():
        m = re.match(r"^(M\d)\b.*\b(ACCEPTED|REJECTED)(?: \*)?\s+(ACCEPTED|REJECTED)\b", l)
        if m: d[m.group(1)] = (m.group(2), m.group(3))
    return d
i69 = p69(); tab = {}
for l in lines:
    m = re.match(r"^\| (M\d) .*\| (ACCEPTED|REJECTED)(?: \(wrong\))? \| (ACCEPTED|REJECTED) \|$", l)
    if m: tab[m.group(1)] = (m.group(2), m.group(3))
print("mutants in I69:", len(i69), "| in the addendum table:", len(tab), "| identical:", i69 == tab)
if len(i69) != 10 or i69 != tab: fail("mutation table differs from I69")
rej1 = sum(1 for k, v in i69.items() if k != "M0" and v[0] == "REJECTED"); rej2 = sum(1 for k, v in i69.items() if k != "M0" and v[1] == "REJECTED")
print("rejected by v1:", rej1, "| by v2:", rej2, "| v1 accepted:", 9 - rej1)
if (rej1, rej2) != (2, 9) or i69["M0"] != ("ACCEPTED", "ACCEPTED"): fail("mutation totals differ from the text (2, 9, control accepted by both)")
for k, v in i69.items():
    if (k != "M0" and v[0] == "ACCEPTED") != ("(wrong)" in next(l for l in lines if l.startswith(f"| {k} ")).split("|")[2]): fail(f"wrong-marker for {k} does not match I69")
# claims in the evidence
claims = [
 ("I57 launches 1 and 2: 72 and 41 entries, no reports", "I57", r"== review3: entries=72; REPORT\.md present: no[\s\S]*== review3b: entries=41; REPORT\.md present: no"),
 ("I68 launch 3: 3 entries, no report", "I68", r"== review3c: exists; entries=3; REPORT\.md present: no"),
 ("I68 launch 4: report file present", "I68", r"== review3d: exists; entries=1; REPORT\.md present: yes"),
 ("I72 launch 4 report: 51 bytes, status line and heading, 0 findings lines", "I72", r"\n51\nSTATUS: IN PROGRESS\n\n# Review of verify_block_rev3\n\[end of file\][\s\S]*findings lines \([^)]*\): 0"),
 ("I69 totals", "I69", r"mutants that must be rejected: 9; rejected by v1: 2; rejected by v2: 9"),
 ("I70 package integrity and checksums", "I70", r"integrity: OK\nentries: 8\n(?:  \./.*: OK\n){7}"),
 ("I70 block, patch, rev2 block equalities", "I70", r"block == delivered block \(sha256 e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53\)\npatch == delivered patch\nrev2 block == the revision 2 block of Addendum 3"),
 ("I70 patch applies to the base", "I70", r"git apply --check exit 0 on base/handoff\.md in a scratch repository \(not applied\)"),
 ("I70 base equals the pushed handoff.md", "I70", r"base/handoff\.md == handoff\.md of the pushed REV2 tip: yes"),
 ("I70 independence patterns all zero", "I70", r"'20 of 20':\s+0\n[\s\S]*'I60':\s+0\n[\s\S]*'I61':\s+0\n[\s\S]*'I59':\s+0\n[\s\S]*'e1ccd6a7':\s+0\n[\s\S]*'false PASS of revision 2':\s+0\n[\s\S]*'mismatches':\s+0"),
 ("I70 no secrets", "I70", r"secrets scan[^\n]*: 0 hits"),
 ("I71 PR #90 unchanged", "I71", r"PR #90: state=open draft=true head=9407db5a01acea9684f158caa8107fb71611a102 commits=3 changed_files=7 base=main"),
 ("I71 state", "I71", r"remote docs/g4-fts-errata-handoff-oct2026: d963daa502de4220411d0d0c2f19f67b3ec2682b[\s\S]*working clone HEAD: d963daa502de4220411d0d0c2f19f67b3ec2682b; status lines: 0"),
]
for label, eid, rx in claims:
    f = re.search(rx, ev(eid)) is not None; print(f"   claim {'FOUND ' if f else 'MISSING'} {label}")
    if not f: fail(f"claim not found in {eid}: {label}")
rc, out = git("ls-remote", "origin", "refs/heads/docs/g4-fts-errata-handoff-oct2026"); print("live REV2 tip:", out.split()[0] if out else "none")
if not out.startswith("d963daa502de4220411d0d0c2f19f67b3ec2682b"): fail("REV2 tip differs")
rc, out = git("ls-remote", "origin", "refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026")
if not out.startswith("9407db5a01acea9684f158caa8107fb71611a102"): fail("REV3 tip differs")
rc, out = git("ls-remote", "origin", "refs/heads/main")
if not out.startswith("2491ae469edd6ef1267a14604c4f8f40d698f7ea"): fail("main differs")
rc, out = git("status", "--porcelain"); print("clone status lines:", len(out.splitlines()))
if out.strip(): fail("clone not clean")
print("RESULT:", "ALL MECHANICAL CHECKS PASSED" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
