<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"cbb06d4d6f294d22bd904b63e8c38d4fd0680635fd47b7cb32f08abd466c3aa6","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Streaming and Batching</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"4645755f0edef8239babaeb5a08e0731c0a7a094e4d8fd57b9217ff9355ad087","type":"markdown"} -->
In this notebook you'll learn how to stream model responses and handle multiple chat completion requests in batches.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"a3e8a7ecb83e18f4df78b9a68643d7ba4982203ec3e74b1f2783bf8d73740bab","type":"markdown"} -->
By the time you complete this notebook, you will:

- Learn to stream model responses.
- Learn to batch model responses.
- Compare the performance of batch processing to single prompt chat completion.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"4916523fec4a028006d34e8eaad31ab3f6828914ca9467f2c9ab66e3acfd56f3","type":"markdown"} -->
Here we import the `ChatNVIDIA` class from `langchain_nvidia_ai_endpoints`, which will enable us to interact with the remote `nvidia/nemotron-nano-12b-v2-vl` endpoint.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"8423d09247ffdef741b1ac0898e59f910e27d47bf2d26d46281e5320be10b26b","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"d741a922d2642a3fc57f5481f8c069b9cfe987622157b766b7bad7190f65996b","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")
model = 'nvidia/nemotron-nano-12b-v2-vl'
llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"979fb11e8476b352552cc015d4229ea0ed65ce840660a60b1af8f05cb363577a","type":"markdown"} -->
## Sanity Check
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"ea72841ac19d96f65e64d09de6e237ac43191bb88681b8164d66575c39326bed","type":"markdown"} -->
Before proceeding with new use cases, let's sanity check that we can interact with our local model via LangChain.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"1078ed45d132c4a855254b49c96b5d5807aa9c6f49eb4f6b2a9d5f7af302b9e5","type":"code"} -->
```python
prompt = 'Where and when was NVIDIA founded?'
result = llm.invoke(prompt)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"f478732f64b4eb30f81a119110259e47a2d071f3ab2176501b3866aaf4389aff","type":"code"} -->
```python
print(result.content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"f6775671b39fbe17b3197c33bc4922e402fa56797c0e676db5325adfa1f85821","type":"markdown"} -->
## Streaming Responses
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"483b26d04054fd53d56446f2b065450b05f8068ca6bdf685ca69fa8e195d3f79","type":"markdown"} -->
As an alternative to the `invoke` method, you can use the `stream` method to receive the model response in chunks. This way, you don't have to wait for the entire response to be generated, and you can see the output as it is being produced. Especially for long responses, or in user-facing applications, streaming output can result in a much better user experience.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"a2f9a2c67ea61432778fa286cbc1fac49cf6ad4caeb3859a684ec3c3cfc88d5f","type":"markdown"} -->
Let's create a prompt that generates a longer response.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"acb5813f59fca01b33689f613b778b9528cd681a51b76e92a926dccafb20c9aa","type":"code"} -->
```python
prompt = 'Explain who you are in roughly 500 words.'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"2a0c3aed5979fd60464521cc498afb21db6e78f7af8e273c373d10e39fbb807b","type":"markdown"} -->
Given this prompt, let's see how the `stream` function works.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"9ab8c4429978ac7cfe1125383383f86367812ff0930aa9f1f177a36b1d4fb7ef","type":"code"} -->
```python
for chunk in llm.stream(prompt):
    print(chunk.content, end='')
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"018e7ee2d25aa7857c12fbc855476ba09463a936f34a19d608402c07090fc378","type":"markdown"} -->
The `stream` method in LangChain serves as a foundational tool and shows the response as it is being generated. This can make the interaction with the LLMs feel more responsive and improve the user experience.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"b65ce406b6e4360ea230bfad6282dc789284735414f319386c9e18e0007e3692","type":"markdown"} -->
In subsequent notebooks we will import this helper function to assist our work.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"af34221e51193608bd13b77cc64874fdb2076d31a459ad3965d251e821da60cd","type":"markdown"} -->
## Batching Responses
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"a6d84032ab4e233184df024efd242324188cb193f6c028a63ece31f2ee9bb08e","type":"markdown"} -->
You can also use `batch` to call the prompts on a list of inputs. Calling `batch` will return a list of responses in the same order as they were passed in.

