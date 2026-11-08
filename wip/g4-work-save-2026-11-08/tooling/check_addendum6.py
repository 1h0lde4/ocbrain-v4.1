import hashlib, io, re, subprocess, sys, zipfile, glob, os
add, evdir, repo, bundle, add5, zip5 = sys.argv[1:7]
txt = open(add, encoding="utf-8").read(); lines = txt.split("\n"); bad = []
def fail(m): bad.append(m); print("FAIL:", m)
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
# ---- structure and governing statuses (hardened rules, as in v2)
nums = [int(m.group(1)) for h in lines if (m := re.match(r"## (\d+)\. ", h))]; print("level-2 headings:", nums)
if nums != list(range(1, 8)): fail(f"section numbers not 1..7: {nums}")
want = "G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED."
ne = [l for l in lines if l.strip()]; print("last non-empty line ok:", ne[-1] == want)
if ne[-1] != want: fail("final line")
if txt.count("**Governing statuses, unchanged:**") != 1: fail("governing-status line count")
if txt.count(want) != 2: fail(f"status sentence count {txt.count(want)}")
if "**Governing statuses, unchanged:** " + want + " No implementation authorized." not in txt: fail("governing line text")
BAD = [
 (r"\bG4\b[^.\n|]{0,40}\b(CLOSED|RESOLVED|FIXED|VERIFIED|CLEARED|DONE|COMPLETED?|PASSED?)\b", "a G4 status other than OPEN"),
 (r"\bG[5-8]\b(?:\s*[–-]\s*G?[5-8])?[^.\n|;]{0,30}\b(RELEASED|UNHELD|OPEN|ACTIVE|STARTED|AUTHORIZED|UNBLOCKED)\b", "a G5-G8 status other than HELD"),
 (r"(?i)freeze readiness[^.\n|;]{0,30}\b(?<!NOT )(DECLARED|READY|ACHIEVED|GRANTED)\b", "freeze readiness declared"),
 (r"(?i)\bfreeze[- ]ready\b", "freeze-ready"),
 (r"(?i)(?<!no )(?<!not )\bimplementation (is |has been |now )?(authorized|approved)\b", "implementation authorized")]
n = 0
for rx, what in BAD:
    for m in re.finditer(rx, txt): n += 1; fail(f"conflicting status text ({what}): {txt[max(0,m.start()-20):m.end()+10]!r}")
print("hardened status rules: conflicting matches:", n)
for tok in ("PLACEHOLDER", "<FILL", "TODO", "TBD", "XXX", "lorem"):
    if tok in re.sub(r"`[^`\n]*`", "", txt): fail(f"token present: {tok}")
# ---- gate table
in_gate = False; st = []
for l in lines:
    if l.startswith("| Gate | Status"): in_gate = True; continue
    if in_gate:
        if not l.startswith("|"): break
        c = [x.strip() for x in l.strip("|").split("|")]
        if c and not set(c[0]) <= set("-"): st.append((c[0].strip("*"), c[1].strip("*")))
for g, s in st: print(f"   {s:8s} {g[:90]}")
if any(s not in ("PASS", "FAIL", "BLOCKED", "NOT RUN") for _, s in st): fail("gate status outside PASS/FAIL/BLOCKED/NOT RUN")
overall = [s for g, s in st if g.startswith("Overall")]; body = [s for g, s in st if not g.startswith("Overall")]
exp = "FAIL" if "FAIL" in body else ("BLOCKED" if "BLOCKED" in body else ("NOT RUN" if "NOT RUN" in body else "PASS"))
print("gates:", body, "| overall:", overall, "| expected:", exp)
if overall != [exp]: fail("overall status does not follow from the gates")
# ---- evidence ids and files
have = {m.group(1) for f in os.listdir(evdir) if (m := re.match(r"(I\d\d)", f))}
cited = set(re.findall(r"\b([HI]\d\d)\b", txt)); miss = sorted(cited - have - {"I80", "I81"}); print("ids cited:", sorted(cited), "| missing:", miss)
if miss: fail(f"cited ids without evidence: {miss}")
def ev(i): return open(glob.glob(f"{evdir}/{i}_*")[0], encoding="utf-8").read()
# ---- digests
want5, wantz, wantb = sha(add5), sha(zip5), sha(bundle)
for label, h in (("addendum 5", want5), ("addendum 5 delivery zip", wantz), ("bundle 6", wantb)):
    ok = h in txt; print(f"   {label}: {h} cited: {ok}")
    if not ok: fail(f"{label} digest not cited correctly")
