# Release test plan

This plan verifies the product defined in [`product-design.md`](product-design.md). It applies to a
reviewed release candidate commit and its eventual protected tag. The machine-readable coverage map is
[`release-evidence.json`](release-evidence.json).

The plan separates repository checks from operator and external-review evidence. A passing pipeline
does not approve legal terms, privacy, export classification, malware disposition, host configuration,
or publication.

## Scope

Test these release surfaces:

- canonical and localized course source;
- generated static Pages output;
- browser interaction behavior affected by the release;
- source, dependency, SBOM, and provenance records;
- security architecture, contribution, deployment, and release controls; and
- deterministic tagged release assets.

Local authoring services require integration tests when their source changes. They are not production
components of the static course.

## Roles and evidence ownership

| Role | Responsibility |
|---|---|
| Contributor | Runs focused tests, updates affected contracts, and records failures honestly |
| CI | Repeats deterministic tests on the submitted commit and retains reports |
| Release owner | Selects the final commit/tag, reviews all evidence, runs manual host checks, and stops on missing evidence |
| External reviewer | Decides legal, license, privacy, export, malware, risk, or release approval within their authority |

Internal identifiers, reviewer records, and private scan details belong in the authorized lifecycle
record. Public repository evidence contains only the design, commands, result shape, and ownership
boundary.

## Entry criteria

- Work is on an issue-linked branch based on current protected `main`.
- The candidate diff is understood and its blast radius is declared.
- Required source and license provenance exists.
- Direct requirements and transitive locks agree.
- No known external approval is represented as complete by repository text.
- The candidate publication state matches `RELEASE_STATUS.json`.

## Test environments

| Environment | Purpose |
|---|---|
| Source checkout | Fast structure, contract, source, and policy validation |
| Node-enabled validation runtime | Link projection and full static bundle checks |
| Resolved Python 3.11 environment | Exact dependency, vulnerability, and CycloneDX inventory checks |
| Built Pages tree | Generated English, Portuguese, and Spanish route and asset verification |
| Containerized browser | Rendered layout and interaction-state checks when browser behavior changes |
| Protected release workflow | Tag containment, deterministic packaging, evidence retention, and draft creation |
| External review systems | Registration, legal, license, export, privacy, secrets, vulnerability, malware, and final release decisions |

## Automated test matrix

Run from the repository root. Any nonzero exit blocks the candidate.

