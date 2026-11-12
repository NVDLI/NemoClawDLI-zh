#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

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
COURSE_SITE_DIR="/tmp/nemoclaw-course-site-$(id -u)"

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

build_course_site() {
  case "$COURSE_SITE_DIR" in
    /tmp/nemoclaw-course-site-[0-9]*) ;;
    *) log "Refusing unsafe course site path: $COURSE_SITE_DIR"; return 1 ;;
  esac

  local locale_tmp
  locale_tmp=$(mktemp -d /tmp/nemoclaw-zh-overlay.XXXXXX)
  rm -rf -- "$COURSE_SITE_DIR"
  mkdir -p "$COURSE_SITE_DIR" "$COURSE_SITE_DIR/zh"
  cp -R "$REPO_DIR/web/." "$COURSE_SITE_DIR/"

  python3 "$REPO_DIR/scripts/build/assemble_locale_overlay.py" \
    --locale-root "$REPO_DIR/i18n/zh" --out "$locale_tmp"
  cp -R "$locale_tmp/web/." "$COURSE_SITE_DIR/zh/"
  rm -rf -- "$locale_tmp"

  # Rebase the translated foyer from the lab-static source layout to this local site.
  python3 - "$COURSE_SITE_DIR/zh/index.html" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
raw = path.read_text(encoding="utf-8")
raw = raw.replace("/lab/static/nemoclaw/", "nemoclaw/")
raw = raw.replace("/lab/static/", "../")
path.write_text(raw, encoding="utf-8")
PY

  python3 "$REPO_DIR/scripts/build/build_language_manifest.py" \
    --out "$COURSE_SITE_DIR/languages.json" --site-root "$COURSE_SITE_DIR" --project-default
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

log "Building the English and default Chinese course routes..."
build_course_site

log "Starting course web server  (port 8081) → /tmp/nemoclaw-web.log"
cd "$REPO_DIR"
nohup python3 -m http.server 8081 --directory "$COURSE_SITE_DIR" > /tmp/nemoclaw-web.log 2>&1 &

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
log "Course home: http://localhost:8081/ (Simplified Chinese by default)"
log "All services started. Proceed with steps 1f → 1i in LOCAL_STARTUP_GUIDE.md"
