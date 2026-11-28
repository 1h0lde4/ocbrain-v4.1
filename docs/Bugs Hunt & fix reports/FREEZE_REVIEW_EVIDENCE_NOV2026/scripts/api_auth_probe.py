"""API authentication probe (in-process FastAPI TestClient). Run from the repo root with
OCBRAIN_API_TOKEN set to a throwaway value and HOME pointing at an empty directory.
Limits: no real socket, no real proxy; authorized SSE streaming is not exercised."""
import os, re, sys, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.CRITICAL)
sys.path.insert(0, ".")
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from interface import api

TOK = os.environ["OCBRAIN_API_TOKEN"]
api.setup(MagicMock(), None)
c = TestClient(api.app, raise_server_exceptions=False)
H = {"Host": "localhost:7437"}
def hit(h, m, p):
    return c.request(m, p, headers=h, json={} if m != "GET" else None).status_code
def sse(h, p):
    with c.stream("GET", p, headers=h) as r:
        return r.status_code

routes = []
for r in api.app.routes:
    path, methods = getattr(r, "path", None), getattr(r, "methods", None)
    if path and methods:
        for m in sorted(methods - {"HEAD", "OPTIONS"}):
            if path.endswith("/events") or path == "/events": continue
            routes.append((m, re.sub(r"\{[^}]+\}", "x", path)))
print("non-SSE route/method pairs probed:", len(routes))
noauth = {k: hit(H, *k) for k in routes}
wrong = {k: hit({**H, "Authorization": "Bearer wrong"}, *k) for k in routes}
print("no token statuses:", sorted(set(noauth.values())), "| non-401:", {k: v for k, v in noauth.items() if v != 401})
print("wrong token statuses:", sorted(set(wrong.values())))
print("valid token GET statuses:", sorted({hit({**H, 'Authorization': 'Bearer ' + TOK}, m, p) for m, p in routes if m == "GET"}))
for m, p in [("GET", "/health/"), ("GET", "/Health"), ("GET", "/%68ealth"), ("POST", "/query/"), ("GET", "//health"), ("GET", "//config"),
             ("PUT", "//config"), ("POST", "//update/install"), ("POST", "//rollback"), ("GET", "///health")]:
    r = c.request(m, p, headers=H, json={"x": 1} if m != "GET" else None)
    print(f"variant {m:4} {p:18} -> {r.status_code} {r.headers.get('content-type','')[:22]}")
print("Host evil.example:", hit({"Host": "evil.example"}, "GET", "/health"), "| Host localhost.evil.com:", hit({"Host": "localhost.evil.com"}, "GET", "/health"))
for name, path, h in [("SSE /events no token", "/events", H), ("SSE /events wrong token", "/events", {**H, "Authorization": "Bearer wrong"}),
                      ("SSE /executions/x/events no token", "/executions/x/events", H), ("SSE /executions/x/events wrong token", "/executions/x/events", {**H, "Authorization": "Bearer wrong"}),
                      ("SSE token in query string only", "/events?token=" + TOK, H)]:
    print(f"{name}: {sse(h, path)}")
for name, h, p, m in [("X-Forwarded-For 127.0.0.1", {**H, "X-Forwarded-For": "127.0.0.1"}, "/health", "GET"),
                      ("X-Forwarded-Host/Proto", {"Host": "localhost:7437", "X-Forwarded-Host": "localhost:7437", "X-Forwarded-Proto": "https"}, "/health", "GET"),
                      ("Forwarded: for=127.0.0.1", {**H, "Forwarded": "for=127.0.0.1;host=localhost"}, "/health", "GET"),
                      ("Host evil + X-Forwarded-Host localhost", {"Host": "evil.example", "X-Forwarded-Host": "localhost:7437"}, "/health", "GET"),
                      ("X-Original-URL/X-Rewrite-URL -> /", {**H, "X-Original-URL": "/", "X-Rewrite-URL": "/"}, "/query", "POST")]:
    print(f"forwarded-header case '{name}': {hit(h, m, p)}")
