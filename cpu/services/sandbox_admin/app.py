"""
sandbox-admin is the minimal control plane for the OpenShell-sandboxed OpenClaw
deployment in the course lab.

The endpoints below expose the `sandbox_admin.SandboxAdmin` helper surface. Read
endpoints do real work. Mutating endpoints write to the mounted policy file and the
openclaw cron directory; if the underlying reload mechanism (SIGHUP, control endpoint,
etc.) isn't wired up the response carries `X-Reload-Effected: deferred`.

By design this is a tiny stub. Don't expand it without a security review. It
holds a read-only docker socket and a read-write mount of the sandbox policy.
"""
from __future__ import annotations

import os
import json
import threading
import time
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Response

try:
    import docker  # type: ignore
    _docker_client: Optional["docker.DockerClient"] = docker.from_env()  # type: ignore[attr-defined]
except Exception:  # pragma: no cover (docker socket may be absent in tests)
    _docker_client = None


POLICY_PATH = Path(os.environ.get("POLICY_PATH", "/policy/sandbox-policy.yaml"))
TOKEN = os.environ.get("SANDBOX_ADMIN_TOKEN", "dli-openclaw-token")
TARGET = os.environ.get("SANDBOX_TARGET_CONTAINER", "openclaw")
CRON_DIR = Path("/sandbox/.openclaw/cron")
CRON_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="sandbox-admin", version="0.1.0")


# ─── auth ──────────────────────────────────────────────────────────────────

