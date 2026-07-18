<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"57d4f0e63431fc3779d353eab92a52a874bcf00c6c4463d805ed3edf957d254c","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Combining Chains</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"f7300bd100543ff0802abbc8019b3feefcbedcbd1df9dc64e00637f979b0ee11","type":"markdown"} -->
In this notebook you'll learn how to compose multiple LLM-related chains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"1e13c60e53994cde7abf112caa2bf76d2b9b2d9f7c9d946894aea425726382e8","type":"markdown"} -->
By the time you complete this notebook you will:

- Learn how to compose chains of chains
- Apply your ability to chain meaningful language tasks.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"6ce8c64cc27cf259c1c2248dafef09e7c7a07e38b3705966b65e7185fd3ba288","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"fe8a07f8e29704ed8c72091c34ce44956cd4b2a6331a6a6220553baac2abf3d3","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")

# Use the model selected in the course connection panel, or keep the lesson default.
model = os.getenv("NVIDIA_MODEL") or "nvidia/nemotron-nano-12b-v2-vl"
# model = "nvidia/nemotron-3-nano-30b-a3b"  # Compatible fallback; responses may differ.
# model = "meta/llama-3.3-70b-instruct"  # Legacy fallback; responses may differ more.

llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"5dad838170cfa01e63dbac104194db6bdcd2e521eca706b626a71591fccd49f4","type":"markdown"} -->
## Combining Multiple LLM Chains
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"65c8e86d68eb4387375e3c68c0995d56e661bdc237a40547bb3430d17b2ce85c","type":"markdown"} -->
If you recall, runnables can be composed into chains, but also, chains are themselves runnables. Therefore, chains can be used to compose larger chains.

It's easy to imagine tasks we would like to perform that would require multiple calls to an LLM for the desired end result. We'll begin our exploration of chaining chains with such a scenario, where we will compose multiple LLM chains, piping the output of one chain into the next.

