#!/usr/bin/env bash
# build_pages.sh assembles a static, fully client-side site into ./public/.
#
# Driven by .gitlab-ci.yml or .github/workflows/pages.yml, or run by hand.
# In GitLab staging, CI passes BUILD_PAGES_COURSE_PREFIX=web, so the course
# preview is written to public/web/nemoclaw. The CI job may mirror that output
# under public/<branch-slug>/ as a classic-Pages compatibility layer.
# Do not bake branch names into the bundle; relative links keep previews portable
# and avoid a preview artifact that can accidentally masquerade as production.
#
# What it produces (everything experienceable in a browser, no server logic):
#   public/index.html         landing page (the release picker, Pages-relative links)
#   public/nemoclaw/           the course, self-contained standalone bundle
#   public/engine.js           the link-graph + self-test engine (UMD, runs in-browser)
#   public/link-graph.html     the link-graph viewer (engine.js + embedded snapshot)
#   public/tests.html          client-side test runner (engine smoke + SKILL self-tests + CI gate)
#   public/validation.html     the CI gate report rendered from docs/validation/latest.json
#   public/gate.json           machine-readable gate summary (for tests.html)
#   public/branches.json       build-time branch preview manifest for the foyer dropdown
#   public/languages.json      build-time language manifest for the foyer dropdown
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
T1="$(cd "$HERE/../.." && pwd)"  # repo root (implementation lives under scripts/build)
OUT="${1:-$T1/public}"
# Build the source language at $OUT root, then each sparse same-branch overlay under i18n/<lang>/
# over canonical web/ and into $OUT/<lang>/. BUILD_PAGES_LANGS=0 disables that loop.
LANGS="${BUILD_PAGES_LANGS:-1}"
REUSE_VALIDATION="${BUILD_PAGES_REUSE_VALIDATION:-0}"
# Reusing a same-commit report requires the source tree to remain byte-for-byte at HEAD.
# Fresh local builds may still refresh material snapshots before regenerating validation.
if [ -n "${BUILD_PAGES_PULL_MATERIALS+x}" ]; then
    PULL_MATERIALS="$BUILD_PAGES_PULL_MATERIALS"
elif [ "$REUSE_VALIDATION" = "1" ]; then
    PULL_MATERIALS="0"
else
    PULL_MATERIALS="1"
fi
if [ "$REUSE_VALIDATION" = "1" ] && [ "$PULL_MATERIALS" != "0" ]; then
    echo "[build_pages]   ERROR: report reuse requires BUILD_PAGES_PULL_MATERIALS=0" >&2
    exit 1
fi
COURSE_PREFIX="${BUILD_PAGES_COURSE_PREFIX:-}"
COURSE_PREFIX="${COURSE_PREFIX#/}"; COURSE_PREFIX="${COURSE_PREFIX%/}"
SOURCE_MIRROR_PREFIX="${BUILD_PAGES_SOURCE_MIRROR_PREFIX:-}"
# If the course bundle is intentionally staged at web/nemoclaw, keep the read-only
# validator source mirror somewhere else so it cannot overwrite the runnable preview.
if [ -z "${BUILD_PAGES_SOURCE_MIRROR_PREFIX+x}" ] && [ "$COURSE_PREFIX" = "web" ]; then
    SOURCE_MIRROR_PREFIX="validated-source"
fi
SOURCE_MIRROR_PREFIX="${SOURCE_MIRROR_PREFIX#/}"; SOURCE_MIRROR_PREFIX="${SOURCE_MIRROR_PREFIX%/}"
case "$COURSE_PREFIX:$SOURCE_MIRROR_PREFIX" in
    *..*|*//*|*\*)
        echo "[build_pages]   ERROR: refusing unsafe path prefix: '$COURSE_PREFIX' / '$SOURCE_MIRROR_PREFIX'" >&2
        exit 1
        ;;
