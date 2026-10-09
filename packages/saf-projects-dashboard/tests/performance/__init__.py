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
Performance testing utilities for comparing web-component vs Dash component approaches.

This module provides tools to measure:
- Bundle sizes and build times
- Core Web Vitals (LCP, TBT, CLS)
- Memory usage and potential leaks
- Network efficiency and callback patterns
- Re-render counts and optimization effectiveness

Usage:
    from tests.performance import bundle_analyzer, web_vitals, memory_profiler
    from tests.performance.report_generator import generate_report
"""

from .bundle_analyzer import (
    BundleAnalysis,
    BundleMetrics,
    analyze_bundle,
    analyze_dash_component,
    compare_bundle_analyses,
    compare_bundles,
)
from .memory_profiler import MemoryProfile, MemorySnapshot, compare_memory_profiles, profile_memory, sync_profile_memory
from .report_generator import PerformanceComparison, generate_report
from .web_vitals import (
    WebVitalsAnalysis,
    WebVitalsMetrics,
    compare_web_vitals,
    measure_web_vitals,
    run_web_vitals_benchmark,
    sync_run_benchmark,
)

__all__ = [
    # Bundle analysis
    "BundleMetrics",
    "BundleAnalysis",
    "analyze_bundle",
    "analyze_dash_component",
    "compare_bundles",
    "compare_bundle_analyses",
    # Web Vitals
    "WebVitalsMetrics",
    "WebVitalsAnalysis",
    "measure_web_vitals",
    "run_web_vitals_benchmark",
    "compare_web_vitals",
    "sync_run_benchmark",
    # Memory profiling
    "MemorySnapshot",
    "MemoryProfile",
    "profile_memory",
    "compare_memory_profiles",
    "sync_profile_memory",
    # Report generation
    "PerformanceComparison",
    "generate_report",
]