To do this we are going to work with the following list of `thesis_statements`. Note: any typos you see in the thesis statements are intentional.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"80642b90feb6a7287c84b6b1dff6434d1ff5502d2e6f9cded559c1cf8b3aceff","type":"code"} -->
```python
thesis_statements = [
    "The fundametal concepts quantum physcis are difficult to graps, even for the mostly advanced students.",
    "Einstein's theroy of relativity revolutionised undrstanding of space and time, making it clear that they are interconnected.",
    "The first law of thermodynmics states that energy cannot be created or destoryed, excepting only transformed from one form to another.",
    "Electromagnetism is one of they four funadmental forces of nature, and it describes the interaction between charged particles.",
    "In the study of mechanic, Newton's laws of motion provide a comprehensive framework for understading the movement of objects under various forces."
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"c8b3f5fe7fcb3b119b432d9695acbcd26d9650b5e730726b63d7252b1cdfae37","type":"markdown"} -->
Our goal is going to be to expand each of these thesis statements into a well-written paragraph, with the thesis statement itself being the first paragraph. You may have noticed, however, that each of these thesis statements contains spelling and/or grammar errors that need correcting.

Therefore, we are going to create a chain first to address the spelling and grammar issues, and then chain the corrected thesis statements into a second LLM chain responsible for generating the full paragraphs.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"b0b97b78e4645bcd2d0fd13c67c34409c258422e10e55be64ec330d95caacbbc","type":"markdown"} -->
## Exercise: Create a Spelling and Grammar Chain
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"5e67fc48752cbb6e7f823356e29c351421d51c95413d9d64abe704e5ebacd6f6","type":"markdown"} -->
To begin, create `grammar_chain` which returns its inputs after performing spelling and grammar corrections on them.

We already have an LLM instance defined above (`llm`), but you will need to create both a prompt template and output parser to include in your chain.

You may need to develop your prompt template iteratively. Make sure especially that the chain returns only the corrected text, and not any additional comments etc. from the model.

Test your chain by sending it the batch of `thesis_statements` defined above.

Check out the solution below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"204e3a27c38130d0fd2d9c37ff5b38633d394e137e29cdbd019aaaf8bee24de8","type":"code"} -->
```python
grammar_chain = 'TODO' # TODO: grammar_chain should return its inputs after performing spelling and grammar on them.
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"34e401c7cc73f661ed9befc5483b88625f847cc4b57b6ad49655bd31ef1084bc","type":"markdown"} -->
We begin by engineering a prompt for spelling and grammar correction. We take care to be specific in our prompt that the model should generate only the corrected text with no addional comment or preface.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"ed150aa5d3c6bddcd305c030ab225bab6fa32a2958c5664a3f659dc9b7f52d7b","type":"code"} -->
```python
spelling_and_grammar_template = ChatPromptTemplate.from_template(
    "Fix any spelling or grammatical issues in the following text."
    " Return back the correct text and only the corrected text with"
    " no additional comment or preface. Text: {text}"
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"c52422e6933817bb5afbbbfdb992a149ec8f00bf9aee87369c719af767b103f2","type":"markdown"} -->
Next we create an instance of a string output parser.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"a45d5e7d2a81f7cdc07183c70e44e42aa65c9d434cd853383f168af4980f7d4d","type":"code"} -->
```python
parser = StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"78305dbe73d42ba83314ee83bf5e9b387befcae27ffb361c1cbd523ee9c58cd2","type":"markdown"} -->
All that's left to do is compose the chain...
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"05d924ec78c42dd2e11364e6d6b3aa85d628a1dab7e0878b79b8ee5f7445d51a","type":"code"} -->
```python
grammar_chain = spelling_and_grammar_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"f16467a27fe9b1499809cfa5a9f6b403ac98a721c020f72afaf190e8cc1e2fb4","type":"markdown"} -->
...and pass the thesis statements to it in batch.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"bc832b1ea73223cd874de30acf4a7daa11d2c05c70c99ae2578154d9bd5fd72e","type":"code"} -->
```python
corrected_texts = grammar_chain.batch(thesis_statements)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"05cff46b7a8f52dc9bd27c77e200ac12fc11f78efed9d05ed31876f80ac230c4","type":"markdown"} -->
Looking at the corrected outputs, it appears that the model did an excellent job.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"5fcbeaed7940d88fae60c64e96ac21818e833df6778461fe8aaf0a84f58a8587","type":"code"} -->
```python
for corrected_text in corrected_texts:
    print(corrected_text)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"587e1f9dc89b18fc6c025475ffb98b5ec68d0c83b8b1054f09cddb28d4535ed3","type":"markdown"} -->
## Exercise: Create a Paragraph Generator Chain
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"2d913061e662c5567fa2ab63f44993a706e708334aa264dc259c20bd0f85b9c6","type":"markdown"} -->
Create a second chain called `paragraph_generator_chain`. Given a sentence as input, it should use that sentence as the first sentence of a paragraph which it should generate.

**Note:** this chain should not contain any grammar or spell checking functionality. The chain should be responsible only for the paragraph generation task.

Test your chain by sending it the batch of `thesis_statements` defined above.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"2aaa66191a7542290be58e38bdc0520369a4101e2d1bef1713ae144308029a63","type":"code"} -->
```python
paragraph_generator_chain = 'TODO'
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"8462ae2d4dbfb00f27e3153359bde30b5482c8f3dd85354c469456579e72d8b1","type":"markdown"} -->
We begin the task by engineering a prompt.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"eb6a6fd162fec18ef5d2096ba74e86343b98f07c38c0ad03026eca9e65b0af80","type":"code"} -->
```python
paragraph_generator_template = ChatPromptTemplate.from_template(
    "Generate a 4 to 8 sentence paragraph that begins with the following thesis statement."
    " Return back the paragraph and only the paragrah with no addional comment or preface."
    " Thesis statement: {thesis}"
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"c0b563dc836c110b4f12f40c35a8f9120f28c87fc06aecf6fc35f6edf0888847","type":"markdown"} -->
Since we already have a model instance and parser, all we have to do is compose the chain...
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"3d680c2288ea2deba6017d955a4c771bb1c72f37add045696d0a659a8d75fefe","type":"code"} -->
```python
paragraph_generator_chain = paragraph_generator_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"4107345da9c5289c3caa54a0b3a8a0e4ced3148eb32a8cf1e8cde817425644ea","type":"markdown"} -->
...and send it the batch of thesis statements.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"f6da1d3c2deee50fc0e4750d454e03a0f968fb6e7e3fa5c48b4847d9e747ff28","type":"code"} -->
```python
paragraphs = paragraph_generator_chain.batch(thesis_statements)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"869bb28ec3926be30b56f7610fb9efe52d47a87020dce0c629e0d32d4c09c261","type":"markdown"} -->
Looking at the generated paragraphs, it looks like the model did a great job.

It's worth highlighting that even though we did not prompt the model to address spelling and grammar mistakes, it did fix some of the spelling mistakes anyway, however, it's clear that most of the grammar errors from the thesis statements we passed in are still present.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"df5e20907b90a423466d248b9a3088e2f2368e0a727439e3badbce428c2cc748","type":"code"} -->
```python
for paragraph in paragraphs:
    print(paragraph+'\n')
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"5540db10343f05a8139f18ab6cea39b3ebc108d685cdb363a218e85b7ce70bba","type":"markdown"} -->
## Exercise: Create a Chain of Chains
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"cdeff876d6082afce323aaa1ddcbc4958d3d98d9dad84792498dfe1616a0e0c1","type":"markdown"} -->
Reusing the chains you've already created, create a `corrected_generator_chain` that uses the LLM first to perform spelling and grammar corrections on `thesis_statements` before then generating full paragraphs based the (corrected) thesis statements.

