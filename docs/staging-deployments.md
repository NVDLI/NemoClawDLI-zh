# Staging Deployments and Production Lock

This is a temporary deployment design for review while the course is still changing quickly. Its objective is to let reviewers experience branch output on the real GitLab Pages host without allowing an ordinary branch failure to replace production content.

## Behavior

- `pages` is the only deploy job because this GitLab instance supports only classic GitLab Pages (`pages can only be used within a pages job`).
- On production refs (`$CI_DEFAULT_BRANCH` and `nemoclaw-only`), `pages` is manual and builds the normal production site at `$CI_PAGES_URL/nemoclaw/`.
- On ordinary branches, `pages` is also manual. It builds a combined Pages artifact: production root from a protected ref, plus the branch foyer at `public/$CI_COMMIT_REF_SLUG/index.html` and the branch course at `public/$CI_COMMIT_REF_SLUG/web/nemoclaw/`, served as `$CI_PAGES_URL/$CI_COMMIT_REF_SLUG/` and `$CI_PAGES_URL/$CI_COMMIT_REF_SLUG/web/nemoclaw/`.
- The branch foyer reads `branches.json` and shows a branch dropdown when a build-time manifest is present. The manifest is advisory: a branch appears when it is detectable in git refs, and its preview URL works after that branch has been manually published to Pages.
- The branch foyer also reads `languages.json` and shows a language dropdown when the artifact contains more than one built language. English follows the preview course prefix (`web/nemoclaw/` in branch previews); translations use their built course path such as `pt/nemoclaw/`.
- Translation branches run the test gate and are aggregated by the production build; they do not publish standalone previews by default.
- Preview deployments are review surfaces, not durable course URLs. With classic Pages they persist until the next Pages deploy replaces the single project artifact.

## Temporary Compromise

The preview path intentionally mirrors the source path segment `web/nemoclaw` for transferability. That makes it easier to compare a staging artifact with repo-relative source paths and future rsync layouts. The compromise is that GitLab Pages has one project-wide published artifact on this instance, so a branch preview deploy must publish a combined artifact instead of an isolated Pages deployment. Branch previews also persist until another Pages deploy replaces the artifact. This is acceptable as a temporary review path only because the production root is rebuilt from an approved production ref and the branch content is confined to `/<branch-slug>/web/nemoclaw/`.

## Guardrails

- Branch previews are manual, so a branch push cannot deploy to Pages by itself.
- Failed branch preview jobs do not publish a new Pages artifact.
- Branch preview jobs rebuild `public/index.html` and `public/nemoclaw/` from `PROD_PAGES_REF`, which is restricted to `$CI_DEFAULT_BRANCH` or `nemoclaw-only`.
- Branch preview jobs regenerate root `public/branches.json` from the real checkout after the protected-root archive build, so the production foyer branch browser does not disappear when a branch preview deploys.
- Branch content is built only under `public/$CI_COMMIT_REF_SLUG/`; its course lives at `public/$CI_COMMIT_REF_SLUG/web/nemoclaw/`, and its foyer link is checked in CI so it cannot point at the production-only `nemoclaw/` path.
- `CI_COMMIT_REF_SLUG` is checked before it becomes a path.
- The branch foyer dropdown reads only static `branches.json`, and the language dropdown reads only static `languages.json`; neither calls GitLab at runtime or requires tokens.
- `resource_group: pages-site` serializes Pages deploys so preview and production jobs cannot race.
- `scripts/build/build_pages.sh` refuses empty, current-directory, or root output paths before deleting and rebuilding the artifact directory. It rejects unsafe course and source-mirror prefixes, and moves the validator source mirror to `validated-source/web/nemoclaw` when the preview course itself occupies `web/nemoclaw`.

## Limits

This is not a final governance model. A branch author who can change `.gitlab-ci.yml` can still propose changes to these guardrails, so production branches and production environments should stay protected in GitLab. Longer term, prefer a separate staging project or a GitLab Pages version that supports true parallel Pages deployments with `path_prefix`.
