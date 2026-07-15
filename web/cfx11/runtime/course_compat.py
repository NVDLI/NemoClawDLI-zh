# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Browser-owned adapters for the real packages used by c-fx-11-v1.

The course imports upstream LangChain, LangGraph, NVIDIA, OpenAI, Wikipedia,
contractions, IPython, requests, and Pydantic packages. This file does not
reimplement those packages. It supplies the browser transport, rich-output
host, chat host, and assessment middleware that a static Pyodide page needs.
"""

from __future__ import annotations

import base64
from concurrent.futures import Executor, Future
import json
import os
import re
import sys
import types
from functools import wraps
from typing import Any
from urllib.parse import urlsplit

import httpx
import requests
from IPython import display as ipython_display
from js import courseHttpRequest
from openai import OpenAI
from pyodide.ffi import run_sync
from requests import Request, Response
from wikipediaapi._http_client.base_http_client import BaseHTTPClient
from wikipediaapi._http_client.sync_http_client import SyncHTTPClient


def _record(event: str, **detail: Any) -> None:
    trace = globals().setdefault("COURSE_EXECUTION_TRACE", [])
    trace.append({"event": event, **detail})


def _browser_fetch(method: str, url: str, headers: dict[str, str], body: bytes | str | None) -> dict[str, Any]:
    payload = {
        "method": method.upper(),
        "url": url,
        "headers": {str(name): str(value) for name, value in headers.items()},
        "body": body.decode("utf-8") if isinstance(body, bytes) else body,
    }
    raw = run_sync(courseHttpRequest(json.dumps(payload)))
    result = json.loads(str(raw))
    _record(
        "browser_request",
        method=payload["method"],
        host=urlsplit(result.get("url") or url).hostname,
        status=int(result["status"]),
    )
    return result


def _browser_requests_request(
    self,
    method,
    url,
    params=None,
    data=None,
    headers=None,
    cookies=None,
    files=None,
    auth=None,
    timeout=None,
    allow_redirects=True,
    proxies=None,
    hooks=None,
    stream=None,
    verify=None,
    cert=None,
    json=None,
):
    if files or auth or cookies:
        raise RuntimeError("The browser course transport does not accept files, HTTP auth objects, or cookies.")
    prepared = Request(
        method=method,
        url=url,
        params=params,
        data=data,
        json=json,
        headers=headers,
    ).prepare()
    result = _browser_fetch(prepared.method, prepared.url, dict(prepared.headers), prepared.body)
    response = Response()
    response.status_code = int(result["status"])
    response.reason = str(result.get("reason") or "")
    response.url = str(result.get("url") or prepared.url)
    response.headers.update(result.get("headers") or {})
    response.encoding = "utf-8"
    response._content = base64.b64decode(str(result.get("body_base64") or ""), validate=True)
    response._content_consumed = True
    response.request = prepared
    return response


requests.sessions.Session.request = _browser_requests_request


class BrowserHTTPXTransport(httpx.BaseTransport):
    """Use the course's origin-restricted fetch bridge behind real httpx clients."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        result = _browser_fetch(
            request.method,
            str(request.url),
            dict(request.headers),
            request.read(),
        )
        return httpx.Response(
            status_code=int(result["status"]),
            headers=result.get("headers") or {},
            content=base64.b64decode(str(result.get("body_base64") or ""), validate=True),
            request=request,
        )


_original_openai_init = OpenAI.__init__


@wraps(_original_openai_init)
def _browser_openai_init(self, *args, **kwargs):
    kwargs.setdefault("http_client", httpx.Client(transport=BrowserHTTPXTransport()))
    return _original_openai_init(self, *args, **kwargs)


OpenAI.__init__ = _browser_openai_init


def _browser_wikipedia_init(self, *args, **kwargs):
    BaseHTTPClient.__init__(self, *args, **kwargs)
    self._client = httpx.Client(
        headers=self._default_headers,
        **self._client_kwargs,
        transport=BrowserHTTPXTransport(),
    )


SyncHTTPClient.__init__ = _browser_wikipedia_init


def _python_threads_available() -> bool:
    """Use Pyodide's runtime capability flag instead of assuming a platform."""

    if sys.platform == "emscripten":
        return bool(getattr(getattr(sys, "_emscripten_info", None), "pthreads", False))
    return True


COURSE_BATCH_MODE = "gil-locked-threads" if _python_threads_available() else "ordered-browser-fallback"


class BrowserSynchronousExecutor(Executor):
    """Honor LangChain's executor contract when CPython cannot start threads."""

    def __init__(self, *args, **kwargs):
        super().__init__()

    def submit(self, function, /, *args, **kwargs):
        future = Future()
        try:
            future.set_result(function(*args, **kwargs))
        except BaseException as error:
            future.set_exception(error)
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


