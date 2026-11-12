# NeMoClaw Local Startup Guide (Non-Brev)

This guide covers two deployment targets:

- **Windows 11 + WSL2 + Docker** — run everything inside Ubuntu-24.04 on WSL2
- **DGX Spark Station (native Ubuntu Linux)** — same steps, native Docker; access pages either directly from the DGX's own browser (Firefox) at `http://localhost:8081`, or from a Windows browser via SSH tunnel (see § 0.5)

Section 0 is **one-time setup** (skip if `nemoclaw --version` already works).
Section 1 onward is the **every-session startup** after setup is complete.

---

## 0 — One-Time Setup (First Time Only)

### 0.1 Windows 11 + WSL2 + Docker

**Install WSL2 with Ubuntu 24.04** (PowerShell as Administrator):
```powershell
wsl --install -d Ubuntu-24.04
wsl --set-default Ubuntu-24.04
```

**Configure `~/.bashrc`** inside Ubuntu-24.04 (adds NeMoClaw to PATH):
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
export PATH="$HOME/.local/bin:$PATH"
export no_proxy="${no_proxy},localhost,127.0.0.1,::1"
export NO_PROXY="${NO_PROXY},localhost,127.0.0.1,::1"
```
Then `source ~/.bashrc`.

**Install Docker Engine** (not Docker Desktop) inside Ubuntu-24.04:
follow https://docs.docker.com/engine/install/ubuntu/. Then add to `/etc/wsl.conf` so Docker starts automatically:
```ini
[boot]
command = service docker start
```

**Install aiohttp**:
```bash
pip3 install aiohttp --break-system-packages
```

### 0.2 DGX Spark Station (native Ubuntu Linux)

**Add your user to the Docker group** (run once, then log out and back in):
```bash
sudo usermod -aG docker $USER
newgrp docker   # apply in current session without re-login
docker ps       # verify — should list containers without permission error
```

**Install aiohttp**:
```bash
pip3 install aiohttp --break-system-packages
```

**China network only — add Docker Hub mirrors** (Docker Hub is blocked in China):
```bash
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://docker.m.daocloud.io",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
docker pull hello-world   # verify mirrors work
```

**Generate an SSH key and register it with GitHub**:
```bash
# 1. Generate key (press Enter for all prompts — default path, no passphrase)
ssh-keygen -t ed25519 -C "your-email@example.com"

# 2. Copy the public key
cat ~/.ssh/id_ed25519.pub
```
Go to **github.com → Settings → SSH and GPG keys → New SSH key**, paste the output, and save.

Verify the key is accepted:
```bash
ssh -T git@github.com
# Expected: Hi <your-github-username>! You've successfully authenticated...
```

**Clone the course repo**:
```bash
git clone git@github.com:<your-github-username>/NemoClawDLI-zh.git ~/nemoclaw-zh
```

### 0.3 NeMoClaw Installation (both platforms)

Run in the terminal where you'll use NeMoClaw (Ubuntu-24.04 terminal for WSL2; any terminal for DGX):

```bash
# Two-step form avoids pipe-to-bash stdin freeze on slow connections:
curl -fsSL https://www.nvidia.com/nemoclaw.sh -o /tmp/nemoclaw-install.sh
bash /tmp/nemoclaw-install.sh
source ~/.bashrc
nemoclaw --version    # expected: nemoclaw v0.0.55 or newer
```

> **Note:** `curl ... | bash` can freeze if the download is slow (pipe consumes stdin).
> The two-step form above avoids this.

### 0.4 NeMoClaw Onboarding (both platforms)

> ⚠️ **WSL2 only**: Always prefix with `NEMOCLAW_SANDBOX_GPU=0`. Without it, onboarding forces
> `--gpu` and produces a broken sandbox on WSL2.

> ⚠️ **DGX + SSH**: Onboarding downloads container images and can take 30–90 minutes on a slow
> connection. Run it inside `tmux` so an SSH disconnect does not kill the process:
> ```bash
> tmux new-session -s nemoclaw
> # run onboarding inside this tmux window
> # if SSH drops, reconnect and run: tmux attach -t nemoclaw
> ```

> ⚠️ **DGX + pip openshell venv**: If you installed openshell via pip into a virtualenv,
> **deactivate the venv before running `nemoclaw onboard`**. Otherwise nemoclaw detects the
> pip version (0.0.109) and tries to downgrade, which fails if GitHub is unreachable.
> ```bash
> deactivate       # exit any active venv
> which openshell  # must show /usr/local/bin/openshell
> ```

```bash
# WSL2:
NEMOCLAW_SANDBOX_GPU=0 nemoclaw onboard

