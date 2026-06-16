#!/usr/bin/env bash
# OpenClaw-in-OpenShell entrypoint.
#
# Reads every course-specific asset from the host bind mount at $OPENCLAW_SRC
# (default /sandbox/dli/cpu/services/openclaw). Immutable assets are
# symlinked into the runtime paths; openclaw.json is rendered once with
# envsubst. No in-place sed on host files.

set -euo pipefail

echo "OpenClaw initializing inside OpenShell sandbox..."

if [ -z "${_MOUNT_NS_FIXED:-}" ]; then
    export _MOUNT_NS_FIXED=1
    exec unshare --mount --propagation shared -- "$0" "$@"
fi
mkdir -p /run/netns

: "${OPENCLAW_SRC:=/sandbox/dli/cpu/services/openclaw}"

echo "[entrypoint] OPENCLAW_SRC=${OPENCLAW_SRC}"
echo "[entrypoint] CONFIG_DIR=${CONFIG_DIR}"
echo "[entrypoint] WORKSPACE=${WORKSPACE}"
echo "[entrypoint] NOTEBOOK_DIR=${NOTEBOOK_DIR:-/sandbox/notebooks}"

if [ ! -d "${OPENCLAW_SRC}" ]; then
    echo "[entrypoint] FATAL: OPENCLAW_SRC=${OPENCLAW_SRC} not found." >&2
    echo "[entrypoint] Check that ./ is bind-mounted to /sandbox/dli." >&2
    exit 1
fi

mkdir -p "${WORKSPACE}/memory" "${WORKSPACE}/skills" "${WORKSPACE}/bin" \
         "${WORKSPACE}/hooks" "${AGENT_DIR}" \
         "${CONFIG_DIR}/extensions" "${CONFIG_DIR}/qqbot/data" \
         /etc/openshell

# SOUL.md is rendered, not symlinked: the env-discover hook below APPENDS
# to it, and the host bind is :ro. Symlinking through :ro would either
# fail or (depending on the hook's write strategy) silently clobber the
# link with a regular file and diverge from the host template. The cost
# of rendering: host edits to SOUL.md require `docker compose restart
# openclaw` to refresh, the same trade-off as openclaw.json.
rm -f "${WORKSPACE}/SOUL.md" "${AGENT_DIR}/SOUL.md"
cp "${OPENCLAW_SRC}/SOUL.md" "${WORKSPACE}/SOUL.md"
cp "${OPENCLAW_SRC}/SOUL.md" "${AGENT_DIR}/SOUL.md"

# Immutable scripts. Symlink them so host edits are live without a restart.
ln -sfn "${OPENCLAW_SRC}/bin/skills.sh"      "${WORKSPACE}/bin/skills.sh"
ln -sfn "${OPENCLAW_SRC}/env_discover.sh"    "${WORKSPACE}/hooks/env_discover.sh"
for hook in "${OPENCLAW_SRC}/hooks/"*.sh; do
    [ -f "$hook" ] || continue
    ln -sfn "$hook" "${WORKSPACE}/hooks/$(basename "$hook")"
done

# Sandbox policy. Symlinked. Edit the policy on the host and run
# `docker compose restart openclaw` to apply.
ln -sfn "${OPENCLAW_SRC}/sandbox-policy.yaml" /etc/openshell/sandbox-policy.yaml
ln -sfn "${OPENCLAW_SRC}/sandbox-policy.rego" /etc/openshell/sandbox-policy.rego

# Skills seed. Idempotent and no-clobber so student edits win.
if [ -d "${OPENCLAW_SRC}/skills-seed" ] && [ -x "${WORKSPACE}/bin/skills.sh" ]; then
    bash "${WORKSPACE}/bin/skills.sh" seed "${OPENCLAW_SRC}/skills-seed" --no-clobber \
        || echo "[entrypoint] skill seed warnings ignored"
fi

# Render openclaw.json once from the host template. The runtime file lives in
# the named volume so the bedrock-merge step below can mutate it without
# touching the host template.
OPENCLAW_TEMPLATE="${OPENCLAW_SRC}/openclaw.json"
OPENCLAW_JSON="${CONFIG_DIR}/openclaw.json"

OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-dli-openclaw-token}" \
NVIDIA_BASE_URL="${NVIDIA_BASE_URL:-http://llm_client:9000/v1}" \
envsubst '${OPENCLAW_GATEWAY_TOKEN} ${NVIDIA_BASE_URL}' \
    < "${OPENCLAW_TEMPLATE}" > "${OPENCLAW_JSON}"

# Apply PORT (literal integer in the JSON, not a ${VAR} placeholder).
tmp_json="$(mktemp)"
jq --argjson port "${PORT:-8995}" '.gateway.port = $port' \
    "${OPENCLAW_JSON}" > "${tmp_json}" && mv "${tmp_json}" "${OPENCLAW_JSON}"

# Conditional bedrock-proxy provider. Depends on llm_client capability.
# Mutates the rendered runtime file only; host template stays as-is.
llm_client_health_url="${NVIDIA_BASE_URL:-http://llm_client:9000/v1}"
llm_client_health_url="${llm_client_health_url%/v1}/health"
has_bedrock=0
for attempt in $(seq 1 30); do
    if curl -fsS --max-time 2 "${llm_client_health_url}" \
        | jq -e '.bedrock_fallback == true' >/dev/null 2>&1; then
        has_bedrock=1; break
    fi
    sleep 1
done

if [ "${has_bedrock}" = "1" ]; then
    echo "[entrypoint] llm_client Bedrock fallback available; enabling Sonnet/Opus defaults"
    tmp_json="$(mktemp)"
    jq --arg baseUrl "${NVIDIA_BASE_URL}" '
      .models.providers["bedrock-proxy"] = {
        "baseUrl": $baseUrl, "apiKey": "not-needed-local", "api": "openai-completions",
        "models": [
          { "id": "bedrock-proxy/global.anthropic.claude-sonnet-4-6",
            "name": "Claude Sonnet via Bedrock llm_client", "reasoning": true,
            "cost": {"input": 0, "output": 0},
            "contextWindow": 200000, "maxTokens": 32000 },
          { "id": "bedrock-proxy/global.anthropic.claude-opus-4-6-v1",
            "name": "Claude Opus via Bedrock llm_client", "reasoning": true,
            "cost": {"input": 0, "output": 0},
            "contextWindow": 200000, "maxTokens": 32000 }
        ]
      }
      | .agents.defaults.models["bedrock-proxy/global.anthropic.claude-sonnet-4-6"] = {}
      | .agents.defaults.models["bedrock-proxy/global.anthropic.claude-opus-4-6-v1"] = {}
      | .agents.defaults.model.primary    = "bedrock-proxy/global.anthropic.claude-sonnet-4-6"
      | .agents.defaults.model.fallbacks  = [
          "bedrock-proxy/global.anthropic.claude-opus-4-6-v1",
          "deepseek-ai/deepseek-v4-pro",
          "moonshotai/kimi-k2.6"
        ]
      | .agents.defaults.compaction.model = "bedrock-proxy/global.anthropic.claude-sonnet-4-6"
    ' "${OPENCLAW_JSON}" > "${tmp_json}" && mv "${tmp_json}" "${OPENCLAW_JSON}"
else
    echo "[entrypoint] llm_client Bedrock fallback unavailable; keeping DeepSeek/Kimi defaults"
fi

jq '{gateway: {port: .gateway.port, basePath: .gateway.controlUi.basePath},
     workspace: env.WORKSPACE, src: env.OPENCLAW_SRC}' \
   "${OPENCLAW_JSON}" || true

if [ -x "${WORKSPACE}/hooks/env-discover.sh" ]; then
    bash "${WORKSPACE}/hooks/env-discover.sh" "${WORKSPACE}/SOUL.md" "${AGENT_DIR}/SOUL.md" \
        || echo "[entrypoint] env discovery warnings ignored"
fi

# Named volumes mount as root:root, but the openclaw gateway runs as the
# sandbox user (UID 998) after openshell-sandbox drops privileges. Without
# this chown, the agent's exec tool fails with EPERM the first time it
# tries to chmod inside its own data dir (chmod is restricted to owner
# or root). The 777 mode is fine for read/write but not for chmod.
chown -R 998:998 "${CONFIG_DIR}" "${WORKSPACE}" 2>/dev/null || true
chmod -R a+rwX "${CONFIG_DIR}" "${WORKSPACE}" 2>/dev/null || true

echo "[entrypoint] starting inbound port forwarder"
socat TCP-LISTEN:${PORT:-8995},fork,reuseaddr TCP:10.200.0.2:${PORT:-8995} &

echo "[entrypoint] launching OpenShell sandbox on ${PORT:-8995}"
exec openshell-sandbox \
    --policy-rules /etc/openshell/sandbox-policy.rego \
    --policy-data  /etc/openshell/sandbox-policy.yaml \
    -- openclaw gateway --bind lan --port "${PORT:-8995}"
