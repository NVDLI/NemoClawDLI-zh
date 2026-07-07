# Security control disposition

This record classifies security requirements raised during architecture review without copying
private review identifiers or treating generated recommendations as automatically applicable. It
supplements [`security-design.md`](security-design.md) and the executable evidence map in
[`release-test-plan.md`](release-test-plan.md).

## Status vocabulary

- **Verified** means a repository file or deterministic command supplies the stated evidence.
- **Not verified** means the control is absent, incomplete, or cannot yet be demonstrated.
- **Unknown** means the responsible service or host has not supplied reviewable evidence.
- **Human approval required** means an accountable host, service, release, or security owner must
  decide and record the result outside this public repository.
- **Not applicable** means the recommendation does not match the product boundary or cannot be
  implemented by a browser application. The rationale is part of the disposition.

Repository evidence does not grant Legal, OSRB, Export, Privacy, Product Security, SCM, host, or
release approval.

## Source and contribution controls

| Concern | State | Evidence and disposition | Owner or next action |
|---|---|---|---|
| Encrypted Git transport and server identity | Human approval required | The playbook requires HTTPS or SSH with certificate or host-key verification. Network path and host configuration are not repository facts. | GitHub and GitLab administrators verify live transport and identity settings. |
| Protected branches, tags, and review | Human approval required | Workflow files enforce required checks, DCO, read-only pull-request permissions, and protected deployment steps. Rulesets, bypass lists, and reviewer assignments remain host settings. | Host administrators verify rulesets and Rule Insights before publication. |
| Untrusted contribution isolation | Verified | Pull-request jobs use read-only permissions, persist no checkout credential, receive no course secrets, and cannot deploy. | `contribution_safety_audit.py` prevents workflow drift. |
| Git history and object exhaustion | Human approval required | CI jobs have explicit timeouts and hosted runners have bounded resources. A shallow clone is not universal because DCO and release ancestry checks require history. | Host administrators retain object-size limits; release workflows fetch only the history they require. |
| Public and internal source synchronization | Verified | Public changes are detected by a scheduled, read-only fetch that executes only the trusted internal audit script. Differences stop the job and require an integration MR. No job force-pushes either protected branch. | Configure the weekly host schedule after the public repository is populated and review every reconciliation MR. |

The selected public operating model is an NVIDIA-owned Full-OSS-Project intended as OSS Type I.
After approved cutover, public GitHub is canonical for project activity and internal GitLab is an
integration and validation consumer. The authoritative lifecycle record must confirm the Type I
classification and the relationship between the public and internal systems.

## Build and artifact controls

| Concern | State | Evidence and disposition | Owner or next action |
|---|---|---|---|
| Mutable workflow or package dependencies | Verified | GitHub Actions use full commit SHAs. Python and browser dependencies use exact reviewed locks and inventories. | Dependency and contribution audits fail on mutable workflow pins or lock drift. |
| Build resource exhaustion | Verified | Pages and release jobs have timeouts. The Pages tree and downloaded archive have maximum file count, per-file size, total size, depth, archive size, and expansion-ratio limits. | `pages_artifact_integrity.py --self-test` mutation-tests every bound. Host CPU, memory, disk, and egress quotas remain provider controls. |
| Post-validation artifact substitution | Verified | CI creates one manifest-bearing Pages artifact. Deployment safely extracts that artifact, rechecks every byte, deploys it without rebuilding, then a read-only job compares the live site with the reviewed manifest. | The protected environment reviewer approves the artifact-producing commit; post-deploy mismatch fails CI. |
| Unsafe archive extraction | Verified | Deployment rejects absolute paths, traversal, duplicate members, links, devices, unsupported member types, excessive depth, and resource-limit violations before materializing the tree. | Keep extraction inside `pages_artifact_integrity.py`; do not replace it with raw `tar -xf`. |
| Cryptographic artifact signature and signed provenance | Not verified | SHA-256 inventories detect substitution when their trusted handoff is preserved, but a checksum is not a signature. No repository file proves a protected signing identity or artifact attestation. | Release and Product Security owners decide whether GitHub artifact attestations or another signing service is required before publication. |
| Confidentiality of a public course artifact | Not applicable | Once published, HTML, JavaScript, CSS, documentation, endpoints intended for clients, and dependency metadata are public by design. Secret and private-location scanning remains required before publication. | Protect unreleased artifacts at the host and keep secrets out of every generated tree. |

## Static hosting and browser controls

