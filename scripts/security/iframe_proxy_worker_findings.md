# Iframe Proxy Worker Follow-Up Findings

This MR does not change `cors-proxy/cors-proxy-worker-build.js` or `cors-proxy/cors-proxy-worker-openclaw.js`.
The worker source needs owner review before any deployment change.

Findings to review later:

- `cors-proxy-worker-build.js` reflects the request `Origin` into `Access-Control-Allow-Origin`. That keeps LMS/static iframe execution working, but it is broad. Review whether deployed workers should require an exact `ALLOWED_ORIGINS` list.
- `cors-proxy-worker-build.js` forwards caller headers to `integrate.api.nvidia.com`. Keep `X-BILLING-SOURCE` allowed and forwarded because direct and proxy paths both use it for tracking.
- `cors-proxy-worker-openclaw.js` restricts upstream hosts to `brevlab.com` and subdomains, which is important. It still reflects page origins for CORS. Review whether an origin allowlist should be added around LMS/static hosts.
- Any worker-source change should happen in a dedicated worker MR with deployment-owner review. This branch only makes course-runtime proxy use explicit.
