// _chat.js holds the live chat-artifact widgets (ensureChatStyles, mountChatUI, mountAgentChat) that used to live in _shared.js.
import { CONTEXT_WINDOWS, contextWindow, coursePage, coursePages, escHtml, estimateTokens, formatSearchResults, getConfig, getKey, webSearch } from "./_shared.js";

// Inject the shared .chatui-* stylesheet once; idempotent.
// Kept separate from mountChatUI so a run-cell that inspects the panel still mounts it.
// Such a cell calls helpers.mountChatUI.toString() and gets the styles intact.
export function ensureChatStyles() {
  if (document.head.querySelector('style[data-chat-ui="3"]')) return;
  const s = document.createElement("style"); s.dataset.chatUi = "3";
  s.textContent = `
      .chatui{border:1px solid var(--bd,#2a2a2a);border-radius:10px;background:var(--e1,#161616);overflow:hidden;margin:1em 0}
      .chatui-bar{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:10px 12px;border-bottom:1px solid var(--bd,#2a2a2a);background:var(--e2,#1e1e1e)}
      .chatui-bar label{font-family:var(--mono,monospace);font-size:.7rem;color:var(--tf,#8a8a8a);text-transform:uppercase;letter-spacing:.05em}
      .chatui-bar select{background:var(--e1,#161616);color:var(--tx,#f2f2f2);border:1px solid var(--bd,#2a2a2a);border-radius:6px;padding:5px 8px;font-family:var(--mono,monospace);font-size:.78rem}
      .chatui-bar .sp{flex:1}
      .chatui-ctx{font-family:var(--mono,monospace);font-size:.7rem;color:var(--tf,#8a8a8a)}
      .chatui-reset{background:var(--e1,#161616);color:var(--td,#b0b0b0);border:1px solid var(--bd,#2a2a2a);border-radius:6px;padding:5px 11px;font-size:.76rem;cursor:pointer}
      .chatui-reset:hover{border-color:var(--g,#76b900);color:var(--gs,#aee23a)}
      .chatui-mem{background:var(--e1,#161616);color:var(--td,#b0b0b0);border:1px solid var(--bd,#2a2a2a);border-radius:6px;padding:5px 11px;font-size:.76rem;cursor:pointer;font-family:var(--mono,monospace)}
      .chatui-mem:hover{border-color:var(--g,#76b900)}
      .chatui-mem.on{background:rgba(118,185,0,.12);color:var(--gs,#aee23a);border-color:var(--g,#76b900)}
      .chatui-mods{display:flex;align-items:center;flex-wrap:wrap;gap:5px;width:100%;margin-top:2px}
      .chatui-modchip{font-family:var(--mono,monospace);font-size:.68rem;color:var(--td,#b0b0b0);background:var(--e1,#161616);border:1px solid var(--bd,#2a2a2a);border-radius:999px;padding:2px 9px;cursor:pointer}
      .chatui-modchip:hover{border-color:var(--g,#76b900)}
      .chatui-modchip.on{background:var(--g,#76b900);color:#0a0a0a;border-color:var(--g,#76b900);font-weight:700}
      .chatui-log{padding:14px 14px 6px;max-height:480px;overflow-y:auto;display:flex;flex-direction:column;gap:9px}
      .chatui-grow .chatui-log,.chatui-grow .chatui-tool-body,.chatui-grow .chatui-think-body,.chatui-grow .chatui-bot pre{max-height:none}
      .chatui-intro{font-size:.84rem;color:var(--tf,#8a8a8a);line-height:1.5}
      .chatui-examples{display:flex;flex-wrap:wrap;gap:6px;align-self:flex-start;max-width:100%}
      .chatui-ex{text-align:left;font-size:.78rem;color:var(--gs,#aee23a);background:rgba(118,185,0,.06);border:1px solid rgba(118,185,0,.28);border-radius:14px;padding:5px 11px;cursor:pointer;line-height:1.35}
      .chatui-ex:hover{background:rgba(118,185,0,.14);border-color:var(--g,#76b900)}
      .chatui-msgctl{display:flex;gap:12px;margin:-3px 3px 5px;font-family:var(--mono,monospace);font-size:.66rem}
      .chatui-msgctl.user{align-self:flex-end}.chatui-msgctl.bot{align-self:flex-start}
      .chatui-msgctl button{color:var(--tf,#8a8a8a);background:none;border:0;padding:0;cursor:pointer}
      .chatui-msgctl button:hover{color:var(--g,#76b900);text-decoration:underline}
      .chatui-msg{max-width:90%;padding:9px 13px;border-radius:12px;font-size:.9rem;line-height:1.6;word-wrap:break-word;overflow-wrap:anywhere}
      .chatui-user{align-self:flex-end;background:var(--g,#76b900);color:#0a0a0a;border-bottom-right-radius:3px;white-space:pre-wrap}
      .chatui-bot{align-self:flex-start;background:var(--e2,#1e1e1e);color:var(--tx,#f2f2f2);border:1px solid var(--bd,#2a2a2a);border-bottom-left-radius:3px}
      .chatui-bot.err{border-color:var(--err);color:var(--err);white-space:pre-wrap}
      .chatui-bot>:first-child{margin-top:0}.chatui-bot>:last-child{margin-bottom:0}
      .chatui-bot p{margin:.5em 0}.chatui-bot ul,.chatui-bot ol{margin:.5em 0;padding-left:1.4em}.chatui-bot li{margin:.2em 0}
      .chatui-bot h1,.chatui-bot h2,.chatui-bot h3{margin:.6em 0 .3em;line-height:1.3}.chatui-bot h1{font-size:1.15rem}.chatui-bot h2{font-size:1.05rem}.chatui-bot h3{font-size:.98rem}
      .chatui-bot code{font-family:var(--mono,monospace);font-size:.85em;background:var(--e2,#0d0d0d);padding:1px 5px;border-radius:4px;color:var(--gs,#aee23a)}
      .chatui-bot pre{background:var(--e2,#0d0d0d);border:1px solid var(--bd,#2a2a2a);border-radius:6px;padding:10px 12px;overflow-x:auto;margin:.5em 0}.chatui-bot pre code{background:none;padding:0;color:var(--tx,#f2f2f2)}
      .chatui-bot table{border-collapse:collapse;font-size:.85em;margin:.4em 0}.chatui-bot td,.chatui-bot th{border:1px solid var(--bd,#2a2a2a);padding:3px 8px}
      .chatui-bot a{color:var(--gs,#aee23a)}
      .chatui-tool,.chatui-think{align-self:flex-start;max-width:90%;font-family:var(--mono,monospace);font-size:.74rem;color:var(--gs,#aee23a);background:rgba(118,185,0,.07);border:1px solid rgba(118,185,0,.22);border-radius:8px;padding:4px 10px}
      details.chatui-tool>summary,details.chatui-think>summary{cursor:pointer;list-style:none}
      details.chatui-tool>summary::-webkit-details-marker,details.chatui-think>summary::-webkit-details-marker{display:none}
      .chatui-tool-body,.chatui-think-body{margin-top:6px;padding-top:6px;border-top:1px solid rgba(118,185,0,.18);color:var(--td,#b0b0b0);white-space:pre-wrap;max-height:340px;overflow:auto}
      .chatui-tool.err{color:var(--err);background:rgba(248,113,113,.07);border-color:rgba(248,113,113,.3)}
      .chatui-tool.err .chatui-tool-body{border-top-color:rgba(248,113,113,.2)}
      .chatui-think{color:var(--reason);background:rgba(130,80,223,.06);border-color:rgba(130,80,223,.28)}
      .chatui-think-body{border-top-color:rgba(130,80,223,.2)}
      .chatui-warn{align-self:flex-start;max-width:90%;font-family:var(--mono,monospace);font-size:.72rem;color:var(--warn);background:rgba(212,156,44,.08);border:1px solid rgba(212,156,44,.3);border-radius:8px;padding:4px 10px;white-space:pre-wrap}
      .chatui-usage{align-self:flex-start;font-family:var(--mono,monospace);font-size:.68rem;color:var(--tf,#8a8a8a)}
      .chatui-turn{display:flex;flex-direction:column;gap:9px;align-self:stretch}
      .chatui-turn.chatui-cursor::after{content:"▍";color:var(--g,#76b900);animation:chatui-blink 1s steps(2) infinite;align-self:flex-start;font-family:var(--mono,monospace)}
      .chatui-ctxwrap{display:inline-flex;align-items:center;gap:6px}
      .chatui-ctxbar{width:70px;height:6px;border-radius:3px;background:var(--e1,#161616);border:1px solid var(--bd,#2a2a2a);overflow:hidden}
      .chatui-ctxfill{height:100%;width:0;background:var(--g,#76b900);transition:width .2s}
      .chatui-ctx.warn{color:var(--err)}.chatui-ctx.warn .chatui-ctxfill{background:var(--err)}
      .chatui-viz{align-self:stretch;max-width:100%}
      .chatui-viz svg{display:block;width:100%;height:auto}
      .chatui-viz table{width:100%;border-collapse:collapse;font-size:.8rem}
      .chatui-viz td,.chatui-viz th{padding:3px 8px;border-bottom:1px solid var(--bd,#2a2a2a);text-align:left}
      .chatui-cursor::after{content:"▍";color:var(--g,#76b900);animation:chatui-blink 1s steps(2) infinite}
      @keyframes chatui-blink{50%{opacity:0}}
      .chatui-in{display:flex;gap:8px;padding:10px 12px;border-top:1px solid var(--bd,#2a2a2a)}
      .chatui-in textarea{flex:1;resize:none;background:var(--e2,#1e1e1e);color:var(--tx,#f2f2f2);border:1px solid var(--bd,#2a2a2a);border-radius:8px;padding:8px 11px;font-family:inherit;font-size:.9rem;line-height:1.4;min-height:20px;max-height:120px}
      .chatui-in textarea:focus{outline:none;border-color:var(--g,#76b900)}
      .chatui-send{background:var(--g,#76b900);color:#0a0a0a;border:0;border-radius:8px;padding:0 18px;font-weight:700;font-size:.85rem;cursor:pointer}
      .chatui-send:hover{background:var(--gs,#aee23a)}
      .chatui-send:disabled{opacity:.5;cursor:wait}
      .chatui-send.stop{background:var(--err);color:#fff}.chatui-send.stop:hover{background:var(--err);filter:brightness(1.1)}`;
  document.head.appendChild(s);
}

