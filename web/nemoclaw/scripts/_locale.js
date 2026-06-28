// Accessible course-language switcher backed by the build-time language manifest.
// The manifest lists only built locales; each locale lists pages that passed localization review.

const PT_TEXT = new Map(Object.entries({
  "The Agent": "O agente",
  "The ReAct Loop": "O ciclo ReAct",
  "Tools at Scale": "Ferramentas em escala",
  "Workflows": "Workflows",
  "The Index Agent": "O agente de índice",
  "Deep Agents": "Agentes profundos",
  "Connect NemoClaw": "Conectar o NemoClaw",
  "Always-On": "Operação contínua",
  "Modern CLIs": "CLIs modernas",
  "Going Further": "Próximos passos",
  "loop · LLM as function": "ciclo · LLM como função",
  "tools · finish_reason": "ferramentas · finish_reason",
  "JSON · MCP · routing": "JSON · MCP · roteamento",
  "router · planner · ReWOO": "roteador · planejador · ReWOO",
  "embed · retrieve · bundle": "incorporar · recuperar · pacote",
  "planner · sub-agents · VFS": "planejador · subagentes · VFS",
  "launchable · first call": "launchable · primeira chamada",
  "file-as-context · paste URL": "arquivo como contexto · colar URL",
  "sandbox · policy · CI gate": "sandbox · política · gate de CI",
  "Section": "Seção",
  "Section 1": "Seção 1",
  "Section 2": "Seção 2",
  "Section 3": "Seção 3",
  "Section 4": "Seção 4",
  "Course map": "Mapa do curso",
  "click to see all sections": "clique para ver todas as seções",
  "start": "início",
  "end": "fim",
  "No API key": "Sem chave de API",
  "Key …": "Chave …",
  "Key set ✓": "Chave definida ✓",
  "Key rejected ✗": "Chave rejeitada ✗",
  "Model": "Modelo",
  "Pages": "Páginas",
  "none pinned = auto-select": "nenhuma fixada = seleção automática",
  "🧠 memory: on": "🧠 memória: ativa",
  "🧠 memory: off": "🧠 memória: inativa",
  "↺ New chat": "↺ Nova conversa",
  "Ask a question…": "Faça uma pergunta…",
  "Send": "Enviar",
  "⏹ Stop": "⏹ Parar",
  "▶ Run": "▶ Executar",
  "▶ Run all": "▶ Executar tudo",
  "⏳ Running…": "⏳ Executando…",
  "↺ Reset": "↺ Restaurar",
  "↺ Reset code": "↺ Restaurar código",
  "Ready": "Pronto",
  "empty until you Run": "vazio até executar",
  "reset. empty until you Run": "restaurado; vazio até executar",
  "javascript · editable · re-run": "javascript · editável · execute novamente",
  "JSON · editable": "JSON · editável",
  "click to collapse": "clique para recolher",
  "click to expand": "clique para expandir",
  "in scope inside every node:": "disponível em todos os nós:",
  "click a row to inspect & edit its source": "clique em uma linha para inspecionar e editar o código-fonte",
  "in scope for this cell. Click a row to read its source": "disponível nesta célula. Clique em uma linha para ler o código-fonte",
  "✓ API key saved for this browser": "✓ Chave de API salva neste navegador",
  "Enable LMS/static iframe execution": "Ativar execução em iframe LMS/estático",
  "Enable LMS/static iframe execution through the hosted proxy": "Ativar execução em iframe LMS/estático pelo proxy hospedado",
  "Change": "Alterar",
  "NVIDIA API key (starts with": "Chave da API NVIDIA (começa com",
  "Save & verify": "Salvar e verificar",
  "No key yet?": "Ainda não tem uma chave?",
  "Sign up at build.nvidia.com →": "Cadastre-se em build.nvidia.com →",
  "Free-tier models cover every exercise. Leave iframe mode off unless your host page needs it.": "Os modelos da camada gratuita atendem a todos os exercícios. Deixe o modo iframe desativado, a menos que a página hospedeira precise dele."
}));

