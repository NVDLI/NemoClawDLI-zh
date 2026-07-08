# Third-party software and material inventory

This checked-in inventory is the static, human-readable list for the proposed Apache-2.0 source release. It records exact package versions and SPDX license expressions where package metadata or upstream license text supports one. `NOASSERTION` means the source tree alone cannot determine a single license for a mixed container or operating-system component; it is not an approval.

The root [Apache-2.0 license](LICENSE) covers NVIDIA-authored project code. Per-package browser license texts are distributed under [`web/nemoclaw/vendor/licenses/`](web/nemoclaw/vendor/licenses/). Python wheels and container layers retain their upstream license metadata and files. A built-image SBOM remains required for exact operating-system packages and image-layer licenses.

External pages that are only linked or summarized are not software dependencies. They are listed separately at the end so redistribution and inspiration are not conflated.

## Reproducing license-evidence acquisition

The inventory is derived from exact repository inputs and immutable scan artifacts.
Package names are never discovered by searching the web, and a search-engine result is never accepted as license
evidence. Run these steps at the reviewed commit, record every tool version, and retain the raw lock,
metadata response, license text, or SBOM beside the generated result.

| Surface | How components are enumerated | How license evidence is acquired | Retained evidence |
|---|---|---|---|
| Browser npm graph | Every non-root `packages` entry in `scripts/browser-vendor/package-lock.json`; the shipped subset comes from esbuild metafiles during vendoring | SPDX identifier from the exact lock entry; for a shipped package, copy its installed `LICENSE`/`LICENCE` file, or use a reviewed `license-overrides/` text only when the package omits that file | Lock file and SHA-256, generated browser manifest/SBOM, copied license text, asset hashes |
| Python environments | Every exact `==` pin in the four lock/declaration files enforced by `third_party_inventory_audit.py`, plus the three CUDA wheel pins | Exact-version PyPI JSON at `https://pypi.org/pypi/<normalized-name>/<version>/json`; prefer `license_expression`/core metadata, then inspect the exact distribution's license file or tagged upstream source when metadata is named, legacy, or absent | URL recorded in each row, exact lock, scanner SBOM, static SPDX disposition |
| Direct images and OS packages | `FROM` and package-install declarations in the tracked Dockerfiles | Resolve the candidate image to its registry digest, scan that digest to CycloneDX JSON with the approved image scanner, then enumerate component licenses; never infer all layer licenses from the base-image name | Image name plus digest, scanner/tool version, raw CycloneDX JSON and SHA-256, rendered component appendix |
| Direct non-Python runtimes | Exact version in the Dockerfile or deployment input | Exact npm version metadata and package license for OpenClaw; exact tagged upstream release and root license for OPA | Versioned upstream URL and tracked declaration |
| Course materials and figures | External `source_url` rows in the asset/material provenance beacons | Fetch content only through the typed materials vendorer; determine reuse terms from the cited source or its explicit license, and preserve `no reuse license stated` when no grant is present | Committed snapshot, provenance URL/relationship/terms, byte count and SHA-256 |

### Browser packages and license texts

```bash
cd scripts/browser-vendor
npm ci
cd ../..
scripts/runtime/run_node.sh scripts/build/vendor_browser_dependencies.mjs
python3 scripts/validation/course_dependency_integrity.py --self-test
python3 scripts/validation/course_dependency_integrity.py
python3 scripts/compliance/third_party_inventory_audit.py
```

`npm ci` verifies and installs the committed lock. The vendoring script uses esbuild metafiles to
identify code actually bundled for learners. It reads each exact version and SPDX identifier from
the lock, copies the installed package's license text, builds `browser-dependencies.json` and
`browser-sbom.cdx.json`, and records SHA-256 values. The static table below intentionally includes
the complete build graph; rows marked `browser-runtime` are the shipped subset. An exact
`npm view <name>@<version> license dist.integrity repository --json` query may corroborate registry
metadata during review, but it does not override the committed lock or reviewed license text.

### Python package metadata and installed-environment scan

The deterministic inventory parser accepts exact pins from:

- `workspace/requirements.lock`
- `scripts/materials/requirements.lock`
- `scripts/security/requirements-sca.lock`
- `cpu/services/sandbox_admin/requirements.txt`
- the exact CUDA wheel declarations for `torch`, `torchvision`, and `torchaudio`

For each normalized name and version, retrieve the version-specific PyPI JSON URL shown in its
table row. Accept an SPDX expression supplied by current core metadata. If PyPI or the CycloneDX
component supplies only a human-readable name, legacy classifier, or nothing, inspect the license
file from that exact wheel/source distribution and the source tag before recording a static SPDX
mapping. Do not map a generic label such as `BSD` without that inspection.

Reproduce the installed-environment evidence with separate runtime and scanner environments:

```bash
python3 -m venv /tmp/nemoclaw-release-runtime
python3 -m venv /tmp/nemoclaw-release-scanner
/tmp/nemoclaw-release-runtime/bin/python -m pip install -r workspace/requirements.lock
/tmp/nemoclaw-release-scanner/bin/python -m pip install -r scripts/security/requirements-sca.lock
RUNTIME_SITE=$(/tmp/nemoclaw-release-runtime/bin/python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
PATH="/tmp/nemoclaw-release-scanner/bin:$PATH" /tmp/nemoclaw-release-scanner/bin/python \
  scripts/security/run_full_sca.py --execute --require-tools --python-local --cyclonedx-env \
  --python-executable /tmp/nemoclaw-release-runtime/bin/python --python-path "$RUNTIME_SITE" \
  --out-dir /tmp/nemoclaw-release-sca
/tmp/nemoclaw-release-scanner/bin/python scripts/security/audit_sbom_policy.py \
  --sbom /tmp/nemoclaw-release-sca/python-env.cdx.json
```

Then bind the result to the immutable artifact identity and render the static appendix:

```bash
python3 scripts/compliance/render_sbom_license_inventory.py \
  --sbom /tmp/nemoclaw-release-sca/python-env.cdx.json \
  --artifact-id <artifact-name>@sha256:<64-hex-digest> \
  --out <artifact-license-inventory.md>
```

### Images, operating-system packages, and `NOASSERTION`

First build the candidate, resolve every mutable tag to its registry `sha256` digest, and save the
digest in the release record. With the approved scanner installed, the canonical acquisition shape
is:

```bash
syft <image-name>@sha256:<64-hex-digest> \
  -o cyclonedx-json=<image-name>.cdx.json
python3 scripts/compliance/render_sbom_license_inventory.py \
  --sbom <image-name>.cdx.json \
  --artifact-id <image-name>@sha256:<64-hex-digest> \
  --out <image-name>-licenses.md
```

