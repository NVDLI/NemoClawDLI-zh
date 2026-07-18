<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"e351932cb9a9ef039fac9c4938b45fca9ed74233555149f707392fae3e73f2d1","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Prompt Templates</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"424564c68c5715bec8f9d5824ae601b4563a44dbdc28ca19ad07150821ed0bd1","type":"markdown"} -->
In this notebook you'll learn how to capture reusable LLM functionality in prompt templates, and begin working with the powerful prompt template tools provided by LangChain.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"026255eb45e17c33524e00bc1e8497ca994f84092f69e0a89b52266a261a7d0d","type":"markdown"} -->
By the time you complete this notebook you will:

- Appreciate the need and ability to capture LLM-related tasks in prompt templates.
- Be able to create reusable prompt templates with LangChain.
- Use prompt templates to perform a variety of LLM-powered tasks on a collection of provided text samples.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"edec1de5589f139503932e3b385d8bbd703ed9c32dd20441d2052ed437304688","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"fe8a07f8e29704ed8c72091c34ce44956cd4b2a6331a6a6220553baac2abf3d3","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")

# Use the model selected in the course connection panel, or keep the lesson default.
model = os.getenv("NVIDIA_MODEL") or "nvidia/nemotron-nano-12b-v2-vl"
# model = "nvidia/nemotron-3-nano-30b-a3b"  # Compatible fallback; responses may differ.
# model = "meta/llama-3.3-70b-instruct"  # Legacy fallback; responses may differ more.

llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"72d011d491d2486fcc1ba424809581a0f83f990e300612a941020b174b062b11","type":"markdown"} -->
## One-off Tasks vs. Reusable Functionality
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"b47855980e0b742ca752eb65fb82cc0d5bb8fab192cdaa5768d7dcca8d6a5ade","type":"markdown"} -->
If you are the end user of an LLM-based application, especially a chatbot like Perplexity or ChatGPT, then you may very well undertake a process of iterative prompt development to elicit a response from the LLM-based application that is helpful to you. If, however, you are engineering prompts for use in an LLM-based application that you are building, it is often the case that you want to develop a prompt that captures some task or functionality, and that can be reused with a variety of inputs.

As a developer you are already deeply familiar with the progression from one-off tasks to more generalized, templated functionalities. There are many ways you do this, but as a simple and universally relatable example consider the following example of calculating the products of 2 numbers.

