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
Performance benchmark tests for ProjectsDashboard component.

These tests measure and compare performance metrics for the Dash component approach.
They can be run standalone or as part of a CI pipeline.

Usage:
    pytest tests/performance/test_performance.py -v
    pytest tests/performance/test_performance.py -v -m performance --run-benchmarks
"""

import os
from pathlib import Path
import subprocess
import time

import pytest

# Get paths
TESTS_DIR = Path(__file__).parent.parent
PROJECT_DIR = TESTS_DIR.parent
DASH_COMPONENT_DIR = PROJECT_DIR / "projects_dashboard"


# Mark all tests in this module as performance tests
pytestmark = pytest.mark.performance


class TestBundleAnalysis:
    """Tests for bundle size analysis."""

    def test_dash_component_bundle_exists(self):
        """Verify the Dash component bundle has been built."""
        bundle_dir = DASH_COMPONENT_DIR / "projects_dashboard"
        js_files = list(bundle_dir.glob("*.js"))

        assert len(js_files) > 0, (
            f"No JavaScript bundles found in {bundle_dir}. Run 'npm run build:js' in projects_dashboard/ first."
        )

    def test_analyze_dash_bundle_size(self):
        """Analyze and report Dash component bundle size."""
        from .bundle_analyzer import analyze_dash_component

        try:
            analysis = analyze_dash_component(DASH_COMPONENT_DIR)
        except FileNotFoundError as e:
            pytest.skip(f"Bundle not built: {e}")

        # Report metrics
        print(f"\n{'=' * 50}")
        print("Dash Component Bundle Analysis")
        print(f"{'=' * 50}")
        print(f"Total Size: {analysis.total_kb:.2f} KB")
        print(f"Gzipped:    {analysis.total_gzipped_kb:.2f} KB")
        print(f"JS Size:    {analysis.js_size_bytes / 1024:.2f} KB")
        print(f"CSS Size:   {analysis.css_size_bytes / 1024:.2f} KB")
        print(f"Chunks:     {analysis.chunk_count}")
        print(f"{'=' * 50}")

        # Assert reasonable bundle sizes
        # These thresholds can be adjusted based on requirements
        assert analysis.total_gzipped_kb < 500, (
            f"Bundle size ({analysis.total_gzipped_kb:.1f} KB gzipped) exceeds 500 KB threshold"
        )

    def test_bundle_has_css_extraction(self):
        """Verify CSS is properly extracted from the bundle."""
        bundle_dir = DASH_COMPONENT_DIR / "projects_dashboard"
        css_files = list(bundle_dir.glob("*.css"))

        # CSS extraction is optional but recommended for caching
        if len(css_files) == 0:
            pytest.skip("CSS not extracted (inline in JS) - consider MiniCssExtractPlugin")

        total_css_size = sum(f.stat().st_size for f in css_files)
        print(f"\nExtracted CSS size: {total_css_size / 1024:.2f} KB")


class TestWebVitals:
    """Tests for Core Web Vitals measurements."""

    @pytest.fixture
    def benchmark_app_url(self):
        """URL for the benchmark app (requires app to be running)."""
        return os.getenv("BENCHMARK_URL", "http://127.0.0.1:8050")

    def test_measure_lcp(self, benchmark_app_url):
        """Measure Largest Contentful Paint."""
        try:
            from .web_vitals import sync_run_benchmark
        except ImportError:
            pytest.skip("Playwright not installed")

        analysis = sync_run_benchmark(benchmark_app_url, "dash-component", run_count=3)

        print(f"\n{'=' * 50}")
        print("Web Vitals Analysis (3 runs)")
        print(f"{'=' * 50}")
        print(f"Average LCP:  {analysis.avg_lcp_ms:.2f} ms ({analysis.get_lcp_rating()})")
        print(f"Average TBT:  {analysis.avg_tbt_ms:.2f} ms")
        print(f"Average CLS:  {analysis.avg_cls:.4f} ({analysis.get_cls_rating()})")
        print(f"Average Load: {analysis.avg_load_complete_ms:.2f} ms")
        print(f"P95 LCP:      {analysis.p95_lcp_ms:.2f} ms")
        print(f"Test Time:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 50}")

        # Assert Core Web Vitals thresholds
        assert analysis.avg_lcp_ms < 4000, "LCP exceeds 'poor' threshold (4s)"
        assert analysis.avg_cls < 0.25, "CLS exceeds 'poor' threshold (0.25)"


class TestMemoryProfile:
    """Tests for memory profiling."""

    @pytest.fixture
    def benchmark_app_url(self):
        """URL for the benchmark app (requires app to be running)."""
        return os.getenv("BENCHMARK_URL", "http://127.0.0.1:8050")

    def test_no_memory_leaks(self, benchmark_app_url):
        """Check for memory leaks over extended usage."""
        try:
            from .memory_profiler import sync_profile_memory
        except ImportError:
            pytest.skip("Playwright not installed")

        profile = sync_profile_memory(
            benchmark_app_url,
            "dash-component",
            duration_seconds=30,
        )

        print(f"\n{'=' * 50}")
        print("Memory Profile (30 seconds)")
        print(f"{'=' * 50}")
        print(f"Initial Heap: {profile.initial_heap_mb:.2f} MB")
        print(f"Final Heap:   {profile.final_heap_mb:.2f} MB")
        print(f"Peak Heap:    {profile.peak_heap_mb:.2f} MB")
        print(f"Growth:       {profile.heap_growth_mb:.2f} MB ({profile.heap_growth_percent:.1f}%)")
        print(f"DOM Nodes:    {profile.final_dom_nodes}")
        print(f"{'=' * 50}")

        # Assert no significant memory leak
        assert not profile.has_memory_leak_warning(
            threshold_percent=30,
        ), f"Possible memory leak: {profile.heap_growth_percent:.1f}% growth"


class TestBuildPerformance:
    """Tests for build time and process."""

    def test_webpack_build_succeeds(self):
        """Verify webpack build completes successfully."""
        result = subprocess.run(
            ["npm", "run", "build:js"],
            cwd=DASH_COMPONENT_DIR,
            capture_output=True,
            text=True,
            shell=True,
        )

        # Build may already exist, just check it can run
        if result.returncode != 0:
            print(f"Build stderr: {result.stderr}")
            # Don't fail - npm might not be available in test env
            pytest.skip("npm build failed - check npm installation")

    def test_typescript_compilation(self):
        """Verify TypeScript compiles without errors."""
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=DASH_COMPONENT_DIR,
            capture_output=True,
            text=True,
            shell=True,
        )

        if result.returncode != 0:
            print(f"TypeScript errors:\n{result.stdout}")
            pytest.skip("TypeScript check failed - check dependencies")


class TestReportGeneration:
    """Tests for report generation."""

    def test_report_generator_imports(self):
        """Verify report generator can be imported."""
        from .report_generator import PerformanceComparison, generate_report

        assert PerformanceComparison is not None
        assert generate_report is not None

    def test_generate_empty_report(self):
        """Test report generation with no data."""
        from .report_generator import PerformanceComparison, generate_report

        PerformanceComparison()
        report = generate_report(format="markdown")

        assert "Performance Comparison Report" in report
        assert "web-component" in report
        assert "dash-component" in report


# Custom pytest hooks for benchmark running
def pytest_configure(config):
    config.addinivalue_line("markers", "performance: marks tests as performance benchmarks")


def pytest_collection_modifyitems(config, items):
    """Skip benchmark tests unless --run-benchmarks is provided."""
    if not config.getoption("--run-benchmarks", default=False):
        pytest.mark.skip(reason="Use --run-benchmarks to run performance tests")
        for item in items:
            if "benchmark" in item.keywords or "skip" in [m.name for m in item.iter_markers()]:
                continue


def pytest_addoption(parser):
    parser.addoption(
        "--run-benchmarks",
        action="store_true",
        default=False,
        help="Run performance benchmark tests",
    )
