# Philosophy

*A record of the decisions behind how this repository is built and served, written down so contributors can see what each one commits us to. Synthesized from the team's Golden Path design sessions.*

## How content lives here

Content is authored once, by execution surface, under `web/` and `cpu/`. Everything a reader opens is generated from that source: `bundle_standalone.py` inlines each page into a self-contained HTML file, `build_pages.sh` assembles the client-side Pages site, and the `engine.js` that verifies the release also resolves where every generated link goes. A new delivery format is a new generator over the same source, so a correction reaches every format at once.

The proposed external release targets Apache 2.0, with no gate, paywall, or members-only tier after publication. External publication remains pending OSRB approval. The foyer at `web/index.html` shows the courses selected for the release build and the lab serves them. The reference packets under `web/nemoclaw/mats/` are joined to pages by the public URLs they cite, so a page's citations stay with the page.

Generation from one source and an open license push the content into a particular role. The repository keeps a curated body of knowledge and projects it into whatever form a reader opens; a course is one such projection. So most of the day-to-day work goes into curating that source and writing the generators, and very little goes into hand-building any individual format.

## How content is shaped

A page on this platform is built around something that runs. The lab brings up real services, and the convention is that a page ends in an artifact a reader executes against them. Pages are ordered, but the order is a default: there are no enforced prerequisites and no knowledge checks between them, so a reader can take what a page gives, use it, and come back for the next layer when a problem calls for it.

A page anchors its material in a task that runs, then deepens it across later pages, and gives the reader enough default ordering to stay oriented while still choosing where to go next. That is a bet about how the material transfers, and the verification the repository runs is the same bet written into code: the gate checks whether the artifacts execute and the links resolve, so it is measuring whether the thing a page asks a reader to run actually works.

## The services a course builds on

The repository ships the services a course drives: a model gateway (`llm_client`), a sandboxed agent runtime (`openclaw`), and a policy control plane (`sandbox-admin`), among others. Because the live services are present, a course can hand the reader real infrastructure to operate. The services handle the mechanical setup, which leaves the reader free to spend attention on the decision the exercise is actually about.

## What it is for

The repository curates technical knowledge, projects it into the form a reader needs, holds it under an open license, and serves courses that run against real infrastructure. That is the shape of a platform, and it is built to leave a reader able to do the thing the material is about. A change in what the reader can do is what the whole apparatus is tuned to produce, so it is the outcome the gate and the content discipline both work back from.

Contribution follows from the same aim. Tools and agents have made useful material much cheaper to propose, so the repository keeps the barrier to proposing an idea low. A question, correction, source, or teaching idea can arrive through a Discussion or structured Issue without a checkout. Changing the release is deliberately harder. Code from any person or agent starts untrusted, passes deterministic local and CI gates, names its blast radius and evidence, and reaches protected refs or release environments only through human-owned permissions. The decisions here are provisional, written down so the next person has something concrete to argue with.

---

The short, operational form of these commitments is the `purpose` group of tenets projected into [`SKILL.html`](SKILL.html). Run `python3 scripts/validation/tenets.py` to read the full operating creed.
