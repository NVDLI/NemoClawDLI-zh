[Technical Blog](https://developer.nvidia.com/blog)

[Subscribe](https://developer.nvidia.com/email-signup)

[Related Resources](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/#main-content-end)

[Agentic AI / Generative AI](https://developer.nvidia.com/blog/category/generative-ai/)

# Deploy Self-Evolving Agents for Faster, More Secure Research with a Hermes Agent and NVIDIA NemoClaw

![Decorative image.](https://developer-blogs.nvidia.com/wp-content/uploads/2026/05/NemoClaw-Hermes-1024x576.jpg)

Jun 02, 2026


By [Sam Pastoriza](https://developer.nvidia.com/blog/author/spastoriza/ "Posts by Sam Pastoriza"), [Sean Lopp](https://developer.nvidia.com/blog/author/seanlopp/ "Posts by Sean Lopp") and [Matthew Penn](https://developer.nvidia.com/blog/author/mpenn/ "Posts by Matthew Penn")

+7

Like

[Discuss (0)](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/#entry-content-comments)

- [L](https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)
- [T](https://twitter.com/intent/tweet?text=Deploy+Self-Evolving+Agents+for+Faster%2C+More+Secure+Research+with+a+Hermes+Agent+and+NVIDIA+NemoClaw+%7C+NVIDIA+Technical+Blog+https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)
- [F](https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)
- [R](https://www.reddit.com/submit?url=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F&title=Deploy+Self-Evolving+Agents+for+Faster%2C+More+Secure+Research+with+a+Hermes+Agent+and+NVIDIA+NemoClaw+%7C+NVIDIA+Technical+Blog)
- [E](mailto:?subject=I%27d%20like%20to%20share%20a%20link%20with%20you&body=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)

AI agents are a powerful tool for synthesizing data to accelerate research, summarize information, and help teams make decisions faster. But combining internal data with public sources poses security challenges.

This post shares [an open source example](https://github.com/NVIDIA/nemoclaw-community/tree/main/examples/personal-community-sentiment-triage) using [Hermes Agent](https://github.com/nousresearch/hermes-agent) with [NVIDIA NemoClaw](https://www.nvidia.com/en-us/ai/nemoclaw/) for product research across Outlook, Slack, and GitHub. [NVIDIA OpenShell](https://build.nvidia.com/openshell) enforces a security-approved runtime. The agent learns preferences and patterns, writing new memories and skills. The more users work with the agent, the better it gets.

While the integration points are specific to this use case (Slack, Outlook, and GitHub), the pattern of safely mixing public and private data in a self-improving agent is important for many use cases, including sales research, customer support, engineering triage, competitive analysis, and internal knowledge discovery.

You will learn how to:

- Bring up the open-source NemoClaw stack with one install command.
- Wire the agent to two messaging channels (Slack and Outlook) and to community data (GitHub and the NVIDIA developer forums).
- Teach the agent a recurring report format directly from a chat conversation—no code changes or gateway restarts required..
- Save the agent’s learned state so it persists across deployments.

**Prerequisites**

To follow along, you’ll need:

- A host with a running Docker daemon. The example targets Ubuntu 24.04 but works on any distribution OpenShell supports.
- A [build.nvidia.com](https://build.nvidia.com/) API key for inference. The default model is nvidia/nemotron-3-super-120b-a12b. Hermes Agent runs unchanged against a self-hosted NVIDIA Nemotron model on [NVIDIA NIM](https://developer.nvidia.com/nim), or vLLM when traffic must stay on-prem.
- Credentials for at least one messaging integration:
  - An Outlook tenant plus a registered Azure app, or
  - A Slack workspace plus a Slack app.

Setup instructions are available in:

- [docs/set-up-outlook-bridge.md](https://github.com/NVIDIA/nemoclaw-community/blob/main/examples/personal-community-sentiment-triage/docs/set-up-outlook-bridge.md)
- [docs/set-up-slack.md](https://github.com/NVIDIA/nemoclaw-community/blob/main/examples/personal-community-sentiment-triage/docs/set-up-slack.md)
- A GitHub token for pulling data.

How We Built Self-Evolving Hermes Agents With NVIDIA NemoClaw - YouTube

Tap to unmute

[How We Built Self-Evolving Hermes Agents With NVIDIA NemoClaw](https://www.youtube.com/watch?v=NGfvTlU2T5E) [NVIDIA Developer](https://www.youtube.com/channel/UCBHcMCGaiJhv-ESTcWGJPcw)

NVIDIA Developer213K subscribers

[Watch on](https://www.youtube.com/watch?v=NGfvTlU2T5E)

_Video 1. Deploy a self-evolving AI agent with NemoClaw and Hermes Agent_

## Install and bring up Hermes [Scroll to Install and bring up Hermes section](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/\#install_and_bring_up_hermes)

1. Clone the repository and install OpenShell:

|     |
| --- |
| `git clone https:``//github``.com``/NVIDIA/nemoclaw-community``.git`<br>`cd``nemoclaw-community``/examples/personal-community-sentiment-triage`<br>`curl -LsSf https:``//raw``.githubusercontent.com``/NVIDIA/OpenShell/main/install``.sh | OPENSHELL_VERSION=v0.0.38 sh` |

2. Copy the env template and fill in your inference key, plus at least one messaging channel.
3. Start the host-side services using the host-services shell script—then bring up the agent:

|     |
| --- |
| `bash``scripts``/00-host-services``.sh`<br>`bash``scripts``/bring-up``.sh` |

The [bring-up.sh](http://bring-up.sh/) script starts Hermes inside the sandbox. The OpenShell sandbox does two critical things.

- Manages the credentials, ensuring the Hermes agent never sees the Slack or Outlook tokens—authentication happens as requests exit the sandbox proxy.
- Enforces network access policies. The agent has access to sensitive internal data from Outlook or Slack. To protect this data, the agent is prohibited from accessing the public internet.

The GitHub and NVIDIA forum data is available through a separate ETL process that retrieves the data and stores it, giving the agent read-only access. This setup ensures that even a compromised agent can not post data to external sites.

4. Once the script finishes, check that the sandbox is healthy:

|     |
| --- |
| `openshell sandbox list`<br>`# hermes-direct should report Ready`<br>`openshell sandbox``exec``--name hermes-direct -- \`<br>```curl -sf http:``//localhost``:8642``/health`<br>`# {"status":"ok","platform":"hermes-agent"}` |

5. Send the agent a Slack DM or an email from the address you configured in `.env` to confirm it replies.

## Teach once, recall anywhere [Scroll to Teach once, recall anywhere section](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/\#teach_once_recall_anywhere)

With the agent up and running, this section shows you how to teach it a new skill —and how that skill carries across conversations.

1\. Ask for a daily digest.

Teach the agent to summarize GitHub issues each morning. Start by asking for the daily update:

```
> Give me a daily update on important issues for NemoClaw.
```

The reply is helpful—some prose, some bullets—but it’s not in the correct format. Ask for a different format:

```
> That's too long. Give me exactly 5 top issues and 3 discussions, each with the number, title, state, URL, and a one-line "why it matters". Open with a bold header and close with **Bottom line:** in 2-3 sentences.
```

Now that the reply is a well-formatted digest, use positive reinforcement triggers and tell the agent to save this format for future use:

```
> Perfect, that's the format I want every day. Next time I ask for the daily NemoClaw issue digest, give me back exactly this shape—without me spelling it out again. And if a coworker emails the bot for the same thing, they should get the same shape, too.
```

2\. Hermes writes a skill.

When Hermes recognizes the pattern, it writes a [SKILL.md](http://skill.md/) to the filesystem. The file has a short YAML frontmatter (name and description) and the format scaffolding as the body.

3\. Snapshot, tear down, rebuild, restore.

Agents in production are rebuilt when new code ships or configurations change. If learned skills do not survive, the agent must be retaught every time. To prevent this, take a snapshot, destroy the sandbox, rebuild from the image, and restore from the tarball to ensure the skill survives:

|     |
| --- |
| `bash``scripts``/snapshot``.sh``# writes.snapshots/<ISO-timestamp>.tar.gz`<br>`bash``scripts``/tear-down``.sh``# destroys the sandbox container`<br>`bash``scripts``/bring-up``.sh``# rebuilds the sandbox from the image`<br>`bash``scripts``/restore``.sh``# rehydrates /sandbox/.hermes-data/` |

The snapshot captures the agent state, including skills, memories, sessions, and any scheduled jobs. A credential filter excludes files such as .env, \*token\*, and \*secret\* so the tarball is safe to share.

4\. Trigger the skill from a fresh conversation.

From a new conversation, ask for the “daily NemoClaw issue digest over the last 3 days,” and the skill will return the same answer format. Only the numbers and titles change to match the underlying data. The format lives in the skill, not in conversational memory.

## Why the architecture works: Model, harness, and runtime [Scroll to Why the architecture works: Model, harness, and runtime section](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/\#why_the_architecture_works_model_harness_and_runtime)

The agent is deployed with [NVIDIA](https://github.com/NVIDIA/NemoClaw) [NemoClaw](https://github.com/NVIDIA/NemoClaw), a blueprint for open agents built with harnesses powered by open models in a secure runtime.

| Component | What it does | Provided by |
| --- | --- | --- |
| Model | Reasoning, tool selection, drafting | [NVIDIA Nemotron 3 Super](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8) |
| Harness | Skills, sessions, memory, bridges, hooks | [Hermes Agent](https://brev.nvidia.com/launchable/deploy?launchableID=env-3Azt0aYgVNFEuz7opyx3gscmowS) |
| Runtime | Filesystem and network policy, provider injection, credential brokering | [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) |

_Table 1. The three components of the agent_

Figure 1 shows how the layers fit together.

![Architecture diagram showing Hermes Agent interactions with a sandbox.](data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%201867%20927%22%3E%3C/svg%3E)_Figure 1. The Hermes Agent runs inside an OpenShell sandbox, with GitHub and forum data accessed through a host-side mirror_

The network policy is code, not a prompt. `policy.yaml`declares every allowed destination, port, HTTP verb, and binary. This block authorizes inference:

|     |
| --- |
| `network_policies:`<br>`nvidia:`<br>```endpoints:`<br>```- host: integrate.api.nvidia.com`<br>```port: 443`<br>```rules:`<br>```- allow: { method: POST, path:``/v1/chat/completions``}`<br>```- allow: { method: POST, path:``/v1/embeddings``}`<br>```- allow: { method: GET,  path:``/v1/models``}`<br>```binaries:`<br>```- path:``/usr/local/bin/hermes`<br>```- path:``/usr/bin/python3` |

If the agent tries to reach a host not on the allowlist, the proxy returns a 403 (Forbidden) error, and Hermes Agent treats it as a tool error.

### Observability with NeMo Relay and Arize Phoenix [Scroll to Observability with NeMo Relay and Arize Phoenix section](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/\#observability_with_nemo_relay_and_arize_phoenix)

Agents make many decisions—which skill to call, which tool to invoke, what arguments to pass, what to send back to the user—per turn. When something goes wrong, a user can’t fix it without seeing what the agent actually did.

The deployed agent records traces in Agent Trajectory Format (ATIF). The sandbox image includes [NVIDIA NeMo Relay](https://github.com/NVIDIA/NeMo-Flow) by default, so these traces show up without additional setup. Before it’s torn down, [scripts/download-traces.sh](https://github.com/NVIDIA/nemoclaw-community/blob/main/examples/personal-community-sentiment-triage/scripts/download-traces.sh) pulls them off the sandbox. Setting `PHOENIX_COLLECTOR_ENDPOINT` in the `.env` file enables live streaming of traces to a Phoenix collector for interactive debugging.

## Adapt for different use cases [Scroll to Adapt for different use cases section](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/\#adapt_for_different_use_cases)

While a main benefit of Hermes is self-improvement, the example can also be customized before deployment. Update the predefined skills and OpenShell policies to fit specific workflows and environments. The example ships with five skills, picked up automatically by the gateway from the [agents/hermes/skills/](https://github.com/NVIDIA/nemoclaw-community/tree/main/examples/personal-community-sentiment-triage/agents/hermes/skills) folder. Modify the OpenShell policies to give the agent access to data sources or tools.

Get started quickly with NemoClaw: point your agent at NVIDIA-verified skills built into Claude Code, Codex, and Hermes Skills Hub with the full catalog published on [skills.sh](https://github.com/vercel-labs/skills) for use across Cursor, Gemini CLI, GitHub Copilot, Windsurf, and dozens more.

### Learn more [Scroll to Learn more section](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/\#learn_more)

The [NemoClaw Community repository](https://github.com/NVIDIA/nemoclaw-community) ships the full example used in this tutorial. To go deeper:

- Read the [NemoClaw documentation](https://docs.nvidia.com/nemoclaw/latest/) for the blueprint reference and CLI.
- Read the [NVIDIA OpenShell documentation](https://docs.nvidia.com/openshell/latest/home) for sandbox creation, policy syntax, and provider management.
- Pick a Nemotron model from [build.nvidia.com](https://build.nvidia.com/), or self-host it with [NIM](https://developer.nvidia.com/nim).

[Discuss (0)](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/#entry-content-comments)

+7

Like

## Tags

[Agentic AI / Generative AI](https://developer.nvidia.com/blog/category/generative-ai/) \| [Developer Tools & Techniques](https://developer.nvidia.com/blog/category/development/) \| [General](https://developer.nvidia.com/blog/recent-posts/?industry=General) \| [Intermediate Technical](https://developer.nvidia.com/blog/recent-posts/?learning_levels=Intermediate+Technical) \| [Tutorial](https://developer.nvidia.com/blog/recent-posts/?content_types=Tutorial) \| [AI Agent](https://developer.nvidia.com/blog/tag/ai-agent/) \| [Computex 2026](https://developer.nvidia.com/blog/tag/computex-2026/) \| [NemoClaw](https://developer.nvidia.com/blog/tag/nemoclaw/) \| [OpenShell](https://developer.nvidia.com/blog/tag/openshell/)

## About the Authors

![Avatar photo](data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%20131%20131%22%3E%3C/svg%3E)

**About Sam Pastoriza**


Sam Pastoriza is a segment solutions architect at NVIDIA, focused on advancing the field of Agentic AI. He collaborates with cross-functional teams to build agents using NVIDIA NeMo Agent Toolkit, most notably developing the AI-Q Research Assistant blueprint for deep research. Sam’s experience spans the full AI stack: he maintains core toolkit architecture, builds and evaluates specialized industry agents, and designs intuitive front-end interfaces that bring these powerful AI systems to life for end users.

Sam holds a Master’s degree in Data Science and Analytics from Georgetown University and a BS in Software Engineering from Rose-Hulman Institute of Technology.




[View all posts by Sam Pastoriza](https://developer.nvidia.com/blog/author/spastoriza/)

![Avatar photo](data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%20131%20131%22%3E%3C/svg%3E)

**About Sean Lopp**


Sean is a software engineer at NVIDIA where he works on data, AI, and developer tooling to help organizations realize the full potential of NVIDIA AI Enterprise software. He has a decade long career in open source software, especially in the Python data ecosystem. He studied applied mathematics at the Colorado School of Mines.




[View all posts by Sean Lopp](https://developer.nvidia.com/blog/author/seanlopp/)

![Matthew Penn](data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%20131%20131%22%3E%3C/svg%3E)

**About Matthew Penn**


Matt Penn is a senior data scientist and leader of Morpheus Solutions Architecture at NVIDIA. His focus is the application of GPU-accelerated AI and high performance data analytics to cybersecurity challenges across industries. ‌Before joining NVIDIA, Matt served as the director of AI & Data Science at Altamira Technologies and as a lead data scientist at Booz Allen Hamilton where he developed quantitative solutions for customers across the US Public Sector and HPC ecosystem. He holds a master’s degree in Information Systems from Indiana University and a bachelor’s degree in Aerospace Engineering from the University of Central Florida.




[View all posts by Matthew Penn](https://developer.nvidia.com/blog/author/mpenn/)

## Comments

- [![](https://developer-blogs.nvidia.com/wp-content/uploads/2026/05/gtc26-tpe-phase3-keynote-watch-blog-footer-1360x180-copy-enEN-4979800.webp)](https://www.nvidia.com/en-tw/gtc/taipei/?nvid=nv-int-bnr-463583)

![](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/)

![](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/)

- [L](https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)
- [T](https://twitter.com/intent/tweet?text=Deploy+Self-Evolving+Agents+for+Faster%2C+More+Secure+Research+with+a+Hermes+Agent+and+NVIDIA+NemoClaw+%7C+NVIDIA+Technical+Blog+https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)
- [F](https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)
- [R](https://www.reddit.com/submit?url=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F&title=Deploy+Self-Evolving+Agents+for+Faster%2C+More+Secure+Research+with+a+Hermes+Agent+and+NVIDIA+NemoClaw+%7C+NVIDIA+Technical+Blog)
- [E](mailto:?subject=I%27d%20like%20to%20share%20a%20link%20with%20you&body=https%3A%2F%2Fdeveloper.nvidia.com%2Fblog%2Fdeploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw%2F)

- [Join](https://developer.nvidia.com/login)