# SBOM generation and attachment runbook

This runbook generates the SBOM evidence used for source and open-source review without adding
generated SBOM bodies to the repository. Run every command from the repository root at the exact
reviewed commit. Retain the command, tool version, commit SHA, component count, file size, and
SHA-256 alongside each output.

The static course release does not distribute the local-authoring container images. Its normal
attachment set is therefore the browser runtime, resolved workspace Python environment, and exact
source tree. Scan a container image only when that exact digest is itself proposed for distribution.

## Output directory

```bash
COMMIT=$(git rev-parse HEAD)
OUT=/tmp/nemoclaw-sbom-$COMMIT
mkdir -p "$OUT"
```

Do not commit `$OUT`. Attach its reviewed files to the issue or merge request, then retain the same
files in the authorized release evidence record.

## Evidence catalog and retention

[`scripts/compliance/docs/sbom_evidence.json`](sbom_evidence.json) is the compact index used by the license view. It records
three different states instead of presenting every missing aggregate license as the same problem:

- `available`: the linked SBOM is in the repository and the catalog pins its SHA-256 and component count;
- `ci-generated`: the SBOM, evidence manifest, and license appendix are produced for an exact commit;
- `conditional`: the software is not distributed by the static course, so its digest-bound scan is
  required only if that artifact is later proposed for distribution.

GitLab SCA artifacts expire after 30 days. They support merge review but are not permanent release
evidence. A versioned public release copies its Python SBOM, evidence manifest, and license appendix
into release assets. It also composes a release catalog whose relative links resolve to the
versioned Python and browser SBOM filenames. Any distributed image must receive the same treatment.
Verify the committed catalog and its linked browser SBOM with:

```bash
python3 scripts/compliance/sbom_evidence.py --check
python3 scripts/compliance/sbom_evidence.py --self-test
```

The offline check rejects missing repository declarations, malformed URLs, stale link-check dates,
and incomplete license hints. Scheduled CI and protected release preparation also read the official
external URLs with bounded retries:

```bash
python3 scripts/compliance/sbom_evidence.py --check-external-links
```

The source checkout carries `ci_sbom_evidence.json` with an explicit `unavailable` state. The deep
SCA job exports its numeric job ID as a dotenv report, and Pages receives that job's artifacts
through an explicit `needs` edge. Pages then reads one byte from each expected path through the
job-ID artifact API with `CI_JOB_TOKEN`. It emits clickable direct-job links only after the
manifest names the exact preview commit and every expected path succeeds. A missing producing job,
commit mismatch, or missing path stays visibly unavailable; a branch or job-name guess never turns
into an evidence link. The verified files are also copied beside the staged evidence catalog. That
same-origin CycloneDX copy is SHA-256 checked in the browser before the license view renders its
resolved Python component rows; the GitLab links remain the provenance and retention authority.

Evidence emission calls `scripts/compliance/render_sbom_license_inventory.py` to create the
component-level Markdown appendix from the same digest-bound CycloneDX input.

## Browser runtime CycloneDX

The browser generator enumerates the packages actually included by the esbuild metafiles, copies
their license texts, and writes the deterministic CycloneDX document.

```bash
cd scripts/browser-vendor
npm ci
cd ../..
scripts/runtime/run_node.sh scripts/build/vendor_browser_dependencies.mjs
python3 scripts/validation/course_dependency_integrity.py --self-test
python3 scripts/validation/course_dependency_integrity.py
cp web/nemoclaw/vendor/browser-sbom.cdx.json "$OUT/browser-runtime.cdx.json"
```

The exact npm lock remains the authority for the wider build graph. An optional
`npm view <name>@<version> license dist.integrity repository --json` query may corroborate a row,
but it does not override the reviewed lock and installed license text.

## Resolved Python environment CycloneDX

Keep runtime packages separate from scanner packages. This is the same command sequence used by
the required `security_deep_sca` CI job.

