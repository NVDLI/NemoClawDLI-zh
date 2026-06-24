// _keypanel.js holds the inline API-key setup panel (mountKeyPanel) that used to live in _shared.js.
import { chat, hasKey, setKey, updateKeyPill, iframeProxyModeEnabled, setIframeProxyMode } from "./_shared.js";

export function mountKeyPanel(container, opts = {}) {
  /* @doc <code>helpers.mountKeyPanel(el)</code> ::
       Renders an inline API-key setup panel using the existing <code>.key-panel</code> CSS
       classes. When a key is saved it shows a compact "✓ saved" row with a Change button. On
       save, strips invisible Unicode, verifies live, then updates the topbar
       <code>#key-status</code> pill.
  */
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return null;
  const _clean = raw => raw.trim().replace(/[^\x20-\x7E]/g, "");
  function _draw() {
    const proxyChecked = iframeProxyModeEnabled();
    if (hasKey()) {
      el.innerHTML = `<div class="key-panel" style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:16px 24px">
        <span style="color:var(--gs,#aee23a);font-family:var(--mono,monospace);font-size:.88rem">&#10003; API key saved for this browser</span>
        <label style="display:flex;align-items:center;gap:8px;margin:0;color:var(--td,#b0b0b0);font-size:.82rem">
          <input type="checkbox" class="iframe-proxy-toggle" ${proxyChecked ? "checked" : ""}/>
          Enable LMS/static iframe execution
        </label>
        <button class="btn" style="margin:0;padding:7px 16px;font-size:.82rem">Change</button>
      </div>`;
      const toggle = el.querySelector(".iframe-proxy-toggle");
      if (toggle) toggle.onchange = () => {
        setIframeProxyMode(toggle.checked);
        const pill = document.getElementById("key-status");
        if (pill) updateKeyPill(pill);
      };
      el.querySelector(".btn").onclick = () => {
        localStorage.removeItem("nvapi");
        const pill = document.getElementById("key-status");
        if (pill) updateKeyPill(pill);
        if (opts.onClear) opts.onClear();
        _draw();
      };
    } else {
      el.innerHTML = `<div class="key-panel">
        <label>NVIDIA API key (starts with <code>nvapi-</code>)</label>
        <input type="password" placeholder="nvapi-&hellip;" autocomplete="off" spellcheck="false"/>
        <label style="display:flex;align-items:center;gap:8px;margin:.7em 0;color:var(--td,#b0b0b0);font-size:.86rem">
          <input type="checkbox" class="iframe-proxy-toggle" ${proxyChecked ? "checked" : ""}/>
          Enable LMS/static iframe execution through the hosted proxy
        </label>
        <button class="btn">Save &amp; verify</button>
        <div class="status"></div>
        <p style="margin:.8em 0 0;font-size:.8rem;color:var(--tf,#8a8a8a)">
          No key yet? <a href="https://build.nvidia.com" target="_blank" rel="noopener">Sign up at build.nvidia.com &rarr;</a>
          Free-tier models cover every exercise. Leave iframe mode off unless your host page needs it.
        </p>
      </div>`;
      const input = el.querySelector("input[type='password']");
      const status = el.querySelector(".status");
      const btn = el.querySelector(".btn");
      async function save() {
        const key = _clean(input.value);
        if (!key.startsWith("nvapi-")) {
          status.className = "status err"; status.textContent = "Key should start with nvapi-"; return;
        }
        status.className = "status"; status.textContent = "Verifying…";
        try {
          const toggle = el.querySelector(".iframe-proxy-toggle");
          setIframeProxyMode(!!toggle?.checked);
          setKey(key);
          // The default model is a reasoning model: it spends tokens on a private
          // reasoning_content channel before writing its answer to content. A tight
          // budget gets consumed entirely by reasoning and leaves content empty, so
          // give the probe enough headroom to reach the one-word answer.
          const r = await chat({ messages: [{ role: "user", content: "Reply with the single word: ready" }], max_tokens: 8196 });
          const reply = r.choices?.[0]?.message?.content?.trim();
          status.className = "status ok";
          status.textContent = reply ? `✓ Connected. Model replied: "${reply}"` : "✓ Connected.";
          const pill = document.getElementById("key-status");
          if (pill) updateKeyPill(pill);
          if (opts.onSave) opts.onSave(key);
          setTimeout(_draw, 1400);
        } catch (e) {
          localStorage.removeItem("nvapi");
          status.className = "status err"; status.textContent = `Connection failed: ${e.message}`;
        }
      }
      btn.addEventListener("click", save);
      input.addEventListener("keydown", ev => { if (ev.key === "Enter") save(); });
    }
  }
  _draw();
  return { update: _draw };
}
