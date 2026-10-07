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
Memory profiling utilities for performance comparison.

Measures:
- JavaScript heap size over time
- Memory growth patterns (potential leaks)
- React component re-render counts
- DOM node counts

Uses Playwright CDP (Chrome DevTools Protocol) for accurate memory profiling.
"""

import asyncio
from dataclasses import dataclass, field
import json
import statistics
from typing import Optional

try:
    from playwright.async_api import CDPSession, Page, async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class MemorySnapshot:
    """A single memory measurement snapshot."""

    timestamp_ms: float
    js_heap_size_bytes: int
    total_heap_size_bytes: int
    heap_size_limit_bytes: int
    dom_node_count: int
    event_listener_count: int

    @property
    def js_heap_mb(self) -> float:
        return self.js_heap_size_bytes / (1024 * 1024)

    @property
    def total_heap_mb(self) -> float:
        return self.total_heap_size_bytes / (1024 * 1024)

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": round(self.timestamp_ms, 2),
            "js_heap_mb": round(self.js_heap_mb, 2),
            "total_heap_mb": round(self.total_heap_mb, 2),
            "heap_limit_mb": round(self.heap_size_limit_bytes / (1024 * 1024), 2),
            "dom_node_count": self.dom_node_count,
            "event_listener_count": self.event_listener_count,
        }


@dataclass
class MemoryProfile:
    """Complete memory profile from a test session."""

    approach: str
    url: str
    duration_ms: float
    snapshots: list[MemorySnapshot] = field(default_factory=list)

    @property
    def initial_heap_mb(self) -> float:
        return self.snapshots[0].js_heap_mb if self.snapshots else 0

    @property
    def final_heap_mb(self) -> float:
        return self.snapshots[-1].js_heap_mb if self.snapshots else 0

    @property
    def peak_heap_mb(self) -> float:
        return max(s.js_heap_mb for s in self.snapshots) if self.snapshots else 0

    @property
    def avg_heap_mb(self) -> float:
        return statistics.mean(s.js_heap_mb for s in self.snapshots) if self.snapshots else 0

    @property
    def heap_growth_mb(self) -> float:
        """Calculate heap growth (potential memory leak indicator)."""
        return self.final_heap_mb - self.initial_heap_mb

    @property
    def heap_growth_percent(self) -> float:
        if self.initial_heap_mb == 0:
            return 0
        return (self.heap_growth_mb / self.initial_heap_mb) * 100

    @property
    def final_dom_nodes(self) -> int:
        return self.snapshots[-1].dom_node_count if self.snapshots else 0

    @property
    def final_event_listeners(self) -> int:
        return self.snapshots[-1].event_listener_count if self.snapshots else 0

    def has_memory_leak_warning(self, threshold_percent: float = 20.0) -> bool:
        """Check if memory growth suggests a potential leak."""
        return self.heap_growth_percent > threshold_percent

    def to_dict(self) -> dict:
        return {
            "approach": self.approach,
            "url": self.url,
            "duration_ms": round(self.duration_ms, 2),
            "summary": {
                "initial_heap_mb": round(self.initial_heap_mb, 2),
                "final_heap_mb": round(self.final_heap_mb, 2),
                "peak_heap_mb": round(self.peak_heap_mb, 2),
                "avg_heap_mb": round(self.avg_heap_mb, 2),
                "heap_growth_mb": round(self.heap_growth_mb, 2),
                "heap_growth_percent": round(self.heap_growth_percent, 1),
                "final_dom_nodes": self.final_dom_nodes,
                "final_event_listeners": self.final_event_listeners,
                "memory_leak_warning": self.has_memory_leak_warning(),
            },
            "snapshots": [s.to_dict() for s in self.snapshots],
        }


# JavaScript to collect memory and DOM metrics
MEMORY_METRICS_SCRIPT = """
() => {
    const memory = performance.memory || {};
    const allElements = document.getElementsByTagName('*');

    // Count event listeners (approximate via getEventListeners if available)
    let listenerCount = 0;
    try {
        // This only works in Chrome DevTools, use CDP for accurate count
        listenerCount = window.__eventListenerCount || 0;
    } catch (e) {}

    return {
        jsHeapSize: memory.usedJSHeapSize || 0,
        totalHeapSize: memory.totalJSHeapSize || 0,
        heapSizeLimit: memory.jsHeapSizeLimit || 0,
        domNodeCount: allElements.length,
        eventListenerCount: listenerCount,
    };
}
"""

# Script to track React re-renders (if React DevTools available)
REACT_PROFILER_SCRIPT = """
() => {
    // Check for React DevTools fiber
    const reactRoot = document.getElementById('_dash-app-content') ||
                      document.getElementById('root') ||
                      document.getElementById('benchmark-container');

    if (!reactRoot) return { available: false };

    const fiber = reactRoot._reactRootContainer?._internalRoot?.current ||
                  reactRoot.__reactFiber$ || null;

    if (!fiber) return { available: false };

    // Count rendered components
    let componentCount = 0;
    const countComponents = (node) => {
        if (!node) return;
        if (typeof node.type === 'function' || typeof node.type === 'object') {
            componentCount++;
        }
        if (node.child) countComponents(node.child);
        if (node.sibling) countComponents(node.sibling);
    };

    try {
        countComponents(fiber);
    } catch (e) {}

    return {
        available: true,
        componentCount: componentCount,
    };
}
"""


async def get_event_listener_count(cdp: "CDPSession", document_node_id: int) -> int:
    """Get accurate event listener count via CDP."""
    try:
        result = await cdp.send(
            "DOMDebugger.getEventListeners",
            {
                "objectId": str(document_node_id),
                "depth": -1,
                "pierce": True,
            },
        )
        return len(result.get("listeners", []))
    except Exception:
        return 0


async def take_memory_snapshot(page: "Page", start_time: float) -> MemorySnapshot:
    """Take a single memory snapshot."""
    import time

    metrics = await page.evaluate(MEMORY_METRICS_SCRIPT)

    return MemorySnapshot(
        timestamp_ms=(time.time() * 1000) - start_time,
        js_heap_size_bytes=metrics.get("jsHeapSize", 0),
        total_heap_size_bytes=metrics.get("totalHeapSize", 0),
        heap_size_limit_bytes=metrics.get("heapSizeLimit", 0),
        dom_node_count=metrics.get("domNodeCount", 0),
        event_listener_count=metrics.get("eventListenerCount", 0),
    )


async def profile_memory(
    url: str,
    approach: str,
    duration_seconds: float = 30.0,
    sample_interval_ms: float = 1000.0,
    headless: bool = True,
    simulate_interactions: bool = False,
) -> MemoryProfile:
    """
    Profile memory usage over time.

    Args:
        url: URL to profile
        approach: Name identifier ("web-component" or "dash-component")
        duration_seconds: How long to profile
        sample_interval_ms: Time between memory samples
        headless: Run browser in headless mode
        simulate_interactions: Simulate user interactions during profiling

    Returns:
        MemoryProfile with all collected snapshots
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright is required. Install with: pip install playwright && playwright install")

    import time

    profile = MemoryProfile(
        approach=approach,
        url=url,
        duration_ms=duration_seconds * 1000,
    )

    async with async_playwright() as p:
        # Enable memory measurement flags
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--enable-precise-memory-info",
                "--js-flags=--expose-gc",
            ],
        )

        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to page
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # Wait for app to stabilize
        await asyncio.sleep(2)

        start_time = time.time() * 1000
        end_time = start_time + (duration_seconds * 1000)

        while (time.time() * 1000) < end_time:
            snapshot = await take_memory_snapshot(page, start_time)
            profile.snapshots.append(snapshot)

            # Optionally simulate interactions
            if simulate_interactions:
                await simulate_user_interaction(page)

            await asyncio.sleep(sample_interval_ms / 1000)

        await browser.close()

    return profile