If you just needed to perform a calculation in a one-off manner for yourself, you could simply write a line of code like the following:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"512d8a2e035073af47004e7882f52d96db4e87197ad381f95c369d64191fa248","type":"code"} -->
```python
99 * 64
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"6f0151ca70554cd11187ee068d18a041aae971162b18b4c15c9233c422b9034a","type":"markdown"} -->
If however, you wanted to capture some more general functionality, say multiplying two numbers together, and wanted this functionality to be able to be reused across a variety of inputs, you would write something like the following function:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"1c8f6a0db8aafc142b9ec4d1d1e34bcbe13f4e22c02e503f4ed8789838613f4a","type":"code"} -->
```python
def multiply_two_numbers(a, b):
    return a * b
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"2e4f04a9cf5945da3463416e5d2637adcc60fdf115a90ccfeb5e49ddfbe07162","type":"markdown"} -->
At this point not only could you do the orignal calculation,...
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"8d6fb4150f507d3957a46d514ebbbcb5b312bff0e7ed4a864c52cea614bc9a7d","type":"code"} -->
```python
multiply_two_numbers(99, 64)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"d22ef70bb50b62256b61509ae1740d8b55037492083b0457de2065ef30c7e4f9","type":"markdown"} -->
...but you can reuse the function for an arbitrary number of calculations, including those deemed useful users other than yourself.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"d3900fcdd042ca4b0f87018ec5377fee2a36ddf478e478c3280ec80195de775b","type":"markdown"} -->
## Prompt Templates As Reusable Functionality
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"a5ffc4076f2005bbb98693380429343134f2e4e620c4030afd13a82eaa981124","type":"markdown"} -->
Prompting is not so different. If you have a one off task, you just write a prompt for it:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"bd79e5ac97d269c8500cf75c851cbd18bfe338924e091205b3e9c7ddd1ce8bb1","type":"code"} -->
```python
one_off_prompt = "Translate the following from English to Spanish: 'Today is a good day.'"
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"90f2981adb0bf45e2bb3d27e0e600cd1ed837c14c31ee1b07634cfa3cc182a65","type":"code"} -->
```python
print(llm.invoke(one_off_prompt).content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"cbb06242989037237c20b78fb552a0e671aa7af160f064e53f1162be318bed81","type":"markdown"} -->
If, however, you'd like to create reusable functionality, you might abstract part of the prompt away into arguments so that you're left with something you could reuse with arbitrary inputs, like the following:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"9ad5f5e7e61e504c0eafe749fdcbeaf6773c7b076801239fdd05f31ebeb86b8f","type":"code"} -->
```python
def translate_from_english_to_spanish(english_statement):
    return f"Translate the following from English to Spanish. Provide just the translated text: {english_statement}"
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"db1b6cacb58b7c7e1e6ee906a38411e2d8eca776176b93699e59991e07a12cbb","type":"code"} -->
```python
english_statements = [
    'Today is a good day.',
    'Tomorrow will be even better.',
    'Next week, who can say.'
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"e97bf7e7b852149e6740c5eab035912ecc8e495d7ce78df5920a78d315c8ed4f","type":"code"} -->
```python
prompts = [translate_from_english_to_spanish(english_statement) for english_statement in english_statements]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"eb7526362ee7678cb5650f67d90cfdb84485363ca148ff3993ded032560941fb","type":"code"} -->
```python
prompts
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"843c8664225827882c79dc1b5e9a3dda7dac3263d1147019545fe92119ce2fc8","type":"code"} -->
```python
translations = llm.batch(prompts)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"54d7f05681b7a0d76d7b6054d025d8bf99a0df0ad3c0a3b72f25f7b45ff31e67","type":"code"} -->
```python
for translation in translations:
    print(translation.content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"4f6ca9d8bd297f5ca9cc29f454f8d8fe4df441280befbf2a7cee0381f07cf9bd","type":"markdown"} -->
Our `translate_from_english_to_spanish` function therefore creates a **prompt template** that capture the functionality of translating an English statement to Spanish.

Of course we could abstract even more out of our prompt and create an even more general template, if we wish:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"f8a2c4c012b9a55e6713d3b9c3b0fadab16cea39dd376bee037ce62f1b6f98e9","type":"code"} -->
```python
def translate(from_language, to_language, statement):
    return f"Translate the following from {from_language} to {to_language}. Provide only the translated text: {statement}"
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"f21ce5a87225851ce767b9bdae0594f1139bdd6db448c5a3a1ff1006b65f055b","type":"code"} -->
```python
print(llm.invoke(translate('English', 'French', 'Computers have many languages of their own')).content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"68e6d889c625d733bbb1e039818a1ec327dc19910b6e6fd5a85e0c3fab2d14f1","type":"markdown"} -->
## LangChain's `ChatPromptTemplate.from_template`
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"097f070fb01ab27c351bd0b6875e76aab849aad9773b37ca43c9139572be322a","type":"markdown"} -->
There's nothing inherently wrong with developing your own conventions for creating prompt templates, but LangChain ships with a very large collection of templating mechanisms that are easy to use, flexible, well-maintained, and widely adopted.

We will start with perhaps the most basic way to create prompt templates for a chat model `ChatPromptTemplate.from_template`. First we need to import `ChatPromptTemplate` into our environment.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"fdfac60f8984a342fef23a94776dc68777fcf753b7122670d24b0af5816eb004","type":"code"} -->
```python
from langchain_core.prompts import ChatPromptTemplate
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"45116258e169bff5ab909d32b63ee50fd9096844ceb15eb9b2b0b58c99a5be71","type":"markdown"} -->
We can now create a template, very much like we did above through the creation of a function. Let's revisit creating a template for translating an English statement to Spanish.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"f0853d9f4d79a7066891f31063c0f0d4ff830c2f96a8912ba92d29ed7af9f072","type":"code"} -->
```python
english_to_spanish_template = ChatPromptTemplate.from_template(
    "Translate the following from English to Spanish."
    " Provide only the translated text: '{english_statement}'"
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"1c6087e4afd75820e7761ce815aad311b082d92d85e8b850a4ec20e94a0b39c6","type":"markdown"} -->
As you can see, this is pretty much identical to the f-string we returned in our `translate_from_english_to_spanish` function above.

To create an actual prompt from the template, we use the template's `invoke` method.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"79a4c7c376b36dd2f2c789ea11dffc85f94b66f8dddeb403005c598f9b63d662","type":"code"} -->
```python
prompt = english_to_spanish_template.invoke("Today is a good day.")
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"1f27afc35735441fb3334852247c316d563dd166d52b95296b16ea6b59981f1a","type":"markdown"} -->
At which point we can now pass it into our LLM as we have been.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"56209e7a78254215b2f26f0a2ad9739804ac8f0df09c1e51f6d609d51b772e54","type":"code"} -->
```python
print(llm.invoke(prompt).content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"ac3acede7d12c6d117dfdadc85cb1334b49ea5bf5959739234e1f63b7e9804ba","type":"markdown"} -->
## Chat Prompt Template Details
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"1ac7facc3f4246cb3709c693c0425fb7d012525901457475f98bb07925a097cc","type":"markdown"} -->
If we look more carefully at the prompt we just created from the template, we'll see that there's a bit more going on than the creation of a string:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"b5c9750e286de9900b8a07d6bb673207ccf77f3332279cd377651070b7cf194f","type":"code"} -->
```python
print(prompt)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"3935ae1e4550d8381bbc76bf612f57b7747b8f911d48ac68b2eadc03e14b767c","type":"markdown"} -->
Under the hood, it would appear that LangChain is constructing a list of `messages`, and specifically, a `HumanMessage` whose `content` is the string prompt we intended to create.

