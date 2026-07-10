# Third-party notices

This repository contains NVIDIA-authored course content and tooling under Apache-2.0 together with
third-party software and referenced or redistributed materials under their own terms.

Use these records to review the third-party scope:

- [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) is the top-level inventory of software,
  source materials, license identifiers, attribution, distribution relationships, and evidence.
- [`web/nemoclaw/vendor/browser-dependencies.json`](web/nemoclaw/vendor/browser-dependencies.json)
  records each browser-delivered artifact, its packages, digest, source references, and whether the
  output is a transformed bundle or a byte-for-byte upstream copy.
- [`web/nemoclaw/vendor/licenses/`](web/nemoclaw/vendor/licenses/) contains the license text copied
  for every browser package represented in the generated vendor manifest.
- [`scripts/compliance/docs/vendor_policy.md`](scripts/compliance/docs/vendor_policy.md) explains how
  to reproduce the vendor output and how new software or materials enter the repository.

## Browser vendor modification status

The browser vendor directory is generated from pinned npm inputs. It is not uniformly copied
as-is. The JavaScript bundles produced by esbuild are combined and minified, so their manifest rows
set `modified_from_upstream` to `true` and name the transformation. Files copied directly from an
installed package are byte-for-byte copies, although the destination filename may differ; those
rows set `modified_from_upstream` to `false`. No manual patch is applied inside the generated
vendor directory. Regeneration replaces the artifacts from the declared inputs.

Transformed bundles:

- `highlight-11.10.0.min.js`
- `codemirror-5.65.21.min.js`
- `js-yaml-5.2.1.esm.min.js`
- `langchain-1.4.7.esm.min.js`

Byte-for-byte upstream copies with repository-selected destination names:

- `highlight-github-dark-11.10.0.min.css`
- `codemirror-5.65.21.min.css`
- `codemirror-monokai-5.65.21.min.css`
- `marked-14.1.4.esm.js`

This notice is an index, not a replacement for the license texts or source-specific evidence.
