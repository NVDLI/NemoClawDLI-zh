# Browser dependency vendoring

This workspace pins the JavaScript packages shipped to learner browsers. The generated files live
under `web/nemoclaw/vendor/`; Pages and launchable builds copy that directory without contacting a
package registry.

To propose an update, install exactly the committed lock, regenerate, inspect package and license
changes, then run the mutation-tested audit:

```bash
cd scripts/browser-vendor
npm ci
cd ../..
scripts/runtime/run_node.sh scripts/build/vendor_browser_dependencies.mjs
python3 scripts/validation/course_dependency_integrity.py --self-test
python3 scripts/validation/course_dependency_integrity.py
```

Run the install in the repository's disposable Node container when host Node.js is absent. Do not
hand-edit generated vendor files or the dependency inventory. Reviewers must inspect lock changes,
the dashboard, licenses, bundle size, and browser behavior before accepting an update.

The CodeMirror entrypoint is intentionally limited to CSS, HTML-mixed, JavaScript, Python, and XML.
Adding or replacing a mode changes the reviewed browser surface and must first update the allowlist
in `course_dependency_integrity.py`; the mutation suite rejects an unreviewed mode.
