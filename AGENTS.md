# AGENTS.md

Cross-harness entry point for this repository. Claude Code, Codex, Cursor, and any
other agent host start here. `AGENTS.md` is the portable convention; harness-native
files (a `CLAUDE.md`, a `.cursor/rules`) may point to it, but this is the canonical
agent contract.

## First move

1. Read [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) once per session for orientation.
2. For issue, MR, taxonomy, or broad prose work, read [`docs/agent_process.md`](docs/agent_process.md). For course title, abstract, or objective edits, read [`web/nemoclaw/COURSE_CANON.md`](web/nemoclaw/COURSE_CANON.md) first; that copy is immutable.
3. Open the `SKILL.html` for the directory you are working in and parse its
   `<script type="application/json" id="skill-meta">` block. That JSON is the brain:
   `web/nemoclaw/SKILL.html` for the course, `web/SKILL.html` for the bundle, the
   root `SKILL.html` for the whole repo.

The quickstart and the directives below are repo-level rules. The `skill-meta` block
is the working contract for the directory in front of you.

## Instruction precedence

When instructions conflict, follow this order, highest authority first:

1. Runtime and platform constraints from the agent host: sandbox mode, permission
   denials, tool availability. A denied action is final. Adapt, do not retry it verbatim.
2. This file (`AGENTS.md`) and any harness-native rules file that defers to it.
3. The directory brain: the `skill-meta` JSON in the relevant `SKILL.html`.
4. Task specs a directive or skill requires: [`SKILL_CONTRACT.md`](SKILL_CONTRACT.md),
   [`QUALITY_DIRECTIVES.md`](QUALITY_DIRECTIVES.md).
5. Orientation and creed: [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md),
   [`PHILOSOPHY.md`](PHILOSOPHY.md), [`README.md`](README.md). Read these first, but
   they orient rather than govern, so they do not override the levels above.

When two same-level sources disagree, prefer the more specific and more recently
maintained one, and state the assumption in your response.

## Ownership

Agent-assisted work is still engineering work. The agent drafts, searches, and runs
tools faster than a person can type. It does not own the result. Ownership stays with
whoever ships the change.

- A generated diff is input to judgment, not proof of quality. Treat generated code as
  code you do not trust yet.
- Read the whole diff. Keep only what serves the design. Delete plausible structure
  that earns nothing.
- Be able to explain every surviving line. A line you cannot account for does not ship.
- Prefer the deterministic gate over the prompt. When the same mistake keeps recurring,
  the durable fix is a check that makes it impossible (a validator rule, a type, a hook),
  not a sharper instruction. This repo already runs that way: `scripts/runtime/engine.js` is the
  one source of truth, the validators are the gates, and each `SKILL.html` carries the
  brain.
- Encode a constraint where a parser can catch it, so the space left for the model to be
  wrong in stays narrow.
- Validate before you claim. "Done" means the gate ran and passed, reported with its
  result, not asserted from memory.
