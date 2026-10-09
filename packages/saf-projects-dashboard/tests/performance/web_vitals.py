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
Web Vitals measurement utilities for performance comparison.

Measures Core Web Vitals:
- LCP (Largest Contentful Paint): Loading performance
- TBT (Total Blocking Time): Interactivity proxy for lab environment
- CLS (Cumulative Layout Shift): Visual stability

Uses Playwright for automated browser testing with Performance API.
"""

import asyncio
from dataclasses import dataclass, field
import statistics

try:
    from playwright.async_api import Page, async_playwright  # type: ignore

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class WebVitalsMetrics:
    """Core Web Vitals measurements for a single page load."""

    # Core Web Vitals
    lcp_ms: float = 0.0  # Largest Contentful Paint
    tbt_ms: float = 0.0  # Total Blocking Time (lab proxy for FID)
    cls: float = 0.0  # Cumulative Layout Shift

    # Additional timing metrics
    fcp_ms: float = 0.0  # First Contentful Paint
    ttfb_ms: float = 0.0  # Time to First Byte
    dom_content_loaded_ms: float = 0.0
    load_complete_ms: float = 0.0

    # Memory metrics (if available)
    js_heap_size_mb: float | None = None
    total_heap_size_mb: float | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "lcp_ms": round(self.lcp_ms, 2),
            "tbt_ms": round(self.tbt_ms, 2),
            "cls": round(self.cls, 4),
            "fcp_ms": round(self.fcp_ms, 2),
            "ttfb_ms": round(self.ttfb_ms, 2),
            "dom_content_loaded_ms": round(self.dom_content_loaded_ms, 2),
            "load_complete_ms": round(self.load_complete_ms, 2),
            "js_heap_size_mb": round(self.js_heap_size_mb, 2) if self.js_heap_size_mb else None,
            "total_heap_size_mb": round(self.total_heap_size_mb, 2) if self.total_heap_size_mb else None,
        }


@dataclass
class WebVitalsAnalysis:
    """Aggregated Web Vitals analysis from multiple runs."""

    approach: str  # "web-component" or "dash-component"
    url: str
    run_count: int
    metrics: list[WebVitalsMetrics] = field(default_factory=list)

    @property
    def avg_lcp_ms(self) -> float:
        return statistics.mean(m.lcp_ms for m in self.metrics) if self.metrics else 0

    @property
    def avg_tbt_ms(self) -> float:
        return statistics.mean(m.tbt_ms for m in self.metrics) if self.metrics else 0

    @property
    def avg_cls(self) -> float:
        return statistics.mean(m.cls for m in self.metrics) if self.metrics else 0

    @property
    def avg_load_complete_ms(self) -> float:
        return statistics.mean(m.load_complete_ms for m in self.metrics) if self.metrics else 0

    @property
    def p95_lcp_ms(self) -> float:
        if not self.metrics:
            return 0
        sorted_values = sorted(m.lcp_ms for m in self.metrics)
        idx = int(len(sorted_values) * 0.95)
        return sorted_values[min(idx, len(sorted_values) - 1)]

    def get_lcp_rating(self) -> str:
        """Get Core Web Vitals rating for LCP."""
        if self.avg_lcp_ms <= 2500:
            return "good"
        elif self.avg_lcp_ms <= 4000:
            return "needs-improvement"
        return "poor"

    def get_cls_rating(self) -> str:
        """Get Core Web Vitals rating for CLS."""
        if self.avg_cls <= 0.1:
            return "good"
        elif self.avg_cls <= 0.25:
            return "needs-improvement"
        return "poor"

    def to_dict(self) -> dict:
        return {
            "approach": self.approach,
            "url": self.url,
            "run_count": self.run_count,
            "summary": {
                "avg_lcp_ms": round(self.avg_lcp_ms, 2),
                "avg_tbt_ms": round(self.avg_tbt_ms, 2),
                "avg_cls": round(self.avg_cls, 4),
                "avg_load_complete_ms": round(self.avg_load_complete_ms, 2),
                "p95_lcp_ms": round(self.p95_lcp_ms, 2),
                "lcp_rating": self.get_lcp_rating(),
                "cls_rating": self.get_cls_rating(),
            },
            "individual_runs": [m.to_dict() for m in self.metrics],
        }


# JavaScript injection scripts for measuring Web Vitals
WEB_VITALS_SCRIPT = """
() => {
    return new Promise((resolve) => {
        const metrics = {
            lcp: 0,
            cls: 0,
            fcp: 0,
            tbt: 0,
            longTasks: [],
        };

        // Observe LCP
        const lcpObserver = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            const lastEntry = entries[entries.length - 1];
            if (lastEntry) {
                metrics.lcp = lastEntry.startTime;
            }
        });
        lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });

        // Observe CLS
        const clsObserver = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (!entry.hadRecentInput) {
                    metrics.cls += entry.value;
                }
            }
        });
        clsObserver.observe({ type: 'layout-shift', buffered: true });

        // Observe FCP
        const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
        if (fcpEntry) {
            metrics.fcp = fcpEntry.startTime;
        }

        // Observe Long Tasks for TBT calculation
        const longTaskObserver = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                // TBT = sum of (long task duration - 50ms) for all long tasks
                if (entry.duration > 50) {
                    metrics.tbt += entry.duration - 50;
                }
            }
        });
        try {
            longTaskObserver.observe({ type: 'longtask', buffered: true });
        } catch (e) {
            // Long task observer may not be available
        }

        // Wait for page to stabilize, then collect metrics
        setTimeout(() => {
            lcpObserver.disconnect();
            clsObserver.disconnect();
            longTaskObserver.disconnect();
            resolve(metrics);
        }, 3000);
    });
}
"""

NAVIGATION_TIMING_SCRIPT = """
() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const memory = performance.memory || {};
    return {
        ttfb: nav ? nav.responseStart - nav.requestStart : 0,
        domContentLoaded: nav ? nav.domContentLoadedEventEnd - nav.navigationStart : 0,
        loadComplete: nav ? nav.loadEventEnd - nav.navigationStart : 0,
        jsHeapSize: memory.usedJSHeapSize || 0,
        totalHeapSize: memory.totalJSHeapSize || 0,
    };
}
"""


async def measure_web_vitals(page: "Page") -> WebVitalsMetrics:
    """
    Measure Web Vitals for the current page.

    Args:
        page: Playwright Page object

    Returns:
        WebVitalsMetrics with all collected measurements
    """
    # Collect Web Vitals using Performance Observer
    vitals = await page.evaluate(WEB_VITALS_SCRIPT)

    # Collect navigation timing
    timing = await page.evaluate(NAVIGATION_TIMING_SCRIPT)

    return WebVitalsMetrics(
        lcp_ms=vitals.get("lcp", 0),
        tbt_ms=vitals.get("tbt", 0),
        cls=vitals.get("cls", 0),
        fcp_ms=vitals.get("fcp", 0),
        ttfb_ms=timing.get("ttfb", 0),
        dom_content_loaded_ms=timing.get("domContentLoaded", 0),
        load_complete_ms=timing.get("loadComplete", 0),
        js_heap_size_mb=timing.get("jsHeapSize", 0) / (1024 * 1024) if timing.get("jsHeapSize") else None,
        total_heap_size_mb=timing.get("totalHeapSize", 0) / (1024 * 1024) if timing.get("totalHeapSize") else None,
    )


async def run_web_vitals_benchmark(
    url: str,
    approach: str,
    run_count: int = 5,
    headless: bool = True,
    throttle_cpu: float | None = None,  # e.g., 4.0 for 4x slowdown
    throttle_network: str | None = None,  # e.g., "slow-3g", "fast-3g"
) -> WebVitalsAnalysis:
    """
    Run multiple Web Vitals measurements for statistical significance.

    Args:
        url: URL to test
        approach: Name identifier ("web-component" or "dash-component")
        run_count: Number of page loads to measure
        headless: Run browser in headless mode
        throttle_cpu: CPU throttling factor (e.g., 4.0 = 4x slower)
        throttle_network: Network throttling preset

    Returns:
        WebVitalsAnalysis with aggregated results
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright is required. Install with: pip install playwright && playwright install")

    analysis = WebVitalsAnalysis(
        approach=approach,
        url=url,
        run_count=run_count,
    )

    async with async_playwright() as p:  # pyright: ignore[reportPossiblyUnboundVariable]
        # Use Chromium for best Performance API support
        browser = await p.chromium.launch(headless=headless)

        for i in range(run_count):
            # Create fresh context for each run (clean cache/state)
            context = await browser.new_context()

            # Apply CPU throttling via CDP if requested
            if throttle_cpu:
                cdp = await context.new_cdp_session(await context.new_page())
                await cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle_cpu})

            page = await context.new_page()

            try:
                # Navigate and wait for network idle
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Measure Web Vitals
                metrics = await measure_web_vitals(page)
                analysis.metrics.append(metrics)

            except Exception as e:
                print(f"Run {i + 1}/{run_count} failed: {e}")
            finally:
                await context.close()

        await browser.close()

    return analysis


