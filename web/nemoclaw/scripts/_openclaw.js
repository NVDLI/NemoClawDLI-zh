// OpenClaw gateway + claw widgets for 03a/03b/03c/04a.
// Holds the live WebSocket gateway client and the connect/probe widgets.
// Also openclawChat, GW_CONNECT, and the recover flow.

import { updateClawPill, escHtml, _escAttr, mountCanvasFlow } from "./_shared.js";

// ── ClawGateway widget ───────────────────────────────────────────────────────
// Live WebSocket client to wss://rawUrl/cli/gateway, reading URL + token from localStorage.
// The browser CF_Authorization cookie covers Cloudflare Access, so no proxy hop is needed.
export function mountClawGateway(targetSel, opts = {}) {
  const target = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!target) return;

  const label      = opts.label      || "OpenClaw Gateway";
  const intro      = opts.intro      !== undefined ? opts.intro : "";
  const actions    = opts.actions    || [];
  const sessionKey = opts.sessionKey || "agent:main:main";
  const autoConnect = !!opts.autoConnect;

  // Credentials from localStorage (written by mountClawProbe syncCanvas:true).
  // The raw URL key builds the WS URL against the actual launchable.
  // _CLAWPROBE_KEY_URL holds the CF CORS proxy, which is wrong for WS.
  function _creds() {
    return {
      rawUrl: localStorage.getItem(_CLAWPROBE_KEY_RAW_URL) ||
              localStorage.getItem(_CLAWPROBE_KEY_URL)     || "",
      token:  localStorage.getItem(_CLAWPROBE_KEY_TOKEN)   || "",
    };
  }

  // Build WS gateway URL directly with no proxy; browser sends CF cookie for CF Access
  function _wsUrl(rawUrl) {
    if (!rawUrl) return null;
    const base = rawUrl.replace(/\/+$/, "").replace(/^https/, "wss").replace(/^http(?!s)/, "ws");
    return base + "/cli/gateway";
  }

  // ── WS state ────────────────────────────────────────────────────────────────
  let _ws      = null;
  let _pending = {};    // id → {resolve, reject, timeout}
  let _chatCb  = null;  // called with each agent/chat event during a chat.send

  function _send(obj) {
    if (_ws && _ws.readyState === WebSocket.OPEN) _ws.send(JSON.stringify(obj));
  }

  function _call(method, params) {
    return new Promise((resolve, reject) => {
      const id = Math.random().toString(36).slice(2) + Date.now().toString(36);
      const tmo = setTimeout(() => {
        delete _pending[id];
        reject(new Error(`${method} timed out`));
      }, 20000);
      _pending[id] = { resolve, reject, tmo };
      _send({ type: "req", id, method, params: params || {} });
    });
  }

  function _connectWs(wsUrl, token) {
    return new Promise((resolve, reject) => {
      if (_ws) { try { _ws.close(); } catch (_) {} }
      _ws = new WebSocket(wsUrl);
      let _connId = null;

      _ws.onopen = () => {};

      _ws.onmessage = ev => {
        let d;
        try { d = JSON.parse(ev.data); } catch (_) { return; }
        const evt = d.event || "";
        const mid = d.id    || "";
        const typ = d.type  || "";

        if (evt === "connect.challenge") {
          _connId = Math.random().toString(36).slice(2) + Date.now().toString(36);
          // Resolve the outer promise on connect response
          _pending[_connId] = {
            resolve: r => {
              clearTimeout(_pending[_connId]?.tmo);
              delete _pending[_connId];
              const scopes  = r?.payload?.auth?.scopes  || [];
              const version = r?.payload?.server?.version || "?";
              resolve({ scopes, version });
              // auto-subscribe to the default session
              _call("sessions.messages.subscribe", { key: sessionKey }).catch(() => {});
            },
            reject: e => {
              clearTimeout(_pending[_connId]?.tmo);
              delete _pending[_connId];
              reject(e);
            },
            tmo: setTimeout(() => reject(new Error("connect timeout")), 15000),
          };
          _ws.send(JSON.stringify({
            type: "req", id: _connId, method: "connect",
            params: {
              minProtocol: 4, maxProtocol: 4,
              client: { id: "openclaw-control-ui", version: "0.1.0", platform: "browser", mode: "webchat" },
              caps: ["tool-events"], role: "operator",
              scopes: ["operator.read", "operator.write", "operator.admin"],
              auth: { token },
            },
          }));
          return;
        }

        // Resolve pending calls
        if (typ === "res" && mid && _pending[mid]) {
          const p = _pending[mid];
          clearTimeout(p.tmo);
          delete _pending[mid];
          if (d.ok) p.resolve(d); else p.reject(new Error(d.error?.message || "gateway error"));
          return;
        }

        // Route agent/chat events to active chat handler
        if (typ === "event" && _chatCb && (evt === "chat" || evt === "agent")) {
          _chatCb(d);
        }
      };

      _ws.onerror = () => reject(new Error("WebSocket error. Check that the URL is correct and the launchable is running."));
      _ws.onclose = () => {
        _setStatus("disconnected");
        _setActions(false);
        Object.values(_pending).forEach(p => { clearTimeout(p.tmo); p.reject(new Error("connection closed")); });
        _pending = {};
      };
    });
  }

  // ── DOM ─────────────────────────────────────────────────────────────────────
  target.innerHTML = `
<div class="claw-probe gw-panel">
  ${intro ? `<div class="gw-intro">${intro}</div>` : ""}
  <div class="claw-label">${label}</div>
  <div class="gw-head">
    <span class="gw-status gw-disc">● disconnected</span>
    <button type="button" class="claw-btn alt gw-connect-btn">Connect</button>
  </div>
  <div class="gw-actions" hidden>
    ${actions.map((a, i) =>
      `<button type="button" class="claw-btn${a.primary ? "" : " alt"} gw-act" data-i="${i}">${a.label}</button>`
    ).join("")}
  </div>
  <div class="gw-out" hidden></div>
</div>`;

  const statusEl  = target.querySelector(".gw-status");
  const connectBtn = target.querySelector(".gw-connect-btn");
  const actionsEl  = target.querySelector(".gw-actions");
  const outEl      = target.querySelector(".gw-out");

  function _setStatus(state, detail) {
    const map = {
      connecting:   ["● connecting…",   "gw-conn"],
      connected:    ["● connected",     "gw-live"],
      disconnected: ["● disconnected",  "gw-disc"],
      error:        ["● error",         "gw-err"],
    };
    const [txt, cls] = map[state] || map.disconnected;
    statusEl.textContent = detail ? `${txt} · ${detail}` : txt;
    statusEl.className   = `gw-status ${cls}`;
  }

  function _setActions(en) {
    actionsEl.hidden = !en;
  }

  function _showOut(html) {
    outEl.hidden  = false;
    outEl.innerHTML = html;
  }

  function _showPre(text) {
    _showOut(`<pre class="gw-pre">${text.replace(/</g,"&lt;")}</pre>`);
  }

  // ── Connect ──────────────────────────────────────────────────────────────────
  connectBtn.addEventListener("click", async () => {
    const { rawUrl, token } = _creds();
    if (!rawUrl || !token) {
      _showOut(`<span class="gw-err-txt">No URL or token yet. Fill in the OpenClaw probe above and click an action first.</span>`);
      return;
    }
    const wsUrl = _wsUrl(rawUrl);
    _setStatus("connecting");
    connectBtn.disabled = true;
    outEl.hidden = true;
    try {
      const { scopes, version } = await _connectWs(wsUrl, token);
      _setStatus("connected", `v${version} · ${scopes.length} scopes`);
      _setActions(true);
      connectBtn.textContent = "Reconnect";
    } catch (e) {
      _setStatus("error", e.message.slice(0, 80));
      _showOut(`<span class="gw-err-txt">${e.message}</span>`);
    }
    connectBtn.disabled = false;
  });

  // ── Action buttons ────────────────────────────────────────────────────────
  actionsEl.querySelectorAll(".gw-act").forEach(btn => {
    const action = actions[parseInt(btn.dataset.i)];
    if (!action) return;

    btn.addEventListener("click", async () => {
      btn.disabled = true;
      outEl.hidden = true;

      try {
        if (action.chat) {
          // Streaming chat
          const ikey = Math.random().toString(36).slice(2) + Date.now().toString(36);
          let fullText = "";
          outEl.hidden  = false;
          outEl.innerHTML = `<div class="gw-chat-out"></div>`;
          const chatDiv = outEl.querySelector(".gw-chat-out");

          await new Promise((resolve, reject) => {
            _chatCb = d => {
              const evt = d.event || "";
              const pl  = d.payload || {};
              if (evt === "chat" && pl.state === "delta") {
                fullText = pl.message?.content?.[0]?.text || (fullText + (pl.deltaText || ""));
                chatDiv.textContent = fullText;
              } else if (evt === "agent" && pl.stream === "lifecycle" && pl.data?.phase === "end") {
                _chatCb = null;
                resolve();
              } else if (evt === "chat" && pl.state === "final") {
                fullText = pl.message?.content?.[0]?.text || fullText;
                chatDiv.textContent = fullText;
              }
            };
            const msg = typeof action.message === "function" ? action.message() : (action.message || "Hello");
            _call("chat.send", { sessionKey, idempotencyKey: ikey, message: msg })
              .catch(e => { _chatCb = null; reject(e); });
            // Safety timeout
            setTimeout(() => { _chatCb = null; resolve(); }, 60000);
          });
        } else {
          // Standard method call
          const params = typeof action.params === "function" ? action.params() : (action.params || {});
          const res = await _call(action.method, params);
          // Pretty-print selected payload shapes
          const pl = res.payload;
          if (action.format === "models" && pl?.models) {
            _showOut(`<table class="gw-table"><thead><tr><th>id</th><th>provider</th><th>ctx</th></tr></thead><tbody>${
              pl.models.map(m => `<tr><td>${m.id}</td><td>${m.provider}</td><td>${m.contextWindow||""}</td></tr>`).join("")
            }</tbody></table>`);
          } else if (action.format === "crons" && pl) {
            const jobs = pl.jobs || [];
            if (!jobs.length) {
              _showOut(`<span class="gw-muted">No cron jobs installed.</span>`);
            } else {
              _showOut(`<table class="gw-table"><thead><tr><th>id</th><th>schedule</th><th>prompt</th></tr></thead><tbody>${
                jobs.map(j => `<tr><td>${j.id}</td><td>${j.schedule}</td><td>${(j.prompt||"").slice(0,60)}</td></tr>`).join("")
              }</tbody></table>`);
            }
          } else {
            _showPre(JSON.stringify(pl, null, 2));
          }
        }
      } catch (e) {
        _showOut(`<span class="gw-err-txt">✗ ${e.message}</span>`);
      }
      btn.disabled = false;
    });
  });

  if (autoConnect) connectBtn.click();

  return { call: _call };
}