```bash
python3 -m venv /tmp/nemoclaw-release-runtime
python3 -m venv /tmp/nemoclaw-release-scanner
/tmp/nemoclaw-release-runtime/bin/python -m pip install -r workspace/requirements.lock
/tmp/nemoclaw-release-scanner/bin/python -m pip install -r scripts/security/requirements-sca.lock
RUNTIME_SITE=$(/tmp/nemoclaw-release-runtime/bin/python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
PATH="/tmp/nemoclaw-release-scanner/bin:$PATH" /tmp/nemoclaw-release-scanner/bin/python \
  scripts/security/run_full_sca.py --execute --require-tools --python-local --cyclonedx-env \
  --python-executable /tmp/nemoclaw-release-runtime/bin/python --python-path "$RUNTIME_SITE" \
  --out-dir "$OUT/python-scan"
/tmp/nemoclaw-release-scanner/bin/python scripts/security/audit_sbom_policy.py \
  --sbom "$OUT/python-scan/python-env.cdx.json" \
  --report "$OUT/python-scan/sbom-policy.json"
cp "$OUT/python-scan/python-env.cdx.json" "$OUT/python-env.cdx.json"
cp "$OUT/python-scan/sbom-policy.json" "$OUT/sbom-policy.json"
python3 scripts/compliance/sbom_evidence.py \
  --sbom "$OUT/python-env.cdx.json" \
  --artifact-name "python-validation-$COMMIT" \
  --record-id python-validation-environment \
  --description "Resolved Python validation environment; not distributed to learners" \
  --distribution not-distributed \
  --category validation \
  --source-commit "$COMMIT" \
  --ci-job manual-review \
  --appendix-out "$OUT/python-license-appendix.md" \
  --manifest-out "$OUT/python-sbom-evidence.json"
```

When reusing the CI result, first verify the job SHA equals `$COMMIT`, download the complete
artifact with authenticated byte ranges, verify every `Content-Range`, and retain the artifact ZIP
SHA-256. Do not reuse an SBOM from an earlier green commit.

## Exact source-tree CycloneDX and SPDX

The command used for the review attachment runs the official pinned Syft image against a read-only
checkout. The explicit source name and full commit make the output identity reviewable.

```bash
container run --rm \
  --mount type=bind,source="$PWD",target=/src,readonly \
  --mount type=bind,source="$OUT",target=/out \
  anchore/syft:v1.44.0@sha256:86fde6445b483d902fe011dd9f68c4987dd94e07da1e9edc004e3c2422650de6 scan dir:/src \
  --source-name NemoClawDLIOS \
  --source-version "$COMMIT" \
  -q \
  -o cyclonedx-json=/out/source-tree.cdx.json \
  -o spdx-json=/out/source-tree.spdx.json
```

Record the scanner identity:

```bash
container run --rm anchore/syft:v1.44.0@sha256:86fde6445b483d902fe011dd9f68c4987dd94e07da1e9edc004e3c2422650de6 version
```

## Digest-bound container image SBOM

This is conditional. It applies only when the image itself is a release artifact. Resolve the tag
to the deployment platform's immutable registry digest before scanning; do not attach a tag-only
scan as final evidence.

```bash
IMAGE=<registry>/<repository>@sha256:<64-hex-digest>
PLATFORM=linux/amd64
container run --rm \
  --mount type=bind,source="$OUT",target=/out \
  anchore/syft:v1.44.0@sha256:86fde6445b483d902fe011dd9f68c4987dd94e07da1e9edc004e3c2422650de6 scan "registry:$IMAGE" \
  --platform "$PLATFORM" \
  -q \
  -o cyclonedx-json=/out/image.cdx.json \
  -o spdx-json=/out/image.spdx.json
python3 scripts/compliance/sbom_evidence.py \
  --sbom "$OUT/image.cdx.json" \
  --artifact-name "$IMAGE" \
  --artifact-id "$IMAGE" \
  --record-id scanned-container-image \
  --description "Digest-bound component inventory for an image proposed for distribution" \
  --distribution conditional-release \
  --category local-authoring \
  --source-commit "$COMMIT" \
  --ci-job manual-review \
  --appendix-out "$OUT/image-license-appendix.md" \
  --manifest-out "$OUT/image-sbom-evidence.json" \
  --allow-unresolved
```

