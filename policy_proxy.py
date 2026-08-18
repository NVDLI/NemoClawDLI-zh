#!/usr/bin/env python3
"""
policy_proxy.py — Local WSL2 policy bridge for NeMoClaw page 04a.

Runs `openshell policy get <agent> --full` in WSL2 (outside the sandbox)
and serves the raw YAML output over HTTP so the browser's helpers.policyGet()
can fetch it directly, bypassing the sandbox restriction that blocks the
operator terminal from reaching the OpenShell control plane from inside
the container.

Usage:
    python3 policy_proxy.py &

Endpoint:
    GET http://localhost:8012/policy?agent=my-assistant
    → raw YAML text (same output as: openshell policy get my-assistant --full)

Port: 8012 (hardcoded; change PORT below if needed)
"""

import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8012


class PolicyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/policy":
            self._respond(404, "text/plain", b"Not found. Use GET /policy?agent=<name>")
            return

        params = parse_qs(parsed.query)
        agent = params.get("agent", ["my-assistant"])[0]

        try:
            result = subprocess.run(
                ["openshell", "policy", "get", agent, "--full"],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout
            if not output.strip():
                output = result.stderr or "(openshell policy get returned no output)"
        except FileNotFoundError:
            output = "(openshell not found in PATH — is NeMoClaw installed?)"
        except subprocess.TimeoutExpired:
            output = "(openshell policy get timed out after 15s)"
        except Exception as e:
            output = f"(error running openshell policy get: {e})"

        self._respond(200, "text/plain; charset=utf-8", output.encode())

    def _respond(self, code, content_type, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")   # allow browser fetch
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Single-line log: timestamp + request summary
        print(f"[policy_proxy] {self.address_string()} - {fmt % args}", flush=True)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), PolicyHandler)
    print(f"[policy_proxy] listening on http://127.0.0.1:{PORT}/policy?agent=my-assistant", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[policy_proxy] stopped.", flush=True)
        sys.exit(0)
