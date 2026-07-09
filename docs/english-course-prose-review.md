# English course prose review

This report applies the structural lessons from Juanjo's Spanish review to the canonical English
course. It does not treat Spanish word choices as English rules. It asks the same editorial
question: would a software developer naturally explain the mechanism this way, or is the sentence
merely grammatical?

## Rules supported by the expert review

1. **Lead with the actor and action.** Prefer “the runtime executes the function and returns its
   result” to a chain of abstract nouns or passive events.
2. **Name the owner of each responsibility.** Model, harness, runtime, gateway, tool, and sandbox
   are not synonyms. A sentence should identify which component selects, executes, stores, routes,
   or blocks something.
3. **Use developer collocations.** Prefer phrases a practitioner would search for or say in review:
   indexing agent, execution runtime, tool call, control boundary, fan-out, and workflow.
4. **Preserve identifiers.** `finish_reason`, method names, routes, JSON values, and product names
   remain exact even when the surrounding sentence changes.
5. **Put the useful fact before the lesson scaffold.** “Fan-out and fixed routing provide this
   control” is stronger than “This section uses fan-out to show…”. The page is not the actor.
6. **Split overloaded sentences at a real conceptual seam.** A long systems sentence is acceptable
   when its clauses describe one mechanism. Split it when separate actors or recommendations are
   competing for the same breath.
7. **Use direct learner instructions only for learner actions.** “Run the cell” is appropriate.
   Descriptions of runtime behavior should stay declarative instead of addressing the reader.
8. **Keep technical contrasts that carry a boundary.** “The kernel decides by binary, not only by
   host” is useful security information. A detector must not erase it merely because the sentence
   has an antithetical shape.

## Complete learner-page scan

Run `python3 scripts/validation/prose_variety.py --scope course` to reproduce the ranking. The
[prose scanner](../scripts/validation/prose_variety.py) is advisory: each concrete signal below has
been read in context and assigned a disposition.

| Page | Findings | Recommendation |
|---|---|---|
| `index.html` | Mildly uniform sentence length and several three-item lists. | Keep. Objectives and the three-system overview are genuine enumerations; no sentence-level defect was found. |
| `01a-loop.html` | Slightly uniform sentence length. The broader validator also requests source coverage. | Keep the prose. Handle source coverage through material provenance, not a rhythm rewrite. |
| `01b-react.html` | Mild rhythm signals only. | Keep. Short labels and the ReAct sequence are technical structure, not marketing cadence. |
| `01c-tools.html` | Repeated paragraph openings; `tools` appears three times around `tools/list` and `tools/call`. | Revise the MCP sentence to “The agent retrieves a server's catalog with `tools/list` and invokes a selected entry with `tools/call`.” During the coordinated locale pass, vary nearby “The cell…” openings where the subject adds no information. |
| `02a-routing.html` | “This section uses…” scaffolding; a two-sentence stub separates component composition from the workflow-agent threshold. | Lead with fan-out and fixed routing. Join the composition claim to the condition that makes a workflow agent worthwhile. |
| `02b-rag.html` | “This module follows…” scaffolding; one sentence repeats `through` for MCP, A2A, and skills. | Lead with the corpus-to-answer mechanism. Recast the diagram instruction around two reading directions and list the capabilities once. |
| `02c-deep.html` | “This cell exposes…” scaffolding; one code comment wraps in the middle of a clause. | Make each stage the subject. Repair the comment at a sentence boundary during the coordinated locale pass. |
| `03a-kickstart.html` | “This cell makes…” scaffolding. | Say that the exposed code makes the same request as the probe; the cell itself is only the container. |
| `03b-openclaw.html` | No concrete composition finding. | Keep. |
| `03c-always-on.html` | No concrete English finding. | Keep. Gateway-versus-HTTP contrasts are load-bearing. |
| `04a-safety.html` | One scaffolding opener and three padding hits (`exactly`, `outright`). | Name the binary-identity test directly and remove the adverbs where they add no condition or degree. Preserve the binary-versus-host contrasts. |
| `04b-modern-clis.html` | No concrete English finding. | Keep. |
| `04c-going-further.html` | The sentence beginning “The remaining choices are…” defers its action behind a copula. | Use “You now need to choose where to deploy it, how to add your own knowledge, and which open problems matter once the basics hold.” |

## Contribution boundary

This MR records the English recommendations and makes the learner-only scan reproducible. It does
not change canonical course prose. Every canonical wording change invalidates reviewed Spanish and
Portuguese source hashes, so the revisions above belong in a coordinated follow-up with both locale
owners. That follow-up should render all three languages before accepting new hashes.

The coordinated follow-up must satisfy the localization and Pages criteria in the
[release test plan](release-test-plan.md).
