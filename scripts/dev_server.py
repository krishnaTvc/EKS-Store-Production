#!/usr/bin/env python3
"""
EKS Beverage Store - Local Frontend Development Server with Reverse Proxy
Serves static assets from frontend/public/ and proxies API routes to
catalog-service (:8001) and order-service (:8002), emulating the Nginx / ALB setup.
"""

import sys
import os
import urllib.request
import urllib.error
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend" / "public"

CATALOG_BACKEND = "http://localhost:8001"
ORDER_BACKEND = "http://localhost:8002"
PORT = 3000


class DevProxyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/catalog/") or self.path.startswith("/assets/catalog/"):
            self.proxy_request(CATALOG_BACKEND, self.path)
        elif self.path.startswith("/api/orders/"):
            self.proxy_request(ORDER_BACKEND, self.path)
        elif self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"healthy\n")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/orders"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            self.proxy_request(ORDER_BACKEND, self.path, method="POST", body=body)
        elif self.path.startswith("/api/catalog/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            self.proxy_request(CATALOG_BACKEND, self.path, method="POST", body=body)
        else:
            self.send_error(405, "Method Not Allowed")

    def proxy_request(self, target_base, path, method="GET", body=None):
        target_url = f"{target_base}{path}"
        headers = {}
        for key in ["Content-Type", "Idempotency-Key", "X-Correlation-Id", "Accept"]:
            if key in self.headers:
                headers[key] = self.headers[key]

        req = urllib.request.Request(target_url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for header, val in resp.getheaders():
                    # Strip hop-by-hop headers
                    if header.lower() not in ["transfer-encoding", "content-length", "connection"]:
                        self.send_header(header, val)
                content = resp.read()
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for header, val in e.headers.items():
                if header.lower() not in ["transfer-encoding", "content-length", "connection"]:
                    self.send_header(header, val)
            err_body = e.read()
            self.send_header("Content-Length", str(len(err_body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(err_body)
        except Exception as e:
            self.send_error(502, f"Bad Gateway: Unable to reach backend at {target_url} ({e})")


def run():
    print(f"Starting EKS Beverage Store Dev UI on http://localhost:{PORT}")
    print(f"Serving static assets from: {FRONTEND_DIR}")
    print(f"Proxying /api/catalog/ -> {CATALOG_BACKEND}")
    print(f"Proxying /api/orders/  -> {ORDER_BACKEND}")
    server = HTTPServer(("0.0.0.0", PORT), DevProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dev server.")
        server.server_close()


if __name__ == "__main__":
    run()
