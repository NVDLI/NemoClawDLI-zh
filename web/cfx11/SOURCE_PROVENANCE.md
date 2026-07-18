# c-fx-11-v1 source provenance

This candidate projects the NVIDIA DLI course `c-fx-11-v1`, *Building LLM Applications With Prompt Engineering*, into a browser course. The source repository remains unchanged.

- Reviewed source: `nvidia/dli/content/c-fx-11-v1`, branch `main`
- Acquisition: authenticated GitLab archive download
- Archive SHA-256: `aa7c553909b90f3a140fc5154234f70ea86a9422be5c8cfcc0c3714796f6ff4f`
- Imported scope: `task1/dli`
- Imported content: 30 notebooks plus the images and learner data beneath that scope
- Browser portability asset: the NVIDIA DLI logo referenced by every notebook is copied from its exact source URL to `assets/nvidia-logo.png` (SHA-256 `cbc005eb51ad3db35fd19db65bd50a4ce9fb329bb0a8a82ceb262cc3cac4f0d8`). The imported Markdown remains unchanged; the renderer maps that one source URL to the local copy.
- Excluded content: environment files, secrets, Docker and proxy configuration, assessment binaries, server runners, and notebook outputs
- Maintainer named by the source README: Josh Wyatt, NVIDIA

Recorded walkthroughs are supplemental references from the adjacent instructor-led course, not part of the imported C-FX archive:

- Walkthrough source: `nvidia/dli/content/s-fx-12-v2` at commit `8dc3b253e9ccb015470cd3b35d907b0fada38452`
- Imported relationship: referenced, not copied; the browser streams the existing NVIDIA course MP4 assets
- Placement evidence: `video-supplements.json` binds each invoked source notebook widget and helper file by SHA-256 to its matching browser lesson
- Scope decision: all 28 walkthroughs actually invoked by S-FX notebooks are shown; the uninvoked `walkthrough_53` helper is recorded as unused and is not assigned an invented placement
- Content drift: recordings may show older code, model availability, or model responses; the current browser lesson remains authoritative
- Terms: these are NVIDIA-owned course assets, but this repository does not infer or grant reuse terms for them

The source license is unresolved because the reviewed archive has no license file. Linked helper Python remains in the source repository and is not copied into this candidate. This candidate is suitable for internal branch staging and review. It must not enter an external release artifact until the course owner and OSRB confirm the applicable terms. The manifest does not infer Apache-2.0 from this repository's license.

`course.json` records the archive digest, every notebook digest, every cell source digest and byte length, and every copied support-file digest. `scripts/notebook-import/import_course.py` performs the import without formatting cell text. Reviewed deviations carry serialized `dli-course-source-patch/1.0` records with the upstream cell digest and a concrete reason. They repair one malformed quote sequence, redirect one unresolved helper link to its upstream source, and make standard-model setup cells honor the visible course selector while retaining commented compatible alternatives. The reasoning lesson keeps its distinct reasoning model and sampling contract. `scripts/validation/cfx11_course_audit.py` reconstructs the committed cell sources and fails when imported content or an explicit patch boundary drifts.
