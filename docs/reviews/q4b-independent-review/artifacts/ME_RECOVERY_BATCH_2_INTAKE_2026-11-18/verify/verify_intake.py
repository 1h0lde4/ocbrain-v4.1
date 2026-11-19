#!/usr/bin/env python3
"""Recompute the intake checks recorded in ../README.md. Run from the repo root:
   python3 docs/reviews/q4b-independent-review/artifacts/ME_RECOVERY_BATCH_2_INTAKE_2026-11-18/verify/verify_intake.py
Reads received/*.zip in memory only (nothing is extracted). Compares against records already in
the repo (Batch 1 addendum API bodies, Batch 1 S05 archive record). Network is not used."""
import hashlib, io, json, pathlib, zipfile
PKG = pathlib.Path(__file__).resolve().parent.parent
ART = PKG.parent
API = ART / "ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB" / "api"
S05 = (ART / "ME_RECOVERY_BATCH_1" / "acquisition_records" / "search_logs" / "S05_archive_verification.txt").read_text()
h = lambda b: hashlib.sha256(b).hexdigest()
rx = {p.name.split("__")[0]: p for p in sorted((PKG / "received").glob("*.zip"))}
print("== received files")
for k, p in rx.items():
    b = p.read_bytes(); print(f"{k} {p.name.split('__',1)[1]} {len(b)}B sha256={h(b)} testzip={zipfile.ZipFile(io.BytesIO(b)).testzip()}")
print("\n== I001 CI package vs GitHub digests (captured earlier via authenticated API) and run->commit")
z = zipfile.ZipFile(rx["I001"])
for d, run in (("RUN_40781867485_4a4783c", "40781867485"), ("RUN_39226693573_f13bfde", "39226693573")):
    base = f"ME07_CI_ACQUISITION/{d}/"
    det = json.loads((API / f"run_{run}_detail.body").read_text())
    print(f"run {run}: head_sha={det['head_sha'][:10]} attempt={det['run_attempt']} event={det['event']} branch={det['head_branch']} conclusion={det['conclusion']}")
    arts = {a["name"]: a for a in json.loads((API / f"run_{run}_artifacts.body").read_text())["artifacts"]}
    sums = {l.split()[1].lstrip("*"): l.split()[0] for l in z.read(base + "raw/SHA256SUMS").decode().splitlines() if l.strip()}
    for name in ("pytest-output", "drift-report"):
        raw = z.read(base + f"raw/{name}.zip"); inner = zipfile.ZipFile(io.BytesIO(raw))
        ok_members = all(inner.read(i) == z.read(base + f"extracted/{name}/{i.filename}") for i in inner.infolist())
        print(f"  {name}.zip {len(raw)}B (GitHub {arts[name]['size_in_bytes']}B) GitHub-digest-match={arts[name]['digest']=='sha256:'+h(raw)} sender-SHA256SUMS-match={sums.get(name+'.zip')==h(raw)} inner-testzip={inner.testzip()} members-match-extracted={ok_members}")
        if run == "40781867485":
            for k, nm in (("I003", "drift-report"), ("I004", "pytest-output")):
                if nm == name: print(f"    {k} outer bytes identical to this copy: {rx[k].read_bytes() == raw}")
print("\n== I002 probe scripts vs Batch 1 S05 record of the original files.zip")
z2 = zipfile.ZipFile(rx["I002"])
checked = 0
for i in z2.infolist():
    if i.is_dir() or i.filename == "RECOVERY_MANIFEST.txt":
        continue  # the sender's own manifest is not an original member
    d = h(z2.read(i)); checked += 1
    print(f"  {i.filename} {i.file_size}B {d[:16]}.. in S05 record: {d in S05}")
assert checked == 6, f"expected 6 original members, checked {checked}"
print(f"  members checked: {checked} (expected 6)")
