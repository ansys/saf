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
Performance Comparison Report Generator.

Aggregates results from bundle analysis, Web Vitals, and memory profiling
to create a comprehensive comparison report.

Usage:
    python -m tests.performance.report_generator --output report.json
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Optional

from .bundle_analyzer import BundleAnalysis, compare_bundle_analyses
from .memory_profiler import MemoryProfile, compare_memory_profiles
from .web_vitals import WebVitalsAnalysis, compare_web_vitals


@dataclass
class PerformanceComparison:
    """Complete performance comparison between two approaches."""

    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    approach1: str = "web-component"
    approach2: str = "dash-component"

    # Individual results
    bundle_analysis_1: BundleAnalysis | None = None
    bundle_analysis_2: BundleAnalysis | None = None
    web_vitals_1: WebVitalsAnalysis | None = None
    web_vitals_2: WebVitalsAnalysis | None = None
    memory_profile_1: MemoryProfile | None = None
    memory_profile_2: MemoryProfile | None = None

    def get_bundle_comparison(self) -> dict | None:
        """Get bundle size comparison if both analyses available."""
        if self.bundle_analysis_1 and self.bundle_analysis_2:
            return compare_bundle_analyses(self.bundle_analysis_1, self.bundle_analysis_2)
        return None

    def get_web_vitals_comparison(self) -> dict | None:
        """Get Web Vitals comparison if both analyses available."""
        if self.web_vitals_1 and self.web_vitals_2:
            return compare_web_vitals(self.web_vitals_1, self.web_vitals_2)
        return None

    def get_memory_comparison(self) -> dict | None:
        """Get memory profile comparison if both profiles available."""
        if self.memory_profile_1 and self.memory_profile_2:
            return compare_memory_profiles(self.memory_profile_1, self.memory_profile_2)
        return None

    def get_overall_winner(self) -> dict:
        """Determine overall winner based on weighted scoring."""
        scores = {self.approach1: 0, self.approach2: 0}
        categories = []

        # Bundle size (weight: 25%)
        bundle_comp = self.get_bundle_comparison()
        if bundle_comp:
            winner = bundle_comp.get("total_size", {}).get("winner")
            if winner and winner != "tie":
                scores[winner] += 25
                categories.append(("Bundle Size", winner))

        # LCP (weight: 25%)
        vitals_comp = self.get_web_vitals_comparison()
        if vitals_comp:
            lcp_winner = vitals_comp.get("lcp_comparison", {}).get("winner")
            if lcp_winner and lcp_winner != "tie":
                scores[lcp_winner] += 25
                categories.append(("LCP", lcp_winner))

            # TBT (weight: 15%)
            tbt_winner = vitals_comp.get("tbt_comparison", {}).get("winner")
            if tbt_winner and tbt_winner != "tie":
                scores[tbt_winner] += 15
                categories.append(("TBT", tbt_winner))

            # CLS (weight: 10%)
            cls_winner = vitals_comp.get("cls_comparison", {}).get("winner")
            if cls_winner and cls_winner != "tie":
                scores[cls_winner] += 10
                categories.append(("CLS", cls_winner))

        # Memory (weight: 25%)
        memory_comp = self.get_memory_comparison()
        if memory_comp:
            heap_1 = memory_comp.get("heap_comparison", {}).get(f"{self.approach1}_peak_mb", 0)
            heap_2 = memory_comp.get("heap_comparison", {}).get(f"{self.approach2}_peak_mb", 0)
            if heap_1 < heap_2:
                scores[self.approach1] += 25
                categories.append(("Memory", self.approach1))
            elif heap_2 < heap_1:
                scores[self.approach2] += 25
                categories.append(("Memory", self.approach2))

        overall_winner = (
            self.approach1
            if scores[self.approach1] > scores[self.approach2]
            else self.approach2
            if scores[self.approach2] > scores[self.approach1]
            else "tie"
        )

        return {
            "scores": scores,
            "category_winners": categories,
            "overall_winner": overall_winner,
            "margin": abs(scores[self.approach1] - scores[self.approach2]),
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "meta": {
                "generated_at": self.generated_at,
                "approaches": [self.approach1, self.approach2],
            },
            "individual_results": {
                "bundle_analysis": {
                    self.approach1: self.bundle_analysis_1.to_dict() if self.bundle_analysis_1 else None,
                    self.approach2: self.bundle_analysis_2.to_dict() if self.bundle_analysis_2 else None,
                },
                "web_vitals": {
                    self.approach1: self.web_vitals_1.to_dict() if self.web_vitals_1 else None,
                    self.approach2: self.web_vitals_2.to_dict() if self.web_vitals_2 else None,
                },
                "memory_profile": {
                    self.approach1: self.memory_profile_1.to_dict() if self.memory_profile_1 else None,
                    self.approach2: self.memory_profile_2.to_dict() if self.memory_profile_2 else None,
                },
            },
            "comparisons": {
                "bundle": self.get_bundle_comparison(),
                "web_vitals": self.get_web_vitals_comparison(),
                "memory": self.get_memory_comparison(),
            },
            "overall": self.get_overall_winner(),
        }

    def to_markdown(self) -> str:
        """Generate a markdown report."""
        lines = [
            "# Performance Comparison Report",
            f"Generated: {self.generated_at}",
            "",
            f"Comparing: **{self.approach1}** vs **{self.approach2}**",
            "",
        ]

        # Summary table
        overall = self.get_overall_winner()
        lines.extend(
            [
                "## Summary",
                "",
                f"**Overall Winner: {overall['overall_winner']}** (margin: {overall['margin']} points)",
                "",
                "| Category | Winner |",
                "|----------|--------|",
            ],
        )
        for category, winner in overall["category_winners"]:
            lines.append(f"| {category} | {winner} |")

        lines.append("")

        # Bundle Size Section
        bundle_comp = self.get_bundle_comparison()
        if bundle_comp:
            lines.extend(
                [
                    "## Bundle Size Analysis",
                    "",
                    "| Metric | " + self.approach1 + " | " + self.approach2 + " | Difference |",
                    "|--------|------|------|------------|",
                ],
            )
            total = bundle_comp.get("total_size", {})
            lines.append(
                f"| Total Size | {total.get(f'{self.approach1}_kb', 'N/A')} KB | "
                f"{total.get(f'{self.approach2}_kb', 'N/A')} KB | "
                f"{total.get('percent', 0):+.1f}% |",
            )
            gzipped = bundle_comp.get("total_gzipped", {})
            lines.append(
                f"| Gzipped | {gzipped.get(f'{self.approach1}_kb', 'N/A')} KB | "
                f"{gzipped.get(f'{self.approach2}_kb', 'N/A')} KB | "
                f"{gzipped.get('percent', 0):+.1f}% |",
            )
            lines.append("")

        # Web Vitals Section
        vitals_comp = self.get_web_vitals_comparison()
        if vitals_comp:
            lines.extend(
                [
                    "## Core Web Vitals",
                    "",
                    "| Metric | " + self.approach1 + " | " + self.approach2 + " | Difference | Winner |",
                    "|--------|------|------|------------|--------|",
                ],
            )

            lcp = vitals_comp.get("lcp_comparison", {})
            lines.append(
                f"| LCP | {lcp.get(f'{self.approach1}_ms', 'N/A')} ms | "
                f"{lcp.get(f'{self.approach2}_ms', 'N/A')} ms | "
                f"{lcp.get('percent', 0):+.1f}% | {lcp.get('winner', 'tie')} |",
            )

            tbt = vitals_comp.get("tbt_comparison", {})
            lines.append(
                f"| TBT | {tbt.get(f'{self.approach1}_ms', 'N/A')} ms | "
                f"{tbt.get(f'{self.approach2}_ms', 'N/A')} ms | "
                f"{tbt.get('percent', 0):+.1f}% | {tbt.get('winner', 'tie')} |",
            )

            cls = vitals_comp.get("cls_comparison", {})
            lines.append(
                f"| CLS | {cls.get(self.approach1, 'N/A')} | "
                f"{cls.get(self.approach2, 'N/A')} | "
                f"{cls.get('percent', 0):+.1f}% | {cls.get('winner', 'tie')} |",
            )
            lines.append("")

        # Memory Section
        memory_comp = self.get_memory_comparison()
        if memory_comp:
            heap = memory_comp.get("heap_comparison", {})
            lines.extend(
                [
                    "## Memory Profile",
                    "",
                    "| Metric | " + self.approach1 + " | " + self.approach2 + " |",
                    "|--------|------|------|",
                    f"| Initial Heap | {heap.get(f'{self.approach1}_initial_mb', 'N/A')} MB | "
                    f"{heap.get(f'{self.approach2}_initial_mb', 'N/A')} MB |",
                    f"| Peak Heap | {heap.get(f'{self.approach1}_peak_mb', 'N/A')} MB | "
                    f"{heap.get(f'{self.approach2}_peak_mb', 'N/A')} MB |",
                    f"| Heap Growth | {heap.get(f'{self.approach1}_growth_mb', 'N/A')} MB | "
                    f"{heap.get(f'{self.approach2}_growth_mb', 'N/A')} MB |",
                    "",
                ],
            )

            recommendations = memory_comp.get("recommendations", [])
            if recommendations:
                lines.append("### Recommendations")
                for rec in recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

        return "\n".join(lines)


