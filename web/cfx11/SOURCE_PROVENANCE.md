# c-fx-11-v1 source provenance

This candidate projects the NVIDIA DLI course `c-fx-11-v1`, *Building LLM Applications With Prompt Engineering*, into a browser course. The source repository remains unchanged.

- Reviewed source: `nvidia/dli/content/c-fx-11-v1`, branch `main`
- Acquisition: authenticated GitLab archive download
- Archive SHA-256: `aa7c553909b90f3a140fc5154234f70ea86a9422be5c8cfcc0c3714796f6ff4f`
- Imported scope: `task1/dli`
- Imported content: 30 notebooks plus the images and learner data beneath that scope
- Excluded content: environment files, secrets, Docker and proxy configuration, assessment binaries, server runners, and notebook outputs
- Maintainer named by the source README: Josh Wyatt, NVIDIA

The source license is unresolved because the reviewed archive has no license file. Linked helper Python remains in the source repository and is not copied into this candidate. This candidate is suitable for internal branch staging and review. It must not enter an external release artifact until the course owner and OSRB confirm the applicable terms. The manifest does not infer Apache-2.0 from this repository's license.

`course.json` records the archive digest, every notebook digest, every cell source digest and byte length, and every copied support-file digest. `scripts/notebook-import/import_course.py` performs the import without formatting cell text. `scripts/validation/cfx11_course_audit.py` reconstructs the committed cell sources and fails when any recorded boundary drifts.
