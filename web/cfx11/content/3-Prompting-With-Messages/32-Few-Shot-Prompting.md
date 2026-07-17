<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"e163c792b8086517b5ce63bd1aa4243c7e5c115567d960a053507d3a5eac7112","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Few Shot Prompting</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"bad31a7cac7ed92d4ca9825e613ccdb74421beebc9d2a843d9825a169a5bc491","type":"markdown"} -->
In this notebook you'll learn how to provide chat models with instructive examples by way of a technique called few-shot prompting.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"8a9cf4aeece6618033f768b306d799ef9b4d18c73c4acff8a3b48bce2877df53","type":"markdown"} -->
By the time you complete this notebook you will:

- Understand how to perform few-shot prompting.
- Observe the effect and limitations of the few-shot prompting technique.
- Learn methods for efficiently creating and editing few-shot prompts.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"d9b59ef3558a9de722df09e94b872e2bd444da74469399cf645fd5cf8c79952e","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"fe8a07f8e29704ed8c72091c34ce44956cd4b2a6331a6a6220553baac2abf3d3","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")

# Use the model selected in the course connection panel, or keep the lesson default.
model = os.getenv("NVIDIA_MODEL") or "nvidia/nemotron-nano-12b-v2-vl"
# model = "nvidia/nemotron-3-nano-30b-a3b"  # Compatible fallback; responses may differ.
# model = "meta/llama-3.3-70b-instruct"  # Legacy fallback; responses may differ more.

llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"d4b39a33e00aacd29e9f46848de0782b481452bb5e53cf17e6e38d5e2b8afb13","type":"markdown"} -->
## Few Shot Prompting
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"286c7010dda07d031c34d899fcccf0bec868466e0536f532f2478752f25f6ff0","type":"markdown"} -->
We can provide example human / AI interactions as a part of our prompt to influence the behavior of the model's responses. Let's create a simple chain to begin playing around with this idea.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"2f319c2cf70821f247d7443f16c711eaeb1f476e0597da803bc0861e8df5f6fd","type":"code"} -->
```python
prompt_template = ChatPromptTemplate.from_messages([
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"a45d5e7d2a81f7cdc07183c70e44e42aa65c9d434cd853383f168af4980f7d4d","type":"code"} -->
```python
parser = StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"5e3351496bdf4abbc4217ad2c88cf46ba4197e1e5d1f6b44fd3c5a8819947363","type":"code"} -->
```python
chain = prompt_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"ca3b22d576deca2a066ee75af1c26e3ed542ce063fd56476b08d507a6663fb32","type":"markdown"} -->
Let's say, for some reason, we want the model to repeat back to us whatever we say, but in all capital letters. We could do the following.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"ae8cb9546952ab52c18382a5b4f928aa46cd6ea1f2850650d8f311fb4a29110f","type":"code"} -->
```python
chain.invoke({"prompt": "Repeat back whatever I say to you, but in all capital letters: hello"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"97a7f2a4ccce42a3549b785d97c93e98ea160f4748593da317d74c2542e6db45","type":"markdown"} -->
The explicit instruction in our prompt did a sufficient job getting the model to respond as we desired. Let's, however, try to get the model to behave in the same way via few-shot prompting. To do this, instead of relying on giving the model explicit instructions, we'll extend our prompt template to contain several human / AI example interactions.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"5152d39b7d2389b42b7e25af6c4b80baf2f3ea7a8438e8e1648a77bac03e7e6e","type":"code"} -->
```python
prompt_template = ChatPromptTemplate.from_messages([
    ("human", "hello"),
    ("ai", "HELLO"),
    ("human", "red"),
    ("ai", "RED"),
    ("human", "blue"),
    ("ai", "BLUE"),
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"5e3351496bdf4abbc4217ad2c88cf46ba4197e1e5d1f6b44fd3c5a8819947363","type":"code"} -->
```python
chain = prompt_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"4d6938115b2024a81c2de2367fc6457a2f329c8acfdc915f94c8b36363affef3","type":"markdown"} -->
Having constructed our few shot prompt, we'll send the model a new prompt, but this time we won't provide any explicit instructions about what the model ought to do.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"d88a9cea365a76816f9e0e5707d5ebe59d227c4bca80cec4bbc360eff2568f09","type":"code"} -->
```python
chain.invoke({"prompt": "hi"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"6673268f47ae8c43db9eabffae81f1b1e5d106669ac7abadab92df3ae0a35ea5","type":"code"} -->
```python
chain.invoke({"prompt": "orange"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"60748ddeba84e8960c61b81dc551431f345521da64ff3fc0d3eed6271eac9f63","type":"markdown"} -->
What's interesting here is that at no point in time have we given any explicit or specific instructions to the model about what it ought to do.

So how much will these few-shot prompt examples actually influence the model? The short answer is we have to test and see.

Here's an exmaple where we get the correct uppercasing, but not a mirrored response.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"465df94acdcb0bc1892262d07050ddce1dd4a3f0580e4763f18b2fcc9c89a71d","type":"code"} -->
```python
chain.invoke({"prompt": "nvidia"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"4f61742a893eff127ce1de21dca9d132e4ab73cb470dcee8f1c08ea2a4e79c31","type":"markdown"} -->
And given that all of our shots were single word single response examples, we shouldn't be too surprised if prompts that are departures from our examples don't work as expected.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"45612d3c6b84a3c6be3ee6ef4a22316f28be65291619f3ba18ff54d853448b5f","type":"code"} -->
```python
chain.invoke({"prompt": "How's it going today?"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"daa2f7defc5c791c2b397d0d4cf83369d517ab72933e77b1ce56ec037f4449eb","type":"markdown"} -->
## Aside: Few Shot Prompting Alone
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"c90ba30bc49d6a40bc742323f72b127c7ebad99c441636af95952715a9ca4381","type":"markdown"} -->
We've introduced few-shot prompting here in isolation for the sake of learning the core concepts, but in practice, few-shot prompting is just one of several tools at your disposal when prompting LLMs, and typically you will be using them in tandem with other techniques like being specific in your main prompt (as we've already covered) and utilizing the system message, which we'll cover in the next notebook.