// ── ClawProbe widget ─────────────────────────────────────────────────────────
// Paste-your-URL surface for a base URL + bearer token (both saved in localStorage).
// Caller-supplied `fetch` actions print their responses; pages 3a/3b/3c/4a vary `actions`.
const _CLAWPROBE_KEY_URL     = "nemoclaw_clawurl";
const _CLAWPROBE_KEY_RAW_URL = "nemoclaw_clawrawurl"; // raw (pre-proxy) URL for WS
const _CLAWPROBE_KEY_TOKEN   = "nemoclaw_clawtoken";
const _CLAWPROBE_KEY_CFJWT   = "nemoclaw_clawcfjwt";

export function mountClawProbe(targetSel, opts = {}) {
  const target = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!target) return;

  const defaultUrl   = (opts.defaultUrl   || "/lab/openclaw").replace(/\/+$/, "");
  // Respect an explicit empty token from the no-bearer llm_client probe.
  // A bare `|| default` would turn "" into the openclaw token.
  // llm_client then forwards it upstream and the model backend rejects with a 400.
  const defaultToken = (opts.defaultToken !== undefined) ? opts.defaultToken : "dli-openclaw-token";
  // The placeholder follows the default, so a no-bearer probe shows "(none needed)".
  // That beats showing the misleading openclaw token in a field that takes none.
  // Callers can override with opts.tokenPlaceholder.
  const tokenPlaceholder = (opts.tokenPlaceholder !== undefined)
    ? opts.tokenPlaceholder
    : (defaultToken || "(none needed in your launchable)");
  const actions      = opts.actions || [];
  const label        = opts.label || "Live OpenClaw probe";
  const intro        = opts.intro !== undefined ? opts.intro : "Paste the base URL of a running OpenClaw service. Your launchable's proxy is the default; to reach a remote launchable, paste its URL (https://nemoclaw-<id>.brevlab.com) instead.";

  function _normalizeBaseUrl(raw) {
    const text = String(raw || "").trim();
    if (!text) return "";
    try {
      const u = new URL(text);
      u.hash = "";
      // Brev launchables are rooted at the origin. Trim pasted app paths like /chat?session=main.
      if (/\.brevlab\.com$/i.test(u.hostname)) return u.origin;
      return u.href.replace(/\/+$/, "");
    } catch (_) {
      return text.replace(/\/+$/, "");
    }
  }

  // Key saved url+token by base URL so probes for different services do not share auth.
  // Same-URL openclaw probes (3a/3b/3c) still share with each other.
  // llm_client and sandbox-admin keep their own key, so no token bleeds into llm_client.
  const _grp     = defaultUrl.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "default";
  // The openclaw probes keep the legacy key for the 3a/3b/3c mountCanvasFlow cells.
  // Those cells read it directly to share url+token; other services get a scoped key.
  const _shared  = (_grp === "lab_openclaw");
  const keyUrl   = _shared ? _CLAWPROBE_KEY_URL   : (_CLAWPROBE_KEY_URL   + ":" + _grp);
  const keyToken = _shared ? _CLAWPROBE_KEY_TOKEN : (_CLAWPROBE_KEY_TOKEN + ":" + _grp);
  // Strip any stale proxy prefix so the input always shows the raw target URL.
  // Earlier builds wrote the effective (proxied) URL into the probe's own slot.
  // Those values would get double-proxied on reload, so heal them here.
  const _storedUrl = localStorage.getItem(keyUrl);
  const _stripPb   = (opts.proxyBase || "").replace(/\/+$/, "");
  const _strippedUrl = (_stripPb && (opts.proxyMode || "origin") === "prefix" &&
                        _storedUrl && _storedUrl.startsWith(_stripPb + "/https/"))
    ? "https://" + _storedUrl.slice(_stripPb.length + "/https/".length)
    : _storedUrl;
  if (_strippedUrl !== _storedUrl && _strippedUrl)
    localStorage.setItem(keyUrl, _strippedUrl); // heal stale storage
  const savedUrl   = _normalizeBaseUrl(_strippedUrl || defaultUrl);
  let savedToken = localStorage.getItem(keyToken) || defaultToken;
  // A no-bearer probe must never inherit a stale openclaw token from before key scoping.
  // Blank it so llm_client sends no bearer.
  if (defaultToken === "" && savedToken === "dli-openclaw-token") savedToken = "";
  const keyCfJwt  = _CLAWPROBE_KEY_CFJWT + ":" + _grp;
  const savedCfJwt = opts.cfAccess ? (localStorage.getItem(keyCfJwt) || "") : "";

  // Label helper. A key with fieldHelp content renders a toggle button.
  // A key without it renders a plain label. Both match the .claw-lf sizing exactly.
  const _lbl = (key, text) => opts.fieldHelp?.[key]
    ? `<button type="button" class="claw-lf claw-help-trigger" data-field="${key}" aria-expanded="false">${text}</button>`
    : `<label class="claw-lf">${text}</label>`;
  // Help panel rendered immediately after its row (hidden by default).
  const _hlp = (key) => {
    const h = opts.fieldHelp?.[key];
    return h ? `<div class="claw-help-panel" data-field="${key}" hidden role="region">${h}</div>` : "";
  };

  target.innerHTML = `
    <div class="claw-probe">
      <div class="claw-head">
        <div class="claw-label">${escHtml(label)}</div>
        ${intro ? `<div class="claw-intro">${escHtml(intro)}</div>` : ""}
      </div>
      <div class="claw-row">
        ${_lbl("url", "Base URL")}
        <input class="claw-input claw-url" type="text" spellcheck="false" autocapitalize="off"
               placeholder="https://your-tunnel.example.com" value="${_escAttr(savedUrl)}"/>
      </div>
      ${_hlp("url")}
      <div class="claw-row">
        ${_lbl("token", "Bearer token")}
        <input class="claw-input claw-token" type="password" spellcheck="false" autocapitalize="off"
               placeholder="${_escAttr(tokenPlaceholder)}" value="${_escAttr(savedToken)}"/>
        <button type="button" class="claw-btn alt claw-eye" title="Show token" aria-label="Show or hide token">👁</button>
      </div>
      ${_hlp("token")}
      ${opts.cfAccess ? `
      <div class="claw-row">
        ${_lbl("cfJwt", "CF Access JWT")}
        <input class="claw-input claw-cfjwt" type="password" spellcheck="false" autocapitalize="off"
               placeholder="paste CF_Authorization value from DevTools → Application → Cookies"
               value="${_escAttr(savedCfJwt)}"/>
        <button type="button" class="claw-btn alt claw-eye claw-eye-jwt" title="Show JWT" aria-label="Show or hide CF Access JWT">👁</button>
      </div>
      ${_hlp("cfJwt")}` : ""}
      <div class="claw-actions"></div>
      <pre class="claw-out" aria-live="polite"></pre>
    </div>
  `;

  // Inject the widget CSS once (idempotent, keyed off the marker class).
  if (!document.head.querySelector('style[data-claw-probe="1"]')) {
    const s = document.createElement("style");
    s.dataset.clawProbe = "1";
    s.textContent = `
      .claw-probe{border:1px solid var(--bd,#2a2a2a);border-radius:8px;background:var(--e1,#161616);padding:14px 16px;margin:1em 0}
      .claw-head{margin-bottom:.8em}
      .claw-label{font-weight:700;font-size:.95rem;color:var(--gs,#aee23a);margin-bottom:.2em}
      .claw-intro{font-size:.86rem;color:var(--td,#b0b0b0);line-height:1.5}
      .claw-row{display:flex;align-items:center;gap:8px;margin:.4em 0}
      .claw-lf{font-family:var(--mono,monospace);font-size:.75rem;color:var(--tf,#8a8a8a);width:96px;flex:0 0 96px;text-transform:uppercase;letter-spacing:.04em}
      .claw-input{flex:1;background:var(--e2,#1e1e1e);border:1px solid var(--bd,#2a2a2a);border-radius:5px;padding:7px 10px;color:var(--tx,#f2f2f2);font-family:var(--mono,monospace);font-size:.82rem;min-width:0}
      .claw-input:focus{outline:none;border-color:var(--g,#76b900)}
      .claw-actions{display:flex;flex-wrap:wrap;gap:6px;margin:.7em 0 .5em}
      .claw-btn{background:var(--g,#76b900);color:#000;border:0;border-radius:5px;padding:6px 14px;font-size:.82rem;font-weight:700;cursor:pointer;font-family:inherit}
      .claw-btn:hover{background:var(--gs,#aee23a)}
      .claw-btn:disabled{opacity:.5;cursor:wait}
      .claw-btn.alt{background:var(--e2,#1e1e1e);color:var(--gs,#aee23a);border:1px solid var(--bd,#2a2a2a)}
      .claw-btn.alt:hover{border-color:var(--g,#76b900)}
      .claw-eye{flex:0 0 auto;padding:5px 9px;font-size:.88rem;line-height:1}
      .claw-help-trigger{background:none;border:none;padding:0;cursor:pointer;text-align:left;width:96px;flex:0 0 96px;font-family:var(--mono,monospace);font-size:.75rem;color:var(--tf,#8a8a8a);text-transform:uppercase;letter-spacing:.04em;text-decoration:underline dotted;text-underline-offset:2px;line-height:inherit}
      .claw-help-trigger:hover,.claw-help-trigger[aria-expanded="true"]{color:var(--gs,#aee23a);text-decoration-style:solid}
      .claw-help-panel{padding:8px 12px 8px 104px;font-size:.82rem;line-height:1.65;color:var(--td,#b0b0b0);border-left:2px solid var(--bd,#2a2a2a);margin:.1em 0 .5em}
      .claw-help-panel p{margin:.3em 0}.claw-help-panel p:first-child{margin-top:0}.claw-help-panel p:last-child{margin-bottom:0}
      .claw-help-panel code{font-size:.88em;background:var(--e2,#0d0d0d);padding:1px 5px;border-radius:3px;color:var(--gs,#aee23a)}
      .claw-help-panel strong{color:var(--tx,#f2f2f2)}
      .claw-help-panel a{color:var(--gs,#aee23a)}
      .claw-out{background:var(--e2,#0d0d0d);border:1px solid var(--bd,#2a2a2a);border-radius:5px;padding:10px 12px;font-family:var(--mono,monospace);font-size:.78rem;line-height:1.5;color:var(--tx,#f2f2f2);min-height:60px;max-height:340px;overflow:auto;white-space:pre-wrap;word-break:break-word;margin:0}
      .claw-out.ok{border-color:var(--gd,#4a7a00)}
      .claw-out.err{border-color:var(--err,#a04040);color:var(--err,#ffb0b0)}
      .claw-html-frame{width:100%;height:340px;border:1px solid var(--bd,#2a2a2a);border-radius:5px;margin-top:.5em;background:#fff;display:block}
    `;
    document.head.appendChild(s);
  }

  const urlInp   = target.querySelector(".claw-url");
  const tokenInp = target.querySelector(".claw-token");
  const eyeBtn   = target.querySelector(".claw-eye");
  if (eyeBtn) {
    eyeBtn.addEventListener("click", () => {
      const showing = tokenInp.type !== "password";
      tokenInp.type = showing ? "password" : "text";
      eyeBtn.title  = showing ? "Show token" : "Hide token";
    });
  }
  // Wire help-panel toggles for any field that has a help entry.
  target.querySelectorAll(".claw-help-trigger").forEach(btn => {
    const panel = target.querySelector(`.claw-help-panel[data-field="${btn.dataset.field}"]`);
    if (!panel) return;
    btn.addEventListener("click", () => {
      const opening = panel.hidden;
      panel.hidden  = !opening;
      btn.setAttribute("aria-expanded", String(opening));
    });
  });

  const cfJwtInp  = opts.cfAccess ? target.querySelector(".claw-cfjwt")    : null;
  const eyeJwtBtn = opts.cfAccess ? target.querySelector(".claw-eye-jwt")   : null;
  if (eyeJwtBtn && cfJwtInp) {
    eyeJwtBtn.addEventListener("click", () => {
      const showing = cfJwtInp.type !== "password";
      cfJwtInp.type  = showing ? "password" : "text";
      eyeJwtBtn.title = showing ? "Show JWT" : "Hide JWT";
    });
  }
  if (cfJwtInp) {
    cfJwtInp.addEventListener("input", () => {
      localStorage.setItem(keyCfJwt, cfJwtInp.value.trim());
      _syncCanvasKeys(urlInp.value.trim(), tokenInp.value.trim(), cfJwtInp.value.trim());
    });
  }
  const outEl    = target.querySelector(".claw-out");
  const actBox   = target.querySelector(".claw-actions");

  // _syncCanvasKeys and _effectiveUrl read from opts directly, not the const aliases below.
  // That keeps them safe to call during mountClawProbe init, before those consts are reached.
  function _effectiveUrl(raw) {
    const pb = (opts.proxyBase || "").replace(/\/+$/, "");
    const pm = opts.proxyMode  || "origin";
    if (!pb || !raw) return raw;
    // Idempotent guard: already routed through this proxy → return as-is.
    if (raw.startsWith(pb + "/")) return raw;
    if (pm === "prefix") {
      // Encode as <proxyBase>/https/<host>/<path>, avoiding the `://` double-slash.
      // Cloudflare URL normalisation collapses that before the worker sees the request.
      // The worker rebuilds https:// from the scheme prefix; only HTTPS targets work.
      if (raw.startsWith("https://")) return pb + "/https/" + raw.slice("https://".length);
      return raw;
    }
    // "origin" mode: replace the scheme+host with proxyBase.
    try {
      const u = new URL(raw);
      return pb + u.pathname + u.search;
    } catch (_) { return raw; }
  }

  function _syncCanvasKeys(rawUrl, rawToken, rawCfJwt) {
    if (!opts.syncCanvas) return;
    localStorage.setItem(_CLAWPROBE_KEY_URL,     _effectiveUrl(rawUrl)); // proxy URL for fetch
    localStorage.setItem(_CLAWPROBE_KEY_RAW_URL, rawUrl);                // raw URL for WS
    localStorage.setItem(_CLAWPROBE_KEY_TOKEN,   rawToken);
    if (opts.cfAccess) localStorage.setItem(_CLAWPROBE_KEY_CFJWT, rawCfJwt || "");
    updateClawPill(document.getElementById("claw-status"));
  }

  urlInp.addEventListener("input", () => {
    const raw = _normalizeBaseUrl(urlInp.value);
    if (urlInp.value.trim() !== raw) urlInp.value = raw;
    localStorage.setItem(keyUrl, raw);
    _syncCanvasKeys(raw, tokenInp.value.trim(), cfJwtInp?.value.trim());
  });
  tokenInp.addEventListener("input", () => {
    const tok = tokenInp.value.trim();
    localStorage.setItem(keyToken, tok);
    _syncCanvasKeys(_normalizeBaseUrl(urlInp.value), tok, cfJwtInp?.value.trim());
  });
  // Initialise canvas keys on page load with whatever is already stored.
  _syncCanvasKeys(savedUrl, savedToken, savedCfJwt);

  function setOutput(text, kind = "") {
    outEl.classList.remove("ok", "err");
    if (kind) outEl.classList.add(kind);
    // Highlight the response with the course hljs theme when it looks like JSON.
    // Errors and non-JSON stay plain text, so a stack trace or status line reads as written.
    const t = (text || "").trim();
    const looksJson = kind !== "err" && (t.startsWith("{") || t.startsWith("["));
    if (looksJson && window.hljs) {
      try {
        outEl.innerHTML = "";
        const code = document.createElement("code");
        code.className = "language-json hljs";
        code.textContent = text;
        outEl.appendChild(code);
        window.hljs.highlightElement(code);
        return;
      } catch (_) { /* fall through to plain text */ }
    }
    outEl.textContent = text;
  }

  // Used by runAction to annotate the output line with "(via proxy)".
  const _proxyBase = (opts.proxyBase || "").replace(/\/+$/, "");

  function _fetchUrl(displayUrl) {
    return _effectiveUrl(displayUrl);
  }

  async function runAction(action) {
    const base = _normalizeBaseUrl(urlInp.value);
    if (urlInp.value.trim() !== base) urlInp.value = base;
    if (!base) { setOutput("Set a base URL above first.", "err"); return; }
    const token = (tokenInp.value || "").trim();
    const displayUrl = base + (action.path || "/");
    const fetchTarget = _fetchUrl(displayUrl);
    const method = action.method || "GET";
    let body = null;
    if (typeof action.body === "function") {
      try { body = action.body(); }
      catch (e) { setOutput("body() threw: " + (e?.message || e), "err"); return; }
    } else if (action.body) {
      body = action.body;
    }
    const cfJwt = cfJwtInp ? cfJwtInp.value.trim() : "";
    const headers = { "Accept": "application/json, text/html, */*" };
    if (token) headers["Authorization"]          = "Bearer " + token;
    if (cfJwt) headers["CF-Access-Jwt-Assertion"] = cfJwt;
    if (body)  headers["Content-Type"]            = "application/json";

    const showUrl = _proxyBase ? displayUrl + "  (via proxy)" : displayUrl;
    setOutput(`→ ${method} ${showUrl}\n   …in flight`);
    // Hide any previous HTML frame while a new request is in flight.
    const _htmlFrame = target.querySelector(".claw-html-frame");
    if (_htmlFrame) _htmlFrame.hidden = true;
    const t0 = performance.now();
    try {
      const r = await fetch(fetchTarget, {
        method,
        headers,
        body: body ? JSON.stringify(body) : null,
      });
      const dt = Math.round(performance.now() - t0);
      const ct = r.headers.get("content-type") || "";
      const head = `← ${r.status} ${r.statusText}   ${dt}ms`;

      if (ct.includes("text/html")) {
        const html = await r.text();
        // A Cloudflare Access "Sign in" page returns HTML 200 when the JWT is gone or stale.
        // That login form in the iframe looks like a broken probe.
        // Detect it and tell the student to refresh the CF Access JWT.
        if (/cloudflareaccess\.com|Sign in ・ Cloudflare Access|Cloudflare Access/i.test(html)) {
          setOutput(head + "\n\nCloudflare Access wants a fresh login because your CF Access JWT is missing or expired" +
            " (it lasts about a day).\n\nFix: open your NemoClaw tab → DevTools → Application → Storage → Cookies →" +
            " click the nemoclaw domain → copy the CF_Authorization value → paste it into the CF Access JWT field" +
            " above and probe again.", "err");
          const _fr = target.querySelector(".claw-html-frame");
          if (_fr) _fr.hidden = true;
          return;
        }
        setOutput(head + `   (HTML · ${html.length} bytes)`, r.ok ? "ok" : "err");
        // Render in a sandboxed iframe below the output bar.
        let fr = target.querySelector(".claw-html-frame");
        if (!fr) {
          fr = document.createElement("iframe");
          fr.className = "claw-html-frame";
          fr.setAttribute("sandbox", "allow-same-origin allow-popups");
          target.querySelector(".claw-probe").appendChild(fr);
        }
        fr.srcdoc = html;
        fr.hidden = false;
      } else {
        let j = null, printed;
        if (ct.includes("application/json")) {
          j = await r.json();
          if (action.filterModels && j && Array.isArray(j.data)) {
            const f = action.filterModels;
            const test = typeof f === "function" ? f
              : Array.isArray(f) ? (id) => f.some(s => String(id).includes(s))
              : (id) => String(id).includes(String(f));
            const before = j.data.length;
            j = { ...j, data: j.data.filter(m => test(m.id ?? m)) };
            j._filtered = `showing ${j.data.length} of ${before}`;
          }
          printed = JSON.stringify(j, null, 2);
          // Auto-fill the bearer token when the probe knows how to find it.
          // OpenClaw's /api/agent exposes the gateway token in agent.dashboardUrl.
          // So base URL + CF Access JWT discover it with no manual paste.
          if (opts.autofillToken && r.ok && j) {
            try {
              const found = opts.autofillToken(j);
              if (found && found !== tokenInp.value.trim()) {
                tokenInp.value = found;
                localStorage.setItem(keyToken, found);
                _syncCanvasKeys(_normalizeBaseUrl(urlInp.value), found, cfJwtInp ? cfJwtInp.value.trim() : "");
                printed += "\n\n↳ bearer token auto-filled from this response (" + found.slice(0, 8) + "…). Ready for the gateway steps below.";
              }
            } catch (_) { /* response shape didn't match; leave the field as-is */ }
          }
        } else {
          printed = await r.text();
        }
        setOutput(head + "\n\n" + printed, r.ok ? "ok" : "err");
      }
    } catch (e) {
      const dt = Math.round(performance.now() - t0);
      const hint = "Possible causes:\n" +
        "• CORS blocked, because a header is not in the Access-Control-Allow-Headers preflight response.\n" +
        "• Wrong URL, so confirm no trailing /v1 on the base URL.\n" +
        "• Service offline. If the launchable just started, wait 30 s and try again.\n" +
        "• 502 on /v1/chat/completions, so the model backend isn't responding; check that\n" +
        "  NVIDIA_API_KEY resolved correctly in the launchable environment.\n\n" +
        "Gateway token: once the URL and CF Access JWT check out, GET /api/agent above fills it in for you from agent.dashboardUrl.";
      setOutput(`✗ network error after ${dt}ms\n   ${String(e?.message || e)}\n\n${hint}`, "err");
    }
  }

  actions.forEach(action => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "claw-btn" + (action.kind === "alt" ? " alt" : "");
    b.textContent = action.label;
    b.addEventListener("click", async () => {
      b.disabled = true;
      try { await runAction(action); }
      finally { b.disabled = false; }
    });
    actBox.appendChild(b);
  });

  return {
    getUrl:   () => _normalizeBaseUrl(urlInp.value),
    getToken: () => tokenInp.value.trim(),
    run:      runAction,
  };
}


