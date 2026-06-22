// https://nvidia-api-cors-proxy.vkudlay.workers.dev/
/**
 * Cloudflare Worker for the NVIDIA API CORS proxy (paste-and-deploy format)
 *
 * DEPLOY (no wrangler needed):
 *   1. workers.cloudflare.com → Create Worker → paste this file → Deploy
 *   2. Note your URL: https://your-name.your-subdomain.workers.dev
 *
 * WHY: The edX platform injects its own ACAO header on top of the API's,
 * producing two values which browsers reject. This worker strips the
 * upstream header and sets exactly one correct value.
 */

addEventListener("fetch", event => {
  event.respondWith(handle(event.request));
});

async function handle(request) {
  const origin = request.headers.get("Origin") || "*";

  // Handle CORS preflight
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin":  origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        // X-BILLING-SOURCE lets the DLI web client tag usage (e.g. dli-nemoclaw-web)
        // so spend is attributed to the course. It must be allowed here or the
        // browser blocks the request; the worker forwards it upstream unchanged.
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-BILLING-SOURCE",
        "Access-Control-Max-Age":       "86400",
      },
    });
  }

  // Forward to NVIDIA API
  const url      = new URL(request.url);
  const upstream = "https://integrate.api.nvidia.com" + url.pathname + url.search;

  const fwd = new Headers(request.headers);
  fwd.delete("host");

  let resp;
  try {
    resp = await fetch(upstream, { method: request.method, headers: fwd, body: request.body });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 502,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": origin },
    });
  }

  // Replace (not add to) the upstream ACAO header. No Allow-Credentials: this
  // proxy carries the caller's bearer key in the request, never cookies, so
  // credentialed CORS is intentionally not enabled (it would let any origin make
  // cookie-bearing calls). The preflight above already omits it.
  const out = new Headers(resp.headers);
  out.set("Access-Control-Allow-Origin", origin);

  return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: out });
}