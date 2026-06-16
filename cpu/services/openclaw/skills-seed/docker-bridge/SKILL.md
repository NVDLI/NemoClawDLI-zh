---
name: docker-bridge
description: "Inspect and manage the lab's containers through docker_router, the HTTP service that fronts the Docker socket. Use when: (1) checking container status or health, (2) reading a container's logs, (3) restarting a container for diagnostics, (4) listing what is running. The sandbox never touches the Docker socket directly; every call goes through docker_router over the egress proxy."
---

# Docker Bridge

The sandbox cannot reach the Docker socket. Container introspection and lifecycle go
through `docker_router`, a small HTTP service that holds the socket and exposes a narrow
API. The agent calls it at `http://docker_router:8070` through the sandbox egress proxy
(`http://10.200.0.1:3128`); the proxy and the policy together decide what the agent may
reach.

Containers are addressed by their compose service name (`openclaw`, `llm_client`,
`sandbox-admin`, `lab`, `nginx`, `docker_router`). docker_router resolves the running
container from that label, so the hashed container name is never needed.

## API

Every call goes through the proxy. The pattern is:

```bash
/usr/bin/curl -s --proxy http://10.200.0.1:3128 http://docker_router:8070<path>
```

### Health

```bash
/usr/bin/curl -s --proxy http://10.200.0.1:3128 http://docker_router:8070/health | jq .
```

### List containers

```bash
/usr/bin/curl -s --proxy http://10.200.0.1:3128 http://docker_router:8070/containers | jq .
```

### Inspect one container

```bash
/usr/bin/curl -s --proxy http://10.200.0.1:3128 http://docker_router:8070/containers/openclaw | jq .
```

### Read logs

`/logs.txt` returns plain text; `/logs` returns the same under a `logs` JSON key.

```bash
/usr/bin/curl -s --proxy http://10.200.0.1:3128 "http://docker_router:8070/containers/openclaw/logs.txt?tail=120"
```

### Restart a container (diagnostic)

```bash
/usr/bin/curl -s --proxy http://10.200.0.1:3128 -X POST http://docker_router:8070/containers/openclaw/restart
```

Restarting `openclaw` restarts this agent. When the target is `openclaw`, explain the
command to the operator and let them run it from the host or lab shell rather than
restarting your own container mid-task.

## Lifecycle

`POST /lifecycle/{service}/{action}` (actions: `start`, `stop`, `restart`, `status`) is
the allow-listed lifecycle path. The allow-list is the security boundary: a service or
action that is not on it returns 403 before any Docker call runs, and essential services
(`lab`, `nginx`, `llm_client`) are deliberately off it so this path cannot take the lab
down.

```bash
/usr/bin/curl -s --proxy http://10.200.0.1:3128 -X POST http://docker_router:8070/lifecycle/openclaw/status
```

## When docker_router is unreachable

A failed call usually means the proxy denied the destination or docker_router is down.
Check the policy allows the `docker-router` egress group, then ask the operator to
confirm the service from the host with `docker compose ps docker_router`.

## Service names

| Service | What |
|---------|------|
| lab | JupyterLab and the student environment |
| llm_client | Model gateway (NIM / OpenAI / Bedrock) |
| openclaw | This agent's container (the sandbox) |
| sandbox-admin | Policy control plane (hot-swaps the active policy) |
| docker_router | Container lifecycle API (this service) |
| nginx | Reverse proxy |
