<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"4b191d06a2d6aea5691b155862a4306a3d1b25c733dca6f891f85d36015c2f3b","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Chatbots</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"c58aa1e42924ed057ecd9ebbecea61371bf2e9f8582c14f606255ece03d0c5c1","type":"markdown"} -->
In this notebook, you will learn how to store conversation history and thereby enable chatbot functionality in your LLM-based chains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"994e8e4a3ca41a74b4921737f65f7a03269cd221f5e3c4ea9e803af0088d5a35","type":"markdown"} -->
By the time you complete this notebook you will:

- Understand the core principles and techniques required to create chatbot applications capable of retaining conversation history.
- Create easy-to-use chatbots, capable of assuming a variety of different personas.
- Interact with a simple chatbot application interface, well-suited for chatbot application prototyping.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"15c4faff0506ab4a6c5ecc8309bc6973b78baaa56fe695589969a8508e0c97e4","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"d741a922d2642a3fc57f5481f8c069b9cfe987622157b766b7bad7190f65996b","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")
model = 'nvidia/nemotron-nano-12b-v2-vl'
llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"c057e5a185dd2265d03baa287f418427616a9c4c253fc1c2cefc3a49b554e99e","type":"markdown"} -->
## Placeholder Messages
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"0c69c0e197cd247f32b78dbfe91a498e73099ff1c4af4ef1f4089de180514b37","type":"markdown"} -->
Before we begin work enabling conversation history and chatbot functionality, we need to introduce a new kind of message that we have not yet covered, **placeholder** messages.

