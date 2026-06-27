# Python dependency vulnerability guard

This repo uses two layers for Python dependency security.

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
`mcp>=1.5.0`.

The check is wired into:

- `.gitlab-ci.yml` test job
- `scripts/git-hooks/pre-push`
- `scripts/security/SKILL.html`, so an agent can discover and run it from the security visor
- `AGENT_QUICKSTART.md`, so it appears in the normal validation cadence

## Full installed-environment SCA

The fast gate does not replace a full transitive scan. Once the workspace/test
container has installed the real environment, run one of the standard scanners
inside that environment.

Preferred Python environment scan:

```bash
python3 -m pip install pip-audit
python3 -m pip_audit --local --strict --format json --output /tmp/pip-audit.json
python3 -m pip_audit --local --strict
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

## Maintenance

When a new advisory arrives:

1. Raise the package floor or pin in the relevant manifest.
2. Add the package and required floor to `REQUIRED_FLOORS` in `scripts/security/audit_python_dependencies.py` if it is a dependency class we must track explicitly.
3. Run `python3 scripts/security/audit_python_dependencies.py`.
4. Run the usual repo gate.
5. Record the full installed-environment scan result when the test/lab container is available.
