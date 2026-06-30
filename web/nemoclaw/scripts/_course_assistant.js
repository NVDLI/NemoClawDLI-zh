// Page-aware ReAct assistant. Shared chrome mounts it lazily in the page language.
import { mountAgentChat } from "./_chat.js";
import {
  courseCode, courseCodeArtifacts, coursePage, coursePages,
  courseRuntimeFiles, courseRuntimeSource,
} from "./_langchain.js";

const MODELS = [
  { id: "nvidia/nemotron-3-nano-30b-a3b", label: "Nemotron Nano 30B · fast" },
  { id: "nvidia/nemotron-3-super-120b-a12b", label: "Nemotron Super 120B · stronger" },
];
const ASSISTANT_WIDTH_KEY = "nemoclaw_course_assistant_width_v1";
const ASSISTANT_SESSIONS_KEY = "nemoclaw_course_assistant_sessions_v1";
const MAX_ASSISTANT_SESSIONS = 12;
const MAX_SESSION_HISTORY_CHARS = 100000;
const MAX_ARTIFACT_FIELD_CHARS = 40000;

function newSession(page = null) {
  const now = Date.now();
  return {
    id: crypto.randomUUID?.() || "session-" + now + "-" + Math.random().toString(36).slice(2, 8),
    title: "New session", manualTitle: false,
    pageId: page?.id || "", pageTitle: page?.title || "",
    createdAt: now, updatedAt: now, history: [], artifact: null,
  };
}

function cleanHistory(items) {
  const normalized = (Array.isArray(items) ? items : [])
    .filter(item => item && ["system", "user", "assistant"].includes(item.role) && typeof item.content === "string")
    .slice(-40)
    .map(item => ({ role: item.role, content: item.content.slice(0, 60000) }));
  const summary = normalized.filter(item => item.role === "system").at(-1);
  const kept = [], summaryChars = summary ? Math.min(20000, summary.content.length) : 0;
  let remaining = MAX_SESSION_HISTORY_CHARS - summaryChars;
  for (let index = normalized.length - 1; index >= 0 && remaining > 0; index -= 1) {
    const item = normalized[index];
    if (item === summary) continue;
    const content = item.content.slice(0, remaining);
    if (content) { kept.push({ role: item.role, content }); remaining -= content.length; }
  }
  kept.reverse();
  if (summary) kept.unshift({ role: "system", content: summary.content.slice(0, summaryChars) });
  return kept;
}

function cleanArtifact(value) {
  if (!value || typeof value !== "object") return null;
  return {
    title: String(value.title || "Browser artifact").slice(0, 96),
    html: String(value.html || "").slice(0, MAX_ARTIFACT_FIELD_CHARS),
    javascript: String(value.javascript || "").slice(0, MAX_ARTIFACT_FIELD_CHARS),
    updatedAt: Number(value.updatedAt || Date.now()),
  };
}

export function loadCourseAssistantStore(storage = localStorage) {
  let parsed = null;
  try { parsed = JSON.parse(storage.getItem(ASSISTANT_SESSIONS_KEY) || "null"); } catch (_) {}
  const sessions = (parsed && Array.isArray(parsed.sessions) ? parsed.sessions : []).map(item => ({
    id: String(item.id || ""), title: String(item.title || "New session").slice(0, 72),
    manualTitle: item.manualTitle === true,
    pageId: String(item.pageId || "").slice(0, 80), pageTitle: String(item.pageTitle || "").slice(0, 160),
    createdAt: Number(item.createdAt || Date.now()), updatedAt: Number(item.updatedAt || Date.now()), history: cleanHistory(item.history), artifact: cleanArtifact(item.artifact),
  })).filter(item => item.id).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_ASSISTANT_SESSIONS);
  if (!sessions.length) sessions.push(newSession());
  const activeId = sessions.some(item => item.id === parsed?.activeId) ? parsed.activeId : sessions[0].id;
  return { version: 1, activeId, sessions };
}

export function saveCourseAssistantStore(store, storage = localStorage) {
  store.sessions = store.sessions.map(session => ({
    ...session, history: cleanHistory(session.history), artifact: cleanArtifact(session.artifact),
  })).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_ASSISTANT_SESSIONS);
  if (!store.sessions.some(item => item.id === store.activeId)) store.activeId = store.sessions[0]?.id || "";
  const serialized = JSON.stringify({ version: 3, activeId: store.activeId, sessions: store.sessions });
  storage.setItem(ASSISTANT_SESSIONS_KEY, serialized);
  return { chars: serialized.length, sessions: store.sessions.length };
}

function currentPage() {
  const id = (location.pathname.split("/").pop() || "index.html").replace(/\.html$/, "");
  return coursePages().find(page => page.id === id) || coursePages()[0];
}

function currentTitle(page) {
  return (document.querySelector("h1")?.textContent || page.title).replace(/\s+/g, " ").trim();
}

export async function searchCoursePages(query, readPage = coursePage, catalog = coursePages()) {
  const terms = (String(query || "").toLowerCase().match(/[\p{L}\p{N}-]{3,}/gu) || []).slice(0, 8);
  if (!terms.length) return [];
  const docs = await Promise.all(catalog.map(async item => ({ item, body: await readPage(item.id) })));
  return docs.map(({ item, body }) => {
    const lower = body.toLowerCase();
    const score = terms.reduce((sum, term) => sum + lower.split(term).length - 1, 0);
    const hits = terms.map(term => lower.indexOf(term)).filter(index => index >= 0);
    const start = Math.max(0, (hits.length ? Math.min(...hits) : 0) - 180);
    return { id: item.id, title: item.title, score, excerpt: body.slice(start, start + 900) };
  }).filter(result => result.score > 0).sort((a, b) => b.score - a.score).slice(0, 4);
}

