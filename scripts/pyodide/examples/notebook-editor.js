(function () {
  "use strict";

  const PYTHON_KEYWORDS = new Set(
    "and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield match case".split(" "),
  );
  const PYTHON_BUILTINS = new Set(
    "abs all any bool dict enumerate filter float int len list map max min next object open print range repr reversed round set sorted str sum tuple type zip".split(" "),
  );

  function definePythonMode() {
    if (typeof globalThis.CodeMirror?.defineMode !== "function" || globalThis.CodeMirror.modes["course-python"]) return;
    globalThis.CodeMirror.defineMode("course-python", () => ({
      startState: () => ({ string: "", definition: false }),
      token(stream, state) {
        if (state.string) {
          let escaped = false;
          while (!stream.eol()) {
            const character = stream.next();
            if (character === state.string && !escaped) {
              state.string = "";
              break;
            }
            escaped = character === "\\" && !escaped;
            if (character !== "\\") escaped = false;
          }
          return "string";
        }
        if (stream.eatSpace()) return null;
        if (stream.match(/^#.*/)) return "comment";
        if (stream.match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?/i)) return "number";
        if (stream.match(/^[rubf]*(?:"|')/i)) {
          state.string = stream.current().slice(-1);
          return "string";
        }
        if (stream.match(/^[A-Za-z_]\w*/)) {
          const word = stream.current();
          if (state.definition) {
            state.definition = false;
            return "def";
          }
          if (word === "def" || word === "class") {
            state.definition = true;
            return "keyword";
          }
          if (PYTHON_KEYWORDS.has(word)) return "keyword";
          if (PYTHON_BUILTINS.has(word)) return "builtin";
          return "variable";
        }
        if (stream.match(/^(?:\*\*|\/\/|:=|==|!=|<=|>=|->|[-+*/%@&|^~<>]=?)/)) return "operator";
        stream.next();
        return null;
      },
      lineComment: "#",
    }));
  }

  function attach(textarea, { run, runNext }) {
    let errorLine = null;
    const fallback = {
      getValue: () => textarea.value,
      setValue: (value) => { textarea.value = value; },
      focus: () => textarea.focus(),
      refresh: () => {},
      clearError: () => {},
      showError: () => {},
      element: textarea,
    };
    textarea.addEventListener("keydown", (event) => {
      const execute = event.key === "Enter" && (event.shiftKey || event.ctrlKey || event.metaKey);
      if (!execute) return;
      event.preventDefault();
      (event.shiftKey ? runNext : run)();
    });
    if (typeof globalThis.CodeMirror?.fromTextArea !== "function") return fallback;
    definePythonMode();
    const editor = globalThis.CodeMirror.fromTextArea(textarea, {
      mode: "course-python",
      theme: "default",
      lineNumbers: true,
      indentUnit: 4,
      indentWithTabs: false,
      lineWrapping: false,
      viewportMargin: Infinity,
      extraKeys: {
        "Shift-Enter": () => runNext(),
        "Ctrl-Enter": () => run(),
        "Cmd-Enter": () => run(),
        Tab(instance) {
          if (instance.somethingSelected()) instance.indentSelection("add");
          else instance.replaceSelection("    ", "end", "+input");
        },
      },
    });
    editor.setSize(null, "auto");
    editor.getInputField().setAttribute("aria-label", textarea.getAttribute("aria-label") || "Editable Python");
    const clearError = () => {
      if (errorLine === null) return;
      editor.removeLineClass(errorLine, "background", "py-code-error-line");
      editor.removeLineClass(errorLine, "gutter", "py-code-error-gutter");
      editor.setGutterMarker(errorLine, "CodeMirror-linenumbers", null);
      errorLine = null;
    };
    const showError = (line, column = 1) => {
      clearError();
      if (!Number.isInteger(line) || line < 1 || line > editor.lineCount()) return;
      errorLine = line - 1;
      const marker = document.createElement("span");
      marker.className = "py-code-error-marker";
      marker.textContent = "●";
      marker.title = `Python error on line ${line}`;
      editor.setGutterMarker(errorLine, "CodeMirror-linenumbers", marker);
      editor.addLineClass(errorLine, "background", "py-code-error-line");
      editor.addLineClass(errorLine, "gutter", "py-code-error-gutter");
      const character = Math.max(0, Math.min((Number(column) || 1) - 1, editor.getLine(errorLine).length));
      editor.setCursor({ line: errorLine, ch: character });
      editor.scrollIntoView({ line: errorLine, ch: character }, 80);
      editor.focus();
    };
    editor.on("change", clearError);
    return {
      getValue: () => editor.getValue(),
      setValue: (value) => editor.setValue(value),
      focus: () => editor.focus(),
      refresh: () => editor.refresh(),
      clearError,
      showError,
      element: editor.getWrapperElement(),
    };
  }

  globalThis.PYODIDE_NOTEBOOK_EDITOR = Object.freeze({ attach, definePythonMode });
})();
