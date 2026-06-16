#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# env_discover.sh. Lightweight environment survey for SOUL.md injection.
#
# Generates a markdown block describing the runtime environment and injects
# it into SOUL.md by replacing {{SYSTEM_SPEC}}. Falls back to appending
# (idempotently, using sentinel comments) if the placeholder is missing.
#
# Makes no LLM calls. Survives a partial toolchain. Runs on Azure, AWS, and GCP.
#
# Usage:  env_discover.sh [SOUL_MD_PATH...]
#   Patches each path given. Defaults: $WORKSPACE/SOUL.md, $AGENT_DIR/SOUL.md
#
# Env vars (all optional):
#   WORKSPACE, AGENT_DIR, CONFIG_DIR, NVIDIA_BASE_URL, PORT
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

# ── Helpers ───────────────────────────────────────────────────────────────

probe() { eval "$1" 2>/dev/null || echo "${2:-n/a}"; }
http_status() { curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$1" 2>/dev/null || echo "unreachable"; }
is_writable() {
    local f="$1/.env_discover_probe"
    touch "$f" 2>/dev/null && rm -f "$f" && echo "rw" || echo "ro"
}

# ── OS / Identity ────────────────────────────────────────────────────────

KERN=$(probe "uname -srm")
HOST=$(probe "hostname")
WHOAMI=$(probe "id -un")
UID_INFO=$(probe "id")

# ── Cloud (no metadata endpoint needed) ──────────────────────────────────

CLOUD="unknown"
if [ -f /sys/class/dmi/id/board_vendor ]; then
    case "$(cat /sys/class/dmi/id/board_vendor 2>/dev/null)" in
        *Microsoft*) CLOUD="azure" ;; *Amazon*) CLOUD="aws" ;; *Google*) CLOUD="gcp" ;;
    esac
fi
[ "$CLOUD" = "unknown" ] && case "$KERN" in *azure*) CLOUD="azure";; *aws*) CLOUD="aws";; esac

# ── Network ──────────────────────────────────────────────────────────────

if command -v ip &>/dev/null; then
    NET_IF=$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $2, $4}' | head -5)
    NET_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -1)
else
    NET_IF="ip cmd missing"
    NET_GW=$(probe "route -n 2>/dev/null | awk '/^0\.0\.0\.0/{print \$2}' | head -1" "unknown")
fi
NET_GW="${NET_GW:-unknown}"
NET_DNS=$(probe "awk '/^nameserver/{printf \"%s \", \$2}' /etc/resolv.conf")
NET_PROXY="${HTTP_PROXY:-${http_proxy:-none}}"
NET_NO_PROXY="${NO_PROXY:-${no_proxy:-none}}"

# ── NFS / Mounts ─────────────────────────────────────────────────────────

NFS_MOUNTS=$(mount 2>/dev/null | grep -E 'nfs|cifs' | awk '{
    rw="rw"; if (index($0,"(ro,") || index($0," ro,")) rw="ro"
    printf "    - `%s` → %s (%s)\n", $3, $1, rw
}')
[ -z "$NFS_MOUNTS" ] && NFS_MOUNTS="    (none detected)"

# ── Writable locations ───────────────────────────────────────────────────