Put simply, and as the name suggest, a placeholder message is used in a prompt template to hold the place of a list of other messages.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"3b2e070e9022fc5d8df3d73ceb454c8803a4cacdc44b87e936dc1a8c4380e6f5","type":"code"} -->
```python
template_with_placeholder = ChatPromptTemplate.from_messages([
    ('placeholder', '{messages}'),
    ('human', '{prompt}')
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"a4945db201e6699e65aa6b75cd662531261433982c1d1d695c411f049dd27d5e","type":"code"} -->
```python
messages = [
    ('human', 'The sun came up today.'),
    ('ai', 'That is wonderful!'),
    ('human', 'The sun went down today.'),
    ('ai', 'That is also wonderful!.')
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"682be766306d05f13d4eee1675b3602f77be05a72c94b2129f3eee3617811bd0","type":"code"} -->
```python
prompt = 'What happened today?'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"cf8b5dc119306ef2f3f5fc5dbe619a96809220e5d6eec2c4f47b5cdf5ab98ee6","type":"markdown"} -->
When invoking (or streaming or batching) prompt templates or chains that contain placeholder messages, we provide a value as the template indicates, only in the case of a placeholder message, we provide a list of other messages, rather than a string.

Here we invoke `template_with_placeholder`, passing in the `messages` list to fulfil the template's `messages` parameter, and the `prompt` string to fulfil its `prompt` parameter.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"992fbbff9f9c91318b6e30d89e333e6ac21068e2d4e073f15182f6d3799dc1c5","type":"code"} -->
```python
template_with_placeholder.invoke({'messages': messages, 'prompt': prompt})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"c882d7e5afe664ca0f2fafca9f118c5a478f5bc5dbf90558bcbae1a06ba17d71","type":"markdown"} -->
As you can see, LangChain expanded the `placeholder` message, for which we provided a list, into a list of individual messages that we provided when invoking the prompt template.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"a533c8fb671afcf84cbcdf2a8a86062e1e7e2630ac845dd2cc0ddee5949b658d","type":"markdown"} -->
It should come as no surprise that we can use this prompt template in chains just as we would any other.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"0bdf740957bca20feaccd4a798a290634a7e2e66d5824d27beef6f7cb30993e8","type":"code"} -->
```python
chain = template_with_placeholder | llm | StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"55b4151017f35733b5a06551b4cbe45b78e863fb4c7d2babc4f115b493368a00","type":"code"} -->
```python
chain.invoke({'messages': messages, 'prompt': prompt})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"45dbb71dcd49539ca9f24e4c249e20462edd865b4e0cde420498da925a517a16","type":"markdown"} -->
## Rudimentary Conversation History
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"3222ece52164717bffeb4293233eed0d56312b2a17dd22c3d7c4d9bfbd7935e0","type":"markdown"} -->
We can easily construct a rudimentary conversation history mechanism using a message placeholder. First we'll create a prompt template utilizing a placeholder, and use it in a simple chain.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"f0c0148df9018575f684d173a04ed30b9dc2f03bf9aad508df405c668fe27f5e","type":"code"} -->
```python
chat_conversation_template = ChatPromptTemplate.from_messages([
    ('placeholder', '{chat_conversation}')
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"6fa6ffd9e6e7ef5d5b67f067f952294f2a6dda769bf8edda9fd72ff8a63ca7be","type":"code"} -->
```python
chat_chain = chat_conversation_template | llm | StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"72f582b81ddfa4ef431b4ef1b8ca624de8783a7d3959d9a4db289d8cb241adf0","type":"markdown"} -->
Next we'll create a list to store our conversation, which we will add to over time.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"6a59d174e620156f3a32ca32585fbcec83955aa94189099b004006faa2f458b6","type":"code"} -->
```python
chat_conversation = []
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"d0b4996a594d7659a912cba693517143a93bf8360ade557ab665fc01470de789","type":"markdown"} -->
We will begin by appending our first prompt, as a `user` message to the `chat_conversation` list.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"fc8763d9eab9dcf54cada74132c4ae3f977f6066e1a3bbe854e3cba2c26b9c16","type":"code"} -->
```python
chat_conversation.append(('user', 'Hello, my name is Michael.'))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"cd7149533fb886c5e8f6f78f0805c6e6431e7533e1745e52cc33e8f51785df3f","type":"markdown"} -->
Just to test it out, we can now invoke our `chat_chain` with the current `chat_conversation` list.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"f7c4a64d85494b28d01dcad92416de0c980e36c54a317b163cb26bb9835983e7","type":"code"} -->
```python
chat_chain.invoke({'chat_conversation': chat_conversation})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"98c68be30bd52116c58354115b81e16f75067e4e71bf821c4dd553ed91cc7da1","type":"markdown"} -->
It looks like the LLM is able to respond just fine. Since we are wanting to keep track of the conversation history, however, let's invoke the chain again, but this time append the response to the `chat_conversation` list as an `ai` message.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"af0325a801e842922f58df3810afa7ecee6216459acf81b44013b1525ecbedb8","type":"code"} -->
```python
response = chat_chain.invoke({'chat_conversation': chat_conversation})
chat_conversation.append(('ai', response))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"800ebf51fd1b3ada3e6ba4ce1e1dedac0b9cd2999d41ef14c28cd92d04e32de8","type":"markdown"} -->
Looking at `chat_conversation` we see it now contains a list of the messages thus far.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"4243bb594fcfdf519d23c84402941d6864824b0152c4a9640e80bfbb36efa791","type":"code"} -->
```python
chat_conversation
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"8c615e7873ecf22e8f2d6e0d5e80c5fb82d0300c2e04cfafada9e00a1e114f47","type":"markdown"} -->
Let's repeat this same process with a new message, and let's pass in a prompt that relies on previous conversation history to answer correctly.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"879bad5583ee20122954e484a30dfd731ded2480cf5aed7f52683d9c5aaa5b57","type":"code"} -->
```python
chat_conversation.append(('user', 'Do you remember what my name is?'))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"09a4099f645d250e253aaa48b90b23a925f2cfc1fcd872dd00811e01f0dbc915","type":"code"} -->
```python
response = chat_chain.invoke({'chat_conversation': chat_conversation})
chat_conversation.append(('ai', response))
chat_conversation
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"9b03134f48e829da725893273e5db0a5fa375f1565e80a42ff1394c84746d40f","type":"markdown"} -->
As you can see, by appending user prompt and AI responses to `chat_conversation` as `user` and `ai` messages respectively, and then invoking our placeholder-containing `chat_chain` with the entire up-to-date conversation, we now have the ability to converse with the LLM in a way where it retains details from earlier in the conversation.

At its most basic level, all chatbot functionality that is capable of retaining conversation history utilizes this method of passing in the conversation prior to new user messages.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"8ca2827fb10a702e22f3ea2c81760033feae98d99757cc7752b896d736d1677e","type":"markdown"} -->
## Chatbot Class
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"853423c3a6d919360de33f421dd56b4dc4b3fbe47e0d190b53a79a5196450f4c","type":"markdown"} -->
We can encapsulate the functionality we achieved above into a class that will make interacting with our conversation history-enabled LLM much simpler. Please read the following `Chatbot` class definition, including its comments, carefully.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"f1d862a70f3f2e82f5f63d20cc6c3f553f1f2c360ca388b4791fe3150c20db3c","type":"code"} -->
```python
class Chatbot:
    def __init__(self, llm):
        # This is the same prompt template we used earlier, which a placeholder message for storing conversation history.
        chat_conversation_template = ChatPromptTemplate.from_messages([
            ('placeholder', '{chat_conversation}')
        ])

        # This is the same chain we created above, added to `self` for use by the `chat` method below.
        self.chat_chain = chat_conversation_template | llm | StrOutputParser()

        # Here we instantiate an empty list that will be added to over time.
        self.chat_conversation = []

    # `chat` expects a simple string prompt.
    def chat(self, prompt):
        # Append the prompt as a user message to chat conversation.
        self.chat_conversation.append(('user', prompt))
        
        response = self.chat_chain.invoke({'chat_conversation': self.chat_conversation})
        # Append the chain response as an `ai` message to chat conversation.
        self.chat_conversation.append(('ai', response))
        # Return the chain response to the user for viewing.
        return response

    # Clear conversation history.
    def clear(self):
        self.chat_conversation = []
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"7f0f132a42ede0925dfbf4b893a1de7fa227cb420d07754efd618297080830a9","type":"markdown"} -->
Let's instantiate a chatbot instance.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"e6a9765ecf75ea9f50b99d639f293a65a6779e1eb3d10a42f28adb73c6c2be93","type":"code"} -->
```python
chatbot = Chatbot(llm)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"13511b222ac6af584e0154b81e4400c1da7f8247399b67e653e4f6e94262f3ea","type":"markdown"} -->
We can now utilize its `chat` method.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"d1f54aaf6aeb70a5e5d1f96e61ea1439732451659164d8dcfb77d694bcd05e0d","type":"code"} -->
```python
print(chatbot.chat('Hi, my name is Michael.'))
# print(chatbot.chat_conversation)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"5cd0079f50f3c880d81b8d34341e2dcd265aa48b27bf6e8789cb82ea96e01d50","type":"code"} -->
```python
print(chatbot.chat('I just want to be reminded of my name please. What\'s my name'))
# print(chatbot.chat_conversation)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"99136eae178d69dd91ebd1e12ca6cde49c329598095c15166c646cf969fcb8e2","type":"code"} -->
```python
print(chatbot.chat("Tell me something interesting I probably don't know about pi."))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"94860c3323e7a77508b4d543313331c0bf64917057a4ea2f6e58761b1756d020","type":"code"} -->
```python
print(chatbot.chat("That's really cool! Give me another.")) # Note we are not being specific about what "another" refers to...the LLM needs to have previous messages to understand our intent.
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"54a8c7e8bc9435514f60fe11b73713258f3bd7994a627e3f66887b5d72e1d01a","type":"markdown"} -->
## More Advanced Chatbots
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"1d7e300770abc80631519d29f2edf21db761d77882e2166485df3a11789c83d7","type":"markdown"} -->
The topic of managing conversation history, and therefore of creating chatbots is actually quite large and there are many more advanced techniques that are outside the scope of this workshop. We do, however, want to provide you with some additional references for further study, should you wish to pursue the topic further.

- [Session-based conversation history, and history trimming](https://python.langchain.com/docs/how_to/chatbots_memory/): LangChain ships with tooling for wrapping chains in a way that provides history management, and specifically, managing multiple conversation sessions. This resource introduces the use of LangChain tooling for managing session-based conversation history, and also covers some techniques for managing the length of conversation history via message trimming and summarization, an important topic as chat conversations may grow large, or even too large to continue passing into an LLM.
- [Conversational RAG](https://python.langchain.com/docs/tutorials/qa_chat_history/): Retrieval Augmented Generation, or RAG (see [this DLI self-paced course](https://learn.nvidia.com/courses/course-detail?course_id=course-v1:DLI+S-FX-15+V1) for more) is a technique whereby LLMs can be provided real-time context from external data sources in support of generating their response. This resource discusses RAG in the context of chatbots capable of retaining conversation history.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"7b3cb12c55ba2166eba7e7ed98ec25b5da8146bc2c8cdbe67fcefbf24f6e850d","type":"markdown"} -->
## Exercise: Enable Role-based Chatbots
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"ce27b85db2d8c3887669b31a9d77051f1667ee7e79c769eb773ee5c538d28068","type":"markdown"} -->
For this exercise you'll enable your chatbot instances to assume a specific role by leveraging a system message.

Below is the class definition for `ChatbotWithRole` which currently is identical to the `Chatbot` class definition above except that we've defined a `system_message` argument (defaulting to an empty string) that be used when instantiating `ChatbotWithRole` instances.

Edit the class definition as needed so that you can supply a system message that will create a specific role for your chatbot. Upon completion you should be able to use system messages like the following to create an overarching role for your chatbot to assume.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"5bf46baa3ee4e65e9660ca5ea3c29adf8b8bf603155fa0a339269b56ad7175ee","type":"code"} -->
```python
brief_chatbot_system_message = "You always answer as briefly and concisely as possible."

