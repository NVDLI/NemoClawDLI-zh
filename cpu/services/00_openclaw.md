<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400" height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Lab Services</b></font></h1>
<h2><b>Service: OpenClaw / OpenShell</b>: The Sandboxed Agentic Shell</h2>
<br>

OpenClaw is a **policy-governed, sandboxed gateway** that gives an AI agent the ability
to execute shell commands, read and write files, and call web APIs, but only within the
bounds of a YAML policy file that an instructor controls.  It is reachable inside the
Docker network as both `openclaw:8995` (legacy name) and `openshell:8995` (current name).

---

## What it is

OpenClaw runs a full Linux environment inside a privileged container.  A gateway process
at port 8995 accepts:

1. **Natural-language prompts**: forwarded to `llm_client` for planning, then dispatched
   as tool calls back into the sandbox.
2. **WebSocket event streams**: each tool call (command start, stdout/stderr, exit code)
   is streamed as a structured JSON event to the caller.

The policy YAML (`sandbox-policy.yaml`) defines which filesystem paths, domains, and
shell commands are permitted.  The `sandbox-admin` service (port 8099) can hot-swap the
policy without restarting OpenClaw.

Source: `cpu/services/openclaw/`: Dockerfile, `ocstart/` helper modules,
`policy.hardened.yaml`, `policy.permissive.yaml`, and skill seed directories.

---

## Why it is implemented this way

**Privilege separation.** The notebook kernel (running as a normal user) never executes
shell commands directly.  All execution goes through the gateway, which enforces the
policy before any command reaches the OS.

**Policy-as-code.** Instructors version-control `sandbox-policy.yaml`.  Switching from
a permissive demo policy to a hardened exercise policy is a single API call to
`sandbox-admin`.

**Event streaming.** Because agent interactions are multi-step and can take tens of
seconds, the gateway streams tool events over WebSocket so the notebook can render
progress in real time.

**Skill library.** The `skills-seed/` directory pre-loads skills (one `SKILL.md` per
folder: a description plus the steps to follow). The agent selects a skill by matching a
request against its description, so its repertoire grows by adding files, not by
redeployment.

---

## Health validation

```python
import requests

r = requests.get("http://openshell:8995/health", timeout=10)
r.raise_for_status()
print(f"OpenClaw HTTP {r.status_code}: {'OK' if r.ok else 'FAIL'}")
```

The health check above confirms the gateway is reachable. The Basic API section below
drives a real agent turn over plain HTTP, and the WebSocket section shows the full
tool-event stream over `/cli/gateway`.

---

## Basic API

`/v1/responses` takes `model: "openclaw"` (the agent name, not a backend model
id), with the conversation key in the `x-openclaw-session-key` header. The
backend LLM is the agent's configured primary; override it only with an
allow-listed id via the `x-openclaw-model` header.

### HTTP passthrough (simple responses)

```python
import requests

GATEWAY = "http://openshell:8995"
TOKEN   = "dli-openclaw-token"

r = requests.post(
    f"{GATEWAY}/v1/responses",
    headers={"Authorization": f"Bearer {TOKEN}",
             "x-openclaw-session-key": "intro-session"},
    json={"model": "openclaw", "input": "What Python packages are installed?"},
    timeout=60,
)
r.raise_for_status()
print(r.json()["output"][0]["content"][0]["text"])
```

### WebSocket event stream (full tool visibility)

The HTTP surfaces (`/v1/responses`, `/v1/chat/completions`) collapse a whole agent run
into one assistant message: you see the final text but not the individual tool calls. To
watch exec invocations, exit codes, and command output as they happen, subscribe to the
JSON-RPC WebSocket at `/cli/gateway`. The handshake:

- Identify as `openclaw-control-ui` / `webchat` and request `role: "operator"` with
  `scopes: ["operator.read", "operator.write"]` in the connect params. The token alone
  does not grant scopes; the connect call has to ask.
- Send an `Origin: http://openshell:8995` header so the gateway treats the connection as
  a Control-UI request.
- Call `sessions.messages.subscribe` with `{key: <session_key>}`. Outbound events come
  back with the key namespaced as `agent:main:<session_key>`, so match the bare key as a
  suffix rather than an exact compare.
- Filter `event: "agent"` frames. The `command:<id>` stream carries exec output
  (`payload.data.output`, `exitCode`, `durationMs`); the terminal `phase: "end"` frame
  signals the run is done.

---

## Control UI: a webchat in the browser

The gateway also serves a browser Control UI. In the lab it is at
[`/lab/openclaw`](/lab/openclaw) (nginx gates it with your Jupyter session and injects
the gateway token, so it just works once you are in the lab). It is a chat window onto
the same agent the API talks to: type a prompt, watch the tool calls and output stream,
and inspect the session. Reach for it when you want to drive the agent by hand rather
than from a notebook cell.

One gotcha worth stating, because it is easy to trip on: the UI lives at the gateway's
base path, not its root. `http://openshell:8995/` returns `404` (it is the API host, not
a page); the UI is at `http://openshell:8995/lab/openclaw/`, which is what `/lab/openclaw`
proxies to. If you ever conclude "there is no UI" from hitting the root, that is why.

---

## Practical: compare two policies side by side

A useful exercise is to observe how the same prompt behaves under different policies.
You can drive that from any notebook:

```python
import requests

GATEWAY = "http://openshell:8995"
TOKEN   = "dli-openclaw-token"
PROMPT  = "Try to read /etc/passwd"

def run_with_session(session_key: str) -> str:
    r = requests.post(
        f"{GATEWAY}/v1/responses",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "x-openclaw-session-key": session_key},
        json={"model": "openclaw", "input": PROMPT},
        timeout=60,
    )
    return r.json()["output"][0]["content"][0]["text"] if r.ok else r.text

# Each call goes through the current active policy
print("Response:", run_with_session("policy-demo"))
```

