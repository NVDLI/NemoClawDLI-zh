// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

// Browser proxy for NemoClaw launchables protected by Cloudflare Access.
const WORKER_VERSION = "openclaw-cors-proxy/2026-06-26-ws-gateway";

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "*";
    const cors = {
      "Access-Control-Allow-Origin":  origin,
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, x-openclaw-session-key, Accept, CF-Access-Jwt-Assertion",
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
    // Restrict targets because requests carry Cloudflare Access credentials.
    // Without this allowlist, an attacker could redirect those credentials to another host.
    const hostOk = /^[a-z0-9.-]+$/.test(host) && (host === "brevlab.com" || host.endsWith(".brevlab.com"));
    if (!hostOk) {
      return new Response('Upstream host not allowed (NemoClaw launchables only).', { status: 403, headers: { "Content-Type": "text/plain", ...cors } });
    }
    const targetSearch = new URLSearchParams(url.search);
    const fwdHeaders = new Headers(request.headers);
    // Forward the JWT as the CF_Authorization cookie checked by Cloudflare Access.
    // Browser WebSockets cannot set headers, so the gateway accepts a short-lived query value.
    // Delete that value before forwarding the request.
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

    const isWebSocket = (request.headers.get("Upgrade") || "").toLowerCase() === "websocket";
    if (isWebSocket) {
      // OpenClaw validates Origin during the WebSocket handshake.
      // nginx uses the same trusted origin; the Worker terminates CF/JWT authentication.
      fwdHeaders.set("Origin", "http://localhost:8088");
      const upstream = await fetch(target, { method: request.method, headers: fwdHeaders, redirect: "manual" });
      if (upstream.webSocket) return upstream;
      return new Response("Upstream did not accept WebSocket upgrade", { status: 502, headers: { "Content-Type": "text/plain", ...cors } });
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
