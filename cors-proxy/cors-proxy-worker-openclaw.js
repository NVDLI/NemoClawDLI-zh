// https://openclaw-cors-proxy.vkudlay.workers.dev/
export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "*";
    const cors = {
      "Access-Control-Allow-Origin":  origin,
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, x-openclaw-session-key, X-BILLING-SOURCE, Accept, CF-Access-Jwt-Assertion",
      "Access-Control-Max-Age":       "86400",
    };
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    const url  = new URL(request.url);
    const path = url.pathname.slice(1);
    if (!path.startsWith("https/")) {
      return new Response('Use /https/<host>/<path> (drop the ://).', { status: 400, headers: { "Content-Type": "text/plain", ...cors } });
    }
    const rest = path.slice("https/".length);
    const host = (rest.split("/")[0] || "").toLowerCase();
    // Host allowlist: this proxy reaches NemoClaw launchables only. Keep it tight,
    // because the CF Access service token below is forwarded to the target host.
    // Without this check the worker is an open relay that would leak that token
    // (and any forwarded auth) to an arbitrary host an attacker names in the path.
    const hostOk = /^[a-z0-9.-]+$/.test(host) && (host === "brevlab.com" || host.endsWith(".brevlab.com"));
    if (!hostOk) {
      return new Response('Upstream host not allowed (NemoClaw launchables only).', { status: 403, headers: { "Content-Type": "text/plain", ...cors } });
    }
    const targetSearch = new URLSearchParams(url.search);
    const fwdHeaders = new Headers(request.headers);
    // Forward the JWT as the CF_Authorization cookie that Cloudflare Access checks.
    // Fetch probes can send CF-Access-Jwt-Assertion. Browser WebSocket constructors
    // cannot set headers, so the gateway path accepts the same value as a short-lived
    // query parameter and strips it before forwarding upstream.
    const cfJwt = fwdHeaders.get("CF-Access-Jwt-Assertion") || targetSearch.get("cf_access_jwt");
    targetSearch.delete("cf_access_jwt");
    const target = "https://" + rest + (targetSearch.toString() ? "?" + targetSearch.toString() : "");
    if (cfJwt) {
      fwdHeaders.delete("CF-Access-Jwt-Assertion");
      fwdHeaders.set("Cookie", "CF_Authorization=" + cfJwt);
    }
    if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
      fwdHeaders.set("CF-Access-Client-Id",     env.CF_ACCESS_CLIENT_ID);
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