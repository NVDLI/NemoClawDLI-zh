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

A `translate-<lang>` branch is **never merged into the source**. The build never reads the branch
directly either: instead each translation is **staged as content** under `i18n/<lang>/` (its `web/`
tree only), and `build_pages.sh` turns every `i18n/<lang>/` into `public/<lang>/`. One Pages site
then serves the source at the root and every language at `/<lang>/`; relative links resolve under the
subpath with no build-time base change. Staging from a branch (not pushing it) is deliberate: a raw
branch push carries this repo's deep history, whose old big blobs the production mirror rejects (a
5 MiB pre-receive limit). `git archive <branch> web` carries only the current `web/` tree, with no
history and no big files.

- On a **`translate-<lang>` branch**, CI derives the language from the branch name and runs **test**:
  the same structural gate as the source plus `validate_bundle --lang <code>` (English-prose suites
  marked not-applicable) and `translation_status.py --check` (the re-translate list, advisory). It
  does not deploy on its own.
- On the **source branch**, the **pages** job stages every `translate-*` branch into `i18n/<lang>/`
  (`git archive`), then runs `build_pages.sh`, which aggregates the source plus every staged language
  into one `public/` tree and deploys it.

So a contributor opens a merge request **into** `translate-pt` (not into the source); the pipeline
proves the translation is still structurally whole and shows what is left to sync.

## Publishing to the live site (the rsync-mirror production flow)

The production site (the `NemoClawDLIOS` Pages vendor on gitlab-master) is a single-branch mirror
that rebuilds Pages with `build_pages.sh` from content the publish step rsyncs in. The translation
reaches it the same way the source does, as filtered content: stage each language under `i18n/<lang>/`
before the rsync, and the mirror's `build_pages.sh` builds `/<lang>/` from it. No branch is ever
pushed to the mirror (its history would reject this repo's big blobs).

```bash
SRC="$HOME/s-fx-43-v1"        # source, branch nemoclaw-only

# 1. Stage each translation's web/ tree under i18n/<lang>/ (web only: no history, no big files).
git -C "$SRC" fetch origin
for lang in pt; do
  rm -rf "$SRC/i18n/$lang"; mkdir -p "$SRC/i18n/$lang"
  git -C "$SRC" archive "origin/translate-$lang" web | tar -x -C "$SRC/i18n/$lang"
done

# 2. Publish exactly as today. The rsync carries i18n/<lang>/ to the mirror (it strips nothing here:
#    web/ has no >5 MiB files), the mirror commits + pushes main, and its build_pages builds /<lang>/.
bash ~/publish-pages.sh "sync course source + translations"
```

`i18n/` is build staging, not source: leave it untracked on `nemoclaw-only` (do not commit it there),
and the rsync still carries it to the mirror, where it becomes the translation content the live site
serves at `/<lang>/`.

## Files here

- `translation_status.py` is the drift tool. It reports what changed upstream since the base, split
  into re-translate (prose) and merge-verbatim (code/asset/contract), with `--json`, `--check`,
  and `--set-base`.
- `translation_base.json` is the sync marker (lang, upstream, base commit).
- `SKILL.html` is the directory beacon: this process, machine-readable and interactive.
