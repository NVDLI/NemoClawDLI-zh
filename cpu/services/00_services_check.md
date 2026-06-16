---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400" height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Lab Services Health Check</b></font></h1>
<h2><b>Microservice diagnostic notebook</b></h2>
<br>

This notebook checks every microservice that course notebooks depend on.
Run it whenever you suspect a service is down, after a `docker-compose restart`,
or to confirm the environment is healthy before starting a module.

Each section corresponds to one `##`-delimited block in [`docker-compose.yml`](../../docker-compose.yml).
A green ✅ means the service responded correctly; ❌ means it needs attention.

---

## Imports & helpers

```python
import os, json, time, requests
from IPython.display import display, Markdown

def check(name, fn, *, detail=""):
    try:
        result = fn()
        print(f"✅  {name:<30} {result}")
    except Exception as e:
        print(f"❌  {name:<30} {e}  {detail}")

LLM_BASE  = os.environ.get("NVIDIA_BASE_URL", "http://llm_client:9000/v1")
```

---

## LLM Gateway: `llm_client:9000`

The only service that holds API credentials.  All other services tunnel through it.

```python
# Basic health + model inventory
def _llm_health():
    r = requests.get("http://llm_client:9000/health", timeout=10)
    r.raise_for_status()
    d = r.json()
    return f"backends={d['backends']} models={d['models']}"

check("llm_client /health", _llm_health)

# Smoke-test: one chat completion
def _llm_chat():
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
    llm = ChatNVIDIA(base_url=LLM_BASE, model="nvidia/nemotron-nano-12b-v2-vl", max_tokens=20)
    reply = llm.invoke("Reply with exactly: OK")
    return repr(reply.content[:40])

check("llm_client chat completion", _llm_chat)

# Smoke-test: embeddings
def _llm_embed():
    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
    emb = NVIDIAEmbeddings(base_url=LLM_BASE, model="nvidia/llama-nemotron-embed-vl-1b-v2")
    v = emb.embed_query("hello")
    return f"dim={len(v)}"

check("llm_client embeddings", _llm_embed)
```

---

## Docker Router: `docker_router:8070`

Lets notebooks restart containers, query logs, and inspect service state.

```python
def _dr_containers():
    r = requests.get("http://docker_router:8070/containers", timeout=10)
    r.raise_for_status()
    containers = r.json()
    running = [c for c in containers if c.get("status") == "running"]
    return f"{len(running)}/{len(containers)} containers running"

check("docker_router /containers", _dr_containers)
```

---

## OpenClaw / OpenShell: `openshell:8995`

Policy-governed agentic shell sandbox; the released course drives it in Modules 3 and 4.

```python
def _openclaw_health():
    r = requests.get("http://openshell:8995/openclaw/", timeout=10)
    r.raise_for_status()
    return f"HTTP {r.status_code}"

check("openclaw /openclaw/", _openclaw_health)
```

---

## Sandbox Admin: `sandbox-admin:8099`

Hot-swaps the OpenClaw sandbox policy; the released course uses it to switch between
permissive and hardened containment.

```python
def _sadmin():
    r = requests.get("http://sandbox-admin:8099/", timeout=10)
    # A 404 is acceptable here. The server is up but the root path is not registered.
    return f"HTTP {r.status_code}"

check("sandbox-admin /", _sadmin)
```

---

## Summary

```python
print("\nAll checks complete.")
```
