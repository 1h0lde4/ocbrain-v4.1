#!/usr/bin/env python3
"""Mechanical check of Addendum 3 (read-only).
usage: python3 -I check_addendum3.py ADDENDUM EVIDENCE_DIR REPO BUNDLE_ZIP REV2_PATCH P1D_PATCH ATTACHMENT ADD1 ADD2 REPORT
"""
import re, sys, os, subprocess, hashlib, zipfile
add, evdir, repo, bundle, rev2, p1d, att, add1, add2, report = sys.argv[1:]
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
for needle in ("F7", "F8", "OPEN"):
    if needle not in txt: fail(f"missing {needle}")
have = {f.split("_")[0] for f in os.listdir(evdir) if re.match(r"^[A-I]\d\d_", f)}
cited = {c for c in re.findall(r"\b([A-I]\d\d)\b", txt) if c[0] in "ABCDEFGHI"}
miss = sorted(cited - have - {"I49", "I50"}); print("ids cited:", sorted(cited), "| missing files:", miss)
if miss: fail("cited evidence id without file")
evtext = "".join(open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read() for f in os.listdir(evdir) if os.path.isfile(os.path.join(evdir, f)))
for f in (rev2, p1d, att, add1, add2, report): evtext += open(f, encoding="utf-8", errors="replace").read()
def ev(n):
    for f in os.listdir(evdir):
        if f.startswith(n + "_"): return open(os.path.join(evdir, f), encoding="utf-8", errors="replace").read()
    return ""
f40 = sorted(set(re.findall(r"\b[0-9a-f]{40}\b", txt)))
unres = [s for s in f40 if git("cat-file", "-t", s)[0] != 0 and s not in evtext]; print("40-hex ids:", len(f40), "| unresolved:", unres)
if unres: fail("unresolved 40-hex")
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
deliv = {sha(f) for f in (bundle, rev2, p1d, att, add1, add2, report)}
f64 = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", txt))); nf = [s for s in f64 if s not in evtext and s not in deliv]
print("64-hex digests:", len(f64), "| not backed:", nf)
if nf: fail("digest not backed")
for n, f in (("bundle", bundle), ("P1d rev2", rev2), ("attachment", att), ("addendum1", add1), ("addendum2", add2), ("report", report)):
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
 ("I44 P1d has no is-ancestor, no diff-tree, no cat-file -e", "I44", r"merge-base/is-ancestor occurrences in P1d: 1   diff-tree occurrences: 0[\s\S]*cat-file -e occurrences: 0; 'live' occurrences in added lines: 0"),
 ("I44 P1d cumulative diff only", "I44", r"git diff --name-only 51564e34c18e5cc908cf517000ebc9bd41eaf194 origin/docs/g4-fts-errata-handoff-oct2026"),
 ("I44 P1d section 7 used --oneline", "I44", r"git log --diff-filter=A --oneline -- handoff\.md"),
 ("I44 P3 committer date 2026-11-01T14:12:28", "I44", r"9407db5a01acea9684f158caa8107fb71611a102 committer-date=2026-11-01T14:12:28\+00:00"),
 ("I44 post-repair state: 556 tracked, 0 / 0 / 0", "I44", r"tracked files in HEAD: 556; status lines: 0; 'git diff HEAD --stat' lines: 0; staged-vs-HEAD lines: 0"),
 ("I44 incident counts 44 ?? and 556 D", "I44", r"44 \?\?\n\s+556 D"),
 ("I45 11 scenarios, 0 mismatches, 5 false PASS", "I45", r"scenarios: 11; mismatches with expectation: 0; scenarios where P1d as delivered would give a false PASS: 5"),
 ("I45 s01 block PASS, P1d-orig FAIL", "I45", r"s01_original_transfer_and_handoff\s+PASS\s+PASS\s+FAIL"),
 ("I45 s05 block FAIL, P1d-orig PASS", "I45", r"s05_other_file_changed_then_reverted\s+FAIL\s+FAIL\s+PASS"),
 ("I45 s06 false PASS", "I45", r"s06_handoff_commit_local_not_ancestor\s+FAIL\s+FAIL\s+PASS"),
 ("I45 s07 false PASS", "I45", r"s07_remote_moves_after_fetch\s+FAIL\s+FAIL\s+PASS"),
 ("I45 s08 false PASS", "I45", r"s08_merge_commit_in_sequence\s+FAIL\s+FAIL\s+PASS"),
 ("I45 s09 false PASS", "I45", r"s09_handoff_file_missing_from_tree\s+FAIL\s+FAIL\s+PASS"),
 ("I45 s10 and s11 FAIL/FAIL/FAIL", "I45", r"s10_wrong_expected_parent_of_handoff\s+FAIL\s+FAIL\s+FAIL[\s\S]*s11_remote_branch_missing\s+FAIL\s+FAIL\s+FAIL"),
 ("I46 apply-check exit 0, numstat 33 5", "I46", r"P1d-rev2 git apply --check exit 0[\s\S]*33\t5\thandoff\.md"),
 ("I46 19 headings, CR 0", "I46", r"proposed file: headings 19; lines 575; CR 0"),
 ("I46 block identical, 25 lines", "I46", r"IDENTICAL \(non-blank lines\)\nblock lines tested: 25; extracted: 25"),
 ("I47 unmodified block PASS twice, same block sha", "I47", r"block sha256 \(as extracted from the proposed patch\): 014fad4792ab082448fc48f3328c49ceb67bf551261ac828cb4a81527336519f[\s\S]*PASS: handoff commit 51564e34c18e5cc908cf517000ebc9bd41eaf194[\s\S]*exit: 0[\s\S]*fresh clone from the remote: OK[\s\S]*PASS: handoff commit 51564e34c18e5cc908cf517000ebc9bd41eaf194[\s\S]*exit: 0"),
 ("I47 state unchanged: HEAD = remote tip, status 0", "I47", r"HEAD d963daa502de4220411d0d0c2f19f67b3ec2682b; status lines 0; remote tip d963daa502de4220411d0d0c2f19f67b3ec2682b"),
 ("I48 versions git 2.43.0 and bash 5.2.21", "I48", r"git version 2\.43\.0\nGNU bash, version 5\.2\.21"),
 ("I36 last clean status 23:51:16Z", "I36", r"started-utc: 2026-11-01T23:51:16Z"),
 ("I41 pre-repair 556 D and 44 ??", "I41", r"44 \?\?\n\s+556 D "),
]
for label, eid, rx in claims:
    f = re.search(rx, ev(eid)) is not None; print(f"   claim {'FOUND ' if f else 'MISSING'} {label}")
    if not f: fail(f"claim not found in {eid}: {label}")
