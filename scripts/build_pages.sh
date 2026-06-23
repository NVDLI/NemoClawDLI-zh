#!/usr/bin/env bash
# build_pages.sh assembles a static, fully client-side site into ./public/.
#
# Driven by .gitlab-ci.yml or .github/workflows/pages.yml, or run by hand.
#
# What it produces (everything experienceable in a browser, no server logic):
#   public/index.html         landing page (the release picker, Pages-relative links)
#   public/nemoclaw/           the course, self-contained standalone bundle
#   public/engine.js           the link-graph + self-test engine (UMD, runs in-browser)
#   public/link-graph.html     the link-graph viewer (engine.js + embedded snapshot)
#   public/tests.html          client-side test runner (engine smoke + SKILL self-tests + CI gate)
#   public/validation.html     the CI gate report rendered from docs/validation/latest.json
#   public/gate.json           machine-readable gate summary (for tests.html)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
T1="$(dirname "$HERE")"            # task1 root (scripts/ is directly under it)
OUT="${1:-$T1/public}"
# Build the source language at $OUT root, then each translate-<lang> branch into $OUT/<lang>/ so one
# Pages site serves every language. BUILD_PAGES_LANGS=0 disables that loop; it is set on the
# recursive per-language build so a language build never tries to build languages of its own.
LANGS="${BUILD_PAGES_LANGS:-1}"

echo "[build_pages] task1 root: $T1"
echo "[build_pages] output:     $OUT"
rm -rf "$OUT"; mkdir -p "$OUT"

# ── 0. Rebase materials to the web's ground truth (best-effort), then refresh the gate ──
# pull_materials.py never aborts: a per-source failure keeps the committed snapshot and records
# status=unreachable, so the build always completes and the failure shows up (loud) on the
# validator screen rather than breaking the deploy. Then re-run the gate so the report the build
# publishes reflects exactly what was just pulled. (Run locally too; it refreshes your mats/.)
echo "[build_pages] rebasing materials from the web (best-effort; falls back to committed snapshots) ..."
if python3 -c "import requests, bs4, markdownify" >/dev/null 2>&1; then
    python3 "$T1/scripts/pull_materials.py" || echo "[build_pages]   pull reported issues; see the validator screen / _materials.json"
else
    echo "[build_pages]   SKIP pull: vendoring deps (requests beautifulsoup4 markdownify lxml) not installed; using committed snapshots"
fi
python3 "$T1/scripts/validate_bundle.py" --scope ship >/dev/null 2>&1 || true   # refresh docs/validation/latest.json post-pull

# ── 1. Courses: build the full self-hosted standalone straight into public/ ──
# --full gives the lab experience (dark theme, topbar + journey-map + nav, interactive panels)
# made self-contained: bundle_standalone.py inlines each page's CSS, ships _shared.js, carries
# the assets, and adds the off-lab key panel, so one call produces a complete course dir. (The
# default, no --full, is the light chrome-free iframe export for the edX navigator.) The bundle
# is generated from web/<course>/ on every build and is never committed (no intermediate).
for c in nemoclaw; do
    src="$T1/web/$c"
    if [ ! -d "$src" ] || [ ! -f "$T1/scripts/bundle_standalone.py" ]; then
        echo "[build_pages]   ERROR: need web/$c and scripts/bundle_standalone.py to build $c" >&2
        exit 1
    fi
    echo "[build_pages] bundling $c -> public/$c/ (full standalone) ..."
    python3 "$T1/scripts/bundle_standalone.py" --src "web/$c" --out "$OUT/$c" --clean --full
    echo "[build_pages]   $c -> public/$c/ ($(find "$OUT/$c" -name '*.html' | wc -l) pages)"
done

# ── 2. Link-graph viewer (engine.js runs client-side; offline = embedded snapshot) ──
cp "$T1/scripts/engine.js" "$OUT/engine.js"
cp "$T1/scripts/link_graph.html" "$OUT/link-graph.html"

# Favicon at the site root for the foyer + aux pages (the course carries its own under assets/).
cp "$T1/web/nemoclaw/assets/favicon.ico" "$OUT/favicon.ico"

