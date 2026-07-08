# Release test plan

This plan verifies the product defined in [`product-design.md`](product-design.md). It applies to a
reviewed release candidate commit and its eventual protected tag. The machine-readable coverage map is
[`release-evidence.json`](release-evidence.json).
Detailed dependency procedures live in [`dependency_security.md`](dependency_security.md).
Security requirement dispositions live in
[`security-control-disposition.md`](security-control-disposition.md).
Artifact promotion lives in [`release_artifacts.md`](release_artifacts.md), and Pages assembly
lives in [`pages_deploy.md`](pages_deploy.md).

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
- The OSS registration scope names the DLI course repository and excludes the separately owned
  NemoClaw product, launchable, runtime, and service deployments.

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

Run the shared deterministic sequence from the repository root:

```bash
python3 scripts/validation/release_gate.py --tier ship
```

The matrix below explains its constituent claims and adds conditional browser, service,
host, and external-review work. Any applicable nonzero exit blocks the candidate.

| ID | Claim | Command | Pass condition | Evidence |
|---|---|---|---|---|
| A01 | Design and test evidence remain complete and public-safe | `python3 scripts/validation/release_evidence_audit.py --self-test` then `python3 scripts/validation/release_evidence_audit.py` | Every mutation is detected; repository audit has zero findings | CI log and validation report |
| A01a | Public repository work products match their reviewed requirement and applicability levels | `python3 scripts/validation/repository_work_products_audit.py --self-test`; `python3 scripts/validation/repository_work_products_audit.py` | Mutation suite passes; required files, evidence paths, policy content, intake templates, and gate wiring have zero findings | CI log, applicability matrix, and validation report |
| A02 | Product topology and endpoint controls match implementation | `python3 scripts/figures/render_security_architecture.py --check`; `python3 scripts/validation/security_architecture_audit.py --self-test`; `python3 scripts/validation/security_architecture_audit.py`; `python3 scripts/security/audit_iframe_proxy_opt_in.py --self-test`; `python3 scripts/security/audit_iframe_proxy_opt_in.py`; `bash scripts/runtime/run_node.sh scripts/validation/gateway_token_audit.mjs --self-test` | Generated graph is current; topology, endpoint-selection, credential-destination, relay, and complete gateway-token mutations are rejected | CI log and source-backed graph |
| A02a | Threat controls remain correctly assigned to repository, host, service, residual, or non-applicable ownership | `python3 scripts/validation/threat_control_audit.py --self-test`; `python3 scripts/validation/threat_control_audit.py`; `python3 scripts/validation/repository_sync_audit.py --self-test` | Mutation suites pass; repository controls are wired; signing and hosting gaps remain visible; provider controls are not claimed by client code; the dual-repository audit cannot write protected refs | CI log, disposition record, and authorized external evidence |
| A03 | Contribution and release authority remain separated | `python3 scripts/validation/contribution_safety_audit.py --self-test`; `python3 scripts/validation/contribution_safety_audit.py` | Mutation suite and repository audit pass | CI report |
| A04 | Required public files, licenses, sources, material provenance, and contributor-local hygiene are intact | `python3 scripts/compliance/source_gate.py`; `python3 scripts/validation/local_path_leak_audit.py --self-test`; `python3 scripts/validation/local_path_leak_audit.py`; `python3 scripts/validation/local_path_leak_audit.py --commit-range origin/main..HEAD`; `python3 scripts/materials/pull_materials.py --self-test`; `python3 scripts/materials/pull_materials.py --verify-committed` | Root terms pass; inventory resolves; no forbidden private links or contributor workstation paths exist in the tree or any proposed commit; path/retry/tamper mutations pass; every committed material matches its manifest metadata, character count, and full SHA-256 without network access | CI log |
| A04a | Sensitive contribution content stays in approved private systems | `python3 scripts/validation/sensitive_content_audit.py --self-test`; `python3 scripts/validation/sensitive_content_audit.py`; `python3 scripts/validation/sensitive_content_audit.py --commit-range origin/main..HEAD` | Mutation suite passes; tree and complete proposed history contain no restricted finding details, private service locations, personal corporate addresses, or concrete credentials | CI log |
| A04b | Security-relevant diffs notify the release operator | `python3 scripts/validation/release_change_reminder.py --self-test`; `python3 scripts/validation/release_change_reminder.py --commit-range origin/main..HEAD` | Mutation suite passes; applicable external assessment, scan, open-source/license, and final-artifact actions are listed without claiming completion | CI log and authorized release record |
| A04c | The static third-party list matches exact package locks, material provenance, and scanned component evidence | `python3 scripts/compliance/third_party_inventory_audit.py --self-test`; `python3 scripts/compliance/third_party_inventory_audit.py`; `python3 scripts/compliance/export_third_party_csv.py --self-test`; `python3 scripts/compliance/render_sbom_license_inventory.py --self-test` | Mutation suites pass; every npm and Python package/version is listed with a license identifier; uncommon license scopes, direct container declarations, and every external-source material row remain visible; `scripts/compliance/docs/sbom_generation.md` retains the reproducible npm, Python, source-tree, conditional-image, material, checksum, and attachment procedure; the compliance SKILL previews and exports the SWIPAT table with explicit vendored, build-input, validation, and local-authoring relationships; a CycloneDX scan can produce a digest-bound component appendix without guessing unresolved licenses | `THIRD_PARTY_LICENSES.md`, filtered SWIPAT CSV, SBOM runbook, attached scan set and manifest, retained raw metadata/SBOM and hashes, SKILL browser-render log, and CI log |
| A05 | Dependency manifests and locks agree | `python3 scripts/security/audit_dependency_locks.py --self-test`; `python3 scripts/security/audit_dependency_locks.py` | Mutation suite passes and no lock drift exists | CI log |
| A06 | Direct dependencies and accepted exceptions meet repository policy | `python3 scripts/security/audit_python_dependencies.py`; `python3 scripts/security/audit_vulnerability_waivers.py` | No unhandled vulnerable floor/pin; every exception is fingerprinted, owned, controlled, scoped, and unexpired | CI log |
| A07 | Resolved environment is scanned and inventoried | Run the isolated A07 procedure below, or the required `security_deep_sca` CI job | Scanner succeeds; SBOM covers expected locked components; retired components remain absent | Retained scanner and SBOM artifacts |
| A08 | Course structure, prose contracts, browser dependencies, localization, links, and directory contracts ship cleanly | `python3 scripts/validation/course_dependency_integrity.py --self-test`; `python3 scripts/validation/course_dependency_integrity.py`; `python3 scripts/validation/cell_audit.py --self-test`; `python3 scripts/validation/cell_audit.py`; `python3 scripts/validation/validate_layout.py --quiet`; `python3 scripts/skills/skill_consistency.py`; `python3 scripts/skills/gen_directory_beacons.py --check`; `python3 scripts/skills/test_skill_contract.py`; `python3 scripts/skills/skill_contract.py`; run `skill_renderer_runtime_audit.py` in the standard browser runtime; `python3 scripts/validation/validate_bundle.py --scope ship --no-write` | Dependency and editor-asset mutations are rejected; every source directory has a valid beacon with no exemptions; every beacon renders without page or resource errors; every package, license, asset hash, source reference, and browser CycloneDX component resolves; required and recommended findings are zero | Validation report, SKILL renderer log, public dependency inventory, and browser SBOM |
| A09 | Locale overlays cannot ship stale or structurally divergent | `python3 scripts/build/assemble_locale_overlay.py --self-test`; `python3 scripts/validation/localization_audit.py --self-test`; run `localization_audit.py --locale` for every locale profile | Mutation suites and every locale audit pass | CI log and localization manifest |
| A10 | Release packaging is deterministic | `python3 scripts/build/package_release.py --self-test` | Repeated fixture builds have identical archive, manifest, and checksums | CI log |
| A11 | Generated Pages output matches the source contract and reviewed commit | `python3 scripts/build/project_docs_explorer.py --self-test`; `python3 scripts/build/project_source_tree.py --self-test`; `python3 scripts/validation/branch_preview_manifest_audit.py --self-test`; `python3 scripts/validation/pages_artifact_integrity.py --self-test`; `BUILD_PAGES_PULL_MATERIALS=0 bash scripts/build/build_pages.sh /tmp/nemoclaw-pages-test`; run `skill_renderer_runtime_audit.py --site-root /tmp/nemoclaw-pages-test`; run `pages_artifact_integrity.py` with the candidate SHA before upload, during bounded extraction, and against the deployed HTTPS URL | Projection, resource-bound, traversal, link, renderer, export-preview, tamper, and deployed-byte fixtures pass; build exits zero; every source directory contract and configured file is present; the same-commit gate report, language routes, dependency evidence, executable-reference policy, file inventory, extracted tree, and live site agree | Pages artifact, SHA-256 inventory, SKILL renderer log, browser result, and post-deployment integrity job |
| A12 | Browser state transitions remain usable | Run the applicable containerized browser audits named in `docs/lab_runtime_testing.md` against source and built output | Entry, success, error, reset/remount, reload, keyboard, and narrow-layout cases pass | Browser logs and screenshots |
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

