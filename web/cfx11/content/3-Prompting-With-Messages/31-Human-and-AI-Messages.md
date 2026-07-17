<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"767a3bf0e14f580e8d00b1967a4e2622890d77fa449a3c2344bf05b0b2b65d0e","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Human and AI Messages</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"7b959756bbba157624e25119bc9c9f9fd5a84938c94e60a25061faf899698d62","type":"markdown"} -->
In this notebook you'll learn about two of the core chat message types, human and AI messages, and how to use them explictly in application code.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"c3d1333a7736ac978bfc35151eecc07098a1c816a90b220e98fa5aa6af957387","type":"markdown"} -->
By the time you complete this notebook you will:

- Make explicit the role-based messaging system utilized by chat variant LLMs.
- Learn how to use `ChatPromptTemplate` to create human and AI messages in prompt templates.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"43aaecfaf7d240fe39b9ef47e91a2b125650b6443b846256882b69e43e1f8d37","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"fe8a07f8e29704ed8c72091c34ce44956cd4b2a6331a6a6220553baac2abf3d3","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")

# Use the model selected in the course connection panel, or keep the lesson default.
model = os.getenv("NVIDIA_MODEL") or "nvidia/nemotron-nano-12b-v2-vl"
# model = "nvidia/nemotron-3-nano-30b-a3b"  # Compatible fallback; responses may differ.
# model = "meta/llama-3.3-70b-instruct"  # Legacy fallback; responses may differ more.

llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"078000b93a4ee76f4be4b093b6a9a882b6ac3db2b088dc666ff88780f833d453","type":"markdown"} -->
## Chat Messages
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"570a14464fe7bad07cbcc9ccc422f2e823f816e4b462d5fb42319ccc931650c1","type":"markdown"} -->
As we've mentioned earlier in the workshop, there are important differences working with LLMs that are of the "chat" or "instruction" variety, versus LLMs that are not. Primarily, we have pointed out that chat models are intended to be used in a conversational manner whereas non-chat models primarily aim to generate whatever ought to come next for a given piece of text.

As we have been working with LangChain throughout the workshop, we have been constructing prompts primarily via `ChatPromptTemplate`. As the "Chat" in the name implies, prompts constructed with `ChatPromptTemplate` are well-suited to creating prompts that work with the expectations of chat models, namely, role-based conversational interactions.

