"""Local dev server: serves public/ and routes /api/* to the Vercel handlers. Usage: python3 dev.py [port]"""
import os, sys, importlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

class Dev(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=os.path.join(HERE, "public"), **k)
    def _api(self, verb):
        name = self.path.split("?")[0][len("/api/"):]
        try: mod = importlib.import_module(f"api.{name}")
        except ImportError: return self.send_error(404)
        import types
        for k, v in vars(mod.handler).items():          # borrow the handler's methods (incl. helpers like _send)
            if isinstance(v, types.FunctionType) and not k.startswith("__"): setattr(self, k, types.MethodType(v, self))
        getattr(self, verb)()
    def do_GET(self):
        self._api("do_GET") if self.path.startswith("/api/") else super().do_GET()
    def do_POST(self): self._api("do_POST")
    def do_DELETE(self): self._api("do_DELETE")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"http://localhost:{port}"); ThreadingHTTPServer(("", port), Dev).serve_forever()
