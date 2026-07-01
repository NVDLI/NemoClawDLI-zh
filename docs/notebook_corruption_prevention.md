# Notebook corruption: causes, detection, and prevention

Use this focused procedure when editing service documents under `cpu/`. General editing
and validation rules live in [`agent_process.md`](agent_process.md); containerized service
and page checks live in [`lab_runtime_testing.md`](lab_runtime_testing.md).

## Symptom

Authored `.md` files under `cpu/` (the shared service docs)
occasionally appear with:

- Multiple copies of the same content stacked end-to-end (perfectly
  periodic duplication).
- Doubled identifiers like `chatchat`, `thinkthink`, `promptprompt`.
- Interleaved model names like
  `nvidia/nemotron-nano-nvidia/nemotron-nano-12b-v2-vl2b-v2-vl`.
- Duplicate `<h1>` banners or duplicate `## **Part N:**` headers within
  one file.

## Root cause

The VS Code remote-server (the `code-server` running on the workspace
host) keeps an in-memory buffer for every open file. When an external
tool modifies the file on disk, its **external-change handler merges
the new disk content into the buffer in an append-style way** instead
of replacing the buffer. On the next save (auto-save or focus-loss),
the buffer dumps the combined content back to disk. Repeated edit
cycles compound: N edits → N copies in the file.

This is most visible during agentic edit passes where a single file
gets multiple `Edit`s in quick succession, but it can happen any time
the IDE has the file open while something else (script, agent, sync
tool) writes it.

## Defense in depth

Four layers, in order of where they catch the problem:

| Layer | Lives in | Catches |
| :--- | :--- | :--- |
| **L1: IDE doesn't auto-save** | `.vscode/settings.json` | the trigger event. With `files.autoSave: off`, the buffer doesn't dump unless the user explicitly saves. |
| **L2: External-change reload, not merge** | `.vscode/settings.json` `files.hotExit: off` plus markdown-specific formatting disabled | the merge step. When disk changes, the editor prompts/reloads rather than appending. |
| **L3: Post-edit audit** | `scripts/validation/nb_audit.py` | corruption already on disk. Fast structural scan that exits non-zero if any signal fires. Run after every edit. |
| **L4: Pre-commit hook** | `scripts/git-hooks/pre-commit` (linked to `.git/hooks/pre-commit`) | corruption from reaching the repo. Refuses to commit any staged course `.md` that fails the audit. |

L1 and L2 are workspace-scoped (every contributor opening this repo in
VS Code gets them automatically). L3 and L4 are repo-scoped and apply
to the authored `.md` files under `cpu/`.

## Usage

### Run the audit

    python3 scripts/validation/nb_audit.py            # exit 1 on real corruption
    python3 scripts/validation/nb_audit.py --strict   # also flag soft signals (repeated paragraphs)
    python3 scripts/validation/nb_audit.py PATH ...   # audit specific files

By default the audit auto-discovers every folder containing `.md`
files under `cpu/`. New material there is picked up with no script change.

The audit catches:

- **Multiple `<h1 style=` banners** in one file (legit files have one).
- **Duplicate `## **Part N:**` headers** within a file.
- **Doubled tokens** from a curated list of corruption-prone identifiers
  (`chat`, `think`, `prompt`, `reply`, `invoke`, `stream`, `content`,
  `client`, `model`, `llm`, `user`, `agent`, `session`, `context`, `tool`)
  regardless of length, plus any 4+-char token containing `_`, `-`,
  `/`, or `.`, plus any 5+-char plain token.
- **Adjacent `nvidia/nemotron-...` repeats** with only alphanumerics
  and hyphens between them (excludes legitimate Markdown links where
  the model name appears in both the link text and the URL).

### Install the pre-commit hook

    bash scripts/build/install-hooks.sh

The hook symlinks `.git/hooks/pre-commit` to the source in
`scripts/git-hooks/pre-commit`. Re-running the installer is
idempotent.

### Recover from existing corruption

Depending on the corruption shape:

1. **Periodic duplication (multiple identical copies stacked end-to-end).**
   Truncate to the first period:

       python3 - << 'PY'
       import re
       from pathlib import Path
       p = Path("cpu/<dir>/<file>.md")
       text = p.read_text()
       offs = [m.start() for m in re.finditer(r"^<h1 style=", text, re.M)]
       if len(offs) > 1:
           p.write_text(text[offs[0]:offs[1]])
       PY

2. **Periodic duplication where each period is itself corrupted**
   (e.g. doubled identifiers inside the first copy). The file is
   irrecoverable from in-place dedupe; rewrite from a canonical source
   (conversation history, mirror copy, or a known-good prior commit).

3. **Git history is not a safe fallback.** Some commits in this repo
   have captured corrupted state. Always re-run `nb_audit.py` on the
   restored content before committing.

## Why this is the right shape

- L1/L2 (IDE settings) prevent the race entirely for users with VS
  Code; agentic tools editing the files outside the IDE never trigger
  a merge.
- L3 (audit) is fast, deterministic, and runs after every edit so
  in-flight corruption is caught immediately rather than compounding.
- L4 (pre-commit) is the last-line gate: if L1/L2 are bypassed (a
  contributor with their own VS Code settings, or a different editor),
  L4 still stops corruption from reaching the repo.

The audit is intentionally narrow: it catches what we've actually seen
go wrong, with a tested allowlist for the known false positives
(Markdown links containing model names, the legitimate `-rw-rw-`
substring in file-permission output). If a new corruption shape
appears, extend `CORRUPTION_PRONE_IDS` or the relevant regex in
`scripts/validation/nb_audit.py` and add a synthetic test case alongside
the existing eight in the script's self-test.