Later in this notebook we are going to learn how to leverage our understanding of the various roles involved in chat model interactions, but to begin, let's revisit some familiar tasks, but take the time to notice how our prompts and our chat model's responses are in fact being structured in a way to indicate that they are in fact a part of a role-based dialogue.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"88c067bbf9a003340e3b3034014c1711b4933a5b52ecdd3a09efb9652872fa04","type":"markdown"} -->
## Human Messages
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"7b98416118580a524bcdd69a0b7e0658e4e312bc95643ad90ca2d3f1f7df6376","type":"markdown"} -->
To begin, we'll create an incredibly simple chat prompt template.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"738dd9cd16b036343ab274b5876481848ee0bf18702c63acc8e6304ec0f33fac","type":"code"} -->
```python
prompt_template = ChatPromptTemplate.from_template("{prompt}")
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"f97b546b268746a65f84683476139827384b8f9d1ec1015176532920fe65a8ce","type":"markdown"} -->
Next we'll instantiate an actual prompt by invoking the prompt template and then print the prompt in its entirety so we can discuss it further in the context of our current exploration.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"0ba72fd57d9ce071f07899101cb9cf09127f6028f52953341cd9a471c08555c4","type":"code"} -->
```python
prompt = prompt_template.invoke({"prompt": "hello"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"cf07194ee232eb531e15f690000d19846dea69cf05504782658afcfacb9228a2","type":"code"} -->
```python
prompt
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"6e3add3ea97c5886ce3457f21c53f8e8006cc4cb60cdbcb439256faed622991d","type":"markdown"} -->
First, we see that this prompt is a `ChatPromptValue`: this is a prompt intended to be used with chat model.

Next, we notice that the message is something called a `HumanMessage`. Messages in a chat dialogue are always associated with a role, and this message is understood to be generated by someone with the role of "human".

Invoking the `to_messages` method on the prompt makes this even more clear.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"f082ac99f14703418fbe66304cbbe85b97ac255249334b5c99a805dc2e7a5e6f","type":"code"} -->
```python
prompt.to_messages()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"fa46da2a28d2fee07a9215eb1801b42880027ebafd83c1b738b598e48870feeb","type":"markdown"} -->
## AI Messages
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"485c28cb4f8b839a690b477720056e61696549aa92d892e7ed34c7bf905fe48e","type":"markdown"} -->
Let's create a very basic chain so we can send our prompt to our chat model and then take a closer look at the message it sends back to us. Worth noting is that we are not including a parser at the end of our chain because we are interested to explore the entirety of the response from the model.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"682ec7f8ab71bdf36108debe1e2af3209af024b81c4e07b1415677f3f487b019","type":"code"} -->
```python
chain = prompt_template | llm
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"22c318aa680066ba4262f5c49d4248c37f69666f46b010ce81f3d116c2179620","type":"code"} -->
```python
response = chain.invoke({"prompt": "hello"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"a9f4b3d22a523fdada41c85c175425bcd15b32b4cd0f54d9433accd52d7195a1","type":"code"} -->
```python
response
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"74332f5e136cb89eacf8b769fcba6c9e0349a4b4f6a939c554038c66a0354bfe","type":"markdown"} -->
Right away we see that the response from the model is an `AIMessage` which we (and the model) can take to understand means that the message was generated by someone with the role of "AI".
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"a41e838d37961f9b843c3b376c8db4f24a50fceebb9bf9598f794f81f9ab5336","type":"markdown"} -->
## Explicit Role Use in Prompts
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"41af4043f90d66c1f079ca9c2a57f03498ec7546ea125b08c37764d270d1b49c","type":"markdown"} -->
So under the hood LangChain, via `ChatPromptTemplate` has been taking care to manage the roles of both our "human" prompts and the "AI" chat model responses. However, LangChain also provides us with easy to use mechanisms for explicit role management.

One of the most simple ways is by using `ChatPromptTemplate.from_messages`, which takes a list of messages, where each message is a 2-tuple with its first value indicating the role associated with the message, and the second value being the content of the message itself.

Here we use `ChatPromptTemplate.from_messages` to recreate the exact same prompt we created above using `from_template`. In this case we are explicitly stating that the prompt will be associated with the "human" role.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"2f319c2cf70821f247d7443f16c711eaeb1f476e0597da803bc0861e8df5f6fd","type":"code"} -->
```python
prompt_template = ChatPromptTemplate.from_messages([
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"b2d4352c618770d206632e10263f617dafcc631ddcddf3c6a1369e7acaa7740f","type":"markdown"} -->
Looking at the prompt itself we see that just like what we did above, the the prompt is a `ChatPromptValue` that includes a message of type `HumanMessage`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"0ba72fd57d9ce071f07899101cb9cf09127f6028f52953341cd9a471c08555c4","type":"code"} -->
```python
prompt = prompt_template.invoke({"prompt": "hello"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"cf07194ee232eb531e15f690000d19846dea69cf05504782658afcfacb9228a2","type":"code"} -->
```python
prompt
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"f082ac99f14703418fbe66304cbbe85b97ac255249334b5c99a805dc2e7a5e6f","type":"code"} -->
```python
prompt.to_messages()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"05415d3274f9968f3f40775d5212ea544bbd624a1f0e4cadfee750a2270fe889","type":"markdown"} -->
We can work with this prompt template exactly like we've been doing all this time with prompts created with `from_template`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"682ec7f8ab71bdf36108debe1e2af3209af024b81c4e07b1415677f3f487b019","type":"code"} -->
```python
chain = prompt_template | llm
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"22c318aa680066ba4262f5c49d4248c37f69666f46b010ce81f3d116c2179620","type":"code"} -->
```python
response = chain.invoke({"prompt": "hello"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"a9f4b3d22a523fdada41c85c175425bcd15b32b4cd0f54d9433accd52d7195a1","type":"code"} -->
```python
response
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"acdee0e21a5698455923b89938e9139d4da4495ce10bc211b2eeb01f39639c49","type":"markdown"} -->
## Using ChatPromptMessages Directly
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"db9dbafeed22a08e7089ec67b5d12bd2d8bcd4bdf50c93aa7dbb954de395ff34","type":"markdown"} -->
As an aside, in more recent versions of LangChain we can use `ChatPromptMessages` directly, which is equivalent to using `ChatPromptTemplate.from_messages`. Thus the following two cells are identical.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"6ed6081551bff716f8a53ce0b213cf163202493d0b7d998d85de518a84a1f7b8","type":"code"} -->
```python
ChatPromptTemplate.from_messages([
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"8bcb6b7a4b328fe453667b5a50c327ed718c9af6662e1338b64137ab5b27e7fe","type":"code"} -->
```python
ChatPromptTemplate([
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"76bee10f82d4ba9efbd25a384ec9bf72704429348832d51000929dca615461f0","type":"markdown"} -->
We will primarily use `from_messages` in this workshop primarily because we expect you to see it much more frequently in documentation and literature, but feel free to use whichever of the two variations you like.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"91b79eb353d68f6578d09f94cdfe159c39cd350b6a0242d5bb0083d4324b3269","type":"markdown"} -->
## Exercise: Create an Explicit Human Message
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"ea4b44851e0c90088f70f3f8dea60f7f9d782fc4fbdca112fc512620454f1ca6","type":"markdown"} -->
As a very simple exercise, just to get you actively using human messages explicitly, refactor the following chain to use `ChatPromptTemplate.from_messages`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"7b735da778d43913178b98ce580689620a24dd1b8c5a2bd268d22d66b89de332","type":"code"} -->
```python
template = ChatPromptTemplate.from_template("Give the concise etomology of the following English word: {word}")
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"a45d5e7d2a81f7cdc07183c70e44e42aa65c9d434cd853383f168af4980f7d4d","type":"code"} -->
```python
parser = StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"5b7cd86e712b80f37ff3d0f2ebf117eeece92c6a160e6dfb349708e5b1620d6e","type":"code"} -->
```python
chain = template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"8a7518c48dbb6d86f7888d0ddfca9047708136152bf810ee0e9ce0f1d4788b0a","type":"code"} -->
```python
print(chain.invoke({"word": "learning"}))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"0764f7f24760d70c8d1feae6da34ae76343b7e634be3bb56fe5200a12ec8837e","type":"code"} -->
```python
template = ChatPromptTemplate.from_messages([
    ("human", "Give the concise etomology of the following English word: {word}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"a45d5e7d2a81f7cdc07183c70e44e42aa65c9d434cd853383f168af4980f7d4d","type":"code"} -->
```python
parser = StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"5b7cd86e712b80f37ff3d0f2ebf117eeece92c6a160e6dfb349708e5b1620d6e","type":"code"} -->
```python
chain = template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"8a7518c48dbb6d86f7888d0ddfca9047708136152bf810ee0e9ce0f1d4788b0a","type":"code"} -->
```python
print(chain.invoke({"word": "learning"}))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:62","index":62,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:63","index":63,"schema":"dli-course-cell/1.0","source_sha256":"852fea28f73d66d3f2d64464625013fe38d571111e0b9ea5d64701029eb8d664","type":"markdown"} -->
## Explicit Use of the AI Role
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:64","index":64,"schema":"dli-course-cell/1.0","source_sha256":"e8086c3996186a9c6648cd6eb2ef1449c2ca679df281a8ee3bf6c0d60453644a","type":"markdown"} -->
In addition to providing "human" role message, we can also pass messages to the model associated with the AI role.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:65","index":65,"schema":"dli-course-cell/1.0","source_sha256":"498269fbb1c73e1d2beb90a7bf18b097a0bef165a27d8413b1e43b593fa5408a","type":"code"} -->
```python
prompt_template = ChatPromptTemplate.from_messages([
    ("human", "Hello."),
    ("ai", "Hello, how are you?"),
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:66","index":66,"schema":"dli-course-cell/1.0","source_sha256":"a03e58e513b26b050d7b4b3428af3e2baef522d2443aa6e564613031ee38f617","type":"markdown"} -->
If we invoke this prompt we can see that unlike prompts we have sent to our chat models in the past, it contains 3 messages, two associated with the human role and one with the AI.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:67","index":67,"schema":"dli-course-cell/1.0","source_sha256":"4636d4a86791deff486a67f1feb1eee7e3cc028629ddc6ed2ec077341961ccc8","type":"code"} -->
```python
prompt = prompt_template.invoke({"prompt": "I'm well, thanks!"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:68","index":68,"schema":"dli-course-cell/1.0","source_sha256":"f082ac99f14703418fbe66304cbbe85b97ac255249334b5c99a805dc2e7a5e6f","type":"code"} -->
```python
prompt.to_messages()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:69","index":69,"schema":"dli-course-cell/1.0","source_sha256":"96fb81729d5acf36eb52e7f57d51c5f67ba9dc466c3903556cf1683a0a020a9c","type":"markdown"} -->
This ability allows us to construct prompts that contain additional context for the model to use when generating its response.

From the model's perspective it is seeing what has already happened in the current chat conversation and this context about what has already happened can influence how the model responds in subsequent conversational turns.

There are 2 primary ways we tend to utilize this ability.

The first is when we want to implement chatbot functionality. After every human / AI interaction, we can add the interaction to our prompt. Thus, whenever we send a message to the chatbot, it is aware of the full context of the conversation up until that point, and is able to respond more appropriately. We will be looking at creating chatbot functionality in detail later in the workshop.

The second is by constructing our own fictitious human / AI interactions to serve as examples to the model about how it ought to respond to subsequent human messages. This technique of providing example human / AI interactions by way of our prompt is referred to as few-shot prompting, which we will look at in the next notebook.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:70","index":70,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:71","index":71,"schema":"dli-course-cell/1.0","source_sha256":"30d3c21ed1c6e551be4a7b8eee65dfc86dc78058652759c269e103a04b447b03","type":"markdown"} -->
## Using `HumanMessage` and `AIMessage`
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:72","index":72,"schema":"dli-course-cell/1.0","source_sha256":"836efc65caefad339d5820b1bf4687d805ca81c340875c519b80a2e329ecfbae","type":"markdown"} -->
It's often the case with LangChain that we have multiple ways to do the same thing, and this is true in the case of creating role-specific messages. Up until now we have been using the 2-tuple syntax to create a message explicitly associated with a role.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:73","index":73,"schema":"dli-course-cell/1.0","source_sha256":"498269fbb1c73e1d2beb90a7bf18b097a0bef165a27d8413b1e43b593fa5408a","type":"code"} -->
```python
prompt_template = ChatPromptTemplate.from_messages([
    ("human", "Hello."),
    ("ai", "Hello, how are you?"),
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:74","index":74,"schema":"dli-course-cell/1.0","source_sha256":"e6671585f992c949ec86063e6b3d832e635c2bf502f121417d5f6e5c9f71c21a","type":"markdown"} -->
As an alternative to the 2-tuple syntax above, we can also use LangChain's `HumanMessage` and `AIMessage` classes.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:75","index":75,"schema":"dli-course-cell/1.0","source_sha256":"54d8930a991ec8bc7e8d06c8f3647ba21a2f384ed92c8f3f2a9e1ad498274830","type":"code"} -->
```python
from langchain_core.messages import HumanMessage, AIMessage
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:76","index":76,"schema":"dli-course-cell/1.0","source_sha256":"aafa7fec29564a1706290cb0a3aa8a9a18a5551fa140e018430199baf55d63bd","type":"markdown"} -->
The following is identical to the 2-tuple implementation above.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:77","index":77,"schema":"dli-course-cell/1.0","source_sha256":"659970799a9d6a17c571b31d680f62633360325cb8f8bea55d406c9505e93033","type":"code"} -->
```python
prompt_template = ChatPromptTemplate.from_messages([
    HumanMessage(content="Hello"),
    AIMessage(content="Hello, how are you?"),
    HumanMessage(content="{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:78","index":78,"schema":"dli-course-cell/1.0","source_sha256":"6aa823ce6017ad880fd16ed8073df0ecd97d0f55a54c0b689a82671d628a72c4","type":"markdown"} -->
It really is just a matter of choice which of these you might prefer to use in your applications, and you should feel free to use either in this workshop. Most importantly is to be able to recognize and understand each of them, as you're likely to see them both in documentation and examples.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:79","index":79,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/31-Human-and-AI-Messages:80","index":80,"schema":"dli-course-cell/1.0","source_sha256":"802d5e7140ce2282fef9340ba52dc932f04a57585351eb51522d126b8dba3d48","type":"markdown"} -->
Now that you're familiar with human and AI messages, including how to author them in chat prompt templates, in the next notebook you'll learn a powerful and popular technique called few-shot prompting that will leverage your message authoring skills to provide chat models with examples capable of impacting their behavior.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>3-Prompting-With-Messages/32-Few-Shot-Prompting.ipynb</code> next: <strong>Few-Shot Prompting</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Keep one message format you would reuse, since the next notebook uses that same structure to turn examples into a behavior-shaping interface.</p>
</div>
<!-- /dli-course-cell -->
