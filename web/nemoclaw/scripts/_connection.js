// Shared launchable routing. Every OpenClaw HTTP/WebSocket consumer uses this module.

export const DEFAULT_OPENCLAW_PROXY_BASE = "https://openclaw-cors-proxy.experiments.courses.nvidia.com";
export const OPENCLAW_PROXY_BASE_KEY = "nemoclaw_openclaw_proxy_base_v1";
export const OPENCLAW_PROXY_ENABLED_KEY = "nemoclaw_openclaw_proxy_enabled_v1";
export const OPENCLAW_URL_KEY = "nemoclaw_clawurl";
export const OPENCLAW_RAW_URL_KEY = "nemoclaw_clawrawurl";
export const OPENCLAW_TOKEN_KEY = "nemoclaw_clawtoken";
export const OPENCLAW_ACCESS_JWT_KEY = "nemoclaw_clawcfjwt";
let querySynced = false;

function storage() {
  try { return globalThis.localStorage || null; }
  catch (_) { return null; }
}

function browserLocation() {
  try { return globalThis.location || null; }
  catch (_) { return null; }
}

function isPersonalWorkerHost(hostname) {
  return /(?:^|\.)workers\.dev$/i.test(String(hostname || ""));
}

function isBrevHost(hostname) {
  return /(?:^|\.)brevlab\.com$/i.test(String(hostname || ""));
}

function pageBase() {
  return browserLocation()?.href || "http://localhost/";
}

export function normalizeOpenClawProxyBase(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  const url = new URL(text);
  const localHttp = url.protocol === "http:" && ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  if (url.protocol !== "https:" && !localHttp) throw new Error("OpenClaw relay URL must use HTTPS");
  if (isPersonalWorkerHost(url.hostname)) throw new Error("Personal worker relays are not allowed");
  if (url.username || url.password || url.search || url.hash) {
    throw new Error("OpenClaw relay URL cannot include credentials, query parameters, or a fragment");
  }
  return url.href.replace(/\/+$/, "");
}

export function normalizeOpenClawLaunchableUrl(raw) {
  const text = String(raw || "").trim().replace(/\/+$/, "");
  if (!text) return "";
  let outer;
  try { outer = new URL(text, pageBase()); }
  catch (_) { return text; }

  // Earlier builds stored the effective relay URL instead of the launchable URL.
  // Recover only an HTTPS Brev target; never retain an outer personal worker host.
  const match = outer.pathname.match(/^\/https\/([^/]+)(\/.*)?$/i);
  if (match && isBrevHost(match[1].split(":")[0])) {
    return new URL("https://" + match[1]).origin;
  }
  if (isPersonalWorkerHost(outer.hostname)) return "";
  outer.hash = "";
  if (isBrevHost(outer.hostname)) {
    outer.search = "";
    outer.pathname = "";
    return outer.origin;
  }
  return /^[a-z][a-z0-9+.-]*:/i.test(text) ? outer.href.replace(/\/+$/, "") : text;
}

function syncConfigFromQuery() {
  if (querySynced) return;
  const target = storage();
  const loc = browserLocation();
  if (!target || !loc) return;
  querySynced = true;
  try {
    const params = new URLSearchParams(loc.search || "");
    const enabled = params.get("openclaw_proxy");
    if (["1", "true", "on", "relay", "auto"].includes(String(enabled).toLowerCase())) {
      target.setItem(OPENCLAW_PROXY_ENABLED_KEY, "1");
    } else if (["0", "false", "off", "direct"].includes(String(enabled).toLowerCase())) {
      target.setItem(OPENCLAW_PROXY_ENABLED_KEY, "0");
    }
    const proxyBase = params.get("openclaw_proxy_base");
    if (proxyBase) target.setItem(OPENCLAW_PROXY_BASE_KEY, normalizeOpenClawProxyBase(proxyBase));
    const launchable = params.get("openclaw_url");
    if (launchable) {
      const clean = normalizeOpenClawLaunchableUrl(launchable);
      if (clean) target.setItem(OPENCLAW_RAW_URL_KEY, clean);
    }
  } catch (_) { /* invalid presenter hints must not corrupt saved connection state */ }
}

export function getOpenClawProxyConfig() {
  syncConfigFromQuery();
  const target = storage();
  let base = DEFAULT_OPENCLAW_PROXY_BASE;
  let enabled = true;
  try {
    const stored = target?.getItem(OPENCLAW_PROXY_BASE_KEY);
    if (stored) base = normalizeOpenClawProxyBase(stored) || DEFAULT_OPENCLAW_PROXY_BASE;
    enabled = target?.getItem(OPENCLAW_PROXY_ENABLED_KEY) !== "0";
  } catch (_) {
    try { target?.removeItem(OPENCLAW_PROXY_BASE_KEY); } catch (_) {}
  }
  return { enabled, base };
}

export function setOpenClawProxyConfig({ enabled, base } = {}) {
  const target = storage();
  const current = getOpenClawProxyConfig();
  const next = {
    enabled: enabled === undefined ? current.enabled : !!enabled,
    base: base === undefined ? current.base : (normalizeOpenClawProxyBase(base) || DEFAULT_OPENCLAW_PROXY_BASE),
  };
  try {
    target?.setItem(OPENCLAW_PROXY_ENABLED_KEY, next.enabled ? "1" : "0");
    if (next.base === DEFAULT_OPENCLAW_PROXY_BASE) target?.removeItem(OPENCLAW_PROXY_BASE_KEY);
    else target?.setItem(OPENCLAW_PROXY_BASE_KEY, next.base);
  } catch (_) {}
  return next;
}

