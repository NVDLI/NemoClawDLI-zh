#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Async CORS + WebSocket proxy for local OpenClaw gateway.

  HTTP  : adds CORS headers, forwards to http://localhost:18789
  WS    : bridges ws://browser ↔ ws://localhost:18789/cli/gateway

Handles concurrent HTTP requests AND long-lived WebSocket sessions on a
single asyncio event loop — no thread blocking, no connection starvation.

Install dependency (WSL2):
    pip install aiohttp --break-system-packages

Start:
    python3 openclaw_proxy.py
"""

import asyncio
import aiohttp
from aiohttp import web

TARGET = "http://localhost:18789"
PORT   = 8011

# ── CORS header set ───────────────────────────────────────────────────────────
_CORS_FIXED = {
    "Access-Control-Allow-Methods":
        "GET, POST, PUT, DELETE, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": (
        "Authorization, Content-Type, x-openclaw-session-key, Accept, "
        "CF-Access-Jwt-Assertion, X-OpenClaw-Access-Provider, "
        "X-OpenClaw-Access-Session"
    ),
}

# Headers that must not be forwarded (hop-by-hop or WebSocket-handshake headers)
_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "sec-websocket-key", "sec-websocket-version",
    "sec-websocket-extensions", "sec-websocket-protocol",
    "host", "referer", "content-length",
})


def _cors(request):
    """Return CORS headers echoing the request's Origin."""
    origin = request.headers.get("Origin", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        **_CORS_FIXED,
    }


def _fwd(request):
    """Headers safe to forward to the upstream gateway."""
    return {k: v for k, v in request.headers.items() if k.lower() not in _HOP}


# ── HTTP handler ──────────────────────────────────────────────────────────────

async def _http(request):
    url = TARGET + request.path_qs
    body = await request.read()

    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.request(
                method=request.method,
                url=url,
                headers=_fwd(request),
                data=body or None,
                timeout=aiohttp.ClientTimeout(total=90),
                allow_redirects=False,
            ) as resp:
                out = await resp.read()
                ct = resp.headers.get("Content-Type", "application/json")
                h = {**_cors(request), "Content-Type": ct}
                print(f"[http] {request.method} {request.path} → {resp.status} ({len(out)}b)")
                return web.Response(status=resp.status, body=out, headers=h)

        except aiohttp.ClientError as e:
            print(f"[http] {request.method} {request.path} → upstream error: {e}")
            return web.Response(status=502, text=str(e), headers=_cors(request))

        except Exception as e:
            print(f"[http] {request.method} {request.path} → error: {e}")
            return web.Response(status=500, text=str(e), headers=_cors(request))


# ── WebSocket handler ─────────────────────────────────────────────────────────

async def _ws(request):
    """
    Bidirectional WebSocket bridge:
      browser  ←→  this proxy  ←→  OpenClaw gateway (:18789)

    Both legs run as concurrent asyncio tasks, so neither direction
    blocks the other, and the event loop stays free for HTTP requests.
    """
    # Upgrade the browser → proxy leg
    ws_browser = web.WebSocketResponse(heartbeat=30)
    await ws_browser.prepare(request)

    # Build the upstream ws:// URL (http → ws, https → wss)
    scheme   = "wss" if TARGET.startswith("https") else "ws"
    upstream = scheme + TARGET[TARGET.index("://"):] + request.path_qs

    print(f"[ws ] {request.path} → {upstream}")
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(
                upstream,
                headers=_fwd(request),
                heartbeat=30,
                timeout=aiohttp.ClientTimeout(total=None),   # WS sessions are long-lived
            ) as ws_gw:

                async def browser_to_gw():
                    """Forward frames from the browser to the gateway."""
                    async for msg in ws_browser:
                        if   msg.type == aiohttp.WSMsgType.TEXT:
                            await ws_gw.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await ws_gw.send_bytes(msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSE,
                                          aiohttp.WSMsgType.ERROR):
                            break

                async def gw_to_browser():
                    """Forward frames from the gateway to the browser."""
                    async for msg in ws_gw:
                        if   msg.type == aiohttp.WSMsgType.TEXT:
                            await ws_browser.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await ws_browser.send_bytes(msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSE,
                                          aiohttp.WSMsgType.ERROR):
                            break

                # Run both directions concurrently.
                # return_exceptions=True prevents one side's close from
                # raising into the other before it has a chance to finish.
                await asyncio.gather(
                    browser_to_gw(),
                    gw_to_browser(),
                    return_exceptions=True,
                )

    except aiohttp.ClientError as e:
        print(f"[ws ] {request.path} → upstream error: {e}")
    except Exception as e:
        print(f"[ws ] {request.path} → error: {e}")

    print(f"[ws ] {request.path} closed")
    return ws_browser


# ── Router ────────────────────────────────────────────────────────────────────

async def route(request):
    """Dispatch incoming request to the right handler."""
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=_cors(request))

    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await _ws(request)

    return await _http(request)


# ── App ───────────────────────────────────────────────────────────────────────

app = web.Application()
app.router.add_route("*", "/", route)
app.router.add_route("*", "/{path_info:.*}", route)

if __name__ == "__main__":
    print(f"OpenClaw async proxy  http://localhost:{PORT}  →  {TARGET}")
    print(f"  WebSocket:           ws://localhost:{PORT}/cli/gateway  →  ws://localhost:18789/cli/gateway")
    print()
    web.run_app(app, host="localhost", port=PORT, access_log=None)