def generate_report(
    output_path: Path | None = None,
    bundle_1: BundleAnalysis | None = None,
    bundle_2: BundleAnalysis | None = None,
    vitals_1: WebVitalsAnalysis | None = None,
    vitals_2: WebVitalsAnalysis | None = None,
    memory_1: MemoryProfile | None = None,
    memory_2: MemoryProfile | None = None,
    format: str = "json",  # "json" or "markdown"
) -> str:
    """
    Generate a performance comparison report.

    Args:
        output_path: Optional path to write the report
        bundle_1, bundle_2: Bundle analyses for each approach
        vitals_1, vitals_2: Web Vitals analyses for each approach
        memory_1, memory_2: Memory profiles for each approach
        format: Output format ("json" or "markdown")

    Returns:
        Report content as string
    """
    comparison = PerformanceComparison(
        bundle_analysis_1=bundle_1,
        bundle_analysis_2=bundle_2,
        web_vitals_1=vitals_1,
        web_vitals_2=vitals_2,
        memory_profile_1=memory_1,
        memory_profile_2=memory_2,
    )

    content = comparison.to_markdown() if format == "markdown" else json.dumps(comparison.to_dict(), indent=2)

    if output_path:
        output_path.write_text(content)
        print(f"Report written to: {output_path}")

    return content