Use the scanner and version approved for the release environment; `syft` above documents the
required CycloneDX command shape, not an approval of an unreviewed tool installation. Retain the
scanner version, database timestamp when applicable, raw SBOM, SBOM SHA-256, image digest, and
rendered Markdown. Image-level `NOASSERTION` remains truthful because a mixed image has no single
license; the appendix supplies the actionable component-level results.

### Materials and figures

```bash
python3 scripts/materials/pull_materials.py --list
python3 scripts/materials/pull_materials.py --verify-committed
python3 scripts/materials/pull_materials.py --check
python3 scripts/compliance/third_party_inventory_audit.py
```

The materials vendorer uses typed extractors: NVIDIA blog article HTML, the arXiv API for paper
metadata, and the NVIDIA glossary extractor. It enforces HTTPS, same-host redirects, bounded
responses and retries, then records source URL, relationship, character/byte count, and SHA-256.
Those extractors acquire content, not permission. A reviewer must determine the cited source's
terms; absent an explicit reuse grant, the inventory must continue to say so. Figure provenance is
read from `web/nemoclaw/assets/SKILL.html`, and material provenance from
`web/nemoclaw/mats/SKILL.html`; the audit fails if an external source row is omitted here.

### Reconciliation and precedence

1. Scanner-provided SPDX identifiers or expressions win.
2. A static mapping may fill scanner named/missing metadata only for the exact normalized package
   name and exact version, and is labeled `exact package/version static fallback`.
3. A named license without a reviewed exact-version mapping remains unresolved.
4. Missing metadata remains `NOASSERTION`; it is never changed by guessing from a project name.
5. External-source terms remain descriptive when they are not an OSS SPDX license.

The deterministic CI gate reads committed evidence without network access. Live PyPI, registry,
and source retrieval is a separate acquisition/review activity so upstream drift cannot silently
change a release. This process produces review evidence; it does not replace open-source or legal
approval.

## Browser runtime and browser-build packages

Source of truth: [`scripts/browser-vendor/package-lock.json`](scripts/browser-vendor/package-lock.json). Rows marked `browser-runtime` also appear in the shipped browser manifest and have checked-in license text. Platform-specific esbuild packages are build-only optional packages.

| Scope | Package | Version | SPDX license | Evidence |
|---|---|---|---|---|
| browser-runtime | @cfworker/json-schema | 4.1.1 | MIT | [`licenses/@cfworker__json-schema--4.1.1.txt`](web/nemoclaw/vendor/licenses/@cfworker__json-schema--4.1.1.txt) |
| browser-build-only | @esbuild/aix-ppc64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/android-arm | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/android-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/android-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/darwin-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/darwin-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/freebsd-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/freebsd-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-arm | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-ia32 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-loong64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-mips64el | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-ppc64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-riscv64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-s390x | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/linux-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/netbsd-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/netbsd-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/openbsd-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/openbsd-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/openharmony-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/sunos-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/win32-arm64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/win32-ia32 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-build-only | @esbuild/win32-x64 | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-runtime | @langchain/core | 1.1.48 | MIT | [`licenses/@langchain__core--1.1.48.txt`](web/nemoclaw/vendor/licenses/@langchain__core--1.1.48.txt) |
| browser-runtime | @langchain/langgraph | 1.4.7 | MIT | [`licenses/@langchain__langgraph--1.4.7.txt`](web/nemoclaw/vendor/licenses/@langchain__langgraph--1.4.7.txt) |
| browser-runtime | @langchain/langgraph-checkpoint | 1.1.3 | MIT | [`licenses/@langchain__langgraph-checkpoint--1.1.3.txt`](web/nemoclaw/vendor/licenses/@langchain__langgraph-checkpoint--1.1.3.txt) |
| browser-bundle-input | @langchain/langgraph-sdk | 1.9.25 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-bundle-input | @langchain/langgraph-sdk/node_modules/eventemitter3 | 5.0.4 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-bundle-input | @langchain/langgraph-sdk/node_modules/p-queue | 9.3.0 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-bundle-input | @langchain/langgraph-sdk/node_modules/p-timeout | 7.0.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-runtime | @langchain/openai | 1.4.7 | MIT | [`licenses/@langchain__openai--1.4.7.txt`](web/nemoclaw/vendor/licenses/@langchain__openai--1.4.7.txt) |
| browser-bundle-input | @langchain/protocol | 0.0.18 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-bundle-input | @standard-schema/spec | 1.1.0 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-bundle-input | @types/json-schema | 7.0.15 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-bundle-input | argparse | 2.0.1 | Python-2.0 | [lock](scripts/browser-vendor/package-lock.json) |
| browser-runtime | base64-js | 1.5.1 | MIT | [`licenses/base64-js--1.5.1.txt`](web/nemoclaw/vendor/licenses/base64-js--1.5.1.txt) |
| browser-runtime | codemirror | 5.65.21 | MIT | [`licenses/codemirror--5.65.21.txt`](web/nemoclaw/vendor/licenses/codemirror--5.65.21.txt) |
| browser-build-only | esbuild | 0.28.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-runtime | eventemitter3 | 4.0.7 | MIT | [`licenses/eventemitter3--4.0.7.txt`](web/nemoclaw/vendor/licenses/eventemitter3--4.0.7.txt) |
| browser-runtime | highlight.js | 11.10.0 | BSD-3-Clause | [`licenses/highlight.js--11.10.0.txt`](web/nemoclaw/vendor/licenses/highlight.js--11.10.0.txt) |
| browser-bundle-input | is-network-error | 1.3.2 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-runtime | js-tiktoken | 1.0.21 | MIT | [`licenses/js-tiktoken--1.0.21.txt`](web/nemoclaw/vendor/licenses/js-tiktoken--1.0.21.txt) |
| browser-runtime | js-yaml | 5.2.1 | MIT | [`licenses/js-yaml--5.2.1.txt`](web/nemoclaw/vendor/licenses/js-yaml--5.2.1.txt) |
| browser-runtime | langsmith | 0.7.14 | MIT | [`licenses/langsmith--0.7.14.txt`](web/nemoclaw/vendor/licenses/langsmith--0.7.14.txt) |
| browser-runtime | marked | 14.1.4 | MIT | [`licenses/marked--14.1.4.txt`](web/nemoclaw/vendor/licenses/marked--14.1.4.txt) |
| browser-runtime | mustache | 4.2.0 | MIT | [`licenses/mustache--4.2.0.txt`](web/nemoclaw/vendor/licenses/mustache--4.2.0.txt) |
| browser-runtime | openai | 6.45.0 | Apache-2.0 | [`licenses/openai--6.45.0.txt`](web/nemoclaw/vendor/licenses/openai--6.45.0.txt) |
| browser-runtime | p-finally | 1.0.0 | MIT | [`licenses/p-finally--1.0.0.txt`](web/nemoclaw/vendor/licenses/p-finally--1.0.0.txt) |
| browser-runtime | p-queue | 6.6.2 | MIT | [`licenses/p-queue--6.6.2.txt`](web/nemoclaw/vendor/licenses/p-queue--6.6.2.txt) |
| browser-bundle-input | p-retry | 7.1.1 | MIT | [lock](scripts/browser-vendor/package-lock.json) |
| browser-runtime | p-timeout | 3.2.0 | MIT | [`licenses/p-timeout--3.2.0.txt`](web/nemoclaw/vendor/licenses/p-timeout--3.2.0.txt) |
| browser-runtime | zod | 3.25.76 | MIT | [`licenses/zod--3.25.76.txt`](web/nemoclaw/vendor/licenses/zod--3.25.76.txt) |

