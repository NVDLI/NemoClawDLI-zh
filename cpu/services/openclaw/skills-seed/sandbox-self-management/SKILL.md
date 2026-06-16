# OpenShell Sandbox Self-Management

You are running inside an **OpenShell sandbox**. The `openshell-sandbox` supervisor
wraps your process in a policy-enforced isolation environment. This skill helps you
understand that environment, diagnose issues, and propose changes to your own
configuration and policies.

## Your Architecture

```
┌─ Docker Container (openshell service) ─────────────────────────┐
│                                                                │
│  entrypoint.sh (root)                                          │
│  ├─ unshare --mount --propagation shared (mount namespace fix) │
│  ├─ socat (inbound: 0.0.0.0:PORT → 10.200.0.2:PORT)          │
│  └─ exec openshell-sandbox (PID 1 after exec)                 │
│      ├─ network namespace (veth pair)                          │
│      │    host: 10.200.0.1 (proxy + Docker DNS)               │
│      │    sandbox: 10.200.0.2 (you are here)                  │
│      ├─ HTTP CONNECT proxy (10.200.0.1:3128)                  │
│      │    every outbound TCP goes through this                 │
│      │    policy checked per-connection via OPA (host + binary)│
│      ├─ Landlock (filesystem restrictions, best_effort mode)   │
│      ├─ seccomp (syscall filters)                              │
│      ├─ bypass detection monitor (dmesg --follow + iptables    │
│      │    REJECT rules for direct connections that skip proxy) │
│      └─ openclaw gateway (your process, as sandbox user)       │
│                                                                │
│  Outbound path:                                                │
│  you → proxy (10.200.0.1:3128) → OPA policy check → dest      │
│                                                                │
│  Inbound path:                                                 │
│  nginx → socat (0.0.0.0:PORT) → you (10.200.0.2:PORT)         │
└────────────────────────────────────────────────────────────────┘
```

You run as the `sandbox` user (uid 998, gid 998) with restricted capabilities.
The supervisor runs as root and manages the isolation layers around you.

### Entrypoint sequence (from `openclaw_shell.entrypoint.sh`)
1. `unshare --mount --propagation shared` (for mount namespace isolation)
2. Bootstrap directories (workspace, skills, bin, hooks, agent-dir, qqbot data)
3. Deploy tools/hooks (no-clobber): `skills.sh`, `env_discover.sh`, hook scripts
4. Deploy base config (no-clobber for `openclaw.json`; workspace SOUL.md first-run only; agent-dir SOUL.md always updated)
5. Seed skills from `/tmp/openclaw/skills-seed/` (no-clobber)
6. Substitute env vars in `openclaw.json` (gateway token, base URL; port already set to 8995 in template)
7. Run startup hooks: `env-discover.sh` (patches SOUL.md)
8. Fix volume ownership (`chown -R sandbox:sandbox`)
9. Start socat inbound port forwarder (background)
10. Verify Jupyter Bridge connectivity (retries up to 45s)
11. `exec openshell-sandbox` with `--policy-rules` (Rego) + `--policy-data` (YAML)

## Key Paths

| Path | Access | Purpose |
|------|--------|---------|
| `/sandbox/.openclaw/openclaw.json` | rw | Your main config |
| `/sandbox/.openclaw/workspace/` | rw | Your workspace (memory, synth, skills) |
| `/sandbox/.openclaw/agents/main/agent/SOUL.md` | rw | Your agent identity |
| `/etc/openshell/policy.yaml` | **ro** | Sandbox network + filesystem policy (YAML data) |
| `/etc/openshell/sandbox-policy.rego` | **ro** | OPA Rego rules for policy evaluation |
| `/usr/lib/node_modules/openclaw/` | ro | OpenClaw installation |
| `/tmp/openclaw/` | rw | Template files + runtime logs |
| `/sandbox/notebooks/` | **ro** | Course materials (NFS mount) |
| `/sandbox/.openclaw/workspace/synth/` | rw | Shared synth volume (NFS mount, writable) |

## What You Can and Cannot Do

