# Maintainer roles

Ownership is role-based so governance does not depend on stale personal contact details.

| Role | Responsibility | Required authority |
|---|---|---|
| Repository maintainer | Triage, review routing, issue state, and community moderation | Issue and review management |
| Surface owner | Technical and learner-impact review for an assigned path | Review approval, no release bypass |
| Release manager | Protected tags, release evidence, publication, and rollback | Protected environment and tag authority |
| Security responder | Private vulnerability intake and coordinated remediation | Private security route |

One person may hold several roles, but nobody approves their own final push or protected release.
The public host records current assignments through teams, rulesets, environment reviewers, and
`CODEOWNERS` after stable public team handles exist. Until then, the canonical host's protected
settings are authoritative; do not place provisional names or private contacts in this file.

Changes to role authority require a reviewed governance change plus matching host-setting evidence.
Agents may prepare evidence and patches. They cannot satisfy independent human review, moderation,
merge, tag, or release ownership.
