# Copyright (C) 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
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

"""
Run performance tests for the web-component approach.
"""

import gzip
from pathlib import Path
import sys
import time

WEB_COMPONENT_URL = "http://127.0.0.1:5433/projects/6980c39c924613b4604bac3e"


def get_gzipped_size(file_path):
    """Calculate gzipped size of a file."""
    with open(file_path, "rb") as f:
        content = f.read()
    return len(gzip.compress(content, compresslevel=9))


def analyze_web_component_bundle():
    """Analyze the web-component bundle."""
    web_component_dir = Path("src/ansys/solutions/dashboard/ui/assets/dashboard-app")
    files = []

    for f in web_component_dir.glob("*"):
        if f.is_file() and f.suffix in [".js", ".css"]:
            size = f.stat().st_size
            gzipped = get_gzipped_size(f)
            files.append((f.name, size, gzipped, f.suffix))

    total_size = sum(f[1] for f in files)
    total_gzipped = sum(f[2] for f in files)
    js_size = sum(f[1] for f in files if f[3] == ".js")
    css_size = sum(f[1] for f in files if f[3] == ".css")

    print("=" * 50)
    print("Web Component Bundle Analysis")
    print("=" * 50)
    print(f"Total Size: {total_size / 1024:.2f} KB")
    print(f"Gzipped:    {total_gzipped / 1024:.2f} KB")
    print(f"JS Size:    {js_size / 1024:.2f} KB")
    print(f"CSS Size:   {css_size / 1024:.2f} KB")
    for f in files:
        print(f"  - {f[0]}: {f[1] / 1024:.2f} KB ({f[2] / 1024:.2f} KB gzipped)")
    print("=" * 50)

    return {
        "total_kb": total_size / 1024,
        "gzipped_kb": total_gzipped / 1024,
        "js_kb": js_size / 1024,
        "css_kb": css_size / 1024,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Performance Tests for Web-Component Approach")
    print(f"URL: {WEB_COMPONENT_URL}")
    print("=" * 60)

    # Bundle analysis only (Web Vitals and Memory are run via pytest)
    bundle = analyze_web_component_bundle()

    print("\n" + "=" * 60)
    print("BUNDLE SUMMARY")
    print("=" * 60)
    print(f"Total Size: {bundle['total_kb']:.2f} KB")
    print(f"Gzipped:    {bundle['gzipped_kb']:.2f} KB")
    print(f"JS Size:    {bundle['js_kb']:.2f} KB")
    print(f"CSS Size:   {bundle['css_kb']:.2f} KB")
    print("=" * 60)
    print("\nTo run Web Vitals and Memory tests, use:")
    print(f'  $env:BENCHMARK_URL="{WEB_COMPONENT_URL}"')
    print("  pytest tests/performance/test_performance.py::TestWebVitals -v -s")
    print("  pytest tests/performance/test_performance.py::TestMemoryProfile -v -s")