export function mountChatUI(container, opts = {}) {
  /* @doc <code>helpers.mountChatUI(el, opts)</code> ::
       Render a live, observable chat artifact (controls + streaming transcript + input) into
       <code>el</code>. <code>opts</code>: <code>{ modules:[{id,title}], models:[{id,label}],
       intro, greeting, memory, respond(text, ctx), onReset() }</code>. With <code>memory:true</code>
       the widget keeps the conversation, shows a memory toggle (starts on), offers prior turns as
       <code>ctx.history</code> (empty while the toggle is off, so the same respond reads as a stateless
       function), and makes the edit button rewind the transcript to that turn. <code>respond</code> streams
       into <code>ctx.view</code>: <code>view.token(t)</code> (answer, rendered as markdown),
       <code>view.reasoning(t)</code> (a collapsible thinking trace), <code>view.tool(label,
       detail)</code> (a tool chip that expands to show <code>detail</code>),
       <code>view.usage({input, output})</code> (per-turn tokens + running context),
       <code>view.html(h)</code>, <code>view.error(msg)</code>. <code>ctx</code> has <code>{
       module, modules, model, thread, turn, history, memory }</code>, where <code>modules</code> is the
       array of pinned page ids (empty = auto) and <code>history</code> is the prior turns to prepend
       when memory is on. Returns <code>{ thread, reset(), ctx }</code>.
  */
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return null;
  // Markdown: load marked once (cached on window); render answers as HTML + hljs.
  if (!window.__markedP) window.__markedP = import("https://cdn.jsdelivr.net/npm/marked@14/+esm").then(m => m.marked || m.default).catch(() => null);
  let MARKED = null; window.__markedP.then(m => { MARKED = m; });
  const _sanitize = (html) => { const d = document.createElement("div"); d.innerHTML = html;
    d.querySelectorAll("script,iframe,style,object,embed,link,meta,form").forEach(n => n.remove());
    d.querySelectorAll("*").forEach(n => [...n.attributes].forEach(a => { if (/^on/i.test(a.name) || /javascript:/i.test(a.value)) n.removeAttribute(a.name); }));
    return d.innerHTML; };
  const renderMd = (elm, t) => { if (MARKED) { elm.innerHTML = _sanitize(MARKED.parse(t)); if (window.hljs) elm.querySelectorAll("pre code").forEach(b => { try { window.hljs.highlightElement(b); } catch (_) {} }); } else { elm.textContent = t; } };
  ensureChatStyles();
  const modules = opts.modules || [];
  const models  = opts.models || [];
  // Opt-in memory keeps completed turns in ctx.history and rewinds them on edit.
  const memoryEnabled = opts.memory === true;
  let memoryOn = memoryEnabled;
  const history = [];   // [{role,content}] of completed turns, surfaced as ctx.history while memory is on
  const memToggle = memoryEnabled
    ? `<button class="chatui-mem on" type="button" aria-pressed="true" title="When on, the model sees the whole conversation. Turn it off to watch it answer each message as a stateless function with no recall.">🧠 memory: on</button>`
    : "";
  const modelSel = models.length
    ? `<label>Model</label><select class="chatui-model">${models.map(m => `<option value="${escHtml(m.id)}">${escHtml(m.label || m.id)}</option>`).join("")}</select>` : "";
  const modChips = modules.length
    ? `<div class="chatui-mods"><label>Pages</label>${modules.map(m => `<button type="button" class="chatui-modchip" data-id="${escHtml(m.id)}" title="${escHtml(m.title || m.id)}">${escHtml(m.id)}</button>`).join("")}<span class="chatui-ctx" data-pinhint>none pinned = auto-select</span></div>` : "";
  el.innerHTML = `<div class="chatui${opts.growLog ? " chatui-grow" : ""}">
      <div class="chatui-bar">${modelSel}<span class="chatui-ctx chatui-ctxwrap" data-ctx hidden><span data-ctxtext></span><span class="chatui-ctxbar"><span class="chatui-ctxfill"></span></span></span><span class="sp"></span>${memToggle}<button class="chatui-reset" type="button">↺ New chat</button>${modChips}</div>
      <div class="chatui-log"></div>
      <div class="chatui-in"><textarea class="chatui-text" rows="1" placeholder="Ask a question…"></textarea><button class="chatui-send" type="button">Send</button></div>
    </div>`;

  const log = el.querySelector(".chatui-log");
  const text = el.querySelector(".chatui-text");
  const sendBtn = el.querySelector(".chatui-send");
  const resetBtn = el.querySelector(".chatui-reset");
  const modelEl = el.querySelector(".chatui-model");
  const ctxEl = el.querySelector("[data-ctx]");
  const chips = [...el.querySelectorAll(".chatui-modchip")];
  chips.forEach(c => c.addEventListener("click", () => c.classList.toggle("on")));
  const memBtn = el.querySelector(".chatui-mem");
  if (memBtn) memBtn.addEventListener("click", () => {
    memoryOn = !memoryOn;
    memBtn.classList.toggle("on", memoryOn);
    memBtn.setAttribute("aria-pressed", String(memoryOn));
    memBtn.textContent = "🧠 memory: " + (memoryOn ? "on" : "off");
  });
  const selectedModules = () => chips.filter(c => c.classList.contains("on")).map(c => c.dataset.id);
  const ctx = { thread: "chat-" + Math.random().toString(36).slice(2, 9), turn: 0, _ctx: 0,
                get modules() { return selectedModules(); },
                get module() { const s = selectedModules(); return s[0] || "auto"; },   // back-compat
                get model()  { return modelEl ? modelEl.value : (models[0] && models[0].id) || null; },
                get window() { return contextWindow(ctx.model); },
                // Prior turns for respond; empty when memory is off.
                get history() { return (memoryEnabled && memoryOn) ? history.map(m => ({ ...m })) : []; },
                get memory()  { return memoryEnabled && memoryOn; } };

  const ctxText = el.querySelector("[data-ctxtext]");
  const ctxFill = el.querySelector(".chatui-ctxfill");
  const ctxBar  = el.querySelector(".chatui-ctxbar");
  const k = (n) => n >= 1000 ? (n / 1000).toFixed(n >= 100000 ? 0 : 1) + "k" : String(n);
  // The context-budget readout in the bar.
  // A known window (a course model in CONTEXT_WINDOWS) shows percent full, red past 90%.
  // An unknown window (such as the OpenClaw gateway's own model) shows the absolute count.
  const setBudget = (used, model, winOverride) => {
    const win = winOverride || CONTEXT_WINDOWS[model || ctx.model]; ctx._ctx = used;
    if (!ctxEl) return;
    if (!used) { ctxEl.hidden = true; return; }
    ctxEl.hidden = false;
    if (win) {
      const pct = Math.min(100, Math.round((used / win) * 100));
      ctxText.textContent = "context " + k(used) + " / " + k(win) + " (" + pct + "%)";
      ctxBar.style.display = ""; ctxFill.style.width = pct + "%";
      ctxEl.classList.toggle("warn", pct >= 90);
    } else {
      ctxText.textContent = "context " + k(used) + " tok";
      ctxBar.style.display = "none"; ctxEl.classList.remove("warn");
    }
  };
  if (opts.intro) { const i = document.createElement("div"); i.className = "chatui-intro"; i.textContent = opts.intro; log.appendChild(i); }
  if (opts.greeting) { const g = document.createElement("div"); g.className = "chatui-msg chatui-bot"; g.textContent = opts.greeting; log.appendChild(g); }
  const scroll = () => { log.scrollTop = log.scrollHeight; };
  const bubble = (cls, txt) => { const d = document.createElement("div"); d.className = "chatui-msg " + cls; if (txt != null) d.textContent = txt; log.appendChild(d); scroll(); return d; };
  // A control row under a message. It can copy the text.
  // The student's own messages also get edit-and-requeue.
  // That drops the text back in the box to tweak and resend.
  const addMsgControls = (side, getText, editable, editHandler) => {
    const row = document.createElement("div"); row.className = "chatui-msgctl " + side;
    const copy = document.createElement("button"); copy.type = "button"; copy.textContent = "⎘ copy";
    copy.addEventListener("click", () => { navigator.clipboard.writeText(getText() || "").then(() => { copy.textContent = "copied ✓"; setTimeout(() => { copy.textContent = "⎘ copy"; }, 1200); }).catch(() => {}); });
    row.appendChild(copy);
    if (editable) {
      const edit = document.createElement("button"); edit.type = "button";
      // With memory, edit rewinds here; otherwise it just requeues text.
      edit.textContent = editHandler ? "✎ edit · rewind here" : "✎ edit & requeue";
      edit.addEventListener("click", () => {
        if (running) return;
        if (editHandler) editHandler();          // truncate transcript + memory back to this turn, refill the box
        else text.value = getText() || "";
        text.style.height = "auto"; text.style.height = Math.min(text.scrollHeight, 120) + "px"; text.focus();
      });
      row.appendChild(edit);
    }
    log.appendChild(row); scroll(); return row;
  };
  // Remove a node and every node after it in the log (used to rewind the transcript on edit).
  const removeFrom = (node) => { let n = node; while (n) { const nx = n.nextSibling; n.remove(); n = nx; } };
  // Clickable starter prompts that invite a real first interaction.
  // One click fills the box, and the student can edit it before sending.
  const addExamples = () => { if (!opts.examples || !opts.examples.length) return;
    const ex = document.createElement("div"); ex.className = "chatui-examples";
    opts.examples.forEach(s => { const b = document.createElement("button"); b.type = "button"; b.className = "chatui-ex"; b.textContent = s;
      b.addEventListener("click", () => { text.value = s; text.style.height = "auto"; text.style.height = Math.min(text.scrollHeight, 120) + "px"; text.focus(); });
      ex.appendChild(b); });
    log.appendChild(ex); };
  addExamples();

  let running = false, curAC = null;
  async function send() {
    const q = text.value.trim();
    if (!q || running) return;
    const histMark = history.length, turnMark = ctx.turn;   // where "edit · rewind here" rolls back to
    text.value = ""; text.style.height = "auto";
    const userBub = bubble("chatui-user", q);
    // Memory edit drops later turns and restarts from this message.
    const editHandler = memoryEnabled ? () => {
      removeFrom(userBub);
      history.length = Math.min(history.length, histMark);
      ctx.turn = turnMark;
      setBudget(0);
      text.value = q;
    } : null;
    addMsgControls("user", () => q, true, editHandler);   // copy + edit (rewind, or plain requeue)
    // One container per turn, with no fixed slots and no reordering.
    // Reasoning, tool, and answer blocks are appended in the order they stream.
    // The transcript reads exactly as the agent ran: reason, act, observe, answer.
    const turn = document.createElement("div"); turn.className = "chatui-turn chatui-cursor";
    log.appendChild(turn); scroll();
    // The Send button becomes a Stop button for the duration of the turn.
    // Its AbortController is handed to respond as ctx.signal.
    // A long agent or gateway run can then be cancelled instead of waited out.
    running = true; curAC = new AbortController();
    sendBtn.textContent = "⏹ Stop"; sendBtn.classList.add("stop");
    let cur = null;         // the currently-open streaming block: {kind, el, body?, _t, _raf}
    let answered = false, errored = false;
    // Per ReAct round the reasoning trace and the answer each live in ONE reused block.
    // Reuse keeps a stray content token interleaved mid-reasoning from splitting the trace.
    // A tool call, warn, or note ends the round; the next reasoning opens a fresh block.
    let roundThink = null, roundAnswer = null;
    // A reasoning block stays open while it streams, then folds shut.
    // The fold happens once the agent advances to its next act or answer, and it stays expandable.
    const endThink = () => { if (cur && cur.kind === "think") { cur.el.open = false;
      const s = cur.el.querySelector("summary"); if (s) s.textContent = "🧠 reasoning · ~" + estimateTokens(cur._t) + " tok"; } };
    const newThink = () => { const d = document.createElement("details"); d.className = "chatui-think"; d.open = true;
      d.innerHTML = '<summary>🧠 reasoning</summary><div class="chatui-think-body"></div>';
      turn.appendChild(d); cur = { kind: "think", el: d, body: d.querySelector(".chatui-think-body"), _t: "" }; return cur; };
    const newAnswer = () => { endThink(); const d = document.createElement("div"); d.className = "chatui-msg chatui-bot";
      turn.appendChild(d); cur = { kind: "answer", el: d, _t: "", _raf: 0 }; answered = true; return cur; };
    const flush = () => { if (cur && cur.kind === "answer") { if (cur._raf) { cancelAnimationFrame(cur._raf); cur._raf = 0; } renderMd(cur.el, cur._t); } };
    const view = {
      reasoning(t) {
        if (!roundThink) { newThink(); roundThink = cur; }
        else if (cur !== roundThink) { cur = roundThink; cur.el.open = true; }   // reasoning resumed after a stray token
        cur._t += t; cur.body.textContent = cur._t; scroll(); },
      token(t) {
        if (cur && cur.kind === "think") endThink();         // fold the reasoning before the answer renders
        if (!roundAnswer) { newAnswer(); roundAnswer = cur; }
        else if (cur !== roundAnswer) { cur = roundAnswer; }
        const c = cur; c._t += t;
        if (!c._raf) c._raf = requestAnimationFrame(() => { c._raf = 0; renderMd(c.el, c._t); scroll(); }); },
      // A tool call closes the current streaming block and appends its own.
      // A read that happens after some reasoning therefore renders below it.
      tool(label, detail) { endThink(); flush(); cur = null; roundThink = null; roundAnswer = null; let c;
        if (detail != null) { c = document.createElement("details"); c.className = "chatui-tool";
          c.innerHTML = "<summary>🔧 " + escHtml(String(label)) + "</summary>";
          const b = document.createElement("div"); b.className = "chatui-tool-body";
          if (typeof detail === "object") {
            // Object payloads (tool args, results, gateway frames) render as syntax-highlighted JSON.
            // The student sees the exact structure rather than "[object Object]" or a flat string.
            const pre = document.createElement("pre"); pre.style.cssText = "margin:0;overflow:auto;max-height:340px";
            const code = document.createElement("code"); code.className = "language-json";
            code.textContent = JSON.stringify(detail, null, 2); pre.appendChild(code); b.appendChild(pre);
            if (window.hljs) { try { window.hljs.highlightElement(code); } catch (_) {} }
          } else { b.textContent = String(detail); }
          c.appendChild(b);
        } else { c = document.createElement("div"); c.className = "chatui-tool"; c.textContent = "🔧 " + label; }
        turn.appendChild(c); scroll(); return c; },
      warn(msg) { endThink(); flush(); cur = null; roundThink = null; roundAnswer = null; const d = document.createElement("div"); d.className = "chatui-warn"; d.textContent = "⚠ " + msg; turn.appendChild(d); scroll(); return d; },
      note(msg) { flush(); cur = null; roundThink = null; roundAnswer = null; const d = document.createElement("div"); d.className = "chatui-usage"; d.textContent = msg; turn.appendChild(d); scroll(); return d; },
      usage(u) { u = u || {};
        const f = document.createElement("div"); f.className = "chatui-usage";
        if (u.context != null) {            // absolute context size + (optionally) the source's own window
          const win = u.window || CONTEXT_WINDOWS[u.model || ctx.model];
          f.textContent = "context " + u.context + (win ? " / " + win : "") + " tok" + (u.model ? " · " + u.model : "");
          setBudget(u.context, u.model, u.window);
        } else {
          const total = (u.input || 0) + (u.output || 0);
          const win = CONTEXT_WINDOWS[u.model || ctx.model];
          f.textContent = "↑ " + (u.input || 0) + " in · ↓ " + (u.output || 0) + " out" + (total ? " · context " + total + " tok" + (win ? " of " + win : "") : "");
          if (total) setBudget(total, u.model);   // bar matches the footer's context total
        }
        turn.appendChild(f); scroll(); },
      html(h) { endThink(); flush(); cur = null; const d = document.createElement("div"); d.className = "chatui-viz"; turn.appendChild(d); d.innerHTML = h; scroll(); return d; },
      error(msg) { errored = true; flush(); cur = null; const d = document.createElement("div"); d.className = "chatui-msg chatui-bot err"; d.textContent = "⚠ " + msg; turn.appendChild(d); scroll(); },
    };

    try { await opts.respond(q, { module: ctx.module, modules: ctx.modules, model: ctx.model, thread: ctx.thread, turn: ctx.turn, window: ctx.window, history: ctx.history, memory: ctx.memory, signal: curAC.signal, view }); }
    catch (e) { if (!curAC.signal.aborted) view.error(e && e.message ? e.message : String(e)); }
    finally {
      flush(); endThink();
      turn.classList.remove("chatui-cursor");
      if (curAC.signal.aborted) view.note("⏹ stopped");
      else if (!answered && !errored) { const d = document.createElement("div"); d.className = "chatui-msg chatui-bot"; d.textContent = "(no answer)"; turn.appendChild(d); }
      addMsgControls("bot", () => (roundAnswer && roundAnswer._t) || turn.innerText || "", false);   // copy the reply
      // Record the completed turn so ctx.history can carry it into the next call while memory is on.
      if (memoryEnabled && !curAC.signal.aborted && !errored)
        history.push({ role: "user", content: q }, { role: "assistant", content: (roundAnswer && roundAnswer._t) || "" });
      running = false; curAC = null;
      sendBtn.textContent = "Send"; sendBtn.classList.remove("stop");
      ctx.turn++; text.focus();
    }
  }

  sendBtn.addEventListener("click", () => { if (running) { try { curAC.abort(); } catch (_) {} } else send(); });
  text.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!running) send(); } });
  text.addEventListener("input", () => { text.style.height = "auto"; text.style.height = Math.min(text.scrollHeight, 120) + "px"; });
  function reset() {
    if (curAC) { try { curAC.abort(); } catch (_) {} }
    log.querySelectorAll(".chatui-msg, .chatui-turn, .chatui-examples, .chatui-msgctl").forEach(n => n.remove());
    if (opts.greeting) bubble("chatui-bot", opts.greeting);
    addExamples();
    ctx.thread = "chat-" + Math.random().toString(36).slice(2, 9); ctx.turn = 0; setBudget(0);
    history.length = 0;
    if (opts.onReset) try { opts.onReset(ctx); } catch (_) {}
  }
  resetBtn.addEventListener("click", reset);
  return { thread: ctx.thread, reset, ctx };
}