# ── 2b. SKILL explorers: the reusable framer + each explorer folder, source shipped
# as read-only assets so a student with a key can read AND ask about the real code on
# the live site without leaving the HTML space. Each folder's SKILL.html references the
# framer as ../web/_skill_explorer.js and its files as ./<file>, which resolve here too
# because the deploy mirrors that relative shape (public/web/_skill_explorer.js + public/<dir>/).
mkdir -p "$OUT/web"
cp "$T1/web/_skill_explorer.js" "$OUT/web/_skill_explorer.js"
for d in cors-proxy scripts docs workspace; do
    if [ -d "$T1/$d" ]; then
        mkdir -p "$OUT/$d"
        # the explorer + the documented source it shows (read-only); skip caches + subdirs
        for f in "$T1/$d"/*.html "$T1/$d"/*.js "$T1/$d"/*.mjs "$T1/$d"/*.py \
                 "$T1/$d"/*.sh "$T1/$d"/*.md "$T1/$d"/*.txt "$T1/$d"/Dockerfile; do
            [ -f "$f" ] && cp "$f" "$OUT/$d"/
        done
        echo "[build_pages] explorer $d -> public/$d/ ($(find "$OUT/$d" -maxdepth 1 -type f | wc -l) files, source shipped read-only)"
    fi
done

# Project each shipped explorer's topbar nav to the Pages layout. In the lab/source tree the
# logo home is ../web/index.html and the up-breadcrumb is the root SKILL.html hub; neither path
# exists on Pages (the foyer is the site-root index.html and the root hub is a source-layout dev
# artifact that is not deployed). Point the logo at the foyer and drop the redundant up-link so
# the topbar has no dead targets on the live site.
for d in cors-proxy scripts docs workspace; do
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
    ( cd "$T1" && find web/nemoclaw -type f \
        \( -name '*.html' -o -name '*.md' -o -name '*.css' -o -name '*.js' -o -name '*.svg' -o -name '*.json' \) -print0 \
      | tar --null -cf - -T - ) | ( cd "$OUT" && tar -xf - )
    echo "[build_pages] validated source -> public/web/nemoclaw/ ($(find "$OUT/web/nemoclaw" -type f | wc -l) text files, read-only for the report preview)"
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
python3 - "$OUT/index.html" <<'PROJ'
import sys, re
p = sys.argv[1]; s = open(p).read()
s = s.replace("/lab/static/", "")   # authoritative /lab/static -> Pages-relative
tools = ('      <a href="validation.html">Validation report &rarr;</a>\n'
         '      <a href="tests.html">Test harness &rarr;</a>')
s = re.sub(r'<!-- build:deploy-tools[^>]*-->', tools, s)
open(p, "w").write(s)
PROJ

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

# ── 6. Translations: each translate-<lang> branch built into public/<lang>/ ──
# A translation is a never-merged overlay branch with identical structure, so it builds with this
# same script from a throwaway worktree of the branch, into $OUT/<lang>/. One Pages site then serves
# the source at root and every language at /<lang>/, with relative links resolving under the subpath.
# This is how a translation reaches the rsync-mirror production site (NemoClawDLIOS): publish pushes
# the translate-* branches to that remote, and this loop builds each one it can see.
if [ "$LANGS" = 1 ] && git -C "$T1" rev-parse --git-dir >/dev/null 2>&1; then
    # CI checks out only the branch being built, so fetch the language branches into remote-tracking
    # refs first (best-effort: offline / a local checkout that already has them is fine).
    git -C "$T1" fetch origin '+refs/heads/translate-*:refs/remotes/origin/translate-*' --quiet 2>/dev/null || true
    refs="$(git -C "$T1" for-each-ref --format='%(refname:short)' \
            'refs/heads/translate-*' 'refs/remotes/*/translate-*' 2>/dev/null \
            | sed 's#^.*/##' | sort -u)"
    for br in $refs; do
        lang="${br#translate-}"
        [ -n "$lang" ] || continue
        wt="$(mktemp -d)"
        if git -C "$T1" worktree add -q --detach "$wt" "$br" 2>/dev/null \
           || git -C "$T1" worktree add -q --detach "$wt" "origin/$br" 2>/dev/null; then
            echo "[build_pages] language $lang -> $OUT/$lang/ (from branch $br) ..."
            BUILD_PAGES_LANGS=0 bash "$wt/scripts/build_pages.sh" "$OUT/$lang" \
                || echo "[build_pages]   WARN: $lang build failed; the other languages still ship"
            git -C "$T1" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
        else
            echo "[build_pages]   WARN: cannot check out $br; skipping $lang"; rm -rf "$wt"
        fi
    done
fi

echo "[build_pages] done -> $OUT"
echo "[build_pages] preview locally: python3 -m http.server -d $OUT 8000"