const PT_ATTRS = new Map(Object.entries({
  "Ask a question…": "Faça uma pergunta…",
  "Course progression; current step highlighted.": "Progresso do curso; etapa atual destacada.",
  "Show the whole course map": "Mostrar o mapa completo do curso",
  "Choose language": "Escolher idioma",
  "Run every node in order": "Executar todos os nós em ordem",
  "Run this cell": "Executar esta célula",
  "Restore every node's code to its original": "Restaurar o código original de todos os nós",
  "Restore this cell's original code and clear its output": "Restaurar o código original desta célula e limpar a saída",
  "Copy current code": "Copiar o código atual"
}));

const LOCALIZED_UI = "#journey-map,.topbar,.cf-wrap,.rc-card,.chatui,.key-panel";

function ptPage() {
  return document.documentElement.lang.toLowerCase() === "pt-br";
}

function translatedText(value) {
  const direct = PT_TEXT.get(value);
  if (direct) return direct;
  for (const [prefix, replacement] of [["Previous: ", "Anterior: "], ["Next: ", "Próxima: "]]) {
    if (value.startsWith(prefix)) return replacement + (PT_TEXT.get(value.slice(prefix.length)) || value.slice(prefix.length));
  }
  return value;
}

function localizeUi(root = document.body) {
  if (!ptPage() || !root) return;
  const scopes = [];
  if (root.nodeType === Node.ELEMENT_NODE && root.matches?.(LOCALIZED_UI)) scopes.push(root);
  if (root.nodeType === Node.ELEMENT_NODE) scopes.push(...root.querySelectorAll?.(LOCALIZED_UI) || []);
  if (!scopes.length && root.nodeType === Node.ELEMENT_NODE && root.closest?.(LOCALIZED_UI)) scopes.push(root);
  scopes.forEach(scope => {
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      if (node.parentElement?.closest("pre,code,textarea,script,style")) return;
      const value = node.nodeValue || "";
      const trimmed = value.trim();
      if (!trimmed) return;
      const replacement = translatedText(trimmed);
      if (replacement !== trimmed) node.nodeValue = value.replace(trimmed, replacement);
    });
    scope.querySelectorAll?.("[placeholder],[title],[aria-label]").forEach(element => {
      for (const attr of ["placeholder", "title", "aria-label"]) {
        const value = element.getAttribute(attr);
        if (!value) continue;
        const replacement = PT_ATTRS.get(value) || translatedText(value);
        if (replacement !== value) element.setAttribute(attr, replacement);
      }
    });
  });
}

function mountPortugueseUi() {
  if (!ptPage() || document.documentElement.dataset.ptUiMounted === "1") return;
  document.documentElement.dataset.ptUiMounted = "1";
  localizeUi();
  new MutationObserver(mutations => mutations.forEach(mutation => {
    const root = mutation.target.nodeType === Node.ELEMENT_NODE ? mutation.target : mutation.target.parentElement;
    localizeUi(root);
  })).observe(document.body, { childList: true, subtree: true, characterData: true });
}

function manifestCandidates() {
  const parts = location.pathname.split("/").filter(Boolean);
  const courseAt = parts.lastIndexOf("nemoclaw");
  const parent = courseAt > 0 ? parts[courseAt - 1] : "";
  const nested = parent === "web" || /^[a-z]{2}(?:-[a-z0-9]+)?$/.test(parent);
  const first = nested ? "../../languages.json" : "../languages.json";
  return [first, "../languages.json", "../../languages.json", "../../../languages.json", "../../../../languages.json"]
    .filter((item, index, all) => all.indexOf(item) === index);
}

async function findManifest() {
  for (const rel of manifestCandidates()) {
    try {
      const url = new URL(rel, location.href);
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) continue;
      const data = await response.json();
      if (data?.schema === "nemoclaw-languages/1" && Array.isArray(data.languages)) {
        return { data, url };
      }
    } catch (_) {}
  }
  return null;
}

function courseBase(entry, manifestUrl) {
  return new URL(entry.url, manifestUrl);
}