esac
echo "[build_pages] task1 root: $T1"
echo "[build_pages] output:     $OUT"
[ -n "$COURSE_PREFIX" ] && echo "[build_pages] course path: $COURSE_PREFIX/nemoclaw"
[ -n "$SOURCE_MIRROR_PREFIX" ] && echo "[build_pages] source mirror: $SOURCE_MIRROR_PREFIX/web/nemoclaw"
case "$OUT" in
    /|""|.)
        echo "[build_pages]   ERROR: refusing unsafe output path: '$OUT'" >&2
        exit 1
        ;;
esac
rm -rf "$OUT"; mkdir -p "$OUT"

# ── 0. Rebase materials to the web's ground truth (best-effort), then refresh the gate ──
# pull_materials.py never aborts: a per-source failure keeps the committed snapshot and records
# status=unreachable, so the build always completes and the failure shows up (loud) on the
# validator screen rather than breaking the deploy. Then re-run the gate so the report the build
# publishes reflects exactly what was just pulled. (Run locally too; it refreshes your mats/.)
if [ "$PULL_MATERIALS" = "0" ]; then
    echo "[build_pages] skipping live materials pull (BUILD_PAGES_PULL_MATERIALS=0); using committed snapshots"
else
    echo "[build_pages] rebasing materials from the web (best-effort; falls back to committed snapshots) ..."
    if python3 -c "import requests, bs4, markdownify" >/dev/null 2>&1; then
        python3 "$T1/scripts/materials/pull_materials.py" || echo "[build_pages]   pull reported issues; see the validator screen / _materials.json"
    else
        echo "[build_pages]   SKIP pull: vendoring deps (requests beautifulsoup4 markdownify lxml) not installed; using committed snapshots"
    fi
fi
# The published report must describe this exact tree. A prior required job may supply its
# same-commit report; reuse is fail-closed on schema, SHA, scope, required findings, and suite
# status. Direct/local builds regenerate by default.
if [ "$REUSE_VALIDATION" = "1" ]; then
    python3 "$T1/scripts/validation/validation_report_audit.py" \
        --report "$T1/docs/validation/latest.json" --expect-head
    echo "[build_pages] reusing same-commit validation report"
else
    python3 "$T1/scripts/validation/validate_bundle.py" --scope ship
fi

# ── 1. Courses: build the full self-hosted standalone straight into public/ ──
# --full gives the lab experience (dark theme, topbar + journey-map + nav, interactive panels)
# made self-contained: bundle_standalone.py inlines each page's CSS, ships _shared.js, carries
# the assets, and adds the off-lab key panel, so one call produces a complete course dir. (The
# default, no --full, is the light chrome-free iframe export for the edX navigator.) The bundle
# is generated from web/<course>/ on every build and is never committed (no intermediate).
for c in nemoclaw; do
    src="$T1/web/$c"
    if [ ! -d "$src" ] || [ ! -f "$T1/scripts/build/bundle_standalone.py" ]; then
        echo "[build_pages]   ERROR: need web/$c and scripts/build/bundle_standalone.py to build $c" >&2
        exit 1
    fi
    course_out="$OUT/${COURSE_PREFIX:+$COURSE_PREFIX/}$c"
    echo "[build_pages] bundling $c -> $course_out/ (full standalone) ..."
    python3 "$T1/scripts/build/bundle_standalone.py" --src "web/$c" --out "$course_out" --clean --full
    for required in \
        scripts/SKILL.html styles/SKILL.html styles/_style.css assets/SKILL.html mats/SKILL.html \
        dependencies.html vendor/browser-dependencies.json vendor/browser-sbom.cdx.json; do
        if [ ! -f "$course_out/$required" ]; then
            echo "[build_pages]   ERROR: bundled course is missing $c/$required" >&2
            exit 1
        fi
    done
    echo "[build_pages]   $c -> $course_out/ ($(find "$course_out" -name '*.html' | wc -l) pages)"
done

# ── 2. Link-graph viewer (engine.js runs client-side; offline = embedded snapshot) ──
cp "$T1/scripts/runtime/engine.js" "$OUT/engine.js"
cp "$T1/scripts/runtime/link_graph.html" "$OUT/link-graph.html"

# Favicon at the site root for the foyer + aux pages (the course carries its own under assets/).
cp "$T1/web/nemoclaw/assets/favicon.ico" "$OUT/favicon.ico"

