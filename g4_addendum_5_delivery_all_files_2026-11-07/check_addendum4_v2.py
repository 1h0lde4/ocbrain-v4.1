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
# ---- v2: status-text hardening. Rejects incorrect, ambiguous, duplicate or conflicting governing-status text anywhere in the addendum.
gov_n = txt.count("**Governing statuses, unchanged:**")
if gov_n != 1: fail(f"v2: the governing-status line must occur exactly once (found {gov_n})")
if txt.count(want) != 2: fail(f"v2: the exact status sentence must occur exactly twice, in the governing line and as the final line (found {txt.count(want)})")
BAD = [
 (r"\bG4\b[^.\n|]{0,40}\b(CLOSED|RESOLVED|FIXED|VERIFIED|CLEARED|DONE|COMPLETED?|PASSED?)\b", "a G4 status other than OPEN"),
 (r"\bG[5-8]\b(?:\s*[–-]\s*G?[5-8])?[^.\n|;]{0,30}\b(RELEASED|UNHELD|OPEN|ACTIVE|STARTED|AUTHORIZED|UNBLOCKED)\b", "a G5-G8 status other than HELD"),
 (r"(?i)freeze readiness[^.\n|;]{0,30}\b(?<!NOT )(DECLARED|READY|ACHIEVED|GRANTED)\b", "freeze readiness declared"),
 (r"(?i)\bfreeze[- ]ready\b", "freeze-ready"),
 (r"(?i)(?<!no )(?<!not )\bimplementation (is |has been |now )?(authorized|approved)\b", "implementation authorized"),
]
for rx, what in BAD:
    for m in re.finditer(rx, txt):
        fail(f"v2: conflicting status text ({what}): ...{txt[max(0, m.start()-20):m.end()+10]!r}")
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
# ---- evidence ids
have = {f.split("_")[0] for f in os.listdir(evdir) if re.match(r"^[A-I]\d\d_", f)}
cited = set(re.findall(r"\b([HI]\d\d)\b", txt)); miss = sorted(cited - have - {"I65", "I66", "I67"})
print("ids cited:", sorted(cited), "| missing files:", miss)
if miss: fail("cited evidence id without file")
evtext = "".join(open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read() for f in os.listdir(evdir) if os.path.isfile(os.path.join(evdir, f)))
for f in (rev3, rev2, att, add1, add2, add3, report): evtext += open(f, encoding="utf-8", errors="replace").read()
f40 = sorted(set(re.findall(r"\b[0-9a-f]{40}\b", txt)))
unres = [s for s in f40 if git("cat-file", "-t", s)[0] != 0 and s not in evtext]; print("40-hex ids:", len(f40), "| unresolved:", unres)
if unres: fail("unresolved 40-hex")
deliv = {sha(f) for f in (bundle, rev3, rev2, att, add1, add2, add3, report)}
f64 = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", txt))); nf = [s for s in f64 if s not in evtext and s not in deliv]
print("64-hex digests:", len(f64), "| not backed:", nf)
if nf: fail("digest not backed")
for n, f in (("bundle", bundle), ("P1d rev3", rev3), ("attachment", att), ("addendum1", add1), ("addendum2", add2), ("addendum3", add3), ("report", report)):
    print(f"   {n}: {sha(f)} cited: {sha(f) in txt}")
    if sha(f) not in txt: fail(f"{n} hash not cited or stale")
if "9,007" not in txt or os.path.getsize(att) != 9007: fail("attachment size not cited or changed")
alld = set(re.findall(r"\b[0-9a-f]{64}\b", evtext)) | deliv | set(re.findall(r"\b[0-9a-f]{40}\b", evtext))
pre = sorted(set(re.findall(r"(?<!…)\b([0-9a-f]{8,16})…", txt)))
unp = [p for p in pre if not any(d.startswith(p) for d in alld) and git("cat-file", "-t", p)[0] != 0]
print("abbreviated hex ids:", pre, "| not a prefix of any id seen:", unp)
if unp: fail("abbreviated id with no source")
# ---- bundle manifest
z = zipfile.ZipFile(bundle); man = z.read("MANIFEST.sha256").decode().splitlines(); bad = 0
for l in man:
    h, p = l.split(None, 1)
    if hashlib.sha256(z.read(p.strip())).hexdigest() != h: bad += 1
