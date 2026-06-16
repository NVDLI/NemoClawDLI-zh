# CUDA-enabled base image. Lets any notebook that wants torch.cuda run on the
# DGX Spark when GPU passthrough is enabled (docker-compose.gpu.yml).
# CUDA 12.8 is the minimum that ships compiled kernel images for Blackwell
# (sm_100, GB10 on DGX Spark). Earlier wheels (cu121/cu124) report
# torch.cuda.is_available()==True on GB10 but fail at runtime with
# "no kernel image available for execution on the device".
FROM nvcr.io/nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04

# Install Python 3.11 + system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip \
    build-essential bash curl unzip wget git libgl1 tree jq \
    nodejs npm poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Make python3 / pip resolve to 3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    ln -sf /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /tmp

#Run pip dependencies
# Build context is the repo's task1/ dir (docker-compose.override.yml:
# context: .), so workspace files are addressed as workspace/<path>.
COPY workspace/requirements.txt .
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

# Install PyTorch with CUDA 12.8 support. cu128 is required for Blackwell
# GPU architecture (sm_100) on the DGX Spark GB10; earlier wheels compiled
# without sm_100 kernels cause "no kernel image" errors at runtime.
# Install the PyTorch family together so pip resolves a mutually-compatible
# version set; all three must come from the same wheel index in one command
# to avoid version drift (e.g. torchaudio 2.11 shipping before torch 2.11).
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu128 \
    --upgrade

# Re-run requirements.txt AFTER PyTorch so that any package (e.g. OpenTelemetry)
# that pip deprioritised earlier in favour of PyTorch's transitive deps gets the
# pinned version we specify in requirements.txt.  This is a no-op for packages
# already at the right version.
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

RUN pip install --no-cache-dir --root-user-action ignore \
    uv jupyterlab==4.5.5 jupyterlab-widgets jupyter-archive ipywidgets \
    jupyter-resource-usage jupytext jupyter-server-proxy \
    "jupyter-server>=2.0.0" jupyter-collaboration \
    jupyterlab-language-pack-zh-CN \
    jupyterlab-language-pack-ja-JP \
    jupyterlab-language-pack-zh-TW

COPY cpu/services/jupyter/ /opt/jupyter_cfg/
RUN rm -rf /root/.jupyter/* \
    && cp /opt/jupyter_cfg/bashrc /root/.bashrc \
    && mkdir -p /root/.jupyter \
    && cp -r /opt/jupyter_cfg/.jupyter/* /root/.jupyter/ \
    && mkdir -p /usr/local/share/jupyter/lab/settings \
    && cp -r /opt/jupyter_cfg/.jupyter /root/.jupyter \
    && cp /opt/jupyter_cfg/overrides.json /usr/local/share/jupyter/lab/settings/overrides.json

WORKDIR /sandbox

# Seed location for the shared 'dli' named volume.  In production the entrypoint
# syncs /sandbox/dli_seed/workspace/ into /sandbox/dli/workspace/ on first boot.
# That populates the named volume that openclaw also mounts, so live edits in
# JupyterLab are visible to openclaw immediately.  In dev,
# docker-compose.override.yml redirects the same named volume to a bind mount of
# the repo root, so the seed step is skipped.
COPY workspace/ /sandbox/dli_seed/workspace/

# Surface-first course layout: the NemoClaw release ships the browser course
# under web/ and the shared service code under cpu/services/, with companion
# mats/ and the shared scripts/ tooling at the task1 root. These are seeded
# alongside workspace/ so the production image (named-volume seed) carries the
# course; dev (bind mount) is unaffected.
COPY web/     /sandbox/dli_seed/web/
COPY cpu/     /sandbox/dli_seed/cpu/
COPY mats/    /sandbox/dli_seed/mats/
COPY scripts/ /sandbox/dli_seed/scripts/

# Expose port 8888 for JupyterLab
EXPOSE 8888
EXPOSE 9012

ENV SHELL=/bin/bash

# Start JupyterLab when the container runs
ADD workspace/entrypoint.sh /usr/local/bin
RUN chmod +x /usr/local/bin/*.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
