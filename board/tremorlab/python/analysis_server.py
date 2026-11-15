# Analysis server: one JSON request line in, one response line out, run by tremorlab.analysis.
import json
import socketserver
import threading
import time

from tremorlab.analysis.wire import BAD_REQUEST, run_op


def _respond(line, log):
    t0 = time.monotonic()
    try:
        req = json.loads(line)
    except ValueError:
        return {"ok": False, "error": BAD_REQUEST}
    if not isinstance(req, dict):
        return {"ok": False, "error": BAD_REQUEST}
    op = req.get("op")
    resp = run_op(op, req.get("args"))
    n = len((req.get("args") or {}).get("t") or []) if isinstance(req.get("args"), dict) else 0
    status = "ok" if resp["ok"] else resp["error"]
    log(f"analyzed {op} n={n} in {(time.monotonic() - t0) * 1000:.0f} ms: {status}")
    return resp


def start(port, log):
    """Serve on 0.0.0.0:port from a daemon thread; each connection may send several requests."""

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            for line in self.rfile:
                if not line.strip():
                    continue
                resp = _respond(line, log)
                self.wfile.write((json.dumps(resp, separators=(",", ":")) + "\n").encode())
                self.wfile.flush()

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    srv = Server(("0.0.0.0", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"analysis listening on 0.0.0.0:{port}")
    return srv