export function artifactFromMarkdown(markdown, title = "Generated browser artifact") {
  let html = "", javascript = "", css = "";
  const fences = String(markdown || "").matchAll(/```([^\n`]*)\n([\s\S]*?)```/g);
  for (const match of fences) {
    const language = match[1].trim().toLowerCase();
    if (["html", "htm"].includes(language)) html += (html ? "\n" : "") + match[2].trim();
    else if (["javascript", "js"].includes(language)) javascript += (javascript ? "\n" : "") + match[2].trim();
    else if (language === "css") css += (css ? "\n" : "") + match[2].trim();
  }
  if (css) html = `<style>\n${css}\n</style>\n` + html;
  return html || javascript ? cleanArtifact({ title, html, javascript, updatedAt: Date.now() }) : null;
}

export function parseInlineCourseSourceIntent(text) {
  const raw = String(text || "").trim();
  if (!/^\{[\s\S]*\}$/.test(raw) || raw.length > 500) return null;
  try {
    const value = JSON.parse(raw);
    return value && typeof value === "object" && typeof value.uri === "string" && value.uri.trim()
      ? { uri: value.uri.trim() } : null;
  } catch (_) { return null; }
}

export async function resolveCourseSourceUri(uri, pageId = "") {
  const value = String(uri || "").trim().replace(/^course:\/\//, "");
  if (!value || value.includes("..") || value.length > 160) return null;
  const runtimeFile = value.replace(/^scripts\//, "");
  if (courseRuntimeFiles().some(item => item.file === runtimeFile)) {
    return { label: `read_course_runtime_source · ${runtimeFile}`, content: await courseRuntimeSource(runtimeFile) };
  }
  let page = String(pageId || "").trim(), artifact = value;
  const pageIds = new Set(coursePages().map(item => item.id));
  const hash = value.indexOf("#");
  if (hash > 0) { page = value.slice(0, hash); artifact = value.slice(hash + 1); }
  else {
    const slash = value.indexOf("/");
    if (slash > 0 && pageIds.has(value.slice(0, slash))) { page = value.slice(0, slash); artifact = value.slice(slash + 1); }
  }
  if (!pageIds.has(page) || !artifact) return null;
  const available = await courseCodeArtifacts(page);
  if (!available.some(item => item.id === artifact)) return null;
  return { label: `read_course_source · ${page}#${artifact}`, content: await courseCode(page, artifact) };
}

