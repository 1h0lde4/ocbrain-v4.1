"""Author spot-check server for S3-N1: plain http on loopback; answers 401 Basic unless Authorization is present, then 404.
Logs request line + whether Authorization is present (never the value). usage: python3 n1_server.py PORT LOGFILE"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
port, logf = int(sys.argv[1]), sys.argv[2]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        has = bool(self.headers.get("Authorization"))
        open(logf, "a").write(json.dumps({"line": self.requestline[:100], "authorization": "present" if has else "absent"}) + "\n")
        if has: self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()
        else:
            self.send_response(401); self.send_header("WWW-Authenticate", 'Basic realm="x"'); self.send_header("Content-Length", "0"); self.end_headers()
    do_POST = do_GET
HTTPServer(("127.0.0.1", port), H).serve_forever()
