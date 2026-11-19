# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
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

r"""Create or update package OpenVEX documents.

Requires Python 3.11 or newer; no additional dependencies are needed.
The package argument is a directory name under packages, including the separate
saf-sdk package. The distribution name and initial product version are read from
that package's pyproject.toml. Output is VEX/<package>.openvex.json relative to
the repository, regardless of the current working directory.

Creating and updating:
    A new document starts at revision 1 with a UTC creation timestamp and author
    "ANSYS, Inc.". Use --author to override the author of a new document.
    Updates increment the integer document version, preserve the creation
    timestamp, and set last_updated to the UTC update time. Existing document
    metadata and unrelated statements are preserved.

    The same vulnerability name, product PURL, and exact subcomponent PURL set
    identify a replacement statement. Otherwise, a statement is appended.
    Supply the complete replacement, including notes and aliases to retain.
    Advisory aliases are not used to match vulnerability names.
    Different subcomponent versions remain separate assessments.
    Repeat --subcomponent and --alias as needed.
    Without statement options, an existing document's revision and update
    timestamp are refreshed.

Product versions:
    --product-version changes only top-level PyPI product PURLs matching the
    package distribution name, not subcomponent versions, statuses, or
    assessments. It also increments the revision and refreshes last_updated.
    Otherwise, existing product versions are preserved and a new statement uses
    the existing product version. Multiple existing versions require an explicit
    --product-version.
    Reassess statements before applying them to another release: changing the
    version does not prove that earlier assessments remain valid.

Statement requirements:
    Use --vulnerability and --status together. Statuses are not_affected,
    affected, fixed, and under_investigation. not_affected requires a
    justification or impact statement; affected requires an action statement.
    Invalid input fails without replacing the existing file. Validation checks
    the supported document structure, not the complete OpenVEX schema or the
    truth of an assessment. See the options below for individual statement fields.

Examples (PowerShell, from the repository root):
    Add or replace an assessment:
        uv run --no-project scripts\generate_vex.py saf-cli `
            --vulnerability CVE-2026-126190 --alias GHSA-mmhr-3c5m-f64f `
            --status under_investigation --subcomponent pkg:pypi/soupsieve@2.10 `
            --notes "Optional generated-solution doc dependencies on Python below 3.11.5; investigation ongoing."

    Update the product version:
        uv run --no-project scripts\generate_vex.py saf-cli --product-version 4.5.0

    Run the focused tests:
        uv run tests\test_generate_vex.py
"""

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import tempfile
import tomllib
from typing import Any, TypeGuard

ROOT = Path(__file__).resolve().parents[1]
JUSTIFICATIONS = (
    "component_not_present",
    "vulnerable_code_not_present",
    "vulnerable_code_not_in_execute_path",
    "vulnerable_code_cannot_be_controlled_by_adversary",
    "inline_mitigations_already_exist",
)


def nonempty(value: str) -> str:
    """Reject blank command-line values."""
    if not value.strip():
        raise argparse.ArgumentTypeError("Value must not be empty.")
    return value.strip()


def version(value: str) -> str:
    """Require a version suitable for a PyPI product PURL."""
    value = nonempty(value)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", value):
        raise argparse.ArgumentTypeError("Invalid product version.")
    return value


def parser_for_cli() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package", help="Directory name under packages, such as saf-cli.")
    parser.add_argument("--product-version", type=version, help="Update matching top-level product PURLs.")
    parser.add_argument("--vulnerability", type=nonempty, help="CVE or GHSA identifier.")
    parser.add_argument("--alias", action="append", default=[], type=nonempty, help="Repeat for each advisory alias.")
    parser.add_argument("--description", type=nonempty, help="Vulnerability description.")
    parser.add_argument(
        "--status",
        choices=("not_affected", "affected", "fixed", "under_investigation"),
        help="Assessment status; requires --vulnerability.",
    )
    parser.add_argument(
        "--subcomponent", action="append", default=[], type=nonempty, help="Versioned subcomponent PURL; repeatable."
    )
    parser.add_argument(
        "--notes", type=nonempty, help="Status explanation, including environment or optional-group scope."
    )
    parser.add_argument("--justification", choices=JUSTIFICATIONS, help="OpenVEX justification; only for not_affected.")
    parser.add_argument("--impact-statement", type=nonempty, help="Explain why the product is not affected.")
    parser.add_argument("--action-statement", type=nonempty, help="Remediation or mitigation instructions.")
    parser.add_argument(
        "--author", type=nonempty, help="Required only to override the default author for new documents."
    )
    return parser