Not only is `batch` convenient when working with collections of data that all need to be responded to in some way by an LLM, but the `batch` method is designed to process multiple prompts concurrently, effectively running the responses in parallel as much as possible. This allows for more efficient handling of multiple requests, reducing the overall time needed to generate responses for a list of prompts. By batching requests, you can leverage the computational power of the language model to handle multiple inputs simultaneously, improving performance and throughput.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"57e02951bf5d2cfc68c5c1fdb8e5ebeef832812ee5f7bf1f6633fdc7082374d4","type":"markdown"} -->
We'll demonstrate the functionality and performance benefits of batching by using this list of prompts about state capitals.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"b5bd752757406c613d8b0d92b3ba512426f93f214c8b4e68dbbc86158fa7954b","type":"code"} -->
```python
state_capital_questions = [
    'What is the capital of California?',
    'What is the capital of Texas?',
    'What is the capital of New York?',
    'What is the capital of Florida?',
    'What is the capital of Illinois?',
    'What is the capital of Ohio?'
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"ea617cea8bd0a979a768252cdac72339d9f7ba7ce498beda4cf7099fb5ace201","type":"markdown"} -->
Using `batch` we can pass in the entire list...
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"805f4d394117f24147474ab2fd01a5e444fd268445774df4a72ba831b03ae3ad","type":"code"} -->
```python
capitals = llm.batch(state_capital_questions)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"5aca3ad7bee64343dfeb2abad2d2695c917fbd03498f8aff0adefe42121a1dff","type":"markdown"} -->
... and get back a list of responses.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"dcff3691e5540592a7289fa06daf0ebfbc0aaaeedc721017cf62367ce5bd3ffb","type":"code"} -->
```python
len(capitals)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"949eaaf4b43f4b52527e82ca1429b6041b25dce5d485c73c0bf18b9fd833dd73","type":"code"} -->
```python
for capital in capitals:
    print(capital.content)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"09a5f2f601ba5109a53f5b4d5e842820f0088ff4029ac1c347e472711216cb72","type":"markdown"} -->
One thing to note is that `batch` is not engaging with the LLM in a multi-turn conversation (a topic we will cover at length later in the workshop). Rather, it is asking multiple questions to a new LLM instance each time.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"e2d04e86638c3443b2c9e2227de9bb491e0cfbcfbeec873b8d2521baa3a123a2","type":"markdown"} -->
## Comparing batch and invoke Performance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"a22c4442f2e92d2fdc6f2a538e3e0c998fe2d1ffbed69a3e32a01caff75ccc0e","type":"markdown"} -->
Just to make a quick observation about the potential performance gains from batching, here we time a call to `batch`. Note the `Wall time`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"ad4c67f648dde9a33adc0e597162048debb89c790b14844a1632d179ebc1dc3e","type":"code"} -->
```python
%%time
llm.batch(state_capital_questions)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"afafade3b45f833e9766da07a90caa0a58f46dcf5c7fac511830f83e78da8262","type":"markdown"} -->
And now to compare, we iterate over the `state_capital_questions` list and call `invoke` on each item. Again, note the `Wall time` and compare it to the results from batching above.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"dfa77c3c3d9c0b434bd60232566af6e6049df67911f3f813cd6b5c52668f9060","type":"code"} -->
```python
%%time
for cq in state_capital_questions:
    llm.invoke(cq)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"7ea20e08a9b53e1c358e1a5f9697e0bba453cecb85249c826f89d70acfe0c320","type":"markdown"} -->
## Exercise: Batch Process to Create an FAQ Document
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"3054c0d7c307db968541af747404310d31106e308f905b856299597c4d1a5c48","type":"markdown"} -->
For this exercise you'll use batch processing to respond to a variety of LLM-related questions in service of creating an FAQ document (in this notebook setting the document will just be something we print to screen).