| Concern | State | Evidence and disposition | Owner or next action |
|---|---|---|---|
| Remote executable dependency injection | Verified | The published artifact rejects remote scripts, remote stylesheets, remote base URLs, unreviewed browser dependencies, and manifest drift. | Keep executable dependencies same-origin, vendored, pinned, inventoried, and scanned. |
| Strict response-header CSP, immutable cache headers, and WAF rate limits | Not verified | GitHub Pages does not provide repository-controlled response headers or WAF policy. A meta policy cannot provide all response-header protections, and the interactive course currently contains reviewed inline code. | The hosting owner must accept the residual risk or place an approved CDN or host in front of the site and verify live headers. |
| Same-origin Subresource Integrity | Not applicable | A same-origin hash in HTML is not an independent trust anchor if the HTML and asset can be replaced together. The reviewed whole-tree manifest plus post-deploy byte comparison covers that substitution boundary. | Retain package provenance and whole-artifact integrity instead of claiming redundant same-origin hashes solve host compromise. |
| Browser certificate pinning | Not applicable | A static browser application cannot enforce independent certificate pinning for ordinary HTTPS or WSS requests. Browser and platform trust stores enforce certificate validation. | Hosting and relay owners maintain TLS, HSTS, certificate lifecycle, and approved enterprise interception policy. |
| Malicious model output in the DOM | Verified | Model output is rendered as text or through the reviewed sanitizer and URL checks; it is not accepted as arbitrary executable markup. | Runtime browser audits retain the rendering and navigation boundary. |
| Browser extensions and compromised learner devices | Not applicable | Course JavaScript cannot secure a browser execution context already controlled by an extension or endpoint attacker. | Learner endpoint policy and browser administration own this risk. The course warns that browser storage is not a vault. |
| Client-side prompt complexity detection | Not applicable | A learner controls the browser and can bypass client checks. Heuristic detection of costly reasoning is unreliable. | Model and relay services enforce payload, token, concurrency, timeout, rate, and spend limits. Client limits may improve usability but are not a security boundary. |

## Relay, model, launchable, and runtime controls

| Concern | State | Evidence and disposition | Owner or next action |
|---|---|---|---|
| Relay schema, route, frame-size, and rate enforcement | Unknown | The course registers reviewed endpoints and sends route-specific credentials, but it cannot prove a separately deployed relay's runtime limits. | Relay owners provide deployment evidence for allowlists, schemas, body and frame limits, identity quotas, timeouts, and TLS. |
| Short-lived and audience-scoped credentials | Unknown | The browser does not mint model, relay, Cloudflare, or gateway credentials. Learner-supplied keys can have provider-defined lifetimes. | Credential issuers document lifetime, audience, revocation, replay, and proof-of-possession decisions. |
| Model instruction, authorization, and compute controls | Unknown | Client prompts and valid credentials are untrusted. Browser code cannot enforce server instruction hierarchy, tool authorization, fair scheduling, or tenant quotas. | Model-service owners provide server-side validation, authorization, safety, rate, token, timeout, and concurrency evidence. |
| Launchable bootstrap and runtime isolation | Unknown | The repository documents expected TLS, launch authentication, sandbox policy, and allowlisted tool behavior. The live platform configuration is outside the static artifact. | Launchable and NemoClaw owners verify private listeners, configuration schema, safe deserialization, session quotas, sandbox policy, and credential binding. |
| End-to-end encryption through a relay | Human approval required | A blind relay design changes protocol, observability, credential, and operational requirements. TLS to each reviewed endpoint is already required. | Architecture and service owners decide whether relay-readable payloads are acceptable or a protocol change is warranted. |

## Publication blockers and retained risks

Before public publication, repository-owned checks must pass on the exact source and Pages artifact.
The authorized review record must separately resolve the following items:

1. Live GitHub rulesets, protected environments, security features, bypass lists, and immutable
   release settings.
2. The weekly external-to-internal integration schedule and its named reconciliation owner.
3. Artifact signing or attestation requirements and the protected signing identity, if required.
4. The hosting decision for CSP, cache headers, WAF controls, bandwidth limits, and availability.
5. Operational evidence from every required service for its identity, input-validation,
   resource-isolation, observability, and incident-response controls.
6. Credential lifetime, audience, revocation, replay, and shared-device handling.

An automated repository pass proves only the controls implemented in this source tree. Unknown,
not-verified, and human-owned requirements remain visible rather than being converted into a false
mitigation claim.
