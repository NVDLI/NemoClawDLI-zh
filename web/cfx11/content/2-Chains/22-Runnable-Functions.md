<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"e1bf98164b6c24a04f485074ac3e04109dd93a0411ce1d3ef098f4f957a34b9c","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Runnable Functions</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"4aedbe182893130c5f3a3cacd4ede738dbf331958795ffd841250f6082f25c0f","type":"markdown"} -->
In this notebook you will learn how to convert custom functions into runnables that can be included in LangChain chains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7ed1d5d3598d9dfd44ff52aa769434d46ec975cd34ded253e39b3b255ea9be1a","type":"markdown"} -->
## Objectives
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"539fdd153e122437f53db657d2e5cb982417aa8edc988fdd7748413fe799e4b0","type":"markdown"} -->
By the time you complete this notebook you will:

- Understand how to create custom runnable functions and include them in your LangChain chains.
- Use custom runnable functions to preprocess data before sending it to an LLM.
- Use custom functions to batch translate raw text into prompt templates.
- Create a LangChain sentiment analysis chain utilizing multiple custom runnable functions.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:5","index":5,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:6","index":6,"schema":"dli-course-cell/1.0","source_sha256":"d357b415148d05679d1f9802803fc0a4a039f4ece72445b0c3c596b0eb555b52","type":"markdown"} -->
## Imports
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:7","index":7,"schema":"dli-course-cell/1.0","source_sha256":"f9a61e61e84079394f73c99fc764abf86261eb67240e70807f5a369942aa4ba6","type":"code"} -->
```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:8","index":8,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:9","index":9,"schema":"dli-course-cell/1.0","source_sha256":"70f5e78e300511808de404ed1d62799fc55c2b20e6c2a33706e13dbca5acc811","type":"markdown"} -->
## Create a Model Instance
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:10","index":10,"schema":"dli-course-cell/1.0","source_sha256":"d741a922d2642a3fc57f5481f8c069b9cfe987622157b766b7bad7190f65996b","type":"code"} -->
```python
base_url = os.getenv("NVIDIA_BASE_URL")
model = 'nvidia/nemotron-nano-12b-v2-vl'
llm = ChatNVIDIA(base_url=base_url, model=model, temperature=0)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:11","index":11,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:12","index":12,"schema":"dli-course-cell/1.0","source_sha256":"44486606ecca0d1c34221e760139cf7c54f5cdfe68d5a3fb3bd77c2821983c4b","type":"markdown"} -->
## Using `RunnableLambda` to Create Custom Runnable Functions
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:13","index":13,"schema":"dli-course-cell/1.0","source_sha256":"3870edecaa0afa86dac094525ad5fa158412211943f5a26a71e59d98dabf52a7","type":"markdown"} -->
We have already seen that LangChain provides composable runnables in the forms of LLM instances, prompt templates, and output parsers. Another powerful tool that LangChain provides is the ability to convert arbitrary functions into runnables with `RunnableLambda`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:14","index":14,"schema":"dli-course-cell/1.0","source_sha256":"086797b00de6d9c3efcc74be79450b3b26022f25b84fd1eff62857acb128ded6","type":"code"} -->
```python
from langchain_core.runnables import RunnableLambda
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:15","index":15,"schema":"dli-course-cell/1.0","source_sha256":"0fad2cc7e094f109b1da0916258ab5808b8a3b8104d8333cfa3e86abd5d97421","type":"markdown"} -->
We will begin exploring custom runnable functions with a simply math function.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:16","index":16,"schema":"dli-course-cell/1.0","source_sha256":"ec688482d2c4364c85a5097428983e4bef9f0e99f489e909d8eec106fb8bc8a7","type":"code"} -->
```python
def double(x):
    return 2*x
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:17","index":17,"schema":"dli-course-cell/1.0","source_sha256":"9174a79750c816c007737b171cb0340f7de72f482266ae9a82f7404cc7526007","type":"markdown"} -->
It should come as no surprise that this simple Python function does not have a LangChain runnable's `invoke` (or `batch` or `stream`) method.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:18","index":18,"schema":"dli-course-cell/1.0","source_sha256":"c290234111729b0918da4fef409cce38779c5d8b0f0e01a45337742766146ac3","type":"code"} -->
```python
try:
    double.invoke(2)
except AttributeError:
    print('`double` is a Python function and does not have an `invoke` method.')
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:19","index":19,"schema":"dli-course-cell/1.0","source_sha256":"18ff2bef8770190f832e3b01620aa205e9f7d4079bbced4da33d8fd763b1d131","type":"markdown"} -->
However, we can easily convert it into a LangChain runnable by passing it into `RunnableLambda`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:20","index":20,"schema":"dli-course-cell/1.0","source_sha256":"ceb11257228732029a1f40e7d9e08f55146e0df3c3ab004d8006866a4f0d2ba5","type":"code"} -->
```python
runnable_double = RunnableLambda(double)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:21","index":21,"schema":"dli-course-cell/1.0","source_sha256":"589231df2986ba2ba18ed2958674ba64d8878fcf7d19c3f80d73e5fffd5b30db","type":"code"} -->
```python
runnable_double.invoke(6)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:22","index":22,"schema":"dli-course-cell/1.0","source_sha256":"493b946f267a1273f3824e204a31f7856578fef768f96b6a8c81da5b29f21a3c","type":"code"} -->
```python
runnable_double.batch([2, 4, 6, 8])
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:23","index":23,"schema":"dli-course-cell/1.0","source_sha256":"c35a4580af43093a055ab3a1d5d01a1b94c6d5a6ef1fcdda51f44f8d6ed2c65a","type":"markdown"} -->
Like other runnables, custom function runnables like `runnable_double` can be composed into chains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:24","index":24,"schema":"dli-course-cell/1.0","source_sha256":"d8e41d251f4be408e66898c342980f290e556293f3f67a299f6164ca7151024f","type":"code"} -->
```python
multiply_by_eight = runnable_double | runnable_double | runnable_double
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:25","index":25,"schema":"dli-course-cell/1.0","source_sha256":"c2bf4008167c13142ae30782f7ea5559cde74cda88fd4ef8d0c0caa0070dc75e","type":"code"} -->
```python
multiply_by_eight.invoke(11)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:26","index":26,"schema":"dli-course-cell/1.0","source_sha256":"883661aad52402405adfc20fede6deb42b5424df26ebaa63883f23b296b2cd7b","type":"markdown"} -->
Your own creativity is the only limit as to how you might utilize custom functions in your chains, but for the remainder of this notebook we'll explore a couple common use cases for custom runnable functions in chains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:27","index":27,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:28","index":28,"schema":"dli-course-cell/1.0","source_sha256":"69426955dc5d61452d4ec90d30ad1cf286f154769a8d910ebc48044418740c06","type":"markdown"} -->
## Data Management
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:29","index":29,"schema":"dli-course-cell/1.0","source_sha256":"c077a853e6d2020fecd494974f0d877c29512e811cde1d0c7bd2b5cc97b82dff","type":"markdown"} -->
Whether for formatting, correction, or validation, you may wish to perform some work on data passing through your chains either before or after interacting with an LLM.

