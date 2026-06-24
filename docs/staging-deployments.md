# Staging Deployments and Production Lock

This is a temporary deployment design for review while the course is still changing quickly. Its objective is to let reviewers experience branch output on the real GitLab Pages host without allowing an ordinary branch failure to replace production content.

## Behavior

- `pages` is the only deploy job because this GitLab instance supports only classic GitLab Pages (`pages can only be used within a pages job`).
- On production refs (`$CI_DEFAULT_BRANCH` and `nemoclaw-only`), `pages` is manual and builds the normal production site at `$CI_PAGES_URL/nemoclaw/`.
- On ordinary branches, `pages` is also manual. It builds a combined Pages artifact: production root from a protected ref, plus the branch preview at `public/$CI_COMMIT_REF_SLUG/web/nemoclaw/`, served as `$CI_PAGES_URL/$CI_COMMIT_REF_SLUG/web/nemoclaw/`.
- Translation branches run the test gate and are aggregated by the production build; they do not publish standalone previews by default.
- Preview deployments are review surfaces, not durable course URLs. With classic Pages they persist until the next Pages deploy replaces the single project artifact.

## Temporary Compromise

The preview path intentionally mirrors the source path segment `web/nemoclaw` for transferability. That makes it easier to compare a staging artifact with repo-relative source paths and future rsync layouts. The compromise is that GitLab Pages has one project-wide published artifact on this instance, so a branch preview deploy must publish a combined artifact instead of an isolated Pages deployment. Branch previews also persist until another Pages deploy replaces the artifact. This is acceptable as a temporary review path only because the production root is rebuilt from an approved production ref and the branch content is confined to `/<branch-slug>/web/nemoclaw/`.

## Guardrails

- Branch previews are manual, so a branch push cannot deploy to Pages by itself.
- Failed branch preview jobs do not publish a new Pages artifact.
- Branch preview jobs rebuild `public/index.html` and `public/nemoclaw/` from `PROD_PAGES_REF`, which is restricted to `$CI_DEFAULT_BRANCH` or `nemoclaw-only`.
- Branch content is built only under `public/$CI_COMMIT_REF_SLUG/web/nemoclaw/`.
- `CI_COMMIT_REF_SLUG` is checked before it becomes a path.
- `resource_group: pages-site` serializes Pages deploys so preview and production jobs cannot race.
- `scripts/build_pages.sh` refuses empty, current-directory, or root output paths before deleting and rebuilding the artifact directory. It rejects unsafe course and source-mirror prefixes, and moves the validator source mirror to `validated-source/web/nemoclaw` when the preview course itself occupies `web/nemoclaw`.

## Limits

This is not a final governance model. A branch author who can change `.gitlab-ci.yml` can still propose changes to these guardrails, so production branches and production environments should stay protected in GitLab. Longer term, prefer a separate staging project or a GitLab Pages version that supports true parallel Pages deployments with `path_prefix`.
