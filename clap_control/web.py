from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit
from .scenes import APIError


class IngressServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.slots = threading.BoundedSemaphore(8)

    def verify_request(self, request, client_address):
        return client_address[0] == "172.30.32.2"

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def serve(app, address=("0.0.0.0", 8099)):
    static = Path(__file__).parent / "static"

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            pass  # Do not log ingress session paths or every diagnostic poll.

        def send(self, status, payload, content_type="application/json; charset=utf-8"):
            body = json.dumps(payload, ensure_ascii=False).encode() if isinstance(payload, (dict, list)) else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/status":
                self.send(200, app.status())
            elif path == "/api/settings":
                self.send(200, app.web_settings())
            elif path == "/api/scenes":
                try:
                    self.send(200, app.api.scenes())
                except APIError as exc:
                    self.send(503, {"error": str(exc)})
            elif path in ("/", "/app.js", "/style.css"):
                name, kind = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                              "/style.css": ("style.css", "text/css")}[path]
                self.send(200, (static / name).read_bytes(), kind + "; charset=utf-8")
            else:
                self.send(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != "/api/settings":
                self.send(404, {"error": "Not found"})
                return
            if (self.headers.get("Content-Type", "").split(";")[0] != "application/json"
                    or self.headers.get("X-Clap-Control") != "1"):
                self.send(403, {"error": "JSON request required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Invalid request size")
                app.save_settings(json.loads(self.rfile.read(length)))
                self.send(200, app.web_settings())
            except (ValueError, TypeError) as exc:
                self.send(400, {"error": str(exc)})
            except (APIError, OSError) as exc:
                self.send(503, {"error": str(exc)})

    return IngressServer(address, Handler)
