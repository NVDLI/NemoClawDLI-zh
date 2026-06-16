<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400" height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Lab Services</b></font></h1>
<h2><b>Service: LLM Client</b>: The Lab's AI Gateway</h2>
<br>

Every notebook in this lab that talks to a language model (whether it calls
`ChatNVIDIA(...)`, `NVIDIAEmbeddings(...)`, or raw OpenAI-SDK code) goes through a
single in-network proxy: `llm_client:9000`.  This notebook explains what that proxy is,
why it exists, and how to use it from any course notebook.

---

## What it is

`llm_client` is a **FastAPI server** that runs inside the lab's Docker network on port 9000.
It presents an **OpenAI-compatible REST API** (`/v1/chat/completions`, `/v1/models`,
`/v1/embeddings`, `/v1/reranking`) and forwards requests to one or more back-end providers:

| Back-end | What it covers |
| :--- | :--- |
| **NVIDIA NIM / NIM Microservices** | 125+ hosted models (chat, embed, rerank, VLM) |
| **AWS Bedrock** | Claude 3 family via the Bedrock API |
| **NVIDIA Inference Microservices (NeMo)** | Internal research endpoints |

The server is defined in [`llm_client.py`](llm_client/llm_client.py) and built from
[`llm_client.Dockerfile`](llm_client/llm_client.Dockerfile). Its API key credentials are injected
at container start via the lab's
[`docker-compose.override.yml`](../../../docker-compose.override.yml); **no other
service or notebook holds a key**.

---

## Why it is implemented this way

```
┌─────────────────────────────────────────────────────┐
│  Notebook / microservice / agent                     │
│  http://llm_client:9000/v1/...                       │
└──────────────────────┬──────────────────────────────┘
                       │  in-network only
              ┌────────▼────────┐
              │   llm_client    │  ← one place holds keys
              │   FastAPI       │  ← unified OpenAI interface
              │   :9000         │  ← context cache, OTEL tracing
              └─────┬─────┬────┘
                    │     └─── AWS Bedrock
                    └───────── NVIDIA NIM
```

**Security.** Only `llm_client` is given the NVIDIA API key; every other container talks
to it over the private Docker network without credentials of its own.

**Portability.** Every course notebook sets `base_url = "http://llm_client:9000/v1"`.
Swapping to a different back-end is a one-line change in the gateway config, not a
refactor across 90 notebooks.

**Context cache.** The server keeps a small LRU cache of multi-turn conversations so that
repeated identical prompts from a notebook re-run do not hit the back-end again.

**Observability.** The gateway is instrumented with OpenTelemetry. Point
`OTEL_EXPORTER_OTLP_ENDPOINT` at a collector to export request/response spans; the
released stack ships none, so by default the spans are a no-op.

---

## Health validation

```python
import requests, os

r = requests.get("http://llm_client:9000/health", timeout=10)
r.raise_for_status()
d = r.json()
print(f"backends  : {d['backends']}")
print(f"models    : {d['models']}")
print(f"bedrock   : {d['bedrock_fallback']}")
print(f"cache hits: {d['context_cache']['entries']}/{d['context_cache']['max']}")
```

Expected output when healthy:
```
backends  : 4
models    : 125
bedrock   : True
cache hits: 0/500
```

---

## Basic API

### List available models

```python
import requests

r = requests.get("http://llm_client:9000/v1/models", timeout=10)
models = [m["id"] for m in r.json()["data"]]
print(f"{len(models)} models available")

# Find chat models with "nemotron" in the name
chat = [m for m in models if "nemotron" in m.lower()]
print("nemotron models:", chat[:5])
```

### Chat completion (raw HTTP)

```python
import requests, json

payload = {
    "model": "nvidia/nemotron-nano-12b-v2-vl",
    "messages": [{"role": "user", "content": "What is CUDA?"}],
    "max_tokens": 150,
    "stream": False,
}
r = requests.post("http://llm_client:9000/v1/chat/completions",
                  json=payload, timeout=30)
print(r.json()["choices"][0]["message"]["content"])
```

### Chat via LangChain (the usual pattern)

```python
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA

# base_url is set globally via NVIDIA_BASE_URL env var in the lab
llm = ChatNVIDIA(
    model="nvidia/nemotron-nano-12b-v2-vl",
    base_url=os.environ.get("NVIDIA_BASE_URL", "http://llm_client:9000/v1"),
)
reply = llm.invoke("Explain chain-of-thought prompting in one sentence.")
print(reply.content)
```

### Embeddings

```python
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

embedder = NVIDIAEmbeddings(
    model="nvidia/llama-nemotron-embed-vl-1b-v2",
    base_url=os.environ.get("NVIDIA_BASE_URL", "http://llm_client:9000/v1"),
    truncate="END",
)
vec = embedder.embed_query("semantic search is useful")
print(f"embedding dim: {len(vec)}")
```

### Streaming

```python
from langchain_nvidia_ai_endpoints import ChatNVIDIA

llm = ChatNVIDIA(model="nvidia/nemotron-3-nano-30b-a3b",
                 base_url="http://llm_client:9000/v1")

for chunk in llm.stream("List 5 benefits of microservices, one per line:"):
    print(chunk.content, end="", flush=True)
print()
```

---

## Practical: multi-model comparison

```python
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.output_parsers import StrOutputParser

BASE = "http://llm_client:9000/v1"
PROMPT = "In exactly two sentences, explain what a transformer model is."

models = [
    "nvidia/nemotron-nano-12b-v2-vl",
    "nvidia/nemotron-3-nano-30b-a3b",
    "meta/llama-3.3-70b-instruct",
]

for model_id in models:
    llm = ChatNVIDIA(model=model_id, base_url=BASE, temperature=0) | StrOutputParser()
    answer = llm.invoke(PROMPT)
    print(f"\n── {model_id} ──")
    print(answer[:300])
```

---

## Advanced: Bedrock / reasoning models

The gateway transparently routes requests to AWS Bedrock when a model ID starts with
`bedrock-proxy/`.  You can also request extended thinking (chain-of-thought reasoning)
for supported models:

```python
from langchain_nvidia_ai_endpoints import ChatNVIDIA

# Route to Claude via Bedrock. The gateway holds the Bedrock credentials.
llm = ChatNVIDIA(
    model="bedrock-proxy/anthropic.claude-3-5-sonnet-20241022-v2:0",
    base_url="http://llm_client:9000/v1",
    max_tokens=1024,
)

# Extended thinking makes the model show its reasoning before the answer
response = llm.invoke(
    "Prove that the sum of angles in a triangle is 180 degrees.",
    extra_body={"thinking": {"type": "enabled", "budget_tokens": 512}},
)
# reasoning_content is stripped by the gateway; for full traces use direct LLM.
print(response.content)
```

---

## Consumed by

`llm_client` is the sole keyholder: every model call in the stack routes through it.
The released course (nemoclaw, Securing Agents) reaches it for all chat, structured
output, and reasoning-channel cells, both directly and through the sandboxed agent it
drives. Any other in-lab service or experiment that needs inference uses the same
OpenAI-compatible gateway on `:9000`.