curious_chatbot_system_message = """\
You are incredibly curious, and often respond with reflections and followup questions that lean the conversation in the direction of playfully \
understanding more about the subject matters of the conversation."""

increased_vocabulary_system_message = """\
You always respond using challenging and often under-utilized vocabulary words, even when your response could be made more simply."""
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"4d773977eb84fdb1f3f28254adbe60e444196620bb1937805f48dd6dc59c4946","type":"markdown"} -->
Update the following class definition so that the passed-in `system_message` is effectively utilized by chatbot instances.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:62","index":62,"schema":"dli-course-cell/1.0","source_sha256":"da228c3beb1705a12f260e6ce74ab0c576761a25c0052c6744476285baad039b","type":"code"} -->
```python
class ChatbotWithRole:
    def __init__(self, llm, system_message=''):
        # This is the same prompt template we used earlier, which a placeholder message for storing conversation history.
        chat_conversation_template = ChatPromptTemplate.from_messages([
            ('placeholder', '{chat_conversation}')
        ])

        # This is the same chain we created above, added to `self` for use by the `chat` method below.
        self.chat_chain = chat_conversation_template | llm | StrOutputParser()

        # Here we instantiate an empty list that will be added to over time.
        self.chat_conversation = []

    # `chat` expects a simple string prompt.
    def chat(self, prompt):
        # Append the prompt as a user message to chat conversation.
        self.chat_conversation.append(('user', prompt))
        
        response = self.chat_chain.invoke({'chat_conversation': self.chat_conversation})
        # Append the chain response as an `ai` message to chat conversation.
        self.chat_conversation.append(('ai', response))
        # Return the chain response to the user for viewing.
        return response

    # Clear conversation history.
    def clear(self):
        self.chat_conversation = []
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:63","index":63,"schema":"dli-course-cell/1.0","source_sha256":"a8df16f0e02441bc17b07f2b1f1d245d463efeabaaf392e0ce9b5831befcbff1","type":"markdown"} -->
### Try Out a Chatbot With a Role
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:64","index":64,"schema":"dli-course-cell/1.0","source_sha256":"52cde147b53e9329d8347c882077e557f5fee16ea4b3dd1644be23826557f28a","type":"markdown"} -->
After successfully implementing `ChatbotWithRole`, try creating an instance of it with a system message of your choosing and interact with it.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:65","index":65,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:66","index":66,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:67","index":67,"schema":"dli-course-cell/1.0","source_sha256":"eb88075e08cf46c841131aa5ea86617b283768d3b819ec916fb1ed73c4938d59","type":"markdown"} -->
The solution is brief. Here we added an additional system message to the `chat_conversation_template` that uses the passed-in `system_message`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:68","index":68,"schema":"dli-course-cell/1.0","source_sha256":"de3d0be9cfd0329135ae0a9ad5bd2bcb81155aea8d1189133dbc9f480e699514","type":"code"} -->
```python
class ChatbotWithRole:
    def __init__(self, llm, system_message=''):
        # This is the same prompt template we used earlier, which a placeholder message for storing conversation history.
        chat_conversation_template = ChatPromptTemplate.from_messages([
            ('system', system_message),
            ('placeholder', '{chat_conversation}')
        ])

        # This is the same chain we created above, added to `self` for use by the `chat` method below.
        self.chat_chain = chat_conversation_template | llm | StrOutputParser()

        # Here we instantiate an empty list that will be added to over time.
        self.chat_conversation = []

    # `chat` expects a simple string prompt.
    def chat(self, prompt):
        # Append the prompt as a user message to chat conversation.
        self.chat_conversation.append(('user', prompt))
        
        response = self.chat_chain.invoke({'chat_conversation': self.chat_conversation})
        # Append the chain response as an `ai` message to chat conversation.
        self.chat_conversation.append(('ai', response))
        # Return the chain response to the user for viewing.
        return response

    # Clear conversation history.
    def clear(self):
        self.chat_conversation = []
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:69","index":69,"schema":"dli-course-cell/1.0","source_sha256":"9735d5895528ce22a29e3fd7ab20bba2e536bab83aadcb31bb04a039f7a9a621","type":"markdown"} -->
Let's try it out with one of the system messages defined above.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:70","index":70,"schema":"dli-course-cell/1.0","source_sha256":"d2ae57d5be3fbadda213ce546c3a4d0d31663e09f3be65b9cdae5169251e7795","type":"code"} -->
```python
brief_chatbot = ChatbotWithRole(llm, system_message=brief_chatbot_system_message)
curious_chatbot = ChatbotWithRole(llm, system_message=curious_chatbot_system_message)
increased_vocabulary_chatbot = ChatbotWithRole(llm, system_message=increased_vocabulary_system_message)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:71","index":71,"schema":"dli-course-cell/1.0","source_sha256":"d7821b6cb72804d4fd8b0d75b9fba23982513385d61dfc98be8eba9ebc3203fa","type":"code"} -->
```python
print(brief_chatbot.chat("What would you consider a good morning routine?"))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:72","index":72,"schema":"dli-course-cell/1.0","source_sha256":"623b3eea0063ab45270a655ba67ca6ad1b4202b9977264868d083427ff8a5d41","type":"code"} -->
```python
print(curious_chatbot.chat("What would you consider a good morning routine?"))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:73","index":73,"schema":"dli-course-cell/1.0","source_sha256":"33373dca7a58688b2c57f0fbd071aaea288e54aaa76cf5a1c1862eb9d15788b0","type":"code"} -->
```python
print(increased_vocabulary_chatbot.chat("What would you consider a good morning routine?"))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:74","index":74,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:75","index":75,"schema":"dli-course-cell/1.0","source_sha256":"64fc3e80197e67db35290d504873d055c0157d49c4bc6544a73e04b74700ffa2","type":"markdown"} -->
## Gradio
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:76","index":76,"schema":"dli-course-cell/1.0","source_sha256":"36fbbf2de0109959505aa56a5bc701e41977d17c33105601ac7efd6fb8a2873e","type":"markdown"} -->
_"Gradio is the fastest way to demo your machine learning model with a friendly web interface so that anyone can use it, anywhere!"_

