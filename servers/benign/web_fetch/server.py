"""Benign Web Fetch MCP server (allow-listed local test site only).

Simple explanation
------------------
Gives the agent a ``fetch`` tool that downloads a web page and returns its
text, like popular "fetch" MCP servers. Here it can **only** reach the lab's
own synthetic site. Pages differ in length, and long pages need several calls
(``start_index``), so responses have realistic, variable sizes.

Safety: why this cannot become an SSRF / internet tool
------------------------------------------------------
* The allowed origin (``scheme://host:port``) comes from ``MCP_WEB_BASE_URL``,
  set by the lab, never by the agent. Any URL with a different scheme, host or
  port is refused *before* a connection is made.
* Redirects are not followed (a redirect could point elsewhere).
* Environment proxy settings are ignored (``ProxyHandler({})``).
* 5 s timeout and 256 KiB download cap.
* In Docker, the lab network has no internet route anyway (defence in depth).
"""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

from common.descriptions import describe
from common.logsetup import configure_server_logging
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

SERVER_ID = "web_fetch"
TIMEOUT_S = 5.0
MAX_DOWNLOAD_BYTES = 256 * 1024
DEFAULT_MAX_LENGTH = 5000

log = logging.getLogger(__name__)


def allowed_origin() -> tuple[str, str, int]:
    base = os.getenv("MCP_WEB_BASE_URL")
    if not base:
        raise RuntimeError("MCP_WEB_BASE_URL is not set; refusing to start without an allow-list")
    return _origin(base)


def _origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    port = parts.port or {"http": 80, "https": 443}.get(parts.scheme, 0)
    return parts.scheme, (parts.hostname or "").lower(), port


def check_allowed(url: str) -> None:
    """Raise ToolError unless ``url`` has exactly the allowed origin."""
    try:
        parts = urlsplit(url)
        origin = _origin(url)
    except ValueError:
        raise ToolError(f"Invalid URL: {url!r}") from None
    if parts.username is not None or parts.password is not None:
        # "http://a@b@host/" style URLs: different parsers disagree on the host
        # (a classic SSRF trick), so credentials in URLs are never accepted.
        raise ToolError(f"URL not allowed: {url!r} (credentials in URLs are refused)")
    if origin != allowed_origin():
        raise ToolError(f"URL not allowed: {url!r} (only the lab test site may be fetched)")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # type: ignore[override]
        return None  # surface 3xx as an HTTPError instead of following it


_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


class _TextExtractor(HTMLParser):
    """Minimal HTML -> text: keeps visible text, drops script/style."""

    BLOCK = {"p", "h1", "h2", "h3", "li", "tr", "br", "div", "nav", "footer", "table"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> tuple[str, str]:
    p = _TextExtractor()
    p.feed(html)
    return p.title.strip(), p.text()


mcp = MCPServer(
    name="lab-web-fetch",
    instructions="Fetch pages from the lab's synthetic test website and return their text.",
    version="0.1.0",
)


@mcp.tool(description=describe("web_fetch", "fetch"))
def fetch(url: str, max_length: int = DEFAULT_MAX_LENGTH, start_index: int = 0) -> str:
    """Fetch a web page and return its text content.

    Long pages are returned in chunks: call again with `start_index` set to
    continue where the previous chunk ended.
    """
    check_allowed(url)
    if max_length < 1 or start_index < 0:
        raise ToolError("max_length must be >= 1 and start_index >= 0")
    try:
        with _opener.open(url, timeout=TIMEOUT_S) as resp:
            data = resp.read(MAX_DOWNLOAD_BYTES + 1)
            ctype = resp.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        raise ToolError(f"HTTP {exc.code} fetching {url}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ToolError(f"Failed to fetch {url}: {exc}") from None
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ToolError(f"Page too large (limit {MAX_DOWNLOAD_BYTES} bytes)")

    raw = data.decode("utf-8", errors="replace")
    title, text = html_to_text(raw) if ctype == "text/html" else ("", raw)
    chunk = text[start_index:start_index + max_length]
    if not chunk and start_index > 0:
        raise ToolError(f"start_index {start_index} is past the end of the content ({len(text)} chars)")
    header = f"Title: {title}\n\n" if title and start_index == 0 else ""
    end = start_index + len(chunk)
    footer = (f"\n\n[Content truncated. Call fetch again with start_index={end} to continue.]"
              if end < len(text) else "")
    log.info("fetch %s -> %d/%d chars from %d", url, len(chunk), len(text), start_index)
    return header + chunk + footer


def main() -> None:
    configure_server_logging("web-fetch-server")
    log.info("starting; allowed origin=%s session=%s", allowed_origin(), os.getenv("MCP_SESSION_ID", "-"))
    mcp.run("stdio")


if __name__ == "__main__":
    main()
