#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Simple CORS proxy for NVIDIA API - forwards requests from localhost to integrate.api.nvidia.com"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.error, json

TARGET = "https://integrate.api.nvidia.com"
PORT = 8010

class CORSProxy(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        self._proxy("GET", None)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self._proxy("POST", body)

    def _proxy(self, method, body):
        url = TARGET + self.path
        req = urllib.request.Request(url, data=body, method=method)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "origin", "referer", "content-length"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                content_type = resp.headers.get("Content-Type", "application/json")
                status = resp.status
                is_sse = "text/event-stream" in content_type

                self.send_response(status)
                self._cors_headers()
                self.send_header("Content-Type", content_type)
                if is_sse:
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()
                    print(f"[proxy] {method} {self.path} -> {status} SSE stream")
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                else:
                    data = resp.read()
                    print(f"[proxy] {method} {self.path} -> {status} ({len(data)} bytes)")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            print(f"[proxy] {method} {self.path} -> HTTPError {e.code}: {data[:200]}")
            self.send_response(e.code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            print(f"[proxy] {method} {self.path} -> Exception: {e}")

    def _cors_headers(self):
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        requested = self.headers.get("Access-Control-Request-Headers", "")
        allowed = requested if requested else "Authorization, Content-Type, X-Billing-Invoke-Origin, User-Agent"
        self.send_header("Access-Control-Allow-Headers", allowed)

    def log_message(self, fmt, *args):
        pass  # suppressed; debug prints below handle output

print(f"CORS proxy running on http://localhost:{PORT} → {TARGET}")
ThreadingHTTPServer(("localhost", PORT), CORSProxy).serve_forever()