function currentEntry(languages, manifestUrl) {
  const here = location.href.split(/[?#]/)[0];
  return [...languages]
    .map(entry => ({ entry, base: courseBase(entry, manifestUrl).href }))
    .filter(item => here.startsWith(item.base))
    .sort((a, b) => b.base.length - a.base.length)[0]?.entry || languages[0];
}

function pageName(entry, manifestUrl) {
  const base = courseBase(entry, manifestUrl);
  const rel = location.href.split(/[?#]/)[0].slice(base.href.length);
  return (rel || "index.html").split("/").pop() || "index.html";
}

function hasPage(entry, file) {
  return !Array.isArray(entry.available_pages) || entry.available_pages.includes(file);
}

function targetUrl(entry, manifestUrl, file) {
  const base = courseBase(entry, manifestUrl);
  const target = new URL(hasPage(entry, file) ? file : "index.html", base);
  target.search = location.search;
  target.hash = location.hash;
  return target.href;
}

function rewriteUnavailableCourseLinks(current, fallback, manifestUrl) {
  if (!current || current.code === fallback.code) return;
  const currentBase = courseBase(current, manifestUrl);
  const fallbackBase = courseBase(fallback, manifestUrl);
  document.querySelectorAll('a[href]').forEach(anchor => {
    if (!(anchor instanceof HTMLAnchorElement)) return;
    let url;
    try { url = new URL(anchor.getAttribute("href"), location.href); } catch (_) { return; }
    if (url.origin !== location.origin || !url.href.startsWith(currentBase.href)) return;
    const file = url.pathname.split("/").pop() || "index.html";
    if (!file.endsWith(".html") || hasPage(current, file)) return;
    anchor.href = new URL(file, fallbackBase).href;
    anchor.dataset.languageFallback = fallback.code;
    const note = current.locale === "pt-BR" ? "Ainda não disponível em português; abre em inglês." : "Not available in this language; opens in English.";
    anchor.title = anchor.title ? `${anchor.title} · ${note}` : note;
    if (!anchor.querySelector(".language-fallback-badge")) {
      const badge = document.createElement("span");
      badge.className = "language-fallback-badge";
      badge.textContent = fallback.code.toUpperCase();
      badge.setAttribute("aria-label", note);
      anchor.appendChild(badge);
    }
  });
}

export async function mountLanguageMenu() {
  mountPortugueseUi();
  const bar = document.querySelector(".topbar");
  if (!bar || bar.querySelector(".language-menu")) return;
  const found = await findManifest();
  if (!found || found.data.languages.length < 2) return;
  const languages = found.data.languages;
  const current = currentEntry(languages, found.url);
  const fallback = languages.find(entry => entry.code === found.data.default) || languages[0];
  const file = pageName(current, found.url);
  rewriteUnavailableCourseLinks(current, fallback, found.url);

  const wrap = document.createElement("div");
  wrap.className = "language-menu";
  const button = document.createElement("button");
  button.className = "language-menu-button";
  button.type = "button";
  button.textContent = "🌐";
  button.setAttribute("aria-label", current.locale === "pt-BR" ? "Escolher idioma" : "Choose language");
  button.setAttribute("aria-haspopup", "menu");
  button.setAttribute("aria-expanded", "false");
  const menu = document.createElement("div");
  menu.className = "language-menu-popover";
  menu.setAttribute("role", "menu");
  menu.hidden = true;
  languages.forEach(entry => {
    const link = document.createElement("a");
    link.setAttribute("role", "menuitem");
    link.href = targetUrl(entry, found.url, file);
    link.lang = entry.locale || entry.code;
    link.textContent = entry.native_label || entry.label;
    if (entry.code === current.code) link.setAttribute("aria-current", "page");
    if (!hasPage(entry, file)) {
      const small = document.createElement("small");
      small.textContent = entry.locale === "pt-BR" ? "página inicial" : "course home";
      link.appendChild(small);
    }
    menu.appendChild(link);
  });
  const close = () => { menu.hidden = true; button.setAttribute("aria-expanded", "false"); };
  button.addEventListener("click", () => {
    const open = menu.hidden;
    menu.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    if (open) menu.querySelector("a")?.focus();
  });
  wrap.addEventListener("keydown", event => {
    if (event.key === "Escape") { close(); button.focus(); }
  });
  document.addEventListener("click", event => { if (!wrap.contains(event.target)) close(); });
  wrap.append(button, menu);
  const pill = bar.querySelector(".key-pill");
  if (pill) bar.insertBefore(wrap, pill);
  else bar.appendChild(wrap);
}
