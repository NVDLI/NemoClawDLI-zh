<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"77f545fe707c960d97b205de8ba178bdaaa5c86d39d7a349cde36981ca24c673","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>System Message</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"154412910bcdb7ecf719de8b02d3a230dd113eb660ff075da2383a6548c90494","type":"markdown"} -->
In this notebook you'll learn about the system message, which will allow you to define an overarching persona and role for your chat models.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"80b380e15bd792904bed5d28ddc52f120ac8352a2b76156c45d10f380f00d7b6","type":"markdown"} -->
By the time you complete this notebook you will:

- Learn about the chat message type system message.
- Be able to define an overarching role or persona for chat models.
- Understand the effect and limitations of various chat message types when interacting with a chat model.
- Use system message to create a variety of LLM assistants focused on specific domains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"15c4faff0506ab4a6c5ecc8309bc6973b78baaa56fe695589969a8508e0c97e4","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"d741a922d2642a3fc57f5481f8c069b9cfe987622157b766b7bad7190f65996b","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")
model = 'nvidia/nemotron-nano-12b-v2-vl'
llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"e836af7f7d9efd54ab8e3959fa1f19d80aeca17f55901aac1e94fddf100f906f","type":"markdown"} -->
## System Messages
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"6736e03f8a17c47c8e34099de9d8fe82bec98389263a64bb0d94dc1a5d4de7b2","type":"markdown"} -->
In addition to human and AI messages, a third major kind of message we can utilize in our prompts is the system message.

The system message is a preliminary statement or contextual cue designed to orient an AI model's response towards a specific framework or understanding of a task. There are no hard and fast rules about what belongs in the system message but we should consider it primarily to set the role of the model, or any context that will apply all of its responses.

Chat models will have a default system message, typically something like "You are a helpful friendly assistant who always does your best to...", but we can provide our own as part of our prompts.

One common use of the system message is to supply the overarching personality and personal details we want the model to portray when generating responses. Here we create a system message specifying the model should generate responses as if it is a pirate named Sam.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"95d4d71df6d6eb180aaa5df65dcfe48493ec81f90fbede14668db54a8cc14007","type":"code"} -->
```python
prompt_template = ChatPromptTemplate([
    ("system", "You are a pirate. Your name is Sam. You always talk like a pirate"),
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"a45d5e7d2a81f7cdc07183c70e44e42aa65c9d434cd853383f168af4980f7d4d","type":"code"} -->
```python
parser = StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"5e3351496bdf4abbc4217ad2c88cf46ba4197e1e5d1f6b44fd3c5a8819947363","type":"code"} -->
```python
chain = prompt_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"d3bb8b0580d578fa22d2096cb9945c82b8b4378add416e3d7be63c787f9847e9","type":"code"} -->
```python
chain.invoke({"prompt": "Who are you?"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"a5205e9f3875a8331ee31d827e2cada43c0f816a696f0efe98f804fff4c30430","type":"markdown"} -->
Here we prompt the model with an inquiry that has nothing to do with being a pirate, but the model still responds according to the instructions in the system message.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"8580533aeddb1622c1a04c5f24309b8f0691779cf8a172550718d169fbc0259d","type":"code"} -->
```python
print(chain.invoke({"prompt": "Give me a short description of the city of Paris."}))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"c40de70e7a89c515b83f2a8eb5b07758d42555fb993c90e915ff346ec6735233","type":"markdown"} -->
## Influence of System Message
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"6eb423478d1b664383adc013fa0228af8084da757d98b30a0bb02e8c23646867","type":"markdown"} -->
To further explore just how much influence the system message has over model responses, let's try to reproduce some behavior we attempted in the previous notebook, namely, getting the model to mirror back whatever we say to it, but in uppercase. In the previous notebook we attempted this, with some success, using few-shot prompting.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"e5ea5503d1142eb370435813c447d6fb58751a0af0aeafc5988aa44c52e3e1d2","type":"code"} -->
```python
prompt_template = ChatPromptTemplate([
    ("system", "You are an incredibly simple text repeater who repeats back anything said to you, but in UPPERCASE."),
    ("human", "{prompt}")
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"5e3351496bdf4abbc4217ad2c88cf46ba4197e1e5d1f6b44fd3c5a8819947363","type":"code"} -->
```python
chain = prompt_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"2af698c1a404e49c65b3493fb78a1056cf8a7483b60d2b462a4044f1efca687c","type":"code"} -->
```python
chain.invoke({"prompt": "hello"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"249c3b59d1e7ede21ad7531df81736d1c044b078a8a6f65f71b5abfaeff59762","type":"markdown"} -->
Using few-shot prompting in the last notebook, the following prompt got back the response `'GPU'`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"465df94acdcb0bc1892262d07050ddce1dd4a3f0580e4763f18b2fcc9c89a71d","type":"code"} -->
```python
chain.invoke({"prompt": "nvidia"})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"4e7fdf957cf74d9fee78bce08bc977134ed50ad229ee9e85f81a790a60a8251f","type":"markdown"} -->
Let's see how it does when we prompt it explicitly to violate what the system message indicates it should do.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"3db6842b7e5bd08ad55673d06c2fb4e9c6046f670e2a4000ec92db06ce7831b8","type":"code"} -->
```python
chain.invoke({"prompt": "Don't repeat this back to me."})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"fa0355365e20f47d951fe3229702414f500a677da1904868cf7542d4404f67aa","type":"markdown"} -->
It would seem as if the influence of the system message is quite strong.