def _auth(authorization: Optional[str] = Header(None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != TOKEN:
        raise HTTPException(403, "invalid token")


# ─── discovery ─────────────────────────────────────────────────────────────

@app.get("/admin/health")
def health() -> dict:
    return {"status": "ok", "policy_exists": POLICY_PATH.exists(),
            "docker_available": _docker_client is not None}


@app.get("/admin/services", dependencies=[Depends(_auth)])
def services() -> list:
    if _docker_client is None:
        return []
    out = []
    for c in _docker_client.containers.list(all=True):
        out.append({
            "name": c.name,
            "image": (c.image.tags or ["<none>"])[0],
            "status": c.status,
        })
    return out


# ─── policy ────────────────────────────────────────────────────────────────

@app.get("/admin/policy", dependencies=[Depends(_auth)])
def policy() -> Response:
    if not POLICY_PATH.exists():
        raise HTTPException(404, f"policy file not present at {POLICY_PATH}")
    return Response(POLICY_PATH.read_text(), media_type="application/x-yaml")


@app.post("/admin/policy/preview", dependencies=[Depends(_auth)])
def policy_preview(body: dict = Body(...)) -> dict:
    yaml_text = body.get("policy_yaml")
    if not isinstance(yaml_text, str):
        raise HTTPException(400, "policy_yaml is required (string)")
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise HTTPException(400, f"yaml parse failed: {e}")
    if not isinstance(parsed, dict):
        raise HTTPException(400, "policy root must be a mapping")
    # Cheap structural validation. The full schema check is upstream's job.
    expected = {"network_policies", "filesystem_policy", "process"}
    found = expected & parsed.keys()
    return {"status": "ok", "expected_keys_found": sorted(found),
            "byte_size": len(yaml_text.encode("utf-8"))}


@app.post("/admin/policy/reload", dependencies=[Depends(_auth)])
def policy_reload(body: dict = Body(...)) -> Response:
    """Write the new policy and restart the target container.

    openshell-sandbox enforces its policy at boot (Landlock + seccomp +
    netns are set up before the agent process is forked). It does not
    re-read the policy YAML on SIGHUP, so the only way the reload takes
    effect is to restart the container. We do exactly that here,
    after validating the YAML parses.

    Callers can opt out of the restart with `{"restart": false}` if they
    plan to drive the restart themselves (e.g. for batched changes).
    """
    yaml_text = body.get("policy_yaml")
    if not isinstance(yaml_text, str):
        raise HTTPException(400, "policy_yaml is required (string)")
    try:
        yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise HTTPException(400, f"yaml parse failed: {e}")
    POLICY_PATH.write_text(yaml_text)

    do_restart = body.get("restart", True)
    reload_effected = "deferred"
    if do_restart and _docker_client is not None:
        try:
            container = _docker_client.containers.get(TARGET)
            # Manual stop/start gives fast SIGKILL fallback and returns after the container is back.
            container.stop(timeout=5)
            container.start()
            reload_effected = "restarted"
        except Exception as e:
            reload_effected = f"deferred: {e}"

    payload = {"status": "ok", "policy_path": str(POLICY_PATH),
               "reload_effected": reload_effected}
    return Response(
        content=json.dumps(payload),
        media_type="application/json",
        headers={"X-Reload-Effected": reload_effected},
    )


# ─── cron ──────────────────────────────────────────────────────────────────

def _cron_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_")
    if not safe:
        raise HTTPException(400, "name must be non-empty alphanumeric")
    return CRON_DIR / f"{safe}.json"


@app.get("/admin/cron", dependencies=[Depends(_auth)])
def cron_list() -> list:
    return [json.loads(p.read_text()) for p in CRON_DIR.glob("*.json")]


@app.post("/admin/cron", dependencies=[Depends(_auth)])
def cron_register(body: dict = Body(...)) -> dict:
    for key in ("name", "schedule", "prompt"):
        if key not in body:
            raise HTTPException(400, f"missing key: {key}")
    entry = {
        "name": body["name"],
        "schedule": body["schedule"],
        "prompt": body["prompt"],
        "registered_at": time.time(),
    }
    _cron_path(entry["name"]).write_text(json.dumps(entry, indent=2))
    return entry


@app.delete("/admin/cron/{name}", dependencies=[Depends(_auth)])
def cron_delete(name: str) -> dict:
    path = _cron_path(name)
    if not path.exists():
        raise HTTPException(404, f"cron entry not found: {name}")
    path.unlink()
    return {"name": name, "deleted": True}


# ─── sandbox exec ──────────────────────────────────────────────────────────

# Only a small allowlist of obviously read-only commands.
# The point of /admin/sandbox/exec is introspection from the notebook, not a generic shell.
_ALLOWED_ARGV0 = frozenset({
    "ls", "cat", "pwd", "id", "whoami", "uname",
    "ps", "stat", "head", "tail", "wc", "echo",
})

# Expose only read-only openclaw introspection verbs through this bounded channel.
_ALLOWED_OPENCLAW = (
    ("status",),
    ("health",),
    ("--version",),
    ("-V",),
    ("docs",),
    ("config", "get"),
    ("config", "validate"),
    ("exec-policy", "show"),
    ("cron", "list"),
)


def _openclaw_readonly(argv: list) -> bool:
    sub = tuple(argv[1:])
    return any(sub[: len(p)] == p for p in _ALLOWED_OPENCLAW)


@app.post("/admin/sandbox/exec", dependencies=[Depends(_auth)])
def sandbox_exec(body: dict = Body(...)) -> dict:
    argv = body.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise HTTPException(400, "argv must be a non-empty list of strings")
    if argv[0] == "openclaw":
        if not _openclaw_readonly(argv):
            raise HTTPException(403, f"openclaw subcommand {argv[1:]!r} is not in the read-only allowlist")
    elif argv[0] not in _ALLOWED_ARGV0:
        raise HTTPException(403, f"argv[0]={argv[0]!r} not in read-only allowlist")
    if _docker_client is None:
        raise HTTPException(503, "docker socket not available")
    try:
        container = _docker_client.containers.get(TARGET)
    except Exception as e:
        raise HTTPException(502, f"target container not reachable: {e}")
    rc = container.exec_run(argv, demux=False)
    return {
        "exit_code": rc.exit_code,
        "output": rc.output.decode("utf-8", errors="replace") if rc.output else "",
    }
