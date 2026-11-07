# wavefunction-search-agent — Agent Context
## Harness Compliance: Playbook v1.1

> Proposed replacement for `fleet-mcp-services/contracts/wavefunction-search-agent.md`. Copy it there in a PR. Permission tier is unchanged (Justin's call).

## Project
Reference implementation: `viridisconservation/wavefunction-field` (Apache-2.0). It is a stigmergic intent field: agents post goals with acceptance criteria, sense open work, and submit results. Verified outcomes from trusted verifiers reinforce bounded (MAX-MIN) trails that route later intents. The protocol is in `docs/PROTOCOL.md`.

**Pillar:** infrastructure · **Status:** prototype · **Permission Tier:** Tier 0 (read-only) · **Revenue model:** hosted field, verification-as-a-service, routing for fleet MCP services.

## Fleet contract
- `async process(input) -> dict` dispatches on `input["action"]` ∈ {`sense`, `route`, `get_intent`, `list_intents`, `field_info`, `write`}. It never raises and returns the harness error taxonomy.
- `async health()` returns `{status, agent, version, timestamp, checks}`. `describe()` returns `{name, version, capabilities, inputs, outputs, a2a_role}`.
- Every output includes `session_id` and `budget_consumed`. Routing returns the full distribution and amplitudes ψ.

## Invariants
- I-1 to I-5: harness invariants (unchanged).
- I-6: Σψ² = 1 across candidate agents. Implemented as INV-RT1.
- I-7: entanglement (resonance) is symmetric. Implemented as INV-RT5, bounded at 16 links per intent.
- Trails move only on verifications whose verifier and emitter are in the observer's trust view (INV-DY5).
- All foreign text is returned inside `{"untrusted": …}` (INV-SF1).

## Rails (optional, env-gated, zero network unless configured)
| Rail | Env | Use |
|---|---|---|
| agent-identity-registry | `WF_IDENTITY_REGISTRY_URL` | `resolve`; exclude agents whose pubkey differs (INV-FL4) |
| agent-trust-oracle | `WF_TRUST_ORACLE_URL`, `WF_TRUST_MIN_SCORE` | candidate trusted emitters/verifiers |
| agent-compute-ledger | `WF_COMPUTE_LEDGER_URL` | `record_work` per collapsed result (self-reported tokens) |

[CONFIRM] The MCP tool names on each rail are assumed to equal the action names.