That said, for now we're going to continue exploring the use of few-shot prompts largely in isolation of other techniques, primarily so you can focus on learning how to work with them fluently before being asked to use the technique in concert with others.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"2e741c3335442f34d52d5841b27743d79da28abaeff21bfef098f7b7194185ab","type":"markdown"} -->
## Few Shot Prompt Templates
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"ade594f7af98356f459ee743451c217a706f94a26938b8ad459fd283659c09f4","type":"markdown"} -->
Especially when working with just a few example shots that we want to use for all subsequent interactions, there's nothing wrong with just hardcoding our few-shot prompts into a prompt template like we just did.

Sometimes, however, we might wish to use (or try out) different combinations of examples with a static base prompt, or, ingest user / AI example interactions from data. In scenarios like these, we can use `FewShotChatMessagePromptTemplate` to assist us.

Let's imagine we want to construct a prompt that generates information about a given city, but we want to be very specific about the format of the information that the model generates. This seems like a good use case for few-shot prompting.

The end prompt we have in mind might look something like the following, with a human prompt template for a human to invoke with a city name, but also (currently commented out since it is not defined), a `few_shot_prompt` containing examples for how the model ought to format its response.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"38c268c799acdc7858243c41a8001300df6f1a35ace9947b8ebf6faeb65bb006","type":"code"} -->
```python
city_info_prompt_template = ChatPromptTemplate.from_messages([
    # few_shot_prompt, # NOTE: we would like to provide several examples here in the form of a few-shot prompt.
    ("human", "Provide information about the following city in exactly the same format as you've done in previous responses: City: {city}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"7295ab52a8d0d9ef79344b217adcfefe84d968b63241dc25ed39f1525161a4c2","type":"markdown"} -->
Whether we author them ourselves, obtain them from a data source, or get an LLM to generate them for us, we can construct a list of the human / AI interaction examples we want to use in our few shot prompt.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"0565e10f3081c9ff48515c64ddda06bc44e25e74048582d4b824ce840a5d148c","type":"code"} -->
```python
city_examples_location = [
    {"city": "Oakland", "output": "Oakland, USA, North America, Earth"},
    {"city": "Paris", "output": "Paris, France, Europe, Earth"},
    {"city": "Lima", "output": "Lima, Peru, South America, Earth"},
    {"city": "Seoul", "output": "Seoul, South Korea, Asia, Earth"}
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"15a31f3a1d4e6a911246a70af06a81d83486f1239181e58a1a3ada7e6c8bcf71","type":"markdown"} -->
Since each item in `city_examples_location` is intended to represent a human message and AI message, it makes sense that next we can construct a prompt template to represent a single example interaction.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"9b458d50abbbc1098ac44817eed19a942e7d7a24418e104763a84e60a857219b","type":"code"} -->
```python
prompt_template_for_examples = ChatPromptTemplate.from_messages([
    ("human", "{city}"),
    ("ai", "{output}"),
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"0f2abb96617b4a15e91c215e52a181280cf880fe4b1e86dc0e8a12a75469e3e5","type":"markdown"} -->
And now, with our examples, and with our prompt template for the examples, we can use `FewShotChatMessagePromptTemplate` to construct a few shot prompt out of our examples.

`FewShotChatMessagePromptTemplate` expects 2 arguments:
1. `examples`: a list of dicts (ostensibly containing our examples)
2. `example_prompt`: the prompt template used to render our examples (ostensibly into `human` and `ai` messages)
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"7a4dbeb7ae93843555e41750cef993ef3ee231cc501c53402366ccccc81f31ad","type":"code"} -->
```python
few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=city_examples_location,
    example_prompt=prompt_template_for_examples
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"e05a7f0cc48481923d1ab0924073cc2aca799137aa9a6469a22655936354b022","type":"markdown"} -->
`few_shot_prompt` is a runnable, just like any other prompt template, which we can invoke. Here we invoke it and view the messages it is comprised of.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"83080f7b5070b3a7adf2002f0e883f188cd0fbe441468161e2e7d7c843f9e556","type":"code"} -->
```python
few_shot_prompt.invoke({}).to_messages()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"6403a2c0ec4cbf2ce02d4177c08c24b6d89e46f004b2d615946c47db1bc33f82","type":"markdown"} -->
With `few_shot_prompt` now defined, we can revisit our main `city_info_prompt_template`, but actually include the `few_shot_prompt` instead of leaving it commented out.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"c1ab3ee9d5bfd85fca772ac036db09e08ef3a1526d646c65dabaae45f73a5580","type":"code"} -->
```python
city_info_prompt_template = ChatPromptTemplate.from_messages([
    few_shot_prompt,
    ("human", "Provide information about the following city in exactly the same format as you've done in previous responses: City: {city}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"98164bcd436db8f4fa6d46c5e70047167509cdb3dbb227d48f04290a0029cf1e","type":"markdown"} -->
Finally we can create a chain and use it, in this case, we'll send in a batch of city names.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"1663401e388918b61690287b1d55cbdfc4894aafa2ccaa9014275222dbfd6941","type":"code"} -->
```python
chain = city_info_prompt_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"40d9a7681e0ca82c8780667ed0907a7c205d9369f402b069f8fb2158f4cadd25","type":"code"} -->
```python
cities = [
    "New York",
    "London",
    "Tokyo",
    "Sydney",
    "Cape Town",
    "Toronto",
    "Berlin",
    "Buenos Aires",
    "Dubai",
    "Singapore"
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"cdaf25d118d1f156b5bf76ee69d8c557afe0d4bf48d157953aa64a5130525ed3","type":"code"} -->
```python
chain.batch(cities)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"e60cdb3d485860c8d939103bb9928705f5360b1306e22ea7e3bb50e63fd6c849","type":"markdown"} -->
This might seem like a lot of effort just to include some example shots in your prompt, and many times you will simply want to hardcode your examples into your main prompt. But as we mentioned before, there will be scenarios where you would wish to swap out the examples while keeping the rest of the structure of your main prompt, and this method allows for this quite nicely.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"21a4cb96aa9c80e8d4acc838d4be5947af436c0cfd068521aa62aac247308656","type":"markdown"} -->
## Exercise: Swap in Different Few Shot Examples
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"4274c56ff1cc5f80e54e0f18a0b98426f1a7d738c5981a30e6e39fc4121cf794","type":"markdown"} -->
As an exercise on this very topic, you're going to recreate the chain we just made but with a new set of few-shot examples provided below.

We are going to also provide you with the rest of the chain, and your task simply is to **make as little modification as possible to get it to work with the new examples**.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"be017295eb6c8c2ae7ee3950e43afa31306347e0b52cf1a8695585a0651df28e","type":"code"} -->
```python
city_examples_slogan = [
    {"city": "Oakland", "output": "Oakland, Bright Side of the Bay"},
    {"city": "Paris", "output": "Paris, City of Light"},
    {"city": "Lima", "output": "Lima, City of Kings"},
    {"city": "Seoul", "output": "Seoul, Heartbeat of Korea"},
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"7a4dbeb7ae93843555e41750cef993ef3ee231cc501c53402366ccccc81f31ad","type":"code"} -->
```python
few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=city_examples_location,
    example_prompt=prompt_template_for_examples
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"c1ab3ee9d5bfd85fca772ac036db09e08ef3a1526d646c65dabaae45f73a5580","type":"code"} -->
```python
city_info_prompt_template = ChatPromptTemplate.from_messages([
    few_shot_prompt,
    ("human", "Provide information about the following city in exactly the same format as you've done in previous responses: City: {city}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"1663401e388918b61690287b1d55cbdfc4894aafa2ccaa9014275222dbfd6941","type":"code"} -->
```python
chain = city_info_prompt_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"cdaf25d118d1f156b5bf76ee69d8c557afe0d4bf48d157953aa64a5130525ed3","type":"code"} -->
```python
chain.batch(cities)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"be017295eb6c8c2ae7ee3950e43afa31306347e0b52cf1a8695585a0651df28e","type":"code"} -->
```python
city_examples_slogan = [
    {"city": "Oakland", "output": "Oakland, Bright Side of the Bay"},
    {"city": "Paris", "output": "Paris, City of Light"},
    {"city": "Lima", "output": "Lima, City of Kings"},
    {"city": "Seoul", "output": "Seoul, Heartbeat of Korea"},
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:62","index":62,"schema":"dli-course-cell/1.0","source_sha256":"9b7b60565168d3e420b0600a3370e5781d024753ea02c71087ab9fd089dd77cc","type":"markdown"} -->
**The only change we made to the previous chain is here, where we update the `examples` field to be set to our new `city_examples_slogan` list.**
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:63","index":63,"schema":"dli-course-cell/1.0","source_sha256":"12b1308a79f5171374d7233b8181a11963afde8e41f14c85e6f55928a774e102","type":"code"} -->
```python
few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=city_examples_slogan, # Only change made is right here.
    example_prompt=prompt_template_for_examples
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:64","index":64,"schema":"dli-course-cell/1.0","source_sha256":"c1ab3ee9d5bfd85fca772ac036db09e08ef3a1526d646c65dabaae45f73a5580","type":"code"} -->
```python
city_info_prompt_template = ChatPromptTemplate.from_messages([
    few_shot_prompt,
    ("human", "Provide information about the following city in exactly the same format as you've done in previous responses: City: {city}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:65","index":65,"schema":"dli-course-cell/1.0","source_sha256":"1663401e388918b61690287b1d55cbdfc4894aafa2ccaa9014275222dbfd6941","type":"code"} -->
```python
chain = city_info_prompt_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:66","index":66,"schema":"dli-course-cell/1.0","source_sha256":"cdaf25d118d1f156b5bf76ee69d8c557afe0d4bf48d157953aa64a5130525ed3","type":"code"} -->
```python
chain.batch(cities)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:67","index":67,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:68","index":68,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/32-Few-Shot-Prompting:69","index":69,"schema":"dli-course-cell/1.0","source_sha256":"57c3dd8c848264893ea2748e53cb930b9239a48124efb0960d51da58933d50b0","type":"markdown"} -->
In this notebook, using human and AI messages you were able to compose example interactions that impacted the behavior of your LLM.

In the next notebook, you'll learn about a 3rd message type, the system message, and use it to establish an overarching persona and role for a chat model.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>3-Prompting-With-Messages/33-System-Message.ipynb</code> next: <strong>System Message</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Remember one example pair that changed the answer, because the next notebook adds a higher-level instruction layer that works alongside those demonstrations.</p>
</div>
<!-- /dli-course-cell -->