### Why a Python license appears in the browser table

`argparse@2.0.1` is a JavaScript npm package used transitively by `js-yaml@5.2.1`.
`Python-2.0` is the package's declared license identifier; no Python interpreter or Python package
is included in the browser bundle by that dependency.

## Python runtime and repository-tool packages

Sources of truth are the exact lock files named in the Scope column. The same package/version is shown once with every applicable scope. License expressions were resolved from the exact-version PyPI metadata; legacy ambiguous `BSD` metadata was checked against the package license text.

| Scope | Package | Version | SPDX license expression | Evidence |
|---|---|---|---|---|
| workspace-runtime | aiohappyeyeballs | 2.6.2 | PSF-2.0 | [PyPI](https://pypi.org/pypi/aiohappyeyeballs/2.6.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | aiohttp | 3.14.1 | Apache-2.0 AND MIT | [PyPI](https://pypi.org/pypi/aiohttp/3.14.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | aiosignal | 1.4.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/aiosignal/1.4.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | altair | 6.2.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/altair/6.2.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | annotated-doc | 0.0.4 | MIT | [PyPI](https://pypi.org/pypi/annotated-doc/0.0.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | annotated-types | 0.7.0 | MIT | [PyPI](https://pypi.org/pypi/annotated-types/0.7.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | anyio | 4.14.1 | MIT | [PyPI](https://pypi.org/pypi/anyio/4.14.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | argon2-cffi | 25.1.0 | MIT | [PyPI](https://pypi.org/pypi/argon2-cffi/25.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | argon2-cffi-bindings | 25.1.0 | MIT | [PyPI](https://pypi.org/pypi/argon2-cffi-bindings/25.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | arrow | 1.4.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/arrow/1.4.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | arxiv | 3.0.0 | MIT | [PyPI](https://pypi.org/pypi/arxiv/3.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | asgiref | 3.11.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/asgiref/3.11.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | asttokens | 3.0.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/asttokens/3.0.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | async-lru | 2.3.0 | MIT | [PyPI](https://pypi.org/pypi/async-lru/2.3.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | attrs | 26.1.0 | MIT | [PyPI](https://pypi.org/pypi/attrs/26.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | babel | 2.18.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/babel/2.18.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, material-tooling | beautifulsoup4 | 4.15.0 | MIT | [PyPI](https://pypi.org/pypi/beautifulsoup4/4.15.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock) |
| workspace-runtime | bleach | 6.4.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/bleach/6.4.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | blinker | 1.9.0 | MIT | [PyPI](https://pypi.org/pypi/blinker/1.9.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | boolean-py | 5.0 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/boolean-py/5.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | brotli | 1.2.0 | MIT | [PyPI](https://pypi.org/pypi/brotli/1.2.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | cachecontrol | 0.14.4 | Apache-2.0 | [PyPI](https://pypi.org/pypi/cachecontrol/0.14.4/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | cachetools | 7.1.4 | MIT | [PyPI](https://pypi.org/pypi/cachetools/7.1.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, material-tooling, security-tooling | certifi | 2026.6.17 | MPL-2.0 | [PyPI](https://pypi.org/pypi/certifi/2026.6.17/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | cffi | 2.0.0 | MIT | [PyPI](https://pypi.org/pypi/cffi/2.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | chardet | 5.2.0 | LGPL-2.0-or-later | [PyPI](https://pypi.org/pypi/chardet/5.2.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, material-tooling, security-tooling | charset-normalizer | 3.4.7 | MIT | [PyPI](https://pypi.org/pypi/charset-normalizer/3.4.7/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | click | 8.4.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/click/8.4.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | colorama | 0.4.6 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/colorama/0.4.6/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | comm | 0.2.3 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/comm/0.2.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | contourpy | 1.3.3 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/contourpy/1.3.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | cryptography | 49.0.0 | Apache-2.0 OR BSD-3-Clause | [PyPI](https://pypi.org/pypi/cryptography/49.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | cycler | 0.12.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/cycler/0.12.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | cyclonedx-bom | 7.3.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/cyclonedx-bom/7.3.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| security-tooling | cyclonedx-python-lib | 11.11.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/cyclonedx-python-lib/11.11.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | debugpy | 1.8.21 | MIT | [PyPI](https://pypi.org/pypi/debugpy/1.8.21/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | decorator | 5.3.1 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/decorator/5.3.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | defusedxml | 0.7.1 | PSF-2.0 | [PyPI](https://pypi.org/pypi/defusedxml/0.7.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | distro | 1.9.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/distro/1.9.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, sandbox-admin-runtime | docker | 7.1.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/docker/7.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`cpu/services/sandbox_admin/requirements.txt`](cpu/services/sandbox_admin/requirements.txt) |
| workspace-runtime | duckdb | 1.5.4 | MIT | [PyPI](https://pypi.org/pypi/duckdb/1.5.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | executing | 2.2.1 | MIT | [PyPI](https://pypi.org/pypi/executing/2.2.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | faiss-cpu | 1.14.3 | MIT | [PyPI](https://pypi.org/pypi/faiss-cpu/1.14.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, sandbox-admin-runtime | fastapi | 0.138.2 | MIT | [PyPI](https://pypi.org/pypi/fastapi/0.138.2/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`cpu/services/sandbox_admin/requirements.txt`](cpu/services/sandbox_admin/requirements.txt) |
| workspace-runtime | fastjsonschema | 2.21.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/fastjsonschema/2.21.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | feedparser | 6.0.12 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/feedparser/6.0.12/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | filelock | 3.29.4 | MIT | [PyPI](https://pypi.org/pypi/filelock/3.29.4/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | filetype | 1.2.0 | MIT | [PyPI](https://pypi.org/pypi/filetype/1.2.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | fonttools | 4.63.0 | MIT | [PyPI](https://pypi.org/pypi/fonttools/4.63.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | fqdn | 1.5.1 | MPL-2.0 | [PyPI](https://pypi.org/pypi/fqdn/1.5.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | frozenlist | 1.8.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/frozenlist/1.8.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | fsspec | 2026.6.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/fsspec/2026.6.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | gitdb | 4.0.12 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/gitdb/4.0.12/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | gitpython | 3.1.50 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/gitpython/3.1.50/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | googleapis-common-protos | 1.75.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/googleapis-common-protos/1.75.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | gradio | 6.19.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/gradio/6.19.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | gradio-client | 2.5.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/gradio-client/2.5.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | greenlet | 3.5.3 | MIT AND PSF-2.0 | [PyPI](https://pypi.org/pypi/greenlet/3.5.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | groovy | 0.1.2 | MIT | [PyPI](https://pypi.org/pypi/groovy/0.1.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | grpcio | 1.81.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/grpcio/1.81.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | h11 | 0.16.0 | MIT | [PyPI](https://pypi.org/pypi/h11/0.16.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | hf-gradio | 0.4.1 | MIT | [PyPI](https://pypi.org/pypi/hf-gradio/0.4.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | hf-xet | 1.5.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/hf-xet/1.5.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | httpcore | 1.0.9 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/httpcore/1.0.9/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | httptools | 0.8.0 | MIT | [PyPI](https://pypi.org/pypi/httptools/0.8.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | httpx | 0.28.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/httpx/0.28.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | httpx-sse | 0.4.3 | MIT | [PyPI](https://pypi.org/pypi/httpx-sse/0.4.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | huggingface-hub | 1.21.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/huggingface-hub/1.21.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, material-tooling, security-tooling | idna | 3.18 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/idna/3.18/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | importlib-metadata | 8.7.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/importlib-metadata/8.7.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | ipykernel | 7.3.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/ipykernel/7.3.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | ipython | 9.15.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/ipython/9.15.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | ipython-pygments-lexers | 1.1.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/ipython-pygments-lexers/1.1.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | ipywidgets | 8.1.8 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/ipywidgets/8.1.8/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | isoduration | 20.11.0 | ISC | [PyPI](https://pypi.org/pypi/isoduration/20.11.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | itsdangerous | 2.2.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/itsdangerous/2.2.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jedi | 0.20.0 | MIT | [PyPI](https://pypi.org/pypi/jedi/0.20.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jinja2 | 3.1.6 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jinja2/3.1.6/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jiter | 0.16.0 | MIT | [PyPI](https://pypi.org/pypi/jiter/0.16.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | joblib | 1.5.3 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/joblib/1.5.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | json5 | 0.15.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/json5/0.15.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jsonpatch | 1.33 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jsonpatch/1.33/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | jsonpointer | 3.1.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jsonpointer/3.1.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | jsonschema | 4.26.0 | MIT | [PyPI](https://pypi.org/pypi/jsonschema/4.26.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | jsonschema-specifications | 2025.9.1 | MIT | [PyPI](https://pypi.org/pypi/jsonschema-specifications/2025.9.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | jupyter-app-launcher | 0.3.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-app-launcher/0.3.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyter-client | 8.9.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-client/8.9.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyter-core | 5.9.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-core/5.9.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyter-events | 0.12.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-events/0.12.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyter-lsp | 2.3.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-lsp/2.3.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyter-server | 2.20.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-server/2.20.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyter-server-proxy | 4.5.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-server-proxy/4.5.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyter-server-terminals | 0.5.4 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyter-server-terminals/0.5.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyterlab | 4.5.9 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyterlab/4.5.9/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyterlab-git | 0.54.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyterlab-git/0.54.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyterlab-git-core | 0.54.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyterlab-git-core/0.54.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyterlab-pygments | 0.3.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyterlab-pygments/0.3.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyterlab-server | 2.28.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyterlab-server/2.28.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupyterlab-widgets | 3.0.16 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/jupyterlab-widgets/3.0.16/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | jupytext | 1.19.4 | MIT | [PyPI](https://pypi.org/pypi/jupytext/1.19.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | kiwisolver | 1.5.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/kiwisolver/1.5.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain | 1.3.11 | MIT | [PyPI](https://pypi.org/pypi/langchain/1.3.11/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-classic | 1.0.8 | MIT | [PyPI](https://pypi.org/pypi/langchain-classic/1.0.8/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-community | 0.4.2 | MIT | [PyPI](https://pypi.org/pypi/langchain-community/0.4.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-core | 1.4.8 | MIT | [PyPI](https://pypi.org/pypi/langchain-core/1.4.8/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-mcp-adapters | 0.3.0 | MIT | [PyPI](https://pypi.org/pypi/langchain-mcp-adapters/0.3.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-nvidia-ai-endpoints | 1.4.1 | MIT | [PyPI](https://pypi.org/pypi/langchain-nvidia-ai-endpoints/1.4.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-openai | 1.3.3 | MIT | [PyPI](https://pypi.org/pypi/langchain-openai/1.3.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-protocol | 0.0.18 | MIT | [PyPI](https://pypi.org/pypi/langchain-protocol/0.0.18/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langchain-text-splitters | 1.1.2 | MIT | [PyPI](https://pypi.org/pypi/langchain-text-splitters/1.1.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langgraph | 1.2.6 | MIT | [PyPI](https://pypi.org/pypi/langgraph/1.2.6/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langgraph-checkpoint | 4.1.1 | MIT | [PyPI](https://pypi.org/pypi/langgraph-checkpoint/4.1.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langgraph-prebuilt | 1.1.0 | MIT | [PyPI](https://pypi.org/pypi/langgraph-prebuilt/1.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langgraph-sdk | 0.4.2 | MIT | [PyPI](https://pypi.org/pypi/langgraph-sdk/0.4.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | langsmith | 0.9.3 | MIT | [PyPI](https://pypi.org/pypi/langsmith/0.9.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | lark | 1.3.1 | MIT | [PyPI](https://pypi.org/pypi/lark/1.3.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| security-tooling | license-expression | 30.4.4 | Apache-2.0 | [PyPI](https://pypi.org/pypi/license-expression/30.4.4/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| material-tooling, security-tooling | lxml | 6.1.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/lxml/6.1.1/json); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | markdown-it-py | 4.2.0 | MIT | [PyPI](https://pypi.org/pypi/markdown-it-py/4.2.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| material-tooling | markdownify | 1.2.2 | MIT | [PyPI](https://pypi.org/pypi/markdownify/1.2.2/json); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock) |
| workspace-runtime | markupsafe | 3.0.3 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/markupsafe/3.0.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | matplotlib | 3.10.9 | PSF-2.0 | [PyPI](https://pypi.org/pypi/matplotlib/3.10.9/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | matplotlib-inline | 0.2.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/matplotlib-inline/0.2.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | mcp | 1.28.1 | MIT | [PyPI](https://pypi.org/pypi/mcp/1.28.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | mdit-py-plugins | 0.6.1 | MIT | [PyPI](https://pypi.org/pypi/mdit-py-plugins/0.6.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | mdurl | 0.1.2 | MIT | [PyPI](https://pypi.org/pypi/mdurl/0.1.2/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | mistune | 3.3.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/mistune/3.3.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | msgpack | 1.2.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/msgpack/1.2.1/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | multidict | 6.7.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/multidict/6.7.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | narwhals | 2.22.1 | MIT | [PyPI](https://pypi.org/pypi/narwhals/2.22.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | nbclient | 0.11.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/nbclient/0.11.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | nbconvert | 7.17.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/nbconvert/7.17.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | nbdime | 4.0.4 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/nbdime/4.0.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | nbformat | 5.10.4 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/nbformat/5.10.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | nemo-microservices | 1.5.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/nemo-microservices/1.5.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | nest-asyncio | 1.6.0 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/nest-asyncio/1.6.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | nest-asyncio2 | 1.7.2 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/nest-asyncio2/1.7.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | networkx | 3.4.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/networkx/3.4.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | notebook-shim | 0.2.4 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/notebook-shim/0.2.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | [PyPI](https://pypi.org/pypi/numpy/2.4.6/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | openai | 2.44.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/openai/2.44.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-api | 1.34.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-api/1.34.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-exporter-otlp-proto-common | 1.34.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-exporter-otlp-proto-common/1.34.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-exporter-otlp-proto-grpc | 1.34.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-exporter-otlp-proto-grpc/1.34.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-instrumentation | 0.55b1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-instrumentation/0.55b1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-instrumentation-asgi | 0.55b1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-instrumentation-asgi/0.55b1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-instrumentation-fastapi | 0.55b1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-instrumentation-fastapi/0.55b1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-instrumentation-requests | 0.55b1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-instrumentation-requests/0.55b1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-proto | 1.34.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-proto/1.34.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-sdk | 1.34.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-sdk/1.34.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-semantic-conventions | 0.55b1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-semantic-conventions/0.55b1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | opentelemetry-util-http | 0.55b1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/opentelemetry-util-http/0.55b1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | orjson | 3.11.9 | MPL-2.0 AND (Apache-2.0 OR MIT) | [PyPI](https://pypi.org/pypi/orjson/3.11.9/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | ormsgpack | 1.12.2 | Apache-2.0 OR MIT | [PyPI](https://pypi.org/pypi/ormsgpack/1.12.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | overrides | 7.7.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/overrides/7.7.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | packageurl-python | 0.17.6 | MIT | [PyPI](https://pypi.org/pypi/packageurl-python/0.17.6/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | packaging | 26.2 | Apache-2.0 OR BSD-2-Clause | [PyPI](https://pypi.org/pypi/packaging/26.2/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | pandas | 2.3.3 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/pandas/2.3.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pandocfilters | 1.5.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/pandocfilters/1.5.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | parso | 0.8.7 | MIT | [PyPI](https://pypi.org/pypi/parso/0.8.7/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pdf2image | 1.17.0 | MIT | [PyPI](https://pypi.org/pypi/pdf2image/1.17.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pexpect | 4.9.0 | ISC | [PyPI](https://pypi.org/pypi/pexpect/4.9.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pillow | 12.2.0 | MIT-CMU | [PyPI](https://pypi.org/pypi/pillow/12.2.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | pip | 26.1.2 | MIT | [PyPI](https://pypi.org/pypi/pip/26.1.2/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| security-tooling | pip-api | 0.0.34 | Apache-2.0 | [PyPI](https://pypi.org/pypi/pip-api/0.0.34/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| security-tooling | pip-audit | 2.10.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/pip-audit/2.10.1/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| security-tooling | pip-requirements-parser | 32.0.1 | MIT | [PyPI](https://pypi.org/pypi/pip-requirements-parser/32.0.1/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | platformdirs | 4.10.0 | MIT | [PyPI](https://pypi.org/pypi/platformdirs/4.10.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | playwright | 1.61.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/playwright/1.61.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | plotly | 6.8.0 | MIT | [PyPI](https://pypi.org/pypi/plotly/6.8.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | prometheus-client | 0.25.0 | Apache-2.0 AND BSD-2-Clause | [PyPI](https://pypi.org/pypi/prometheus-client/0.25.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | prompt-toolkit | 3.0.52 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/prompt-toolkit/3.0.52/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | propcache | 0.5.2 | Apache-2.0 | [PyPI](https://pypi.org/pypi/propcache/0.5.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | protobuf | 5.29.6 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/protobuf/5.29.6/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | psutil | 7.2.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/psutil/7.2.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | ptyprocess | 0.7.0 | ISC | [PyPI](https://pypi.org/pypi/ptyprocess/0.7.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pure-eval | 0.2.3 | MIT | [PyPI](https://pypi.org/pypi/pure-eval/0.2.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | py-serializable | 2.1.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/py-serializable/2.1.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | pyarrow | 24.0.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/pyarrow/24.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pycparser | 3.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/pycparser/3.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pydantic | 2.13.4 | MIT | [PyPI](https://pypi.org/pypi/pydantic/2.13.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pydantic-core | 2.46.4 | MIT | [PyPI](https://pypi.org/pypi/pydantic-core/2.46.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pydantic-settings | 2.14.2 | MIT | [PyPI](https://pypi.org/pypi/pydantic-settings/2.14.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pydeck | 0.9.2 | Apache-2.0 | [PyPI](https://pypi.org/pypi/pydeck/0.9.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pydub | 0.25.1 | MIT | [PyPI](https://pypi.org/pypi/pydub/0.25.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pyee | 13.0.1 | MIT | [PyPI](https://pypi.org/pypi/pyee/13.0.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | pygments | 2.20.0 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/pygments/2.20.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | pyjwt | 2.13.0 | MIT | [PyPI](https://pypi.org/pypi/pyjwt/2.13.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | pyparsing | 3.3.2 | MIT | [PyPI](https://pypi.org/pypi/pyparsing/3.3.2/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | python-dateutil | 2.9.0.post0 | Apache-2.0 OR BSD-3-Clause | [PyPI](https://pypi.org/pypi/python-dateutil/2.9.0.post0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | python-dotenv | 1.2.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/python-dotenv/1.2.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | python-json-logger | 4.1.0 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/python-json-logger/4.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | python-multipart | 0.0.32 | Apache-2.0 | [PyPI](https://pypi.org/pypi/python-multipart/0.0.32/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | pytz | 2026.2 | MIT | [PyPI](https://pypi.org/pypi/pytz/2026.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, sandbox-admin-runtime | pyyaml | 6.0.3 | MIT | [PyPI](https://pypi.org/pypi/pyyaml/6.0.3/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`cpu/services/sandbox_admin/requirements.txt`](cpu/services/sandbox_admin/requirements.txt) |
| workspace-runtime | pyzmq | 27.1.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/pyzmq/27.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | rank-bm25 | 0.2.2 | Apache-2.0 | [PyPI](https://pypi.org/pypi/rank-bm25/0.2.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | referencing | 0.37.0 | MIT | [PyPI](https://pypi.org/pypi/referencing/0.37.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | regex | 2026.6.28 | Apache-2.0 AND CNRI-Python | [PyPI](https://pypi.org/pypi/regex/2026.6.28/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | requests | 2.33.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/requests/2.33.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| material-tooling, security-tooling | requests | 2.34.2 | Apache-2.0 | [PyPI](https://pypi.org/pypi/requests/2.34.2/json); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | requests-toolbelt | 1.0.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/requests-toolbelt/1.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | rfc3339-validator | 0.1.4 | MIT | [PyPI](https://pypi.org/pypi/rfc3339-validator/0.1.4/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | rfc3986-validator | 0.1.1 | MIT | [PyPI](https://pypi.org/pypi/rfc3986-validator/0.1.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | rfc3987-syntax | 1.1.0 | MIT | [PyPI](https://pypi.org/pypi/rfc3987-syntax/1.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | rich | 15.0.0 | MIT | [PyPI](https://pypi.org/pypi/rich/15.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | rpds-py | 2026.5.1 | MIT | [PyPI](https://pypi.org/pypi/rpds-py/2026.5.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | safehttpx | 0.1.7 | MIT | [PyPI](https://pypi.org/pypi/safehttpx/0.1.7/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | safetensors | 0.8.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/safetensors/0.8.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | scikit-learn | 1.7.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/scikit-learn/1.7.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | scipy | 1.17.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/scipy/1.17.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | semantic-version | 2.10.0 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/semantic-version/2.10.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | send2trash | 2.1.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/send2trash/2.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | setuptools | 82.0.1 | MIT | [PyPI](https://pypi.org/pypi/setuptools/82.0.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | sgmllib3k | 1.0.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/sgmllib3k/1.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | shellingham | 1.5.4 | ISC | [PyPI](https://pypi.org/pypi/shellingham/1.5.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | simpervisor | 1.0.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/simpervisor/1.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, material-tooling, security-tooling | six | 1.17.0 | MIT | [PyPI](https://pypi.org/pypi/six/1.17.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | smmap | 5.0.3 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/smmap/5.0.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | sniffio | 1.3.1 | MIT OR Apache-2.0 | [PyPI](https://pypi.org/pypi/sniffio/1.3.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | sortedcontainers | 2.4.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/sortedcontainers/2.4.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, material-tooling | soupsieve | 2.8.4 | MIT | [PyPI](https://pypi.org/pypi/soupsieve/2.8.4/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock) |
| workspace-runtime | sqlalchemy | 2.0.51 | MIT | [PyPI](https://pypi.org/pypi/sqlalchemy/2.0.51/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | sse-starlette | 3.4.5 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/sse-starlette/3.4.5/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | stack-data | 0.6.3 | MIT | [PyPI](https://pypi.org/pypi/stack-data/0.6.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, sandbox-admin-runtime | starlette | 1.3.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/starlette/1.3.1/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`cpu/services/sandbox_admin/requirements.txt`](cpu/services/sandbox_admin/requirements.txt) |
| workspace-runtime | streamlit | 1.58.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/streamlit/1.58.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | tavily-python | 0.7.26 | MIT | [PyPI](https://pypi.org/pypi/tavily-python/0.7.26/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | tenacity | 9.1.4 | Apache-2.0 | [PyPI](https://pypi.org/pypi/tenacity/9.1.4/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | terminado | 0.18.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/terminado/0.18.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | threadpoolctl | 3.6.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/threadpoolctl/3.6.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | tiktoken | 0.13.0 | MIT | [PyPI](https://pypi.org/pypi/tiktoken/0.13.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | tinycss2 | 1.5.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/tinycss2/1.5.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | tokenizers | 0.22.2 | Apache-2.0 | [PyPI](https://pypi.org/pypi/tokenizers/0.22.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | toml | 0.10.2 | MIT | [PyPI](https://pypi.org/pypi/toml/0.10.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | tomli | 2.4.1 | MIT | [PyPI](https://pypi.org/pypi/tomli/2.4.1/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| security-tooling | tomli-w | 1.2.0 | MIT | [PyPI](https://pypi.org/pypi/tomli-w/1.2.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | tomlkit | 0.14.0 | MIT | [PyPI](https://pypi.org/pypi/tomlkit/0.14.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | torch | 2.11.0+cu128 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/torch/2.11.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | torchaudio | 2.11.0+cu128 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/torchaudio/2.11.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | torchvision | 0.26.0+cu128 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/torchvision/0.26.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | tornado | 6.5.7 | Apache-2.0 | [PyPI](https://pypi.org/pypi/tornado/6.5.7/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | tqdm | 4.68.3 | MPL-2.0 AND MIT | [PyPI](https://pypi.org/pypi/tqdm/4.68.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | traitlets | 5.15.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/traitlets/5.15.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | transformers | 5.12.1 | Apache-2.0 | [PyPI](https://pypi.org/pypi/transformers/5.12.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | typer | 0.25.1 | MIT | [PyPI](https://pypi.org/pypi/typer/0.25.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, material-tooling, security-tooling | typing-extensions | 4.15.0 | PSF-2.0 | [PyPI](https://pypi.org/pypi/typing-extensions/4.15.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | typing-inspection | 0.4.2 | MIT | [PyPI](https://pypi.org/pypi/typing-inspection/0.4.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | tzdata | 2026.2 | Apache-2.0 | [PyPI](https://pypi.org/pypi/tzdata/2026.2/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, security-tooling | uri-template | 1.3.0 | MIT | [PyPI](https://pypi.org/pypi/uri-template/1.3.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime, material-tooling, security-tooling | urllib3 | 2.7.0 | MIT | [PyPI](https://pypi.org/pypi/urllib3/2.7.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/materials/requirements.lock`](scripts/materials/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | uuid-utils | 0.16.2 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/uuid-utils/0.16.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | uv | 0.11.25 | MIT OR Apache-2.0 | [PyPI](https://pypi.org/pypi/uv/0.11.25/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, sandbox-admin-runtime | uvicorn | 0.49.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/uvicorn/0.49.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`cpu/services/sandbox_admin/requirements.txt`](cpu/services/sandbox_admin/requirements.txt) |
| workspace-runtime | uvloop | 0.22.1 | MIT | [PyPI](https://pypi.org/pypi/uvloop/0.22.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | voila | 0.5.12 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/voila/0.5.12/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | watchdog | 6.0.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/watchdog/6.0.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | watchfiles | 1.2.0 | MIT | [PyPI](https://pypi.org/pypi/watchfiles/1.2.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | wcwidth | 0.8.2 | MIT | [PyPI](https://pypi.org/pypi/wcwidth/0.8.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime, security-tooling | webcolors | 25.10.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/webcolors/25.10.0/json); [`workspace/requirements.lock`](workspace/requirements.lock); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | webencodings | 0.5.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/webencodings/0.5.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | websocket-client | 1.9.0 | Apache-2.0 | [PyPI](https://pypi.org/pypi/websocket-client/1.9.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | websockets | 15.0.1 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/websockets/15.0.1/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| security-tooling | wheel | 0.47.0 | MIT | [PyPI](https://pypi.org/pypi/wheel/0.47.0/json); [`scripts/security/requirements-sca.lock`](scripts/security/requirements-sca.lock) |
| workspace-runtime | widgetsnbextension | 4.0.15 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/widgetsnbextension/4.0.15/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | wrapt | 1.17.3 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/wrapt/1.17.3/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | xxhash | 3.8.0 | BSD-2-Clause | [PyPI](https://pypi.org/pypi/xxhash/3.8.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | yarl | 1.24.2 | Apache-2.0 | [PyPI](https://pypi.org/pypi/yarl/1.24.2/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | zipp | 4.1.0 | MIT | [PyPI](https://pypi.org/pypi/zipp/4.1.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |
| workspace-runtime | zstandard | 0.25.0 | BSD-3-Clause | [PyPI](https://pypi.org/pypi/zstandard/0.25.0/json); [`workspace/requirements.lock`](workspace/requirements.lock) |

### Less common license families and their scope

These identifiers are not themselves a failed review. Distribution form, modification, linking,
notices, and source-availability obligations still require the accountable open-source review.

| Identifier | Packages in this inventory | Scope note |
|---|---|---|
| MPL-2.0 | `certifi`, `fqdn`; compound expressions for `orjson` and `tqdm` | Runtime dependencies; MPL is file-level copyleft, so retain upstream terms and review the exact distributed form. |
| LGPL-2.0-or-later | `chardet` | Security-tooling environment only; it is not in the learner browser artifact or workspace runtime lock. |
| PSF-2.0 | `aiohappyeyeballs`, `defusedxml`, `matplotlib`, `typing-extensions`; compound expression for `greenlet` | Permissive Python ecosystem dependencies. |
| 0BSD, Zlib, CC0-1.0 | Compound expression for `numpy` | NumPy's exact-version metadata accounts for bundled or incorporated subcomponents; these are not separate direct requirements. |
| ISC | `isoduration`, `pexpect`, `ptyprocess`, `shellingham` | Permissive runtime dependencies. |

No package row in this inventory declares GPL. The only GNU-family expression is the
`LGPL-2.0-or-later` tooling entry above.

## Direct container, runtime, and operating-system declarations

These are direct Dockerfile declarations not represented as Python or browser-lock rows above. Mixed images and operating-system packages require the exact built-image SBOM before distribution; a tag or source declaration cannot supply their complete transitive license set.

| Scope | Component | Declared version | SPDX license | Evidence / disposition |
|---|---|---|---|---|
| workspace base image | nvcr.io/nvidia/cuda | 12.8.1-cudnn-devel-ubuntu22.04 | NOASSERTION | mixed NVIDIA and Ubuntu image; `workspace/Dockerfile` |
| service base image | docker | 20.10 | NOASSERTION | mixed image; `cpu/services/docker_router/Dockerfile` |
| service base image | python | 3.11-slim | NOASSERTION | Python-2.0 plus mixed Debian image; `cpu/services/llm_client/llm_client.Dockerfile` |
| service base image | python | 3.12-slim | NOASSERTION | Python-2.0 plus mixed Debian image; `cpu/services/sandbox_admin/Dockerfile` |
| OpenShell build image | ghcr.io/nvidia/openshell/cluster | 0.0.8 | NOASSERTION | image SBOM required; `cpu/services/openclaw/openclaw_shell.Dockerfile` |
| OpenShell runtime image | ghcr.io/nvidia/openshell-community/sandboxes/base | latest | NOASSERTION | mutable tag; exact image digest and SBOM required before distribution |
| OpenClaw runtime | openclaw | 2026.5.28 | MIT | [npm](https://www.npmjs.com/package/openclaw/v/2026.5.28) |
| policy engine | Open Policy Agent | 1.4.2 | Apache-2.0 | [upstream](https://github.com/open-policy-agent/opa/releases/tag/v1.4.2) |
| browser binary | Chromium installed by Playwright | Playwright 1.61.0 channel | NOASSERTION | multi-license browser distribution; built-image SBOM required |
| workspace OS packages | python3.11, python3.11-dev, python3-pip, build-essential, bash, curl, unzip, wget, git, libgl1, tree, jq, nodejs, npm, poppler-utils | base-image-resolved | NOASSERTION | `workspace/Dockerfile`; exact versions and licenses come from built-image SBOM |
| OpenClaw OS packages | jq, socat, tree, curl, git, gettext-base | base-image-resolved | NOASSERTION | `cpu/services/openclaw/openclaw_shell.Dockerfile`; exact versions and licenses come from built-image SBOM |
| router OS packages | python3, py3-pip | base-image-resolved | NOASSERTION | `cpu/services/docker_router/Dockerfile`; exact versions and licenses come from built-image SBOM |

### Resolving `NOASSERTION` after an image scan

A mixed container image or operating-system layer does not have one honest aggregate SPDX license.
Do not replace an image-level `NOASSERTION` with the license of its best-known component. Instead:

1. Pin or record the exact image digest.
2. Generate a CycloneDX JSON SBOM from that digest with the approved image scanner.
3. Render a component-level static appendix:

   ```text
   python3 scripts/compliance/render_sbom_license_inventory.py \
     --sbom <cyclonedx.json> \
     --artifact-id <image-name>@sha256:<64-hex-digest> \
     --out <artifact-license-inventory.md>
   ```

4. Retain the exact SBOM with the release evidence and review every component still reported as
   `NOASSERTION`. The renderer uses an exact package/version entry from this file only when the
   scanner lacks an SPDX identifier or expression; it labels that source as an
   `exact package/version static fallback` rather than scanner evidence.

The generated appendix enumerates component licenses but does not convert the aggregate mixed-image
row into a single-license claim.

## Third-party course-material relationships

This is not a dependency table. It records every provenance row with an external source URL. `inspiration` and `summary` mean the external work is referenced but not copied; `recreation` or `conversion` requires the recorded redistribution disposition to be reviewed. The exact source labels are preserved rather than converted into SPDX identifiers when the source is not OSS.

| Repository file | Relationship | External source | Recorded terms | Source |
|---|---|---|---|---|
| web/nemoclaw/assets/figures/01a-loop-1.svg | inspiration | Russell & Norvig, AIMA ch.1 | (c) Pearson; no reuse license stated | [source](https://aima.cs.berkeley.edu/) |
| web/nemoclaw/assets/figures/01a-loop-2.svg | inspiration | OpenAI API docs | OpenAI terms | [source](https://platform.openai.com/docs) |
| web/nemoclaw/assets/figures/01b-react-1.svg | original | original course diagram; ReAct (Yao et al. 2022) | Apache-2.0 | [source](https://arxiv.org/abs/2210.03629) |
| web/nemoclaw/assets/figures/01b-react-2.svg | recreation | Lilian Weng, LLM-Powered Autonomous Agents | no reuse license stated | [source](https://lilianweng.github.io/posts/2023-06-23-agent/) |
| web/nemoclaw/assets/figures/01b-react-3.svg | inspiration | original course diagram; ReAct (Yao et al. 2022) | Apache-2.0 | [source](https://arxiv.org/abs/2210.03629) |
| web/nemoclaw/assets/figures/01b-react-4.svg | inspiration | original course diagram; inspired by Liu et al. 2023 | Apache-2.0 | [source](https://arxiv.org/abs/2307.03172) |
| web/nemoclaw/assets/figures/01c-tools-2.svg | original | original course diagram; MCP | Apache-2.0 | [source](https://modelcontextprotocol.io) |
| web/nemoclaw/assets/figures/02b-rag-1.svg | inspiration | NVIDIA developer blogs | (c) NVIDIA | [source](https://developer.nvidia.com/blog/rag-101-demystifying-retrieval-augmented-generation-pipelines/) |
| web/nemoclaw/assets/figures/02b-rag-3.svg | recreation | Edge et al. 2024 | see arXiv listing | [source](https://arxiv.org/abs/2404.16130) |
| web/nemoclaw/assets/figures/fig2_react.svg | conversion | Yao et al. 2022; figure conversion | see arXiv listing | [source](https://arxiv.org/abs/2210.03629) |
| web/nemoclaw/assets/figures/fig2_rewoo.svg | conversion | Xu et al. 2023; figure conversion | see arXiv listing | [source](https://arxiv.org/abs/2305.18323) |
| web/nemoclaw/assets/figures/lethal-trifecta.svg | original course graphic | course-provided graphic; Simon Willison lethal trifecta definition | Apache-2.0 | [source](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) |
| web/nemoclaw/assets/figures/rag_arch_2021.svg | conversion | Lewis et al. 2020; figure conversion | see arXiv listing | [source](https://arxiv.org/abs/2005.11401) |
| web/nemoclaw/mats/agentic_ai_learning_path_links.md | compilation | NVIDIA Agentic AI Learning Path | (c) NVIDIA; external terms | [source](https://developer.nvidia.com/topics/ai/agentic-ai-learning-path/) |
| web/nemoclaw/mats/arxiv-2005.11401-rag.md | summary | Lewis et al. 2020 (RAG) | card Apache-2.0; paper: see arXiv listing | [source](https://arxiv.org/abs/2005.11401) |
| web/nemoclaw/mats/arxiv-2210.03629-react.md | summary | Yao et al. 2022 (ReAct) | card Apache-2.0; paper: see arXiv listing | [source](https://arxiv.org/abs/2210.03629) |
| web/nemoclaw/mats/arxiv-2305.18323-rewoo.md | summary | Xu et al. 2023 (ReWOO) | card Apache-2.0; paper: see arXiv listing | [source](https://arxiv.org/abs/2305.18323) |
| web/nemoclaw/mats/arxiv-2404.16130-graphrag.md | summary | Edge et al. 2024 (GraphRAG) | card Apache-2.0; paper: see arXiv listing | [source](https://arxiv.org/abs/2404.16130) |
| web/nemoclaw/mats/build-nvidia-com-spark-hermes-agent-overview.md | conversion | NVIDIA public page | (c) NVIDIA; external terms | [source](https://developer.nvidia.com/) |
| web/nemoclaw/mats/build-nvidia-com-spark-nemoclaw-applications.md | conversion | NVIDIA public page | (c) NVIDIA; external terms | [source](https://developer.nvidia.com/) |
| web/nemoclaw/mats/build-nvidia-com-spark-nemoclaw-instructions.md | conversion | NVIDIA public page | (c) NVIDIA; external terms | [source](https://developer.nvidia.com/) |
| web/nemoclaw/mats/developer-nvidia-com-blog-deploy-self-evolving-agents-for-fa.md | conversion | NVIDIA public page | (c) NVIDIA; external terms | [source](https://developer.nvidia.com/) |
| web/nemoclaw/mats/glossary_raw/README.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/_versions.json | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/ai-agents.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/ai-inference.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/ai-reasoning.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/deep-agents.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-agents-1.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-agents-2.svg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-agents-3.svg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-agents-4.svg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-inference-1.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-inference-2.svg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-inference-3.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-reasoning-1.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-reasoning-2.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/ai-reasoning-3.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/deep-agents-1.png | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/deep-agents-2.png | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/large-language-models-1.svg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/large-language-models-2.svg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/large-language-models-3.svg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/retrieval-augmented-generation-1.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/retrieval-augmented-generation-2.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/retrieval-augmented-generation-3.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/retrieval-augmented-generation-4.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/vector-database-1.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/vector-database-2.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/vector-database-3.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/vector-database-4.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/images/vector-database-5.jpeg | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/large-language-models.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/retrieval-augmented-generation.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/glossary_raw/vector-database.md | conversion | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |
| web/nemoclaw/mats/nvidia_agent_glossary.md | compilation | NVIDIA AI glossary | (c) NVIDIA; external terms | [source](https://www.nvidia.com/en-us/glossary/) |

## Deliberate exclusions

- Public URLs used only as links are not code dependencies and are not redistributed merely because the course links to them.
- NVIDIA-authored source files are governed by the root Apache-2.0 license and are not repeated in this third-party list.
- Exact transitive operating-system and container-layer packages are build outputs. Their authoritative list is the SBOM for the exact image digest, not an estimate copied from a mutable base image.
- This inventory records evidence; OSRB, Legal, and other accountable reviewers retain approval authority.
