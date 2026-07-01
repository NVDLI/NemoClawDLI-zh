# Python dependency vulnerability guard

This repo uses three layers for Python dependency security.
Release evidence and acceptance rules live in
[`release-test-plan.md`](release-test-plan.md); published SBOM retention and naming live
in [`release_artifacts.md`](release_artifacts.md).

## Fast source gate

Run from the repository root:

```bash
python3 scripts/security/audit_python_dependencies.py
```

The script reads the dependency declarations that affect the lab/test images:

- `workspace/requirements.txt`
- `cpu/services/sandbox_admin/requirements.txt`
- `cpu/services/docker_router/Dockerfile`
- `cpu/services/llm_client/llm_client.Dockerfile`

For each tracked security-sensitive package, it checks the declared floor or exact
pin against PyPI vulnerability metadata. It fails when a manifest lowers a floor,
uses an unbounded spec for a tracked package, pins below the required floor, or
PyPI/OSV reports a known vulnerability for that declared release.

This catches the class that triggered the Starlette, protobuf, and MCP report:
a source manifest allowed a vulnerable minimum such as `starlette>=0.40.0` or
`mcp>=1.5.0`. It also tracks vulnerable transitive packages surfaced by the
resolved workspace scan, such as `aiohttp` and `cryptography`. It also makes unused vulnerable runtime dependencies visible so they can be removed instead of waived.

The workspace manifest keeps reviewed direct dependencies readable. `workspace/requirements.lock`
is the exact Python 3.11 transitive closure used by release installation and SBOM generation.
Material refresh tooling and SCA tooling have separate locks under `scripts/materials/` and
`scripts/security/`, so scanner packages do not appear as runtime components.

Validate lock shape, direct-pin parity, and detector mutations:

```bash
python3 scripts/security/audit_dependency_locks.py --self-test
python3 scripts/security/audit_dependency_locks.py
```

Regenerate with the repository's pinned `uv==0.11.25` after changing a direct manifest:

```bash
uv pip compile workspace/requirements.txt --python-version 3.11 --no-header --no-annotate --output-file workspace/requirements.lock
uv pip compile scripts/materials/requirements.lock.in --python-version 3.11 --no-header --no-annotate --output-file scripts/materials/requirements.lock
uv pip compile scripts/security/requirements-sca.lock.in --python-version 3.11 --no-header --no-annotate --output-file scripts/security/requirements-sca.lock
```

Review the full lock diff, rerun SCA, and commit each direct manifest with its lock. Exact versions
stabilize resolution and SBOM identity; installed-environment SCA remains required. The direct gate
also rejects unpinned workspace dependencies and dependencies intentionally removed from the runtime.
`langserve`, `langgraph-cli`, unused optional Jupyter extensions and language packs, and
`pymupdf` are such packages: no tracked course, notebook, service, or Jupyter configuration
uses them. The CLI's in-memory runtime also conflicts with the supported protobuf,
cryptography, OpenTelemetry, and Starlette compatibility line. Reintroduction requires
demonstrated runtime or learner need plus current source/license and compatibility review.
Run its network-free regression check with:

```bash
python3 scripts/security/audit_python_dependencies.py --self-test
```

The check is wired into:

- `.gitlab-ci.yml` test job
- `scripts/git-hooks/pre-push`
- `scripts/security/SKILL.html`, so an agent can discover and run it from the security visor
- `AGENT_QUICKSTART.md`, so it appears in the normal validation cadence

## Waiver registry

Known vulnerability exceptions must be explicit, owned, sourced, and time-boxed in:

```bash
scripts/security/vulnerability-waivers.json
```

The registry is intentionally empty by default. Any entry must include:

- `id`: advisory ID, CVE, GHSA, or BDSA identifier
- `package`: affected package or image component
- `reason`: why the risk is accepted for this repo
- `owner`: accountable person or team
- `expires`: `YYYY-MM-DD`
- `source`: scanner report, issue, MR, or advisory URL

Validate it with:

```bash
python3 scripts/security/audit_vulnerability_waivers.py
```

Expired waivers fail locally and in CI. Use a waiver only when the scanner finding
is not currently actionable; do not use it to bypass an available safe upgrade.