# Ship the project license and the static third-party inventory at the artifact root. Course UI
# links resolve here, and downstream static-host distributions must carry both files. Preserve the
# runbook path referenced by the inventory without shipping generated SBOM bodies.
cp "$T1/LICENSE" "$OUT/LICENSE"
cp "$T1/THIRD_PARTY_LICENSES.md" "$OUT/THIRD_PARTY_LICENSES.md"
mkdir -p "$OUT/scripts/compliance/docs"
cp "$T1/scripts/compliance/docs/sbom_generation.md" "$OUT/scripts/compliance/docs/sbom_generation.md"

# ── 2b. SKILL explorers: the reusable framer + each explorer folder, source shipped
# as read-only assets so a student with a key can read AND ask about the real code on
# the live site without leaving the HTML space. Each folder's SKILL.html references the
# framer as ../web/_skill_explorer.js and its files as ./<file>, which resolve here too
# because the deploy mirrors that relative shape (public/web/_skill_explorer.js + public/<dir>/).
mkdir -p "$OUT/web"
cp "$T1/web/_skill_explorer.js" "$OUT/web/_skill_explorer.js"
for d in deploy scripts docs workspace; do
    if [ -d "$T1/$d" ]; then
        mkdir -p "$OUT/$d"
        # the explorer + the documented source it shows (read-only); skip caches + subdirs
        for f in "$T1/$d"/*.html "$T1/$d"/*.js "$T1/$d"/*.mjs "$T1/$d"/*.py \
                 "$T1/$d"/*.sh "$T1/$d"/*.md "$T1/$d"/*.txt "$T1/$d"/*.yml "$T1/$d"/*.yaml "$T1/$d"/*.conf "$T1/$d"/*.json "$T1/$d"/*.svg "$T1/$d"/Dockerfile; do
            [ -f "$f" ] && cp "$f" "$OUT/$d"/
        done
        if [ "$d" = "docs" ] && [ -d "$T1/docs/assets/repository-overview" ]; then
            mkdir -p "$OUT/docs/assets/repository-overview"
            cp "$T1"/docs/assets/repository-overview/* "$OUT/docs/assets/repository-overview"/
        fi
        if [ "$d" = "docs" ]; then
            for f in "$T1/docs"/*.pptx; do [ -f "$f" ] && cp "$f" "$OUT/docs"/; done
        fi
        echo "[build_pages] explorer $d -> public/$d/ ($(find "$OUT/$d" -maxdepth 1 -type f | wc -l) files, source shipped read-only)"
    fi
done

# Project every docs explorer declaration from source. Then inspect every declared Markdown
# document and project its local link/image targets. This checks the final Pages tree rather than
# assuming that a source-tree link remains valid after selective artifact assembly.
python3 "$T1/scripts/build/project_docs_explorer.py" \
    --source-skill "$T1/docs/SKILL.html" \
    --source-root "$T1" \
    --artifact-root "$OUT"

if [ -f "$T1/docs/repository-overview.slides.json" ]; then
    test -f "$OUT/docs/repository-overview.html"
    test -f "$OUT/docs/repository-overview.slides.json"
    test -f "$OUT/docs/assets/repository-overview/captures.json"
    if [ -f "$T1/docs/repository-overview.pptx" ]; then test -f "$OUT/docs/repository-overview.pptx"; fi
fi

# Project each shipped explorer's topbar nav to the Pages layout. In the lab/source tree the
# logo home is ../web/index.html and the up-breadcrumb is the root SKILL.html hub; neither path
# exists on Pages (the foyer is the site-root index.html and the root hub is a source-layout dev
# artifact that is not deployed). Point the logo at the foyer and drop the redundant up-link so
# the topbar has no dead targets on the live site.
for d in deploy scripts docs workspace; do
    f="$OUT/$d/SKILL.html"
    [ -f "$f" ] || continue
    python3 - "$f" <<'PROJ'
import sys, re, json
p = sys.argv[1]; s = open(p).read()
m = re.search(r'(<script[^>]*id="explorer-config"[^>]*>)(.*?)(</script>)', s, re.S)
if m:
    cfg = json.loads(m.group(2))
    nav = cfg.get("nav", {})
    nav["home"] = "../index.html"   # the foyer is the bundle front door on Pages
    nav.pop("up", None)             # no source-layout root hub on the live site
    cfg["nav"] = nav
    s = s[:m.start(2)] + json.dumps(cfg, indent=2) + s[m.end(2):]
    open(p, "w").write(s)
PROJ
done

# ── 2c. Validated course SOURCE, mirrored read-only at its repo-relative path ──
# The validation report names offenders by repo-relative path (e.g. web/nemoclaw/01a-loop.html)
# and previews the exact source the validator checked. The course itself deploys as the bundled
# standalone under public/nemoclaw/, which is TRANSFORMED, so the report would otherwise have no
# way to show what the validator actually saw. Mirror the source text files (no binary assets) to
# public/web/nemoclaw/ so those paths resolve. These are fetched as text by the report, never
# navigated to as pages, so the /lab/static and _shared.js references inside them do not matter.
if [ -d "$T1/web/nemoclaw" ]; then
    mirror_out="$OUT/${SOURCE_MIRROR_PREFIX:+$SOURCE_MIRROR_PREFIX/}"
    mkdir -p "$mirror_out"
    ( cd "$T1" && find web/nemoclaw -path 'web/nemoclaw/standalone' -prune -o -type f \
        \( -name '*.html' -o -name '*.md' -o -name '*.css' -o -name '*.js' -o -name '*.svg' -o -name '*.json' \) \
        -print0 | tar --null -cf - -T - ) | ( cd "$mirror_out" && tar -xf - )
    echo "[build_pages] validated source -> ${mirror_out%/}/web/nemoclaw/ ($(find "$mirror_out/web/nemoclaw" -type f | wc -l) text files, read-only for the report preview)"
fi

# ── 3. CI gate artifacts: the authoritative test results, surfaced statically ──
if [ -f "$T1/docs/validation/latest.json" ]; then
    cp "$T1/docs/validation/latest.json" "$OUT/gate.json"
else
    printf '{"note":"no gate report; run validate_bundle in CI"}\n' > "$OUT/gate.json"
fi
cat > "$OUT/validation.html" <<'HTML'
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link rel="icon" type="image/x-icon" href="favicon.ico"/>
<title>Validation gate &middot; review</title></head><body>
<div id="explorer"></div>
<script type="application/json" id="explorer-config">{"mode":"report","title":"Validation gate","nav":{"home":"index.html"}}</script>
<script src="web/_skill_explorer.js"></script>
</body></html>
HTML
echo "[build_pages] validation.html (framer report mode) written"

# ── 4. Landing page: the authoritative foyer (web/index.html), PROJECTED to Pages ──
# ONE source. web/index.html is the Jupyter/lab authoritative foyer and links repo files via
# /lab/static/ (resolved there by Jupyter extra_static_paths). For the standalone Pages site
# we strip that prefix to relative paths and inject the Pages-only tool links at the
# build:deploy-tools marker. The Pages site never points at /lab.
cp "$T1/web/index.html" "$OUT/index.html"
python3 - "$OUT/index.html" "$COURSE_PREFIX" <<'PROJ'
import sys, re
p, course_prefix = sys.argv[1], sys.argv[2].strip("/")
s = open(p).read().replace("/lab/static/", "")   # authoritative /lab/static -> Pages-relative
if course_prefix:
    s = s.replace('href="nemoclaw/', 'href="' + course_prefix + '/nemoclaw/')
    s = s.replace('"nemoclaw": "nemoclaw/', '"nemoclaw": "' + course_prefix + '/nemoclaw/')
tools = ('      <a href="validation.html">Validation report &rarr;</a>\n'
         '      <a href="tests.html">Test harness &rarr;</a>')
s = re.sub(r'<!-- build:deploy-tools[^>]*-->', tools, s)
open(p, "w").write(s)
PROJ

# ── 4b. Branch manifest for the foyer dropdown ──────────────────────────────
# Static Pages cannot discover Git refs at runtime. In a real checkout (CI or local
# dev), write the refs we can see; archive-only production-root rebuilds skip this
# and the outer Pages job writes the manifest after it adds the branch preview.
if git -C "$T1" rev-parse --git-dir >/dev/null 2>&1 && [ -f "$T1/scripts/build/build_branch_manifest.py" ]; then
    python3 "$T1/scripts/build/build_branch_manifest.py" --out "$OUT/branches.json" || echo "[build_pages] branch manifest skipped"
fi

# ── 5. Client-side test runner ──
# Three live, in-browser layers: an engine smoke test, the course SKILL self-test
# harnesses (which auto-run and badge themselves), and the CI gate summary.
cat > "$OUT/tests.html" <<'HTML'
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link rel="icon" type="image/x-icon" href="favicon.ico"/>
<title>Client-side test runner</title></head><body>
<div id="explorer"></div>
<script type="application/json" id="explorer-config">{"mode":"tests","title":"Test harness","nav":{"home":"index.html"}}</script>
<script src="engine.js"></script>
<script src="web/_skill_explorer.js"></script>
</body></html>
HTML

# ── 6. Translations: sparse same-branch overlays built into public/<lang>/ ──
# i18n/<lang>/ contains localized prose and locale metadata only. assemble_locale_overlay.py starts
# from canonical web/ and applies the declared locale files, so standalone runtime modules, styles,
# assets, machine-contract pages, and untranslated fallbacks cannot fork. The locale audit separately
# holds inline executable structure equivalent. The assembled tree is temporary build input.
if [ "$LANGS" = 1 ] && [ -d "$T1/i18n" ]; then
    for d in "$T1"/i18n/*/; do
        [ -f "${d}locale.json" ] || continue
        [ -f "${d}localization_state.json" ] || continue
        lang="$(basename "$d")"
        echo "[build_pages] language $lang -> $OUT/$lang/ (from i18n/$lang) ..."
        mkdir -p "$OUT/$lang"
        locale_tmp="$(mktemp -d)"
        if ! python3 "$T1/scripts/build/assemble_locale_overlay.py" --locale-root "i18n/$lang" --out "$locale_tmp"; then
            echo "[build_pages]   WARN: $lang overlay assembly failed; the other languages still ship"
            rm -rf "$locale_tmp"; continue
        fi
        if ! python3 "$T1/scripts/build/bundle_standalone.py" --src "$locale_tmp/web/nemoclaw" \
                --out "$OUT/$lang/nemoclaw" --clean --full; then
            echo "[build_pages]   WARN: $lang course build failed; the other languages still ship"
            rm -rf "$locale_tmp"; continue
        fi
        # the language foyer is its own translated web/index.html, /lab/static -> relative
        if [ -f "$locale_tmp/web/index.html" ]; then
            python3 - "$locale_tmp/web/index.html" "$OUT/$lang/index.html" <<'PROJ'