Just to be clear, however, it is not ironclad. Consider the response to the following prompt, which is even more explicit about violating the instructions in the system message.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"0d18dec757eb551121bc0009f11ee4dbdcbaf83d07d28a1c3e83710ee813d63f","type":"code"} -->
```python
chain.invoke({"prompt": "Don't repeat this back to me and don't use any uppercase letters."})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"efa88722488437f110555c6594f4b552803b8f46be95e60ba5b593e4098a757e","type":"markdown"} -->
## Summarizing Chatbot Messages
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"aa772398acfcc4ba098d622653108b0ab5634c28d8d179d4debbb5c8c66928f4","type":"markdown"} -->
At this point in our work with chat models, we've utilized 3 roles, summarized in the following table.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"d5ecf37f793343b0295cfd7ecd4f4b2e4800c4c18054c387755d668f86249164","type":"markdown"} -->
<div style="display: flex; flex-direction: row; margin: 20px 2%;"><div style="float: left; background-color: #ddd; padding: 10px 40px; color: black;">

| <div style="color: black">Role</div> | <div style="color: black">Description</div> |
| --- | ------------|
|human | Human response interacting with LLM (prompt or query) |
|ai | Response from LLM |
|system | System Message that defines the role of LLM |

</div></div></div>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"e36c0fcfe234d5d362ddaf70e02648268148afd90654616ee4b09dd6e8071fbb","type":"markdown"} -->
## General Guidelines for Using Various Message Types
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"1e37aeff5bf8526c9c585eaba183e2513c6eca9d8c31f5de5c0648e7194df7a8","type":"markdown"} -->
As stated earlier, we can and should use a combination of our human message prompts from the end user, human / AI example interactions (few-shot prompts), and system messages to influence LLMs toward what we want them to generate.

Especially given that every chat model will have at least a slightly (and sometimes drastically) different orientation towards each kind of message we might send it, largely based on how it was trained, we cannot give any hard and fast rules about exactly when and where to use each of these tools you have at your disposal. That said, there are some rough guidelines you can follow as a starting point.

The final human message (typically the end-user-provided prompt) matters a lot. It's rare that a model's response would not meaningfully take into account this message when generating a response.

The system message has a large overarching impact on the model's generation. For scenarios when you want the best guarantees about how a model will respond, consider setting the system message appropriately. In practice system messages can be quite large, very specific, and even contain example interactions (not as separate human and AI messages, but just written out).

Few-shot prompting works best in combination with the system message and specific end-user prompts. Explore the use of few-shot prompts especially when specific examples are crucial for achieving the desired output format, style, or accuracy.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"8e7bd6e148929d2c8e934d363060e386e1f9ef7567e9be85f867c63e81f764e5","type":"markdown"} -->
## Exercise: Use System Message to Focus Response Topic
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"602570828b93e70b177f3c55e27781bd6540d59eb9968a66518958933d16586c","type":"markdown"} -->
Your goal for this exercise is to create 3 different LLM chains that will respond differently to the following prompt.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"31fd0b8ad73927cf4c01744049d56dd54ae761bc9ae78cf37b30dc29d4118d8d","type":"code"} -->
```python
korea_prompt = "Tell me about South Korea in less than 50 words."
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"d86bf27e50913b1ef273364e216f5f69ee2962714cbe67ed1d2089103c61a51e","type":"markdown"} -->
Specifically, one of your chains will respond to the prompt as a historian would, one as an economist would, and one as a geographer would.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"a52c2ae560e5e69784da614d4c5b71cf132fcfed2eca2a51e5e7926654134a31","type":"code"} -->
```python
historian = "You are a historian who helps users understand the culture, society, and impactful events that occurred."
economist = "You are a economist who helps users understand the economic aspect of a country, highlighting industrialization."
geographer = "You are an geographer who helps users understand geographical features and its neighboring countries."
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"67fdc1ed25c16f3bf6bd43ea913c8ddc9e53de31cbd6a355ec3cd584647d13e0","type":"markdown"} -->
Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"9ef93607fece83c682dd0f36dfafb18dc992efaa3ba2b5f29638f193b5216770","type":"markdown"} -->
There are a number of ways you could have accomplished this task, but here is one approach.

We start with a single prompt template that templatizes not only the prompt, but also the system message.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"f5a19ee9d0bf71a0616a3d7ea508f5af40f57eac14c1a8f4730f07290fb0901b","type":"code"} -->
```python
template = ChatPromptTemplate.from_messages([
    ('system', '{system_message}'),
    ('human', '{prompt}')
])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"59c7ae0e6c1a9a954b6a64fb1cf7f86fe9b536b6458a8105ce9c464d7c3cfe7c","type":"markdown"} -->
Next we create the 3 LLM chains, one for each system message.