f64 = sorted(set(re.findall(r"\b[0-9a-f]{64}\b", txt))); ok64 = {want5, wantz, wantb}
unb = [s for s in f64 if s not in ok64]; print("64-hex digests:", len(f64), "| not backed:", unb)
if unb: fail(f"unbacked digests {unb}")
# ---- bundle
zf = zipfile.ZipFile(bundle); print("bundle integrity:", "OK" if zf.testzip() is None else "BAD", "| entries:", len(zf.namelist()))
man = dict(reversed(l.split("  ", 1)) for l in zf.read("MANIFEST_sha256.txt").decode().strip().split("\n"))
mm = [n for n, h in man.items() if hashlib.sha256(zf.read(n)).hexdigest() != h]; print("manifest mismatches:", mm)
if mm: fail("bundle manifest mismatch")
for i in ("I76", "I77", "I78", "I79"):
    p = glob.glob(f"{evdir}/{i}_*")[0]
    if zf.read(os.path.basename(p)) != open(p, "rb").read(): fail(f"bundle copy of {i} differs from the evidence file")
blk = hashlib.sha256(zf.read("verify_block_rev3_as_tested.sh")).hexdigest(); print("bundle block sha256:", blk)
if blk != "e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53": fail("block is not the tested rev3 block")
# ---- claims against evidence
i77, i78, i76, i79 = ev("I77"), ev("I78"), ev("I76"), ev("I79")
claims = [
 ("R1 `?@` accepted", r"127\.0\.0\.1:18443\?@github\.com/1h0lde4/ocbrain-v4\.1\s+-> ACCEPTED", i77),
 ("R1 `#@` accepted", r"evil\.example#@github\.com/1h0lde4/ocbrain-v4\.1\s+-> ACCEPTED", i77),
 ("R1 `/@` rejected", r"evil\.example/@github\.com/1h0lde4/ocbrain-v4\.1\s+-> rejected", i77),
 ("R1 `/x?@` rejected", r"evil\.example/x\?@github\.com/1h0lde4/ocbrain-v4\.1\s+-> rejected", i77),
 ("R2 connects to 127.0.0.1 port 1", r"Failed to connect to 127\.0\.0\.1 port 1", i77),
 ("R3 3 lines with the query token", r"DUMMYTOKENQ: 3", i77), ("R4 3 lines with the user-name token", r"DUMMYTOKENU: 3", i77),
 ("R5 git alone prints the user-name token", r"could not read Password for 'http://DUMMYTOKENU@127\.0\.0\.1:18402'", i77),
 ("control 0", r"control \(token string absent from output\): 0", i77),
 ("I78 first line IN PROGRESS", r"STATUS: IN PROGRESS", i78), ("I78 size 2367", r"\b2367\b", i78),
 ("I78 states the reported PASS", r"rev3 printed `PASS at", i78), ("I78 states the secret output", r"E REPRODUCED SECRET OUTPUT", i78),
 ("I76 429 five-hour limit", r"5-hour limit", i76), ("I79 PR 90", r"PR90 open draft= True commits= 3 files= 7 head= 9407db5a01acea9684f158caa8107fb71611a102", i79)]
for label, rx, t in claims:
    f = re.search(rx, t) is not None; print(f"   claim {'FOUND ' if f else 'MISSING'} {label}")
    if not f: fail(f"claim not backed: {label}")
# ---- live state
def run(*a): return subprocess.run(a, capture_output=True, text=True, cwd=repo)
head = run("git", "rev-parse", "HEAD").stdout.strip(); rem = run("git", "ls-remote", "origin", "refs/heads/docs/g4-fts-errata-handoff-oct2026").stdout.split()[0:1]
stat = run("git", "status", "--porcelain").stdout.splitlines(); print("HEAD:", head, "| remote tip:", rem, "| status lines:", len(stat))
if head != "d963daa502de4220411d0d0c2f19f67b3ec2682b" or rem != [head] or stat: fail("repository state changed")
f40 = sorted(set(re.findall(r"\b[0-9a-f]{40}\b", txt))); print("40-hex ids:", f40)
if any(x != head for x in f40): fail("a 40-hex id in the text is not the live tip")
for pre, full in (("d963daa5", head), ("9407db5a", "9407db5a01acea9684f158caa8107fb71611a102")):
    if pre not in txt: fail(f"abbreviation {pre} not used")
print("RESULT:", "FAILURES PRESENT" if bad else "ALL MECHANICAL CHECKS PASSED"); sys.exit(1 if bad else 0)