A mixed image still has no honest single SPDX license. The generated component appendix resolves
individual packages; it does not replace the image-level `NOASSERTION` with a guessed aggregate.

## License metadata precedence

1. Retain scanner-provided SPDX identifiers and expressions.
2. Use `THIRD_PARTY_LICENSES.md` only as an exact normalized-name and exact-version fallback when
   the scanner provides a name or omits license metadata.
3. Leave an unreviewed named license unresolved.
4. Leave missing metadata as `NOASSERTION`.
5. Keep descriptive external-content terms descriptive when they are not an OSS SPDX license.

For Python metadata review, use the exact-version endpoint
`https://pypi.org/pypi/<normalized-name>/<version>/json`. If it supplies only a legacy label or no
expression, inspect the license file from that exact wheel/source distribution and its source tag.

## Course-material source and terms retrieval

```bash
python3 scripts/materials/pull_materials.py --list
python3 scripts/materials/pull_materials.py --verify-committed
python3 scripts/materials/pull_materials.py --check
python3 scripts/compliance/third_party_inventory_audit.py
```

The materials vendorer uses typed extractors for NVIDIA article HTML, arXiv API paper metadata, and
the NVIDIA glossary. It enforces HTTPS, same-host redirects, bounded responses, and bounded retries,
then records the source URL, relationship, size, and SHA-256. Those extractors acquire content, not
permission. A reviewer determines the cited source's terms; when no explicit reuse grant exists,
the inventory continues to say so. Figure and material provenance come from their respective
`SKILL.html` beacons, and the inventory audit rejects a missing external-source row.

### Paper licenses and NVIDIA document authors

The document-source acquisition is separate from content vendoring. It scans canonical course and
material files for every arXiv ID, reads each official arXiv abstract page's “Rights to this article”
link, and records the title, full author list, selected license, license URL, reuse meaning, and every
canonical citation location. It reads published NVIDIA JSON-LD bylines when present. If an official
NVIDIA page publishes no byline, the record says `not-listed-on-source` instead of guessing an owner.

Generate a review candidate without overwriting the committed evidence:

```bash
python3 scripts/compliance/source_document_audit.py \
  --refresh \
  --output /tmp/document_sources.json
diff -u scripts/compliance/docs/document_sources.json /tmp/document_sources.json
```

After a human has checked source URLs, licenses, bylines, and repository-item mappings, replace the
committed JSON deliberately and project its static Markdown tables:

```bash
cp /tmp/document_sources.json scripts/compliance/docs/document_sources.json
python3 scripts/compliance/source_document_audit.py --update-markdown
python3 scripts/compliance/source_document_audit.py
python3 scripts/compliance/export_legal_scope_csv.py \
  --category all \
  --output /tmp/nemoclaw-document-and-legal-scope.csv
```

The normal audit and CI never use the network. They reject a missing or stale arXiv record, a license
label that disagrees with its evidence URL, citation-location drift, an NVIDIA material without an
author/source record, and Markdown that no longer matches the reviewed JSON. The arXiv non-exclusive
distribution license is recorded as a limited arXiv distribution grant, not an open reuse license.

## Attachment manifest

The normal attachment bundle contains:

- `browser-runtime.cdx.json`
- `python-env.cdx.json`
- `sbom-policy.json`
- `python-license-appendix.md`
- `python-sbom-evidence.json`
- `source-tree.cdx.json`
- `source-tree.spdx.json`
- a short manifest naming the commit, commands, tools, counts, byte sizes, and SHA-256 values

Generate checksums only after the files have passed their format and policy checks:

```bash
shasum -a 256 \
  "$OUT/browser-runtime.cdx.json" \
  "$OUT/python-env.cdx.json" \
  "$OUT/sbom-policy.json" \
  "$OUT/python-license-appendix.md" \
  "$OUT/python-sbom-evidence.json" \
  "$OUT/source-tree.cdx.json" \
  "$OUT/source-tree.spdx.json"
```

Attachment is evidence transport, not approval. The accountable reviewer still decides license
disposition and whether any additional released artifact requires its own SBOM.