export function shouldProxyOpenClaw(rawUrl, config = getOpenClawProxyConfig()) {
  const clean = normalizeOpenClawLaunchableUrl(rawUrl);
  if (!clean || !config.enabled || !config.base) return false;
  let upstream;
  try { upstream = new URL(clean, pageBase()); }
  catch (_) { return false; }
  if (!isBrevHost(upstream.hostname)) return false;
  const loc = browserLocation();
  return !loc || upstream.origin !== loc.origin;
}

function appendPath(rawUrl, pathAndQuery) {
  const clean = normalizeOpenClawLaunchableUrl(rawUrl);
  if (!clean) return "";
  const suffix = String(pathAndQuery || "");
  if (!suffix) return clean;
  return clean.replace(/\/+$/, "") + (suffix.startsWith("/") ? suffix : "/" + suffix);
}

export function openclawHttpUrl(rawUrl, pathAndQuery = "", config = getOpenClawProxyConfig()) {
  const clean = normalizeOpenClawLaunchableUrl(rawUrl);
  const direct = appendPath(clean, pathAndQuery);
  if (!direct || !shouldProxyOpenClaw(clean, config)) {
    return { url: direct, displayUrl: direct, viaProxy: false, directUrl: direct, directDisplayUrl: direct };
  }
  const upstream = new URL(direct, pageBase());
  const proxied = new URL(config.base);
  const proxyPath = proxied.pathname.replace(/\/+$/, "");
  const upstreamPath = String(pathAndQuery || "") ? upstream.pathname : "";
  proxied.pathname = proxyPath + "/https/" + upstream.host + upstreamPath;
  proxied.search = upstream.search;
  return {
    url: proxied.href,
    displayUrl: proxied.href,
    viaProxy: true,
    directUrl: direct,
    directDisplayUrl: direct,
  };
}

export function openclawWebSocketUrl(rawUrl, pathAndQuery = "/cli/gateway", cfJwt = "", config = getOpenClawProxyConfig()) {
  const routed = openclawHttpUrl(rawUrl, pathAndQuery, config);
  if (!routed.url) return routed;
  const url = new URL(routed.url, pageBase());
  url.protocol = url.protocol === "http:" ? "ws:" : "wss:";
  if (routed.viaProxy && String(cfJwt || "").trim()) {
    url.searchParams.set("cf_access_jwt", String(cfJwt).trim());
  }
  const display = new URL(url.href);
  if (display.searchParams.has("cf_access_jwt")) display.searchParams.set("cf_access_jwt", "...");
  return { ...routed, url: url.href, displayUrl: display.href };
}

export function migrateOpenClawConnectionStorage() {
  syncConfigFromQuery();
  const target = storage();
  if (!target) return { rawUrl: "", migrated: false };
  const beforeRaw = target.getItem(OPENCLAW_RAW_URL_KEY) || "";
  const beforeEffective = target.getItem(OPENCLAW_URL_KEY) || "";
  const clean = normalizeOpenClawLaunchableUrl(beforeRaw) || normalizeOpenClawLaunchableUrl(beforeEffective);
  if (!clean) {
    if (beforeRaw || beforeEffective) {
      target.removeItem(OPENCLAW_RAW_URL_KEY);
      target.removeItem(OPENCLAW_URL_KEY);
    }
    return { rawUrl: "", migrated: !!(beforeRaw || beforeEffective) };
  }
  const effective = openclawHttpUrl(clean).url || clean;
  target.setItem(OPENCLAW_RAW_URL_KEY, clean);
  target.setItem(OPENCLAW_URL_KEY, effective);
  return { rawUrl: clean, migrated: clean !== beforeRaw || effective !== beforeEffective };
}

export function setOpenClawConnection({ rawUrl, token, accessJwt } = {}) {
  const target = storage();
  const current = migrateOpenClawConnectionStorage();
  const clean = rawUrl === undefined
    ? current.rawUrl
    : normalizeOpenClawLaunchableUrl(rawUrl);
  const nextToken = token === undefined ? (target?.getItem(OPENCLAW_TOKEN_KEY) || "") : String(token || "").trim();
  const nextAccessJwt = accessJwt === undefined ? (target?.getItem(OPENCLAW_ACCESS_JWT_KEY) || "") : String(accessJwt || "").trim();
  if (!target) return { rawUrl: clean, effectiveUrl: openclawHttpUrl(clean).url || clean, token: nextToken, accessJwt: nextAccessJwt };
  if (clean) {
    target.setItem(OPENCLAW_RAW_URL_KEY, clean);
    target.setItem(OPENCLAW_URL_KEY, openclawHttpUrl(clean).url || clean);
  } else {
    target.removeItem(OPENCLAW_RAW_URL_KEY);
    target.removeItem(OPENCLAW_URL_KEY);
  }
  if (nextToken) target.setItem(OPENCLAW_TOKEN_KEY, nextToken);
  else target.removeItem(OPENCLAW_TOKEN_KEY);
  if (nextAccessJwt) target.setItem(OPENCLAW_ACCESS_JWT_KEY, nextAccessJwt);
  else target.removeItem(OPENCLAW_ACCESS_JWT_KEY);
  return {
    rawUrl: clean,
    effectiveUrl: clean ? (target.getItem(OPENCLAW_URL_KEY) || clean) : "",
    token: nextToken,
    accessJwt: nextAccessJwt,
  };
}

export function getOpenClawConnection() {
  const target = storage();
  const migrated = migrateOpenClawConnectionStorage();
  return {
    rawUrl: migrated.rawUrl,
    effectiveUrl: target?.getItem(OPENCLAW_URL_KEY) || "",
    token: target?.getItem(OPENCLAW_TOKEN_KEY) || "",
    accessJwt: target?.getItem(OPENCLAW_ACCESS_JWT_KEY) || "",
    proxy: getOpenClawProxyConfig(),
  };
}

migrateOpenClawConnectionStorage();