def product_key(product: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """Identify a product and its exact subcomponent configuration."""
    return (
        product["identifiers"]["purl"],
        tuple(sorted(component["identifiers"]["purl"] for component in product.get("subcomponents", []))),
    )


def statement_key(statement: dict[str, Any]) -> tuple[str, tuple[tuple[str, tuple[str, ...]], ...]]:
    """Keep distinct assessments for different dependency configurations."""
    return statement["vulnerability"]["name"], tuple(sorted(product_key(product) for product in statement["products"]))


def is_object(value: object) -> TypeGuard[dict[str, Any]]:
    """Narrow a decoded JSON object without assuming its field types."""
    return isinstance(value, dict)


def is_array(value: object) -> TypeGuard[list[Any]]:
    """Narrow a decoded JSON array without assuming its item types."""
    return isinstance(value, list)


def validate_document(document: Any) -> None:
    """Reject unsupported or malformed existing documents before modifying them."""
    if not is_object(document):
        raise ValueError("Expected an OpenVEX object.")
    content: dict[str, Any] = document
    if content.get("@context") != "https://openvex.dev/ns/v0.2.0":
        raise ValueError("Expected an OpenVEX v0.2.0 document.")
    revision = content.get("version")
    if type(revision) is not int or revision < 1:
        raise ValueError("Document version must be a positive integer.")
    if not isinstance(content.get("timestamp"), str) or not content["timestamp"]:
        raise ValueError("Document must have a creation timestamp.")
    raw_statements = content.get("statements")
    if not is_array(raw_statements):
        raise ValueError("Document statements must be an array.")
    statements: list[Any] = raw_statements
    for item in statements:
        if not is_object(item):
            raise ValueError("Each statement must be an object.")
        statement: dict[str, Any] = item
        if not isinstance(statement.get("products"), list) or not statement["products"]:
            raise ValueError("Each statement must contain a nonempty products array.")
        try:
            statement_key(statement)
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError(
                "Each statement must identify a vulnerability and products/subcomponents by PURL."
            ) from error


def validate_statement_options(args: argparse.Namespace) -> None:
    """Require evidence fields appropriate to the requested status."""
    if not args.vulnerability:
        if any(
            (
                args.status,
                args.alias,
                args.description,
                args.subcomponent,
                args.notes,
                args.justification,
                args.impact_statement,
                args.action_statement,
            )
        ):
            raise ValueError("Statement options require --vulnerability.")
        return
    if not args.status:
        raise ValueError("--vulnerability requires --status.")
    if args.status == "not_affected" and not (args.justification or args.impact_statement):
        raise ValueError("not_affected requires --justification or --impact-statement.")
    if args.status == "affected" and not args.action_statement:
        raise ValueError("affected requires --action-statement.")
    if args.justification and args.status != "not_affected":
        raise ValueError("--justification applies only to not_affected.")
    for component in args.subcomponent:
        if not re.fullmatch(r"pkg:[^\s@]+@[^\s@]+", component):
            raise ValueError(f"Expected a versioned subcomponent PURL: {component}")


def build_statement(args: argparse.Namespace, purl: str) -> dict[str, Any] | None:
    """Construct an assessment only from explicit caller-supplied evidence."""
    validate_statement_options(args)
    if not args.vulnerability:
        return None
    vulnerability: dict[str, Any] = {"name": args.vulnerability}
    if args.alias:
        vulnerability["aliases"] = sorted(set(args.alias))
    if args.description:
        vulnerability["description"] = args.description
    product: dict[str, Any] = {"identifiers": {"purl": purl}}
    if args.subcomponent:
        product["subcomponents"] = [
            {"identifiers": {"purl": component}} for component in sorted(set(args.subcomponent))
        ]
    statement: dict[str, Any] = {
        "vulnerability": vulnerability,
        "products": [product],
        "status": args.status,
    }
    for option, field in (
        (args.notes, "status_notes"),
        (args.justification, "justification"),
        (args.impact_statement, "impact_statement"),
        (args.action_statement, "action_statement"),
    ):
        if option:
            statement[field] = option
    return statement


def resolve_product_version(statements: list[dict[str, Any]], prefix: str, requested: str | None, initial: str) -> str:
    """Update matching products or retain the version already being assessed."""
    existing_versions = {
        product["identifiers"]["purl"][len(prefix) :]
        for statement in statements
        for product in statement["products"]
        if product["identifiers"]["purl"].startswith(prefix)
    }
    if requested:
        for statement in statements:
            for product in statement["products"]:
                if product["identifiers"]["purl"].startswith(prefix):
                    product["identifiers"]["purl"] = prefix + requested
        return requested
    if len(existing_versions) > 1:
        raise ValueError("Multiple product versions found; specify --product-version.")
    return next(iter(existing_versions), initial)


def write_document(path: Path, document: dict[str, Any]) -> None:
    """Replace the file only after serialization and writing succeed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(json.dumps(document, indent=2) + "\n")
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def generate(args: argparse.Namespace, root: Path = ROOT) -> Path:
    """Create a document or update it without changing unrelated assessments."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.package):
        raise ValueError("Package must be a directory name under packages.")
    manifest = root / "packages" / args.package / "pyproject.toml"
    project = tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]
    package_name = re.sub(r"[-_.]+", "-", project["name"]).lower()
    path = root / "VEX" / f"{args.package}.openvex.json"
    exists = path.exists()
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    document: dict[str, Any]
    if exists:
        document = json.loads(path.read_text(encoding="utf-8"))
        validate_document(document)
        if args.author:
            raise ValueError("--author is only supported when creating a document.")
    else:
        document = {
            "@context": "https://openvex.dev/ns/v0.2.0",
            "@id": f"https://github.com/ansys/saf/blob/main/VEX/{path.name}",
            "author": args.author or "ANSYS, Inc.",
            "role": "Product supplier",
            "timestamp": now,
            "version": 1,
            "statements": [],
        }
    prefix = f"pkg:pypi/{package_name}@"
    statements: list[dict[str, Any]] = document["statements"]
    product_version = resolve_product_version(statements, prefix, args.product_version, project["version"])
    statement = build_statement(args, prefix + product_version)
    if statement is not None:
        key = statement_key(statement)
        matches = [index for index, existing in enumerate(statements) if statement_key(existing) == key]
        if len(matches) > 1:
            raise ValueError("Multiple matching statements found; resolve duplicates before updating.")
        if matches:
            statements[matches[0]] = statement
        else:
            statements.append(statement)
    if not statements:
        raise ValueError("A new document requires --vulnerability and --status.")
    if exists:
        document["version"] += 1
        document["last_updated"] = now
    write_document(path, document)
    return path


def main() -> None:
    """Report input and filesystem errors as command-line failures."""
    parser = parser_for_cli()
    args = parser.parse_args()
    try:
        path = generate(args)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f"Saved VEX document: {path}")


if __name__ == "__main__":
    main()