WRITE_TESTS=""
for d in "${WORKSPACE:-/sandbox/.openclaw/workspace}" \
         "/tmp" \
         "${CONFIG_DIR:-/sandbox/.openclaw}"; do
    [ -d "$d" ] && WRITE_TESTS="${WRITE_TESTS}
    - \`$d\` → $(is_writable "$d")"
done

# ── Course root discovery ────────────────────────────────────────────────

COURSE_ROOT=""
for cand in "/sandbox/notebooks" \
            "/sandbox/notebooks" \
            "/sandbox/notebooks"; do
    [ -d "$cand/notebooks" ] 2>/dev/null && { COURSE_ROOT="$cand"; break; }
done
if [ -z "$COURSE_ROOT" ]; then
    COURSE_ROOT=$(find /sandbox /dli /mnt -maxdepth 4 -type d -name notebooks 2>/dev/null \
        | head -1 | sed 's|/notebooks$||' || true)
fi
COURSE_ROOT="${COURSE_ROOT:-not found}"

if [ "$COURSE_ROOT" != "not found" ] && [ -d "$COURSE_ROOT/notebooks" ]; then
    NOTEBOOKS=$(find "$COURSE_ROOT/notebooks" -maxdepth 1 -name "*.ipynb" -printf "%f\n" 2>/dev/null \
        | sort | tr '\n' ', ' | sed 's/,$//')
else
    NOTEBOOKS="none found";
fi

# ── Tools ────────────────────────────────────────────────────────────────

TOOLS=""
declare -A TOOL_VER=(
    [node]="--version" [npm]="--version" [python3]="--version"
    [pip3]="--version" [git]="--version" [jq]="--version"
    [curl]="--version" [gh]="--version" [opa]="version"
    [openclaw]="--version" [docker]="--version"
    [kubectl]="version --client --short" [helm]="version --short"
    [socat]="-V" [uv]="--version"
)
for cmd in node npm python3 pip3 git jq curl gh opa openclaw docker kubectl helm socat uv; do
    if command -v "$cmd" &>/dev/null; then
        ver=$(eval "$cmd ${TOOL_VER[$cmd]}" 2>&1 | head -3 | grep -oP '\d+\.\d+[\.\d]*' | head -1)
        TOOLS="${TOOLS}
    - \`$cmd\` ${ver:-(installed)}"
    fi
done
for cmd in docker kubectl helm wget jupyter nvidia-smi; do
    command -v "$cmd" &>/dev/null || TOOLS="${TOOLS}
    - \`$cmd\` ✗"
done

# npm globals
NPM_G=""
command -v npm &>/dev/null && NPM_G=$(find /usr/lib/node_modules /usr/local/lib/node_modules \
    -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//')

# Python
PY_PKG=$(pip3 list --format=columns 2>/dev/null | tail -n +3 | awk '{printf "%s,",$1}' | sed 's/,$//' || echo "bare")
VENV=""
[ -d "/app/.venv/bin" ] && VENV=$(ls /app/.venv/bin/ 2>/dev/null \
    | grep -vE '^(activate|python|pip|pydoc|deactivate|idle|2to3)' \
    | grep -vE '\.(bat|csh|fish|nu|ps1|py)$' | sort -u | tr '\n' ',' | sed 's/,$//')

# ── Services ─────────────────────────────────────────────────────────────

GW="${NET_GW}"
SVC_TESTS=""
declare -A SVC_URL=(
    [llm_client:9000]="${GW}:9000/health"
    [lab:8888]="${GW}:8888/"
    [nginx:80]="${GW}:80/"
)
for svc in "llm_client:9000" "lab:8888" "nginx:80"; do
    SVC_TESTS="${SVC_TESTS}
    - \`$svc\` → HTTP $(http_status "http://${SVC_URL[$svc]}")"
done

LLM_URL="${NVIDIA_BASE_URL:-http://${GW}:9000/v1}"
MODEL_N=$(curl -s --max-time 5 "${LLM_URL}/models" 2>/dev/null | jq '.data | length' 2>/dev/null || echo "n/a")

LISTEN=$(probe "ss -tlnp 2>/dev/null | awk '/LISTEN/{print \$4}' | tr '\n' ',' | sed 's/,$//'" "n/a")

# ── Dev Source ───────────────────────────────────────────────────────────

DEV_SRC_INFO="not found"
for _cand in "${OPENCLAW_HOME:-/home/ocuser}/OpenClaw" "/usr/lib/node_modules/openclaw"; do
    if [ -d "$_cand/ui/src" ]; then
        _ver=$(cd "$_cand" && git describe --tags 2>/dev/null || echo "unknown")
        DEV_SRC_INFO="\`$_cand\` ($_ver, writable)"
        break
    fi
done

PATCH_INFO=""
if [ -f /tmp/openclaw-patch-status.json ]; then
    PATCH_INFO=$(node -e 'const s=require("/tmp/openclaw-patch-status.json");console.log(s.applied.length+" applied: "+s.applied.join(", "))' 2>/dev/null || echo "")
fi

# ── Misc ─────────────────────────────────────────────────────────────────

DISK=$(probe "df -h / 2>/dev/null | tail -1 | awk '{print \$2\" total, \"\$4\" free (\"\$5\" used)\"}'" "n/a")

SANDBOX_TYPE="none detected"
[ -n "${OPENCLAW_SANDBOX:-}" ] && SANDBOX_TYPE="openshell"
[ -f "/.dockerenv" ]           && SANDBOX_TYPE="${SANDBOX_TYPE} + docker"

SECC=$(probe "awk '/^Seccomp:/{print \$2}' /proc/self/status" "n/a")
case "$SECC" in 0) SL="disabled";; 1) SL="strict";; 2) SL="filter";; *) SL="$SECC";; esac

INET=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "https://example.com" 2>/dev/null || true)
[ -z "$INET" ] || [ "$INET" = "000" ] && INET="blocked"

# ── Build spec ───────────────────────────────────────────────────────────

SPEC=$(cat <<SPECEOF
### Discovered System Spec
<!-- env_discover:begin -->
<!-- $(date -u +"%Y-%m-%dT%H:%M:%SZ") auto-generated, do not hand-edit -->

- **Host:** \`$HOST\` | **Kernel:** \`$KERN\` | **Cloud:** $CLOUD
- **User:** \`$WHOAMI\` ($UID_INFO)
- **Sandbox:** $SANDBOX_TYPE | seccomp=$SL
- **Internet:** $INET

**Network:**
    - Interfaces: $NET_IF
    - Gateway: \`$GW\` | DNS: \`$NET_DNS\`
    - Proxy: \`$NET_PROXY\` | NO_PROXY: \`$NET_NO_PROXY\`

**Filesystem:**
    - Course root: \`$COURSE_ROOT\` ($([ "$COURSE_ROOT" != "not found" ] && is_writable "$COURSE_ROOT" || echo "n/a"))
    - Writability:$WRITE_TESTS
    - NFS:
$NFS_MOUNTS
    - Disk: $DISK

**Notebooks:** $NOTEBOOKS

**Tools:**$TOOLS
    - npm globals: ${NPM_G:-n/a}
    - pip: ${PY_PKG}$([ -n "$VENV" ] && printf "\n    - /app/.venv: $VENV")

**Services (via $GW):**$SVC_TESTS
    - LLM models: $MODEL_N
    - Listening: $LISTEN

**Dev Source:** $DEV_SRC_INFO$([ -n "$PATCH_INFO" ] && printf "\n    - Patches: $PATCH_INFO")
<!-- env_discover:end -->
SPECEOF
)

# ── Inject ───────────────────────────────────────────────────────────────

inject_spec() {
    local target="$1"
    [ -f "$target" ] || { echo "[env_discover] SKIP $target (not found)"; return 0; }

    if grep -qF '{{SYSTEM_SPEC}}' "$target"; then
        awk -v spec="$SPEC" '{
            if (index($0, "{{SYSTEM_SPEC}}")) print spec
            else print
        }' "$target" > "${target}.tmp" && mv "${target}.tmp" "$target"
        echo "[env_discover] ✓ Replaced {{SYSTEM_SPEC}} in $target"
    else
        # Idempotent: strip previous block by sentinels, then append
        sed -i '/<!-- env_discover:begin -->/,/<!-- env_discover:end -->/d' "$target" 2>/dev/null || true
        sed -i '/^### Discovered System Spec$/d' "$target" 2>/dev/null || true
        # Trim trailing blank lines
        sed -i -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$target" 2>/dev/null || true
        printf '\n%s\n' "$SPEC" >> "$target"
        echo "[env_discover] ✓ Appended to $target"
    fi
}

if [ $# -gt 0 ]; then
    for f in "$@"; do inject_spec "$f"; done
else
    inject_spec "${WORKSPACE:-/sandbox/.openclaw/workspace}/SOUL.md"
    inject_spec "${AGENT_DIR:-/sandbox/.openclaw/agents/main/agent}/SOUL.md"
fi

echo "[env_discover] Done."