import sys, re
src, out = sys.argv[1], sys.argv[2]
s = open(src).read().replace("/lab/static/", "")
s = re.sub(r'<!-- build:deploy-tools[^>]*-->', '', s)   # the Pages-only tool links are root-only
open(out, "w").write(s)
PROJ
        fi
        fav="$locale_tmp/web/nemoclaw/assets/favicon.ico"; [ -f "$fav" ] || fav="$T1/web/nemoclaw/assets/favicon.ico"
        [ -f "$fav" ] && cp "$fav" "$OUT/$lang/favicon.ico" || true
        rm -rf "$locale_tmp"
    done
fi

# -- 7. Language manifest for the foyer dropdown -----------------------------
# Generate this after translations are built so the manifest lists only languages
# that actually exist in this artifact. The English URL follows COURSE_PREFIX;
# translation courses live under <lang>/nemoclaw/.
if [ -f "$T1/scripts/build/build_language_manifest.py" ]; then
    python3 "$T1/scripts/build/build_language_manifest.py" --out "$OUT/languages.json" --site-root "$OUT" --course-prefix "$COURSE_PREFIX" || echo "[build_pages] language manifest skipped"
fi

echo "[build_pages] done -> $OUT"
echo "[build_pages] preview locally: python3 -m http.server -d $OUT 8000"
