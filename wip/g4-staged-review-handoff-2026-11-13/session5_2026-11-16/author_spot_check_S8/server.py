"""Author spot-check server: TLS smart-HTTP in front of `git http-backend`. Loopback only (run inside `unshare -rn`).
usage: python3 server.py LABEL PORT CERT KEY PROJECT_ROOT REPO_NAME|NONE LOGFILE
REPO_NAME NONE -> answer 404 to everything. Any GET is mapped to <repo>/info/refs?service=git-upload-pack and any POST to
<repo>/git-upload-pack, so odd request targets (`/?@github.com/...`) still reach the repository; the real request line is logged.
Authorization header is logged as present/absent only."""
import json, ssl, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

label, port, cert, key, root, repo, logf = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]
sni_seen = {}

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _log(self, status):
        rec = {"server": label, "listen": f"127.0.0.1:{port}", "client": "%s:%s" % self.client_address,
               "host_header": self.headers.get("Host"), "request_line": self.requestline,
               "authorization": "present" if self.headers.get("Authorization") else "absent", "status": status}
        with open(logf, "a") as f: f.write(json.dumps(rec) + "\n")
    def _body(self):
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            out = b""
            while True:
                n = int(self.rfile.readline().strip().split(b";")[0], 16)
                if n == 0: self.rfile.readline(); break
                out += self.rfile.read(n); self.rfile.readline()
            return out
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))
    def _serve(self, post):
        body = self._body() if post else b""
        if repo == "NONE":
            self._log(404); self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
        env = {"PATH": "/usr/bin:/bin", "GIT_PROJECT_ROOT": root, "GIT_HTTP_EXPORT_ALL": "1", "REMOTE_ADDR": "127.0.0.1",
               "REQUEST_METHOD": "POST" if post else "GET",
               "PATH_INFO": f"/{repo}/git-upload-pack" if post else f"/{repo}/info/refs",
               "QUERY_STRING": "" if post else "service=git-upload-pack",
               "CONTENT_TYPE": self.headers.get("Content-Type", ""), "CONTENT_LENGTH": str(len(body))}
        if self.headers.get("Git-Protocol"): env["GIT_PROTOCOL"] = self.headers["Git-Protocol"]
        if self.headers.get("Content-Encoding"): env["HTTP_CONTENT_ENCODING"] = self.headers["Content-Encoding"]
        r = subprocess.run(["/usr/lib/git-core/git-http-backend"], input=body, env=env, capture_output=True)
        hdr, _, data = r.stdout.partition(b"\r\n\r\n")
        status, heads = 200, []
        for line in hdr.decode("latin-1").split("\r\n"):
            if line.lower().startswith("status:"): status = int(line.split()[1])
            elif ":" in line: heads.append(tuple(x.strip() for x in line.split(":", 1)))
        self._log(status); self.send_response(status)
        for k, v in heads: self.send_header(k, v)
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self): self._serve(False)
    def do_POST(self): self._serve(True)

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(cert, key)
srv = ThreadingHTTPServer(("127.0.0.1", port), H); srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
srv.serve_forever()