Here is a list of LLM-related questions.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"27fb5f280fd1c091d8b47cb709ef991e91ebfd1fab7d1c21a3f841eaf830a88e","type":"code"} -->
```python
faq_questions = [
    'What is a Large Language Model (LLM)?',
    'How do LLMs work?',
    'What are some common applications of LLMs?',
    'What is fine-tuning in the context of LLMs?',
    'How do LLMs handle context?',
    'What are some limitations of LLMs?',
    'How do LLMs generate text?',
    'What is the importance of prompt engineering in LLMs?',
    'How can LLMs be used in chatbots?',
    'What are some ethical considerations when using LLMs?'
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"85fb454b5f0901a28cf3aa12cd7b7ed8a0433d46ea8eb2f7cf4ab4e1663d6698","type":"markdown"} -->
You job is to populate `faq_answers` below with a list of responses to each of the questions. Use the `batch` method to make this very easy.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"011c390edcbff40b1c513d665ecd08f6e4d612d09930b32337bded529e516e08","type":"markdown"} -->
Upon successful completion, you should be able to print the return value of calling the following `create_faq_document` with `faq_questions` and `faq_answers` and get an FAQ document for all of the LLM-related questions above.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"b11dcdaa09406799154091df54e87a3fca8d74834b3cb94d04fbc7633ff099e8","type":"code"} -->
```python
def create_faq_document(faq_questions, faq_answers):
    faq_document = ''
    for question, response in zip(faq_questions, faq_answers):
        faq_document += f'{question.upper()}\n\n'
        faq_document += f'{response.content}\n\n'
        faq_document += '-'*30 + '\n\n'

    return faq_document
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"27f85ff6642ac151b52af801f7027406a68311baf7f97447cb5b6ae3bad549eb","type":"markdown"} -->
If you get stuck, check out the *Solution* below.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"d449675ba502bf7bff4493037ed45587ec0bdbb46077b235ea1ff3317a470b5b","type":"code"} -->
```python
faq_answers = []
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"4b422ee2fac57b660d8bd6d020969f292a2bcc292860cf95715d685e8154f5e9","type":"code"} -->
```python
# This should work after you successfully populate `faq_answers` with LLM responses.
print(create_faq_document(faq_questions, faq_answers))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"112d485a1101c424a02eb08bf6b2a6c8833b45ec4a89a8232660dec2d5b3f363","type":"code"} -->
```python
faq_answers = llm.batch(faq_questions)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"26af32b23353e1df1d4399210ba832532380010389dc548f3fecf97030b1b421","type":"code"} -->
```python
def create_faq_document(faq_questions, faq_answers):
    faq_document = ''
    for question, response in zip(faq_questions, faq_answers):
        faq_document += f'{question.upper()}\n\n'
        faq_document += f'{response.content}\n\n'
        faq_document += '-'*30 + '\n\n'

    return faq_document
###################################################################
## Fancier solution: Create the markdown, and then render it
from IPython.display import display, Markdown

def md_blocq(body):
    return f"<blockquote>\n\n{body}\n\n</blockquote>"

def md_details(head, body):
    return f"<details><summary><b>{head}</b></summary>{md_blocq(body)}</details>"

def create_faq_document(faq_questions, faq_answers):
    faq_document = ''
    for question, response in zip(faq_questions, faq_answers):
        faq_document += md_details(question, response.content)

    return faq_document

Markdown(create_faq_document(faq_questions, faq_answers))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"5655f8586e45c792001cf095223b8a76f50c1574d9200fae233697213a52d10c","type":"code"} -->
```python
print(create_faq_document(faq_questions, faq_answers))
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"1-Intro-to-Prompting/14-Streaming-and-Batching:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"02c08e5e4e539bf359084a917a14e8cdd6dc45324807370990f3ce95cdcfaa64","type":"markdown"} -->
In this notebook you learned how to stream and batch model responses, and used batched LLM calls to generate a helpful FAQ document.

In the next notebook you'll begin focusing more heavily on the creation of prompts themselves with an emphasis on iterative prompt development and engineering prompts that are very specific.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>1-Intro-to-Prompting/15-Iterative-Prompting.ipynb</code> next: <strong>Iterative Prompt Development</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Keep one case where streaming or batching changed the workflow payoff, so the next notebook can focus on improving the prompt itself rather than the transport pattern.</p>
</div>
<!-- /dli-course-cell -->
