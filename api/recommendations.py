import json, os, sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from engine import run

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        month = (parse_qs(urlparse(self.path).query).get("month") or [None])[0]
        try:
            body, code = json.dumps(run(os.path.join(ROOT, "data"), month)).encode(), 200
        except Exception as e:
            body, code = json.dumps({"error": str(e)}).encode(), 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)
