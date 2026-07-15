<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"a280559c9c97b46f946a71c79de8fff5c8d42409ef6c55b4e8578db5104343c8","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Hello World with OpenAI Library</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"12042590cc5ae7c1fdb263d65628003d0ad800e91b701a1f32b329d48991cf77","type":"markdown"} -->
In this notebook, we will learn how to interact with the OpenAI API to generate text completions using the Nemotron Nano 12B V2-VL model. This introductory section will help you understand the basics of setting up and using the OpenAI library for interacting with LLMs.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"e9ce0846e662b77700f07fff807737857c44d04563643b591f710f701c0f99ce","type":"markdown"} -->
By the time you complete this notebook you will:

- Understand how to set up and use the OpenAI library.
- Generate text completions using the Nemotron Nano 12B V2-VL model.
- Learn to interpret and utilize the API response.
- Understand the importance of using *chat* completion endpoints with chat models like Nemotron Nano 12B V2-VL.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"42cb2fdb8cb6d920f7bff5f611416e2d39bfbad26d93080a56a432806a768afa","type":"markdown"} -->
Here we import the `OpenAI` library, which will enable us to interact with the NVIDIA API Catalog. The API Catalog exposes an OpenAI-compatible API, making it easy to work with using familiar tools.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"512269926580fca04519ff1a17cf30319473cc788e60b2b676cf99979c256a16","type":"code"} -->
```python
import os
from openai import OpenAI
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"19232c45e3540e645664b8b0faf7064c9a85328381cf6b793c0ba76c70dacae4","type":"markdown"} -->
## Setting Up the OpenAI Client
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"c83c03ab04f7a4176c89e4633c78b8c36347333509577e96bcc2063b964c04c8","type":"markdown"} -->
To start using the API, we need to set up the OpenAI client. This involves configuring the base URL and providing an API key.

In this course environment, the connection details have already been configured as environment variables, so we can simply retrieve them:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"2b850ab590b7d45e1b46139fe9a9c09d0b300a49c24d3babe3da015422dcc174","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"9f0567470165cc2ad7b1a5f488cd63e9cd9e7b2e6af8b3057aea53e8aa86a6df","type":"markdown"} -->
The API key is also provided via environment variable. While you could use your own API key from [build.nvidia.com](https://build.nvidia.com/explore/discover), we've pre-configured one for this course:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"377d84c52fbebac5ab7e9c797b9b0a20f7626bf73a75325872ca3e2be9092839","type":"code"} -->
```python
api_key = os.getenv("NVIDIA_API_KEY")
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"5d3943cb8a2cfbc34eb4fff7490c083b67174245b8b78913331347b0184cd1cf","type":"markdown"} -->
With a `base_url` and `api_key` we can now instantiate an OpenAI client.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"57d756f96f4779fb21a5c319bd066d2bfa70ad78659eba3dbda4eef2c275d124","type":"code"} -->
```python
client = OpenAI(base_url=base_url, api_key=api_key)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"1ca5234cf5a9e2731062ae4b6cf7262dc652010095b31d0f1c86c7404e451803","type":"markdown"} -->
## Observing Available Models
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"978c8096a0073fac17ec16321e1ea7506ce5ce9fb8291d80e9a98f7f18916b18","type":"markdown"} -->
Now that we've created an OpenAI client, we can use it to observe the models available to us using a call to `client.models.list()`. The NVIDIA API Catalog provides access to many models, including the Llama 3.1 8B Instruct model we'll be using in this course.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"6b0daf186af02abf92b6681508b0b7c125142abea26ba7fdb41cb18631d3bedf","type":"code"} -->
```python
available_models = client.models.list()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"198a49a9094af97aab297a884bd7327b867cca0f7908c37136ed7ab10f626a25","type":"code"} -->
```python
available_models.data
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"96f790d41ead4cb1675963b4c805084cdb51cb9536d61ebc0aedacea1a4a8aa2","type":"markdown"} -->
There's a lot of information here that we are not concerned with, but if we drill into the object a little we can see more clearly the model we have available through the client:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"91514a14691b22de13849d6628687b676ef8fe885862826b1dd4875df99cf4bc","type":"code"} -->
```python
## Accessing Single Value:
# available_models.data[0].id