// ── Gateway plumbing, shared by 03a/03b/03c/04a ─────────────────────────────
// GW_CONNECT opens /cli/gateway, runs the handshake, and parks state.call/state._ws.
// mountGwRecover mounts the recover flow; both honour the canvas Stop button.

// openclawChat streams one chat turn to the live agent over /cli/gateway.
// It keeps one socket per tab and reads the URL + token the probe stored.
// The gateway-page artifacts use it as their mountChatUI respond.
let _ocSock = null;
export async function openclawChat(message, { session = "main", onToken, onTool, view, signal = null, idleMs = 90000, totalMs = 240000 } = {}) {
  /* @doc <code>helpers.openclawChat(message, {session, onToken, onTool, view})</code> :: Send one
       chat turn to the live OpenClaw agent over the <code>/cli/gateway</code>
       WebSocket and stream the reply. Reads the launchable URL + token from the OpenClaw probe
       (Kickstart page). Pass a <code>view</code> (a <code>mountChatUI</code>
       <code>ctx.view</code>) and it drives the whole observable trace for you: answer text, a
       stack-ordered chip per tool/command call (with its args and full result, errors marked),
       and the gateway-reported context-token budget. (Or pass
       <code>onToken(delta)</code>/<code>onTool(name,{id,args})</code> to handle events
       yourself.) The gateway streams no reasoning channel, so none is shown. Reuse the same
       <code>session</code> for multi-turn. The gateway companion to chat()/createReactAgent.
  */
  const rawUrl = (localStorage.getItem("nemoclaw_clawrawurl") || localStorage.getItem("nemoclaw_clawurl") || "").replace(/\/+$/, "");
  const token  = localStorage.getItem("nemoclaw_clawtoken") || "";
  if (!rawUrl || !token) throw new Error("Connect first on the Kickstart page (3a): set your launchable URL + token in the probe.");
  const wsUrl = rawUrl.replace(/^https/, "wss").replace(/^http(?!s)/, "ws") + "/cli/gateway";

  async function connect() {
    return await new Promise((resolve, reject) => {
      const pend = {}, ws = new WebSocket(wsUrl);
      let chatCb = null;
      const call = (method, params) => new Promise((res, rej) => {
        const id = Math.random().toString(36).slice(2) + Date.now().toString(36);
        const tmo = setTimeout(() => { delete pend[id]; rej(new Error(method + " timed out")); }, 20000);
        pend[id] = { res, rej, tmo };
        ws.send(JSON.stringify({ type: "req", id, method, params: params || {} }));
      });
      ws.onmessage = ev => { let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
        if (d.type === "res" && d.id && pend[d.id]) { const p = pend[d.id]; clearTimeout(p.tmo); delete pend[d.id]; d.ok ? p.res(d.payload) : p.rej(new Error(d.error?.message || "gateway error")); }
        if (d.type === "event" && chatCb) chatCb(d);
      };
      ws.onerror = () => {};
      ws.onclose = () => { if (_ocSock && _ocSock.ws === ws) _ocSock = null; };
      const sock = { ws, call, setCb: cb => { chatCb = cb; }, subs: {} };
      const base = ws.onmessage;
      ws.onmessage = ev => { let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
        if (d.event !== "connect.challenge") { base(ev); return; }
        ws.onmessage = base;
        call("connect", { minProtocol: 4, maxProtocol: 4, client: { id: "openclaw-control-ui", version: "0.1.0", platform: "browser", mode: "webchat" }, caps: ["tool-events"], role: "operator", scopes: ["operator.read", "operator.write", "operator.admin"], auth: { token } })
          .then(() => resolve(sock)).catch(reject);
      };
      setTimeout(() => reject(new Error("no challenge arrived within 15s. Your Cloudflare Access session likely expired. Reopen your launchable URL to re-authenticate.")), 15000);
    });
  }

  if (!_ocSock || _ocSock.ws.readyState !== 1) _ocSock = await connect();
  const sock = _ocSock;
  if (!sock.subs[session]) { await sock.call("sessions.messages.subscribe", { key: session }); sock.subs[session] = true; }
  // Pull readable text out of a gateway tool result / partial result, in full.
  const resText = (r) => { if (r == null) return ""; if (typeof r === "string") return r;
    if (Array.isArray(r.content)) return r.content.map(c => c && c.text || "").join("\n");
    return JSON.stringify(r); };
  // One-line summary of a tool's args for the chip label (command, path, query…).
  const argSummary = (a) => { if (a == null) return ""; if (typeof a === "string") return a;
    const v = a.command || a.path || a.query || a.file || Object.values(a)[0]; return v == null ? "" : String(v); };
  return await new Promise((resolve, reject) => {
    let text = "", myRun = null, idle, glob, toolStarts = 0, usedTok = 0, winTok = 0, lastModel = "", finished = false, sawAgent = false;
    const chips = {};   // toolCallId -> chip element (stack-ordered, never reused)
    const done = (stalled) => { if (finished) return; finished = true; clearTimeout(idle); clearTimeout(glob); sock.setCb(null);
      if (stalled) sock.call("chat.abort", { sessionKey: session }).catch(() => {});
      if (!text.trim() && toolStarts > 0) text = "(the agent ran " + toolStarts + " tool(s) but returned no text. Try the Health check / Recover cells on Kickstart)";
      if (view && usedTok) view.usage({ context: usedTok, window: winTok || undefined, model: lastModel });
      resolve(text); };
    const bump = () => { clearTimeout(idle); idle = setTimeout(() => done(true), idleMs); };
    glob = setTimeout(() => done(true), totalMs);
    // Stop button: abort the agent run (chat.abort) and resolve with what we have.
    if (signal) { if (signal.aborted) return done(true); signal.addEventListener("abort", () => done(true), { once: true }); }

    sock.setCb(d => {
      const pl = d.payload || {};
      if (pl.isHeartbeat || d.event === "health" || d.event === "tick") return;
      if (myRun && pl.runId && pl.runId !== myRun) return;
      bump();
      // The gateway carries token accounting on its frames.
      // totalTokens is what is used; contextTokens is the agent's configured window.
      // Trust both, since this deployment may size the model unlike the build endpoint.
      if (pl.totalTokens) usedTok = pl.totalTokens;
      if (pl.contextTokens) winTok = pl.contextTokens;
      if (pl.model) lastModel = pl.model;
      if (d.event === "chat" && pl.state === "final") { const ft = (pl.message && pl.message.content && pl.message.content[0] && pl.message.content[0].text) || ""; if (ft) text = ft; if (!sawAgent && ft) done(false); return; }
      if (d.event !== "agent") return;
      const sk = pl.sessionKey || ""; if (sk !== session && !sk.endsWith(":" + session)) return;
      sawAgent = true;
      const data = pl.data || {}, stream = pl.stream || "";
      const id = data.toolCallId;
      if (stream === "assistant" || ("delta" in data && "text" in data)) {
        const full = data.text || text;
        if (full.length > text.length) { const delta = full.slice(text.length); if (view) view.token(delta); else if (onToken) onToken(delta); }
        text = full;
      }
      else if (stream === "tool" && data.phase === "start") {
        toolStarts++; const name = data.name || "tool"; const sum = argSummary(data.args);
        if (view) chips[id] = view.tool(name + (sum ? " · " + sum : ""), "(running…)");
        else if (onTool) onTool(name, { id, args: data.args });
      }
      else if (stream === "tool" && data.phase === "update" && view && chips[id] && data.partialResult) {
        const b = chips[id].querySelector(".chatui-tool-body"); if (b) b.textContent = resText(data.partialResult);
      }
      else if (stream === "tool" && data.phase === "result" && view && chips[id]) {
        const c = chips[id], b = c.querySelector(".chatui-tool-body"); if (b) b.textContent = resText(data.result);
        if (data.isError) { c.classList.add("err"); const s = c.querySelector("summary"); if (s) s.textContent = s.textContent.replace("🔧", "✗"); }
      }
      else if (data.phase === "end" && !data.itemId) { done(false); }
    });

    bump();
    sock.call("chat.send", { sessionKey: session, idempotencyKey: Math.random().toString(36).slice(2) + Date.now().toString(36), message })
      .then(res => { myRun = (res && res.runId) || null; })
      .catch(e => { clearTimeout(idle); clearTimeout(glob); sock.setCb(null); reject(e); });
  });
}