def main():
    """CLI entry point for report generation."""
    parser = argparse.ArgumentParser(description="Generate performance comparison report")
    parser.add_argument("--output", "-o", type=Path, help="Output file path")
    parser.add_argument("--format", "-f", choices=["json", "markdown"], default="json", help="Output format")
    parser.add_argument("--bundle-1", type=Path, help="Bundle analysis JSON for approach 1")
    parser.add_argument("--bundle-2", type=Path, help="Bundle analysis JSON for approach 2")
    parser.add_argument("--vitals-1", type=Path, help="Web Vitals JSON for approach 1")
    parser.add_argument("--vitals-2", type=Path, help="Web Vitals JSON for approach 2")
    parser.add_argument("--memory-1", type=Path, help="Memory profile JSON for approach 1")
    parser.add_argument("--memory-2", type=Path, help="Memory profile JSON for approach 2")

    parser.parse_args()

    # Load any provided JSON files
    # (In a real implementation, you'd deserialize these back to dataclasses)

    print("Performance Report Generator")
    print("=" * 40)
    print("This tool generates comparison reports from collected metrics.")
    print("\nTo collect metrics, run:")
    print("  1. Bundle analysis: python -m tests.performance.bundle_analyzer")
    print("  2. Web Vitals: python -m tests.performance.web_vitals")
    print("  3. Memory profiling: python -m tests.performance.memory_profiler")
    print("\nThen provide the output files to this command.")


if __name__ == "__main__":
    main()
