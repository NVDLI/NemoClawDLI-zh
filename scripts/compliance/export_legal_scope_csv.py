#!/usr/bin/env python3
"""Export an auditable relationship map without conflating software and course materials."""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

import export_third_party_csv as software
import third_party_inventory_audit as inventory


ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = (
    "referenced-source",
    "tooling-not-distributed",
    "recreated-asset",
    "vendored-material",
    "vendored-browser-code",
)
HEADER = (
    "Repository Item",
    "Scope Category",
    "Artifact Relationship",
    "Distributed by NVIDIA in This Repository",
    "Executed in Learner Browser",
    "External Source or Package",
    "Recorded License or Terms",
    "Corroborating Repository Evidence",
    "Legal Scope Note",
)


def material_rows(base: str, ref: str) -> list[list[str]]:
    document = (ROOT / inventory.INVENTORY).read_text(encoding="utf-8")
    rows = inventory.rows(inventory.section(document, "Third-party course-material relationships"))
    output: list[list[str]] = []
    for row in rows:
        if len(row) < 5 or row[0] == "Repository file":
            continue
        repository_file, relationship, source_name, terms, source_cell = row[:5]
        links = software.markdown_links(source_cell)
        source_url = links[0][1] if links else source_cell
        if relationship == "recreation":
            category = "recreated-asset"
            note = "A repository-authored recreation is distributed; review the recorded source terms before release."
        elif relationship == "conversion":
            category = "vendored-material"
            note = "A copied or format-shifted material artifact is distributed; the source terms remain controlling."
        else:
            category = "referenced-source"
            note = (
                "The repository item is distributed, but the external work is used as a citation, summary, "
                "inspiration, original-work reference, or link compilation rather than a vendored copy."
            )
        output.append([
            repository_file,
            category,
            relationship,
            "Yes - repository-authored item" if category == "referenced-source" else "Yes",
            "No",
            source_url,
            terms,
            software.repository_file(base, ref, repository_file),
            f"Source label: {source_name}. {note}",
        ])
    return output


def tooling_rows(base: str, ref: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in software.browser_build_rows(base, ref):
        if "Category: browser-build-only." not in item[6]:
            continue
        rows.append([
            f"{item[0]}@{item[1]}", "tooling-not-distributed", "browser-build-only", "No", "No",
            item[7], item[2], item[8], item[6],
        ])
    for item in software.python_rows(base, ref):
        rows.append([
            f"{item[0]}@{item[1]}", "tooling-not-distributed", "validation or authoring dependency",
            "No", "No", item[7], item[2], item[8], item[6],
        ])
    for item in software.local_authoring_rows(base, ref):
        rows.append([
            f"{item[0]}@{item[1]}", "tooling-not-distributed", "local-authoring declaration",
            "No", "No", item[7], item[2], item[8], item[6],
        ])
    return rows


def browser_code_rows(base: str, ref: str) -> list[list[str]]:
    rows = []
    for item in software.vendored_rows(base, ref):
        rows.append([
            f"{item[0]}@{item[1]}", "vendored-browser-code",
            "direct" if "Relationship: direct." in item[6] else "transitive",
            "Yes", "Yes", item[7], item[2], item[8],
            "Copied into the same-origin static course; the linked repository license text and package source corroborate scope.",
        ])
    return rows


def scope_rows(categories: list[str], base: str, ref: str) -> list[list[str]]:
    rows = material_rows(base, ref) + tooling_rows(base, ref) + browser_code_rows(base, ref)
    return [row for row in rows if row[1] in categories]


def render_csv(rows: list[list[str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
    return stream.getvalue()


def validate(rows: list[list[str]]) -> list[str]:
    findings = []
    for number, row in enumerate(rows, 2):
        if len(row) != len(HEADER):
            findings.append(f"row {number} has {len(row)} columns instead of {len(HEADER)}")
        elif any(not row[index].strip() for index in (0, 1, 2, 3, 5, 6, 7, 8)):
            findings.append(f"row {number} lacks scope, source, terms, evidence, or disposition detail")
    return findings


def self_test() -> list[str]:
    rows = scope_rows(list(CATEGORIES), software.DEFAULT_REPOSITORY, "main")
    findings = validate(rows)
    if {row[1] for row in rows} != set(CATEGORIES):
        findings.append("scope export does not exercise every legal relationship category")
    material_count = len(inventory.rows(inventory.section(
        (ROOT / inventory.INVENTORY).read_text(encoding="utf-8"),
        "Third-party course-material relationships",
    )))
    exported_material_count = sum(row[1] in {"referenced-source", "recreated-asset", "vendored-material"} for row in rows)
    if exported_material_count != material_count:
        findings.append("scope export does not exactly cover the material-provenance table")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", action="append", choices=(*CATEGORIES, "all"))
    parser.add_argument("--repository", default=software.DEFAULT_REPOSITORY)
    parser.add_argument("--project-ref", default="main")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        findings = self_test()
        print("legal-scope CSV exporter self-test: " + ("PASS" if not findings else f"FAIL ({len(findings)})"))
        for finding in findings:
            print(f"  {finding}")
        return bool(findings)
    categories = args.category or list(CATEGORIES)
    if "all" in categories:
        categories = list(CATEGORIES)
    rows = scope_rows(list(dict.fromkeys(categories)), args.repository, args.project_ref)
    findings = validate(rows)
    if findings:
        for finding in findings:
            print(f"export error: {finding}", file=sys.stderr)
        return 1
    text = render_csv(rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {len(rows)} legal-scope rows to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