## Python List Comprehension: Read it out loud
[
    model_card.id
    for model_card in available_models.data
    if "nvidia" in model_card.id
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"dce6be5682b90c56c4a22412bfc9b0f32516a22710cf6f0971a98f0c97efc61f","type":"markdown"} -->
## Making a Simple Chat Completion Request
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"8723e896d51940ec35e4e9a5c1efdd743d409dfe21c5ef52a129352ecebe580a","type":"markdown"} -->
With the `client` instance now created, we can make a simple request to generate chat completions by using the `client.chat.completions.create` method which expects a `model` to use for the completion, as well as a list of `messages` to send to the model. We will be discussing the details of the `messages` list in more detail below, but for now we will pass in a simple single message containing a prompt from the user (you) asking for a fun fact about space.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"99eb92acd74350fc25a8e7685ba7f48e74d8e0a1e53ec8c9ac0065ca41837b7f","type":"code"} -->
```python
model = 'nvidia/nemotron-nano-12b-v2-vl'
prompt = 'Tell me a fun fact about space.'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"8208eaf0633e3a9304ba8a8e55dd07da6cfd7ece48373e804d34f155dba59297","type":"code"} -->
```python
response = client.chat.completions.create(
    model=model,
    messages=[{'role': 'user', 'content': prompt}]
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"892d16162fd815cfb5ab42e567238c4bede9887e89cc55c21932b5a5df699973","type":"code"} -->
```python
print(response)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"7a0e0dae350606059d49291ffb9d9e86ff5a22f7dde70c7577d6f77b8c6ae260","type":"markdown"} -->
There's a fair amount of information provided in the API response, but the part we are most interested in is the response from the model.

Here we parse just the model's generated response out of the full API response.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"6ed0555ef14cc7ec38d913b03e93fdbde07cad97f6bc1b0d4d68ccc35d841a1c","type":"code"} -->
```python
model_response = response.choices[0].message.content
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"b4b9e9ff8565fd810eac7dade836c057e1d914e39bc2f9f71d1a8ed2930a750c","type":"code"} -->
```python
print(model_response)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"1286b1c9a130d6527ff9ff5ac6778410065d7df269b8c429eb3e5b5000debb59","type":"markdown"} -->
## Exercise: Create Your First Prompt
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"300beafe0ed675e177264d2261a271d23c0c1dbcde83256259cc654cf676734a","type":"markdown"} -->
Use our existing OpenAI API `client` to generate and print a response from the Nemotron Nano 12B V2-VL model to a prompt of your choice.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"38dd55740c7426e4bc880639d1840a1f559e8120bc54394e7a7a3f45aced080b","type":"code"} -->
```python
prompt = 'What is the OpenAI API?'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"8208eaf0633e3a9304ba8a8e55dd07da6cfd7ece48373e804d34f155dba59297","type":"code"} -->
```python
response = client.chat.completions.create(
    model=model,
    messages=[{'role': 'user', 'content': prompt}]
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"6ed0555ef14cc7ec38d913b03e93fdbde07cad97f6bc1b0d4d68ccc35d841a1c","type":"code"} -->
```python
model_response = response.choices[0].message.content
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"b4b9e9ff8565fd810eac7dade836c057e1d914e39bc2f9f71d1a8ed2930a750c","type":"code"} -->
```python
print(model_response)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"17639f3d4dff4b80fddcc65caf720508c5c8f9d37b091cccbbd5edea8b8f9351","type":"markdown"} -->
## Understanding Completion and Chat Completion Endpoints
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"bab9538e6dd6518a47066348bf0d774c7b0536bbe65ec74fbde3c5c069b5c9f4","type":"markdown"} -->
We have been working with the `chat.completions` endpoint, but when working with the OpenAI API, you also have the option to use the `completions` endpoint. Understanding the differences between these endpoints is crucial, as they handle prompts and generate responses differently, even for a single prompt.

The `chat.completions` endpoint is designed to handle multi-turn conversations, keeping track of the context provided by previous messages. It generates more concise, focused responses by anticipating a back-and-forth interaction, even if only a single prompt is provided.

The `completions` endpoint is designed for generating a response to a single prompt without maintaining conversational context. It aims to complete the prompt that was given to it, rather than respond to it conversationally.

The main takeaway is that when working with OpenAI-compatible chat models such as `nvidia/nemotron-nano-12b-v2-vl`, use `chat.completions` and not legacy `completions`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/12-Hello-OpenAI:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"ea66e8de9eb0cb7d2b36203cb668cf51d4462238ad5676917198b83329a12a30","type":"markdown"} -->
By completing this notebook, you should now have a basic understanding of how to use the OpenAI library to generate chat completions, and parse out the model response. This foundation will prepare you for more advanced topics and techniques in prompt engineering.

In the next notebook, we will explore how to use LangChain to interact with language models, which will provide more flexibility and advanced capabilities for managing and generating text.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>1-Intro-to-Prompting/13-Hello-LangChain.ipynb</code> next: <strong>Hello World with LangChain</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Keep one minimal request and response shape handy, so you can compare what the LangChain wrapper changes and what it leaves alone.</p>
</div>
<!-- /dli-course-cell -->