If you find yourself building chatbots, especially for prototypes or even personal use chatbots, you might consider [Gradio](https://www.gradio.app/), which makes it easy to setup a pleasant chat interface, including in Jupyter environments.

Pass a `chatbot` instance (created with either the `Chatbot` class or `ChatbotWithRole` class) into the following `create_chatbot_interface` function and have a conversation. If you're interested, check out [chat_helpers/gradio_interface.py](chat_helpers/gradio_interface.py) for the source code.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:77","index":77,"schema":"dli-course-cell/1.0","source_sha256":"a787c55696916400f174a8449475fbfd9dba6968c0496a4c5984b759e65c98d7","type":"code"} -->
```python
from chat_helpers.gradio_interface import create_chatbot_interface_from_bot
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:78","index":78,"schema":"dli-course-cell/1.0","source_sha256":"1de0dd2e49123bf393b607bf08e1ade40c00372356d0fdeb0a1b44c1001cb9d0","type":"code"} -->
```python
app = create_chatbot_interface_from_bot(curious_chatbot)
app.launch(share=True)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:79","index":79,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:80","index":80,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/36-Chatbots:81","index":81,"schema":"dli-course-cell/1.0","source_sha256":"598cb610e1448c925ac69974131ec66b002888f74268b5babb9c206389372a99","type":"markdown"} -->
In this notebook you learned how to leverage a new message type, a placeholder message, to create chatbots capable of retaining conversation history.

This was the final notebook in this section focused primarily on the explicit use of chat message types to benefit your LLM-based application code, and you learned a variety of techniques in addition to managing conversation history, like few-shot prompting, utilizing the system message, and performing chain-of-though prompting.

In this next section you will focus your attention on using a variety of prompt engineering techniques to enable your LLM-based applications to generated structured data, a powerful capability that unlocks the ability of your LLM-based applications to interact more immediately with downstream code, and opens incredible possibilities for using LLMs to tag and anaylyze large collections of textual data.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>4-Structured-Output/40-Section-Introduction.ipynb</code> next: <strong>Section 4: Structured Output</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Keep one conversational behavior you want to make machine-readable, because the next section turns free-form assistant output into typed fields other systems can trust.</p>
</div>
<!-- /dli-course-cell -->
