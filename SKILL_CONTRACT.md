# SKILL contract: the per-directory agent brain

`SKILL.html` is the single artifact an agent samples to work in a directory.
One file. Two readers.

- **Humans** read the prose, click the start button, browse the page or notebook table.
- **Agents** parse the `<script type="application/json" id="skill-meta">` block.

If both readers can do their job from this one file, the contract holds.

---

## Hard rules

```
SKILL.html lives in <dir>/SKILL.html              (dual-reader, ships to students)
skill-meta JSON is the AUTHORITATIVE machine contract
/tmp holds scratch/agent work (ephemeral, never committed); worth-keeping agent docs live in the repo by name
No SKILL.md anywhere; the JSON block replaces it.
No AUDIT.md beacons; audit findings go to /tmp or git history.
```

---

## skill-meta kinds (enforced by skill_contract.py)

A skill-meta classifies into exactly one kind, by its `schema` first and its `node_type`
second. `scripts/skills/skill_contract.py` checks that every beacon is a valid contract of its
kind: the required keys are present, the `schema` / `node_type` value is known, `version`
is semver where the kind carries one, and notebook `status` values are valid. It rides the
gate as the `skill_schema` and `skill_drift` suites and runs in CI; `--fix` repairs
mechanical drift. The kinds below are the de-facto contract, read off the shipped tree.

| Kind | Selector | Required keys | Used by |
|---|---|---|---|
| `service-skill/1.0` | `schema` | schema, service, address, source_dir, summary, interfaces, tests, title, version | `cpu/services/<svc>/` |
| `service-index/1.0` | `schema` | schema, id, source_dir, summary, services, tests, title, version | `cpu/services/` |
| `dir-skill/1.0` | `schema` (node_type `directory-explorer`) | schema, node_type, source_dir, summary, title, explorer | `scripts/`, `docs/`, `workspace/`, `cors-proxy/` |
| hub | `node_type: hub` | node_type, children, and a label (`title` or `course`) | root, `web/`, `cpu/`, `web/nemoclaw/` |
| leaf | `node_type: leaf` | node_type, source_dir, summary, self_path, label | `web/nemoclaw/assets/`, `web/nemoclaw/mats/` |

The two example schemas below (`course-skill/1.0`, `surface-skill/1.0`) are kept as the
reference shape for a notebook course and a notebook-surface hub. No directory in this
bundle currently uses them (the short course is web pages, not notebooks), but the tester
accepts them so a notebook course added later validates without a code change.

---

## skill-meta schema (course / directory)

```json
{
  "schema":         "course-skill/1.0",
  "course":         "Display Title",
  "id":             "folder_name",
  "version":        "1.2.0",
  "source_dir":     "cpu/services/llm_client/",
  "human_landing":  "cpu/services/llm_client/SKILL.html",

  "summary":        "One paragraph. Same as the hero blurb the student reads.",

  "notebook_count": 1,
  "notebooks": [
    {"file":"00_llm_client.md", "topic":"...", "section":"services", "status":"ready"}
  ],

  "services":       {"llm_client":"llm_client:9000"},
  "base_url":       "http://llm_client:9000/v1",
  "models": {
    "primary":   "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "judge":     "nvidia/nemotron-3-super-120b-a12b",
    "embedding": "nvidia/nv-embedqa-mistral-7b-v2"
  },

  "directives": [
    "Always route through http://llm_client:9000/v1. No api.nvidia.com calls.",
    "Temperature 0.3 default (0 only when the lesson teaches determinism).",
    "directory-specific rule N"
  ],

  "known_issues": [
    {"id":"folder-01","note":"...", "fix_ref":"commit sha"}
  ],

  "success_criteria": {
    "all_notebooks_pass_or_soft": true,
    "ci_status_required":         "passing|unstable"
  },

  "do_not_propagate": ["SKILL.md","AUDIT.md","*.audit.md","blog_*.md"]
}
```