# DGX (native Linux, inside tmux, venv deactivated):
nemoclaw onboard
```

During onboarding select:
- Provider: **NVIDIA Endpoints** (`integrate.api.nvidia.com`) — recommended; works everywhere.
  Local vLLM (DGX Spark option) requires HuggingFace model download, which is blocked in China.
- Chat model: e.g. `nvidia/nemotron-3-super-120b-a12b`
- Resource profile: **No profile** (option 6) for DGX Spark
- Web search: **No web search** (option 1)
- Messaging channel: skip (not needed for course exercises)

After onboarding:
```bash
nemoclaw my-assistant status
```

### 0.5 DGX — SSH port forwarding (access pages from Windows browser)

On your **Windows machine**, open an SSH tunnel so your Windows browser can reach the DGX
course pages and proxies. Keep this terminal open for the whole session.

**Scenario A — DGX only (WSL2 deployment not running):**
All standard ports are free on Windows:
```bash
# In Git Bash on Windows:
ssh -L 8081:localhost:8081 \
    -L 8010:localhost:8010 \
    -L 8011:localhost:8011 \
    jiyang_wang@<dgx-ip>
```
Open `http://localhost:8081/zh/nemoclaw/03a-kickstart.html` in Windows browser.
Configure base URLs as `http://127.0.0.1:8010/v1` for both Chat and Embedder.

**Scenario B — DGX and WSL2 running simultaneously:**
WSL2 holds ports 8081/8010/8011 on Windows. Use alternate local ports for DGX:
```bash
ssh -L 8082:localhost:8081 \
    -L 8013:localhost:8010 \
    -L 8014:localhost:8011 \
    jiyang_wang@<dgx-ip>
```
Open `http://localhost:8082/zh/nemoclaw/03a-kickstart.html` in Windows browser.
Configure base URLs as `http://127.0.0.1:8013/v1` for both Chat and Embedder.

> **Alternative — no tunnel needed**: If you have a monitor connected to the DGX, open a
> browser directly on the DGX at `http://localhost:8081/...` and configure base URLs as
> `http://127.0.0.1:8010/v1`. No port conflicts, no SSH tunnel required.

---

## 1 — Every-Session Startup (WSL2 Terminal)

Run these in order from a **WSL2 (Ubuntu-24.04) terminal**:

```bash
# ── 1a. Set your NVIDIA API key ───────────────────────────────────────────
export NVAPI_KEY="nvapi-..."   # paste your key here

# ── 1b. Start all background services (web server + proxies) ─────────────
# WSL2:
bash "/mnt/c/Users/<your-username>/OneDrive - NVIDIA Corporation/NVIDIA/DLI/Courses/NeMoClaw/repo/start_proxies.sh"
# DGX:
# bash ~/nemoclaw-zh/start_proxies.sh
# Starts: http.server :8081, cors_proxy :8010, openclaw_proxy :8011, policy_proxy :8012
# Re-running kills any stale instances first — safe to run again after a crash.

# ── 1c. Recover the OpenClaw container (if needed) ───────────────────────
nemoclaw my-assistant recover
# Expected: "Probe complete: OpenClaw gateway is running in 'my-assistant'."

# ── 1d. Replace SSH forward with gRPC-based forward ──────────────────────
openshell forward stop 18789
nohup openshell forward service my-assistant --target-port 18789 --local 18789 \
  > /tmp/openclaw-fwd.log 2>&1 &

# ── 1e. Fix Docker iptables rules for inference (CRITICAL) ───────────────
# These rules are lost on every WSL2/Docker restart and must be re-applied.
# Docker 29.x does not auto-create conntrack rules for custom bridge networks.
BRIDGE=$(docker network inspect openshell-docker \
  --format '{{index .Options "com.docker.network.bridge.name"}}')
[ -z "$BRIDGE" ] && BRIDGE="br-$(docker network inspect openshell-docker \
  --format '{{.Id}}' | cut -c1-12)"
echo "Bridge: $BRIDGE"
sudo iptables -I DOCKER-FORWARD 3 -i $BRIDGE -j ACCEPT
sudo iptables -I DOCKER-CT 1 -o $BRIDGE -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

# ── 1f. Verify everything is up ──────────────────────────────────────────
CONTAINER=$(docker ps --filter name=openshell-my-assistant --format "{{.Names}}" | head -1)
docker exec $CONTAINER curl --noproxy '*' -sk --max-time 10 \
  -o /dev/null -w "NVIDIA reachability: %{http_code} in %{time_total}s\n" \
  https://integrate.api.nvidia.com/v1/models
# Expected: NVIDIA reachability: 200 in ~0.5s

curl -s http://localhost:18789/healthz   # → {"ok":true,"status":"live"}
curl -s http://localhost:8011/healthz    # → {"ok":true,"status":"live"}
```

