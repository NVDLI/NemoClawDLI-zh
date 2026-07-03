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
| `dir-skill/1.0` | `schema` (node_type `directory-explorer`) | schema, node_type, source_dir, summary, title, explorer | `scripts/`, `docs/`, `workspace/` |
| hub | `node_type: hub` | node_type, children, and a label (`title` or `course`) | root, `web/`, `cpu/`, `web/nemoclaw/` |
| leaf | `node_type: leaf` | node_type, source_dir, summary, self_path, label | `web/nemoclaw/assets/`, `web/nemoclaw/mats/` |

Only schemas present in the repository are valid. Add a new kind to the implementation,
this table, and its mutation coverage in the same change that adds the first instance.
Do not reserve speculative schema names.

Hub beacons index immediate children. Per-directory detail stays in the child beacon.
The root `SKILL.html` is the ontology beacon for the whole repository; `web/SKILL.html`
and `cpu/SKILL.html` are surface hubs.

---

## Where docs live

| Doc | Path | Audience |
|---|---|---|
| Per-directory brain | `<dir>/SKILL.html` | both |
| Repo entry point | `AGENTS.md` | agents |
| Contract spec | `SKILL_CONTRACT.md` (this file) | agents |
| Course contract | `web/nemoclaw/SKILL.html` | both |
| Focused operating docs | `docs/` | contributors and operators |
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

## Durable guidance and scratch

Durable contributor guidance stays tracked and may appear in repository navigation:

- This contract spec and `AGENTS.md`
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