### You CAN
- Read and write files under `/sandbox/` and `/tmp/`
- Read your own config, policy, logs, and the OpenClaw installation
- Read course materials at `/sandbox/notebooks/` (read-only)
- Run `exec` commands as the `sandbox` user
- Make outbound connections to policy-allowed endpoints
- Modify your own `openclaw.json` and restart your gateway
- Update your workspace files, skills, memory, and SOUL.md

### You CANNOT
- Write to `/usr/`, `/etc/`, `/lib/`, `/bin/`, `/run/` or any read-only path (Landlock)
- Write to `/sandbox/notebooks/` (read-only NFS mount)
- Make outbound connections to endpoints not in the policy (proxy blocks)
- Connect to loopback (127.x) or link-local (169.254.x) through the proxy
- Escalate privileges or change your uid (seccomp + no sudo)
- Modify the policy file directly (it's on a read-only filesystem)
- Reach the network outside the proxy, since iptables REJECT rules fast-fail any direct connection

## Diagnosing Connection Issues

When a network request fails, check if it was policy-denied. The proxy logs
every decision to the container's stdout. From inside the sandbox:

```bash
# Check recent proxy decisions (run via exec tool)
# NOTE: You can't see container stdout directly. Ask the operator to check
# docker-compose logs for lines containing your destination host.
#
# The openshell-sandbox also logs to /var/log/openshell.log (if writable)
# and falls back to stdout-only if that path is not available.
```

A denied connection looks like:
```
action="deny" ... dst_host=example.com dst_port=443 ... reason=endpoint example.com:443 not in policy 'llm_inference'; ...
```

An allowed connection looks like:
```
action="allow" ... dst_host=llm_client dst_port=9000 ... policy="llm-inference"
```

### Common failures and what they mean

| Symptom | Proxy log | Cause | Fix |
|---------|-----------|-------|-----|
| `Connection error` | `action="deny"` | Endpoint not in policy | Add endpoint to `policy.yaml` |
| `Connection error` | `blocked: internal address` | SSRF protection | Add `allowed_ips` to endpoint |
| `Connection error` | `Proxy connection error: Connection refused` | Policy allowed but nothing listening | Wrong hostname/port or service down |
| `Connection error` | No proxy log at all | Bypass detection (iptables REJECT) | Process tried direct connection, not through proxy |
| `fetch failed` | `action="deny"` | Node.js respects `HTTP_PROXY` but dest blocked | Same as first row |

### Checking your network environment

```bash
# What proxy am I using?
echo $HTTP_PROXY $HTTPS_PROXY $http_proxy $https_proxy

# Can I resolve Docker service names?
# NOTE: Docker DNS (127.0.0.11) resolves on the host side of the namespace.
# From inside the sandbox, `getent hosts llm_client` will FAIL.
# The proxy resolves hostnames for you on the host side.
getent hosts llm_client   # expected: fails

# What's my IP inside the sandbox?
ip addr show | grep 10.200

# What's the policy say?
cat /etc/openshell/policy.yaml
```

## Understanding the Policy

The policy uses a two-file system. `/etc/openshell/policy.yaml` holds the data: the
endpoints, the filesystem rules, and the process identity. `/etc/openshell/sandbox-policy.rego`
holds the OPA Rego rules that evaluate that data.

The Rego rules define:
- `allow_network` evaluates each CONNECT request against the endpoint and the binary that opened it
- `deny_reason` returns specific diagnostics for debugging a denial
- `filesystem_policy`, `landlock_policy`, and `process_policy` pass through statically from the YAML

### Static (locked at container creation)
- `filesystem_policy`: which paths are read-only vs read-write
  - read_only: `/usr`, `/lib`, `/etc`, `/bin`, `/run`, `/dev/urandom`, `/proc`, `/var/log`
  - read_write: `/sandbox`, `/tmp`, `/dev/null`
- `landlock`: `compatibility: best_effort`
- `process`: `run_as_user: sandbox`, `run_as_group: sandbox`

You cannot change these without rebuilding the container.

### Dynamic (network_policies)
Each policy block has:
- **`name`**: human label for logs
- **`endpoints`**: list of `{host, port}` pairs the block allows
  - `allowed_ips`: CIDR list to override SSRF blocking for private IPs
  - `protocol: rest` + `tls: terminate`: enables L7 HTTP inspection
  - `access: read-only`: restricts to GET/HEAD/OPTIONS
- **`binaries`**: list of `{path}` entries naming which executables can use these endpoints
  (supports glob patterns like `/sandbox/.uv/python/**`)

**Both** the endpoint AND binary must match for a connection to be allowed.

### Current policy blocks (from source)

| Block | Name | Endpoints | Binaries |
|-------|------|-----------|----------|
| `docker-router` | docker-bridge | `docker-router:8070`, `10.200.0.1:8070` | node, curl |
| `llm_inference` | llm-inference | `llm_client:9000`, `10.200.0.1:9000`, `172.18.0.1:9000` | node, curl, python3, python3.13 |
| `lab_services` | lab-services | `lab:8888`, `nginx:80`, `10.200.0.1:8888/80` | node, curl |
| `npm_registry` | npm-registry | `registry.npmjs.org:443` | node, npm |
| `pypi` | pypi | `pypi.org:443`, `files.pythonhosted.org:443` | python3, python3.13, pip3, uv |

### Why both Docker hostnames AND 10.200.0.1?

From the policy source comments: "Docker Compose service names resolve via
Docker DNS on the host side of the network namespace. However, OpenClaw/Node.js
may pre-resolve hostnames to IPs before the CONNECT request reaches the proxy,
so we list both the Docker hostname AND the veth host IP (10.200.0.1) for each
internal service."

### Proposing policy changes

You cannot edit the policy file (read-only filesystem). When you need a new
endpoint, tell the operator what to add. Be specific:

```
I need to reach registry.npmjs.org:443 from /usr/bin/node.
Please add this to the npm_registry policy block in policy.yaml:

  endpoints:
    - { host: registry.npmjs.org, port: 443 }

And rebuild the container (policy is baked at image build time).
```

For internal Docker services (private IPs), remind them about `allowed_ips`:
```
  endpoints:
    - host: new_service
      port: 5000
      allowed_ips: ["172.16.0.0/12", "10.0.0.0/8"]
```

## Managing Your Own Config

Your config lives at `/sandbox/.openclaw/openclaw.json`. You can read, modify,
and apply changes.

```bash
# Read current config
cat ~/.openclaw/openclaw.json | jq .

# Check your model chain
jq -r '.agents.defaults.model' ~/.openclaw/openclaw.json

# Check what providers are configured
jq '.models.providers | keys' ~/.openclaw/openclaw.json

# Check plugin status
jq '.plugins' ~/.openclaw/openclaw.json
```

After modifying the config, use the `gateway` tool to apply changes:
```
gateway config.apply
```

Or restart manually:
```
gateway restart
```

### Config gotchas in sandboxed environments

1. **Base URLs must use Docker hostnames**, not IPs. The proxy resolves
   hostnames via Docker DNS on the host side. Example: `http://llm_client:9000/v1`
   not `http://10.200.0.1:9000/v1`. (Though `10.200.0.1` also works for
   services listed in the policy with `allowed_ips`.)

2. **Plugin entries for removed plugins cause startup failures.** If a plugin
   doesn't exist in the installed version, remove it from `plugins.entries`
   and `plugins.allow`.

3. **The `diagnostics.otel` section is the correct way to configure
   OpenTelemetry.** Don't use `plugins.entries.diagnostics-otel`, which no longer
   exists.

4. **`openclaw.json` is treated as immutable-from-template for env vars.** The
   entrypoint always re-substitutes `${OPENCLAW_GATEWAY_TOKEN}`, `${NVIDIA_BASE_URL}`,
   and `"port"` on every boot via `sed`. Runtime edits to these three fields will
   be overwritten on restart. Other fields (model config, tools, agents) survive
   restarts since `cp -n` protects the file from full replacement.

5. **The basePath is `/openclaw`.** The config template sets this, and the entrypoint
   does not rewrite it. The nginx route and healthcheck expect `/openclaw/`.

5. **`NO_PROXY=10.200.0.1,nginx`** is set in the environment to bypass the
   proxy for direct veth connections (both lowercase and uppercase variants).

## Build lineage

The container is built from `openclaw_shell.Dockerfile`:

```
Stage 1: ghcr.io/nvidia/openshell/cluster:0.0.8
  → extracts /opt/openshell/bin/openshell-sandbox

Stage 2: ghcr.io/nvidia/openshell-community/sandboxes/base:latest
  → installs jq, socat, tree, OPA v1.4.2
  → copies openshell-sandbox from stage 1
  → npm install -g openclaw@2026.5.28
  → copies template files (SOUL.md, openclaw.json, env_discover.sh)
  → copies entrypoint.sh
  → copies policy files to /etc/openshell/
```

Note: The cluster image tag is `0.0.8` but the embedded binary reports `0.0.7`
(image tag ≠ binary version).

## Docker Compose context

The `openclaw` service runs with:
- `privileged: true` + `NET_ADMIN` + `SYS_ADMIN` + `DAC_OVERRIDE`
  (needed for network namespace creation and Landlock setup)
- `apparmor=unconfined`, `seccomp=unconfined` (at container level; the
  sandbox binary applies its own seccomp internally)
- `init: false` (openshell-sandbox is PID 1)
- Network: `nvidia-openclaw` (default compose network)
- Port: 8995 (mapped host → socat → sandbox)
- Volume mounts:
  - `openclaw_user` → `/sandbox/.openclaw` (rw)
  - `sandbox_workspace` → `/sandbox/workspace` (rw)
  - `./notebooks` → `/sandbox/notebooks` (ro)
  - `./repo` → `/sandbox/repo` (ro)
  - `./papers` → `/sandbox/papers` (ro)
  - `openclaw_logs` → `/var/log` (rw)

## Environment Discovery

Run these to understand your current environment:

```bash
# OpenClaw version
openclaw --version

# OpenShell sandbox supervisor
openshell-sandbox --version

# What node version?
node --version

# What's installed globally?
npm list -g --depth=0

# System info
uname -a
id
cat /etc/os-release | head -5

# Disk usage
df -h /sandbox /tmp

# Process tree (see the supervisor above you)
ps auxf 2>/dev/null || ps aux
```

## Self-Improvement

This skill is a starting point. When you learn something new about your environment,
whether a path, a behavior, a quirk, or a version-specific change, **update this file**.

Things worth recording when you discover them:
- New endpoints you needed and why
- Config fields that changed between OpenClaw versions
- Workarounds for sandbox limitations
- Useful diagnostic commands you found
- Policy patterns that worked well

### Version tracking

When OpenClaw or the sandbox runtime updates, run discovery again and note
what changed:

```bash
# Compare installed version with what the skill was written for
openclaw --version
openshell-sandbox --version
# This skill was last verified against:
# OpenClaw: 2026.4.5
# Sandbox binary: openshell-sandbox 0.0.7 (from cluster:0.0.8 image)
# Base image: ghcr.io/nvidia/openshell-community/sandboxes/base:latest
# Build Dockerfile: cpu/services/openclaw/openclaw_shell.Dockerfile
# Policy format: YAML v1 + OPA Rego
```

If something doesn't match, investigate and update this skill.

### Source code reference

The actual source for this environment lives in the course repo:
- **Dockerfile:** `cpu/services/openclaw/openclaw_shell.Dockerfile`
- **Entrypoint:** `cpu/services/openclaw/openclaw_shell.entrypoint.sh`
- **Policy (YAML):** `cpu/services/openclaw/sandbox-policy.yaml`
- **Policy (Rego):** `cpu/services/openclaw/sandbox-policy.rego`
- **Docker Compose:** `docker-compose.yml` (root)

### Useful references

- OpenClaw OpenShell docs: use the packaged OpenClaw docs inside the image when present, or the upstream OpenClaw documentation for the installed version.
- OpenClaw sandboxing docs: use the packaged OpenClaw docs inside the image when present, or the upstream OpenClaw documentation for the installed version.
- OpenClaw config reference: https://docs.openclaw.ai/gateway/configuration
- OpenShell Community sandboxes: https://github.com/NVIDIA/OpenShell-Community
