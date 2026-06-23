# Language branches: how a translation is built and kept in sync

A translation of this course is a long-lived git branch named `translate-<lang>` (the first is
`translate-pt`, Portuguese). The branch is a full **overlay** of the source branch: the same files
in the same places, with the human-facing prose rendered in the target language and everything else
carried over unchanged. Because the structure is identical, every build, gate, and deploy that runs
on the source branch runs on a translation branch too. A translation is never a fork of the code or
the machine contracts; it is the same course, spoken in another language.

This folder holds the utilities that make that overlay maintainable. The hard part is not the first
pass, it is staying in step as the source moves: when a page is fixed on `main`, the translation
needs to know exactly what changed so it can re-translate only the delta.

## What gets translated, and what does not

| Class | What | Rule |
|---|---|---|
| **Translate** | The prose the reader sees: `web/` course pages, the foyer, the slides, the `mats/` companions, and the human text of the `web/` SKILL hubs. | Render it in the target language. |
| **Verbatim** | Code (`*.js`, `*.py`, `*.css`), data and assets (`*.json`, `*.svg`, images), and the agent/dev docs (`CLAUDE.md`, `AGENT_QUICKSTART.md`, the service SKILL beacons). | Merge from the source unchanged. Never fork it. |

One special case: a `web/` `SKILL.html` is prose-bearing, so its human text is translated, **but its
`<script id="skill-meta">` JSON block is a machine contract and stays byte-identical to the source.**
Translate the words around it, not the contract inside it.

`translation_status.py` encodes this split (`classify()`), so the sync report tells you which changed
files to re-translate and which to merge as-is.

## The sync marker

`translation_base.json` is the whole abstraction. It records the source commit this translation
currently reflects (the **base**). On the source branch `lang` is `null`: there is nothing to keep in
sync. On a `translate-<lang>` branch it carries:

```json
{ "lang": "pt", "upstream": "main", "base_sha": "<source commit this translation reflects>" }
```

`upstream` is the canonical content branch the translation tracks: `main` in the standalone
open-source release, or `nemoclaw-only` when the course is served from the shared `s-fx-43-v1` bundle.

The drift you need to act on is `git diff base_sha..upstream`, classified per file. That is exactly
what `translation_status.py` reports.

## The workflow

```bash
# 1. Create the language branch off the current source tip.
git checkout main && git pull
git checkout -b translate-pt

# 2. Point the marker at this language and pin the base to where you started.
#    (edit translation_base.json: "lang": "pt", "upstream": "main")
python3 scripts/translate/translation_status.py --set-base origin/main

# 3. Translate the reader-facing prose (web/ pages, slides, mats, web SKILL prose).
#    Leave code, assets, and every skill-meta JSON block exactly as the source has them.

# 4. Validate exactly like any branch. --lang skips the English-prose style suites
#    (rhythm, buzz, branding, em-dash) that would false-positive on correct Portuguese;
#    the structural suites (links, layout, SKILL contract, modules, figures, cells) still gate.
python3 scripts/validate_bundle.py --scope ship --lang pt

# 5. Later, when the source has moved, see what to update and re-translate just the delta.
python3 scripts/translate/translation_status.py
#    ... translate the TO RE-TRANSLATE list, merge the TO MERGE VERBATIM list ...
python3 scripts/translate/translation_status.py --set-base origin/main   # advance the base
```

Step 5 is the loop a translation lives in. Run the status, act on the delta, advance the base.

## CI/CD on a `translate-` branch

A `translate-<lang>` branch is **never merged into the source**. It lives on its own, and its
material reaches the live site because the **source build aggregates every language into one Pages
site**: `build_pages.sh` builds the source language at the site root and each `translate-<lang>`
branch it can see (a throwaway git worktree of the branch) into `public/<lang>/`. The site's links
are relative, so a language served at `/<lang>/` resolves correctly with no build-time base change.

- On a **`translate-<lang>` branch**, CI derives the language from the branch name (`translate-pt`
  to `pt`) and runs **test**: the same structural gate as the source plus `validate_bundle --lang
  <code>` (English-prose suites marked not-applicable) and `translation_status.py --check` (the
  re-translate list, advisory, so drift never blocks). It does not deploy on its own.
- On the **source branch**, the **pages** job runs `build_pages.sh`, which aggregates the source
  language plus every `translate-*` branch into one `public/` tree and deploys it.

So a contributor opens a merge request **into** `translate-pt` (not into the source), the pipeline
proves the translation is still structurally whole and shows what is left to sync. The translation
goes live the next time the source build runs and picks the branch up (see the publish recipe below).

## Publishing to the live site (the rsync-mirror production flow)

The production site (the `NemoClawDLIOS` Pages vendor on gitlab-master) is a single-branch mirror
that rebuilds Pages with `build_pages.sh`. For it to serve a language, two things must hold: the
mirror's `build_pages.sh` is this language-aware one (it already fetches `translate-*` from its
`origin` before building), and each `translate-<lang>` branch lives on the mirror's remote so the
build can see it.

One-time setup: give the source repo a remote that points at the mirror.

```bash
SRC="$HOME/s-fx-43-v1"        # source, branch nemoclaw-only
DST="$HOME/NemoClawDLIOS"     # Pages vendor, branch main
git -C "$SRC" remote add mirror "$(git -C "$DST" remote get-url origin)" 2>/dev/null || true
```

Then, to publish (source plus every language):

```bash
# 1. Publish the source language exactly as today (rsync nemoclaw-only -> DST main, commit, push).
~/publish-pages.sh "sync course source"

# 2. Push each language branch to the mirror so its build_pages can build it.
for lang in pt; do
  git -C "$SRC" push mirror "translate-$lang"
done

# 3. Trigger the mirror's pages pipeline so build_pages re-aggregates the source plus every
#    translate-* branch now on the mirror (an empty commit on main is the simplest trigger).
git -C "$DST" commit --allow-empty -m "rebuild Pages: pick up translations" && git -C "$DST" push
```

The mirror's pipeline then rebuilds Pages with the source at the root and each language at
`/<lang>/`. The translation branch is never merged; pushing it to the mirror plus a source rebuild
is what integrates it.

## Files here

- `translation_status.py` is the drift tool. It reports what changed upstream since the base, split
  into re-translate (prose) and merge-verbatim (code/asset/contract), with `--json`, `--check`,
  and `--set-base`.
- `translation_base.json` is the sync marker (lang, upstream, base commit).
- `SKILL.html` is the directory beacon: this process, machine-readable and interactive.