export const GW_CONNECT = `
const rawUrl = localStorage.getItem("nemoclaw_clawrawurl") ||
               localStorage.getItem("nemoclaw_clawurl") || "";
const token  = localStorage.getItem("nemoclaw_clawtoken") || "";
if (!rawUrl || !token) {
  helpers.log("Fill in the OpenClaw probe above (URL + token) first.");
  return;
}
const wsUrl = rawUrl.replace(/\\/+$/, "").replace(/^https/, "wss").replace(/^http(?!s)/, "ws") + "/cli/gateway";
helpers.log("→ " + wsUrl);

// Close any socket a previous Connect on this flow left open, so re-running a
// node (or running another Connect) does not pile up live WebSockets in the
// background. We keep ONE socket per flow on state._ws.
if (state._ws) { try { state._ws.close(); } catch (_) {} state._chatCb = null; }

const _pend = {};
const _ws = new WebSocket(wsUrl);
state._ws = _ws;
// Stop button: abort the run → close the socket and reject any in-flight call.
if (typeof helpers !== "undefined" && helpers.signal) helpers.signal.addEventListener("abort", () => {
  try { _ws.close(); } catch (_) {}
  for (const _id in _pend) { try { clearTimeout(_pend[_id].tmo); _pend[_id].reject(new Error("stopped")); } catch (_) {} delete _pend[_id]; }
}, { once: true });
_ws.onmessage = ev => {
  let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
  if (d.type === "res" && d.id && _pend[d.id]) {
    const p = _pend[d.id]; clearTimeout(p.tmo); delete _pend[d.id];
    if (d.ok) p.resolve(d.payload); else p.reject(new Error(d.error?.message || "gateway error"));
  }
  if (d.type === "event" && state._chatCb) state._chatCb(d);
};
_ws.onerror = () => {};
state._chatCb = null;
state.call = (method, params) => new Promise((resolve, reject) => {
  const id  = Math.random().toString(36).slice(2) + Date.now().toString(36);
  const tmo = setTimeout(() => { delete _pend[id]; reject(new Error(method + " timed out")); }, 20000);
  _pend[id] = { resolve, reject, tmo };
  _ws.send(JSON.stringify({ type: "req", id, method, params: params || {} }));
});
await new Promise((resolve, reject) => {
  const base = _ws.onmessage;
  _ws.onmessage = ev => {
    let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
    if (d.event !== "connect.challenge") { base(ev); return; }
    _ws.onmessage = base;
    state.call("connect", {
      minProtocol: 4, maxProtocol: 4,
      client: { id: "openclaw-control-ui", version: "0.1.0", platform: "browser", mode: "webchat" },
      caps: ["tool-events"], role: "operator",
      scopes: ["operator.read", "operator.write", "operator.admin"],
      auth: { token },
    }).then(pl => {
      helpers.log("● connected  v" + (pl?.server?.version || "?") + "  scopes: " + (pl?.auth?.scopes || []).join(", "));
      resolve(pl);
    }).catch(reject);
  };
  setTimeout(() => reject(new Error("no challenge arrived within 15s. Your Cloudflare Access session most likely expired. Open your launchable URL (https://nemoclaw-<id>.brevlab.com) in a new tab to re-authenticate, then re-run Connect. (Less often, the launchable is still booting, so wait 30s and retry.)")), 15000);
});
`;

