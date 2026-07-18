<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"0d2bd99806a1cb2a065d569a60a5a5de1ad14e6d9d640046a8a80fe68374f997","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Hello World with LangChain</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"dad83828a8667968c6c14d9e6366bd8c1a54bfa98455f9cf1207ac7a028a1576","type":"markdown"} -->
In this notebook, we will learn how to interact with LangChain to generate chat completions using the Nemotron Nano 12B-V2-VL model. This introductory exercise will help you understand the basics of setting up and using LangChain in a Jupyter environment.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"1300da2d172bfbb2a9f826675e4fef635748b772a05022e7a8240540744f1d10","type":"markdown"} -->
By the time you complete this notebook, you will:

- Have an introductory understanding of LangChain.
- Generate simple chat completions using LangChain.
- Compare the differences between using LangChain and the OpenAI library for chat completion.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"3979557b4465480fb2f1d59702dec58a11c21972182e96b8b88c68142298006e","type":"markdown"} -->
Here we import the `ChatNVIDIA` class from `langchain_nvidia_ai_endpoints`, which will enable us to interact with our remote `nvidia/nemotron-nano-12b-v2-vl` endpoint.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"8423d09247ffdef741b1ac0898e59f910e27d47bf2d26d46281e5320be10b26b","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"1b8551068d87fbe2136a0cb8b6c6bdcf20cbb3d6b246f1e7a7bff4178b31315b","type":"markdown"} -->
## Using langchain_nvidia_ai_endpoints
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"69b7bc7cb023e209ed948e15b1a2409578c63351fe142cca309d2813c7e0aaa6","type":"markdown"} -->
As you have observed from the last notebook, using OpenAI completions can lead to a lot of code repetition.

There has been a lot of effort from developers to utilize AI applications efficiently. Amongst them, [LangChain](https://python.langchain.com/v0.2/docs/introduction/) is a popular LLM orchestration framework that aids users to interact with LLMs easily.

LangChain’s simplistic architecture and abstractions let developers effortlessly replace components like language models, prompt, and processing steps, with little modification. In addition, LangChain provides a consistent, unified interface across multiple LLMs from different providers, simplifying interactions and allowing developers to concentrate on application development rather than dealing with model-specific complexities.

This library is highly popular and evolves quickly with advancements in the field. While there are many parts of LangChain such as LangGraph, LangSmith, and LangServe, we are going to focus on LangChain core in our workshop today.

In order to use LangChain with our locally-hosted model, we need to utilize a Framework Connector which ultimately converts an arbitrary API from its core into one that a target code-base would expect. We can do this by utilizing `ChatNVIDIA` class within `langchain-nvidia-ai-endpoints` package. With this tool, which uses the OpenAI API under the hood, we can start to iteratively develop and test out prompts more efficiently, and use LangChain with our NVIDIA NIM LLMs.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"5ae0ab97812847ab49f7cd5f5ae840143cf7f12e69cbbe385ecf53cc22688789","type":"markdown"} -->
## Setting Up a Model Instance With LangChain
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"069413744452e79c7118daee7796926f1ded54fbeb5a54a633f67b199c73e498","type":"markdown"} -->
To start using LangChain, we need to set up the ChatNVIDIA model instance. This involves configuring the base URL and model name, much as we did in the previous notebook with the `OpenAI` library.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"fe8a07f8e29704ed8c72091c34ce44956cd4b2a6331a6a6220553baac2abf3d3","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")

# Use the model selected in the course connection panel, or keep the lesson default.
model = os.getenv("NVIDIA_MODEL") or "nvidia/nemotron-nano-12b-v2-vl"
# model = "nvidia/nemotron-3-nano-30b-a3b"  # Compatible fallback; responses may differ.
# model = "meta/llama-3.3-70b-instruct"  # Legacy fallback; responses may differ more.

llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"da7784338409be6ba85b092eb39a92960c2361d300d2e6f34fc0c0fe44c31991","type":"markdown"} -->
You may have noticed we set a value called `temperature` to `0`. `temperature`. which is a floating point value between `0` and `1` is a way to control the randomness of a model's responses. When set to `0`, the LLM will always generate the text that it considers as having the highest probability of coming next. When set to higher values, it can generate text that is not necessarily what it considers to be the highest probability of coming next therefore introducing randomness and a sense of creativity in its generations.

We won't discuss modifying `temperature` to higher values in great detail, but remember, set it to `0` if you want deterministic responses, and set it higher if you want less deterministic (i.e. more creative) responses.

For those of you interested in learning more about how `temperature` and some other additional hyperparameters work, feel free to check out the appendix notebook, located in this directory, [99-Appendix-Hyperparams](99-Appendix-Hyperparams.ipynb).
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"acda783e7734faab168a0ebc2be264caa1a4069e45ea47bab08c3b6ede1de42a","type":"markdown"} -->
## Making a Simple Request
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"2b3780e0a0255538a8f455fbde4acb043e3666d36666b584ae4d2e35e5d8720c","type":"markdown"} -->
We can now start sending chat completion prompts to our model. We'll begin by using the `invoke` method, which we hope you'll agree is much easier to use than was the OpenAI client in the previous notebook.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"a7354fbb855ce0e700d672dc5d1dda834ead8d7cda97ede245ff21f3414a7cc0","type":"code"} -->
```python
prompt = 'Who are you?'
result = llm.invoke(prompt)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"9d02a11f5fafae47f0412a626583e85cefd1535002f40939a1a39c0ff9f9122f","type":"code"} -->
```python
print(result)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"e12fe99229dd5d9d7bee8be3f4944b6ccbeda38578d7f30138da8deced284705","type":"markdown"} -->
The result is similar to what we obtained using the OpenAI client, but it also includes metadata about the conversation and token usage. This will be useful for maintaining conversation context in more advanced applications.

To extract just the response from the model, we can simply use the result's `content` property, as below.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"f478732f64b4eb30f81a119110259e47a2d071f3ab2176501b3866aaf4389aff","type":"code"} -->
```python
print(result.content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"ff66f611fdc22d1564e99f097d70642aa3b1a21136cd6038cc847f83560a3a44","type":"markdown"} -->
## Exercise: Generate Your Own Completion
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"d8ff3c5bbe42b63aa1cd608d5b6e62f9a9de7776fa5709b13262f5e30facea21","type":"markdown"} -->
Use our existing model instance `llm` to generate and print a response from our local Nemotron Nano 12B-V2-VL model to a prompt of your choice.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"8ff30d3aa31de43bf4db10b77f500fade383899ee74f99b106a199e65281f436","type":"code"} -->
```python
prompt = 'Give me 3 puns having to do with LangChain.'
result = llm.invoke(prompt)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"f478732f64b4eb30f81a119110259e47a2d071f3ab2176501b3866aaf4389aff","type":"code"} -->
```python
print(result.content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/13-Hello-LangChain:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"8007b516b042c812da3f0be4437a61ab46e486dad1ccf3ac7442a8a1fd1400c6","type":"markdown"} -->
You should now be able to use LangChain to generate chat completions and parse out the model response.

In the next notebook, you'll go a little further into using chat completions with LangChain by learning how to stream model responses and handle multiple chat completion requests in batches.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>1-Intro-to-Prompting/14-Streaming-and-Batching.ipynb</code> next: <strong>Streaming and Batching</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Remember one place where the framework wrapper simplified the call, because the next notebook asks you to balance that convenience against response timing and throughput.</p>
</div>
<!-- /dli-course-cell -->
