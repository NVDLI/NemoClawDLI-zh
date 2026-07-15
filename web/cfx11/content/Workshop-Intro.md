<!-- dli-course-cell {"id":"Workshop-Intro:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"13c2501099a2dcd48d52027f461c0511c06322c31a28895d7f732b4107581b95","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Workshop Introduction</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"d240fe35838e79da8cb65b738f12511b9f68f0ec192dbccadc5ebb60dadbac3a","type":"markdown"} -->
<!-- MODEL_POLICY_NEMOTRON_20260505 -->
This workshop uses two Nemotron defaults so the model choice matches the prompt-engineering task:

- `nvidia/nemotron-nano-12b-v2-vl` for normal chat, extraction, classification, tool calling, and agent examples. It is a fast multimodal document-intelligence model, but the early notebooks use it as a text-chat model through the same OpenAI-compatible interface.
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` only when the notebook is explicitly about reasoning. It is an omnimodal reasoning model, so it is useful when the task benefits from deliberate multi-step analysis rather than a direct response.

That split is intentional: most production prompt work should stay with the simpler non-reasoning path until the task actually needs the latency and token budget of a reasoning model.

<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"0d19900dd03b3807db79d8a35dfa136427a3771c1437384747a58756ac9aba27","type":"markdown"} -->
Welcome.

In this workshop you will learn a powerful assortment of techniques for working programmatically with LLMs via prompt engineering. By the time you complete this workshop you will be ready to write application code using LLMs for a wide variety of language related tasks.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"ba93ce50e38f4a23091412b7e7bae26ac71016ffc0c5ce97633cf7b24e065c51","type":"markdown"} -->
## Workshop Outline
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"65ae799d457d4438254ea6bab030fb02822c7d5532a40ecb7ea94b682f0bcafe","type":"markdown"} -->
This workshop is comprised of 5 sections, accessible via the file viewer on the left-hand side of your JupyterLab window. To help orient you to the work you'll be performing today in the workshop, here is a brief description of each section.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"1fc69e3ec8c11f406e2b49dc3c4da6a9699a43a549133eeb6ec68d0bdac15b68","type":"markdown"} -->
### Section 1: Introduction to Prompting
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"f97935cbcbbcfb939547976033ad0189c97c3010581cb155aaeb602ace54922e","type":"markdown"} -->
In this section you'll orient to the workshop environment, including the Nemotron Nano 12B-V2-VL large language model that you'll be using throughout the workshop. You'll begin with the "hello world" of programmatically prompting an LLM and viewing its response and will progress into some of the core prompting techiques, using LangChain, that will support your work for the remainder of the workshop.

This section concludes with a mini project where you will perform a combination of analysis and generative tasks on a batch of inputs.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"eab627a8237034d14ad8760d40761d21fc56ca58ff4769f422f32e1d58dbc7f1","type":"markdown"} -->
### Section 2: LangChain Expression Language (LCEL), Runnables, and Chains
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"bdc6e2f9b74c423041a091ab70eed3692d62dfd84b2bec044a6235b3d5313b6f","type":"markdown"} -->
In this section you'll learn how to create modular, reusable, and composable units of LLM-based work called chains using LangChain expression language, or LCEL. In the service of creating and working with LCEL chains you'll learn how to create custom chain components and compose chains, including in parallel.

This section concludes with a mini project where you'll revisit the section 1 mini-project, but this time will simplify your code by utilizing LCEL chains and also perform some of the project's subtasks in parallel.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"e7e6b1866a6b6b1d636054983ff34afb72f7aa7ce1366e53d78ae1a3e1c5d793","type":"markdown"} -->
### Section 3: Prompting With Messages
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"4208388e8ab084290ef26ac127a477dc747931dae3c707e50517e793c83d774a","type":"markdown"} -->
In this section you'll learn how to explicitly control the kinds of messages we send to and receive from chat models, and leverage them to perform a variety of powerful prompt engineering techniques including few-shot prompting, system message updating, and chain-of-thought prompting. You'll also explore reasoning models, LLMs trained for step-by-step deliberation, and learn how to work with their thinking tokens.

This section concludes by your managing messages to create a chatbot capable of retaining conversation history and assuming a variety of personas that you can specify.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"dbcce63f1746b40ec6a0f7b89037d31c759670a517b198ed7dd312eb831f2f62","type":"markdown"} -->
### Section 4: Structured Output
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"72f46842b4b512bbedb00e9bc517505ccd299f25c404a628ffb15f43c9f928ea","type":"markdown"} -->
In this section you'll learn how to define precise data structure definitions and provide them to LLMs in order to get the LLM to generate structured data capable of being used directly in code.

This section concludes with a mini-project where you use structured data generation techniques to perform data extraction and document tagging on an unstructured text document.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"cbb94e5d1b7a5a00b7ac1b81a56877f01cffc2c4d99f6bee3caa4e85fb6a182b","type":"markdown"} -->
### Section 5: Tool Use and Agents
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"76b71747e3b5ce9bafc07dd114f2b232bdece1bd067ad10643a7af0615821054","type":"markdown"} -->
In this section you'll learn how to create units of functionality external to the LLM called tools, and augment LLMs to be able to utilize tools and include the results of their work in the responses they generate.

In this section you'll conduct a mini-project where you create an LLM agent capable of utilizing external API calls to augment its responses with real-time data.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"b3fc3b2f6b5b1e3c5f9f85d55b37b49794dc05c023a24a760fe33907de3f89c2","type":"markdown"} -->
### Section 6: Assessment
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"4df38ffe897cf47992194ee75e5f42e9f73e627dd6d30fc83bfbd1020ca83de2","type":"markdown"} -->
In this section you'll put what you've learned to the test and earn a certificate of competency in the course by completing an assessment project where you build a LangChain application capable of identifying the main sources of customer complaints out of a collection of customer emails.

This section concludes with a workshop summary and an opportunity to provide feedback to us about the workshop.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"Workshop-Intro:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"56978d4e2b54633e0841d989a2101a92a00865a8b506ed835d1f47663dd5222c","type":"markdown"} -->
<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>1-Intro-to-Prompting/10-Section-Introduction.ipynb</code> next: <strong>Section 1: Introduction to Prompting</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Pick one real workflow you want prompt engineering to improve, so the first section stays tied to a concrete outcome instead of abstract examples.</p>
</div>
<!-- /dli-course-cell -->