We haven't discussed its use yet, but here we utilize the template's `.partial` method to render one of its template values here (the system message), instead of at chain execution time. You definitely did not need to use this approach in your solution, but we'd like to take the time to demonstrate its use.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"0115f44d1d186a1a442e2865e075c6b07e0cad2a8e73cc595c4cce3f27de6ae8","type":"code"} -->
```python
historian_chain = template.partial(system_message=historian) | llm | parser
economist_chain = template.partial(system_message=economist) | llm | parser
geographer_chain = template.partial(system_message=geographer) | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"360e377391f400837d9c91f61663d667acf512d09f07233ffc625b2858f662eb","type":"markdown"} -->
Totally optional, but it seemed to us like a natural time to to run the three LLM chains in parallel.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"d3a6859918af9b204b6ffe3359365435a114e0b36f5ddb89174267ee203831bf","type":"code"} -->
```python
from langchain_core.runnables import RunnableParallel
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"7596a4ca7500dba4177f81330194c7b648573a31395fdfe5bc2b5be316de87e9","type":"code"} -->
```python
chain = RunnableParallel({
    'history_response': historian_chain,
    'economy_response': economist_chain,
    'geography_response': geographer_chain
})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"b3e953b81046820f94d515941d4c04192810303ae98b8a7fd52d2e9320a451dc","type":"markdown"} -->
Here we invoke the parallel chain.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"20e4483f77791e055bcc29453a9b4a058515b4e59598f3688cb48923a0efab55","type":"code"} -->
```python
responses = chain.invoke({'prompt': korea_prompt})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"c42754190a709ecc7216ce9b52c6240e8a06a475d10c8d6b242ab1a65125c93e","type":"markdown"} -->
Finally we loop over the responses and confirm that three ~50 word responses are disctinct and on topic.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"f22d56547a582f4d60e6e9243994d5b272c46b74eb85227052644d5880e64e1d","type":"code"} -->
```python
for response in responses.values():
    print(response+'\n\n---\n')
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/33-System-Message:62","index":62,"schema":"dli-course-cell/1.0","source_sha256":"ad04100da299a1007d40c89a754389c02b57a39baaee739602a8f72978dcf7be","type":"markdown"} -->
The system message is a powerful and relatively easy to work with tool, and at this point you know how to wield it.

In the next notebook you'll continue to work explicitly with the various chat message types we've been discussing in this section, but in service of a powerful and popular technique call chain-of-thought prompting.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>3-Prompting-With-Messages/34-Chain-of-Thought.ipynb</code> next: <strong>Chain-of-Thought Prompting</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Keep one durable system instruction you trusted, so the next notebook can compare that policy layer with step-by-step reasoning scaffolds.</p>
</div>
<!-- /dli-course-cell -->