export function mountCourseAssistant(runtime = {}) {
  if (!location.pathname.includes("/nemoclaw/")) return;
  if (document.querySelector(".course-assistant-launcher")) return;
  const pt = document.documentElement.lang.toLowerCase().startsWith("pt");
  const copy = pt ? {
    open: "Abrir Assistente do Curso", assistant: "ASSISTENTE DO CURSO", dialog: "Assistente do Curso",
    resize: "Redimensionar o Assistente do Curso", resizeTitle: "Arraste para redimensionar · clique duas vezes para restaurar",
    close: "Fechar Assistente do Curso", session: "Sessão", newSession: "+ Nova", deleteSession: "Excluir",
    deleteLabel: "Excluir a sessão atual do Assistente do Curso",
    renameLabel: "Renomear a sessão atual", renamePlaceholder: "Nome da sessão",
    attached: "Página vinculada", noPage: "Nenhuma página vinculada", usePage: id => `Usar ${id}`, refreshPage: "Atualizar página",
    tools: "mapa, prosa, código e fontes do runtime disponíveis",
    chatView: "Conversa", artifactView: "Artefato", artifactTitle: "Título do artefato", htmlLabel: "HTML", javascriptLabel: "JavaScript",
    runArtifact: "▶ Executar", clearArtifact: "Limpar prévia", deleteArtifact: "Excluir artefato", artifactPreview: "Prévia do artefato do curso", generatedReady: "Código gerado pronto",
    previewCleared: "Prévia limpa; código preservado", artifactDeleted: "Artefato excluído", syntaxError: "Erro de sintaxe", runtimeError: "Erro de execução",
    unsupportedImport: "Imports não funcionam no sandbox. Use course.embed(...) para embeddings.",
    saved: "Salvo localmente", saving: "Salvando resposta", full: "Não salvo: armazenamento local cheio", selected: "Sessão selecionada",
    created: "Nova sessão criada", deleted: "Sessão excluída", renamed: "Sessão renomeada", attachedNow: "Página vinculada à sessão", compacted: "Contexto condensado e salvo localmente",
    emptyTitle: "Nova sessão", clear: "↺ Limpar sessão",
    intro: "As sessões ficam neste navegador. Turnos antigos são condensados automaticamente.",
    greeting: id => id ? `A sessão usa ${id}. A prosa e o índice de código estão vinculados; o código exato fica disponível sob demanda.` : "Nenhuma página está vinculada. Pesquise ou leia qualquer parte do curso.",
    examples: ["Resuma esta página", "Mostre o código desta página", "Crie um artefato HTML/JavaScript executável", "Como _shared.js apoia esta página?"],
  } : {
    open: "Open Course Assistant", assistant: "COURSE ASSISTANT", dialog: "Course Assistant",
    resize: "Resize Course Assistant", resizeTitle: "Drag to resize · double-click to reset",
    close: "Close Course Assistant", session: "Session", newSession: "+ New", deleteSession: "Delete",
    deleteLabel: "Delete current Course Assistant session",
    renameLabel: "Rename current Course Assistant session", renamePlaceholder: "Session name",
    attached: "Attached page", noPage: "No page attached", usePage: id => `Use ${id}`, refreshPage: "Refresh page",
    tools: "course map, prose, code, and runtime-source tools available",
    chatView: "Chat", artifactView: "Artifact", artifactTitle: "Artifact title", htmlLabel: "HTML", javascriptLabel: "JavaScript",
    runArtifact: "▶ Run", clearArtifact: "Clear preview", deleteArtifact: "Delete artifact", artifactPreview: "Course artifact preview", generatedReady: "Generated code ready",
    previewCleared: "Preview cleared; code preserved", artifactDeleted: "Artifact deleted", syntaxError: "Syntax error", runtimeError: "Runtime error",
    unsupportedImport: "Imports are unavailable in the sandbox. Use course.embed(...) for embeddings.",
    saved: "Saved locally", saving: "Saving response", full: "Not saved: browser storage is full", selected: "Session selected",
    created: "New session created", deleted: "Session deleted", renamed: "Session renamed", attachedNow: "Page attached to session", compacted: "Compacted and saved locally",
    emptyTitle: "New session", clear: "↺ Clear session",
    intro: "Sessions stay in this browser. Older turns compact automatically.",
    greeting: id => id ? `This session uses ${id}. Its prose and code index are attached; exact source is available on demand.` : "No page is attached. Search or read any part of the course.",
    examples: ["Summarize this page", "Show me this page's code", "Build a runnable HTML/JavaScript artifact", "How does _shared.js support this page?"],
  };
  const page = currentPage();
  const title = currentTitle(page);
  const launcher = document.createElement("button");
  launcher.type = "button";
  launcher.className = "course-assistant-launcher";
  launcher.setAttribute("aria-label", copy.open);
  launcher.setAttribute("aria-controls", "course-assistant-panel");
  launcher.setAttribute("aria-expanded", "false");
  launcher.title = copy.open;
  launcher.textContent = "✦";

  const shell = document.createElement("section");
  shell.className = "course-assistant-shell";
  shell.innerHTML = `<div class="course-assistant-backdrop" data-course-assistant-close></div>
    <aside id="course-assistant-panel" class="course-assistant-panel" role="dialog" aria-modal="true" aria-label="${copy.dialog}" aria-hidden="true">
      <div class="course-assistant-resizer" role="separator" aria-label="${copy.resize}" aria-orientation="vertical" aria-valuemin="320" tabindex="0" title="${copy.resizeTitle}"></div>
      <header><div><span>${copy.assistant}</span><h2 data-course-assistant-title>${copy.emptyTitle}</h2></div><button type="button" data-course-assistant-close aria-label="${copy.close}">×</button></header>
      <div class="course-assistant-sessions"><label for="course-assistant-session">${copy.session}</label><select id="course-assistant-session" aria-label="${copy.session}"></select><button type="button" data-course-assistant-new>${copy.newSession}</button><button type="button" data-course-assistant-delete aria-label="${copy.deleteLabel}">${copy.deleteSession}</button><input type="text" maxlength="72" aria-label="${copy.renameLabel}" placeholder="${copy.renamePlaceholder}"><span role="status" aria-live="polite"></span></div>
      <p class="course-assistant-context"><span></span><button type="button" data-course-assistant-use-page></button></p>
      <div class="course-assistant-tabs" role="tablist"><button type="button" role="tab" aria-selected="true" data-course-assistant-view="chat">${copy.chatView}</button><button type="button" role="tab" aria-selected="false" data-course-assistant-view="artifact">${copy.artifactView}</button></div>
      <div class="course-assistant-body"></div>
      <section class="course-assistant-artifact" hidden>
        <label>${copy.artifactTitle}<input type="text" maxlength="96" data-course-artifact-title></label>
        <div class="course-artifact-editors"><label>${copy.htmlLabel}<textarea data-course-artifact-html spellcheck="false"></textarea></label><label>${copy.javascriptLabel}<textarea data-course-artifact-js spellcheck="false"></textarea></label></div>
        <div class="course-artifact-actions"><button type="button" data-course-artifact-run>${copy.runArtifact}</button><button type="button" data-course-artifact-clear>${copy.clearArtifact}</button><button type="button" data-course-artifact-delete>${copy.deleteArtifact}</button><span role="status" aria-live="polite"></span></div>
        <iframe sandbox="allow-scripts" referrerpolicy="no-referrer" title="${copy.artifactPreview}"></iframe>
      </section>
    </aside>`;
  document.body.append(launcher, shell);
  const panel = shell.querySelector(".course-assistant-panel");
  const body = shell.querySelector(".course-assistant-body");
  const artifactPanel = shell.querySelector(".course-assistant-artifact");
  const artifactTitle = shell.querySelector("[data-course-artifact-title]");
  const artifactHtml = shell.querySelector("[data-course-artifact-html]");
  const artifactJs = shell.querySelector("[data-course-artifact-js]");
  const artifactFrame = artifactPanel.querySelector("iframe");
  const artifactStatus = artifactPanel.querySelector('[role="status"]');
  const viewButtons = [...shell.querySelectorAll("[data-course-assistant-view]")];
  const artifactViewButton = shell.querySelector('[data-course-assistant-view="artifact"]');
  const resizer = shell.querySelector(".course-assistant-resizer");
  const sessionSelect = shell.querySelector("#course-assistant-session");
  const sessionName = shell.querySelector('.course-assistant-sessions input[type="text"]');
  const sessionStatus = shell.querySelector(".course-assistant-sessions [role=status]");
  const sessionTitle = shell.querySelector("[data-course-assistant-title]");
  const contextText = shell.querySelector(".course-assistant-context span");
  const usePageButton = shell.querySelector("[data-course-assistant-use-page]");
  const newSessionButton = shell.querySelector("[data-course-assistant-new]");
  let store = loadCourseAssistantStore();
  const initial = store.sessions.find(item => item.id === store.activeId) || store.sessions[0];
  if (initial && !initial.pageId && !initial.history.length) {
    initial.pageId = page.id; initial.pageTitle = title;
  }
  let chatApi = null;
  let mountedSessionId = null;
  let artifactBlobUrl = "";
  const artifactBridgeId = crypto.randomUUID?.() || "artifact-" + Math.random().toString(36).slice(2);
  const artifactEditors = { html: null, javascript: null };
  let syncingArtifactEditors = false;
  const editorValue = (kind, textarea) => artifactEditors[kind]?.getValue() ?? textarea.value;
  const setEditorValue = (kind, textarea, value) => {
    if (artifactEditors[kind] && artifactEditors[kind].getValue() !== value) {
      syncingArtifactEditors = true; artifactEditors[kind].setValue(value); syncingArtifactEditors = false;
    }
    else textarea.value = value;
  };
  const clearArtifactPreview = message => {
    if (artifactBlobUrl) { URL.revokeObjectURL(artifactBlobUrl); artifactBlobUrl = ""; }
    artifactFrame.src = "about:blank";
    if (message) artifactStatus.textContent = message;
  };
  const activeSession = () => store.sessions.find(item => item.id === store.activeId) || store.sessions[0];
  let activeView = "chat";
  const activateView = view => {
    activeView = view === "artifact" ? "artifact" : "chat";
    body.hidden = activeView !== "chat";
    artifactPanel.hidden = activeView !== "artifact";
    viewButtons.forEach(button => button.setAttribute("aria-selected", String(button.dataset.courseAssistantView === activeView)));
    if (activeView === "artifact") setTimeout(() => Object.values(artifactEditors).forEach(editor => editor?.refresh()), 0);
  };
  const artifactDocument = artifact => {
    const csp = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; font-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'">`;
    const javascript = String(artifact?.javascript || "").replace(/<\/script/gi, "<\\/script");
    const bridge = `<script>(function(){const channel=${JSON.stringify(artifactBridgeId)},pending=new Map();let seq=0;window.course=Object.freeze({embed:(input,options={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});parent.postMessage({channel,type:"request",id,method:"embed",args:[input,options]},"*");setTimeout(()=>{if(pending.delete(id))reject(new Error("course.embed timed out"));},65000);})});addEventListener("message",event=>{const data=event.data||{};if(data.channel!==channel||data.type!=="response"||!pending.has(data.id))return;const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(new Error(data.error)):item.resolve(data.result);});const report=value=>parent.postMessage({channel,type:"artifact-error",message:String(value?.message||value),line:value?.lineno||0,column:value?.colno||0},"*");addEventListener("error",event=>report(event));addEventListener("unhandledrejection",event=>report(event.reason));})();<\/script>`;
    const script = `${bridge}<script>\n${javascript}\n<\/script>`;
    const html = String(artifact?.html || "").trim();
    if (/<html[\s>]/i.test(html)) {
      let documentText = /<head[\s>]/i.test(html) ? html.replace(/<head([^>]*)>/i, `<head$1>${csp}`) : csp + html;
      return /<\/body>/i.test(documentText) ? documentText.replace(/<\/body>/i, script + "</body>") : documentText + script;
    }
    return `<!doctype html><html><head><meta charset="utf-8">${csp}<style>:root{color-scheme:light}body{font:16px/1.5 system-ui;margin:1rem;color:var(--tx,#161616)}*{box-sizing:border-box}</style></head><body>${html}${script}</body></html>`;
  };
  const renderArtifact = (run = false) => {
    const artifact = activeSession()?.artifact;
    artifactTitle.value = artifact?.title || "Browser artifact";
    setEditorValue("html", artifactHtml, artifact?.html || "");
    setEditorValue("javascript", artifactJs, artifact?.javascript || "");
    artifactViewButton.textContent = copy.artifactView + (artifact ? " •" : "");
    artifactStatus.textContent = artifact ? new Date(artifact.updatedAt).toLocaleString() : "";
    if (run && artifact) {
      clearArtifactPreview();
      artifactBlobUrl = URL.createObjectURL(new Blob([artifactDocument(artifact)], { type: "text/html" }));
      artifactFrame.src = artifactBlobUrl;
    } else if (!artifact) clearArtifactPreview();
  };
  const renderSessions = () => {
    sessionSelect.replaceChildren(...store.sessions.map(session => {
      const option = document.createElement("option"); option.value = session.id;
      const label = session.title === "New session" ? copy.emptyTitle : session.title;
      option.textContent = label + (session.pageId ? " · " + session.pageId : ""); return option;
    }));
    sessionSelect.value = store.activeId;
    const session = activeSession();
    const label = session?.title === "New session" ? copy.emptyTitle : session?.title || copy.emptyTitle;
    sessionName.value = label;
    sessionTitle.textContent = label;
    const attached = session?.pageId ? `${copy.attached}: ${session.pageId}${session.pageTitle ? " · " + session.pageTitle : ""}` : copy.noPage;
    contextText.textContent = attached + " · " + copy.tools;
    usePageButton.textContent = session?.pageId === page.id ? copy.refreshPage : copy.usePage(page.id);
    newSessionButton.disabled = store.sessions.length >= MAX_ASSISTANT_SESSIONS;
  };
  const persistStore = (message = copy.saved) => {
    try {
      const saved = saveCourseAssistantStore(store); renderSessions();
      sessionStatus.textContent = `${message} · ${saved.sessions}/${MAX_ASSISTANT_SESSIONS} · ${Math.ceil(saved.chars / 1024)} KB`;
    }
    catch (error) { sessionStatus.textContent = `${copy.full} · ${error?.name || "storage error"}`; }
  };
  persistStore(copy.saved);
  renderArtifact(true);
  viewButtons.forEach(button => button.addEventListener("click", () => activateView(button.dataset.courseAssistantView)));
  let artifactSaveTimer = 0;
  let runArtifact = () => {};
  const saveArtifact = (message = copy.saved, run = false) => {
    if (artifactSaveTimer) { clearTimeout(artifactSaveTimer); artifactSaveTimer = 0; }
    const session = activeSession();
    if (!session) return;
    session.artifact = cleanArtifact({
      title: artifactTitle.value,
      html: editorValue("html", artifactHtml),
      javascript: editorValue("javascript", artifactJs),
      updatedAt: Date.now(),
    });
    session.updatedAt = Date.now();
    persistStore(message);
    renderArtifact(run);
  };
  const scheduleArtifactSave = () => {
    clearTimeout(artifactSaveTimer);
    artifactSaveTimer = setTimeout(() => saveArtifact(copy.saved, false), 300);
  };
  const flushArtifactSave = () => {
    if (!artifactSaveTimer) return;
    clearTimeout(artifactSaveTimer); artifactSaveTimer = 0; saveArtifact(copy.saved, false);
  };
  artifactTitle.addEventListener("input", scheduleArtifactSave);
  const ensureArtifactHtmlMode = () => {
    if (typeof window.CodeMirror?.defineMode !== "function" || window.CodeMirror.modes["course-html"]) return;
    window.CodeMirror.defineMode("course-html", () => ({
      startState: () => ({ inTag: false }),
      token: (stream, state) => {
        if (!state.inTag) {
          if (stream.match("<!--")) { if (!stream.skipTo("-->")) stream.skipToEnd(); else stream.match("-->"); return "comment"; }
          if (stream.peek() === "<") { stream.next(); stream.eat("/"); state.inTag = true; return "tag"; }
          stream.next(); stream.eatWhile(/[^<]/); return null;
        }
        if (stream.peek() === ">") { stream.next(); state.inTag = false; return "tag"; }
        if (stream.peek() === "/") { stream.next(); return "tag"; }
        if (/["']/.test(stream.peek())) { const quote = stream.next(); while (!stream.eol()) { if (stream.next() === quote) break; } return "string"; }
        if (stream.match(/^[A-Za-z_:][\w:.-]*(?=\s*=)/)) return "attribute";
        if (stream.match(/^[A-Za-z_:][\w:.-]*/)) return "tag";
        stream.next(); return null;
      },
    }));
  };
  ensureArtifactHtmlMode();
  const attachArtifactEditor = (textarea, kind, mode) => {
    if (typeof window.CodeMirror !== "function") {
      textarea.addEventListener("input", scheduleArtifactSave);
      textarea.addEventListener("keydown", event => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); runArtifact(); }
      });
      return null;
    }
    const editor = window.CodeMirror.fromTextArea(textarea, {
      mode, theme: "monokai", lineNumbers: true, lineWrapping: false,
      indentUnit: 2, tabSize: 2, indentWithTabs: false, viewportMargin: 20,
      extraKeys: {
        "Ctrl-Enter": () => runArtifact(), "Cmd-Enter": () => runArtifact(),
        "Tab": item => item.execCommand("indentMore"), "Shift-Tab": item => item.execCommand("indentLess"),
      },
    });
    editor.setSize("100%", "100%");
    textarea.__courseAssistantEditor = editor;
    editor.on("change", () => { if (!syncingArtifactEditors) scheduleArtifactSave(); });
    return editor;
  };
  artifactEditors.html = attachArtifactEditor(artifactHtml, "html", window.CodeMirror?.modes?.htmlmixed ? "htmlmixed" : "course-html");
  artifactEditors.javascript = attachArtifactEditor(artifactJs, "javascript", "javascript");
  runArtifact = () => {
    saveArtifact(copy.saved, false);
    const javascript = editorValue("javascript", artifactJs);
    if (/\bimport\s*\(|\bimport\s+[\s\S]*?\bfrom\s*["']|\bfrom\s*["']\.\.?\//.test(javascript)) {
      artifactStatus.textContent = copy.unsupportedImport; artifactStatus.classList.add("error"); return;
    }
    try { Function(javascript); }
    catch (error) { artifactStatus.textContent = `${copy.syntaxError}: ${error.message}`; artifactStatus.classList.add("error"); return; }
    artifactStatus.classList.remove("error"); renderArtifact(true);
  };
  shell.querySelector("[data-course-artifact-run]").addEventListener("click", runArtifact);
  shell.querySelector("[data-course-artifact-clear]").addEventListener("click", () => {
    flushArtifactSave(); clearArtifactPreview(copy.previewCleared);
  });
  shell.querySelector("[data-course-artifact-delete]").addEventListener("click", () => {
    if (artifactSaveTimer) { clearTimeout(artifactSaveTimer); artifactSaveTimer = 0; }
    const session = activeSession();
    if (!session) return;
    session.artifact = null; session.updatedAt = Date.now();
    persistStore(copy.saved); renderArtifact(false); artifactStatus.textContent = copy.artifactDeleted;
  });
  window.addEventListener("message", async event => {
    const data = event.data || {};
    if (event.source !== artifactFrame.contentWindow || data.channel !== artifactBridgeId) return;
    if (data.type === "artifact-error") {
      const locationText = data.line ? ` · line ${data.line}${data.column ? ":" + data.column : ""}` : "";
      artifactStatus.textContent = `${copy.runtimeError}: ${String(data.message || "unknown error").slice(0, 500)}${locationText}`;
      artifactStatus.classList.add("error"); return;
    }
    if (data.type !== "request" || data.method !== "embed") return;
    const respond = payload => artifactFrame.contentWindow?.postMessage({ channel: artifactBridgeId, type: "response", id: data.id, ...payload }, "*");
    try {
      if (typeof runtime.embed !== "function") throw new Error("course.embed is unavailable on this page");
      const rawInput = data.args?.[0];
      const input = (Array.isArray(rawInput) ? rawInput : [rawInput]).map(value => String(value || ""));
      if (!input.length || input.length > 16 || input.some(value => !value || value.length > 2000) || input.join("").length > 12000) {
        throw new Error("course.embed accepts 1-16 non-empty strings, up to 12,000 characters total");
      }
      const requestedType = data.args?.[1]?.inputType;
      const inputType = requestedType === "passage" ? "passage" : "query";
      respond({ result: await runtime.embed(input, { inputType }) });
    } catch (error) { respond({ error: String(error?.message || error).slice(0, 500) }); }
  });
  window.addEventListener("pagehide", () => {
    flushArtifactSave();
  });
  const maxPanelWidth = () => Math.floor(window.innerWidth * 0.9);
  const minPanelWidth = () => Math.min(320, maxPanelWidth());
  const setPanelWidth = (width, persist = true) => {
    if (window.innerWidth <= 640) {
      panel.style.removeProperty("width");
      return;
    }
    const next = Math.max(minPanelWidth(), Math.min(maxPanelWidth(), Math.round(width)));
    panel.style.width = next + "px";
    resizer.setAttribute("aria-valuenow", String(next));
    resizer.setAttribute("aria-valuemax", String(maxPanelWidth()));
    if (persist) try { localStorage.setItem(ASSISTANT_WIDTH_KEY, String(next)); } catch (_) {}
  };
  const resetPanelWidth = () => {
    try { localStorage.removeItem(ASSISTANT_WIDTH_KEY); } catch (_) {}
    setPanelWidth(Math.min(480, maxPanelWidth()), false);
  };
  try {
    const saved = Number(localStorage.getItem(ASSISTANT_WIDTH_KEY));
    if (Number.isFinite(saved) && saved > 0) setPanelWidth(saved, false);
    else resetPanelWidth();
  } catch (_) { resetPanelWidth(); }
  resizer.addEventListener("pointerdown", event => {
    if (window.innerWidth <= 640) return;
    event.preventDefault();
    resizer.setPointerCapture(event.pointerId);
    shell.classList.add("resizing");
  });
  resizer.addEventListener("pointermove", event => {
    if (resizer.hasPointerCapture(event.pointerId)) setPanelWidth(window.innerWidth - event.clientX);
  });
  const endResize = event => {
    if (resizer.hasPointerCapture(event.pointerId)) resizer.releasePointerCapture(event.pointerId);
    shell.classList.remove("resizing");
  };
  resizer.addEventListener("pointerup", endResize);
  resizer.addEventListener("pointercancel", endResize);
  resizer.addEventListener("dblclick", resetPanelWidth);
  resizer.addEventListener("keydown", event => {
    const width = panel.getBoundingClientRect().width;
    if (event.key === "ArrowLeft") setPanelWidth(width + 48);
    else if (event.key === "ArrowRight") setPanelWidth(width - 48);
    else if (event.key === "Home") resetPanelWidth();
    else if (event.key === "End") setPanelWidth(maxPanelWidth());
    else return;
    event.preventDefault();
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth <= 640) panel.style.removeProperty("width");
    else setPanelWidth(panel.getBoundingClientRect().width, false);
  });
  let priorFocus = null;
  const mountSession = async (session = activeSession()) => {
    if (!session || mountedSessionId === session.id) return;
    if (chatApi?.stop) chatApi.stop();
    body.replaceChildren();
    mountedSessionId = session.id;
    const attachedPage = coursePages().find(item => item.id === session.pageId) || null;
    const attachedTitle = session.pageTitle || attachedPage?.title || "";
    const pageContext = async id => {
      const [prose, artifacts] = await Promise.all([coursePage(id), courseCodeArtifacts(id)]);
      const codeIndex = artifacts.length
        ? artifacts.map(item => `- ${id}#${item.id} · ${item.kind} · ${item.lines} lines · ${item.summary}`).join("\n")
        : "(no lesson code artifacts on this page)";
      return `${prose}\n\n## Available implementation source\n${codeIndex}\n\nUse the code-reading tools for exact source. Course-authored source is public and Apache-2.0; never claim it is private or inaccessible.`;
    };
    chatApi = await mountAgentChat(body, {
      models: MODELS,
      memory: true,
      initialHistory: session.history,
      resetLabel: copy.clear,
      compactAtTokens: 12000,
      compactKeepMessages: 6,
      onUserMessage: question => {
        const current = store.sessions.find(item => item.id === mountedSessionId);
        if (!current) return;
        if (!current.manualTitle) current.title = question.replace(/\s+/g, " ").trim().slice(0, 48) || "New session";
        current.updatedAt = Date.now();
        persistStore(copy.saved);
      },
      onTurnSnapshot: (history, meta) => {
        const current = store.sessions.find(item => item.id === mountedSessionId);
        if (!current) return;
        current.history = cleanHistory(history); current.updatedAt = Date.now();
        persistStore(meta?.state === "running" ? copy.saving : copy.saved);
      },
      onHistoryChange: history => {
        const current = store.sessions.find(item => item.id === mountedSessionId);
        if (!current) return;
        current.history = cleanHistory(history);
        const firstUser = current.history.find(item => item.role === "user");
        if (!current.manualTitle) current.title = firstUser ? firstUser.content.replace(/\s+/g, " ").trim().slice(0, 48) || "New session" : "New session";
        current.updatedAt = Date.now();
        persistStore(current.history.some(item => item.role === "system") ? copy.compacted : copy.saved);
      },
      onAssistantMessage: answer => {
        const current = store.sessions.find(item => item.id === mountedSessionId);
        if (!current) return;
        const artifact = artifactFromMarkdown(answer, `${current.title || "Course Assistant"} artifact`);
        if (!artifact) return;
        current.artifact = artifact; current.updatedAt = Date.now();
        persistStore(copy.saved); renderArtifact(false); artifactStatus.textContent = copy.generatedReady;
      },
      intro: copy.intro,
      greeting: copy.greeting(attachedPage?.id || ""),
      examples: copy.examples,
      system: pt
        ? `Você é o Assistente do Curso Securing Agents. ${attachedPage ? `Esta sessão está vinculada à página ${attachedPage.id}, “${attachedTitle}”, fornecida como contexto inicial. Comece por ela.` : "Esta sessão não tem uma página vinculada."} Para perguntas sobre o curso, use list_course_pages, search_course_pages e read_course_page. Para código, use list_course_code e depois read_course_source com o URI retornado; para módulos compartilhados, use list_course_runtime_files e read_course_runtime_source. Invoque as ferramentas pela API: nunca imprima os argumentos JSON como resposta. O runtime do curso é JavaScript no navegador: use HTML/JavaScript por padrão. O sandbox de artefato fornece course.embed(textos, {inputType}); não use import, fetch, localStorage nem pacotes externos. O curso não oferece uma célula genérica para colar código. Use queue_course_artifact para criar uma área editável e executável. Leia o código antes de explicar e nunca invente uma implementação nem alegue que o código é privado ou inacessível. Cite os IDs das páginas e os arquivos usados.`
        : `You are the Course Assistant for Securing Agents. ${attachedPage ? `This session is attached to ${attachedPage.id}, “${attachedTitle}”, supplied as initial context. Begin there.` : "This session has no attached page."} For course questions, use list_course_pages, search_course_pages, and read_course_page. For code, use list_course_code then read_course_source with the returned URI; for shared modules use list_course_runtime_files and read_course_runtime_source. Invoke tools through the API: never print tool arguments as JSON. The course runtime is browser JavaScript: default to HTML/JavaScript. The artifact sandbox provides course.embed(texts, { inputType }); do not use import, fetch, localStorage, or external packages. The course has no generic pasteable code cell. Use queue_course_artifact to create an editable, runnable view. Inspect source before explaining code, and never invent an implementation or claim source is private or inaccessible. Cite course page ids and source files used.`,
      recoverInlineToolIntent: async answer => {
        const intent = parseInlineCourseSourceIntent(answer);
        return intent ? resolveCourseSourceUri(intent.uri, attachedPage?.id || "") : null;
      },
      initialContext: attachedPage ? async () => ({ label: (pt ? "página + índice de código · " : "page + code index · ") + attachedPage.id, content: await pageContext(attachedPage.id) }) : null,
      buildTools: ({ tool, z, coursePage: readPage, coursePages: pages }) => {
        const catalog = pages();
        return [
          tool(async () => catalog.map(item => `${item.id} · ${item.title}`).join("\n"), {
            name: "list_course_pages",
            description: pt ? "Liste os IDs e títulos das páginas antes de escolher o que consultar." : "List every Securing Agents course page id and title before choosing what to inspect.",
            schema: z.object({}),
          }),
          tool(async ({ query }) => {
            return JSON.stringify(await searchCoursePages(query, readPage, catalog), null, 2);
          }, {
            name: "search_course_pages",
            description: pt ? "Busque no texto do curso e retorne as páginas mais relevantes com trechos curtos." : "Search all course prose and return the most relevant page ids with short excerpts.",
            schema: z.object({ query: z.string().min(2).describe(pt ? "conceito ou frase a localizar no curso" : "concept or phrase to find across the course") }),
          }),
          tool(async ({ page: id }) => readPage(id), {
            name: "read_course_page",
            description: pt ? "Leia uma página completa depois que o mapa ou a busca a identificar." : "Read one complete Securing Agents page after the map or search identifies it.",
            schema: z.object({ page: z.enum(catalog.map(item => item.id)).describe("course page id") }),
          }),
          tool(async ({ page: id }) => JSON.stringify((await courseCodeArtifacts(id)).map(item => ({ ...item, uri: `${id}#${item.id}` })), null, 2), {
            name: "list_course_code",
            description: pt ? "Liste as células e os módulos JavaScript disponíveis em uma página." : "List the exact JavaScript lesson artifacts and page modules available on one course page.",
            schema: z.object({ page: z.enum(catalog.map(item => item.id)).describe("course page id") }),
          }),
          tool(async ({ uri }) => {
            const resolved = await resolveCourseSourceUri(uri, attachedPage?.id || "");
            return resolved?.content || `(unknown course source URI "${uri}")`;
          }, {
            name: "read_course_source",
            description: pt ? "Leia o código-fonte exato usando o URI retornado por list_course_code." : "Read exact lesson source using the single URI returned by list_course_code, for example 02c-deep#deep-src.",
            schema: z.object({ uri: z.string().min(1).describe("source URI returned by list_course_code") }),
          }),
          tool(async () => courseRuntimeFiles().map(item => `${item.file} · ${item.summary}`).join("\n"), {
            name: "list_course_runtime_files",
            description: pt ? "Liste os módulos JavaScript compartilhados e públicos do curso." : "List public shared JavaScript modules such as _shared.js and _canvas.js.",
            schema: z.object({}),
          }),
          tool(async ({ file }) => courseRuntimeSource(file), {
            name: "read_course_runtime_source",
            description: pt ? "Leia o código-fonte exato de um módulo compartilhado listado." : "Read the exact public source of one shared course runtime module.",
            schema: z.object({ file: z.enum(courseRuntimeFiles().map(item => item.file)).describe("runtime filename") }),
          }),
          tool(async ({ title: artifactName, html, javascript }) => {
            const current = store.sessions.find(item => item.id === mountedSessionId);
            if (!current) return "No active Course Assistant session.";
            current.artifact = cleanArtifact({ title: artifactName, html, javascript, updatedAt: Date.now() });
            current.updatedAt = Date.now(); persistStore(copy.saved); renderArtifact(true); activateView("artifact");
            return `Queued browser artifact “${current.artifact.title}” with ${current.artifact.html.length} HTML chars and ${current.artifact.javascript.length} JavaScript chars.`;
          }, {
            name: "queue_course_artifact",
            description: pt ? "Crie uma área editável e executável. Para embeddings, chame course.embed; não use import, fetch, localStorage ou pacotes externos." : "Queue editable HTML/JavaScript. For embeddings call course.embed; do not use import, fetch, localStorage, external packages, or a nonexistent course cell.",
            schema: z.object({
              title: z.string().min(1).describe("short artifact title"),
              html: z.string().describe("HTML body or complete document; use an empty string when not needed"),
              javascript: z.string().describe("browser JavaScript; use an empty string when not needed"),
            }),
          }),
        ];
      },
      recursionLimit: 24,
    });
  };
  sessionSelect.addEventListener("change", async () => {
    flushArtifactSave(); store.activeId = sessionSelect.value; mountedSessionId = null;
    persistStore(copy.selected); renderArtifact(true); await mountSession();
  });
  const renameSession = () => {
    const session = activeSession();
    if (!session) return;
    const name = sessionName.value.replace(/\s+/g, " ").trim().slice(0, 72);
    if (!name) { renderSessions(); return; }
    session.title = name; session.manualTitle = true; session.updatedAt = Date.now();
    persistStore(copy.renamed);
  };
  sessionName.addEventListener("change", renameSession);
  sessionName.addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); renameSession(); sessionName.blur(); }
  });
  usePageButton.addEventListener("click", async () => {
    const session = activeSession();
    if (!session) return;
    session.pageId = page.id; session.pageTitle = title; session.updatedAt = Date.now();
    mountedSessionId = null; persistStore(copy.attachedNow); await mountSession(session);
  });
  newSessionButton.addEventListener("click", async () => {
    flushArtifactSave();
    const current = activeSession();
    if (current && !current.history.length && !current.artifact && current.title === "New session") {
      sessionName.focus(); sessionName.select(); return;
    }
    if (store.sessions.length >= MAX_ASSISTANT_SESSIONS) { sessionStatus.textContent = `${copy.full} · ${MAX_ASSISTANT_SESSIONS}/${MAX_ASSISTANT_SESSIONS}`; return; }
    const session = newSession({ id: page.id, title }); store.sessions.unshift(session); store.activeId = session.id; mountedSessionId = null;
    persistStore(copy.created); renderArtifact(true); await mountSession(session);
  });
  shell.querySelector("[data-course-assistant-delete]").addEventListener("click", async () => {
    flushArtifactSave();
    if (chatApi?.stop) chatApi.stop();
    store.sessions = store.sessions.filter(item => item.id !== store.activeId);
    if (!store.sessions.length) store.sessions.push(newSession({ id: page.id, title }));
    store.activeId = store.sessions[0].id; mountedSessionId = null; persistStore(copy.deleted); renderArtifact(true); await mountSession();
  });
  const close = () => {
    shell.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    launcher.setAttribute("aria-expanded", "false");
    if (priorFocus) priorFocus.focus();
  };
  const open = async () => {
    priorFocus = document.activeElement;
    shell.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    launcher.setAttribute("aria-expanded", "true");
    await mountSession();
    panel.querySelector("button[data-course-assistant-close]").focus();
  };
  launcher.addEventListener("click", () => shell.classList.contains("open") ? close() : open());
  shell.querySelectorAll("[data-course-assistant-close]").forEach(el => el.addEventListener("click", close));
  window.addEventListener("keydown", event => { if (event.key === "Escape" && shell.classList.contains("open")) close(); });
}

export function mountCourseLicenseNote() {
  if (document.querySelector(".course-license-note")) return;
  const main = document.querySelector("main");
  if (!main || !document.querySelector(".topbar")) return;
  const note = document.createElement("footer");
  note.className = "course-license-note";
  note.innerHTML = document.documentElement.lang.toLowerCase().startsWith("pt")
    ? 'Material do curso, código de exemplo e diagramas originais: <a href="../../LICENSE">Apache-2.0</a>. Material externo citado mantém seus próprios termos; veja a <a href="assets/SKILL.html">proveniência</a>.'
    : 'Course-authored prose, example code, and original diagrams: <a href="../../LICENSE">Apache-2.0</a>. Named external material keeps its own terms; see <a href="assets/SKILL.html">provenance</a>.';
  main.appendChild(note);
}
