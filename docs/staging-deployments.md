# Staging Deployments and Production Lock

This deployment design lets reviewers experience branch output on the real GitLab Pages host without allowing an ordinary branch failure to replace production content or leave large downloadable artifacts around indefinitely.

## Behavior

- `pages` is the only deploy job because this GitLab instance still supports only classic GitLab Pages (`pages can only be used within a pages job`).
- On production refs (`$CI_DEFAULT_BRANCH` and `nemoclaw-only`), `pages` is manual and builds the normal production site at `$CI_PAGES_URL/nemoclaw/`.
- On ordinary branches, `pages` is also manual. It builds a combined Pages artifact: production root from a protected ref, plus the branch foyer at `public/$CI_COMMIT_REF_SLUG/index.html` and the branch course at `public/$CI_COMMIT_REF_SLUG/web/nemoclaw/`, served as `$CI_PAGES_URL/$CI_COMMIT_REF_SLUG/` and `$CI_PAGES_URL/$CI_COMMIT_REF_SLUG/web/nemoclaw/`.
- The root and branch foyers read `branches.json`, which contains only preview paths present in the published artifact. The UI also sends a same-origin `HEAD` request before showing each option, so a stale or missing target stays hidden.
- The branch foyer also reads `languages.json` and shows a language dropdown when the artifact contains more than one built language. English follows the preview course prefix (`web/nemoclaw/` in branch previews); translations use their built course path such as `pt/nemoclaw/`.
- Translation branches run the test gate and are aggregated by the production build; they do not publish standalone previews by default.
- Preview deployments are review surfaces, not durable course URLs. Their downloadable job artifacts expire after three days. Review environments also request auto-stop after three days.

## Storage Contract

The preview path intentionally mirrors the source path segment `web/nemoclaw` for transferability. That makes it easier to compare a staging artifact with repo-relative source paths and future rsync layouts. The compromise is that classic GitLab Pages has one project-wide published artifact on this instance, so a branch preview deploy must publish a combined artifact instead of an isolated Pages deployment. This is acceptable as a temporary review path only because the production root is rebuilt from an approved production ref and the branch content is confined to `/<branch-slug>/web/nemoclaw/`.

Classic Pages keeps one project artifact active. Publishing branch B replaces branch A's combined artifact, so only the latest staged branch is previewable and listed. A git branch existing, or having an unplayed manual Pages job, does not make it appear in the selector.

The `pages` job must keep both cleanup controls:

- `artifacts.expire_in: 3 days`, so the downloadable `public/` artifacts do not accumulate as 10-20 MiB entries.
- `environment.auto_stop_in: 3 days` for branch previews, so the review environment list does not grow without bound. Production sets this to `never`.

`scripts/validation/ci_storage_audit.py` enforces this shape in CI.

## Guardrails

- Branch previews are manual, so a branch push cannot deploy to Pages by itself.
- The `test` job is blocking. Required-tier release failures prevent the manual Pages job from publishing.
- A preview job compares `CI_COMMIT_SHA` with the live remote branch head and refuses stale pipelines after a newer push.
- Failed branch preview jobs do not publish a new Pages artifact.
- Branch preview jobs rebuild `public/index.html` and `public/nemoclaw/` from `PROD_PAGES_REF`, which is restricted to `$CI_DEFAULT_BRANCH` or `nemoclaw-only`.
- Branch preview jobs regenerate root `public/branches.json` from the real checkout after the protected-root archive build, so the production foyer branch browser does not disappear when a branch preview deploys.
- Branch content is built only under `public/$CI_COMMIT_REF_SLUG/`; its course lives at `public/$CI_COMMIT_REF_SLUG/web/nemoclaw/`, and its foyer link is checked in CI so it cannot point at the production-only `nemoclaw/` path.
- `CI_COMMIT_REF_SLUG` is checked before it becomes a path.
- `branch_preview_manifest_audit.py` rejects manifest entries without matching artifact paths, unlisted preview paths, old schemas, and missing readiness flags. It validates both the root and branch foyer manifests before deployment.
- The blocking `pages_smoke` job retries after deployment, then verifies the live root foyer code, both manifests, and every advertised course URL. A successful artifact upload without reachable Pages output is not considered done.
- The branch foyer dropdown reads static `branches.json`, then probes the same-origin target with `HEAD`; it never calls GitLab or requires tokens. The language dropdown remains static.
- `resource_group: pages-site` serializes Pages deploys so preview and production jobs cannot race.
- `scripts/build/build_pages.sh` refuses empty, current-directory, or root output paths before deleting and rebuilding the artifact directory. It rejects unsafe course and source-mirror prefixes, and moves the validator source mirror to `validated-source/web/nemoclaw` when the preview course itself occupies `web/nemoclaw`.

## Limits

This is not a parallel-preview system. A branch author who can change `.gitlab-ci.yml` can still propose changes to these guardrails, so production branches and production environments should stay protected in GitLab. Longer term, prefer a separate staging project or a GitLab Pages version that supports true parallel Pages deployments with `path_prefix`.
