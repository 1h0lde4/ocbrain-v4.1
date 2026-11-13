import json, sys, hashlib
jpath, out, start, need = sys.argv[1:5]
START = "  " + start
hits = []
def walk(o):
    if isinstance(o, str):
        if START in o and need in o and "extract_handback" not in o and "def walk" not in o:
            hits.append(o)
    elif isinstance(o, dict):
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
with open(jpath, encoding="utf-8") as f:
    for line in f:
        if start not in line: continue
        try: walk(json.loads(line))
        except Exception as e: print("parse error", e, file=sys.stderr)
bodies = []
for h in hits:
    i = h.index(START)
    rep = []
    for ln in h[i:].split("\n"):
        if ln.startswith("  "): rep.append(ln[2:])
        elif ln.strip() == "": rep.append("")
        else: break
    while rep and rep[-1] == "": rep.pop()
    bodies.append("\n".join(rep) + "\n")
print("hits:", len(hits), "distinct bodies:", len(set(bodies)))
if not bodies: sys.exit(2)
best = max(set(bodies), key=len)
open(out, "w", encoding="utf-8").write(best)
print("wrote", out, len(best.encode()), "bytes sha256", hashlib.sha256(best.encode()).hexdigest())
