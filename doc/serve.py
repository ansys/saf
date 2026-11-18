# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Serve the built HTML documentation locally with the same URL layout as production.

The technology radar is built with ``basePath=/version/stable/radar``, so the documentation
must be served under ``/version/stable/`` for the embedded radar to load. Opening the HTML
files directly from disk (``file://``) does not work.

Usage: ``uv run python doc/serve.py [--port 8000]``
"""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PREFIX = "/version/stable"
HTML_DIR = Path(__file__).resolve().parent / "_build" / "html"


class PrefixedHandler(SimpleHTTPRequestHandler):
    """Serve ``HTML_DIR`` under ``PREFIX`` and redirect ``/`` to it."""

    def do_GET(self):
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", f"{PREFIX}/")
            self.end_headers()
            return
        super().do_GET()

    def translate_path(self, path):
        if path == PREFIX or path.startswith(f"{PREFIX}/"):
            path = path[len(PREFIX) :] or "/"
        return super().translate_path(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if not (HTML_DIR / "index.html").is_file():
        raise SystemExit(f"No built documentation in {HTML_DIR}. Run 'moon run root:build-doc' first.")

    handler = partial(PrefixedHandler, directory=str(HTML_DIR))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Serving documentation at http://127.0.0.1:{args.port}{PREFIX}/ (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