| ID | Claim | Command | Pass condition | Evidence |
|---|---|---|---|---|
| A01 | Design and test evidence remain complete and public-safe | `python3 scripts/validation/release_evidence_audit.py --self-test` then `python3 scripts/validation/release_evidence_audit.py` | Every mutation is detected; repository audit has zero findings | CI log and validation report |
| A02 | Product topology matches implementation | `python3 scripts/figures/render_security_architecture.py --check`; `python3 scripts/validation/security_architecture_audit.py --self-test`; `python3 scripts/validation/security_architecture_audit.py` | Generated graph is current; mutation suite and audit pass | CI log and source-backed graph |
| A03 | Contribution and release authority remain separated | `python3 scripts/validation/contribution_safety_audit.py --self-test`; `python3 scripts/validation/contribution_safety_audit.py` | Mutation suite and repository audit pass | CI report |
| A04 | Required public files, license, sources, and private-link boundary are intact | `python3 scripts/compliance/source_gate.py` | Root license and terms pass; inventory resolves; no forbidden private links or provenance gaps | CI log |
| A05 | Dependency manifests and locks agree | `python3 scripts/security/audit_dependency_locks.py --self-test`; `python3 scripts/security/audit_dependency_locks.py` | Mutation suite passes and no lock drift exists | CI log |
| A06 | Direct dependencies and accepted exceptions meet repository policy | `python3 scripts/security/audit_python_dependencies.py`; `python3 scripts/security/audit_vulnerability_waivers.py` | No unhandled vulnerable floor/pin; every exception is owned, sourced, and unexpired | CI log |
| A07 | Resolved environment is scanned and inventoried | Run the isolated A07 procedure below, or the required `security_deep_sca` CI job | Scanner succeeds; SBOM covers expected locked components; retired components remain absent | Retained scanner and SBOM artifacts |
| A08 | Course structure, prose contracts, browser dependencies, localization, and links ship cleanly | `python3 scripts/validation/course_dependency_integrity.py --self-test`; `python3 scripts/validation/course_dependency_integrity.py`; `python3 scripts/validation/cell_audit.py --self-test`; `python3 scripts/validation/cell_audit.py`; `python3 scripts/validation/validate_layout.py --quiet`; `python3 scripts/skills/skill_consistency.py`; `python3 scripts/skills/skill_contract.py`; `python3 scripts/validation/validate_bundle.py --scope ship --no-write` | Dependency and editor-asset mutations are rejected; every package, license, asset hash, source reference, and browser CycloneDX component resolves; required and recommended findings are zero | Validation report, public dependency inventory, and browser SBOM |
| A09 | Locale overlays cannot ship stale or structurally divergent | `python3 scripts/build/assemble_locale_overlay.py --self-test`; `python3 scripts/validation/localization_audit.py --self-test`; run `localization_audit.py --locale` for every locale profile | Mutation suites and every locale audit pass | CI log and localization manifest |
| A10 | Release packaging is deterministic | `python3 scripts/build/package_release.py --self-test` | Repeated fixture builds have identical archive, manifest, and checksums | CI log |
| A11 | Generated Pages output matches the source contract | `python3 scripts/build/project_docs_explorer.py --self-test`; `python3 scripts/validation/branch_preview_manifest_audit.py --self-test`; `BUILD_PAGES_PULL_MATERIALS=0 bash scripts/build/build_pages.sh /tmp/nemoclaw-pages-test` | Projection fixtures pass; build exits zero; language manifest and every advertised course route exist; the dependency dashboard, package inventory, and browser SBOM survive artifact projection; the docs explorer renders Markdown, restores `?file=` plus heading URLs, and contains every local target linked by a rendered document | Pages artifact and live smoke result |
| A12 | Browser state transitions remain usable | Run the applicable containerized browser audits named in `AGENT_QUICKSTART.md` against source and built output | Entry, success, error, reset/remount, reload, keyboard, and narrow-layout cases pass | Browser logs and screenshots |
| A13 | Service-stack changes preserve local authoring behavior | `python3 workspace/run_tests.py services --notebook <notebook>` for each affected service notebook | Affected service tests pass in the declared lab environment | Test log |

For A07, keep runtime and scanner packages separate:

```bash
python3 -m venv /tmp/nemoclaw-release-runtime
python3 -m venv /tmp/nemoclaw-release-scanner
/tmp/nemoclaw-release-runtime/bin/python -m pip install -r workspace/requirements.lock
/tmp/nemoclaw-release-scanner/bin/python -m pip install -r scripts/security/requirements-sca.lock
RUNTIME_SITE=$(/tmp/nemoclaw-release-runtime/bin/python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
PATH="/tmp/nemoclaw-release-scanner/bin:$PATH" /tmp/nemoclaw-release-scanner/bin/python \
  scripts/security/run_full_sca.py --execute --require-tools --python-local --cyclonedx-env \
  --python-executable /tmp/nemoclaw-release-runtime/bin/python --python-path "$RUNTIME_SITE" \
  --out-dir /tmp/nemoclaw-release-sca
/tmp/nemoclaw-release-scanner/bin/python scripts/security/audit_sbom_policy.py \
  --sbom /tmp/nemoclaw-release-sca/python-env.cdx.json
```

Final release evidence comes from the protected workflow's exact environment and retained artifact
paths.

## Manual and external evidence matrix

Store links, identifiers, named reviewers, and detailed reports outside the public repository.

