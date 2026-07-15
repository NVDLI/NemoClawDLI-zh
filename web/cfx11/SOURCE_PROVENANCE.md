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

The source license is unresolved because the reviewed archive has no license file. Linked helper Python remains in the source repository and is not copied into this candidate. This candidate is suitable for internal branch staging and review. It must not enter an external release artifact until the course owner and OSRB confirm the applicable terms. The manifest does not infer Apache-2.0 from this repository's license.

`course.json` records the archive digest, every notebook digest, every cell source digest and byte length, and every copied support-file digest. `scripts/notebook-import/import_course.py` performs the import without formatting cell text. Two cells carry serialized `dli-course-source-patch/1.0` records. One source cell accidentally follows a closed address string with a second, unclosed triple-quote opener, so the projection removes those three characters. One Markdown cell links a helper file whose source terms remain unresolved, so the projection points that reference to the upstream repository instead of copying it. Both records retain the upstream digest and reason. `scripts/validation/cfx11_course_audit.py` reconstructs the committed cell sources and fails when imported content or an explicit patch boundary drifts.
