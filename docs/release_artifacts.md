# Release artifacts and tags

This contract separates preview deployment from versioned publication. The repository remains
an internal release candidate until `RELEASE_STATUS.json` records external approval.

## Ref and artifact lanes

| Lane | Ref | Artifact | Retention | Authority |
|---|---|---|---|---|
| Branch preview | topic branch commit | Combined classic-Pages preview | 3 days | Manual review environment |
| Internal production | protected `main` or approved production ref | Current Pages deployment | Replaced by next approved deploy | Protected production environment |
| Public release | protected annotated `vMAJOR.MINOR.PATCH` tag | Versioned archive, manifest, SBOM, checksums | Published release lifetime | Protected tag plus release environment |

A Pages deployment proves a commit is previewable. It does not create a version. A public release
always starts from a protected tag and never from a branch name or an unreviewed workflow input.

## Tag contract

- Use SemVer tags such as `v1.2.3` or an explicit prerelease such as `v1.3.0-rc.1`.
- Create an annotated tag on a commit contained in protected `main`. Lightweight tags are refused.
- Protect `v*` creation, update, and deletion. Name eligible release operators directly.
- Never move, delete, or reuse a published version tag. Fix release defects under a new version.
- Prefer signed annotated tags after the external repository has a documented signing identity and
  trust-root rotation process. Do not claim signature verification before that trust path exists.

Example after approval and final validation:

```bash
git tag -a v1.0.0 -m "NemoClaw DLI course v1.0.0" <reviewed-main-sha>
git push origin v1.0.0
```

The release workflow verifies the tag name, annotated tag object, target commit, and containment
in `origin/main`. Host rules remain responsible for tag creation authority.

## Published asset set

Each public draft receives:

- `nemoclaw-vX.Y.Z.tar.gz`: deterministic built Pages tree under a versioned top-level directory
- `release-manifest.json`: schema, tag object, commit, source epoch, archive digest, file count,
  and attached-asset digests
- `nemoclaw-vX.Y.Z.python-env.cdx.json`: CycloneDX SBOM for the resolved release environment
- `SHA256SUMS`: digest list for every published asset

Validation reports and the full `pip-audit` result remain workflow evidence. They are retained with
the transfer artifact for 30 days but are not public release assets. This keeps operator evidence
available without publishing noisy scanner detail as a supported product interface.
The workflow installs scanner tools in a separate environment, so scanner dependencies do not
pollute the runtime SBOM. Scanner versions are pinned in the workflow so the same environment is
serialized consistently until an explicit dependency update changes the tooling.

## Reproducibility rules

`scripts/build/package_release.py` normalizes file order, owner, group, mode, archive time, gzip
time, and top-level path. The commit time supplies `SOURCE_DATE_EPOCH` to generated branch metadata
and `source_date_epoch` to the packager. The release build disables live material refresh, so public
URLs changing during a run cannot alter the archive.

Run the deterministic self-test locally and in CI:

```bash
python3 scripts/build/package_release.py --self-test
```

The generated manifest binds the archive to both the tag object and peeled commit. `SHA256SUMS`
supports offline verification. When the external GitHub repository is created, enable immutable
releases. GitHub then locks the published tag and assets and emits a release attestation.

## Promotion and recovery

1. Validate a topic commit and publish an ephemeral preview.
2. Merge through protected `main` after required CI and human acceptance.
3. Update `RELEASE_STATUS.json` only after OSRB approval.
4. Create the protected annotated version tag on the accepted `main` commit.
5. Run the release workflow. It rebuilds, scans, packages, and prepares a draft.
6. Review release notes, workflow evidence, manifest, SBOM, and checksums.
7. Publish once immutable-release settings are confirmed.

Draft assets may be replaced after a failed review. Published assets and tags are immutable. A bad
published artifact is superseded by a new patch version and a clear release note.

Primary references: [Git annotated tags](https://git-scm.com/docs/git-tag),
[GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases),
and [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).
