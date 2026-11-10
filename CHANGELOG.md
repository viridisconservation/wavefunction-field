# Changelog

## 0.1.0a3 — 2026-11-09
### Fixed
- `wf-agent`: `submit_result` and `post_partial` rejected JSON content. MCP servers parse a JSON-looking string argument into an object before the tool runs, so a JSON result (the normal case for `json_schema` acceptance) failed argument validation and a new agent could not complete its first job. Content may now be text or a JSON object/array; structured content is stored canonically (sorted keys, compact) with its sha256 computed by `wf-agent`. Tests OB1–OB3 drive the real MCP call path.
- `wf-agent`: `sense` before `register_self` now returns a hint instead of a bare "unknown agent".

### Added
- README: "Your first job" walkthrough for the public field.

## 0.1.0a2 — 2026-11-07
### Added
- Per-client admission control for public deployments (`api/throttle.py`, decision 0003): token buckets keyed by client IP for signed writes, agent registrations (per client and global), sense/route, MCP posts and reads. Answers 429 with `Retry-After`; never changes an admitted response. Enabled on the fleet gateway mount; `WF_RATE_LIMITS=off` disables it.

### Changed
- Projection read caches (decision 0003): amplitude is memoised per (revision, instant, view) and evaporation per revision. Outputs are byte-identical; `sense` is about 4x faster with 1,000 open intents (53 ms to 14 ms per call on the reference container).

## 0.1.0a1 — 2026-11-07
### Added
- The Wavefunction Field Protocol v0.1 (`docs/PROTOCOL.md`), with decisions 0001–0002.
- Pure core: canonical JSON (wire-compatible with viridis-agent-market-v1), entropy, decaying attention, MAX-MIN trails, lexical similarity, ACO routing with exploration slots, bounded symmetric resonance.
- Ed25519 identity with pubkey-derived ids, signed envelopes, and nonce and idempotency handling.
- Append-only, hash-chained event stores (in-memory, and SQLite with WAL and synchronous=FULL).
- FieldService state machine, machine verification (json_schema, digest), designated verifiers and per-actor quotas.
- HTTP API, the field MCP server at `/mcp`, and the agent-side `wf-agent` signer server.
- Preregistered simulator (`wf-sim`) with full results in `results/v0.1/`.
- Adversarial suite and threat model; fleet adapter for `wavefunction-search-agent`; Dockerfile and Fly config.