# LangChain and LangGraph both reach this constructor through
# get_executor_for_config(). Keep their real batch/tool APIs and normal
# GIL-locked executor whenever the interpreter supports pthreads. Official
# Pyodide builds currently do not, so only that capability state receives the
# ordered executor rather than failing every batch with "can't start new
# thread". A future pthread-capable runtime automatically takes the native path.
import langchain_core.runnables.config as _langchain_config

if not _python_threads_available():
    _langchain_config.ContextThreadPoolExecutor = BrowserSynchronousExecutor

_record("batch_scheduler", mode=COURSE_BATCH_MODE)


def _markdown_record(self):
    return {"type": "text/markdown", "data": str(self.data)}


def _json_record(self):
    value = self.data
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return {"type": "application/json", "data": json.dumps(value, indent=2, default=str)}


def _image_record(self):
    svg_renderer = getattr(self, "_repr_svg_", None)
    svg = svg_renderer() if callable(svg_renderer) else None
    if svg:
        return {"type": "image/svg+xml", "data": str(svg)}
    for mime_type, method_name in (("image/png", "_repr_png_"), ("image/jpeg", "_repr_jpeg_")):
        renderer = getattr(self, method_name, None)
        if not callable(renderer):
            continue
        raw = renderer()
        if raw:
            encoded = raw if isinstance(raw, str) else base64.b64encode(raw).decode("ascii")
            return {"type": mime_type, "data": encoded}
    filename = getattr(self, "filename", None)
    if filename:
        return {"type": "text/markdown", "data": f"![Course image]({filename})"}
    return {"type": "text/plain", "data": "The image payload could not be rendered in this browser."}


ipython_display.display = display
ipython_display.Markdown._course_display_ = _markdown_record
ipython_display.JSON._course_display_ = _json_record
ipython_display.Image._course_display_ = _image_record


class _ChatDisplay:
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def _course_display_(self):
        return {"type": "application/x-course-chat+json", "data": json.dumps({"chat_id": self.chat_id})}


class BrowserChatHost:
    """Render the source course's chatbot object in the static course page."""

    def __init__(self, chatbot):
        self.chatbot = chatbot

    def launch(self, **kwargs):
        chatbots = globals().setdefault("__course_chatbots", {})
        chat_id = f"chat-{len(chatbots) + 1}"
        chatbots[chat_id] = self.chatbot
        display(_ChatDisplay(chat_id))
        _record("chat_host", chat_id=chat_id)
        return self


def create_chatbot_interface_from_bot(chatbot):
    return BrowserChatHost(chatbot)


def _assessment_terms(result):
    if isinstance(result, (dict, list)):
        text = json.dumps(result)
    else:
        text = str(getattr(result, "content", result))
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
        "primary_output": str(getattr(primary_result, "content", primary_result)),
        "counterfactual_output": str(getattr(counter_result, "content", counter_result)),
    }
    _record("assessment", passed=passed, checks=checks)
    display_json(report)
    if not passed:
        failed = ", ".join(name for name, ok in checks.items() if not ok)
        raise ValueError(f"Assessment did not pass: {failed}")
    print("Assessment passed. Your chain used the supplied emails and handled the counterfactual set.")
    return report


def _owned_module(name: str, **members: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(members)
    sys.modules[name] = module
    if "." in name:
        parent_name, child = name.rsplit(".", 1)
        parent = sys.modules.setdefault(parent_name, types.ModuleType(parent_name))
        setattr(parent, child, module)
    return module


_owned_module("assessment_helper", run_assessment=run_assessment)
_owned_module(
    "chat_helpers.gradio_interface",
    create_chatbot_interface_from_bot=create_chatbot_interface_from_bot,
)


def _assert_upstream_packages() -> None:
    expected = {
        "langchain": "1.3.13",
        "langchain-core": "1.4.9",
        "langgraph": "1.2.9",
        "langchain-nvidia-ai-endpoints": "1.4.3",
        "openai": "2.45.0",
        "Wikipedia-API": "0.15.0",
        "contractions": "0.1.73",
    }
    import importlib.metadata as metadata

    actual = {name: metadata.version(name) for name in expected}
    if actual != expected:
        raise RuntimeError(f"Browser package lock mismatch: expected {expected}, received {actual}")
    package_modules = {
        "langchain": __import__("langchain"),
        "langchain_core": __import__("langchain_core"),
        "langgraph": __import__("langgraph"),
        "openai": __import__("openai"),
        "wikipediaapi": __import__("wikipediaapi"),
        "contractions": __import__("contractions"),
    }
    for name, module in package_modules.items():
        sources = [str(getattr(module, "__file__", "") or "")]
        spec = getattr(module, "__spec__", None)
        sources.extend(str(path) for path in (getattr(spec, "submodule_search_locations", None) or []))
        sources = [source for source in sources if source]
        if not sources or not all("site-packages" in source for source in sources):
            raise RuntimeError(f"{name} did not resolve to an installed upstream package: {sources!r}")


_assert_upstream_packages()
