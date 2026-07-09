(function () {
  "use strict";

  const EXECUTE_CELL = String.raw`
import ast
import asyncio
import contextlib
import html as html_lib
import io
import inspect
import json as jsonlib
import pprint
import re
import traceback

stdout = io.StringIO()
stderr = io.StringIO()
scope = __course_scope
scope["inputs"] = __cell_inputs.to_py()
if "__request_id" in globals():
    scope["__request_id"] = __request_id
reply = {
    "ok": True,
    "stdout": "",
    "stderr": "",
    "value": None,
    "display": "",
    "display_type": "text/plain",
    "display_language": "",
    "displays": [],
    "has_value": False,
    "execution_count": __execution_count,
    "error_line": None,
    "error_column": None,
}

course_displays = []
background_tasks = scope.setdefault("__course_background_tasks", {})
DISPLAY_WIDTH = 100

def _language_name(value):
    language = str(value or "text").strip().lower()
    return language if re.fullmatch(r"[a-z0-9_+-]{1,32}", language) else "text"

class _DisplayObject:
    def __init__(self, data, mime_type, language=""):
        self.data = data
        self.mime_type = mime_type
        self.language = _language_name(language) if language else ""

    def _course_display_(self):
        record = {"type": self.mime_type, "data": str(self.data)}
        if self.language:
            record["language"] = self.language
        return record

class HTML(_DisplayObject):
    def __init__(self, data):
        super().__init__(data, "text/html")

class Markdown(_DisplayObject):
    def __init__(self, data):
        super().__init__(data, "text/markdown")

class Code(_DisplayObject):
    def __init__(self, data, language="python"):
        super().__init__(data, "text/x-code", language)

class JSON(_DisplayObject):
    def __init__(self, data, expanded=True, indent=2):
        self.value = data
        self.expanded = bool(expanded)
        rendered = jsonlib.dumps(data, ensure_ascii=False, indent=max(0, int(indent)), default=str)
        super().__init__(rendered, "application/json", "json")

class Artifact(_DisplayObject):
    def __init__(self, filename, content, mime_type="text/plain", language=""):
        safe_name = str(filename or "artifact.txt").replace("\\", "/").split("/")[-1].strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,127}", safe_name):
            raise ValueError("Artifact filename must be a simple relative filename")
        payload = jsonlib.dumps({
            "filename": safe_name,
            "content": str(content),
            "mime_type": str(mime_type or "text/plain"),
            "language": _language_name(language) if language else "",
        }, ensure_ascii=False)
        super().__init__(payload, "application/x-course-artifact+json")

def _display_record(value):
    course_method = getattr(value, "_course_display_", None)
    if callable(course_method):
        return course_method()
    html_method = getattr(value, "_repr_html_", None)
    if callable(html_method):
        return {"type": "text/html", "data": str(html_method())}
    markdown_method = getattr(value, "_repr_markdown_", None)
    if callable(markdown_method):
        return {"type": "text/markdown", "data": str(markdown_method())}
    json_method = getattr(value, "_repr_json_", None)
    if callable(json_method):
        return JSON(json_method())._course_display_()
    if isinstance(value, (dict, list)):
        return JSON(value)._course_display_()
    if isinstance(value, (tuple, set, frozenset)):
        return {
            "type": "text/x-code",
            "language": "python",
            "data": pprint.pformat(value, width=DISPLAY_WIDTH, sort_dicts=False, compact=False),
        }
    return {"type": "text/plain", "data": repr(value)}

def display(*objects):
    for value in objects:
        course_displays.append(_display_record(value))

def display_text(source):
    course_displays.append({"type": "text/plain", "data": str(source)})

def display_markdown(source):
    """Render Markdown through the notebook's sanitized rich-output path."""
    course_displays.append({
        "type": "text/markdown",
        "data": str(source),
    })

def display_html(source):
    display(HTML(source))

def display_json(value, indent=2):
    display(JSON(value, indent=indent))

def display_code(source, language="python"):
    display(Code(source, language=language))

def display_table(rows, headers=None):
    values = list(rows)
    if values and all(isinstance(row, dict) for row in values):
        columns = list(headers or dict.fromkeys(key for row in values for key in row))
        matrix = [[row.get(column, "") for column in columns] for row in values]
    else:
        matrix = [list(row) if isinstance(row, (list, tuple)) else [row] for row in values]
        width = max((len(row) for row in matrix), default=0)
        columns = list(headers or [f"Column {index + 1}" for index in range(width)])
    heading = "".join(f"<th>{html_lib.escape(str(column))}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html_lib.escape(str(value))}</td>" for value in row) + "</tr>"
        for row in matrix
    )
    display(HTML(f"<table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table>"))

def display_artifact(filename, content, mime_type="text/plain", language=""):
    display(Artifact(filename, content, mime_type=mime_type, language=language))

def _background_record(name, task):
    if task.cancelled():
        state, result, error = "cancelled", None, ""
    elif task.done():
        exception = task.exception()
        state = "failed" if exception else "completed"
        result = None if exception else task.result()
        error = str(exception or "")
    else:
        state, result, error = "running", None, ""
    return {"name": name, "state": state, "result": result, "error": error}

def register_background(name, awaitable):
    job_name = str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", job_name):
        raise ValueError("Background job name must contain only letters, numbers, dots, dashes, or underscores")
    existing = background_tasks.get(job_name)
    if existing and not existing.done():
        if inspect.iscoroutine(awaitable):
            awaitable.close()
        raise RuntimeError(f"Background job '{job_name}' is already running")
    task = asyncio.create_task(awaitable, name=f"course:{job_name}")
    background_tasks[job_name] = task
    return _background_record(job_name, task)

def background_status(name=None):
    if name is not None:
        task = background_tasks.get(str(name))
        return _background_record(str(name), task) if task else None
    return [_background_record(job_name, task) for job_name, task in background_tasks.items()]

async def wait_background(name):
    job_name = str(name)
    task = background_tasks.get(job_name)
    if not task:
        raise KeyError(f"Background job '{job_name}' is not registered")
    await task
    return _background_record(job_name, task)

async def cancel_background(name):
    job_name = str(name)
    task = background_tasks.get(job_name)
    if not task:
        return None
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return _background_record(job_name, task)

def clear_output(wait=False):
    course_displays.clear()
    for stream in (stdout, stderr):
        stream.seek(0)
        stream.truncate(0)

helper_defaults = {
    "display": display,
    "display_text": display_text,
    "display_markdown": display_markdown,
    "display_html": display_html,
    "display_json": display_json,
    "display_code": display_code,
    "display_table": display_table,
    "display_artifact": display_artifact,
    "clear_output": clear_output,
    "register_background": register_background,
    "background_status": background_status,
    "wait_background": wait_background,
    "cancel_background": cancel_background,
    "HTML": HTML,
    "Markdown": Markdown,
    "Code": Code,
    "JSON": JSON,
    "Artifact": Artifact,
}
helper_overrides = scope.setdefault("__course_helper_overrides", {})
scope.update(helper_defaults)
scope.update(helper_overrides)
scope.update({
    "_display_record": _display_record,
    "course_displays": course_displays,
    "html_lib": html_lib,
    "asyncio": asyncio,
    "background_tasks": background_tasks,
    "_background_record": _background_record,
    "stdout": stdout,
    "stderr": stderr,
})

async def run_course_cell():
    tree = ast.parse(__cell_source, filename="<course-cell>", mode="exec")
    final_expression = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    flags = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        statements = eval(compile(tree, "<course-cell>", "exec", flags=flags), scope, scope)
        if inspect.isawaitable(statements):
            await statements
        if final_expression:
            expression = ast.Expression(final_expression.value)
            ast.fix_missing_locations(expression)
            value = eval(compile(expression, "<course-cell>", "eval", flags=flags), scope, scope)
            if inspect.isawaitable(value):
                value = await value
            record = _display_record(value)
            reply["value"] = value
            reply["display_type"] = record["type"]
            reply["display"] = record["data"]
            reply["display_language"] = record.get("language", "")
            reply["has_value"] = value is not None

try:
    await run_course_cell()
except Exception as error:
    reply["ok"] = False
    reply["stderr"] = traceback.format_exc()
    if isinstance(error, SyntaxError):
        reply["error_line"] = error.lineno
        reply["error_column"] = error.offset
    else:
        course_frames = [frame for frame in traceback.extract_tb(error.__traceback__) if frame.filename == "<course-cell>"]
        if course_frames:
            reply["error_line"] = course_frames[-1].lineno
            reply["error_column"] = 1

reply["stdout"] = stdout.getvalue()
reply["stderr"] += stderr.getvalue()
reply["displays"] = course_displays
try:
    scope.get("inputs", {}).pop("api_key", None)
except Exception:
    pass
jsonlib.dumps(reply, default=str)
`;

  function definitionSource(name) {
    const lines = EXECUTE_CELL.split("\n");
    const start = lines.findIndex(line => new RegExp(`^(?:async\\s+def|def|class)\\s+${name}\\b`).test(line));
    if (start < 0) throw new Error(`Missing Python helper definition: ${name}`);
    let end = start + 1;
    while (end < lines.length && !/^(?:async\s+def|def|class)\s+\w+\b/.test(lines[end])) end += 1;
    return lines.slice(start, end).join("\n").trimEnd();
  }

  const HELPER_DOCS = [
    ["display", "display(*objects)", "Render one or more values using their richest safe representation."],
    ["display_text", "display_text(value)", "Render plain text without syntax or Markdown interpretation."],
    ["display_json", "display_json(value, indent=2)", "Render JSON with indentation and syntax highlighting."],
    ["display_code", "display_code(source, language='python')", "Render source code with language-aware syntax highlighting."],
    ["display_table", "display_table(rows, headers=None)", "Render dictionaries or row sequences as a safe HTML table."],
    ["display_artifact", "display_artifact(filename, content, mime_type='text/plain', language='')", "Preview a generated file and offer it for download without executing it."],
    ["display_markdown", "display_markdown(source)", "Send Markdown directly to the notebook's sanitized rich-output renderer."],
    ["display_html", "display_html(source)", "Render sanitized HTML."],
    ["clear_output", "clear_output(wait=False)", "Clear output accumulated during the current execution."],
    ["register_background", "register_background(name, awaitable)", "Register a named asyncio task that survives later cell executions."],
    ["background_status", "background_status(name=None)", "Inspect one registered task or list every task and its state."],
    ["wait_background", "await wait_background(name)", "Wait for a registered task and return its result record."],
    ["cancel_background", "await cancel_background(name)", "Cancel a registered task; Stop and Reset terminate the whole worker."],
  ].map(([name, signature, description]) => Object.freeze({
    name, signature, description, source: definitionSource(name),
  }));

  globalThis.PYODIDE_EXECUTION_CONTRACT = Object.freeze({
    source: EXECUTE_CELL,
    helpers: Object.freeze(HELPER_DOCS),
  });
})();