Live source checks are separate from the deterministic matrix. Scheduled monitoring and protected
release preparation run a strict retried `pull_materials.py --check`. A production-ref push may
continue only when every live failure is classified as transient reachability; source drift,
malformed content, unsafe redirects, TLS failures, and committed-provenance mismatches still block.

## Manual and external evidence matrix

Store links, identifiers, named reviewers, and detailed reports outside the public repository.

| ID | Evidence | Procedure | Pass condition | Owner |
|---|---|---|---|---|
| M01 | Course program and release registration | Compare the NemoClaw DLI course purpose, intended OSS Type I class, attributes, contacts, version, course source, excluded product scope, and release status with the reviewed design | Required fields accurately identify the Full-OSS DLI course repository without claiming the NemoClaw product, launchable, or runtime | Release owner |
| M02 | Public course repository baseline | Confirm the course repository is in the approved organization and review README, LICENSE, verbatim SECURITY policy, contribution and coding guidance, conduct, changelog, maintainer plan, Feature and Bug issue forms, and pull-request template | Host location and required work products are accepted, and public GitHub is configured as the canonical course planning, issue, contribution, CI, and release home | Repository owner and approver |
| M03 | Product legal/open-source terms | Submit the final release request and answer follow-up questions | Authorized legal/open-source reviewer records approval | External reviewer |
| M04 | OSS license disposition | Review `THIRD_PARTY_LICENSES.md`, register the final source and released artifacts, correct inventory data, and review every actionable component | The static package/version/SPDX inventory matches the exact locks; zero released components lack required license disposition | Release owner and external reviewer |
| M05 | Export classification | Supply the cryptography inventory, distribution method, and principal use from the design; answer follow-up questions | Authorized export reviewer closes the review and the registration reflects it | External reviewer |
| M06 | Privacy applicability and review | Compare deployment data flows, browser storage, external recipients, logs, and retention ownership with the selected hosting configuration | Privacy marks the assessment complete, or the authorized process records that no assessment is required | Privacy reviewer |
| M07 | Authoritative secret scan | Scan the final registered source ref and review every finding | Zero verified secrets; any exposed credential was rotated before removal | Release owner |
| M08 | Authoritative vulnerability scan | Scan every final released artifact; review severity, age, fix availability, and artifact-specific dispositions | No overdue fixable Critical/High finding lacks an approved disposition, mitigation, and remediation plan | Release owner and risk authority |
| M09 | Malware scan | Read `release-manifest.json.external_evidence`; submit every file in `malware_scan_required` to the qualified scanner, and record applicability for the remaining text-only assets | Every listed artifact has zero malicious and zero suspicious detections, or an authorized false-positive disposition; the external record closes the manifest's `required-before-publication` policy | Release owner and malware reviewer |
| M10 | Live host controls | Verify HTTPS, protected default branch and tags, required checks, immutable release settings, private vulnerability intake, a `github-pages` environment with required reviewers and self-review prevention, the weekly public-to-internal integration schedule, and the recorded CSP/CDN/WAF decision | Live configuration matches the design, disposition record, and release playbook | Host administrator and release owner |
| M10a | Generated threat-analysis reconciliation | First compare the generated Target of Evaluation with the package's threat-analysis invariants and correct scope or fact drift. Then compare findings with `security-control-disposition.md` by aggregate control theme, correct private row-level statuses that contradict evidence, assign service controls to their operators, and retain unresolved signing, hosting, credential, and service requirements. | The generated Target of Evaluation matches the canonical invariants; every generated status has an evidence-backed owner and disposition in the authorized review system; the public repository contains no private row-by-row assessment | Product Security reviewer and release owner |
| M11 | Final release review | Review the exact tag, pipeline, generated-tree browser results, downloadable Pages artifact and its SHA-256 inventory, Pages smoke, archive manifest, SBOM, checksums, known issues, external evidence, and rollback plan before approving the deployment environment | Authorized reviewer records an approved decision against the exact artifact | Release reviewer |

