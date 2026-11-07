# Changelog

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