To change the policy first, use `sandbox-admin` (see `00_sandbox_admin.md`).

---

## Starting and stopping the gateway: a least-privilege control surface

OpenClaw comes up when the lab boots, so it is ready when you open a notebook. You can
also start and stop it yourself, and the way that is wired is worth a look.

The kernel running your notebook holds no Docker socket. It cannot run `docker stop`,
reach the host daemon, or touch another container. The one process that can is
`docker_router`, and it exposes a single lifecycle endpoint behind an allow-list:

- **Services:** `openclaw` only (the sandboxed agent).
- **Actions:** `start`, `stop`, `restart`, `status`.
- Anything off the list returns `403` before a Docker call runs.

This is least privilege, not a deep result: the lab's essential services (`lab`,
`nginx`, `llm_client`) are not on the list, so this path cannot take the lab down
whatever a notebook or agent asks of it. It is a useful bound on one narrow surface. It
is not what contains the agent's own actions; that is the kernel sandbox in the next
section.

```python
import requests
ROUTER = "http://docker_router:8070"

# Stop the gateway, check it is down, bring it back:
print(requests.post(f"{ROUTER}/lifecycle/openclaw/stop",   timeout=60).json())
print(requests.post(f"{ROUTER}/lifecycle/openclaw/status", timeout=30).json())
print(requests.post(f"{ROUTER}/lifecycle/openclaw/start",  timeout=120).json())

# Off the allow-list -> refused before Docker is touched:
print(requests.post(f"{ROUTER}/lifecycle/llm_client/stop", timeout=30).status_code)  # 403
print(requests.post(f"{ROUTER}/lifecycle/openclaw/delete", timeout=30).status_code)  # 403
```

The allow-list is `LIFECYCLE_SERVICES` in `services/docker_router/docker_router.py`.
You widen it by editing that file in version control, where a reviewer sees the change;
a running agent cannot.

---

## What actually contains the agent: OpenShell's kernel layers

The policy file and the allow-list above bound what gets *asked for*. What enforces a
bound regardless of what the model decides is OpenShell: the agent's shell runs under
four kernel-level mechanisms, each denying by default.

| Layer | Kernel mechanism | What it stops |
| :--- | :--- | :--- |
| Filesystem | Landlock LSM | reads and writes outside the allowed paths, at the syscall level |
| Syscalls | seccomp-bpf | calls outside the permitted set (`ptrace`, `mount`, `setuid`, ...) |
| Network | network namespace | direct egress; the shell has no route off-box of its own |
| Egress policy | OPA-evaluated CONNECT proxy | outbound connections to hosts or ports the policy does not allow |

A system-prompt rule like "do not exfiltrate secrets" is a request the model can be
talked out of by a crafted document or a malicious tool result. A kernel denial is not:
if the model decides to disobey, the syscall returns `EACCES` or `EPERM` and the action
does not happen. This is least authority applied to an agent, the discipline OS designers
worked out decades ago.

It is a bound, not a promise of safety. The sandbox does not stop the agent from giving a
wrong answer, from being steered by a poisoned input into a permitted-but-unwise action,
or from a policy written too loosely in the first place. It stops the class of harm that
lives below the policy line. To see where each layer's bound begins and ends, run the
same prompt under a permissive and a hardened policy (the side-by-side cell above) and
watch the kernel refuse the action the policy forbids.

---

## Skills: give the agent a reusable workflow

A skill is a folder under the agent's workspace skills directory
(`/sandbox/ocspace/skills/<name>/SKILL.md`, a volume this kernel shares) holding a
markdown file: YAML frontmatter with a `name` and a `description`, then the steps to
follow. The `description` is the retrieval key. The agent reads the skills it has and
pulls one in mid-turn when a request matches that description; you do not call it by name.

The cell below writes a small multi-step workflow skill, then asks for something that
matches it. Watch the agent run the steps and summarise.

```python
import pathlib, requests

skill = """---
name: dir-report
description: "Produce a short inventory report on a directory. Use when the user asks to summarize, inventory, or report on the contents of a folder or path."
---
# Directory report

When asked to report on a directory PATH, run these steps in order, then summarise:

1. Count the files:  find PATH -type f | wc -l
2. Total size:       du -sh PATH
3. Largest files:    ls -lS PATH | head -6

Then give three bullets: how many files, the dominant file types, and the total size.
"""

# The agent's skills live on a volume this kernel shares, so writing the file is enough.
d = pathlib.Path("/sandbox/ocspace/skills/dir-report")
d.mkdir(parents=True, exist_ok=True)
(d / "SKILL.md").write_text(skill)

r = requests.post(
    "http://openshell:8995/v1/responses",
    headers={"Authorization": "Bearer dli-openclaw-token",
             "x-openclaw-session-key": "skills-demo"},
    json={"model": "openclaw",
          "input": "Give me an inventory report on /sandbox/ocspace/skills."},
    timeout=120,
)
print(r.json()["output"][-1]["content"][0]["text"])
```

The seeded skills in the same directory (`docker-bridge`, `sandbox-self-management`,
`skills-manager`, and `caveman`) are larger examples of the same shape: a description for
retrieval and a body of steps the agent follows. A skill can grow from a single successful
trajectory into a reusable library entry that a later session loads on demand.

---

## Consumed by

The released course (nemoclaw, Securing Agents) is the primary consumer: Modules 3 and 4
drive this gateway as the policy-governed sandboxed agent, demonstrating how the kernel
contains the code the agent runs on the student's behalf and how a policy hot-swap changes
what it can reach. The OpenAI-compatible API on `:8995` is also available to any in-lab
experiment that wants a sandboxed agent.
