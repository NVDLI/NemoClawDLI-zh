# Validation Remediation Guide

Snapshot: `validate_bundle [af75cd0] --scope ship`, generated 2026-06-25.

Current gate state: PASS for ship. Remaining work is advisory, but `recommended` means a known defect, not polish.

- Required: 0
- Recommended: 212
- Consider: 891
- Main generated report: `docs/validation/latest.md`
- Machine report: `docs/validation/latest.json`

## How To Use This

Use this guide for planning and review. Use `docs/validation/latest.md` for exact row-by-row findings.

Do not fix findings by hiding the surface from the validator. A good patch should make the learner-facing text or interface better, and then the validator should agree.

Avoid these patterns:

- Do not replace every color with `var(--g)`.
- Do not turn prose into stub lists just to break a paragraph run.
- Do not delete comments that explain a real safety or runtime constraint.
- Do not mass-reflow code across service files unless tests cover the touched path.
- Do not use semicolon-separated sentence stubs as a prose escape hatch.

## Triage Order

1. Fix recommended color-theme findings as one visual-surface pass.
2. Fix recommended prose findings page by page, with human review of narrative quality.
3. Use the mechanical comment fixer for a scoped subset of code comments.
4. Treat duplicate code, file size, and service refactors as separate engineering MRs.
5. Leave `consider` prose findings alone unless the sentence is genuinely worse for learners.

## Recommended Findings

### Color Theme: 199

Most remaining recommended findings are hard-coded SVG colors. Top affected files:

| Path | Count | Recommended approach |
|---|---:|---|
| `web/nemoclaw/assets/figures/fig2_react.svg` | 93 | Convert legacy fills/strokes to semantic `--gfx-*` variables. |
| `web/nemoclaw/assets/figures/fig2_rewoo.svg` | 57 | Same as above. Keep ReWOO/ReAct colors parallel. |
| `web/nemoclaw/assets/figures/rag_arch_2021.svg` | 44 | Convert by role: text, borders, panels, highlights, arrows. |
| `web/nemoclaw/scripts/_figures.js` | 3 | Fix generator literals so future figures inherit theme colors. |
| `web/nemoclaw/scripts/_canvas.js` | 1 | Replace dynamic SVG fill literal with a theme variable. |
| `web/nemoclaw/scripts/_viz.js` | 1 | Replace dynamic SVG fill literal with a theme variable. |

Recommended color mapping:

| Old color | Likely role | Replacement candidate |
|---|---|---|
| `#76b900` | NVIDIA green accent | `var(--gfx-green, var(--g))` |
| `#32ee5a` | bright green highlight | `var(--gfx-green, var(--g))` or a defined tint if it is a fill area |
| `#3b82f6`, `#2f528f` | blue actor/tool lane | `var(--gfx-blue, var(--acc))` |
| `#00d9f0` | teal/data lane | `var(--gfx-teal, var(--acc))` |
| `#ffff00` | warning/highlight | `var(--gfx-amber, var(--warn))` |
| `#595959`, `#7f7f7f`, `#adb9ca` | subdued text or secondary shapes | `var(--gfx-sub, var(--td))` or `var(--gfx-faint, var(--tf))` |
| `#e7e6e6` | light panel or line | `var(--gfx-line, var(--bd))` or `var(--gfx-panel, var(--e1))` |

Sample static SVG fix:

```svg
<!-- Before -->
<rect fill="#2f528f" stroke="#595959"/>
<text fill="#7f7f7f">tool call</text>

<!-- After -->
<rect fill="var(--gfx-blue,var(--acc))" stroke="var(--gfx-sub,var(--td))"/>
<text fill="var(--gfx-sub,var(--td))">tool call</text>
```

Sample generated SVG fix:

```js
// Before
path.setAttribute("fill", "#76b900");

// After
path.setAttribute("fill", "var(--gfx-green,var(--g))");
```

Validation for this pass:

```bash
python3 scripts/validation/color_theme.py
python3 scripts/validation/figure_audit.py
python3 scripts/validation/validate_bundle.py --no-write --scope ship
```

Check the rendered figures in light and dark mode. Color replacement can pass the static validator while making labels low contrast.

### Prose: Grammar And Composition: 6

Affected paths:

- `web/nemoclaw/01b-react.html`: 4
- `web/nemoclaw/03a-kickstart.html`: 1
- `web/nemoclaw/04a-safety.html`: 1

Recommended approach: rewrite the sentence, not just the token. The current problems are filler, weak openers, an expletive opener, one run-on, and two comma-welded step chains.

Sample fixes:

```text
Before:
This issue actually becomes more likely as the context grows due in part to a larger phenomena known as context rot.

After:
The risk grows with context size. Context rot is the broader pattern: contradictions, stale observations, and weak conventions accumulate until the model has to sort too much history before acting.
```

```text
Before:
The cookie is HttpOnly and scoped to the launchable origin, so the browser attaches it but the launchable sends no CORS header for this page, and you never see the response.

After:
The cookie is HttpOnly and scoped to the launchable origin. The browser attaches it. The launchable does not send a CORS header for this page, so JavaScript cannot read the response.
```

