// https://nvidia-api-cors-proxy.vkudlay.workers.dev/
/**
 * Cloudflare Worker for the NVIDIA API CORS proxy.
 *
 * The course does not use this path by default. It exists for LMS/static iframe
 * hosts where a direct browser call is blocked by injected or missing CORS headers.
 * Set ALLOWED_ORIGINS to a comma-separated list of exact origins. Set
 * ALLOW_ANY_ORIGIN=1 only for a temporary local test worker.
 */

const UPSTREAM_ORIGIN = "https://integrate.api.nvidia.com";
const DEFAULT_ALLOWED_ORIGINS = [
  "https://vkudlay.gitlab-master-pages.nvidia.com",
  "https://vkudlay.gitlab.io",
  "https://nvidia.github.io",
];
const ALLOWED_METHODS = "GET, POST, OPTIONS";
const ALLOWED_HEADERS = "Content-Type, Authorization, X-BILLING-SOURCE";

function allowedOrigins(env) {
  const extra = String(env?.ALLOWED_ORIGINS || "")
    .split(",")
    .map(s => s.trim())
    .filter(Boolean);
  return new Set([...DEFAULT_ALLOWED_ORIGINS, ...extra]);
}

function originAllowed(origin, env) {
  if (!origin) return false;
  if (env?.ALLOW_ANY_ORIGIN === "1") return true;
  return allowedOrigins(env).has(origin);
}

function corsHeaders(origin, env) {
  const allowed = originAllowed(origin, env);
  return {
    "Access-Control-Allow-Origin": allowed ? origin : "null",
    "Access-Control-Allow-Methods": ALLOWED_METHODS,
    "Access-Control-Allow-Headers": ALLOWED_HEADERS,
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function jsonError(message, status, origin, env) {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin, env) },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const cors = corsHeaders(origin, env);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: originAllowed(origin, env) ? 204 : 403, headers: cors });
    }
    if (!originAllowed(origin, env)) {
      return jsonError("Origin not allowed for iframe proxy.", 403, origin, env);
    }
    if (!ALLOWED_METHODS.split(/, */).includes(request.method)) {
      return jsonError("Method not allowed.", 405, origin, env);
    }

    const url = new URL(request.url);
    const upstream = UPSTREAM_ORIGIN + url.pathname + url.search;
    const fwd = new Headers(request.headers);
    fwd.delete("host");
    fwd.delete("cookie");

    let resp;
    try {
      resp = await fetch(upstream, {
        method: request.method,
        headers: fwd,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      });
    } catch (e) {
      return jsonError(String(e), 502, origin, env);
    }

    const out = new Headers(resp.headers);
    for (const [k, v] of Object.entries(cors)) out.set(k, v);
    out.delete("Access-Control-Allow-Credentials");
    return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: out });
  },
};
