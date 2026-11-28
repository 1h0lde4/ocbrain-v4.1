"""R-1 probe: drive scripts/ci_test_gate.evaluate() with crafted pytest output. Read-only; run from the repo root."""
import sys
sys.path.insert(0, "scripts")
import ci_test_gate as g

two = ("FAILED tests/t.py::test_f[a - 1] - AssertionError: x\n"
       "FAILED tests/t.py::test_f[a - 2] - AssertionError: y\n"
       "FAILED tests/t.py::test_g - boom\n"
       "=========== 3 failed, 10 passed in 1.0s ===========\n")
print("parse_failed_ids ->", sorted(g.parse_failed_ids(two)))
for label, allow in [("empty allowlist", set()),
                     ("allowlist = full ids of test_f[a - 1] and test_g", {"tests/t.py::test_f[a - 1]", "tests/t.py::test_g"})]:
    v = g.evaluate(two, 1, allow)
    print(label, "| ok =", v.ok, "| new =", sorted(v.new_failures), "| known =", sorted(v.known_failures_seen), "| reasons =", v.reasons)

one = "FAILED tests/x.py::test_p[a - b] - AssertionError: new real failure\n=========== 1 failed, 10 passed in 1.0s ===========\n"
v = g.evaluate(one, 1, {"tests/x.py::test_p[a"})
print("hand-truncated allowlist entry + 1 real failing ' - ' id -> ok =", v.ok, "| new =", sorted(v.new_failures), "| known =", sorted(v.known_failures_seen), "| reasons =", v.reasons)
v = g.evaluate(one, 1, set())
print("same output, empty allowlist -> ok =", v.ok, "| reasons =", v.reasons)
