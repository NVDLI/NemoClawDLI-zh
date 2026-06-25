// _keypanel.js holds the inline API-key setup panel (mountKeyPanel) that used to live in _shared.js.
import { chat, hasKey, setKey, updateKeyPill, iframeProxyModeEnabled, setIframeProxyMode } from "./_shared.js";

const BUILD_SIGNUP_URL = "https://build.nvidia.com";

export function mountKeyPanel(container, opts = {}) {
  /* @doc <code>helpers.mountKeyPanel(el)</code> ::
       Renders an inline API-key setup panel using the existing <code>.key-panel</code> CSS
       classes. When a key is saved it shows a compact "? saved" row with a Change button. On
       save, strips invisible Unicode, verifies live, then updates the topbar
       <code>#key-status</code> pill.
  */
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return null;
  const _clean = raw => raw.trim().replace(/[^ -~]/g, "");
  function _draw() {
    const proxyChecked = iframeProxyModeEnabled();
    if (hasKey()) {
      el.innerHTML = `<div class="key-panel key-panel-saved">
        <span class="key-saved-label">&#10003; API key saved for this browser</span>
        <label class="iframe-proxy-toggle-row">
          <input type="checkbox" class="iframe-proxy-toggle" ${proxyChecked ? "checked" : ""}/>
          Enable LMS/static iframe execution
        </label>
        <button class="btn key-change-btn">Change</button>
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
        <label class="iframe-proxy-toggle-row">
          <input type="checkbox" class="iframe-proxy-toggle" ${proxyChecked ? "checked" : ""}/>
          Enable LMS/static iframe execution through the hosted proxy
        </label>
        <button class="btn">Save &amp; verify</button>
        <div class="status"></div>
        <p style="margin:.8em 0 0;font-size:.8rem;color:var(--tf,#8a8a8a)">
          No key yet? <a href="${BUILD_SIGNUP_URL}" target="_blank" rel="noopener">Sign up at build.nvidia.com &rarr;</a>
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
        status.className = "status"; status.textContent = "Verifying?";
        try {
          const toggle = el.querySelector(".iframe-proxy-toggle");
          setIframeProxyMode(!!toggle?.checked);
          setKey(key);
          // Give the reasoning-model probe enough tokens to reach its final answer.
          const r = await chat({ messages: [{ role: "user", content: "Reply with the single word: ready" }], max_tokens: 8196 });
          const reply = r.choices?.[0]?.message?.content?.trim();
          status.className = "status ok";
          status.textContent = reply ? `? Connected. Model replied: "${reply}"` : "? Connected.";
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
  try {
    sessionStorage.removeItem("nemoclaw_open_key_panel");
    const params = new URLSearchParams(location.search || "");
    const openKeyPanel = params.get("openKeyPanel") === "1";
    if (openKeyPanel) {
      params.delete("openKeyPanel");
      const qs = params.toString();
      history.replaceState(null, "", location.pathname + (qs ? `?${qs}` : "") + location.hash);
      requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "center" }));
    } else if (location.hash === "#key-panel" && hasKey()) {
      history.replaceState(null, "", location.pathname + location.search);
      requestAnimationFrame(() => scrollTo({ top: 0, behavior: "auto" }));
    }
  } catch (_) {}
  return { update: _draw };
}