You'll be learning a lot throughout the workshop about `messages`, including `HumanMessage`s, but for now, recall from an earlier notebook when you began interacting with our local LLM with the `OpenAI` library that we had to take care to interact with the **chat** completions endpoint, given that we are working with a chat model, and that when constructing our prompt, we had to include some additional structure to our prompt, including the creation of a `messages` list and the specification of our prompt as being associated with a `user` role. Here's a reminder from that previous notebook:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"5f2852233f644af8fa14ee63c677195caea58fd1542bd81984bcf36d56fdb02a","type":"markdown"} -->
```python
response = client.chat.completions.create(
    model=model,
    messages=[{'role': 'user', 'content': prompt}]
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"b68eae72a13f8c2c1c22e1a4d7bb91f771d7fb9d4220212bf3e7172909125354","type":"markdown"} -->
The important thing for you to understand now, is that when working with chat models specifically, the model expects interactions via messages in a turn-based structure where for each message, it is associated with a specific role like AI assistant, human user, or others.

One of the great things about working with LangChain is that a lot of the specific formatting required to adhere to the expectations of working with a chat model are taken care of for you, but at the same time, when needed, you can drill down for full control of your program.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"533a6a21d16357541477b592f8ceee5e51ad7eb4eb69bcdd221371bd45012967","type":"markdown"} -->
## Prompt Templates for Multiple Values
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"4147b3f4d860ad360b8dd135f3f8f73050dc53df0df09058ce072b741f9d057c","type":"markdown"} -->
For reference, here is the template we created above to translate a statement from English to Spanish, as well as its use with our local LLM.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"822abd83043d7667f5818261ee30992aa72aea3c5083f657bf715724585e5ae9","type":"code"} -->
```python
english_to_spanish_template = ChatPromptTemplate.from_template(
    "Translate the following from English to Spanish."
    " Provide only the translated text '{english_statement}'"
)

prompt = english_to_spanish_template.invoke("Today is a good day.")

print(llm.invoke(prompt).content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"b2a4134e768c9326ad0c5bc7f1ce302db2d6abcf9aee7e93adbe7a3b871db9aa","type":"markdown"} -->
You may have noticed when calling `invoke` on the template, that we passed in a single string...
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"f76930d18a7fc0648dee05ff669f2da87b2f7f3ee89de50a6043d1ef295a164f","type":"code"} -->
```python
english_to_spanish_template.invoke("Today is a good day.")
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"c2c6ed02351d0059ab96d0af7e7d8c43d212bced76ef358054424685ab18ed6a","type":"markdown"} -->
...which in this case was fine since the template `"Translate the following from English to Spanish: '{english_statement}'"` was only expecting a single value, namely, `english_statement`.

When invoking templates that expect multiple values, and in fact as a best practice even for templates that expect a single value, instead of passing in a string, we pass in a `dict` that maps the template placeholders to their intended values. Thus, a better way of invoking our template would be:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"84d8896bda134ddee4cef148d64adace5da4145b64b7b7ea90b23274ad4da0be","type":"code"} -->
```python
english_to_spanish_template.invoke({"english_statement": "Today is a good day."})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"422ed4d171aeea5603b4f0cbca96db3dac59af51cafc09f32eaafc2b65c51598","type":"markdown"} -->
...which as you can see results in the same prompt.