def compare_web_vitals(
    analysis1: WebVitalsAnalysis,
    analysis2: WebVitalsAnalysis,
) -> dict:
    """
    Compare Web Vitals between two approaches.

    Returns comparison with percentage differences.
    """

    def calc_diff(val1: float, val2: float) -> dict:
        if val1 == 0:
            return {"diff": 0, "percent": 0, "winner": "tie"}
        diff = val2 - val1
        percent = (diff / val1) * 100
        winner = analysis1.approach if val1 < val2 else analysis2.approach if val2 < val1 else "tie"
        return {"diff": round(diff, 2), "percent": round(percent, 1), "winner": winner}

    return {
        "approach1": analysis1.approach,
        "approach2": analysis2.approach,
        "lcp_comparison": {
            f"{analysis1.approach}_ms": round(analysis1.avg_lcp_ms, 2),
            f"{analysis2.approach}_ms": round(analysis2.avg_lcp_ms, 2),
            **calc_diff(analysis1.avg_lcp_ms, analysis2.avg_lcp_ms),
        },
        "tbt_comparison": {
            f"{analysis1.approach}_ms": round(analysis1.avg_tbt_ms, 2),
            f"{analysis2.approach}_ms": round(analysis2.avg_tbt_ms, 2),
            **calc_diff(analysis1.avg_tbt_ms, analysis2.avg_tbt_ms),
        },
        "cls_comparison": {
            f"{analysis1.approach}": round(analysis1.avg_cls, 4),
            f"{analysis2.approach}": round(analysis2.avg_cls, 4),
            **calc_diff(analysis1.avg_cls, analysis2.avg_cls),
        },
        "load_comparison": {
            f"{analysis1.approach}_ms": round(analysis1.avg_load_complete_ms, 2),
            f"{analysis2.approach}_ms": round(analysis2.avg_load_complete_ms, 2),
            **calc_diff(analysis1.avg_load_complete_ms, analysis2.avg_load_complete_ms),
        },
    }


# Synchronous wrapper for easier pytest integration
def sync_run_benchmark(url: str, approach: str, run_count: int = 5) -> WebVitalsAnalysis:
    """Synchronous wrapper for run_web_vitals_benchmark."""
    return asyncio.run(run_web_vitals_benchmark(url, approach, run_count))
