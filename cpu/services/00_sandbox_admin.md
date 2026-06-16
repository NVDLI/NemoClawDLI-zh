<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400" height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Lab Services</b></font></h1>
<h2><b>Service: Sandbox Admin</b>: Policy Control Plane for OpenShell</h2>
<br>

`sandbox-admin` is the **control plane for OpenClaw's sandbox policy**.  While OpenClaw
runs the actual sandboxed agent, `sandbox-admin` lets a notebook hot-swap which policy
file is active, preview what a policy change would permit, and restart OpenClaw to apply
it, all without touching the file system directly.

---

## What it is

A lightweight **FastAPI server** at port 8099 that wraps three operations:

1. **Policy management**: read and replace [`sandbox-policy.yaml`](openclaw/sandbox-policy.yaml) at runtime.
2. **Service control**: restart OpenClaw after a policy swap via the Docker socket.
3. **Cron registry**: schedule recurring tasks inside the OpenClaw sandbox.

Source: [`sandbox_admin/app.py`](sandbox_admin/app.py).

---

## Why it is implemented this way

Directly editing `/etc/openclaw-policy.yaml` inside the container would require exec
access, which notebooks do not have.  `sandbox-admin` bridges this gap:

- **No exec needed**: the notebook makes an HTTP call; `sandbox-admin` holds the
  necessary file-system and Docker socket permissions.
- **Preview first**: `/admin/policy/preview` runs a dry-run diff so students can see
  what will change before committing.
- **Atomic swap**: policy write and container restart happen inside a single endpoint
  to avoid a window where the new policy is on disk but not yet loaded.

---

## Health validation

```python
import requests

ADMIN = "http://sandbox-admin:8099"
ADMIN_TOKEN = "dli-openclaw-token"   # fixed lab token; same across all courses
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

r = requests.get(f"{ADMIN}/admin/health", timeout=5)
# Returns 200 if running; 404 at root (/) is also acceptable.
print(f"sandbox-admin HTTP {r.status_code}")

# List registered services
services = requests.get(f"{ADMIN}/admin/services", headers=AUTH).json()
print(services)
```

---

## Basic API

### Read the current policy

```python
import requests, yaml

r = requests.get(f"{ADMIN}/admin/policy", headers=AUTH)
r.raise_for_status()
# /admin/policy returns raw YAML text, not JSON
policy_text = r.text
print(policy_text[:1000])
```

### Swap to a different policy

```python
import pathlib, requests

# Read a policy file from the openshell workspace
policy_text = pathlib.Path(
    "/sandbox/dli/cpu/services/openclaw/policy.hardened.yaml"
).read_text()

# Preview the diff first
preview = requests.post(
    f"{ADMIN}/admin/policy/preview",
    json={"policy_yaml": policy_text},
    headers=AUTH,
).json()
print("Changes:", preview)

# Apply and restart OpenClaw
r = requests.post(
    f"{ADMIN}/admin/policy/reload",
    json={"policy_yaml": policy_text},
    headers=AUTH,
    timeout=30,
)
r.raise_for_status()
print(r.json())
```

---

## Bounded shell: run a read-only command inside the sandbox

`POST /admin/sandbox/exec` runs a single command inside the OpenShell container and
returns its exit code and output. It is a narrow introspection channel, not a generic
shell: `argv[0]` must be on a small read-only allow-list, and for `openclaw` only its
read-only subcommands are permitted. Anything else is refused with `403` before a process
is started.

```python
import requests
ADMIN = "http://sandbox-admin:8099"
TOKEN = "dli-openclaw-token"

def exec_in_sandbox(argv):
    r = requests.post(f"{ADMIN}/admin/sandbox/exec",
                      headers={"Authorization": f"Bearer {TOKEN}"},
                      json={"argv": argv}, timeout=30)
    return r.status_code, (r.json() if r.ok else r.text)

# Allowed: read-only introspection
print(exec_in_sandbox(["openclaw", "--version"]))   # (200, {'exit_code': 0, 'output': 'OpenClaw 2026.5.28 ...'})
print(exec_in_sandbox(["whoami"]))                   # (200, {...})

# Refused before anything runs: not on the allow-list
print(exec_in_sandbox(["rm", "-rf", "/"])[0])        # 403
```

The allow-list (`_ALLOWED_ARGV0` and `_ALLOWED_OPENCLAW` in
`services/sandbox_admin/app.py`) is the boundary: `ls`, `cat`, `pwd`, `id`, `whoami`,
`uname`, `ps`, `stat`, `head`, `tail`, `wc`, `echo`, plus `openclaw status|health|--version|
docs|config get|config validate|exec-policy show|cron list`. This enumerable surface is
exactly what makes the degrees-of-freedom argument provable: the blast radius is a list.

---

## Practical: switch between permissive and hardened policies

```python
import pathlib, requests, time

ADMIN = "http://sandbox-admin:8099"
ADMIN_TOKEN = "dli-openclaw-token"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
POLICY_DIR = pathlib.Path("/sandbox/dli/cpu/services/openclaw")

def set_policy(name: str):
    """Switch OpenClaw to a named policy file and wait for restart."""
    text = (POLICY_DIR / f"policy.{name}.yaml").read_text()
    r = requests.post(f"{ADMIN}/admin/policy/reload", json={"policy_yaml": text},
                      headers=AUTH, timeout=30)
    r.raise_for_status()
    time.sleep(3)   # give OpenClaw time to restart
    print(f"Policy '{name}' applied: {r.json()}")

# Use permissive for demos, hardened for exercises
set_policy("permissive")
# ... run demo ...
set_policy("hardened")
```

---

## Advanced: schedule a recurring task

```python
import requests

# Register a cron-style job (runs inside the OpenClaw sandbox)
r = requests.post(
    f"{ADMIN}/admin/cron",
    json={
        "name":     "health-ping",
        "schedule": "*/5 * * * *",   # every 5 minutes
        "prompt":   "echo 'alive' >> /sandbox/.openclaw/logs/health.txt",
    },
    headers=AUTH,
    timeout=10,
)
r.raise_for_status()
print("Scheduled:", r.json())

# List registered jobs
jobs = requests.get(f"{ADMIN}/admin/cron", headers=AUTH).json()
print("Jobs:", jobs)

# Remove it
requests.delete(f"{ADMIN}/admin/cron/health-ping", headers=AUTH)
```

---

## Consumed by

The released course (nemoclaw, Securing Agents) uses this service in Modules 3 and 4 to
switch the sandboxed agent between permissive and hardened policies and demonstrate
containment. The admin API on `:8099` is also available to any in-lab experiment that
needs to hot-swap the OpenClaw policy.
