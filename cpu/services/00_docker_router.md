<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400" height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Lab Services</b></font></h1>
<h2><b>Service: Docker Router</b>: Container Orchestration for Notebooks</h2>
<br>

Every lab notebook that needs to restart a container, read service logs, or trigger an
assessment does so through `docker_router:8070`: a thin FastAPI proxy that wraps the
Docker socket behind a safe, network-accessible HTTP API.

---

## What it is

`docker_router` is a **FastAPI server** running at `docker_router:8070` inside the Docker
network.  It binds the host's Docker socket (`/var/run/docker.sock`) and exposes a small
set of read/restart operations so that notebooks never need to mount the socket themselves.

Defined in [`docker_router.py`](docker_router/docker_router.py) and built from the
[`Dockerfile`](docker_router/Dockerfile) in the same directory.  In the browser, reach it through the
lab's gated route at `/lab/svc/docker-router/`.

---

## Why it is implemented this way

Mounting the Docker socket directly into a notebook kernel is a security anti-pattern:
it gives arbitrary code root-equivalent access to the host.  `docker_router` solves this
by:

1. **Allowlisting operations**: only `list`, `inspect`, `logs`, and `restart` are
   exposed; no container creation or exec.
2. **Scoping visibility**: the router returns only containers whose names match the lab's
   compose project prefix, so nested student processes can not see unrelated infrastructure.
3. **Network-only access**: notebooks reach it over the Docker bridge network at
   `http://docker_router:8070`; the socket never leaves the container.

---

## Health validation

```python
import requests

r = requests.get("http://docker_router:8070/health", timeout=5)
r.raise_for_status()
print("docker_router:", r.json())

# Confirm the running containers are visible
containers = requests.get("http://docker_router:8070/containers", timeout=5).json()
running = [c for c in containers if c.get("status") == "running"]
print(f"{len(running)}/{len(containers)} containers running")
for c in running:
    print(f"  {c['name']:<45} {c['status']}")
```

---

## Basic API

### List all containers

```python
import requests, json

containers = requests.get("http://docker_router:8070/containers").json()
for c in containers:
    print(f"{c['name']:<45} {c['status']}")
```

### Fetch logs from a specific service

```python
import os
svc = f"{os.environ.get('COMPOSE_PROJECT_NAME','task1')}-llm_client-1"   # derive the prefix; never hardcode a course code
r = requests.get(f"http://docker_router:8070/containers/{svc}/logs?tail=50")
r.raise_for_status()
logs = r.json().get("logs", "")
print(logs[-3000:])   # last 3 000 chars
```

### Restart a container (diagnostic use)

```python
# Restarting drops in-flight requests, so only use this when instructed.
svc = f"{os.environ.get('COMPOSE_PROJECT_NAME','task1')}-openclaw-1"
r = requests.post(f"http://docker_router:8070/containers/{svc}/restart", timeout=30)
print(r.json())
```

### Full route reference

```python
r = requests.get("http://docker_router:8070/help")
import json; print(json.dumps(r.json(), indent=2))
```

---

## Practical: build a service dashboard

```python
import requests
from IPython.display import display, HTML

containers = requests.get("http://docker_router:8070/containers").json()

rows = ""
for c in containers:
    color = "#76B900" if c["status"] == "running" else "#cc3300"
    name = c["name"].split("-")[-1]   # strip compose prefix
    rows += f"<tr><td>{name}</td><td style='color:{color}'>{c['status']}</td></tr>"

display(HTML(f"""
<table style='font-family:monospace;border-collapse:collapse'>
  <tr><th style='text-align:left;padding:4px 12px'>Container</th>
      <th style='text-align:left;padding:4px 12px'>Status</th></tr>
  {rows}
</table>
"""))
```

---

## Advanced: tail live logs with polling

```python
import requests, time, IPython.display as ipd

def tail_service(name_fragment: str, lines: int = 30, polls: int = 5, interval: float = 2.0):
    """Poll a service's logs and stream updates to the notebook."""
    containers = requests.get("http://docker_router:8070/containers").json()
    target = next((c["name"] for c in containers if name_fragment in c["name"]), None)
    if not target:
        print(f"No container matching '{name_fragment}'"); return

    seen = set()
    for _ in range(polls):
        r = requests.get(f"http://docker_router:8070/containers/{target}/logs?tail={lines}")
        for line in r.json().get("logs", "").splitlines():
            if line not in seen:
                seen.add(line)
                print(line)
        time.sleep(interval)

tail_service("llm_client", lines=20, polls=3)
```

---

## Consumed by

The released course (nemoclaw, Securing Agents) does not call this service directly.
It is kept as **retained shared infrastructure** on `:8070`: it restarts the sandboxed
agent after a policy hot-swap and backs the `00_services_check.md` health-check notebook.