// ── Shared recover flow (health check + toolSearch repair) ───────────────────
// One mountGwRecover("#gw-recover") call mounts the same detect-and-recover cells.
// Synced across 03a/03c/04a.
export function mountGwRecover(sel) {
  mountCanvasFlow(sel, {
  label: "Detect & recover · health check, then escalating reset",
  intro: "Health check, recover, and logs for the shared agent runtime. Health check tests whether the agent can run a command and whether toolSearch is on; Recover disables toolSearch and clears sessions (the restart that applies it is opt-in, so Run-all is safe); Runtime logs tails the log when a run stalls. Run these on a fresh launchable, or whenever a chat logs ⚠ DEGRADED.",
  edges: [
    { from: "gw-health", to: "gw-fix" },
  ],
  nodes: [
    {
      id: "gw-health", icon: "🩺", title: "Health check", x: 0, y: 0,
      summary: "Checks env status, toolSearch, stuck approvals, and runs one trivial command. HEALTHY = tools work; DEGRADED = run Recover.",
      code: GW_CONNECT + `
// ── tune these ──────────────────────────────────────────────────────────────
const PROBE_TIMEOUT_S = 60;                // how long to wait for the test command (this model can be slow)
const PROBE_MARKER    = "HEALTHCHECK_OK";  // the agent must echo this for a pass
// ──────────────────────────────────────────────────────────────────────────────
helpers.log("Checking the runtime");

// 1. Is the sandbox/environment even available?
try {
  const envs = await state.call("environments.list", {});
  (envs.environments || []).forEach(e => helpers.log("  env " + e.id + ": " + e.status));
} catch (e) { helpers.log("  environments.list failed: " + e.message); }

// 2. The #1 cause of the tool_search_code loop: tools.toolSearch is ON, so the
//    model uses the code bridge to find tools and gets stuck instead of calling
//    exec. The Recover cell turns it off.
let toolSearch = null;
try {
  const cfg = await state.call("config.get", {});
  toolSearch = !!(cfg.parsed && cfg.parsed.tools && cfg.parsed.tools.toolSearch);
  helpers.log("  tools.toolSearch: " + toolSearch + (toolSearch ? "  ← likely the cause; the Recover cell disables it" : ""));
} catch (e) { helpers.log("  config.get failed: " + e.message); }

// 3. A command stuck waiting on an approval looks exactly like a hang.
let pending = 0;
try {
  const appr = await state.call("exec.approval.list", {});
  pending = Array.isArray(appr) ? appr.length : 0;
  helpers.log("  pending exec approvals: " + pending);
} catch (e) { helpers.log("  exec.approval.list failed: " + e.message); }

// 3. Behavioral probe: ask the agent to echo a marker through its exec tool. This is the
//    real test, since the tool_search_code loop breaks exactly this, so it costs one model
//    turn. We stream what the agent does as it happens, and conclude THE MOMENT the marker
//    comes back rather than waiting for the model's closing prose, which is most of the wait.
const PROBE = "quick-health-" + Math.random().toString(36).slice(2, 8);
await state.call("sessions.messages.subscribe", { key: PROBE });
let ok = false, sawTool = false, runId = null;
const trace = [], t0 = performance.now();
const secs = () => ((performance.now() - t0) / 1000).toFixed(1) + "s";
helpers.log("  · probe: asked the agent to echo a marker with its exec tool…");
const outcome = await new Promise((resolve) => {
  const timer = setTimeout(() => resolve("timed out after " + PROBE_TIMEOUT_S + "s"), PROBE_TIMEOUT_S * 1000);
  if (helpers.signal) helpers.signal.addEventListener("abort", () => resolve("stopped"), { once: true });
  state._chatCb = d => {
    const pl = d.payload || {};
    if (pl.isHeartbeat || d.event === "health" || d.event === "tick") return;
    if (runId && pl.runId && pl.runId !== runId) return;
    if (d.event !== "agent") return;
    const data = pl.data || {};
    trace.push({ t: secs(), itemId: data.itemId, phase: data.phase, name: data.name, exitCode: data.exitCode, output: (data.output || "").slice(0, 80) });
    if ((data.itemId || "").startsWith("tool:") && data.phase === "start" && !sawTool) {
      sawTool = true; helpers.log("  · " + secs() + " agent called its " + (data.name || "exec") + " tool");
    }
    if ((data.itemId || "").startsWith("command:") && data.phase === "end") {
      helpers.log("  · " + secs() + " exec returned, exit " + data.exitCode);
      if (data.exitCode === 0 && (data.output || "").includes(PROBE_MARKER)) { ok = true; clearTimeout(timer); resolve("marker echoed"); }
    }
  };
  state.call("chat.send", { sessionKey: PROBE, idempotencyKey: "h" + Date.now(), message: "Run exactly this with your exec tool and report nothing else: echo " + PROBE_MARKER })
    .then(r => { runId = r && r.runId; }).catch(() => { clearTimeout(timer); resolve("chat.send failed"); });
});
state._chatCb = null;
state.call("chat.abort", { sessionKey: PROBE }).catch(() => {});
state.call("sessions.delete", { key: PROBE }).catch(() => {});   // don't leave the probe session behind

if (ok) {
  helpers.log("✓ HEALTHY in " + secs() + ". The agent called its exec tool and the command returned. Tool calls work.");
} else {
  helpers.log("✗ DEGRADED (" + outcome + ")" + (sawTool ? ", the agent fired a tool but no exec result came back" : ", the agent never called a tool") + (pending ? "; " + pending + " exec approval(s) stuck" : "") + (toolSearch ? "; tools.toolSearch is ON" : "") + ".");
  helpers.log("  → Run the 🛠 Recover cell next" + (toolSearch ? " (it turns off toolSearch, the usual cause)" : "") + ".");
}
helpers.log.details("probe trace · " + trace.length + " agent frames in " + secs(), trace);
return { healthy: ok, outcome, pendingApprovals: pending, toolSearch };
`,
    },
    {
      id: "gw-fix", icon: "🛠", title: "Recover", x: 1, y: 0,
      summary: "Disables tools.toolSearch via config.patch (the cause of the tool_search_code loop) and clears sessions. The restart that applies the change is opt-in (set DO_RESTART = true and re-run this cell), so Run-all never knocks the runtime out mid-flow.",
      code: GW_CONNECT + `
helpers.log("Repairing the runtime");

// 1. THE KEY FIX. tools.toolSearch lets the model run a code "bridge" to find and
//    invoke tools. A weaker model (e.g. nemotron-3-super-120b) loops on that
//    bridge ("tool_search_code · run bridge code") and never calls exec. Turn it
//    off with a config merge-patch so the agent uses the native exec tool.
const cfg = await state.call("config.get", {});
if (cfg.parsed && cfg.parsed.tools && cfg.parsed.tools.toolSearch) {
  await state.call("config.patch", { raw: JSON.stringify({ tools: { toolSearch: false } }), baseHash: cfg.hash });
  helpers.log("  ✓ disabled tools.toolSearch (the tool_search_code loop)");
} else {
  helpers.log("  tools.toolSearch already off");
}

// 2. Clear session state: reset the Main Session, delete throwaway sessions.
await state.call("sessions.reset", { key: "agent:main:main" }).catch(() => {});
let offset = 0, all = [];
for (;;) { const page = await state.call("sessions.list", { limit: 100, offset }); all = all.concat(page.sessions || []); if (!page.hasMore) break; offset = page.nextOffset; }
let removed = 0;
for (const s of all.filter(s => !/:main$/.test(s.key))) { try { await state.call("sessions.delete", { key: s.key }); removed++; } catch (e) {} }
helpers.log("  ✓ reset agent:main:main and deleted " + removed + " throwaway session(s)");

// 3. Applying the toolSearch change needs a runtime restart, which DROPS the
//    connection for ~40s, so it is opt-in, never automatic. Leave DO_RESTART
//    false (config is patched and applies on the next restart); flip it to true
//    and re-run ONLY this cell when you want to restart now. Default-false keeps
//    "Run all" from knocking the runtime out from under the cells after it.
const DO_RESTART = false;
if (DO_RESTART) {
  await state.call("gateway.restart.request", { reason: "course recovery: disable toolSearch" }).catch(e => helpers.log("  restart failed: " + e.message));
  helpers.log("  ⟳ restart requested. Wait ~40s, then re-run Connect and the 🩺 Health check.");
  helpers.log("  Still failing after that? The sandbox is wedged below the gateway, so relaunch the launchable from Brev.");
} else {
  helpers.log("  config patched + sessions cleared. To apply it now: set DO_RESTART = true above and re-run THIS cell (it restarts the runtime, ~40s).");
}
`,
    },
    {
      id: "gw-logs", icon: "📜", title: "Runtime logs", x: 2, y: 0,
      summary: "Tails the gateway/agent log (logs.tail): model calls, tool dispatches, errors, hangs. The deepest view when a run stalls and Health check is green; reasoning itself is not exposed over the gateway.",
      code: GW_CONNECT + `
// ── tune these ──────────────────────────────────────────────────────────────
const LOG_LINES = 40;          // how many recent log lines to show
// ──────────────────────────────────────────────────────────────────────────────
const lg = await state.call("logs.tail", { limit: LOG_LINES + 20 });
const lines = lg.lines || [];
helpers.log("runtime log · last " + lines.length + " line(s)" + (lg.file ? " · " + lg.file : ""));
lines.slice(-LOG_LINES).forEach(raw => {
  // Each line is a JSON STRING: { "0": "{subsystem…}", "1": <message>, …, _meta }.
  // Parse it, read the level + subsystem, and join the numeric arg keys (skip "0",
  // the subsystem tag) into one message.
  let L; try { L = typeof raw === "string" ? JSON.parse(raw) : raw; } catch (_) { return; }
  const lvl = ((L._meta && L._meta.logLevelName) || "?").padEnd(5);
  let sub = ""; try { sub = JSON.parse(L["0"] || "{}").subsystem || ""; } catch (_) {}
  const msg = Object.keys(L).filter(k => /^[0-9]+$/.test(k) && k !== "0")
    .map(k => typeof L[k] === "string" ? L[k] : JSON.stringify(L[k]))
    .join(" ").replace(/\\n/g, " ").slice(0, 180);
  if (msg) helpers.log("  " + lvl + (sub ? " [" + sub + "]" : "") + " " + msg);
});
helpers.log.details("raw logs.tail response", lg);
return { lines: lines.length };
`,
    },
  ],
  });
}