## Execution order

1. Run focused tests while editing.
2. Run `release_gate.py --tier ship --no-write --changed-since origin/main` once before pushing. A01 through
   A10 map claims inside that gate; they are not a second command checklist.
3. Build the complete multilingual Pages tree and run A11. Reuse a prior report only when the
   fail-closed report audit proves the same commit, ship scope, clean source tree, and required pass.
4. Run A12 and A13 when the diff touches their runtime surfaces.
5. Push the issue-linked branch and require CI on the submitted commit.
6. Preview the tested commit and complete M01 through M06 far enough to expose review gaps.
7. Freeze the release candidate under a protected annotated tag only after repository review.
8. Run the protected release workflow and retain its archive, manifest, SBOM, checksums, and reports.
9. Complete M07 through M10 against the final source ref and packaged artifacts.
10. Complete M10a, then obtain M11. Publish only after the publication state and protected
    environment permit it.

Release candidates omit `--changed-since` so every detector mutation runs. CI retains per-command
timing evidence; recurring high-latency checks should be optimized at their canonical owner, not
copied into a second abbreviated gate.

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
- The deployed HTTPS tree matches the reviewed Pages manifest byte-for-byte.
- The external integration audit has run on its declared cadence and any external-ahead or diverged state has a reviewed reconciliation record.
- The protected tag points to that commit and is contained in protected `main`.
- Archive, manifest, SBOM, checksums, and retained validation evidence agree on version and commit.
- M01 through M11, including M10a, are complete or formally Not Applicable through the authorized
  process.
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
