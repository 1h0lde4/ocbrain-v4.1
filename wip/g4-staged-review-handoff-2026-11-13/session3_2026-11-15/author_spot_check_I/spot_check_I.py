"""Author spot-check of S7 findings I-1, I-2, I-3 (own harness, not the reviewer's).
Takes lines 1-44 of check_addendum4.py verbatim (the status handling), appends an exit-by-`ok` line, and runs it on
mutated copies of the addendum. Run with: python3 -I spot_check_I.py
Reads package files only as data; writes under author_check/variants_I/."""
import glob, os, subprocess, sys

SP = "/tmp/claude-0/-home-claude/3adcc49e-2c16-5b57-97ab-65b038335fc4/scratchpad"
PK = f"{SP}/a9/stage_S7/pkg/review_package/optional_item_I"
OUT = f"{SP}/author_check/variants_I"
os.makedirs(OUT, exist_ok=True)

checker = open(f"{PK}/check_addendum4.py", encoding="utf-8").read().splitlines()
front = "\n".join(checker[:44]) + "\nsys.exit(0 if ok else 1)\n"
open(f"{OUT}/front.py", "w", encoding="utf-8").write(front)
(addendum,) = glob.glob(f"{PK}/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_4_*.md")
base = open(addendum, encoding="utf-8").read().split("\n")

GOV = next(i for i, l in enumerate(base) if l.startswith("**Governing statuses, unchanged:** "))
gov = base[GOV]
gate_hdr = next(i for i, l in enumerate(base) if l.startswith("| Gate | Status"))
gate_end = next(i for i in range(gate_hdr + 1, len(base)) if not base[i].startswith("|"))

def v_base(L): return L
def v_A02(L): L[GOV] = gov.replace("G4 OPEN", "G4 CLOSED"); return L            # contract: must FAIL
def v_C01(L): L.insert(GOV + 1, "Status update: G4 CLOSED. Freeze readiness DECLARED."); return L
def v_C04(L): L.insert(GOV + 1, "**Governing statuses, unchanged:** G4 CLOSED · Low · not freeze-blocking. G5–G8 RELEASED. Freeze readiness DECLARED."); return L
def v_M01(L):
    L[GOV] = gov.replace("G4 OPEN", "G4 CLOSED")
    L[GOV + 1:GOV + 1] = ["", "```", gov, "```"]; return L
def v_T13(L):
    L[gate_end:gate_end] = ["", "| Gate | Status |", "|---|---|", "| Decoy gate | FAIL |", "| Overall result (SELF-REVIEW ONLY) | PASS |"]; return L

rows = [("base", v_base, "PASS"), ("A02", v_A02, "FAIL"), ("C01", v_C01, "FAIL"), ("C04", v_C04, "FAIL"),
        ("M01", v_M01, "FAIL"), ("T13", v_T13, "FAIL")]
print(f"governing line is file line {GOV+1}; first gate table lines {gate_hdr+1}-{gate_end}")
env = {"PATH": os.environ["PATH"], "LC_ALL": "C.UTF-8"}
for name, fn, expect in rows:
    path = f"{OUT}/{name}.md"
    open(path, "w", encoding="utf-8").write("\n".join(fn(list(base))))
    r = subprocess.run([sys.executable, "-I", f"{OUT}/front.py", path] + ["x"] * 10, capture_output=True, text=True, env=env)
    got = "PASS" if r.returncode == 0 else "FAIL"
    cls = ("correct " + got) if got == expect else ("FALSE PASS" if got == "PASS" else "false FAIL")
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL:")]
    print(f"{name:5s} contract_expects={expect} checker={got} (rc={r.returncode}) -> {cls}  {fails if fails else ''}")