// Mount a live chat artifact backed by LangChain's createReactAgent.
// It handles the CDN load, one agent per model with its own MemorySaver, token and tool streaming, and the no-key guard.
// A page therefore only declares its tools and prompt.
export async function mountAgentChat(container, opts = {}) {
  /* @doc <code>helpers.mountAgentChat(el, opts)</code> ::
       Live chat artifact on LangChain <code>createReactAgent</code>. <code>opts</code>: <code>{
       models:[{id,label}], system,
       buildTools({tool,z,coursePage,coursePages,webSearch,formatSearchResults}), greeting,
       modules, recursionLimit, growLog }</code>. <code>growLog:true</code> drops the panel's internal
       scroll caps so a long transcript flows with the page instead of trapping the wheel. Loads LangChain from a CDN, builds one agent per model
       (MemorySaver for multi-turn), streams tokens + tool chips, guards the missing key. The
       off-the-shelf companion to <code>mountChatUI</code>.
  */
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return null;
  let LC = null;
  async function deps() {
    if (!LC) {
      const [oai, core, prebuilt, lg, zod] = await Promise.all([
        import("https://cdn.jsdelivr.net/npm/@langchain/openai@1.4.7/+esm"),
        import("https://cdn.jsdelivr.net/npm/@langchain/core@1.1.48/tools/+esm"),
        import("https://cdn.jsdelivr.net/npm/@langchain/langgraph@1/prebuilt/+esm"),
        import("https://cdn.jsdelivr.net/npm/@langchain/langgraph@1/+esm"),
        import("https://cdn.jsdelivr.net/npm/zod@3/+esm"),
      ]);
      LC = { ChatOpenAI: oai.ChatOpenAI, tool: core.tool, createReactAgent: prebuilt.createReactAgent, MemorySaver: lg.MemorySaver, z: zod.z };
    }
    return LC;
  }
  const agents = {};
  async function getAgent(model) {
    if (!agents[model]) {
      const d = await deps();
      const cfg = await getConfig();
      const baseURL = cfg.url.startsWith("http") ? cfg.url : (window.location.origin + cfg.url);
      // The OpenAI SDK adds x-stainless-* platform headers that the CORS proxy rejects in preflights.
      // Strip them with a custom fetch wrapper.
      const _fetchNoStainless = (url, init) => {
        if (init && init.headers) {
          const h = init.headers instanceof Headers ? init.headers : new Headers(init.headers);
          for (const k of [...h.keys()]) { if (k.startsWith("x-stainless")) h.delete(k); }
          init = { ...init, headers: h };
        }
        return fetch(url, init);
      };
      const llm = new d.ChatOpenAI({ configuration: { baseURL, dangerouslyAllowBrowser: true,
        fetch: _fetchNoStainless },
        apiKey: cfg.needsKey ? getKey() : "no-key-needed", model, temperature: 0, maxTokens: 16384 });
      const tools = opts.buildTools
        ? opts.buildTools({ tool: d.tool, z: d.z, coursePage, coursePages, webSearch, formatSearchResults }) : [];
      agents[model] = d.createReactAgent({ llm, tools, checkpointer: new d.MemorySaver() });
    }
    return agents[model];
  }
  return mountChatUI(el, {
    modules: opts.modules, models: opts.models, intro: opts.intro, greeting: opts.greeting, examples: opts.examples, growLog: opts.growLog,
    respond: async (text, ctx) => {
      const cfg = await getConfig();
      if (cfg.needsKey && !getKey()) { ctx.view.error("Add your nvapi- key on the course home, then chat."); return; }
      const agent = await getAgent(ctx.model);
      const messages = [];
      if (ctx.turn === 0 && opts.system) messages.push({ role: "system", content: typeof opts.system === "function" ? opts.system(ctx) : opts.system });
      // Pin one or more course pages chosen via the "Pages" chips, on turn 0 only.
      // Later turns reuse the thread's checkpointed context, so they skip this.
      // The whole page is pinned and shown in the chip, so nothing is clipped.
      if (ctx.turn === 0 && opts.modules) {
        for (const id of (ctx.modules || [])) {
          const body = await coursePage(id);
          ctx.view.tool("pinned " + id + " · " + estimateTokens(body) + " tok", body);
          messages.push({ role: "system", content: "Pinned course page (" + id + "):\n\n" + body });
        }
      }
      messages.push({ role: "user", content: text });
      // Pre-flight context-budget check, run on turn 0 only.
      // It warns before the call when the prompt alone would overflow the window, rather than letting the endpoint drop tokens silently.
      // Later turns live in the checkpointed thread.
      if (ctx.turn === 0) {
        const est = estimateTokens(messages);
        if (est > ctx.window) ctx.view.warn("This prompt is ~" + est + " tokens but " + ctx.model + " holds ~" + ctx.window + ". Unpin a page or split the question.");
      }
      const stream = await agent.stream({ messages },
        { streamMode: "messages", configurable: { thread_id: ctx.thread }, recursionLimit: opts.recursionLimit || 12, signal: ctx.signal });
      // Every tool call pushes its own chip in call order, and a chip is never reused.
      // Chips are keyed by the tool call's unique id, not by index.
      // Arg-delta chunks reset their index to 0 each model message, so an index key would let a later read overwrite an earlier one.
      const byId = {}, activeByIndex = {};
      let lastInput = 0, totalOutput = 0, sawUsage = false;
      const labelFor = (name, args) => {
        let a = ""; try { const o = JSON.parse(args || "{}"); a = o.page || o.id || o.query || o.expression || Object.values(o)[0] || ""; } catch (_) {}
        return a ? name + " · " + a : name;
      };
      const markErr = (c) => { if (c && c.el) { c.el.classList.add("err"); if (c.sumEl && !/^✗/.test(c.sumEl.textContent)) c.sumEl.textContent = "✗ " + c.sumEl.textContent.replace(/^🔧 /, ""); } };
      for await (const part of stream) {
        const chunk = Array.isArray(part) ? part[0] : part;
        const meta  = Array.isArray(part) ? part[1] : null;
        const node  = meta && meta.langgraph_node;
        // tool RESULT messages arrive on the "tools" node.
        // Fill the matching chip's body with the full text the tool returned (no clipping).
        // If the tool errored, mark the chip so the failure is shown, not hidden.
        if (node === "tools" && chunk.tool_call_id && byId[chunk.tool_call_id]) {
          const c = byId[chunk.tool_call_id];
          c.result = (c.result || "") + (typeof chunk.content === "string" ? chunk.content : JSON.stringify(chunk.content));
          if (c.bodyEl) c.bodyEl.textContent = c.result;
          if (chunk.status === "error" || /^\(unknown page|→ \d{3}$/.test(c.result.trim())) markErr(c);
          continue;
        }
        for (const tc of (chunk.tool_call_chunks || [])) {
          const idx = tc.index == null ? 0 : tc.index;
          let c;
          if (tc.id) {   // first chunk of a NEW call → push a fresh chip
            c = { name: tc.name || "tool", args: "" };
            c.el = ctx.view.tool((tc.name || "tool") + " …", "(running)");
            c.bodyEl = c.el.querySelector(".chatui-tool-body");
            c.sumEl = c.el.querySelector("summary");
            byId[tc.id] = c; activeByIndex[idx] = c;
          } else { c = activeByIndex[idx]; }   // arg-delta → the call open at this index
          if (!c) continue;
          if (tc.name) c.name = tc.name;
          c.args += (tc.args || "");
          if (c.sumEl) c.sumEl.textContent = "🔧 " + labelFor(c.name, c.args);
        }
        // reasoning deltas (nemotron exposes them on additional_kwargs)
        const rc = chunk.additional_kwargs && (chunk.additional_kwargs.reasoning_content || chunk.additional_kwargs.reasoning);
        if (rc && node === "agent") ctx.view.reasoning(typeof rc === "string" ? rc : String(rc));
        if (chunk.usage_metadata) { sawUsage = true; lastInput = chunk.usage_metadata.input_tokens || lastInput; totalOutput += chunk.usage_metadata.output_tokens || 0; }
        if (typeof chunk.content === "string" && chunk.content && node === "agent")
          ctx.view.token(chunk.content);
      }
      if (sawUsage) ctx.view.usage({ input: lastInput, output: totalOutput });
    },
    onReset: opts.onReset,
  });
}

// Reusable terminal-like console with history, suggestions, completion, and output hooks.
export function mountConsole(container, { prompt = "$", greeting = "", suggestions = [], onSubmit, disabled = false, disabledMsg = "" } = {}) {
  const root = typeof container === "string" ? document.querySelector(container) : container;
  if (!root) return null;
  const id = "dl" + Math.random().toString(36).slice(2, 8);
  const opts = (suggestions || []).map(s => '<option value="' + String(s).replace(/"/g, "&quot;") + '"></option>').join("");
  root.innerHTML =
    '<div class="da-term">' +
      '<div class="da-out"></div>' +
      '<div class="da-line"><span class="da-ps">' + prompt + '</span>' +
        '<input class="da-in" list="' + id + '" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="console input"/>' +
        '<datalist id="' + id + '">' + opts + '</datalist>' +
      '</div>' +
      '<div class="da-chips"></div>' +
    '</div>';
  const out = root.querySelector(".da-out");
  const input = root.querySelector(".da-in");
  const chipRow = root.querySelector(".da-chips");
  const con = {
    write(text, cls) { const d = document.createElement("div"); if (cls) d.className = cls; d.textContent = (text == null ? "" : String(text)); out.appendChild(d); },
    raw(text) { if (text == null || text === "") return; out.appendChild(document.createTextNode(String(text))); },
    clear() { out.innerHTML = ""; },
  };
  root.addEventListener("click", e => { if (e.target.tagName !== "BUTTON" && e.target.tagName !== "INPUT") input.focus(); });
  if (disabled) { if (disabledMsg) con.write(disabledMsg, "da-dim"); input.disabled = true; return con; }
  (suggestions || []).forEach(s => {
    const b = document.createElement("button"); b.type = "button"; b.className = "da-chip"; b.textContent = s;
    b.addEventListener("click", () => { input.value = s; input.focus(); });
    chipRow.appendChild(b);
  });
  if (greeting) con.write(greeting, "da-dim");
  const hist = []; let hi = 0;
  input.addEventListener("keydown", async e => {
    if (e.key === "Enter") {
      const line = input.value.trim(); input.value = "";
      con.write(prompt + " " + line, "da-cmd");
      if (!line) return;
      hist.push(line); hi = hist.length;
      input.disabled = true;
      try { if (onSubmit) await onSubmit(line, con); } catch (err) { con.write("error: " + ((err && err.message) || err), "da-err"); }
      input.disabled = false; input.focus(); input.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Tab") {
      const v = input.value.toLowerCase();
      const hit = (suggestions || []).find(s => s.toLowerCase().startsWith(v) && s.toLowerCase() !== v);
      if (v && hit) { input.value = hit; e.preventDefault(); }
    } else if (e.key === "ArrowUp") { if (hi > 0) { hi--; input.value = hist[hi] || ""; } e.preventDefault(); }
    else if (e.key === "ArrowDown") { if (hi < hist.length) { hi++; input.value = hist[hi] || ""; } e.preventDefault(); }
  });
  return con;
}
