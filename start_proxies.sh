#!/usr/bin/env bash
# start_proxies.sh — Launch all NeMoClaw background services in WSL2.
#
# Usage:
#   bash start_proxies.sh
#
# Starts:
#   • python3 -m http.server 8081   (course web server)
#   • cors_proxy.py                 (NVIDIA NIM API CORS bridge, port 8010)
#   • openclaw_proxy.py             (OpenClaw gateway proxy, port 8011)
#   • policy_proxy.py               (live policy fetch bridge, port 8012)
#
# Each service is backgrounded with nohup; logs go to /tmp/nemoclaw-*.log.
# Running the script again kills any existing instances before restarting.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── helpers ──────────────────────────────────────────────────────────────────

log()  { echo "[start_proxies] $*"; }
kill_port() {
  local port="$1"
  local pid
  pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    kill "$pid" 2>/dev/null || true
    log "  killed existing process on port $port (PID $pid)"
  fi
}

# ── kill any existing instances ───────────────────────────────────────────────

log "Stopping any existing services..."
kill_port 8081
kill_port 8010
kill_port 8011
kill_port 8012
# also kill by script name for safety
pkill -f "http.server 8081"       2>/dev/null || true
pkill -f "cors_proxy.py"          2>/dev/null || true
pkill -f "openclaw_proxy.py"      2>/dev/null || true
pkill -f "policy_proxy.py"        2>/dev/null || true
sleep 0.5

# ── start services ────────────────────────────────────────────────────────────

log "Starting course web server  (port 8081) → /tmp/nemoclaw-web.log"
cd "$REPO_DIR"
nohup python3 -m http.server 8081 > /tmp/nemoclaw-web.log 2>&1 &

log "Starting CORS proxy         (port 8010) → /tmp/nemoclaw-cors.log"
nohup python3 "$REPO_DIR/cors_proxy.py" > /tmp/nemoclaw-cors.log 2>&1 &

log "Starting OpenClaw proxy     (port 8011) → /tmp/nemoclaw-openclaw.log"
nohup python3 "$REPO_DIR/openclaw_proxy.py" > /tmp/nemoclaw-openclaw.log 2>&1 &

log "Starting policy proxy       (port 8012) → /tmp/nemoclaw-policy.log"
nohup python3 "$REPO_DIR/policy_proxy.py" > /tmp/nemoclaw-policy.log 2>&1 &

# ── verify ───────────────────────────────────────────────────────────────────

sleep 1
log ""
log "Service status:"
for port in 8081 8010 8011 8012; do
  if lsof -ti tcp:"$port" >/dev/null 2>&1; then
    log "  ✓ port $port is listening"
  else
    log "  ✗ port $port NOT listening — check /tmp/nemoclaw-*.log"
  fi
done
log ""
log "All services started. Proceed with steps 1f → 1i in LOCAL_STARTUP_GUIDE.md"