```text
Before:
From here the page computes from your box's policy rather than from a baked example, and the cell keeps the code in a dropdown, so you can inspect the exact call without making it the main lesson.

After:
From here, the page computes from your box's policy rather than from a baked example. The code stays collapsed, but you can open it to inspect the exact call.
```

### Prose: Buzz Cadence: 3

Affected paths:

- `web/nemoclaw/02a-routing.html`: 1
- `web/nemoclaw/01a-loop.html`: 2 canvas text findings

Recommended approach: remove mirrored constructions and stubby instruction chains. Keep the teaching point concrete.

Sample fixes:

```text
Before:
This notebook will not dig too deep into the many options, but they should be understood and we will motivate some surface-level support mechanisms to tackle some more advanced problems.

After:
This notebook samples the main routing options and focuses on the support mechanisms used later in the course.
```

```text
Before:
If you expand it, look for the recursive dfs(pos) function: it pushes a move when it enters a branch and pushes the reverse move when it backs out.

After:
Expand the node and inspect `dfs(pos)`. The function records a move when it enters a branch. During backtracking, it records the reverse move.
```

```text
Before:
The run node is open by default because it is the part to edit: change DIRECTIVE, then adjust model, advanced, includeText, includeImage, includeHistory, includeCoords, or toolSpecInSystem one at a time.

After:
The run node stays open because it is the editable part. Change `DIRECTIVE` first. Then adjust one setting at a time: model, advanced options, inputs, history, coordinates, or tool-spec placement.
```

### Prose: Structural Rhythm: 3

Affected paths:

- `web/nemoclaw/01a-loop.html`: paragraph run
- `web/nemoclaw/01b-react.html`: list pileup
- `web/nemoclaw/03a-kickstart.html`: paragraph run

Recommended approach: add real structure only where the page needs it. Do not insert decorative lists or callouts. If a paragraph run explains a sequence, convert the sequence into steps. If two lists are adjacent, merge them or add a real connective paragraph.

Sample fix for a paragraph run:

```html
<p>Classic agent designs mainly change the decision step.</p>
<ul>
  <li>A reflex rule chooses directly from the current observation.</li>
  <li>A model-based agent keeps enough state to interpret the next observation.</li>
  <li>A goal-based agent chooses actions by checking them against a target.</li>
  <li>A learning agent updates its behavior after feedback.</li>
</ul>
<p>The labs start with rigid logic, then add model calls, context, and loops.</p>
```

Sample fix for list pileup:

```text
Before:
[list]
One short bridge sentence.
[list]

After:
Use one list if both lists answer the same question. If the second list changes the question, add a paragraph that says what changed and why the learner should now look at the second set.
```

### Prose: Bare Assertions: 1

Affected path: `web/nemoclaw/01a-loop.html`.

Recommended approach: merge the definition into the explanation that follows. Keep at most one bare definition per section.

Sample fix:

```text
Before:
The decision step is where the classic agent designs differ.

After:
Classic agent designs mainly differ in how they choose the next action: a fixed rule, a remembered world state, a goal test, or feedback from prior attempts.
```

## Consider Findings

`consider` findings are not all defects. Use them to find clusters. Fix only when the change improves maintainability or learner comprehension.

### Code Comments: 337

By kind:

- `comment-midsentence-wrap`: 208
- `comment-block-too-long`: 109
- `comment-colon-no-list`: 14
- `inline-comment-too-long`: 6

Recommended approach:

1. Run dry-run first.
2. Apply the safe fixer on one file or one subsystem.
3. Review the diff manually.
4. Run `code_hygiene.py` and the relevant unit/runtime check.

Commands:

```bash
python3 scripts/validation/fix_comment_hygiene.py --file web/nemoclaw/scripts/_canvas.js
python3 scripts/validation/fix_comment_hygiene.py --apply --file web/nemoclaw/scripts/_canvas.js
python3 scripts/validation/code_hygiene.py
```

Human-only examples:

```js
// Before: long explanation that names every branch and repeats the code below.
// After: State only why the branch exists. Let names and code carry the what.
```

### Code Duplication: 210

By kind:

- `duplicate-block`: 208
- `duplicate-interface`: 2

Recommended approach: do not deduplicate course cells just because a detector found mirrored teaching code. Deduplicate service code when both sites share runtime behavior and tests cover the helper.

Good candidates:

- repeated helper blocks in `cpu/services/llm_client/llm_client.py`
- repeated fixture setup in `cpu/services/llm_client/tests/conftest.py`
- repeated service URL wiring in `cpu/services/docker_router/docker_router.py`

Sample service refactor:

```python
# Before
payload = {"model": model, "messages": messages, "stream": stream}
headers = {"content-type": "application/json"}

# After
def build_chat_payload(model, messages, *, stream=False):
    return {"model": model, "messages": messages, "stream": stream}
```

Only extract after checking both call sites use the same defaults and error behavior.

