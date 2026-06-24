# Staging Deployments and Production Lock

This is a temporary deployment design for review while the course is still changing quickly. Its objective is to let reviewers experience branch output on the real GitLab Pages host without allowing an ordinary branch failure to replace production content.

## Behavior

- `pages` is the only deploy job because this GitLab instance supports only classic GitLab Pages (`pages can only be used within a pages job`).
- On production refs (`$CI_DEFAULT_BRANCH` and `nemoclaw-only`), `pages` is manual and builds the normal production site at `$CI_PAGES_URL/nemoclaw/`.
- On ordinary branches, `pages` is also manual. This GitLab Pages runner serves non-default branch artifacts under `/$CI_COMMIT_REF_SLUG/`, so the branch artifact builds the foyer at its root and the course at `public/web/nemoclaw/`, served as `$CI_PAGES_URL/$CI_COMMIT_REF_SLUG/web/nemoclaw/`.
- The foyer reads `branches.json` and shows a branch dropdown when a build-time manifest is present. The manifest is advisory: a branch appears when it is detectable in git refs, and its preview URL works after that branch has been published by a manual Pages deploy.
- Translation branches run the test gate and are aggregated by the production build; they do not publish standalone previews by default.
- Preview deployments are review surfaces, not durable course URLs. With classic Pages they persist until another Pages deploy for that branch replaces the artifact.

## Temporary Compromise

The preview path intentionally mirrors the source path segment `web/nemoclaw` for transferability. That makes it easier to compare a staging artifact with repo-relative source paths and future rsync layouts. The compromise is that this relies on the current GitLab Pages runner behavior for non-default refs instead of the newer `pages.path_prefix` syntax, which this instance rejects. Keep this as a review path until either a separate staging project or true Pages parallel deployments are available.

## Guardrails

- Branch previews are manual, so a branch push cannot deploy to Pages by itself.
- Failed branch preview jobs do not publish a new Pages artifact.
- Branch preview artifacts are served under `/$CI_COMMIT_REF_SLUG/`, separate from the production root.
- Branch content is built only under `public/web/nemoclaw/` inside that branch artifact.
- `CI_COMMIT_REF_SLUG` is checked before use.
- `resource_group: pages-site` serializes Pages deploys so preview and production jobs cannot race.
- `scripts/build_pages.sh` refuses empty, current-directory, or root output paths before deleting and rebuilding the artifact directory. It rejects unsafe course and source-mirror prefixes, and moves the validator source mirror to `validated-source/web/nemoclaw` when the preview course itself occupies `web/nemoclaw`.
- The foyer branch dropdown reads only static `branches.json`; it does not call GitLab at runtime or require tokens.

## Limits

This is not a final governance model. A branch author who can change `.gitlab-ci.yml` can still propose changes to these guardrails, so production branches and production environments should stay protected in GitLab. Longer term, prefer a separate staging project or a GitLab Pages version that supports true parallel Pages deployments with `path_prefix`.
