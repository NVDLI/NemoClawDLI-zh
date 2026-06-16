# OpenClaw-in-OpenShell sandbox image.
#
# Image carries upstream artifacts only:
#   - openshell-sandbox supervisor binary
#   - npm-installed openclaw runtime
#   - shell tools the entrypoint depends on (jq, socat, curl, git, tree,
#     opa, gettext-base for envsubst)
#   - the entrypoint script itself
#
# Every course-specific asset (openclaw.json, SOUL.md, sandbox-policy.{yaml,rego},
# hooks/, skills-seed/, bin/skills.sh, env_discover.sh) is read at runtime
# from the host bind mount at $OPENCLAW_SRC (default
# /sandbox/dli/workspace/services/openclaw). The entrypoint symlinks immutable
# assets into the runtime paths and renders openclaw.json once with envsubst.
# Editing on the host now reflects in the running container without rebuilding.

FROM ghcr.io/nvidia/openshell/cluster:0.0.8 AS openshell-bin
FROM ghcr.io/nvidia/openshell-community/sandboxes/base:latest

USER root

COPY --from=openshell-bin /opt/openshell/bin/openshell-sandbox /usr/local/bin/openshell-sandbox
RUN chmod +x /usr/local/bin/openshell-sandbox

# `gettext-base` provides envsubst (used to render openclaw.json at startup).
RUN apt-get update && apt-get install -y --no-install-recommends \
        jq socat tree curl git gettext-base \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /usr/local/bin/opa \
        https://openpolicyagent.org/downloads/v1.4.2/opa_linux_amd64_static \
    && chmod +x /usr/local/bin/opa

ARG OPENCLAW_VERSION=2026.5.28
ARG OPENCLAW_HOME=/sandbox

ENV HOME=${OPENCLAW_HOME} \
    CONFIG_DIR=${OPENCLAW_HOME}/.openclaw \
    OPENCLAW_VERSION=${OPENCLAW_VERSION} \
    OPENCLAW_HOME=${OPENCLAW_HOME} \
    WORKSPACE=/sandbox/workspace \
    AGENT_DIR=${OPENCLAW_HOME}/.openclaw/agents/main/agent \
    LLM_REQUEST_TIMEOUT=300

RUN npm install -g openclaw@${OPENCLAW_VERSION}

RUN mkdir -p ${WORKSPACE} ${WORKSPACE}/memory ${WORKSPACE}/skills \
             ${WORKSPACE}/bin ${WORKSPACE}/hooks ${AGENT_DIR} /etc/openshell \
    && chmod -R a+rwX ${CONFIG_DIR} ${WORKSPACE}

COPY openclaw_shell.entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
RUN chown -R 998:998 /sandbox/.npm

WORKDIR /sandbox
EXPOSE 8995
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
