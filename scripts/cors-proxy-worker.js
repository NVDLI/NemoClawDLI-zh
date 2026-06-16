/**
 * Cloudflare Worker — CORS relay for NVIDIA API on learn.learn.nvidia.com
 *
 * WHY THIS EXISTS
 * The edX platform (learn.learn.nvidia.com) injects its own
 * Access-Control-Allow-Origin header onto responses that pass through it.
 * Combined with the NVIDIA API's own ACAO header, browsers see two values
 * and reject the response. This worker receives the fetch, forwards it to
 * the NVIDIA API, and returns a response with exactly one ACAO header.
 *
 * DEPLOY (5 minutes, free Cloudflare account, no credit card)
 * 1. Sign up at https://workers.cloudflare.com
 * 2. Workers & Pages → Create Worker → paste this file → Deploy
 * 3. Note your worker URL: https://your-name.your-subdomain.workers.dev
 *
 * CONFIGURE THE COURSE
 * In the edX XBlock HTML editor, add this BEFORE the page's inline script:
 *
 *   <script>
 *     window.NV_API_PROXY = "https://your-name.your-subdomain.workers.dev";
 *   </script>
 *
 * That's it. No other changes needed.
 */

const UPSTREAM = "https://integrate.api.nvidia.com";

export default {
  async fetch(request) {
    const origin = request.headers.get("Origin") || "*";

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin":  origin,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
          "Access-Control-Max-Age":       "86400",
        },
      });
    }

    const url      = new URL(request.url);
    const upstream = UPSTREAM + url.pathname + url.search;

    // Forward all headers except those that would confuse the upstream
    const fwdHeaders = new Headers(request.headers);
    fwdHeaders.delete("host");
    fwdHeaders.delete("cf-connecting-ip");
    fwdHeaders.delete("cf-ray");

    let upstreamResp;
    try {
      upstreamResp = await fetch(upstream, {
        method:  request.method,
        headers: fwdHeaders,
        body:    request.body,
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), {
        status: 502,
        headers: {
          "Content-Type":                "application/json",
          "Access-Control-Allow-Origin": origin,
        },
      });
    }

    // Copy upstream headers, replacing (not adding to) ACAO
    const respHeaders = new Headers(upstreamResp.headers);
    respHeaders.set("Access-Control-Allow-Origin", origin);
    respHeaders.set("Access-Control-Allow-Credentials", "true");

    return new Response(upstreamResp.body, {
      status:     upstreamResp.status,
      statusText: upstreamResp.statusText,
      headers:    respHeaders,
    });
  },
};