names = {n for n in z.namelist() if not n.endswith("/")}; listed = {l.split(None, 1)[1].strip() for l in man}
print("bundle manifest entries:", len(man), "| mismatches:", bad, "| unlisted:", sorted(names - listed - {"MANIFEST.sha256"}))
if bad or (names - listed - {"MANIFEST.sha256"}): fail("bundle manifest")
# every evidence file in the bundle equals the file in the evidence dir
for n in z.namelist():
    if n.startswith("evidence/"):
        if z.read(n) != open(os.path.join(evdir, os.path.basename(n)), "rb").read(): fail(f"bundle evidence differs from evidence dir: {n}")
# ---- scenario table in the addendum == the table in I60 (parsed, not retyped)
def norm(x): return re.sub(r"\s*\((false|incidental)\)", "", x).strip()
i60 = {}
for l in ev("I60").splitlines():
    m = re.match(r"^(s\d\d)\s+(PASS|FAIL)\s+(PASS|FAIL)( \*)?\s+(PASS|FAIL)( \*)?", l)
    if m: i60[m.group(1)] = (m.group(2), m.group(3), m.group(5), bool(m.group(4)))
tab = {}
for l in lines:
    m = re.match(r"^\| (s\d\d) .*\| (PASS|FAIL) \| ([^|]+) \| ([^|]+) \|$", l)
    if m: tab[m.group(1)] = (m.group(2), norm(m.group(3)), norm(m.group(4)), "(false)" in m.group(3))
print("scenarios in I60:", len(i60), "| in the addendum table:", len(tab))
if len(i60) != 20 or len(tab) != 20: fail("scenario count is not 20")
for s in sorted(i60):
    a, b = i60[s], tab.get(s)
    same = b is not None and a[:3] == b[:3] and a[3] == b[3]
    if not same: fail(f"scenario row differs: {s} I60={a} addendum={b}")
print("scenario rows identical to I60:", all(i60.get(s, ())[:3] == tab.get(s, ("", "", "", ""))[:3] for s in i60))
fp2 = sum(1 for s in i60 if i60[s][0] == "FAIL" and i60[s][1] == "PASS"); fp3 = sum(1 for s in i60 if i60[s][0] == "FAIL" and i60[s][2] == "PASS")
print("false PASS rev2:", fp2, "rev3:", fp3)
if fp2 != 6 or fp3 != 0: fail("false-PASS counts do not match the text (6 and 0)")
# ---- patches
def hunks(p):
    t = open(p, encoding="utf-8").read(); parts = re.split(r"(?m)^(?=@@ )", t); return parts[1:]
h2, h3 = hunks(rev2), hunks(rev3); print("hunks rev2/rev3:", len(h2), len(h3))
if not (len(h2) == len(h3) == 3 and h2[0] == h3[0] and h2[1] == h3[1] and h2[2] != h3[2]): fail("rev3 differs from rev2 outside step 2 (hunks 1 and 2 must be equal, hunk 3 must differ)")
rc, _ = git("apply", "--check", rev3); print("git apply --check rev3 exit:", rc)
if rc != 0: fail("rev3 does not apply to the working tree")
rc, out = git("apply", "--numstat", rev3); print("numstat:", out.strip())
if out.split()[:3] != ["46", "5", "handoff.md"]: fail("numstat differs from 46/5")
rv = open(rev3, encoding="utf-8").read().splitlines(); inb = False; blk = []
for l in rv:
    if l == "+   ```bash": inb = True; continue
    if l == "+   ```": inb = False
    if inb: blk.append(l[4:])
