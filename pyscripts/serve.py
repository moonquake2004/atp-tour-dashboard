#!/usr/bin/env python3
"""
Zero-dependency static preview server for the generated site.

    python3 pyscripts/serve.py [port]        # serves docs/
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from wtalib import ROOT


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter output
        if "404" in (fmt % args):
            sys.stderr.write(f"  404 {self.path}\n")


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4174
    directory = ROOT / "docs"
    if not directory.exists():
        raise SystemExit("docs/ is missing — run build_site.py first")

    handler = functools.partial(Handler, directory=str(directory))

    # Threaded: a page requests hundreds of headshots, and a single-threaded
    # server serialises them until the page appears to hang.
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with Server(("127.0.0.1", port), handler) as httpd:
        print(f"▶ Serving docs/ at http://127.0.0.1:{port}/")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
