"""Local, offline static web server for the synthetic test site.

The web-fetch MCP server may only fetch from this site, never the internet.

* In Docker it runs as its own ``testweb`` container on the internal lab
  network: ``python -m servers.benign.web_fetch.testsite --host 0.0.0.0 --port 8080``.
* Locally, :func:`shared_site_url` starts one shared copy per process on
  ``127.0.0.1:18080`` (``MCP_TESTWEB_PORT``). :func:`serve_site` starts a private
  copy on a free port (used by unit tests).

Only GET/HEAD of files under ``site/`` are served (stdlib ``SimpleHTTPRequestHandler``
already refuses paths outside its directory).
"""

from __future__ import annotations

import argparse
import functools
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent / "site"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # keep test output clean
        pass


def _make_server(host: str, port: int, quiet: bool) -> ThreadingHTTPServer:
    handler = functools.partial(_QuietHandler if quiet else SimpleHTTPRequestHandler,
                                directory=str(SITE_DIR))
    return ThreadingHTTPServer((host, port), handler)


@contextmanager
def serve_site(host: str = "127.0.0.1", port: int = 0) -> Iterator[str]:
    """Run the site in a background thread; yield its base URL."""
    httpd = _make_server(host, port, quiet=True)
    thread = threading.Thread(target=httpd.serve_forever, name="testsite", daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


_shared_url: str | None = None
_shared_lock = threading.Lock()
DEFAULT_LOCAL_PORT = 18080


def shared_site_url(port: int | None = None) -> str:
    """Start (once per process) and return a shared local site.

    Mirrors Docker, where every session uses the same ``testweb`` container.
    A *fixed* port keeps URLs -- and therefore message sizes -- identical across
    runs, so the same seed reproduces the same wire traffic. Falls back to a
    random free port if the fixed one is taken. The site is static and
    read-only, so sharing it between concurrent sessions is safe.
    """
    global _shared_url
    with _shared_lock:
        if _shared_url is None:
            port = port if port is not None else int(os.getenv("MCP_TESTWEB_PORT", DEFAULT_LOCAL_PORT))
            try:
                httpd = _make_server("127.0.0.1", port, quiet=True)
            except OSError:
                httpd = _make_server("127.0.0.1", 0, quiet=True)
            threading.Thread(target=httpd.serve_forever, name="testsite-shared", daemon=True).start()
            _shared_url = f"http://127.0.0.1:{httpd.server_address[1]}"
        return _shared_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the synthetic lab website")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    httpd = _make_server(args.host, args.port, quiet=False)
    print(f"serving {SITE_DIR} on http://{args.host}:{args.port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