`status` values: `ready` (clean), `setup` (needs prep cell),
`wip` (don't ship), `ref` (reference-only).

---

## skill-meta schema (surface hub)

A surface hub indexes the directories under it. `web/SKILL.html` indexes the web
surface; `cpu/SKILL.html` indexes the services. The hub carries:

```json
{
  "schema":      "surface-skill/1.0",
  "surface":     "web",
  "version":     "1.x.x",
  "audit_date":  "YYYY-MM-DD",
  "entries": [{"id":"nemoclaw","skill_html":"nemoclaw/SKILL.html","notebook_count":0}],
  "services":    {"llm_client":"llm_client:9000", ...}
}
```

Per-directory detail does NOT live in the hub. Only the index.

The root `SKILL.html` is the ontology beacon for the whole repo: it documents
every immediate child (web, cpu, repos, scripts, workspace, docs) so an
agent can orient from one file. The mats reference layer is course-scoped under
`web/nemoclaw/mats/`, documented as part of the course.

---

## Where docs live

| Doc | Path | Audience |
|---|---|---|
| Per-directory brain | `<dir>/SKILL.html` | both |
| Repo entry point | `AGENT_QUICKSTART.md` | agents |
| Contract spec | `SKILL_CONTRACT.md` (this file) | agents |
| Quality directives | `QUALITY_DIRECTIVES.md` | agents |
| Scratch | `/tmp` (ephemeral) | agents |

---

## Updating a SKILL.html

```
1. open <dir>/SKILL.html
2. update skill-meta JSON   → page/notebook list, models, directives
3. update human prose       → hero, tables, callouts
4. one file                 → the agent block stays in sync with the prose
```

Every change to a page or notebook in `<dir>/` MUST be reflected in the
SKILL.html of that directory in the same commit. If the page or notebook count
changed, the JSON count changes. If a model swapped, the `models` block changes.
The SKILL.html is the source of truth. Staleness in this file is a CI failure.

---

## What is agent-only (kept in the repo by name; scratch in /tmp)

Anything the student must never see, kept worth-keeping in the repo by plain name:

- This contract spec, AGENT_QUICKSTART, QUALITY_DIRECTIVES
- The reference docs under `docs/`

Throwaway audits, reruns, and one-shot scripts go to `/tmp` and are never
committed. Git history is the archive.

---

## Anti-patterns (corruption markers)

These are signs the directory was edited by a previous agent that lost the plot:

| Marker | Why it's corruption | Fix |
|---|---|---|
| Apologetic prose | "Sorry, this is just a simplified..." treats the student as second-class | Cut the apology, keep the content |
| Stray em-dashes | the long-dash character used as filler between unrelated clauses | Restructure the sentence |
| Over-documentation | 12-line preamble explaining what one obvious cell does | Delete the preamble |
| Hedge phrases | "we'll briefly", "in this small example", "this isn't the real" | State what it IS, not what it's not |
| Phantom xrefs | "See section 5e" where section 5e doesn't exist | Answer in place or delete the deferral |
| Dead deferral | "we revisit this later" with no later | Same fix |
| Stale SKILL.md | A SKILL.md file in any directory | Delete; the skill-meta JSON replaces it |

If a sweep finds any of these, fix the affected SKILL.html or notebook directly.

---

## Prose: put the concrete first

When you write narrative (a hero blurb, a callout, a doc), lead with the concrete (what
runs, the actual decision, the number) and let the point come at the end, derived from it.
A thesis stated up front and then justified reads as marketing, because the claim arrives
before the evidence that would earn it. This shares a root with the hedge-phrase and
em-dash markers above: a sentence built from its own specifics rarely needs a dash or a
hedge to prop a claim up.

## Assume it is AI-generated

Treat any prose in this repo as AI-generated until you have read it against the markers
above. A fresh draft, a vendored import, the guidance docs, and the text you wrote a
minute ago all qualify. Read it against the markers before you trust it, including this
file.
