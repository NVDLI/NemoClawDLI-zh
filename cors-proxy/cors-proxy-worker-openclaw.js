// https://openclaw-cors-proxy.vkudlay.workers.dev/
/**
 * Cloudflare Worker for iframe access to NemoClaw launchable gateways.
 *
 * This worker is not a general relay. Origins opt in by exact allowlist, and
 * upstream hosts stay pinned to brevlab.com launchables unless the worker owner
 * adds explicit extra hosts through ALLOWED_UPSTREAM_HOSTS.
 */

const DEFAULT_ALLOWED_ORIGINS = [
  "https://vkudlay.gitlab-master-pages.nvidia.com",
  "https://vkudlay.gitlab.io",
  "https://nvidia.github.io",
];
const DEFAULT_UPSTREAM_SUFFIXES = [".brevlab.com"];
const DEFAULT_UPSTREAM_HOSTS = ["brevlab.com"];
const ALLOWED_METHODS = "GET, POST, PUT, DELETE, PATCH, OPTIONS";
const ALLOWED_HEADERS = "Authorization, Content-Type, x-openclaw-session-key, X-BILLING-SOURCE, Accept, CF-Access-Jwt-Assertion";

function csv(env, name) {
  return String(env?.[name] || "").split(",").map(s => s.trim()).filter(Boolean);
}

function originAllowed(origin, env) {
  if (!origin) return false;
  if (env?.ALLOW_ANY_ORIGIN === "1") return true;
  return new Set([...DEFAULT_ALLOWED_ORIGINS, ...csv(env, "ALLOWED_ORIGINS")]).has(origin);
}

function corsHeaders(origin, env) {
  return {
    "Access-Control-Allow-Origin": originAllowed(origin, env) ? origin : "null",
    "Access-Control-Allow-Methods": ALLOWED_METHODS,
    "Access-Control-Allow-Headers": ALLOWED_HEADERS,
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function upstreamAllowed(host, env) {
  if (!/^[a-z0-9.-]+$/.test(host)) return false;
  const exact = new Set([...DEFAULT_UPSTREAM_HOSTS, ...csv(env, "ALLOWED_UPSTREAM_HOSTS")]);
  const suffixes = [...DEFAULT_UPSTREAM_SUFFIXES, ...csv(env, "ALLOWED_UPSTREAM_SUFFIXES")];
  return exact.has(host) || suffixes.some(suffix => host.endsWith(suffix));
}

function textError(message, status, origin, env) {
  return new Response(message, {
    status,
    headers: { "Content-Type": "text/plain", ...corsHeaders(origin, env) },
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
      return textError("Origin not allowed for launchable proxy.", 403, origin, env);
    }

    const url = new URL(request.url);
    const path = url.pathname.slice(1);
    if (!path.startsWith("https/")) {
      return textError("Use /https/<host>/<path> (drop the ://).", 400, origin, env);
    }

    const rest = path.slice("https/".length);
    const host = (rest.split("/")[0] || "").toLowerCase();
    if (!upstreamAllowed(host, env)) {
      return textError("Upstream host not allowed (NemoClaw launchables only).", 403, origin, env);
    }

    const target = "https://" + rest + url.search;
    const fwdHeaders = new Headers(request.headers);
    fwdHeaders.delete("host");
    const cfJwt = fwdHeaders.get("CF-Access-Jwt-Assertion");
    if (cfJwt) {
      fwdHeaders.delete("CF-Access-Jwt-Assertion");
      fwdHeaders.set("Cookie", "CF_Authorization=" + cfJwt);
    } else {
      fwdHeaders.delete("cookie");
    }
    if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
      fwdHeaders.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
      fwdHeaders.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);
    }

    const upstream = await fetch(target, {
      method: request.method,
      headers: fwdHeaders,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "follow",
    });
    const out = new Response(upstream.body, upstream);
    for (const [k, v] of Object.entries(cors)) out.headers.set(k, v);
    return out;
  },
};