Specifying which string maps to which placeholder via dictionary items becomes essential when working with prompts that expect multiple value. Here we demonstrate the creation and use of our more general template from above that allows for the translation from and to arbitrary languages.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"0520dd12f5ab486b98c2c01fd6b19175e75144ab1687671827c7404c3ea1bd02","type":"code"} -->
```python
translate_template = ChatPromptTemplate.from_template(
    "Translate the following from {from_language} to {to_language}."
    " Provide only the translated text: {statement}"
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:62","index":62,"schema":"dli-course-cell/1.0","source_sha256":"847e9a266a96712387a43d56c56b669418ae591b6770e5ccc036dc5a841331d5","type":"code"} -->
```python
prompt = translate_template.invoke({
    "from_language": "English",
    "to_language": "French",
    "statement": "Sometimes a little additional complexity is worth it."
})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:63","index":63,"schema":"dli-course-cell/1.0","source_sha256":"56209e7a78254215b2f26f0a2ad9739804ac8f0df09c1e51f6d609d51b772e54","type":"code"} -->
```python
print(llm.invoke(prompt).content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:64","index":64,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:65","index":65,"schema":"dli-course-cell/1.0","source_sha256":"591533b129f1c7afacd15e1f4362db84b4cebef0c61be02751d16f838a7fb6a4","type":"markdown"} -->
## Exercise: Create Prompt Templates
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:66","index":66,"schema":"dli-course-cell/1.0","source_sha256":"aadf9debc87536e5d5a2f0efb0feb8254a3edd0124cdf937ccf005f0df03f4ce","type":"markdown"} -->
This exercise is a little longer than previous exercises and will conclude this section. For it, you are going to capture 3 LLM-related tasks into prompt templates, and apply each of these tasks to a list of statements we will provide you.

The LLM-related tasks you should create templates for are:
- Sentiment analysis: ascertain whether the overall sentiment of a given piece of text is 'positive' or 'negative'.
- Main topic identification: identify and state the main topic for a given piece of text.
- Followup question generation: generate an appropriate and interesting followup question that will clarify some aspect of a given piece of text.

Please use `statements` immediately below as the pieces text you should use for each of your templates. Upon completion you should be able to perform 3 LLM-related tasks on all 5 pieces of provided text.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:67","index":67,"schema":"dli-course-cell/1.0","source_sha256":"86f037fc5fd934fff591b13e3198018e622abc99507d58d799f5d57b9dfa449d","type":"code"} -->
```python
statements = [
    "I had a fantastic time hiking up the mountain yesterday.",
    "The new restaurant downtown serves delicious vegetarian dishes.",
    "I am feeling quite stressed about the upcoming project deadline.",
    "Watching the sunset at the beach was a calming experience.",
    "I recently started reading a fascinating book about space exploration."
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:68","index":68,"schema":"dli-course-cell/1.0","source_sha256":"5304b045a0f5093b6ef94c71b381623e79cf2f546bdd8168a56faeea996f31c7","type":"markdown"} -->
If you're up for the challenge, feel free to begin your work straightaway. If you'd like some assistance, click on *Walkthrough* below to expand a step by step walkthrough of the exercise.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:69","index":69,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:70","index":70,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"markdown"} -->
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:71","index":71,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:72","index":72,"schema":"dli-course-cell/1.0","source_sha256":"ab4647b3a89a95fdc30036524ef700d4028f35820e6aaa60e1cafdeed7efb9c0","type":"markdown"} -->
## Walkthrough
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:73","index":73,"schema":"dli-course-cell/1.0","source_sha256":"f15f2cd2561e1f0e1943bee10303e9ebe7e2ed8f30830d647970c2eb47a27113","type":"markdown"} -->
### Prompt Template for Sentiment Analysis
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:74","index":74,"schema":"dli-course-cell/1.0","source_sha256":"9a39470f3fdc8469dd8133fc52950e3cf7d4b98a66eff16efd0e6982785cbc32","type":"markdown"} -->
Start by constructing prompt templates for each of the LLM-related tasks we'd like to accomplish, beginning with a prompt template for sentiment analysis.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:75","index":75,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:76","index":76,"schema":"dli-course-cell/1.0","source_sha256":"82cb874a6c89b5cc49b6a32377ca2ecbf2dd438dba2dce7c0394d82be32aeb27","type":"code"} -->
```python
sentiment_template = 'TODO'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:77","index":77,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:78","index":78,"schema":"dli-course-cell/1.0","source_sha256":"983f547953a25de9240f597a89592e4f9de01625fbfef03dfda8be8aeafb297f","type":"code"} -->
```python
sentiment_template = ChatPromptTemplate.from_template("""In a single word, either 'positive' or 'negative', \
provide the overall sentiment of the following piece of text: {text}""")
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:79","index":79,"schema":"dli-course-cell/1.0","source_sha256":"16dc7da5c21060877ee099a1ad1ef7de6961a002cb8872c15a828785fc8ac01c","type":"markdown"} -->
### Prompt Template for Main Topic Identification
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:80","index":80,"schema":"dli-course-cell/1.0","source_sha256":"e9878389821ec5ffb4ad1d04377c93e94619ae75443ae55114464103db665c9a","type":"markdown"} -->
Next create a prompt template for main topic identification.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:81","index":81,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:82","index":82,"schema":"dli-course-cell/1.0","source_sha256":"4151203dfd923e87dd9a546408e3a609e0630234053652a49714c03574dc5cdf","type":"code"} -->
```python
main_topic_template = 'TODO'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:83","index":83,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:84","index":84,"schema":"dli-course-cell/1.0","source_sha256":"e448e1da942e2d0272885fc536496267218031000d7ca0b167863f996550d870","type":"code"} -->
```python
main_topic_template = ChatPromptTemplate.from_template(
    "Identify and state, as concisely as possible, the main topic"
    " of the following piece of text. Only provide the main topic and no other helpful comments. Text: {text}"
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:85","index":85,"schema":"dli-course-cell/1.0","source_sha256":"513fecdb260f2b02af90506c995c9b17b8ea02359c612abe640d20e2f90c39aa","type":"markdown"} -->
### Prompt Template for Followup Question Generation
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:86","index":86,"schema":"dli-course-cell/1.0","source_sha256":"62971acf6b93a710432fa3ed8c143ecf7eb8490e8977f823437aa2cd9c4cbee7","type":"markdown"} -->
Next create a prompt template for generating a relevant followup question.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:87","index":87,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:88","index":88,"schema":"dli-course-cell/1.0","source_sha256":"74b8b4a72904a8d99c5c069b05e0d475a36e525b653e40b06c073f6e669792f2","type":"code"} -->
```python
followup_template = 'TODO'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:89","index":89,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:90","index":90,"schema":"dli-course-cell/1.0","source_sha256":"06303ef4743be0bdb29d1b7061f0745ce8ab03a35699108cce6859ad4d9260aa","type":"code"} -->
```python
followup_template = ChatPromptTemplate.from_template(
    "What is an appropriate and interesting followup question that would help"
    " me learn more about the provided text? Only supply the question. Text: {text}"
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:91","index":91,"schema":"dli-course-cell/1.0","source_sha256":"f9935ad3278272b816b58eefac19787e8a696c24d7ddf249808f6d2b64940d9a","type":"markdown"} -->
### Create Lists of Prompts for Future Batching
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:92","index":92,"schema":"dli-course-cell/1.0","source_sha256":"32769719ad31e70417d07122b6d235614ee53b07024f1610306b7b742afb9ea5","type":"markdown"} -->
In order to generate batched responses for each of our 3 LLM-related tasks, we will need a list of prompts for each task.

For this step of the exercise, use `statements` (defined above) in conjunction with each of the prompt templates you just created to create a list of prompts for each of the 3 LLM-related tasks you'd like to accomplish.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:93","index":93,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:94","index":94,"schema":"dli-course-cell/1.0","source_sha256":"780ea88635b261aac8ebecd6cf50df6426c3cf3b0c2e340d61d2d7bfc506f9dd","type":"code"} -->
```python
sentiment_prompts = [] # TODO: populate with sentiment analysis prompts for each statement in `statements`.
main_topic_prompts = [] # TODO: populate with main topic prompts for each statement in `statements`.
followup_prompts = [] # TODO: populate with followup question prompts for each statement in `statements`.
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:95","index":95,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:96","index":96,"schema":"dli-course-cell/1.0","source_sha256":"9690b28d9473a7a0c14c940dc5205434a5e61da53126732ab763135f29f7a805","type":"code"} -->
```python
sentiment_prompts = [sentiment_template.invoke({"text": statement}) for statement in statements]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:97","index":97,"schema":"dli-course-cell/1.0","source_sha256":"a5a40c870d4ef537dfd3c4e38a476adfbc11329a38062ce1ea81ae0fb0d8919a","type":"code"} -->
```python
main_topic_prompts = [main_topic_template.invoke({"text": statement}) for statement in statements]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:98","index":98,"schema":"dli-course-cell/1.0","source_sha256":"3404257a7922630b2ff14e2f77d5419082976e13a912133e8261db67672cf8ad","type":"code"} -->
```python
followup_prompts = [followup_template.invoke({"text": statement}) for statement in statements]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:99","index":99,"schema":"dli-course-cell/1.0","source_sha256":"489bfb567fb76e1852473a1a583465799aae410f53ce4186ff8eb17f1b83dff2","type":"markdown"} -->
### Generate Responses for Each LLM Tasks Using Batching
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:100","index":100,"schema":"dli-course-cell/1.0","source_sha256":"dd8d5540a5240ed0cc2a813b82126c634ac2f2d1fdc03727a8f940941dd9c5e8","type":"markdown"} -->
Use batching to call the LLM with each of your constructed prompts, once for each task.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:101","index":101,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:102","index":102,"schema":"dli-course-cell/1.0","source_sha256":"61c24276c37e8d11700694a3c1d2615c9b420e686aed59a43d3f3394d6f1da54","type":"code"} -->
```python
sentiments = [] # TODO: use the LLM to populate this list with the sentiment of each statement in `statements`.
main_topics = [] # TODO: use the LLM to populate this list with the main topic of each statement in `statements`.
followups = [] # TODO: use the LLM to populate this list with a followup question for each statement in `statements`.
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:103","index":103,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:104","index":104,"schema":"dli-course-cell/1.0","source_sha256":"59630e7f5f4befeab1412fa9cdb92b170ca542cf03394707036d2a0078fe2e2f","type":"code"} -->
```python
sentiments = llm.batch(sentiment_prompts)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:105","index":105,"schema":"dli-course-cell/1.0","source_sha256":"56eee8892365ff0a72afb09014c55ceb261a3d3f672cb937d697bbfa7194c24f","type":"code"} -->
```python
main_topics = llm.batch(main_topic_prompts)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:106","index":106,"schema":"dli-course-cell/1.0","source_sha256":"cff94265d55dac4e03724317b749c8ea3459824b3e02d2f8bde6ea9b89a669d3","type":"code"} -->
```python
followups = llm.batch(followup_prompts)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:107","index":107,"schema":"dli-course-cell/1.0","source_sha256":"4658929aba08ec299419a5311cc15cad8971bdee768ea77b662968912fdf571e","type":"markdown"} -->
### Print Results
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:108","index":108,"schema":"dli-course-cell/1.0","source_sha256":"2cc0874ed3b5ee678cc45397d64170d76af74a8f1882364efecfcb255d6ae95b","type":"markdown"} -->
Finally, loop over the original statements and all the model responses for the various topics to make a nice print out of everthing.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:109","index":109,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:110","index":110,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:111","index":111,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:112","index":112,"schema":"dli-course-cell/1.0","source_sha256":"b188dea3b4c0d36f7d21cea432dfba4b194ae87ec3ae64dc18a77e68447d40e5","type":"code"} -->
```python
for statement, sentiment, main_topic, followup in zip(statements, sentiments, main_topics, followups):
    print(
        f"Statement: {statement}\n"
        f"Overall sentiment: {sentiment.content}\n"
        f"Main topic: {main_topic.content}\n"
        f"Followup question: {followup.content}\n"
    )
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:113","index":113,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:114","index":114,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/16-Prompt-Templates:115","index":115,"schema":"dli-course-cell/1.0","source_sha256":"cc608691dee47f4424e77f3268fd394f50d2c57c921683bbd44c589a6d179cc4","type":"markdown"} -->
Through a combination of capturing LLM-related functionality in prompt templates, and batching calls to a chat model, you're already starting to peform legitimate work. Even with what you know thus far, it's not hard to see how you could easily extend it to create a serious amount of LLM-powered analysis and text generation on large collections of textual data.

However, we are just getting started. In the next notebook we are going to introduce something called LangChain Expression Language (LCEL) which will enable you to create concise but powerful chains of LLM application functionality. As you'll see, using LCEL chains will allow us to create functionalilty, much like you did in the previous exercise, much more efficiently.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>1-Intro-to-Prompting/99-Appendix-Hyperparams.ipynb</code> next: <strong>Appendix: Explore Hyperparameters</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Save one template input-output pattern you trust, then use the appendix to see how generation settings change behavior around that same contract.</p>
</div>
<!-- /dli-course-cell -->
