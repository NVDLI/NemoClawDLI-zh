# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Browser compatibility layer for the APIs exercised by c-fx-11-v1.

This module preserves the learner-facing Python while providing the narrow
LangChain, OpenAI, display, and assessment interfaces used by the imported
course. Model operations call the real NVIDIA OpenAI-compatible endpoint.
"""

from __future__ import annotations

import json
import os
import re
import sys
import types
from dataclasses import dataclass
from functools import wraps
from pyodide.ffi import run_sync
from js import courseNvidiaChat, coursePublicJson


def _record(event, **detail):
    trace = globals().setdefault("COURSE_EXECUTION_TRACE", [])
    trace.append({"event": event, **detail})


def _json_default(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "content"):
        return value.content
    return str(value)


def _content(value):
    return value.content if hasattr(value, "content") else value


def _message_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"role": "user", "content": value}
    role = getattr(value, "role", None) or getattr(value, "type", "user")
    role = {"human": "user", "ai": "assistant"}.get(role, role)
    result = {"role": role, "content": getattr(value, "content", str(value))}
    if getattr(value, "tool_calls", None):
        result["tool_calls"] = value.tool_calls
    if getattr(value, "tool_call_id", None):
        result["tool_call_id"] = value.tool_call_id
    if getattr(value, "name", None):
        result["name"] = value.name
    return result


class BaseMessage:
    role = "user"
    type = "human"

    def __init__(self, content="", **kwargs):
        self.content = content
        self.additional_kwargs = dict(kwargs.get("additional_kwargs") or {})
        self.tool_calls = kwargs.get("tool_calls", [])
        self.tool_call_id = kwargs.get("tool_call_id")
        self.name = kwargs.get("name")

    def pretty_print(self):
        label = {"user": "Human", "assistant": "AI", "system": "System", "tool": "Tool"}.get(self.role, self.role.title())
        print(f"{' ' + label + ' Message ':=^40}\n\n{self.content}")

    def __repr__(self):
        args = [f"content={self.content!r}"]
        if self.tool_calls:
            args.append(f"tool_calls={self.tool_calls!r}")
        if self.additional_kwargs:
            args.append(f"additional_kwargs={self.additional_kwargs!r}")
        return f"{type(self).__name__}({', '.join(args)})"


class HumanMessage(BaseMessage):
    role = "user"
    type = "human"


class AIMessage(BaseMessage):
    role = "assistant"
    type = "ai"


class AIMessageChunk(AIMessage):
    pass


class SystemMessage(BaseMessage):
    role = "system"
    type = "system"


class ToolMessage(BaseMessage):
    role = "tool"
    type = "tool"


MESSAGE_TYPES = {
    "human": HumanMessage,
    "user": HumanMessage,
    "ai": AIMessage,
    "assistant": AIMessage,
    "system": SystemMessage,
    "tool": ToolMessage,
}


@dataclass
class ChatPromptValue:
    messages: list

    def to_messages(self):
        return self.messages

    def __repr__(self):
        return f"ChatPromptValue(messages={self.messages!r})"


class GraphView:
    def __init__(self, nodes):
        self.nodes = nodes

    def draw_ascii(self):
        return "\n  |\n  v\n".join(f"[{node}]" for node in self.nodes)

    def draw_mermaid_png(self):
        labels = [str(node) for node in self.nodes]
        width = 760
        height = max(120, 72 * len(labels) + 30)
        boxes = []
        arrows = []
        for index, label in enumerate(labels):
            y = 20 + index * 72
            safe = (label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            boxes.append(f'<rect x="80" y="{y}" width="600" height="46" rx="8"/><text x="380" y="{y + 29}" text-anchor="middle">{safe}</text>')
            if index:
                arrows.append(f'<path d="M380 {y - 26} V{y}" marker-end="url(#arrow)"/>')
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z"/></marker></defs>
{''.join(arrows)}{''.join(boxes)}</svg>'''
        return svg.encode("utf-8")


class Runnable:
    label = "Runnable"

    def invoke(self, value):
        raise NotImplementedError

    def batch(self, values):
        return [self.invoke(value) for value in values]

    def stream(self, value):
        yield self.invoke(value)

    def __or__(self, other):
        return RunnableSequence([self, as_runnable(other)])

    def __ror__(self, other):
        return RunnableSequence([as_runnable(other), self])

    def get_graph(self):
        return GraphView([self.label])


def as_runnable(value):
    if isinstance(value, Runnable):
        return value
    if isinstance(value, dict):
        return RunnableParallel(value)
    if callable(value):
        return RunnableLambda(value)
    raise TypeError(f"{value!r} is not a runnable")


class RunnableSequence(Runnable):
    label = "RunnableSequence"

    def __init__(self, steps):
        flattened = []
        for step in steps:
            if isinstance(step, RunnableSequence):
                flattened.extend(step.steps)
            else:
                flattened.append(as_runnable(step))
        self.steps = flattened

    def invoke(self, value):
        current = value
        for step in self.steps:
            _record("runnable", name=step.label, input_type=type(current).__name__)
            current = step.invoke(current)
        return current

    def stream(self, value):
        if not self.steps:
            return
        current = value
        for step in self.steps[:-1]:
            current = step.invoke(current)
        yield from self.steps[-1].stream(current)

    def __or__(self, other):
        return RunnableSequence([*self.steps, as_runnable(other)])

    def get_graph(self):
        return GraphView([step.label for step in self.steps])


class RunnableLambda(Runnable):
    label = "RunnableLambda"

    def __init__(self, function):
        self.function = function
        self.label = getattr(function, "__name__", self.label)

    def invoke(self, value):
        return self.function(value)


class RunnableParallel(Runnable):
    label = "RunnableParallel"

    def __init__(self, branches=None, **kwargs):
        source = dict(branches or {})
        source.update(kwargs)
        self.branches = {name: as_runnable(branch) for name, branch in source.items()}

    def invoke(self, value):
        return {name: branch.invoke(value) for name, branch in self.branches.items()}

    def get_graph(self):
        return GraphView(["fan out", *self.branches, "fan in"])


def _input_mapping(template, value):
    if isinstance(value, dict):
        return value
    variables = list(dict.fromkeys(re.findall(r"(?<!{){([A-Za-z_]\w*)[^}]*}", template)))
    if len(variables) == 1:
        return {variables[0]: value}
    if not variables:
        return {}
    raise TypeError(f"prompt expects {variables}; invoke it with a mapping")


def _safe_format(template, values):
    class Safe(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    normalized = {key: value if isinstance(value, str) else json.dumps(value, default=_json_default) for key, value in values.items()}
    return str(template).format_map(Safe(normalized))


class FewShotChatMessagePromptTemplate:
    def __init__(self, examples, example_prompt, **kwargs):
        self.examples = examples
        self.example_prompt = example_prompt

    def format_messages(self, values):
        messages = []
        for example in self.examples:
            messages.extend(self.example_prompt.invoke(example).to_messages())
        return messages


class ChatPromptTemplate(Runnable):
    label = "ChatPromptTemplate"

    def __init__(self, messages):
        if isinstance(messages, str):
            messages = [("human", messages)]
        self.messages = list(messages)
        self.partials = {}

    @classmethod
    def from_template(cls, template):
        return cls([("human", template)])

    @classmethod
    def from_messages(cls, messages):
        return cls(messages)

    def partial(self, **values):
        clone = ChatPromptTemplate(self.messages)
        clone.partials = {**self.partials, **values}
        return clone

    def invoke(self, value):
        all_templates = " ".join(str(item[1]) for item in self.messages if isinstance(item, (tuple, list)) and len(item) > 1)
        values = {**self.partials, **_input_mapping(all_templates, value)}
        result = []
        for item in self.messages:
            if isinstance(item, FewShotChatMessagePromptTemplate):
                result.extend(item.format_messages(values))
                continue
            if isinstance(item, BaseMessage):
                result.append(item)
                continue
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise TypeError(f"unsupported prompt message: {item!r}")
            role, template = item
            if role == "placeholder":
                key = str(template).strip("{}")
                for message in values.get(key, []):
                    if isinstance(message, BaseMessage):
                        result.append(message)
                    elif isinstance(message, (tuple, list)) and len(message) == 2:
                        message_role, content = message
                        result.append(MESSAGE_TYPES.get(message_role, HumanMessage)(content))
                    elif isinstance(message, str):
                        result.append(HumanMessage(message))
                    else:
                        raise TypeError(f"unsupported placeholder message: {message!r}")
                continue
            result.append(MESSAGE_TYPES.get(role, HumanMessage)(_safe_format(template, values)))
        return ChatPromptValue(result)


class StrOutputParser(Runnable):
    label = "StrOutputParser"

    def invoke(self, value):
        return str(_content(value))


def _extract_json(text):
    if isinstance(text, (dict, list)):
        return text
    raw = str(_content(text)).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"(?:\{.*\}|\[.*\])", raw, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


class JsonOutputParser(Runnable):
    label = "JsonOutputParser"

    def __init__(self, pydantic_object=None, **kwargs):
        self.pydantic_object = pydantic_object

    def invoke(self, value):
        parsed = _extract_json(value)
        if self.pydantic_object:
            validated = self.pydantic_object.model_validate(parsed)
            return validated.model_dump()
        return parsed

    def get_format_instructions(self):
        if not self.pydantic_object:
            return "Return one valid JSON object and no surrounding prose."
        schema = self.pydantic_object.model_json_schema()
        return "Return one valid JSON object matching this JSON Schema and no surrounding prose:\n" + json.dumps(schema, indent=2)


SimpleJsonOutputParser = JsonOutputParser


def _tool_schema(function, args_schema=None):
    if args_schema is not None:
        parameters = args_schema.model_json_schema()
    else:
        import inspect
        properties = {}
        required = []
        for name, parameter in inspect.signature(function).parameters.items():
            annotation = parameter.annotation
            kind = "number" if annotation in {int, float} else "string"
            properties[name] = {"type": kind}
            if parameter.default is inspect.Parameter.empty:
                required.append(name)
        parameters = {"type": "object", "properties": properties, "required": required}
    return {
        "type": "function",
        "function": {
            "name": function.__name__,
            "description": (function.__doc__ or "").strip(),
            "parameters": parameters,
        },
    }


class StructuredTool(Runnable):
    def __init__(self, function, args_schema=None):
        wraps(function)(self)
        self.function = function
        self.args_schema = args_schema
        self.name = function.__name__
        self.description = (function.__doc__ or "").strip()
        self.label = f"tool:{self.name}"

    def invoke(self, value):
        if self.args_schema is not None:
            value = self.args_schema.model_validate(value).model_dump()
        if isinstance(value, dict):
            return self.function(**value)
        return self.function(value)

    def schema(self):
        return _tool_schema(self.function, self.args_schema)


def tool(function=None, *, args_schema=None):
    def decorate(fn):
        return StructuredTool(fn, args_schema=args_schema)
    return decorate(function) if function is not None else decorate


def _normalize_messages(value):
    if isinstance(value, ChatPromptValue):
        return [_message_dict(message) for message in value.messages]
    if isinstance(value, list):
        return [_message_dict(message) for message in value]
    if isinstance(value, dict) and "messages" in value:
        return [_message_dict(message) for message in value["messages"]]
    return [{"role": "user", "content": str(value)}]


class ChatNVIDIA(Runnable):
    label = "ChatNVIDIA"

    def __init__(self, base_url=None, model=None, temperature=0.2, max_tokens=1024, api_key=None, **kwargs):
        self.base_url = base_url or os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
        self.model = model or "nvidia/nemotron-3-nano-30b-a3b"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.tools = []
        self.response_schema = None

    def _request(self, value, stream=False):
        key = self.api_key or os.getenv("NVIDIA_API_KEY", "")
        if not key:
            raise RuntimeError("Add your NVIDIA API key in Course settings before running a model cell.")
        request = {
            "base_url": self.base_url,
            "model": self.model,
            "messages": _normalize_messages(value),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": bool(stream),
        }
        if self.tools:
            request["tools"] = [item.schema() for item in self.tools]
        if self.response_schema:
            request["response_format"] = {"type": "json_object"}
        _record("model_request", model=self.model, turns=len(request["messages"]), stream=bool(stream), tools=len(self.tools))
        raw = run_sync(courseNvidiaChat(json.dumps(request), key))
        return json.loads(str(raw))

    def invoke(self, value):
        response = self._request(value, stream=False)
        message = response["message"]
        tool_calls = []
        for item in message.get("tool_calls") or []:
            function = item.get("function", {})
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments or "{}")
            tool_calls.append({"id": item.get("id"), "name": function.get("name"), "args": arguments, "type": "tool_call"})
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
        extra = {"reasoning": reasoning, "reasoning_content": reasoning} if reasoning else {}
        return AIMessage(message.get("content") or "", tool_calls=tool_calls, additional_kwargs=extra)

    def stream(self, value):
        response = self._request(value, stream=True)
        chunks = response.get("chunks") or [{"content": response.get("message", {}).get("content", "")}]
        for chunk in chunks:
            if isinstance(chunk, str):
                chunk = {"content": chunk}
            text = chunk.get("content") or ""
            reasoning = chunk.get("reasoning_content") or chunk.get("reasoning") or ""
            if text or reasoning:
                extra = {"reasoning": reasoning, "reasoning_content": reasoning} if reasoning else {}
                yield AIMessageChunk(text, additional_kwargs=extra)

    def bind_tools(self, tools):
        clone = self._clone()
        clone.tools = list(tools)
        return clone

    def with_structured_output(self, schema):
        clone = self._clone()
        clone.response_schema = schema
        return clone | JsonOutputParser(pydantic_object=schema)

    def _clone(self):
        clone = ChatNVIDIA(self.base_url, self.model, self.temperature, self.max_tokens, self.api_key)
        clone.tools = list(self.tools)
        clone.response_schema = self.response_schema
        return clone


class Agent(Runnable):
    label = "create_agent"

    def __init__(self, model, tools, system_prompt=None):
        self.model = model.bind_tools(tools)
        self.tools = {item.name: item for item in tools}
        self.system_prompt = system_prompt

    def invoke(self, state):
        messages = list(state.get("messages", []))
        normalized = [_message_dict(message) for message in messages]
        if self.system_prompt:
            normalized.insert(0, {"role": "system", "content": self.system_prompt})
        emitted = [HumanMessage(item["content"]) if item.get("role") == "user" else item for item in normalized if item.get("role") != "system"]
        for _ in range(4):
            response = self.model.invoke(normalized)
            emitted.append(response)
            normalized.append(_message_dict(response))
            if not response.tool_calls:
                return {"messages": emitted}
            for call in response.tool_calls:
                selected = self.tools.get(call["name"])
                if selected is None:
                    raise RuntimeError(f"model requested unavailable tool {call['name']!r}")
                observation = selected.invoke(call["args"])
                tool_message = ToolMessage(str(observation), tool_call_id=call.get("id"), name=call["name"])
                emitted.append(tool_message)
                normalized.append(_message_dict(tool_message))
        raise RuntimeError("agent stopped after four model turns without a final answer")


def create_agent(model, tools, system_prompt=None, **kwargs):
    return Agent(model, tools, system_prompt=system_prompt)


class _OpenAICompletions:
    def __init__(self, client):
        self.client = client

    def create(self, model, messages, stream=False, **kwargs):
        llm = ChatNVIDIA(
            base_url=self.client.base_url,
            api_key=self.client.api_key,
            model=model,
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 1024),
        )
        if stream:
            return [types.SimpleNamespace(choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=chunk.content))]) for chunk in llm.stream(messages)]
        message = llm.invoke(messages)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class OpenAI:
    def __init__(self, base_url=None, api_key=None, **kwargs):
        self.base_url = base_url or "https://integrate.api.nvidia.com/v1"
        self.api_key = api_key
        self.chat = types.SimpleNamespace(completions=_OpenAICompletions(self))


def sprint(stream):
    content = ""
    for chunk in stream:
        text = getattr(chunk, "content", str(chunk)) or ""
        print(text, end="", flush=True)
        content += text
    print()
    return content


class _MarkdownDisplay:
    def __init__(self, data):
        self.data = data

    def _course_display_(self):
        return {"type": "text/markdown", "data": str(self.data)}


class _JSONDisplay:
    def __init__(self, data):
        self.data = data

    def _course_display_(self):
        return {"type": "application/json", "data": json.dumps(self.data, indent=2, default=_json_default)}


class _ImageDisplay:
    def __init__(self, data=None, filename=None, **kwargs):
        self.data = data
        self.filename = filename

    def _course_display_(self):
        raw = self.data
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
            if text.lstrip().startswith("<svg"):
                return {"type": "image/svg+xml", "data": text}
        if self.filename:
            return {"type": "text/markdown", "data": f"![Course image]({self.filename})"}
        return {"type": "text/plain", "data": "The image payload could not be rendered in this browser."}


class _ChatDisplay:
    def __init__(self, chat_id):
        self.chat_id = chat_id

    def _course_display_(self):
        return {"type": "application/x-course-chat+json", "data": json.dumps({"chat_id": self.chat_id})}


def _assessment_terms(result):
    if isinstance(result, (dict, list)):
        text = json.dumps(result)
    else:
        text = str(_content(result))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def run_assessment(chain):
    try:
        with open("data/emails.json", "r", encoding="utf-8") as handle:
            primary = json.load(handle)
    except FileNotFoundError as error:
        raise RuntimeError("Assessment data was not mounted for this lesson.") from error
    counterfactual = [
        "From the Dallas store: the shirt tore on first wear. This clothing purchase was disappointing.",
        "From the Dallas store: these jeans arrived damaged. I need a refund for the clothing order.",
        "From the Austin store: the desk is sturdy and I am happy with the furniture purchase.",
        "From the Seattle store: the lamp works perfectly and deserves praise.",
    ]
    primary_result = chain.invoke(primary)
    counter_result = chain.invoke(counterfactual)
    primary_terms = _assessment_terms(primary_result)
    counter_terms = _assessment_terms(counter_result)
    checks = {
        "primary product category": "furniture" in primary_terms,
        "primary store location": "new york" in primary_terms,
        "counterfactual product category": "clothing" in counter_terms,
        "counterfactual store location": "dallas" in counter_terms,
        "input sensitivity": primary_terms != counter_terms,
    }
    passed = all(checks.values())
    report = {
        "passed": passed,
        "checks": checks,
        "primary_output": str(_content(primary_result)),
        "counterfactual_output": str(_content(counter_result)),
    }
    _record("assessment", passed=passed, checks=checks)
    display(_JSONDisplay(report))
    if not passed:
        failed = ", ".join(name for name, ok in checks.items() if not ok)
        raise ValueError(f"Assessment did not pass: {failed}")
    print("Assessment passed. Your chain used the supplied emails and handled the counterfactual set.")
    return report


def _install_module(name, **members):
    module = types.ModuleType(name)
    module.__dict__.update(members)
    sys.modules[name] = module
    if "." in name:
        parent_name, child = name.rsplit(".", 1)
        parent = sys.modules.setdefault(parent_name, types.ModuleType(parent_name))
        setattr(parent, child, module)
    return module


_install_module("langchain_nvidia_ai_endpoints", ChatNVIDIA=ChatNVIDIA)
_install_module("langchain_core.messages", HumanMessage=HumanMessage, AIMessage=AIMessage, SystemMessage=SystemMessage, ToolMessage=ToolMessage)
_install_module("langchain_core.prompts", ChatPromptTemplate=ChatPromptTemplate, FewShotChatMessagePromptTemplate=FewShotChatMessagePromptTemplate)
_install_module("langchain_core.output_parsers", StrOutputParser=StrOutputParser, JsonOutputParser=JsonOutputParser, SimpleJsonOutputParser=SimpleJsonOutputParser)
_install_module("langchain_core.runnables", RunnableLambda=RunnableLambda, RunnableParallel=RunnableParallel)
_install_module("langchain_core.tools", tool=tool)
_install_module("langchain.agents", create_agent=create_agent)
_install_module("openai", OpenAI=OpenAI)
_install_module("assessment_helper", run_assessment=run_assessment)
_install_module("IPython.display", display=display, Markdown=_MarkdownDisplay, JSON=_JSONDisplay, Image=_ImageDisplay)

# The course's Gradio helper is represented by an inspectable browser display.
def create_chatbot_interface_from_bot(bot):
    chatbots = globals().setdefault("__course_chatbots", {})
    chat_id = f"chat-{len(chatbots) + 1}"
    chatbots[chat_id] = bot

    class BrowserChat:
        def launch(self, **kwargs):
            display(_ChatDisplay(chat_id))
            return self
    return BrowserChat()


_install_module("chat_helpers.gradio_interface", create_chatbot_interface_from_bot=create_chatbot_interface_from_bot)


# The one contractions use in this course only needs common English expansions.
def _fix_contractions(text):
    replacements = {"can't": "cannot", "won't": "will not", "n't": " not", "'re": " are", "'ve": " have", "'ll": " will", "'m": " am"}
    result = str(text)
    for source, target in replacements.items():
        result = result.replace(source, target)
    return result


_install_module("contractions", fix=_fix_contractions)


class _WikipediaPage:
    def __init__(self, payload):
        self._payload = payload
        self.summary = str(payload.get("extract") or "")

    def exists(self):
        return bool(self.summary) and self._payload.get("type") != "https://mediawiki.org/wiki/HyperSwitch/errors/not_found"


class _Wikipedia:
    def __init__(self, user_agent=None, language="en", **kwargs):
        self.user_agent = user_agent
        self.language = language

    def page(self, topic):
        from urllib.parse import quote
        url = f"https://{self.language}.wikipedia.org/api/rest_v1/page/summary/{quote(str(topic), safe='')}"
        payload = json.loads(str(run_sync(coursePublicJson(url))))
        return _WikipediaPage(payload)


_install_module("wikipediaapi", Wikipedia=_Wikipedia)

# Make the source helper available without requiring a separate import cell.
globals().update({
    "sprint": sprint,
    "ChatNVIDIA": ChatNVIDIA,
    "ChatPromptTemplate": ChatPromptTemplate,
    "RunnableLambda": RunnableLambda,
    "RunnableParallel": RunnableParallel,
    "StrOutputParser": StrOutputParser,
    "JsonOutputParser": JsonOutputParser,
})
