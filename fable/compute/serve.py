"""Serve the built viewer locally, with the current bundle.

``viewer/dist`` is a static site, but browsers will not run it from a
``file://`` URL (module scripts and ``fetch`` are blocked there). This serves
it over http://127.0.0.1 and answers ``data/*`` requests from the data folder
(default ``viewer/public/data``), so a freshly written ``bundle.json`` shows up
without rebuilding the site.

    python -m fable.compute view                    # build the site once first: cd viewer && npm run build
    python -m fable.compute view --data path/to/dir # serve another bundle.json
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlsplit

from .config import REPO_ROOT

DIST_DIR = REPO_ROOT / "viewer" / "dist"
DATA_DIR = REPO_ROOT / "viewer" / "public" / "data"


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, dist: Path, data: Path, **kwargs):
        self._data = data
        super().__init__(*args, directory=str(dist), **kwargs)

    def translate_path(self, path: str) -> str:
        rel = unquote(urlsplit(path).path)
        # Built with base "./" the site may sit under any prefix; only the
        # part after the last "/data/" matters for data requests.
        if "/data/" in rel:
            name = rel.rsplit("/data/", 1)[1]
            target = (self._data / name).resolve()
            if self._data.resolve() in target.parents:
                return str(target)
        return super().translate_path(path)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args) -> None:  # keep the terminal quiet
        pass


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_server(
    *, dist: Path = DIST_DIR, data: Path = DATA_DIR, port: int = 0
) -> Tuple[_Server, str]:
    if not (dist / "index.html").exists():
        raise FileNotFoundError(
            f"{dist / 'index.html'} not found. Build the viewer first:\n"
            "    cd viewer && npm ci && npm run build"
        )
    handler = functools.partial(_Handler, dist=Path(dist), data=Path(data))
    server = _Server(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, url


def serve_forever(*, data: Optional[Path] = None, port: int = 8765, open_browser: bool = True) -> None:
    server, url = start_server(data=Path(data) if data else DATA_DIR, port=port)
    print(f"FABLE viewer at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