---

## 2 — Get the Gateway Bearer Token (needed once per session for the browser)

```bash
docker exec $CONTAINER \
  cat /sandbox/.openclaw/openclaw.json | python3 -c \
  "import json,sys; c=json.load(sys.stdin); print(c['gateway']['token'])"
```

Copy this token — you will paste it into the browser on page 03a.

---

## 3 — Browser Setup

1. Open **http://localhost:8081/zh/nemoclaw/03a-kickstart.html**
2. Enter your NVIDIA API key in the **API key** field
3. Enter the bearer token from Step 2 in the **Bearer token** field
4. Complete the health check on 03a to confirm the chain is working end to end
5. Proceed through the pages in order: 01a, 01b, 02a … 03a, 03b, 03c, 04a, 04b, 04c

---

## 4 — Page-Specific Notes

### All pages — after a rebuild or recover
If a page shows **DEGRADED** or the health check fails with `toolSearch: true`:
- Run the **🛠 Recover** cell on the current page before the health check
- This resets `toolSearch` to `false`

### Page 04a only — live policy
No manual steps needed. Both changes are baked into the HTML:

1. `window.__SBX_POLICY` is pre-loaded in the page `<head>` on every load
2. The "Read your live policy" RUN cell now falls back to `window.__SBX_POLICY` automatically
   when the operator terminal cannot reach the control plane (local deployment)

Just click RUN on that cell normally — it will log "(local deployment) using pre-loaded policy"
and continue to draw the policy map and populate all downstream cells.

---

## 5 — Quick Diagnostics

| Symptom | Fix |
|---|---|
| Health check times out (~92s) | Re-apply Step 1g iptables rules (lost on restart) |
| Health check shows DEGRADED / `toolSearch: true` | Run 🛠 Recover cell on the current page |
| `[fail] Docker container: openshell-cluster-nemoclaw` in doctor | False positive — ignore. Local deployment uses a different container naming scheme. |
| `openshell forward` not running | Re-run Step 1f |
| Port 18789 returns Squid HTML instead of gateway response | Forward service not running or namespace mismatch — re-run Step 1e then 1f |
| `helpers.policyGet()` fails on page 04a | Normal in local deployment — use the inject-sbx-policy snippet instead |
| Page behaves as if JS changes weren't applied | Browser cached the old ES module — use **Ctrl+Shift+R** (hard refresh) to bypass the module cache |

---

## 6 — What Each Background Process Does

| Process | Port | Role |
|---|---|---|
| `python3 -m http.server 8081` | 8081 | Serves the course HTML pages to the browser |
| `cors_proxy.py` | 8010 | CORS shim — proxies browser → NVIDIA NIM API (integrate.api.nvidia.com) |
| `openclaw_proxy.py` | 8011 | Proxies browser → OpenClaw gateway (localhost:18789) with TLS termination and CORS headers |
| `openshell forward service` | 18789 | gRPC tunnel — bridges WSL2:18789 → openshell-sandbox container (OpenClaw's isolated namespace) |
| `openshell-sandbox` container | (internal) | Runs the OpenClaw agent runtime, Squid egress proxy, and openshell_router for inference |