| ID | Evidence | Procedure | Pass condition | Owner |
|---|---|---|---|---|
| M01 | Program and release registration | Compare purpose, class, attributes, contacts, version, source, and release status with the reviewed design | Required fields are present and accurate for the final release | Release owner |
| M02 | Public repository baseline | Confirm the external repository is in the approved organization and review README, LICENSE, SECURITY, contribution terms, conduct, support, and maintainer files | Host location is approved and required files are accepted by the designated approver | Repository owner and approver |
| M03 | Product legal/open-source terms | Submit the final release request and answer follow-up questions | Authorized legal/open-source reviewer records approval | External reviewer |
| M04 | OSS license disposition | Register the final source and released artifacts; correct inventory data; review every actionable component | Zero released components lack required license disposition | Release owner and external reviewer |
| M05 | Export classification | Supply the cryptography inventory, distribution method, and principal use from the design; answer follow-up questions | Authorized export reviewer closes the review and the registration reflects it | External reviewer |
| M06 | Privacy applicability and review | Compare deployment data flows, browser storage, external recipients, logs, and retention ownership with the selected hosting configuration | Privacy marks the assessment complete, or the authorized process records that no assessment is required | Privacy reviewer |
| M07 | Authoritative secret scan | Scan the final registered source ref and review every finding | Zero verified secrets; any exposed credential was rotated before removal | Release owner |
| M08 | Authoritative vulnerability scan | Scan every final released artifact; review severity, age, fix availability, and artifact-specific dispositions | No overdue fixable Critical/High finding lacks an approved disposition, mitigation, and remediation plan | Release owner and risk authority |
| M09 | Malware scan | Submit every NVIDIA-produced packaged release artifact to the qualified scanner | Zero malicious and zero suspicious detections, or an authorized false-positive disposition | Release owner and malware reviewer |
| M10 | Live host controls | Verify HTTPS, protected default branch and tags, required checks, restricted deployment environments, immutable release settings, and private vulnerability intake | Live configuration matches the design and release playbook | Host administrator and release owner |
| M11 | Final release review | Review the exact tag, pipeline, Pages smoke, archive manifest, SBOM, checksums, known issues, external evidence, and rollback plan | Authorized reviewer records an approved decision | Release reviewer |

## Execution order

1. Run focused tests while editing.
2. Run A01 through A10 before pushing.
3. Build the complete multilingual Pages tree and run A11.
4. Run A12 and A13 when the diff touches their runtime surfaces.
5. Push the issue-linked branch and require CI on the submitted commit.
6. Preview the tested commit and complete M01 through M06 far enough to expose review gaps.
7. Freeze the release candidate under a protected annotated tag only after repository review.
8. Run the protected release workflow and retain its archive, manifest, SBOM, checksums, and reports.
9. Complete M07 through M10 against the final source ref and packaged artifacts.
10. Obtain M11. Publish only after the publication state and protected environment permit it.

## Pass, failure, and exception rules

- Every applicable automated test must pass on the exact candidate commit.
- A skipped browser or service test requires a written applicability reason tied to the diff.
- A test crash, zero-input run, stale report, missing artifact, or mismatched SHA is a failure.
- Repository tests cannot convert missing external evidence into a pass.
- Where an authorized vulnerability exception is allowed, it must name the final artifact, owner,
  justification, current mitigation, remediation plan, source, and expiry.
- Requirements marked non-waivable by the governing process must be complete or explicitly Not
  Applicable through that process. The repository cannot grant a waiver.
- A failed external review blocks publication even when repository tests pass.

## Exit criteria

- Required CI is green for the final commit.
- Required browser and service tests passed or have an accepted applicability record.
- The Pages preview and smoke result match the final commit.
- The protected tag points to that commit and is contained in protected `main`.
- Archive, manifest, SBOM, checksums, and retained validation evidence agree on version and commit.
- M01 through M11 are complete or formally Not Applicable through the authorized process.
- Known issues, mitigations, rollback, and support scope were reviewed.
- The authorized release reviewer recorded approval.

## Evidence record

Record this information in the authorized release system:

| Field | Value to record |
|---|---|
| Source | Canonical repository and final commit |
| Version | Protected annotated tag and tag object ID |
| Design | Link to `docs/product-design.md` at the final commit |
| Test plan | Link to this file at the final commit |
| Pipeline | Required CI URL and commit SHA |
| Preview | Pages URL and smoke job |
| Release assets | Archive, manifest, SBOM, checksums, and their digests |
| Automated results | Validation report, dependency scan, waiver audit, and browser/service evidence |
| External results | Registration, legal/license, export, privacy, secret, vulnerability, malware, and host-control evidence |
| Decision | Reviewer identity, date, outcome, remaining conditions, and rollback owner |

Re-run the complete plan when the release scope, hosting path, data handling, authentication,
external service, dependency environment, packaging format, or release authority changes materially.
