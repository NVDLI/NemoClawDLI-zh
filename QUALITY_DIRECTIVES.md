# Quality directives: Building Agents

Runnable checks that detect real pedagogical harm in the course content and the
service notebooks. Each has a grep command to find instances, a description of
why it matters, and the canonical fix.

The authored notebook content lives under `cpu/` (the shared service docs). The
course itself ships as browser pages under `web/nemoclaw/`. Run all checks with
a script kept in `/tmp` (never versioned).

---

## QD-01: naive-faiss-cache

**Why it matters:** `if INDEX_DIR.exists(): load` silently loads a corrupt partial
index after an interrupted build. Retrieval degrades; no error raised.
Anyone building a retrieval index on a real corpus always hits this.

**Detect:**
```bash
grep -rn "INDEX_DIR.exists()" cpu/ | grep -v fingerprint
```

**Fix:** 4-guard pattern (file existence + fingerprint JSON match + graceful rebuild
+ atomic fingerprint write).

---

## QD-02: missing-heading-separators

**Why it matters:** `RecursiveCharacterTextSplitter` without `\n\n## ` and `\n\n### `
treats H2/H3 section breaks as ordinary paragraph breaks. A 4000-char chunk can
silently span multiple unrelated subsections, diluting retrieval precision.

**Detect:**
```bash
grep -rn "RecursiveCharacterTextSplitter" cpu/ -A5 | \
  grep "separators" | grep -v '"\\\\n\\\\n## "' | grep -v "## "
```

**Fix:** Add `"\n\n## "`, `"\n\n### "` before `"\n\n"` in separator list.

---

## QD-03: no-reranker

**Why it matters:** `similarity_search(k=N)` as final retrieval returns bi-encoder
results, which are fast but imprecise. Cross-encoder reranking (NVIDIARerank) is the
production upgrade. Students who copy `similarity_search` to production experience
retrieval degradation they can't diagnose.

**Detect:**
```bash
grep -rn "similarity_search\|as_retriever()" cpu/ | \
  grep -v "NVIDIARerank\|ContextualCompression\|rerank"
```

**Fix:** For any page that builds a retrieval pipeline (not just a demo), add a
retrieve-then-rerank step or a callout explaining the two-stage upgrade path:
a bi-encoder vector search followed by a cross-encoder rerank (NVIDIARerank).

---

## QD-04: deferred-dead-question

**Why it matters:** Promises like "we revisit in section 5e" where section 5e
doesn't exist leave students with unresolved conceptual questions.
Pedagogically worse than no promise.

**Detect:**
```bash
grep -rn "revisit\|hold this\|answered later\|deferred\|see §" cpu/ web/
```

**Fix:** Answer in-place (one or two sentences), or delete the deferral entirely.
Never point to a section that doesn't exist.

---

## QD-05: stale-notebook-xref

**Why it matters:** After renaming pages or notebooks, prose cross-references to
the old numbers create broken learning paths. A reference that points at a
number the file no longer carries strands the reader.

**Detect:**
```bash
grep -rn "notebook 9[3-9]\|notebook 0[7-9]\b\|NB9[3-9]\|nb9[3-9]" cpu/ web/
```

**Fix:** Batch-replace old numbers with new ones. Verify with: check that the
referenced notebook or page actually exists.

---

## QD-06: same-model-judge

**Why it matters:** Using the same model for generation AND evaluation inflates grades
(the model grades itself charitably) and understates real-world quality. An evaluation
or judge step must run a model at least as strong as the one that produced the output.

**Detect:**
```bash
grep -rn "CHAT_MODEL\|RAG_EXAMPLE_MODEL" cpu/ | \
  grep -i "judge\|eval\|assess\|verdict\|score" | grep -v "#"
```

**Fix:** For evaluation/judge cells, use a model at least as strong as the generation
model. Document the choice explicitly.

---

## QD-07: commented-runnable-code

**Why it matters:** Cells marked "Illustrative; not run" that demonstrate production
patterns (OTEL spans, MCP tools, etc.) teach students a pattern they can never
actually execute. Forward references to "see Notebook X" that point at commented code
are worse than no forward reference.

**Detect:**
```bash
grep -rn "Illustrative.*not run\|not.*runnable\|sketch.*not run" cpu/
```

**Fix:** Either uncomment and wire to real endpoints, or delete and replace with a
prose description that doesn't pretend to be runnable code.

---

## QD-08: input-type-asymmetry-missing

**Why it matters:** NVIDIAEmbeddings uses `input_type="passage"` for indexing and
`input_type="query"` for search. Without knowing this, students using the raw API
directly embed both with the same type, causing subtle retrieval degradation.
The LangChain wrapper handles it, but not mentioning it at all means students
never learn why direct API calls produce worse results.

**Detect:**
```bash
grep -rn "NVIDIAEmbeddings" cpu/ | grep -v "input_type\|passage\|query"
```

**Fix:** Add a one-line comment near the embedder declaration noting the
`input_type="passage"` (index) vs `input_type="query"` (search) split.

---

## Running all directives

```python
# run_quality_check.py (keep in /tmp; not versioned)
import subprocess, re
from pathlib import Path

ROOTS = [Path("cpu"), Path("web")]

checks = {
    "QD-01 naive-faiss-cache": (
        r"INDEX_DIR\.exists\(\)",
        lambda m: "fingerprint" not in m,
    ),
    "QD-02 missing-heading-sep": (
        r"RecursiveCharacterTextSplitter",
        lambda m: "## " not in m and "### " not in m,
    ),
    "QD-04 dead-deferral": (
        r"revisit in §|hold this question",
        lambda m: True,
    ),
    "QD-05 stale-xref": (
        r"notebook 9[3-9]|NB9[3-9]",
        lambda m: True,
    ),
    "QD-07 commented-runnable": (
        r"Illustrative.*not run",
        lambda m: True,
    ),
}

for name, (pattern, should_flag) in checks.items():
    hits = []
    for root in ROOTS:
        for f in root.rglob("*.md"):
            for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                if re.search(pattern, line, re.IGNORECASE):
                    text = f.read_text(errors="ignore")
                    if should_flag(text):
                        hits.append(f"  {f}:{i}: {line.strip()[:80]}")
    status = f"{len(hits)} instance(s)" if hits else "clean"
    print(f"\n{name}: {status}")
    for h in hits[:5]:
        print(h)
    if len(hits) > 5:
        print(f"  ... and {len(hits)-5} more")
```
