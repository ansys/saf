# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.

# SPDX-License-Identifier: Apache-2.0
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
Bundle size analysis utilities for comparing web-component vs Dash component.

Measures:
- Total bundle size (uncompressed and gzipped)
- Individual chunk sizes
- CSS extraction status
- Source map sizes
"""

from dataclasses import dataclass
import gzip
import json
from pathlib import Path


@dataclass
class BundleMetrics:
    """Metrics for a single bundle/chunk."""

    name: str
    size_bytes: int
    size_gzipped: int
    is_css: bool = False
    is_sourcemap: bool = False

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024

    @property
    def size_gzipped_kb(self) -> float:
        return self.size_gzipped / 1024

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "size_kb": round(self.size_kb, 2),
            "size_gzipped_bytes": self.size_gzipped,
            "size_gzipped_kb": round(self.size_gzipped_kb, 2),
            "is_css": self.is_css,
            "is_sourcemap": self.is_sourcemap,
        }


@dataclass
class BundleAnalysis:
    """Complete bundle analysis for an approach."""

    approach: str  # "web-component" or "dash-component"
    total_size_bytes: int
    total_size_gzipped: int
    js_size_bytes: int
    css_size_bytes: int
    sourcemap_size_bytes: int
    chunk_count: int
    bundles: list[BundleMetrics]

    @property
    def total_kb(self) -> float:
        return self.total_size_bytes / 1024

    @property
    def total_gzipped_kb(self) -> float:
        return self.total_size_gzipped / 1024

    def to_dict(self) -> dict:
        return {
            "approach": self.approach,
            "total_size_bytes": self.total_size_bytes,
            "total_size_kb": round(self.total_kb, 2),
            "total_size_gzipped_bytes": self.total_size_gzipped,
            "total_size_gzipped_kb": round(self.total_gzipped_kb, 2),
            "js_size_kb": round(self.js_size_bytes / 1024, 2),
            "css_size_kb": round(self.css_size_bytes / 1024, 2),
            "sourcemap_size_kb": round(self.sourcemap_size_bytes / 1024, 2),
            "chunk_count": self.chunk_count,
            "bundles": [b.to_dict() for b in self.bundles],
        }


def get_gzipped_size(file_path: Path) -> int:
    """Calculate gzipped size of a file."""
    with open(file_path, "rb") as f:  # noqa: PTH123
        content = f.read()
    return len(gzip.compress(content, compresslevel=9))


def analyze_bundle(file_path: Path) -> BundleMetrics:
    """Analyze a single bundle file."""
    size = file_path.stat().st_size
    gzipped = get_gzipped_size(file_path)

    is_css = file_path.suffix == ".css"
    is_sourcemap = file_path.suffix == ".map"

    return BundleMetrics(
        name=file_path.name,
        size_bytes=size,
        size_gzipped=gzipped,
        is_css=is_css,
        is_sourcemap=is_sourcemap,
    )


def analyze_web_component(base_path: Path | None = None) -> BundleAnalysis:
    """
    Analyze the web-component build output.

    Expected location: src/ansys/solutions/dashboard/ui/assets/dashboard-app/
    """
    if base_path is None:
        base_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "ansys"
            / "solutions"
            / "dashboard"
            / "ui"
            / "assets"
            / "dashboard-app"
        )

    bundles = []
    js_size = 0
    css_size = 0
    sourcemap_size = 0

    if not base_path.exists():
        raise FileNotFoundError(
            f"Web component build not found at {base_path}. Run 'npm run build' in web-component folder.",
        )

    for file_path in base_path.glob("*"):
        if file_path.is_file() and file_path.suffix in [".js", ".css", ".map"]:
            metrics = analyze_bundle(file_path)
            bundles.append(metrics)

            if metrics.is_sourcemap:
                sourcemap_size += metrics.size_bytes
            elif metrics.is_css:
                css_size += metrics.size_bytes
            else:
                js_size += metrics.size_bytes

    # Filter out sourcemaps for total calculation
    production_bundles = [b for b in bundles if not b.is_sourcemap]
    total_size = sum(b.size_bytes for b in production_bundles)
    total_gzipped = sum(b.size_gzipped for b in production_bundles)

    return BundleAnalysis(
        approach="web-component",
        total_size_bytes=total_size,
        total_size_gzipped=total_gzipped,
        js_size_bytes=js_size,
        css_size_bytes=css_size,
        sourcemap_size_bytes=sourcemap_size,
        chunk_count=len(production_bundles),
        bundles=bundles,
    )


def analyze_dash_component(base_path: Path | None = None) -> BundleAnalysis:
    """
    Analyze the Dash component build output.

    Expected location: projects_dashboard/projects_dashboard/
    """
    if base_path is None:
        base_path = Path(__file__).parent.parent.parent / "projects_dashboard" / "projects_dashboard"

    bundles = []
    js_size = 0
    css_size = 0
    sourcemap_size = 0

    if not base_path.exists():
        raise FileNotFoundError(
            f"Dash component build not found at {base_path}. Run 'npm run build' in projects_dashboard folder.",
        )

    for file_path in base_path.glob("*.js"):
        if file_path.is_file():
            metrics = analyze_bundle(file_path)
            bundles.append(metrics)

            if metrics.is_sourcemap:
                sourcemap_size += metrics.size_bytes
            else:
                js_size += metrics.size_bytes

    for file_path in base_path.glob("*.map"):
        if file_path.is_file():
            metrics = analyze_bundle(file_path)
            bundles.append(metrics)
            sourcemap_size += metrics.size_bytes

    for file_path in base_path.glob("*.css"):
        if file_path.is_file():
            metrics = analyze_bundle(file_path)
            bundles.append(metrics)
            css_size += metrics.size_bytes

    # Filter out sourcemaps for total calculation
    production_bundles = [b for b in bundles if not b.is_sourcemap]
    total_size = sum(b.size_bytes for b in production_bundles)
    total_gzipped = sum(b.size_gzipped for b in production_bundles)

    return BundleAnalysis(
        approach="dash-component",
        total_size_bytes=total_size,
        total_size_gzipped=total_gzipped,
        js_size_bytes=js_size,
        css_size_bytes=css_size,
        sourcemap_size_bytes=sourcemap_size,
        chunk_count=len(production_bundles),
        bundles=bundles,
    )


def compare_bundle_analyses(
    analysis1: BundleAnalysis,
    analysis2: BundleAnalysis,
) -> dict:
    """
    Compare two BundleAnalysis objects directly.

    Args:
        analysis1: First bundle analysis
        analysis2: Second bundle analysis

    Returns:
        Comparison dictionary with size differences
    """

    def calc_diff(val1: float, val2: float) -> dict:
        if val1 == 0:
            return {"diff": 0, "percent": 0, "winner": "tie"}
        diff = val2 - val1
        percent = (diff / val1) * 100
        if val1 < val2:
            winner = analysis1.approach
        elif val2 < val1:
            winner = analysis2.approach
        else:
            winner = "tie"
        return {"diff": round(diff, 2), "percent": round(percent, 1), "winner": winner}

    return {
        "approach1": analysis1.approach,
        "approach2": analysis2.approach,
        "total_size": {
            f"{analysis1.approach}_kb": round(analysis1.total_kb, 2),
            f"{analysis2.approach}_kb": round(analysis2.total_kb, 2),
            **calc_diff(analysis1.total_size_bytes, analysis2.total_size_bytes),
        },
        "total_gzipped": {
            f"{analysis1.approach}_kb": round(analysis1.total_gzipped_kb, 2),
            f"{analysis2.approach}_kb": round(analysis2.total_gzipped_kb, 2),
            **calc_diff(analysis1.total_size_gzipped, analysis2.total_size_gzipped),
        },
        "js_size": {
            f"{analysis1.approach}_kb": round(analysis1.js_size_bytes / 1024, 2),
            f"{analysis2.approach}_kb": round(analysis2.js_size_bytes / 1024, 2),
            **calc_diff(analysis1.js_size_bytes, analysis2.js_size_bytes),
        },
    }


def compare_bundles() -> dict:
    """
    Compare bundle sizes between both approaches.

    Returns a comparison report as a dictionary.
    """
    try:
        web_component = analyze_web_component()
    except FileNotFoundError as e:
        web_component = None
        web_error = str(e)
    else:
        web_error = None

    try:
        dash_component = analyze_dash_component()
    except FileNotFoundError as e:
        dash_component = None
        dash_error = str(e)
    else:
        dash_error = None

    report = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "web_component": web_component.to_dict() if web_component else {"error": web_error},
        "dash_component": dash_component.to_dict() if dash_component else {"error": dash_error},
    }

    if web_component and dash_component:
        report["comparison"] = {
            "size_difference_kb": round(dash_component.total_kb - web_component.total_kb, 2),
            "size_difference_percent": (
                round(
                    (dash_component.total_size_bytes - web_component.total_size_bytes)
                    / web_component.total_size_bytes
                    * 100,
                    1,
                )
                if web_component.total_size_bytes > 0
                else 0
            ),
            "gzipped_difference_kb": round(dash_component.total_gzipped_kb - web_component.total_gzipped_kb, 2),
            "smaller_approach": (
                "web-component"
                if web_component.total_size_bytes < dash_component.total_size_bytes
                else "dash-component"
            ),
        }

    return report


if __name__ == "__main__":
    print("=" * 60)
    print("Bundle Size Analysis: Web Component vs Dash Component")
    print("=" * 60)

    report = compare_bundles()
    print(json.dumps(report, indent=2))
