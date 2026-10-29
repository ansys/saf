# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "ansys-saf-cli",
#     "packaging>=24.2",
#     "pytest>=9.0.3,<10",
#     "python-dotenv>=1.0.0,<2",
#     "tomlkit>=0.14.0,<1.0.0",
# ]
#
# [tool.uv.sources]
# ansys-saf-cli = { path = "..", editable = true }
# ///

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

script = Path(__file__).resolve().with_name("upgrade_solution_template_uv_lock.py")
spec = importlib.util.spec_from_file_location("upgrade_solution_template_uv_lock", script)
assert spec is not None
assert spec.loader is not None
updater = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = updater
spec.loader.exec_module(updater)


class TestLockfileUpdater:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch
        self.root = tmp_path
        self.lock_dir = self.root / "templates" / "lock_files"
        self.source = self.lock_dir / "dash" / "uv.lock"
        self.source.parent.mkdir(parents=True)
        self.write_lock(self.source, "1.0", "1.5")
        self.solution = self.root / "solution"
        self.solution.mkdir()
        (self.solution / "pyproject.toml").write_text(
            '[project]\nname = "solution"\nversion = "0.1.0"\ndependencies = ["parent>=1"]\n'
            '[project.optional-dependencies]\nextra = ["direct_extra>=1"]\n'
            '[dependency-groups]\ntests = ["direct_test>=1", { include-group = "other" }]\n'
            'other = ["direct_other>=1"]\n',
        )
        self.alert = updater.Alert(
            1,
            "https://github.com/ansys/saf/security/dependabot/1",
            "templates/lock_files/dash/uv.lock",
            "child",
            "GHSA-test",
            "high",
            "<2.0",
            "2.0",
        )
        monkeypatch.setattr(updater, "REPOSITORY_DIR", self.root)
        monkeypatch.setattr(updater, "LOCK_DIR", self.lock_dir)
        monkeypatch.setattr(updater, "TEMPLATE_DIR", self.root)
        monkeypatch.setattr(updater, "SOLUTION_TEMPLATE_PATH", self.root)
        monkeypatch.setattr(updater, "UI_FRAMEWORKS", ["dash"])

    @staticmethod
    def write_lock(path: Path, *versions: str) -> None:
        path.write_text(
            '[[package]]\nname = "solution"\nversion = "0.1.0"\nsource = { editable = "." }\n\n'
            + "".join(f'[[package]]\nname = "child"\nversion = "{version}"\n\n' for version in versions),
            encoding="utf-8",
        )

    def test_all_locked_versions_and_disjoint_ranges(self) -> None:
        alert = replace(self.alert, affected=">=1.0, <2.0 || >=3.0, <3.2")
        assert updater.is_affected(alert, ["2.1", "3.1"])
        assert not updater.is_affected(alert, ["2.1", "3.2"])
        assert not updater.is_affected(alert, [])

    def test_range_syntax_and_prereleases(self) -> None:
        assert updater.is_affected(replace(self.alert, affected="= 1.0"), ["1.0"])
        assert not updater.is_affected(replace(self.alert, affected="= 1.0"), ["1.1"])
        assert updater.is_affected(replace(self.alert, affected="< 2.0"), ["2.0rc1"])
        assert not updater.is_affected(replace(self.alert, affected=">= 2.0"), ["2.0rc1"])
        with pytest.raises(ValueError, match="Unsupported vulnerable version range"):
            updater.is_affected(replace(self.alert, affected="~> 1.0"), ["1.0"])

    def test_direct_dependencies_cover_all_pyproject_tables(self) -> None:
        assert updater.direct_dependencies(self.solution / "pyproject.toml") == {
            "parent",
            "direct-extra",
            "direct-test",
            "direct-other",
        }

    def test_template_lock_templates_solution_package(self) -> None:
        self.write_lock(self.solution / "uv.lock", "2.0")
        content = updater.to_template_lock(self.solution / "uv.lock")
        assert 'name = "{{ cookiecutter.__pkg_name }}"' in content
        assert 'version = "{{ cookiecutter.__version }}"' in content
        assert 'name = "solution"' not in content
        assert "\r" not in content
        self.source.write_text('[[package]]\nname = "child"\nversion = "1.0"\n', encoding="utf-8")
        with pytest.raises(RuntimeError, match="exactly one editable solution package"):
            updater.to_template_lock(self.source)

    def test_markdown_report_saved_under_repository_root(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self.write_lock(self.solution / "uv.lock", "2.0")
        alert = replace(self.alert, advisory="GHSA-test-\u00e9")
        updater.report_alerts(
            [alert],
            {1: "REMEDIATED in proposed lockfile"},
            {"dash": self.solution / "uv.lock"},
        )
        report = self.root / "dist" / "solution-template-dependabot-report.md"
        contents = report.read_text(encoding="utf-8")
        assert "# Solution-template Dependabot report" in contents
        assert alert.advisory in contents
        assert alert.url in contents
        assert alert.manifest in contents
        assert "- Before: 1.0, 1.5" in contents
        assert "- After (staged): 2.0" in contents
        assert "&lt;2.0" in contents
        assert "REMEDIATED" in contents
        output = capsys.readouterr().out
        assert str(report) in output
        assert alert.url not in output

    def test_empty_inventory_replaces_previous_report(self) -> None:
        updater.report_alerts([self.alert], {1: "PLANNED"}, {}, dry_run=True)
        self.monkeypatch.setattr(updater, "fetch_alerts", lambda repository: [])
        assert updater.update_lockfiles([], True, "ansys/saf", True) == 0
        contents = (self.root / "dist" / "solution-template-dependabot-report.md").read_text(encoding="utf-8")
        assert "No matching open Dependabot alerts" in contents
        assert "Dry run" in contents
        assert "GHSA-test" not in contents

    def test_plan_filters_direct_unpatched_safe_and_unsupported(self) -> None:
        direct = replace(self.alert, number=2, package="direct-test")
        unpatched = replace(self.alert, number=3, patched=None)
        safe = replace(self.alert, number=4, affected="<1.0")
        unsupported = replace(self.alert, number=5, manifest="templates/lock_files/other/uv.lock")
        with self.source.open("a") as stream:
            stream.write('[[package]]\nname = "direct_test"\nversion = "1.0"\n')
        updates, statuses = updater.plan_updates(
            [self.alert, direct, unpatched, safe, unsupported],
            {"dash": self.solution},
        )
        assert updates == {"dash": {"child"}}
        assert "direct dependency" in statuses[2]
        assert "no patched version" in statuses[3]
        assert statuses[4].startswith("ALREADY SAFE")
        assert "unsupported" in statuses[5]

    def test_fetch_pagination_and_exact_scope(self) -> None:
        def item(number: int, manifest: str) -> dict[str, object]:
            return {
                "number": number,
                "state": "open",
                "html_url": self.alert.url,
                "dependency": {"manifest_path": manifest, "package": {"ecosystem": "pip", "name": "Child"}},
                "security_advisory": {"ghsa_id": "GHSA-test", "severity": "high"},
                "security_vulnerability": {
                    "vulnerable_version_range": "<2.0",
                    "first_patched_version": {"identifier": "2.0"},
                },
            }

        payload = [
            [item(1, self.alert.manifest)],
            [
                item(2, self.alert.manifest),
                item(3, "packages/other/uv.lock"),
                item(4, "templates/lock_files-extra/dash/uv.lock"),
            ],
        ]
        result = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        commands: list[list[str]] = []

        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return result

        self.monkeypatch.setattr(updater.shutil, "which", lambda name: "gh")
        self.monkeypatch.setattr(updater.subprocess, "run", run)
        alerts = updater.fetch_alerts("ansys/saf")
        assert [alert.number for alert in alerts] == [1, 2]
        assert len(commands) == 1
        assert "--slurp" in commands[0]
        assert "--paginate" in commands[0]

    def test_fetch_decodes_utf8_output_independently_of_windows_locale(self) -> None:
        payload = [
            [
                {
                    "number": 1,
                    "state": "open",
                    "html_url": self.alert.url,
                    "dependency": {
                        "manifest_path": self.alert.manifest,
                        "package": {"ecosystem": "pip", "name": "child"},
                    },
                    "security_advisory": {
                        "ghsa_id": self.alert.advisory,
                        "severity": self.alert.severity,
                        "description": "Unicode advisory: \U0001f510",
                    },
                    "security_vulnerability": {
                        "vulnerable_version_range": self.alert.affected,
                        "first_patched_version": {"identifier": self.alert.patched},
                    },
                }
            ]
        ]
        output = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        assert b"\x90" in output
        run_process = subprocess.run

        def run(
            command: list[str],
            *,
            cwd: Path,
            check: bool,
            capture_output: bool,
            text: bool,
            encoding: str,
        ) -> subprocess.CompletedProcess[str]:
            assert encoding == "utf-8"
            return run_process(
                [
                    sys.executable,
                    "-c",
                    f"import sys; sys.stdout.buffer.write({output!r}); "
                    "sys.stderr.buffer.write('Progress: \\U0001f510'.encode('utf-8'))",
                ],
                cwd=cwd,
                check=check,
                capture_output=capture_output,
                text=text,
                encoding=encoding,
            )

        self.monkeypatch.setattr(updater.shutil, "which", lambda name: "gh")
        self.monkeypatch.setattr(updater.subprocess, "run", run)
        assert updater.fetch_alerts("ansys/saf") == [self.alert]

    def test_permission_failure_is_not_empty_inventory(self) -> None:
        def fail(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 403")

        self.monkeypatch.setattr(updater.shutil, "which", lambda name: "gh")
        self.monkeypatch.setattr(updater.subprocess, "run", fail)
        with pytest.raises(subprocess.CalledProcessError):
            updater.fetch_alerts("ansys/saf")

    def test_missing_cli_is_explicit(self) -> None:
        self.monkeypatch.setattr(updater.shutil, "which", lambda name: None)
        with pytest.raises(RuntimeError, match="GitHub CLI is missing"):
            updater.fetch_alerts("ansys/saf")

    def test_empty_inventory_does_not_generate_solutions(self) -> None:
        def unexpected_generation(*args: object) -> None:
            pytest.fail("An empty alert inventory must not generate solutions.")

        self.monkeypatch.setattr(updater, "fetch_alerts", lambda repository: [])
        self.monkeypatch.setattr(updater, "generate_solution", unexpected_generation)
        assert updater.update_lockfiles([], True, "ansys/saf", False) == 0

    def test_planning_and_verification_catch_previously_safe_advisory(self) -> None:
        second = replace(self.alert, number=2, affected=">=2.0,<2.5", patched="2.5")
        alerts = [self.alert, second]
        updates, statuses = updater.plan_updates(alerts, {"dash": self.solution})
        assert updates == {"dash": {"child"}}
        assert statuses[1] == "PLANNED"
        assert statuses[2].startswith("ALREADY SAFE")

        staged_lockfile = self.solution / "uv.lock"
        self.write_lock(staged_lockfile, "2.1")
        assert not updater.verify_alerts(
            alerts,
            statuses,
            {"dash": staged_lockfile},
        )
        assert statuses[1].startswith("REMEDIATED")
        assert statuses[2].startswith("UNRESOLVED")

    def test_failure_in_second_variant_preserves_first(self) -> None:
        second = self.root / "second-solution"
        second.mkdir()
        self.write_lock(self.solution / "uv.lock", "2.0")
        original = self.source.read_bytes()

        def uv(solution: Path, *arguments: str) -> None:
            if solution == second:
                raise subprocess.CalledProcessError(1, ["uv", *arguments])

        self.monkeypatch.setattr(updater, "UI_FRAMEWORKS", ["dash", "none"])
        self.monkeypatch.setattr(
            updater,
            "generate_solution",
            lambda directory, framework: self.solution if framework == "dash" else second,
        )
        self.monkeypatch.setattr(updater, "run_uv", uv)
        with pytest.raises(subprocess.CalledProcessError):
            updater.update_lockfiles(["child"], False, "ansys/saf", False)
        assert self.source.read_bytes() == original

    def run_update(
        self, patched_version: str, dry_run: bool = False, fail: bool = False
    ) -> tuple[int, list[tuple[str, ...]]]:
        calls: list[tuple[str, ...]] = []

        def uv(solution: Path, *arguments: str) -> None:
            calls.append(arguments)
            if fail and "--check" in arguments:
                raise subprocess.CalledProcessError(1, ["uv", *arguments])
            if "--upgrade-package" in arguments:
                self.write_lock(solution / "uv.lock", patched_version)

        self.write_lock(self.solution / "uv.lock", "1.0", "1.5")
        self.monkeypatch.setattr(updater, "fetch_alerts", lambda repository: [self.alert])
        self.monkeypatch.setattr(updater, "generate_solution", lambda directory, framework: self.solution)
        self.monkeypatch.setattr(updater, "run_uv", uv)
        result = updater.update_lockfiles([], True, "ansys/saf", dry_run)
        return result, calls

    def test_verified_update_is_copied_and_lock_only(self) -> None:
        result, calls = self.run_update("2.0")
        assert result == 0
        assert updater.locked_versions(self.source)["child"] == ["2.0"]
        assert calls == [("lock",), ("lock", "--upgrade-package", "child"), ("lock", "--check")]
        content = self.source.read_text(encoding="utf-8")
        assert 'name = "{{ cookiecutter.__pkg_name }}"' in content
        assert 'version = "{{ cookiecutter.__version }}"' in content

    def test_unresolved_alert_does_not_modify_repository(self) -> None:
        original = self.source.read_bytes()
        result, _ = self.run_update("1.9")
        assert result == 1
        assert self.source.read_bytes() == original

    def test_dry_run_does_not_update_or_copy(self) -> None:
        original = self.source.read_bytes()
        result, calls = self.run_update("2.0", dry_run=True)
        assert result == 0
        assert calls == []
        assert self.source.read_bytes() == original
        contents = (self.root / "dist" / "solution-template-dependabot-report.md").read_text(encoding="utf-8")
        assert "Dry run" in contents
        assert "PLANNED" in contents

    def test_uv_validation_failure_refreshes_report_without_copying(self) -> None:
        original = self.source.read_bytes()
        report = self.root / "dist" / "solution-template-dependabot-report.md"
        report.parent.mkdir()
        report.write_text("stale report", encoding="utf-8")
        with pytest.raises(subprocess.CalledProcessError):
            self.run_update("2.0", fail=True)
        assert self.source.read_bytes() == original
        report_contents = report.read_text(encoding="utf-8")
        assert "stale report" not in report_contents
        assert self.alert.url in report_contents
        assert "No lockfiles copied: uv resolution or validation failed." in report_contents
        assert "FAILED: uv command exited with code 1" in report_contents

    def test_manual_mode_preserves_targeted_update(self) -> None:
        self.write_lock(self.solution / "uv.lock", "2.0")
        calls: list[tuple[Path, tuple[str, ...]]] = []

        def uv(solution: Path, *arguments: str) -> None:
            calls.append((solution, arguments))

        self.monkeypatch.setattr(updater, "generate_solution", lambda directory, framework: self.solution)
        self.monkeypatch.setattr(updater, "run_uv", uv)
        assert updater.update_lockfiles(["child"], False, "ansys/saf", False) == 0
        assert calls[1] == (self.solution, ("lock", "--upgrade-package", "child"))


if __name__ == "__main__":
    sys.exit(
        pytest.main(
            [
                "-c",
                str(Path(__file__).resolve().parent.parent / "pyproject.toml"),
                "-o",
                "addopts=",
                "--noconftest",
                str(Path(__file__).resolve()),
                *sys.argv[1:],
            ]
        )
    )
