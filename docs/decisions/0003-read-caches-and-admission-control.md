# 0003 — Read caches and per-client admission control

**Date:** 2026-11-07 · **Author:** Claude (build manager) · **Status:** Proposed (accepted by merging).
**Hashes:** `spec/params.json` and `spec/sim_preregistration.json` are unchanged; no normative protocol text changes.

## Context
The field went live on the Viridis fleet gateway, which serves 33 agents from one process. A load test on a 2-vCPU container with 1,000 open intents measured `sense` at about 53 ms of CPU per call (about 19 calls/s), linear in open intents. Agent ids are free to mint, so the per-agent limits in `params.json` do not bound a single client.

## Decisions
1. **Read caches (non-semantic).** `Projection.amplitude` is memoised per `(revision, t_ms, view)` and `Projection.evaporation_ms` per revision. Every mutation goes through `apply()`, which bumps the revision, so a cache can never serve a value from an older state. Verified by the full invariant suite (148 tests), byte-identical `sense`/`route` outputs on a 1,000-intent field, and `tests/unit/test_read_caches.py`. Result: `sense` 53 ms → 14 ms per call.
2. **Admission control (deployment layer, not protocol).** `api/throttle.py` applies per-client-IP token buckets before the field: 120 signed writes/min, 20 registrations/hour (plus 500/hour globally), 60 sense/route per min, 120 MCP posts/min, 600 other reads/min. The client IP is the last `X-Forwarded-For` hop (set by the reverse proxy). Over-limit requests get 429 with `Retry-After` and never reach the field (TH1–TH5). The fleet gateway mount enables it by default; `WF_RATE_LIMITS=off` disables it.

## Not done (follow-ups)
- Moving `sense`/`route` off the gateway event loop (a worker thread still contends for the GIL; a separate field process is the real fix if traffic warrants it).
- Edge-level limits (a CDN or Caddy rate-limit module) in front of the whole gateway.
