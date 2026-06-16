#!/bin/bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# Shared workspace seed (production-only path).
#
# /sandbox/dli is a NAMED VOLUME shared with the openclaw sidecar (so
# notebook writes are visible to the sandboxed agent immediately).  In
# dev, docker-compose.override.yml redirects the same volume to a bind
# mount of the repo root, and the seed step below is a no-op because
# the host directory already has content.
#
# In production, the named volume starts empty on first container boot.
# We populate it from the image's baked-in seed at /sandbox/dli_seed/.
# Subsequent boots see a non-empty volume and skip the copy.
# ──────────────────────────────────────────────────────────────────────────
if [ -d /sandbox/dli_seed ] && [ ! -d /sandbox/dli/workspace ]; then
    echo "[lab-entrypoint] Seeding /sandbox/dli/ from image content..."
    mkdir -p /sandbox/dli
    cp -an /sandbox/dli_seed/. /sandbox/dli/
    echo "[lab-entrypoint] Seed complete: $(find /sandbox/dli/workspace -maxdepth 2 | wc -l) entries."
fi

# PyTorch 2.10 + this image's Triton occasionally crashes the inductor
# compile worker subprocess when torch.compile() runs the default
# multi-threaded compile path. Forcing single-threaded compile keeps
# everything in-process and avoids the "compilation subprocess exited
# unexpectedly" InductorError.
# Exported so every kernel JupyterLab launches inherits it.
export TORCHINDUCTOR_COMPILE_THREADS=1

cd /sandbox/dli

# The entrance lands directly on the foyer HTML page.
jupyter lab \
        --ip 0.0.0.0 \
        --allow-root \
        --no-browser \
        --ServerApp.root_dir="/sandbox/dli" \
        --ServerApp.base_url="/lab" \
        --LabApp.default_url='/lab/static/index.html' \
        --ServerApp.extra_static_paths='["/sandbox/dli", "/sandbox/dli/web"]' \
        --IdentityProvider.token="${JUPYTER_TOKEN:-}" \
        --ServerApp.password=""
        # root_dir is /sandbox/dli (the bind mount = task1) so the file
        # browser opens on the surface folders directly: web/ cpu/
        # (course content), plus the shared mats/ repos/ and the workspace/
        # infra. The surface-first layout (task1/{web,cpu}/<course>) keeps the
        # browser course under web/ and the shared services under cpu/, so the
        # tree root has to be /sandbox/dli to show them.
        #
        # default_url funnels an AUTHENTICATED student straight to the foyer
        # (the course picker) on entrance. On its own this also makes a
        # *tokenless* /lab serve index.html (HTTP 200, no auth), which the LMS
        # readiness poll on :80/lab rejects as an exposed notebook (code 99):
        # it requires a tokenless /lab to reach /lab/login. We cannot move the
        # poll off :80/lab (it is the platform default), so nginx gates the
        # bare /lab: a tokenless request → /lab/login (poll passes); an
        # authenticated one (?token= or session cookie) is proxied here, where
        # default_url lands it on the foyer. See `location = /lab` in
        # nginx.conf. Validated end-to-end against a token-protected
        # jupyter-server 2.18: poll→login, ?token→foyer, cookie→foyer,
        # bad-token→login.
        #
        # extra_static_paths is searched IN ORDER, first match wins (these host
        # paths all live under /sandbox/dli, the volume that mirrors task1):
        #   [0] /sandbox/dli   the repo root, so /lab/static/<anything> renders the
        #                      real tree: /lab/static/SKILL.html serves the root hub
        #                      (task1/SKILL.html, the bundle index a visitor expects
        #                      at the bare /static/SKILL.html URL), plus
        #                      /lab/static/{cpu,web,mats,scripts,docs}/... .
        #                      /sandbox/dli is listed first so the root SKILL.html
        #                      wins over the web/ and per-course SKILL.html hubs. The
        #                      only top-level name that collides is SKILL.html (root
        #                      wins, intended); index.html and courses.html do not
        #                      exist at the root, so they fall through to [1].
        #   [1] web            the browser-course surface: /lab/static/index.html is
        #                      web/index.html (the release foyer), /lab/static/courses.html
        #                      is the catalog, and the course is reached under its own
        #                      subpath /lab/static/nemoclaw/, where its relative
        #                      _shared.js / assets resolve correctly.
        # Do NOT add a course directory as its own static root. A root like
        # web/nemoclaw backfills that course's top-level names: it would serve
        # web/nemoclaw/index.html at /lab/static/index.html whenever web/index.html
        # is momentarily absent, and tornado then caches that resolution for the life
        # of the process, silently shadowing the foyer with the course. The course
        # stays one level down, under [1]; nothing links the flat /lab/static/<page>.html form.
        #  SECURITY: [0] also exposes repo-root secrets (BEARER_TOKEN, CF_ACCESS,
        #  *.env) in DEV (the volume mirrors task1), so nginx 404s them under
        #  /lab/static/ (see `location ~* .../lab/static/`). In PROD they are never in
        #  the volume (the image seed copies only web/cpu/mats/scripts/workspace,
        #  not root secrets).