You don't need to overthink this. Just remember, chains are runnables, and can be piped together just like any other runnable.

Test your chain by sending it the batch of `thesis_statements` defined above.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"578968f95805735b47f15017470696d8b5df07999e428a3e6c762a14f7bd622a","type":"markdown"} -->
All we have to do to create our larger chain is to pipe together the 2 chains we already created.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"1541134fe25f9bc8186d4251b57e8c3374e9e2f33b1094d46f54ff9288b4152a","type":"code"} -->
```python
corrected_generator_chain = grammar_chain | paragraph_generator_chain
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"113b83e7446f3a21a02c520ddf4e72398556ed96bb369325a3755859b63a5960","type":"markdown"} -->
Just because it will be interesting, we can take a look at the computational graph for our new chain.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"1b8e88ff0525dcff280b75f0f141ee98efd89008a84b5d1b3d411386ac8c3c89","type":"code"} -->
```python
print(corrected_generator_chain.get_graph().draw_ascii())
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"5f3da9c377710614e0607e79232a5dec2ef35e9984ba4ebe38ca9e5d35364ceb","type":"markdown"} -->
We can batch send our thesis statements to this larger chain just as we did with the smaller chains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"a86631759edeb4e2a84fce38178ffc565dec9f39e896551d59959411b9d60d14","type":"code"} -->
```python
paragraphs = corrected_generator_chain.batch(thesis_statements)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"1eb366be7b67dcbf062e8c5543fc7604d164d20e28dd8056628dc8c9c2898a78","type":"markdown"} -->
Looking at the final outputs we can see that the paragraphs were well-generated, but also, that all the spelling and grammar mistakes in the original thesis statements have been addressed.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"df5e20907b90a423466d248b9a3088e2f2368e0a727439e3badbce428c2cc748","type":"code"} -->
```python
for paragraph in paragraphs:
    print(paragraph+'\n')
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/23-Combining-Chains:62","index":62,"schema":"dli-course-cell/1.0","source_sha256":"bc39a58ffa56892f89e8fbe4145a6717021701efe128d1b80d5336b4c913c4ac","type":"markdown"} -->
In this notebook you learned to treat chains as the runnable they are and combine them together, including in ways that allowed you to leverage LLMs multiple times to accomplish a desired task.

In the next notebook you'll continue on the theme of chain composition, but this time focusing on the ability to create and utilize parallel chains.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>2-Chains/24-Parallel-Chains.ipynb</code> next: <strong>Parallel Chains</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Keep one intermediate output that became the next chain input, because the next notebook asks which of those steps can safely branch and run at the same time.</p>
</div>
<!-- /dli-course-cell -->