bsha = hashlib.sha256(("\n".join(blk) + "\n").encode()).hexdigest()
tested = hashlib.sha256(z.read("tested_block/verify_block_rev3.sh")).hexdigest()
print("block sha256 from the rev3 patch:", bsha, "| tested block in the bundle:", tested, "| lines:", len(blk))
if bsha != tested or len(blk) != 38: fail("block in the patch is not the tested block")
if bsha not in txt: fail("block hash not cited")
if z.read("patches/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch") != open(rev3, "rb").read(): fail("patch in bundle differs from the delivered patch")
# ---- claims found in the evidence files
c53 = ev("I53").split("=== verify_block_rev3.sh")[0]
claims = [
 ("I51 candidate A: 20 scenarios, rev2 6 false PASS, rev3 0", "I51", r"scenarios: 20; rev2: mismatches 6 \(false PASS 6, false FAIL 0\); rev3: mismatches 0 \(false PASS 0, false FAIL 0\)"),
 ("I60 final: 20 scenarios, rev2 6 false PASS, rev3 0", "I60", r"scenarios: 20; rev2: mismatches 6 \(false PASS 6, false FAIL 0\); rev3: mismatches 0 \(false PASS 0, false FAIL 0\)"),
 ("I61 s12: rev2 one ls-remote call, tip advanced, change touches KNOWN_ISSUES.md", "I61", r"== rev2\ns12 ls-remote calls=1 remote tip now == advance commit: yes; advance commit touches: KNOWN_ISSUES\.md"),
 ("I61 s12: rev3 two calls", "I61", r"== rev3\ns12 ls-remote calls=2 remote tip now == advance commit: yes"),
 ("I61 s13 marker engaged", "I61", r"s13 ls-remote calls=1; marker lsr_fail_all present: yes"),
 ("I61 tree entries 120000 / 040000 / 100755", "I61", r"s14 remote tree entry for handoff\.md: 120000 blob[\s\S]*s15 remote tree entry for handoff\.md: 040000 tree[\s\S]*s19 remote tree entry for handoff\.md: 100755 blob"),
 ("I61 s15 rev2 failed only on path-list checks", "I61", r"== rev2 s15 \(why it already failed\):\nFAIL: handoff\.md was not added by the handoff commit"),
 ("I53 draft 1: 15 cases, 4 differ", "I53", r"=== verify_block_rev3_draft1\.sh[\s\S]*cases: 15; differing from expectation: 4"),
 ("I53 candidate A: 15 cases, 0 differ", "I53", r"=== verify_block_rev3\.sh[\s\S]*cases: 15; differing from expectation: 0"),
 ("I59 candidate A unit: 20 cases, 5 differ, 5 leak", "I59", r"=== verify_block_rev3_candidateA\.sh\n(?:  canonical.*\n){20}  cases: 20; differing from expectation: 5; cases whose output contained the dummy token: 5"),
 ("I59 final unit: 20 cases, 0 differ, 0 leak", "I59", r"=== verify_block_rev3\.sh\n(?:  canonical.*\n){20}  cases: 20; differing from expectation: 0; cases whose output contained the dummy token: 0"),
 ("I59 end to end: candidate A 2 of 3 leak", "I59", r"end-to-end runs: 3; runs whose output contained the dummy token: 2"),
 ("I59 end to end: final 0 of 3 leak", "I59", r"end-to-end runs: 3; runs whose output contained the dummy token: 0"),
 ("I62 apply-check, numstat 46 5, headings 19, CR 0", "I62", r"git apply --check exit 0 on the pushed tree \(not applied\)\n46\t5\thandoff\.md[\s\S]*proposed file: headings 19; lines 588; CR 0"),
 ("I62 two cmp identities", "I62", r"extracted_from_patch\.sh: BYTE-IDENTICAL[\s\S]*extracted_from_proposed_file\.sh: BYTE-IDENTICAL"),
 ("I62 patch sha", "I62", r"98468b11c2f88cfe6637f1a1f6ee88a089f60a3957a6cf6d1ea3d1522f7c2cb0"),
 ("I63 PASS in the working clone at 12:47:27Z", "I63", r"== A\. working clone[\s\S]*PASS at 2026-11-06T12:47:27Z: remote tip d963daa502de4220411d0d0c2f19f67b3ec2682b; handoff commit 51564e34c18e5cc908cf517000ebc9bd41eaf194[\s\S]*exit status: 0"),
 ("I63 PASS in the fresh clone at 12:47:29Z", "I63", r"== B\. fresh clone[\s\S]*origin = https://github\.com/1h0lde4/ocbrain-v4\.1[\s\S]*PASS at 2026-11-06T12:47:29Z[\s\S]*exit status: 0"),
 ("I63 four controls exit 1, zero PASS lines", "I63", r"C1 [^\n]*exit 1[^\n]*\n   PASS lines printed: 0\nC2 [^\n]*exit 1[^\n]*\n   PASS lines printed: 0\nC3 [^\n]*exit 1[^\n]*\n   PASS lines printed: 0\nC4 [^\n]*exit 1[^\n]*\n   PASS lines printed: 0"),
 ("I63 block sha equals tested file", "I63", r"block sha256: e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53  \(tested file: e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53\)"),
 ("I57 first attempt 72 entries, second 41, no reports", "I57", r"== review3: entries=72; REPORT\.md present: no; files with a line starting 'PASS at': 0[^\n]*\n== review3b: entries=41; REPORT\.md present: no; files with a line starting 'PASS at': 0"),
 ("I58 candidate A and final hashes", "I58", r"4423b51291334af718e72f3fd41489473895e491b7eb016015e4a9608ac28b83[\s\S]*e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53"),
 ("I56 PR #90 open draft 3 commits 7 files", "I56", r"PR #90: state=open draft=true head=9407db5a01acea9684f158caa8107fb71611a102 commits=3 changed_files=7 base=main"),
 ("I64 PR #90 unchanged", "I64", r"PR #90: state=open draft=true head=9407db5a01acea9684f158caa8107fb71611a102 commits=3 changed_files=7 base=main"),
 ("I64 state: HEAD = REV2 tip, status 0", "I64", r"remote docs/g4-fts-errata-handoff-oct2026: d963daa502de4220411d0d0c2f19f67b3ec2682b[\s\S]*working clone HEAD: d963daa502de4220411d0d0c2f19f67b3ec2682b; status lines: 0"),
 ("I64 versions", "I64", r"git version 2\.43\.0\nGNU bash, version 5\.2\.21"),
 ("I64 rev2 block hash and draft 1 hash", "I64", r"014fad4792ab082448fc48f3328c49ceb67bf551261ac828cb4a81527336519f  a7/verify_block\.sh\n80f6c77b80ca88a33f3a56e29af928f46998450434a87c56df6e0bfbb22a2055"),
 ("I55 candidate A real remote PASS twice", "I55", r"block sha256: 4423b51291334af718e72f3fd41489473895e491b7eb016015e4a9608ac28b83[\s\S]*PASS at[\s\S]*exit status: 0[\s\S]*PASS at[\s\S]*exit status: 0"),
 ("I54 candidate A patch sha", "I54", r"d07352beee3031b4dbf2f725be833896e9ad08c9205869a7027449c830cb7e10"),
]
for label, eid, rx in claims:
    f = re.search(rx, ev(eid)) is not None; print(f"   claim {'FOUND ' if f else 'MISSING'} {label}")
    if not f: fail(f"claim not found in {eid}: {label}")
n_leak53 = c53.count("LEAKS-TOKEN"); print("I53 draft 1 token leaks:", n_leak53)
if n_leak53 != 4: fail("I53 draft 1 leak count is not 4")
# ---- the superseded and the delivered files are marked
if "must not be applied" not in txt: fail("superseded patches not marked")
# ---- live state
rc, out = git("ls-remote", "origin", "refs/heads/docs/g4-fts-errata-handoff-oct2026"); print("live REV2 tip:", out.strip())
if not out.startswith("d963daa502de4220411d0d0c2f19f67b3ec2682b"): fail("REV2 remote tip moved or differs")
rc, out = git("ls-remote", "origin", "refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026"); print("live REV3 tip:", out.strip())
if not out.startswith("9407db5a01acea9684f158caa8107fb71611a102"): fail("REV3 remote tip moved or differs")
rc, out = git("status", "--porcelain"); print("clone status lines:", len(out.splitlines()))
if out.strip(): fail("clone is not clean")
print("RESULT:", "ALL MECHANICAL CHECKS PASSED" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