As an example, suppose you are building a sentiment analysis application where user reviews are analyzed for their sentiment. User reviews can contain various inconsistencies like mixed capitalization, extra whitespace, and contractions. Normalizing this text before sending it to the LLM can improve the accuracy of the sentiment analysis.

The following `normalize_text` function will normalize text by converting it to lowercase, expanding contractions, and removing extra whitespace.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:30","index":30,"schema":"dli-course-cell/1.0","source_sha256":"fd5e5458a3d60c5b1421a9a61404778131d7845348ce28a0d7627870b0534239","type":"code"} -->
```python
import re
import contractions # pip install contractions

def normalize_text(text):
    # Convert text to lowercase
    text = text.lower()
    
    # Expand contractions
    text = contractions.fix(text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:31","index":31,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:32","index":32,"schema":"dli-course-cell/1.0","source_sha256":"d3b53d6c930c4546fbfd9cddff371966ff509458b653829bea365f61b159946e","type":"markdown"} -->
## Exercise: Create Runnable Function to Normalize Text
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:33","index":33,"schema":"dli-course-cell/1.0","source_sha256":"370c66348593ee9918d785ea161c5a0a0f34b77e9b1d6977744d924fbf7889f9","type":"markdown"} -->
Use what you've learned so far about creating runnable functions to create one out of the `normalize_text` function provided above.

Upon successful implementation, you should be able to use it to batch process the following toy list of reviews.

Feel free to check out the *Solution* below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:34","index":34,"schema":"dli-course-cell/1.0","source_sha256":"5a72b36ce36569bb489f7f60806b50bf9e2b4dfbd54e119424ac68617d50e0f5","type":"code"} -->
```python
reviews = [
    "I LOVE this product! It's absolutely amazing.   ",
    "Not bad, but could be better. I've seen worse.",
    "Terrible experience... I'm never buying again!!",
    "Pretty good, isn't it? Will buy again!",
    "Excellent value for the money!!! Highly recommend."
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:35","index":35,"schema":"dli-course-cell/1.0","source_sha256":"58fa68be734d1b62b1ced799ad754353678f5cc20147be2dd226208550872042","type":"markdown"} -->
### Your Work Here
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:36","index":36,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:37","index":37,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:38","index":38,"schema":"dli-course-cell/1.0","source_sha256":"530f645ab18c126a0241dd03a4f37d3fe1e0db1d61e737e2fca72b51dcdfeae7","type":"code"} -->
```python
RunnableLambda(normalize_text).batch(reviews)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:39","index":39,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:40","index":40,"schema":"dli-course-cell/1.0","source_sha256":"0b8bccd5a54b3ce3c6e8d9b6a5db1542a698ff0450452b9b8db6d9df495067c0","type":"markdown"} -->
## Formatting Text for Prompt Templates
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:41","index":41,"schema":"dli-course-cell/1.0","source_sha256":"b1b995684f552f23a0211e97eb5677f8a8bbe98faa0ecce799d6d6f3023c6d77","type":"markdown"} -->
In the previous exercise you ended up with a list of normalized reviews like the following.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:42","index":42,"schema":"dli-course-cell/1.0","source_sha256":"11a55ca37891362eeae36c0fb32a8d871ab9fbc2552cf5668b5fd364d60987f2","type":"code"} -->
```python
normalized_reviews = [
    'i love this product! it is absolutely amazing.',
    'not bad, but could be better. i have seen worse.',
    'terrible experience... i am never buying again!!',
    'pretty good, is not it? will buy again!',
    'excellent value for the money!!! highly recommend.'
]
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:43","index":43,"schema":"dli-course-cell/1.0","source_sha256":"003b93617cf37a0e6f5b195e3e52da1ee4af2056cd6670153a7281a3aa4b8462","type":"markdown"} -->
Let us assume now that we would like to pipe these normalized reviews in to a prompt template for sentiment analysis like the following `sentiment_template`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:44","index":44,"schema":"dli-course-cell/1.0","source_sha256":"3d85695a172ae0272709f69e1da033d95910e2619d65a836cc1414f47269f8a1","type":"code"} -->
```python
sentiment_template = ChatPromptTemplate.from_template(
    "In a single word, either 'positive' or 'negative',"
    " provide the overall sentiment of the following piece of text: {text}"
)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:45","index":45,"schema":"dli-course-cell/1.0","source_sha256":"c252165baead8a54e9d8026653e8df0301cdb9d3266379bdeb422cb1d9e598ec","type":"markdown"} -->
We know from the previous notebook that to invoke the above template, we need to pass in a dictionary that contains keys for its placeholders (`{text}` in the above template), for example:
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:46","index":46,"schema":"dli-course-cell/1.0","source_sha256":"8c930cf83e52c203bf7ff79e6e956435544a465e26c3921b49beef51bad6b68c","type":"code"} -->
```python
sentiment_template.invoke({"text": 'i love this product! it is absolutely amazing.'})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:47","index":47,"schema":"dli-course-cell/1.0","source_sha256":"37f381b6c9989d6060ada1144df0aa705d9e15e01b9badee005b11ef4d9c85d5","type":"markdown"} -->
Therefore, in order to prepare the items in `normalized_review` for being piped into `sentiment_template`, we need to convert each line of text into a dictionary with the key `"text"` and the value the actual line of text.

Let's create a runnable lambda to accomplish this. For this function we'll use an actual lambda function since the work we need to do is so minimal and define the runnable lambda straightaway.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:48","index":48,"schema":"dli-course-cell/1.0","source_sha256":"9bf843ea0da25a5490ddb267b35bd76707b57252f475803bc9ad181dd28f23ad","type":"code"} -->
```python
prep_for_sentiment_template = RunnableLambda(lambda text: {"text": text})
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:49","index":49,"schema":"dli-course-cell/1.0","source_sha256":"8a3ad010d57b8376e33471a6c9f2f5ef73321e0291a220dd665dde3dac74a3eb","type":"markdown"} -->
We can now use `prep_for_sentiment_template` to prep `normalized_reviews` for `sentiment_template`.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:50","index":50,"schema":"dli-course-cell/1.0","source_sha256":"121d919cc67c4575941a51aca5184f3876eb16cf493e3cab086eff604f1314da","type":"code"} -->
```python
prep_for_sentiment_template.batch(normalized_reviews)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:51","index":51,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:52","index":52,"schema":"dli-course-cell/1.0","source_sha256":"89420de08cc01785e7295f6daa034dfc09b1169266b3ab4928fb9c45bf2268c3","type":"markdown"} -->
## Exercise: Create a Sentiment Analysis Chain
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:53","index":53,"schema":"dli-course-cell/1.0","source_sha256":"952510480d8d1f9bcec5ca2d714b77251d3493b1ea4b9d5b8fba0fdf9267d696","type":"markdown"} -->
For this exercise, create a sentiment analysis chain that you can pass the original `reviews` list above into as a batch.