# the only merge-base in P1d is the pre-existing step 3 line
mb = [l for l in open(p1d, encoding="utf-8").read().splitlines() if "merge-base" in l]
print("merge-base lines in P1d:", [l[:70] for l in mb])
if len(mb) != 1 or "git merge-base origin/main HEAD" not in mb[0]: fail("P1d merge-base line is not the existing step 3")
# the block inside the proposed patch is the tested block, byte for byte (sha256), and matches the cited hash
rv = open(rev2, encoding="utf-8").read().splitlines()
blk = [l[4:] for l in rv if l.startswith("+   ") and not l.startswith("+   ```")]
bsha = hashlib.sha256(("\n".join(blk) + "\n").encode()).hexdigest()
tested = hashlib.sha256(zipfile.ZipFile(bundle).read("tested_block/verify_block.sh")).hexdigest()
print("block sha256 from the proposed patch:", bsha, "| tested block in the bundle:", tested)
if bsha != tested: fail("block in the proposed patch is not the tested block")
if bsha not in txt: fail("block hash not cited")
# live state
rc, out = git("ls-remote", "origin", "refs/heads/docs/g4-fts-errata-handoff-oct2026"); print("live REV2 tip:", out.strip())
if not out.startswith("d963daa502de4220411d0d0c2f19f67b3ec2682b"): fail("REV2 remote tip moved or differs")
rc, out = git("status", "--porcelain"); print("clone status lines:", len(out.splitlines()))
if out.strip(): fail("clone is not clean")
print("RESULT:", "ALL MECHANICAL CHECKS PASSED" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
