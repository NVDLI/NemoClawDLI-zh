from __future__ import annotations

import json
import os
import subprocess
from html import escape
from typing import Any, Dict, List, Optional

import docker
import httpx
from docker.errors import DockerException, NotFound
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="DLI Docker Router", version="1.1")


def docker_client():
    return docker.from_env()


def container_record(container):
    attrs = container.attrs or {}
    state = attrs.get("State", {})
    ports = attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
    image_tags = getattr(container.image, "tags", []) or []
    return {
        "id": container.id[:12],
        "name": container.name,
        "status": container.status,
        "image": image_tags[0] if image_tags else str(container.image.short_id),
        "created": attrs.get("Created"),
        "health": (state.get("Health") or {}).get("Status"),
        "ports": ports,
    }


@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        containers = docker_client().containers.list(all=True)
        rows = "".join(
            f"<tr><td>{escape(c.name)}</td><td>{escape(c.status)}</td>"
            f"<td><a href='/containers/{escape(c.name)}/logs?tail=120'>logs</a></td></tr>"
            for c in sorted(containers, key=lambda x: x.name)
        )
        status = f"{len(containers)} containers visible"
    except DockerException as exc:
        rows = f"<tr><td colspan='3'>Docker unavailable: {escape(str(exc))}</td></tr>"
        status = "Docker unavailable"
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DLI Docker Router</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 32px; line-height: 1.45; }}
    code, pre {{ background: #f4f4f4; padding: 2px 5px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
    .muted {{ color: #666; }}
  </style>
</head>
<body>
  <h1>DLI Docker Router</h1>
  <p class="muted">{escape(status)}. Use this only for course diagnostics and assessment support.</p>
  <p><code>/containers</code> lists containers. <code>/containers/&lt;name&gt;/logs?tail=200</code> returns recent logs.</p>
  <p><a href="/docs">OpenAPI docs</a> · <a href="/health">health</a> · <a href="/containers">containers JSON</a></p>
  <table><thead><tr><th>Container</th><th>Status</th><th>Logs</th></tr></thead><tbody>{rows}</tbody></table>
</body>
</html>
"""


@app.get("/help")
async def help_route():
    return {
        "routes": {
            "/": "HTML diagnostic interface",
            "/health": "JSON health check",
            "/healthy": "legacy boolean health check",
            "/containers": "list visible Docker containers",
            "/containers/{container_name}": "container metadata",
            "/containers/{container_name}/logs?tail=200": "recent logs",
            "/containers/{container_name}/logs.txt?tail=200": "plain-text recent logs",
            "/containers/{container_name}/restart": "restart a container; diagnostic use only",
            "/lifecycle/{service}/{action}": "start|stop|restart|status an allow-listed service (openclaw); the allow-list is the security boundary",
        }
    }


@app.get("/health")
async def health():
    try:
        docker_client().ping()
        return {"ok": True, "docker": "reachable"}
    except DockerException as exc:
        return {"ok": False, "docker": "unreachable", "error": str(exc)}


@app.get("/healthy")
async def healthy():
    return (await health()).get("ok", False)


@app.get("/containers")
async def list_containers(all: bool = True):
    containers = docker_client().containers.list(all=all)
    return [container_record(container) for container in sorted(containers, key=lambda x: x.name)]


@app.get("/containers/{container_name}")
async def get_container(container_name: str):
    try:
        return container_record(docker_client().containers.get(container_name))
    except NotFound:
        return {"error": f"Container `{container_name}` not found"}


@app.get("/containers/{container_name}/logs")
async def get_container_logs(container_name: str, tail: int = Query(200, ge=1, le=5000)):
    try:
        logs = docker_client().containers.get(container_name).logs(tail=tail)
        return {"container": container_name, "tail": tail, "logs": logs.decode("utf-8", errors="replace")}
    except NotFound:
        return {"error": f"Container `{container_name}` not found"}


@app.get("/containers/{container_name}/logs.txt", response_class=PlainTextResponse)
async def get_container_logs_text(container_name: str, tail: int = Query(200, ge=1, le=5000)):
    try:
        logs = docker_client().containers.get(container_name).logs(tail=tail)
        return logs.decode("utf-8", errors="replace")
    except NotFound:
        return f"Container `{container_name}` not found"


@app.post("/containers/{container_name}/restart")
async def restart_container(container_name: str):
    try:
        container = docker_client().containers.get(container_name)
        container.restart()
        return {"ok": True, "status": f"Container {container_name} restarted successfully"}
    except NotFound:
        return {"ok": False, "error": f"Container {container_name} not found"}


# Bounded lifecycle surface. Only allow-listed services and verbs reach Docker.
# Essential services stay off-list, so this endpoint cannot take the lab down.
LIFECYCLE_SERVICES = {"openclaw"}
LIFECYCLE_ACTIONS  = {"start", "stop", "restart", "status"}

# The allow-list is the boundary: off-list service or action returns 403 before Docker.


def _service_container(client, service: str):
    # Resolve by the compose-service label so the project name prefix never matters.
    found = client.containers.list(all=True, filters={"label": f"com.docker.compose.service={service}"})
    return found[0] if found else None


def _project_config(client):
    """Read how THIS stack was launched (project name, working dir, compose files)
    straight off a live container's labels, so an on-demand `compose up` matches
    the running deployment exactly instead of guessing paths."""
    any_c = client.containers.list(all=True, limit=1,
        filters={"label": "com.docker.compose.project"})
    if not any_c:
        return None
    lbl = any_c[0].labels or {}
    files = [p for p in (lbl.get("com.docker.compose.project.config_files") or "").split(",") if p]
    return {
        "project": lbl.get("com.docker.compose.project"),
        "working_dir": lbl.get("com.docker.compose.project.working_dir"),
        "files": files,
    }


def _compose_create_and_start(client, service: str):
    """Create + start a profiled (not-yet-created) service via the same compose
    project that launched the stack. Needs the project dir visible inside this
    container at its host path (the docker_router self-path mount); without it the
    config files are unreadable and we say so plainly rather than guess."""
    cfg = _project_config(client)
    if not cfg or not cfg["files"] or not cfg["working_dir"]:
        raise HTTPException(status_code=409, detail="cannot resolve the compose project for on-demand create")
    if not os.path.isfile(cfg["files"][0]):
        raise HTTPException(status_code=409, detail=(
            f"on-demand create needs the project dir mounted into docker_router at its host path "
            f"({cfg['working_dir']}); set HOST_PROJECT_DIR and recreate docker_router, or start "
            f"'{service}' from the orchestrator"))
    cmd = ["docker", "compose", "-p", cfg["project"], "--project-directory", cfg["working_dir"]]
    for f in cfg["files"]:
        cmd += ["-f", f]
    cmd += ["up", "-d", "--no-recreate", "--no-build", service]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"compose up timed out starting '{service}'")
    if proc.returncode != 0:
        raise HTTPException(status_code=502, detail=f"compose up failed: {proc.stderr.strip()[:500]}")


@app.post("/lifecycle/{service}/{action}")
async def lifecycle(service: str, action: str):
    """Start / stop / restart / status an allow-listed service. Anything off the
    allow-list is refused with 403, so the reachable state space is finite and
    auditable. On-demand services that are not yet created are stood up through
    the project's own compose config. This is the provable-security lesson in
    services/00_openclaw.md."""
    if service not in LIFECYCLE_SERVICES:
        raise HTTPException(status_code=403,
            detail=f"service '{service}' is not in the lifecycle allow-list {sorted(LIFECYCLE_SERVICES)}")
    if action not in LIFECYCLE_ACTIONS:
        raise HTTPException(status_code=403,
            detail=f"action '{action}' is not allowed; choose from {sorted(LIFECYCLE_ACTIONS)}")
    try:
        client = docker_client()
        c = _service_container(client, service)
        if action == "status":
            if c is None:
                return {"service": service, "action": action, "status": "not_created"}
        elif action == "start":
            if c is None:                         # profiled + never created: stand it up via compose
                _compose_create_and_start(client, service)
                c = _service_container(client, service)
            elif c.status != "running":
                c.start()
        elif action == "stop":
            if c is None:
                return {"service": service, "action": action, "status": "not_created"}
            c.stop(timeout=10)
        elif action == "restart":
            if c is None:
                _compose_create_and_start(client, service)
                c = _service_container(client, service)
            else:
                c.restart(timeout=10)
        if c is None:
            raise HTTPException(status_code=502, detail=f"service '{service}' did not come up")
        c.reload()
        return {"service": service, "action": action, "container": c.name,
                "status": c.status, "health": (c.attrs.get("State", {}).get("Health") or {}).get("Status")}
    except NotFound:
        raise HTTPException(status_code=404, detail=f"container for '{service}' not found")
    except DockerException as exc:
        raise HTTPException(status_code=502, detail=f"docker error: {exc}")




class Key(BaseModel):
    nvapi_key: str = Field(..., description="Legacy course helper; should start with nvapi-.")

    @field_validator("nvapi_key")
    @classmethod
    def check_nvapi_prefix_function(cls, value: str):
        if not value.startswith("nvapi-"):
            raise ValueError('nvapi_key must start with "nvapi-"')
        return value


API_KEY: Optional[str] = None


@app.post("/set_key/")
async def set_key(key: Key):
    global API_KEY
    API_KEY = key.nvapi_key
    return {"result": "Key set successfully"}


@app.get("/get_key/")
async def get_key():
    return {"nvapi_key": API_KEY}


# ── Assessment runner ─────────────────────────────────────────────────────────

class AssessmentRequest(BaseModel):
    # Research-agent assessment cases: {question, trace, answer}.
    submission: List[Dict[str, Any]] = Field(..., description="Graded cases")
    model_specs: Dict[str, str] = Field(
        default_factory=lambda: {
            "model":    "nvidia/nemotron-3-nano-30b-a3b",
            "base_url": "http://llm_client:9000/v1",
        }
    )
    visualization_file: str = Field("/dli/outputs/assessment_traces.html")


class RerunRequest(BaseModel):
    submission: List[Dict[str, Any]] = Field(...)
    indices: Optional[List[int]] = None
    model_specs: Dict[str, str] = Field(
        default_factory=lambda: {
            "model":    "nvidia/nemotron-3-nano-30b-a3b",
            "base_url": "http://llm_client:9000/v1",
        }
    )


class RubricRequest(BaseModel):
    submission: Any                     # student's answer object (any JSON)
    model_specs: Dict[str, str] = Field(
        default_factory=lambda: {
            "model":    "nvidia/nemotron-nano-12b-v2-vl",
            "base_url": "http://llm_client:9000/v1",
        }
    )
    rubric: Optional[str] = None        # optional grading rubric


@app.post("/run_assessment")
async def run_assessment_endpoint(req: AssessmentRequest):
    """
    The first-class running assessment (research-agent grader ported from
    c-fx-25-v1): per-case structural checks + an EvaluationTrace LLM-judge,
    a registry, a PyVis trace visualization, and a >=80/100 PASSED gate. The
    grader lives at /app/assessment/run_assessment.py (mounted by compose).
    """
    from assessment.run_assessment import run_assessment
    return run_assessment(
        req.submission,
        model_specs=req.model_specs,
        visualization_file=req.visualization_file,
    )


@app.post("/run_assessment/rerun")
async def rerun_tests(req: RerunRequest):
    from assessment.run_assessment import get_registry
    registry = get_registry()
    submission = {"submission": req.submission}
    if req.indices is not None:
        results = [registry.rerun(idx, submission) for idx in req.indices]
    else:
        results = registry.rerun_failed(submission)
    return {
        "rerun_results": results,
        "summary": {
            "total":  len(registry.list_all()),
            "passed": len(registry.list_passed()),
            "failed": len(registry.list_failed()),
        },
    }


@app.get("/run_assessment/summary")
async def assessment_summary():
    from assessment.run_assessment import get_test_summary
    return get_test_summary()


@app.post("/grade_rubric")
async def grade_rubric(req: RubricRequest):
    """
    Lightweight rubric grader (the prior /run_assessment). Retained as a
    standalone self-check endpoint; the first-class graded assessment is
    /run_assessment above.
    """
    base_url = req.model_specs.get("base_url", "http://llm_client:9000/v1")
    model    = req.model_specs.get("model",    "nvidia/nemotron-nano-12b-v2-vl")
    rubric   = req.rubric or (
        "Evaluate the following AI agent submission.  Provide:\n"
        "1. A score out of 10.\n"
        "2. One-paragraph justification.\n"
        "3. Up to 3 specific suggestions for improvement.\n"
        "Be concise and constructive."
    )

    submission_text = (
        json.dumps(req.submission, indent=2)
        if not isinstance(req.submission, str)
        else req.submission
    )

    messages = [
        {"role": "system", "content": rubric},
        {"role": "user",   "content": f"Student submission:\n\n{submission_text[:4000]}"},
    ]

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{base_url}/chat/completions",
                json={"model": model, "messages": messages, "temperature": 0},
            )
            r.raise_for_status()
            data    = r.json()
            verdict = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}")

    return {
        "result":   verdict,
        "messages": messages,
        "model":    model,
    }