Your chain should:
- Normalize the raw reviews.
- Prepare the normalized reviews for use in `sentiment_template` (defined above).
- Pipe the prepared normalized reviews through the `sentiment_template`.
- Pipe the prompt templates to `llm` (already defined above).
- Conclude by parsing the LLM outputs with an instance of `StrOutputParser`, which you will need to instantiate.

Feel free to check out the solution below if you get stuck.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:54","index":54,"schema":"dli-course-cell/1.0","source_sha256":"2db061719e7ef70e522d024c9f1833e72391e39089f16008f0024269c4126d9c","type":"markdown"} -->
### Your Work
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:55","index":55,"schema":"dli-course-cell/1.0","source_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","type":"code"} -->
```python
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:56","index":56,"schema":"dli-course-cell/1.0","source_sha256":"eb90ed3f74a5e9009c6633c2e44657cd53d6fb3a6a0427e0f2be9986882c3530","type":"markdown"} -->
### Solution
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:57","index":57,"schema":"dli-course-cell/1.0","source_sha256":"c4f9258f6f87e27e000287afd7d7f98c2f01275141ff0d9734643b9397410d32","type":"markdown"} -->
The only component of the chain we haven't created yet is the output parser, so we create it here.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:58","index":58,"schema":"dli-course-cell/1.0","source_sha256":"a45d5e7d2a81f7cdc07183c70e44e42aa65c9d434cd853383f168af4980f7d4d","type":"code"} -->
```python
parser = StrOutputParser()
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:59","index":59,"schema":"dli-course-cell/1.0","source_sha256":"0969449497b942162239eaf3c43f004239804c43cd5586ac6aa0931488f3c367","type":"markdown"} -->
With all the runnables created, we can compose our chain.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:60","index":60,"schema":"dli-course-cell/1.0","source_sha256":"112557860d9194014b2de888b063b8d16000b43c97bf50515e34a4b3c324b83f","type":"code"} -->
```python
sentiment_chain = RunnableLambda(normalize_text) | prep_for_sentiment_template | sentiment_template | llm | parser
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:61","index":61,"schema":"dli-course-cell/1.0","source_sha256":"7b1d218e665f10d51ac20c25b74bc17380da1239db8a0dc01db56e6f7ef2a671","type":"markdown"} -->
Now we can batch our raw reviews through the chain.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:62","index":62,"schema":"dli-course-cell/1.0","source_sha256":"fae5a819b126c19ee5f0a1f99ff76ec38015c61f1b4e6ef710121a6fcd05c243","type":"code"} -->
```python
sentiment_chain.batch(reviews)
```
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:63","index":63,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:64","index":64,"schema":"dli-course-cell/1.0","source_sha256":"30ac03ff33731529441be8fbe52a3bd0d4c5ec830e806d54692168ebb7f98ada","type":"markdown"} -->
## Summary
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"2-Chains/22-Runnable-Functions:65","index":65,"schema":"dli-course-cell/1.0","source_sha256":"6a4607e953f48f62bef3a8231b52a9aa0f6a59d05a32b78ec19ad30f2e47502f","type":"markdown"} -->
In this notebook you learned how to create custom runnables to include in your chains. As it turns out, chains themselves are runnables, and in the next notebook you'll begin learning how to chain together chains.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>2-Chains/23-Combining-Chains.ipynb</code> next: <strong>Combining Chains</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Remember one custom function that belongs in the pipeline, so the next notebook can show how that piece composes with model-driven steps instead of standing alone.</p>
</div>
<!-- /dli-course-cell -->