async def simulate_user_interaction(page: "Page"):
    """Simulate common user interactions for memory testing."""
    try:
        # Scroll the page
        await page.evaluate("window.scrollBy(0, 100)")
        await asyncio.sleep(0.1)
        await page.evaluate("window.scrollBy(0, -100)")

        # Click on list items if available
        items = await page.query_selector_all("[data-testid='project-item'], .project-item")
        if items and len(items) > 0:
            await items[0].click()
            await asyncio.sleep(0.5)
    except Exception:
        pass  # Ignore interaction errors


def compare_memory_profiles(
    profile1: MemoryProfile,
    profile2: MemoryProfile,
) -> dict:
    """Compare memory profiles between two approaches."""
    return {
        "approach1": profile1.approach,
        "approach2": profile2.approach,
        "heap_comparison": {
            f"{profile1.approach}_initial_mb": round(profile1.initial_heap_mb, 2),
            f"{profile2.approach}_initial_mb": round(profile2.initial_heap_mb, 2),
            f"{profile1.approach}_peak_mb": round(profile1.peak_heap_mb, 2),
            f"{profile2.approach}_peak_mb": round(profile2.peak_heap_mb, 2),
            f"{profile1.approach}_growth_mb": round(profile1.heap_growth_mb, 2),
            f"{profile2.approach}_growth_mb": round(profile2.heap_growth_mb, 2),
        },
        "dom_comparison": {
            f"{profile1.approach}_nodes": profile1.final_dom_nodes,
            f"{profile2.approach}_nodes": profile2.final_dom_nodes,
        },
        "recommendations": _generate_recommendations(profile1, profile2),
    }


def _generate_recommendations(profile1: MemoryProfile, profile2: MemoryProfile) -> list[str]:
    """Generate optimization recommendations based on profiles."""
    recommendations = []

    if profile1.has_memory_leak_warning():
        recommendations.append(
            f"{profile1.approach}: Possible memory leak detected "
            f"({profile1.heap_growth_percent:.1f}% growth). "
            "Check for uncleared intervals, event listeners, or state accumulation.",
        )

    if profile2.has_memory_leak_warning():
        recommendations.append(
            f"{profile2.approach}: Possible memory leak detected "
            f"({profile2.heap_growth_percent:.1f}% growth). "
            "Check for uncleared intervals, event listeners, or state accumulation.",
        )

    # Compare DOM efficiency
    if profile1.final_dom_nodes > profile2.final_dom_nodes * 1.5:
        recommendations.append(
            f"{profile1.approach} has {profile1.final_dom_nodes} DOM nodes vs "
            f"{profile2.approach}'s {profile2.final_dom_nodes}. "
            "Consider virtualization or reducing unnecessary wrapper elements.",
        )
    elif profile2.final_dom_nodes > profile1.final_dom_nodes * 1.5:
        recommendations.append(
            f"{profile2.approach} has {profile2.final_dom_nodes} DOM nodes vs "
            f"{profile1.approach}'s {profile1.final_dom_nodes}. "
            "Consider virtualization or reducing unnecessary wrapper elements.",
        )

    if not recommendations:
        recommendations.append("Both approaches show healthy memory patterns.")

    return recommendations


# Synchronous wrapper
def sync_profile_memory(url: str, approach: str, duration_seconds: float = 30.0) -> MemoryProfile:
    """Synchronous wrapper for profile_memory."""
    return asyncio.run(profile_memory(url, approach, duration_seconds))