### Code Walls: 133

By kind:

- `code-wall`: 130
- related large-cell pressure: see file-size findings

Recommended approach: add blank lines at logical seams for low-risk files. For generated HTML or SKILL examples, preserve runnable snippets and avoid breaking copy-paste behavior.

Sample fix:

```js
const response = await fetch(url, opts);
const data = await response.json();

if (!response.ok) {
  throw new Error(data.error || response.statusText);
}
```

### Hard-Coded Constants: 89

By kind:

- `embedded-url`: 79
- `repeated-literal`: 10

Recommended approach: name constants where the runtime can safely share one source of truth. Do not move learner-visible example URLs into hidden config if the point of the lesson is to show the endpoint.

Sample fix:

```python
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://llm_client:9000/v1")
```

Use config only where deployment actually supports override. Otherwise prefer a named module constant.

### File Size And Density: 20

By kind:

- `cell-too-large`: 14
- `file-too-large`: 4
- `over-documented`: 2

Recommended approach: split only along stable seams.

Likely seams:

- `cpu/services/llm_client/llm_client.py`: providers, request normalization, streaming, embeddings, reranking, app routes.
- `web/nemoclaw/scripts/_canvas.js`: layout engine, cell controls, execution state, rendering helpers.
- `web/nemoclaw/scripts/studio_main.js`: file model, editor binding, preview/runtime integration, persistence.
- `web/nemoclaw/scripts/_openclaw.js`: API client, policy helpers, UI renderers.

Sample split plan:

```text
1. Extract pure helpers first.
2. Keep the public import surface stable.
3. Add one compatibility import if existing pages rely on the old module path.
4. Run browser/runtime checks after each extraction.
```

### Prose Polish: 132

Main groups:

- `staccato_cadence`: 32
- `over_verbage`: 27
- `word_echo`: 12
- `repeated_phrase`: 11
- `padding`: 7
- `dense_repeats`: 4
- `hollow_intro`: 3
- `comma_weight`: 2
- plus page-level rhythm flags

Recommended approach: use these as review prompts, not a checklist. Fix a page only when several findings point to the same weak paragraph.

Good targets:

- `web/nemoclaw/01b-react.html`: highest rhythm score, also recommended grammar findings.
- `web/nemoclaw/01c-tools.html`: rhythm and repetition clusters.
- `web/nemoclaw/03b-openclaw.html`: rhythm and repeated wording clusters.

Bad fixes:

- swapping synonyms until the validator shuts up
- splitting every long sentence
- turning explanatory prose into stubs
- removing technical terms that must repeat for clarity

Sample paragraph-level fix:

```text
Before:
The agent retrieves the list of tools a server offers with a tools/list call, then invokes any one of them with tools/call.

After:
The agent first asks the server what it can do with `tools/list`. When it chooses one option, it invokes that tool with `tools/call`.
```

## Suggested MR Breakdown

### MR A: Theme Variable Sweep

Scope:

- `web/nemoclaw/assets/figures/fig2_react.svg`
- `web/nemoclaw/assets/figures/fig2_rewoo.svg`
- `web/nemoclaw/assets/figures/rag_arch_2021.svg`
- `web/nemoclaw/scripts/_figures.js`
- `web/nemoclaw/scripts/_canvas.js`
- `web/nemoclaw/scripts/_viz.js`

Validation:

```bash
python3 scripts/validation/color_theme.py
python3 scripts/validation/figure_audit.py
python3 scripts/validation/validate_bundle.py --no-write --scope ship
```

Review focus: rendered contrast in light/dark mode.

### MR B: Recommended Prose Cleanup

Scope:

- `web/nemoclaw/01a-loop.html`
- `web/nemoclaw/01b-react.html`
- `web/nemoclaw/02a-routing.html`
- `web/nemoclaw/03a-kickstart.html`
- `web/nemoclaw/04a-safety.html`

Validation:

```bash
python3 scripts/validation/prose_variety.py
python3 scripts/validation/validate_bundle.py --no-write --scope ship
```

Review focus: preserve narrative and concrete learner framing.

### MR C: Mechanical Comment Hygiene

Scope: one subsystem at a time.

Validation:

```bash
python3 scripts/validation/fix_comment_hygiene.py --apply --file <path>
python3 scripts/validation/code_hygiene.py
python3 scripts/validation/validate_bundle.py --no-write --scope ship
```

Review focus: no logic changes.

### MR D: Service Refactor

Scope: one service file or one helper extraction.

Validation depends on touched file. Minimum:

```bash
python3 scripts/validation/code_hygiene.py
python3 scripts/validation/validate_bundle.py --no-write --scope ship
```

For service runtime paths, also run the matching service tests or lab-runtime harness.

## Done Criteria

A remediation MR is done when:

- `validate_bundle.py --no-write --scope ship` passes.
- The target finding count decreases for the intended category.
- The diff does not introduce validator-gaming prose or hidden code surfaces.
- The MR description names the category it reduces and the remaining category count.