The protobuf waiver for `BDSA-2025-123809` covers an upstream gap rather than a
version preference. The original `Any` recursion fix shipped in `5.29.6`, but
`Struct`, `Value`, and `ListValue` still bypass the JSON parser depth counter in
released wheels through `7.35.1`. Upstream merged the complete fix in
[`protocolbuffers/protobuf#27007`](https://github.com/protocolbuffers/protobuf/pull/27007).
Until that fix reaches a stable wheel, `audit_python_dependencies.py` rejects any
tracked runtime caller of `google.protobuf.json_format.Parse` or `ParseDict`, and
the waiver expires so the dependency cannot remain accepted silently.

## Full installed-environment SCA

### Inventory is not license approval

An SBOM records components and relationships. License data is optional metadata and may be absent
or too weak for a downstream policy engine. For example, the generated CycloneDX document identified
the removed Jupyter packages by name, version, and package URL and carried a Python classifier such as
`License :: OSI Approved :: BSD License`; the review system still required an SPDX-normalized license.
`pymupdf` had no license field in the generated component. An `Unknown License` result therefore does
not mean the component was missing from the SBOM. It means inventory succeeded but license evidence
did not meet policy.

Do not hand-edit a generated SBOM. Remove an unused component, correct its package/source metadata,
or add approved enrichment in the SBOM pipeline. Keep the source/license decision outside generated
artifacts so every rebuild is reproducible.

The fast gate does not replace a full transitive scan. Once the workspace/test
container has installed the real environment, run one of the standard scanners
inside that environment.

Preferred repo wrapper:

```bash
python3 scripts/security/run_full_sca.py
python3 scripts/security/run_full_sca.py --execute --python-local --cyclonedx-env --osv-source
python3 scripts/security/run_full_sca.py --execute --image <built-image>
```

The wrapper is the agent-discoverable SCA entry point. It prints the exact scanner
commands by default and runs only selected scanners when `--execute` is provided.
It never installs tools.
For release SBOMs, keep scanner packages out of the runtime environment and pass the runtime
interpreter with `--python-executable` plus its site-packages path with `--python-path`.

Preferred Python environment scan when running commands directly:

```bash
python3 -m pip install pip-audit
python3 -m pip_audit --local --strict --format json --output /tmp/pip-audit.json
python3 -m pip_audit --local --strict
```

CycloneDX SBOM for the installed Python environment:

```bash
python3 -m pip install cyclonedx-bom
cyclonedx-py environment --of JSON --output-file /tmp/python-env.cdx.json
```

Source or image scan when OSV-Scanner is available:

```bash
osv-scanner scan source .
osv-scanner scan image <built-image>
```

GitLab also supports Dependency Scanning and SBOM-backed findings on merge
requests. Use that as the server-side project policy layer when the instance has
it enabled; keep this repo-local audit as the fast developer and agent-visible
floor guard.

CI includes two SCA jobs:

- `security_sca`: manual on branches/default branch and automatic on schedules. It
  scans the CI Python environment after installing scanner tooling and emits SBOM
  artifacts under `scripts/security/reports/`.
- `security_deep_sca`: automatic on merge requests that change a Python dependency
  manifest, relevant Dockerfile, waiver, or SCA gate; manual on other
  branches/default branch; and automatic on schedules. It creates an isolated `.sca-venv`, installs
  `workspace/requirements.txt`, audits the resolved workspace environment, and
  emits a CycloneDX SBOM under `scripts/security/reports/deep-workspace/`. This
  job has a 2 hour timeout because full dependency resolution can be slow.

Use the GitLab SBOM Dependency Scanning policy layer for continuous
advisory-database rescans of default-branch SBOM components.

## Next hardening steps

These are intentionally not hidden as vague future work. File separate issues/MRs
when taking them on:

1. Add hashes or signed provenance to the exact Python lock workflow when the release host and
   artifact policy are finalized.
2. Add image SCA for built service images. Use public-safe scanners such as Trivy,
   Grype, or OSV-Scanner for public images; keep NVIDIA/private base image scans
   in internal CI or registry tooling when image names/layers are not public-safe.
3. Enable and smoke-test the host dependency graph, Dependabot alerts, CodeQL upload,
   secret scanning, and push protection when mirrored externally. Repo-owned update,
   dependency-review, and CodeQL workflow definitions are already versioned. Keep
   GitLab/internal jobs authoritative while GitLab remains canonical.
4. Add `CODEOWNERS` and protected-branch rules for dependency manifests, Dockerfiles,
   `scripts/security/*`, CI files, deploy files, and waiver registry changes.
5. Consider VEX only if downstream consumers need machine-readable non-affected
   statements. Until then, keep the waiver registry small, explicit, and expiring.
6. Keep release SBOM retention aligned with [`release_artifacts.md`](release_artifacts.md).
   The protected release workflow publishes resolved Python and student-browser CycloneDX SBOMs
   beside each archive; add image SBOMs when public release images exist.

## Maintenance

When a new advisory arrives:

1. Raise the package floor or pin in the relevant manifest.
2. Add the package and required floor to `REQUIRED_FLOORS` in `scripts/security/audit_python_dependencies.py` if it is a dependency class we must track explicitly.
3. If a temporary exception is unavoidable, add a time-boxed entry to `scripts/security/vulnerability-waivers.json`.
4. Run `python3 scripts/security/audit_python_dependencies.py`.
5. Run `python3 scripts/security/audit_vulnerability_waivers.py`.
6. Run `python3 scripts/security/run_full_sca.py --execute --python-local --cyclonedx-env` in the built environment.
7. Run the `security_deep_sca` CI job or the equivalent isolated-venv command when the full workspace dependency graph changed.
8. Run the usual repo gate.
9. Record the full installed-environment scan result when the test/lab container is available.
