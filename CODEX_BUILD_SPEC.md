# Wavefunction Field — Codex Build & Handoff Spec (v0.1)

**Author:** Claude, for Justin Hart (Viridis LLC)
**Date:** 2026-11-07
**Build manager:** Claude (reviews every PR and handoff; writes follow-up prompts)
**Execution agent:** Codex (OpenAI coding agent)
**Authority:** **Branch + PR only.** Codex never merges, tags, publishes, deploys, changes repo visibility, or touches production, payments or live fleet endpoints.

This spec is executed by a coding agent with minimal supervision. It uses the **spec-invariance** method: each work package (WP) names the invariants it must satisfy (registry: `spec/invariants.json`), lists concrete tasks, and defines acceptance checks that prove those invariants. `docs/PROTOCOL.md` is the normative protocol. If this file and PROTOCOL.md disagree, **PROTOCOL.md wins**. Record the conflict in `CODEX_NOTES.md`. Items marked **[CONFIRM]** must be resolved from the actual environment at the start of the WP, not guessed.

---

## 0. How Codex must work

1. **Read in order before any change:** `AGENTS.md` → this file → `docs/PROTOCOL.md` → `spec/invariants.json` → `spec/params.json` → `spec/test_vectors.json` → `spec/sim_preregistration.json` → `spec/BUILD_STATE.json`.
2. **One WP = one branch = one PR.** Branch `codex/wp-<n>-<slug>`. Within a wave, WPs stack: each branch is cut from the previous WP's branch, and the PR base is that branch, or `main` for the first WP of the wave. Never push to `main`.
3. **Invariants are the contract.** Implement to them, then prove them. Each test that proves an invariant puts its id (e.g. `INV-DY4`) in the test name or docstring. If an invariant cannot be met, or a [CONFIRM] turns out false: **stop that WP**, open a **draft** PR with `CODEX_NOTES.md` (blocker, evidence, 2–3 options with your recommendation), and do not start dependent WPs.
4. **Tests ship with code.** A WP is done only when its new tests and all existing tests pass, and every global check (§3.4) passes. Then append the WP id to `spec/BUILD_STATE.json.completed_wps` in that PR.
5. **Never weaken a test, a threshold or an invariant to get a pass** `[G9]`. Never edit `spec/params.json`, `spec/sim_preregistration.json`, `spec/invariants.json` or `docs/PROTOCOL.md` normatively without a decision record in `docs/decisions/` that Justin approves through PR review. Typo fixes are fine; flag them in the PR body.
6. **PR body template:** Summary · Invariants satisfied (checkbox list with the test names that prove each) · Acceptance output (paste the command results) · Out-of-scope confirmed · Assumptions / [CONFIRM] resolutions · Deviations from spec (or "none").
7. **Commits:** conventional commits, DCO `Signed-off-by:` on every commit, SPDX `Apache-2.0` header on every source file.
8. **End of every wave:** write `docs/handoff/WAVE_<X>_HANDOFF.md` (format in §6) in the last PR of the wave and print it as your final message. Justin passes it back to Claude for review.

---

## 1. Context — what we are building and why

Wavefunction Search began as an engine that routes **people** to aligned collectives. v0.1 pivots it into an **open MCP intent field for agents**. An agent emits a goal before it knows who can fulfil it. The field resolves who does the work through stigmergy: attention that fades over time, resonance between like-minded intents, and trails reinforced only by **verified** outcomes from **trusted** verifiers.

Prior art exists. Stigmergic blackboards for agents (SBP, stigmergent-mcp, stigmergy-scheduler, stigmem) and capability registries (A2A Agent Cards, the MCP Registry) are already out there. Our differentiators, which the build MUST deliver and the simulation MUST test:

1. **Intent-first.** Agents post goals plus acceptance criteria, not capability lookups.
2. **Verified collapse.** Trails move only on verified pass/fail (`INV-DY5`).
3. **Trust is local.** Reinforcement counts only from the observer's trust view, which gives sybil resistance (`INV-DY5`, `INV-DY8`, H4).
4. **No lock-in.** MAX-MIN trail bounds keep exploration alive (`INV-DY4`, `INV-RT3`, H3).
5. **A falsifiable efficiency claim.** Self-reported cost-to-collapse falls as verified-trail density rises (H1, H2). This is the product-side reading of the Intelligence Bound, dI/dt ≤ P·D/k_BT ln 2: verified trails raise D for the next agent.

**Fleet fit.** The Viridis fleet already runs identity (`agent-identity-registry`), trust (`agent-trust-oracle`), escrow, covenant, compute ledger and `agent-market-network`, which provides signed post/bid/award. This repo builds **only the routing layer** and plugs into those rails through optional adapters (WP-9). It realises the prototype fleet contract `contracts/wavefunction-search-agent.md`, including fleet invariants I-6 (amplitudes normalise) and I-7 (symmetric entanglement), which map to `INV-RT1` and `INV-RT5`.

---

## 2. Decisions taken in this spec (Justin may override in PR review)

| # | Decision | Why |
|---|---|---|
| D1 | New repo `wavefunction-field`, **private** until the Wave C release gates pass and Justin approves making it public. **[JUSTIN: owner org — default `viridisconservation`]** | Clean provenance, open-source-ready, and no contact with `wavefunction/env/` secrets |
| D2 | Python ≥ 3.11 and the official `mcp` SDK | Matches `agent-market-network`, the gateway and the wavefunction beta runtime |
| D3 | Implements the `wavefunction-search-agent` fleet contract; permission tier unchanged (Tier 0) | Tier promotion is Justin's call |
| D4 | No payments, escrow, pricing or token in v0.1; payments go to existing rails via adapters later | No new money path; less regulatory drag |
| D5 | Trust is local: a `TrustView` per observer. The default view is the field key plus operator-admitted agents | Sybil resistance without global reputation |
| D6 | Verification: machine (`json_schema`, `digest`) signed by the field key, plus `designated` verifiers. `lean` is reserved | Covers deterministic and human/agent review now; Aristotle later |
| D7 | Everything in a field is public in v0.1 | Simplest honest privacy model |
| D8 | Wire-compatible canonical JSON with `viridis-agent-market-v1`; `agent_id` derived from the pubkey | Interop with the market, and no name squatting |
| D9 | Deterministic lexical similarity in v0.1; embeddings later as a plugin | Offline, reproducible tests and sims |
| D10 | Sim thresholds are preregistered and locked (`spec/PREREG_LOCK`) | A falsifiable science claim; no p-hacking |

---

## 3. Global guardrails

### 3.1 Authority (G1)
No merge, tag, publish (PyPI, npm, MCP registry, Smithery, Glama), deploy, DNS change, repo visibility change, outreach or posting. No calls to live `mcp.viridisconservation.com` endpoints, ever, including from tests.

### 3.2 Secrets (G2)
None in the repo. Do not read, copy or reference any file under the `wavefunction/env/` folder or any `.env`. Generated test keys live in `tmp_path` only.

### 3.3 Dependency allowlist (G4)
- **Runtime:** `mcp>=1.25,<2` (brings `pydantic`, `starlette`, `uvicorn`, `httpx`, `anyio`, `sse-starlette`, `pydantic-settings`), `cryptography>=42`, `jsonschema>=4.21` (brings `referencing`).
- **Dev:** `pytest>=8`, `hypothesis>=6.100`, `ruff>=0.6`, `mypy>=1.11` (minimums per decision 0002). Always invoke them from the project venv as `python -m <tool>`, never a globally installed copy.
- **Build backend:** `hatchling`.
- Anything else means stop and write `CODEX_NOTES.md`. No numpy, scipy or matplotlib: stats and SVG plots are written in plain Python.

### 3.4 Global checks (all must pass in every PR)
**Preflight (decision 0002).** Before any work, run `python -m pip download --no-deps -d "$(mktemp -d)" hatchling` and `git ls-remote origin`. If either fails, the environment has no network: stop immediately with a one-line blocker. Do not scaffold, write reports, or fetch packages through a browser.
```bash
python -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
python -m ruff check . && python -m ruff format --check .
python -m mypy --strict src/wavefunction_field/core src/wavefunction_field/identity
python -m pytest -q
python scripts/check_traceability.py     # G7
python scripts/check_deps.py             # G4
python scripts/check_claims.py           # G5
python scripts/check_headers.py          # G8
python scripts/check_core_purity.py      # G3 / INV-DY7
python scripts/check_prereg_lock.py      # INV-SIM3
```
CI (`.github/workflows/ci.yml`) runs these on Python 3.11, 3.12 and 3.13, plus gitleaks via the official container image (**[CONFIRM]** whether the owner org needs a gitleaks license for the GitHub Action; if so, use the docker CLI instead) and a DCO check over the PR's commit range.

### 3.5 Repository layout (target)
```
wavefunction-field/
  AGENTS.md  CODEX_BUILD_SPEC.md  LICENSE  NOTICE  README.md  SECURITY.md  CONTRIBUTING.md  CHANGELOG.md
  pyproject.toml
  spec/        invariants.json params.json test_vectors.json sim_preregistration.json PREREG_LOCK BUILD_STATE.json
  docs/        PROTOCOL.md THREAT_MODEL.md decisions/ handoff/
  src/wavefunction_field/
    core/      canonical.py params.py models.py sanitize.py entropy.py dynamics.py similarity.py
               routing.py resonance.py projection.py errors.py views.py      # pure: no I/O, no clock, no RNG
    identity/  keys.py envelope.py signer.py
    store/     base.py memory.py sqlite.py chain.py
    verify/    base.py digest.py json_schema.py designated.py
    service/   field.py clock.py limits.py metrics.py config.py
    api/       http.py manifest.py untrusted.py
    mcp/       field_server.py agent_server.py agent_config.py
    sim/       world.py scenarios.py run.py stats.py report.py svg.py cli.py
    fleet/     agent.py agent.yaml adapters/{trust_oracle,identity_registry,compute_ledger}.py
  scripts/     check_*.py
  tests/       unit/ property/ service/ api/ mcp/ sim/ adversarial/ fleet/ conftest.py
  examples/    two_agents_demo.py  mcp_configs/
  results/v0.1/   (full sim outputs, committed in WP-7)
```
Console scripts: `wf-field` (serve the field), `wf-agent` (agent-side MCP over stdio), `wf-sim` (simulator).

---

## 4. Waves and dependencies

```
Wave A (kernel):     WP-0 ─┬─ WP-1 (core, pure) ─┐
                           ├─ WP-2 (identity)  ──┼─ WP-4 (FieldService)   ⟶ STOP, handoff A
                           └─ WP-3 (store)     ──┘
Wave B (surfaces+science): WP-5 (verifiers) → WP-6 (HTTP + MCP) → WP-7 (simulator + preregistered runs) → WP-8 (adversarial)   ⟶ STOP, handoff B
Wave C (fleet+release):    WP-9 (fleet adapter + rails) → WP-10 (docs, examples, release readiness)   ⟶ STOP, handoff C
```
WP-1, WP-2 and WP-3 are independent once WP-0 merges. Codex may run them as parallel tasks if the operator launches them that way. In a single session they are stacked in the order shown.

---

## 5. Work packages

### WP-0 — Bootstrap · Wave A
**Objective.** A repo skeleton in which every global check runs and passes.
**Invariants.** G1–G9 machinery; no INV ids yet.
**Tasks.**
1. `pyproject.toml` (hatchling, `src/` layout, the three console scripts, runtime and `[dev]` extras exactly per §3.3), `LICENSE` (Apache-2.0), `NOTICE`, `CONTRIBUTING.md` (DCO), `SECURITY.md` stub, `README.md` stub with a **pre-alpha** banner and the PROTOCOL §0.1 terminology note, `.gitignore`.
2. Package skeleton per §3.5, with empty modules carrying SPDX headers.
3. `tests/conftest.py`: an autouse fixture that blocks outbound sockets (allow Unix and ASGI in-process transports), and an injectable `FakeClock`.
4. Scripts:
   - `check_traceability.py`: every invariant whose `wp` is in `completed_wps` has at least one test referencing its id, and no test references an unknown id.
   - `check_deps.py`: installed top-level requirements in pyproject ⊆ allowlist.
   - `check_claims.py`: a denylist regex over `src/`, `docs/`, `README.md` and `examples/` (quantum mechanics claims, "proven", "guarantee", "energy sav", "joule", "carbon neutral", "verified alignment"). Allowlist the PROTOCOL §0.1 terminology note and decision records.
   - `check_headers.py`
   - `check_core_purity.py`: an AST scan of `core/` rejecting imports of `time`, `random`, `os`, `socket`, `sqlite3`, `httpx`, `asyncio`, `datetime` (except `datetime.timezone` and parsing types, if needed), `secrets`, `uuid`.
   - `check_prereg_lock.py`: sha256 of canonical `sim_preregistration.json` equals `spec/PREREG_LOCK`; otherwise fail unless a decision record names the new hash.
5. `.github/workflows/ci.yml` per §3.4.

**Acceptance.** §3.4 commands all pass. `wf-field --help`, `wf-agent --help` and `wf-sim --help` print usage, even as stubs. `python scripts/check_prereg_lock.py` prints the locked hash `effcc97f…16f5fa`.
**Out of scope.** Any protocol logic.

### WP-1 — Core: models, canonical JSON, dynamics, similarity, routing · Wave A
**Objective.** All PROTOCOL math as pure, typed, property-tested functions over plain data.
**Invariants.** `INV-ID5, INV-DY1, INV-DY2, INV-DY4, INV-DY6, INV-DY7, INV-DY8, INV-RT1, INV-RT2, INV-RT3, INV-RT4, INV-RT5, INV-RT6`.
**Tasks.**
1. `canonical.py`: exactly PROTOCOL §1.3. Add `reject_floats(value)`.
2. `params.py`: a frozen `FieldParams` loaded from `spec/params.json` (package it as data, or load by path with a packaged copy, **[CONFIRM]** hatch data inclusion). Also `params_sha256` and `with_overrides({"trail.w_min": 1e-6, …})` for sim arms.
3. `models.py`: pydantic v2 models for every action body in PROTOCOL §5, with tag regex, limits from params, integer-only numerics, and hypothesis id rules. `sanitize.py`: PROTOCOL §9.2 (reject over-length; strip control and bidi characters) and §9.3 URL validation, purely syntactic (no DNS).
4. `views.py`: `TrustView(verifiers: frozenset, emitters: frozenset)`.
5. `entropy.py`, `dynamics.py`:
   - `decay`.
   - A decayed accumulator as an immutable `(value, t_ref_ms)` with `advance(t)` and `add(r, t)`. Never use absolute-epoch exponents (overflow).
   - Amplitude per §7.1 with the trusted/untrusted split.
   - Trail `W` per §7.3 with floors and clamps.
   - Closed-form `t_evap` per §7.2.
6. `similarity.py`: §7.4 with a `Similarity` protocol and a `LexicalSimilarity` default.
7. `routing.py`: `route(snapshot, intent, view, params, now) → RouteResult(entries, distribution)` per §7.5, and `sense(...)` per §7.6. `resonance.py`: `links_for(new_intent, open_intents)` per §7.1.
8. `projection.py`: a `FieldSnapshot` read model and a **pure** `apply_event(snapshot, event) → snapshot`. Maintain incremental per-(tag, agent) accumulators for the default view and per-intent amplitude accumulators, and support recomputing any custom view by fold. Incremental and fold results MUST be bit-identical for the default view: apply in the same order with the same accumulator code.

**Acceptance.** §3.4. Hypothesis property tests for every listed invariant. The test-vector tests for canonical bytes, entropy and decay pass. A micro-benchmark (marked `bench`, not in CI) shows `route` at 1,000 agents × 4 tags under the default view at ≤ 20 ms median on the Codex machine; report the number.
**Out of scope.** I/O, signatures, stores.

### WP-2 — Identity: keys, envelopes, signer · Wave A
**Objective.** Byte-exact signed writes per PROTOCOL §1.1 and §2.
**Invariants.** `INV-ID1, INV-ID2, INV-ID4`.
**Tasks.**
1. `keys.py`: generate, load and save Ed25519 keys (raw 32-byte seed file, mode 0600, created atomically); `agent_id(pubkey)`.
2. `envelope.py`: build, canonicalise, verify, and parse `signed_at` (accept `+00:00` and `Z`), plus nonce regex validation.
3. `signer.py`: a `FieldSigner` mirroring `AgentMarketSigner`'s ergonomics: `generate_ephemeral()`, `from_private_bytes()`, `public_key_b64`, `agent_id`, and `request(action, body, nonce=None, signed_at=None) → {envelope, pubkey, signature}`. The default nonce is `"nonce-" + uuid4().hex`; `identity/` may use uuid and time, `core/` may not.
4. Reproduce `spec/test_vectors.json` exactly.

**Acceptance.** §3.4. The test-vector test, the byte-flip property test and the skew boundary tests pass.
**Out of scope.** Nonce persistence (WP-3/4).

### WP-3 — Event store · Wave A
**Objective.** Append-only, hash-chained, durable event log with nonce and idempotency indexes.
**Invariants.** `INV-ID3, INV-ST1, INV-ST2, INV-ST4`.
**Tasks.**
1. `base.py`: an `EventStore` protocol with `append(event_core) → StoredEvent`, `iter_events(after_seq=0)`, `head()`, `has_nonce(actor, nonce)`, `get_idempotent(actor, key)`, and `close()`. Appending an event, its nonce and its idempotency record happens in **one** transaction.
2. `chain.py`: hashing per PROTOCOL §8 and `verify_chain(events) → bool`.
3. `memory.py`: an in-memory implementation for tests and sims.
4. `sqlite.py`: stdlib `sqlite3`; `PRAGMA journal_mode=WAL`, `synchronous=FULL`; tables `events`, `nonces(actor_id, nonce PK)` and `idempotency(actor_id, key PK, body_sha256, result_json)`; `BEFORE UPDATE` and `BEFORE DELETE` triggers on `events` that `RAISE(ABORT)`.

**Acceptance.** §3.4. A restart test (close, reopen, replay the nonce → rejected). A tamper test (drop the triggers on a raw connection, mutate each column, `verify_chain` → false). Pragma assertions.
**Out of scope.** Projection and business rules.

### WP-4 — FieldService · Wave A (end of wave)
**Objective.** The protocol state machine end to end, in process: signed write in → validated transition → event appended → projection updated; reads computed lazily at `now`.
**Invariants.** `INV-ID6, INV-DY3, INV-DY5, INV-RT7, INV-SM1, INV-SM2, INV-SM3, INV-SM5, INV-SM6, INV-ST3, INV-SF2, INV-SF3, INV-SF5`.
**Tasks.**
1. `service/clock.py` (`SystemClock`, `FakeClock`) and `service/config.py`: field key path, operator agent ids, default view lists, db path, and params path, loaded from a JSON config file plus env overrides.
2. `service/field.py`, class `FieldService`:
   - On init, write the genesis event (field agent_id, params_sha256, default-view hash) if the store is empty, then rebuild the projection.
   - `apply(request) → result | error` runs PROTOCOL §2.2 in order and then the action rules in §4–§6.
   - Writes that touch a terminal intent first append the lazy terminal event.
   - Reads: `sense`, `route`, `get_intent`, `list_intents`, `get_agent`, `events`, `metrics`; plus `sweep(now)`.
3. Verification in WP-4: the `digest` machine verifier only, behind the `verify/base.py` interface (`Verifier.kind`, `verify(intent, result) → Verdict`). The field signs machine verifications with its key.
4. `service/limits.py`: per-actor quotas (PROTOCOL §9.5), computed from the event log so they are deterministic and restart-safe. "Per minute" uses `server_ms` windows.
5. `service/metrics.py`: counts, collapse rate, median self-reported cost-to-collapse, and density buckets.
6. A Hypothesis `RuleBasedStateMachine` over random multi-agent op sequences (register, emit, signal, claim, submit pass/fail, withdraw, advance clock, sweep, restart-from-store) that asserts SM1, SM3, ST3, DY3 and DY5 after every step.

**Acceptance.** §3.4. The stateful test runs ≥ 200 examples in CI (`--hypothesis-profile=ci`). An end-to-end in-process test: A registers → B registers → A emits a `digest` intent → B senses it → B claims → B submits the wrong digest (result FAILED, intent stays OPEN, B's visible W stays at floor because of the clamp) → B submits the right digest → COLLAPSED → B's W on the intent tags rises above floor **iff** A ∈ V₀.emitters (run the test under both configurations). Write `docs/handoff/WAVE_A_HANDOFF.md`.
**Out of scope.** HTTP and MCP; json_schema and designated verifiers.

---

### WP-5 — Verifiers complete · Wave B
**Invariants.** `INV-SM4` (plus DY5 re-proved under designated verification).
**Tasks.**
1. `json_schema.py`: Draft 2020-12 via `jsonschema`, using a `referencing.Registry` that **cannot retrieve** remote resources (any remote `$ref` fails validation at emit time). Enforce the schema size limit. The artifact must be inline and must parse as JSON.
2. `designated.py`: the `verify` action flow (PROTOCOL §6): permission checks, evidence sanitisation, and FAIL keeps the intent OPEN.
3. Reject `lean` with `ValidationError("not_supported_v0_1")`.
4. A permission-matrix test over all actions × roles (emitter, doer, listed verifier, unlisted agent, field key, revoked agent).

**Acceptance.** §3.4. The sybil-verifier stream (verifier ∉ V₀) leaves W at floor. A remote `$ref` schema is rejected.

### WP-6 — Surfaces: HTTP API, field MCP, agent MCP · Wave B
**Invariants.** `INV-ID7, INV-SF1, INV-SF4, INV-SF6`.
**Tasks.**
1. `api/http.py`: a Starlette app with the routes in PROTOCOL §10.1. JSON errors use the taxonomy with status mapping ValidationError→400, PermissionError→403, ContextError→409, BudgetError→429, BackendError→503, RuntimeError→500 (but see INV-SF7). `api/manifest.py` serves the well-known manifest. `api/untrusted.py` holds the single wrapping function every output path uses.
2. `mcp/field_server.py`: `FastMCP` with the tools in PROTOCOL §10.2, mounted at `/mcp` (streamable HTTP) inside the same Starlette app, plus a stdio mode. **[CONFIRM]** the current `mcp` SDK mounting API (`streamable_http_app()` or its equivalent) and pin the minimum version that has it.
3. `mcp/agent_server.py` (`wf-agent`): the tools in PROTOCOL §10.3. It loads or creates the key (0600) and signs locally. It forwards to `WF_FIELD_URL` over `httpx` with timeouts and no redirects, enforces `WF_ALLOW_SIDE_EFFECTS` (comma list, default empty), and wraps foreign text.
   - Tool descriptions are static strings that include the data-not-instructions sentence and the public-content sentence.
4. `wf-field serve --config field.json --host 127.0.0.1 --port 8787`. It binds localhost by default.
5. `examples/two_agents_demo.py` runs the WP-4 end-to-end story over the HTTP API with two `wf-agent` tool layers in process (ASGI transport, no sockets). `examples/mcp_configs/` holds Claude Desktop / Claude Code and Codex config snippets for `wf-agent`.

**Acceptance.** §3.4. MCP tests use the SDK's in-memory client/server session. A key-leak scan over every captured output of the demo (INV-ID7). A walk of all outputs for bare foreign strings (INV-SF1).

### WP-7 — Simulator and preregistered runs · Wave B
**Invariants.** `INV-SIM1, INV-SIM2, INV-SIM3, INV-SIM4`.
**Tasks.**
1. `sim/`: build the world, scenarios S1–S3, arms, and policy exactly as `spec/sim_preregistration.json` specifies. Every write is a signed envelope applied to a `FieldService` over `MemoryStore` with a `FakeClock` (INV-SIM1). Only the sim owns RNG (`random.Random(seed)`, one stream per purpose, derived deterministically from the seed).
2. `stats.py`: Spearman with average ranks for ties, median and mean, each tested against hand-computed fixtures. `svg.py`: dependency-free scatter and line SVGs. `report.py` writes `report.md`, `report.json` (embedding the prereg sha256, params sha256 and git commit), `intents.csv`, `probe.csv` and plots.
3. `wf-sim run --scenario S1_steady|S2_shock|S3_sybil|all --seeds 1-10 --out results/v0.1/`, and `--quick` (≤ 120 steps, 2 seeds) for CI in under 60 s.
4. Run the **full** preregistered suite and commit `results/v0.1/`. Report each hypothesis as PASS, FAIL or INCONCLUSIVE exactly as measured. **Do not tune parameters after seeing results.** If a hypothesis fails, that is a valid result: write it up in `results/v0.1/report.md` § Discussion with candidate explanations and proposed follow-up experiments, and leave params untouched.
5. Performance: the full suite completes in ≤ 30 min. If it would not, profile and optimise the service (incremental accumulators, candidate prefilter) without changing semantics. Do not shrink the preregistered design.

**Acceptance.** §3.4. A determinism test (two quick runs, identical hashes). A tamper test for the prereg lock. Full-suite outputs committed. The PR body pastes the hypothesis table.

### WP-8 — Adversarial suite and threat model · Wave B (end of wave)
**Invariants.** `INV-SF7`. It also re-proves `INV-ID2/3/4, INV-DY5, INV-DY8, INV-RT6, INV-SF1/2/3/5` under attack.
**Tasks.** `docs/THREAT_MODEL.md`: a STRIDE table mapping threat → mitigation → invariant → test. `tests/adversarial/` covers:
- replay, cross-actor nonce reuse, skew, signature malleability;
- sybil rings (self-verifying, self-dealing, untrusted emitters) and resonance spam;
- lease squatting (many leases must not block results) and an ant-mill attempt (coordinated FAIL farming against an honest doer, which must be impossible without a trusted verifier);
- prompt-injection strings in every text field (asserted wrapped, never in tool descriptions), Trojan Source, oversized payloads;
- SSRF-style URLs, and Hypothesis fuzzing of every endpoint and tool (INV-SF7).

**Acceptance.** §3.4. Write `docs/handoff/WAVE_B_HANDOFF.md`.

---

### WP-9 — Fleet integration and rail adapters · Wave C
**Invariants.** `INV-FL1, INV-FL2, INV-FL3, INV-FL4`.
**Tasks.**
1. `fleet/agent.py`: the fleet contract (`async process(input)` dispatching on `input["action"]` ∈ {`sense`, `route`, `get_intent`, `list_intents`, `field_info`, `write`}; `async health()`; `describe()`). It never raises, returns the taxonomy envelope, adds `session_id` and `budget_consumed` to every output, and includes the full distribution and ψ on `route`. `fleet/agent.yaml` (version 0.1.0).
2. Adapters behind interfaces, each enabled only by env:
   - `TrustSource` from `agent-trust-oracle` (`score ≥ WF_TRUST_MIN_SCORE` joins V₀);
   - `IdentitySource` from `agent-identity-registry` (`resolve`; the pubkey must match, else exclude from route);
   - `CostSink` to `agent-compute-ledger`.

   Use in-process fakes in tests. **[CONFIRM]** each rail's action payload shapes against `fleet-mcp-services/contracts/*.md`. Do not call live endpoints.
3. A separate PR in `fleet-mcp-services` (branch `codex/wavefunction-field-contract`): update `contracts/wavefunction-search-agent.md` to describe this implementation, invariants and adapters. **Do not change the permission tier, gateway routing or deploy files.**

**Acceptance.** §3.4 in both repos (fleet repo: its own test suite stays green).

### WP-10 — Docs, examples, release readiness · Wave C (end of wave)
**Tasks.**
1. Full `README.md`: the problem, the honest positioning against the prior art in §1, a 5-minute quickstart (`wf-field serve` plus two `wf-agent` configs), the trust model in one diagram, and a link to `results/v0.1/report.md` with results stated exactly as measured.
2. `CHANGELOG.md` 0.1.0. `server.json` for the MCP Registry (namespace `io.github.jdhart81`, **[JUSTIN]** confirm) **prepared, not published**.
3. `docs/RELEASE_CHECKLIST.md`: the approvals Justin must give, each with the exact command or click to run: repo public; PyPI publish; MCP Registry publish; hosted reference field deploy behind the fleet gateway at `/field/mcp` (Fly.io); launch post.

**Acceptance.** §3.4. A clean-room test: fresh venv, `pip install .`, run the quickstart verbatim, and the demo passes. Write `docs/handoff/WAVE_C_HANDOFF.md`.

---

## 6. Handoff report format (end of each wave)

`docs/handoff/WAVE_<X>_HANDOFF.md`, also printed as Codex's final message:

```
# Wave <X> handoff — wavefunction-field
## PRs
| WP | branch | PR URL | head SHA | status (ready / draft-blocked) |
## Invariants
| id | test(s) proving it | result |
## Acceptance output
<trimmed output of every §3.4 command on the last branch of the wave>
## Benchmarks / measurements
<numbers with units, machine description>
## Deviations from spec
<each one: what, why, risk; or "none">
## [CONFIRM] resolutions
<each one: question → finding → evidence>
## Blockers / CODEX_NOTES
## Questions for Justin / Claude
## git diff --stat (wave total)
```

## 7. Open items for Justin (do not block Wave A)
1. **D1 owner org** for the GitHub repo (default `viridisconservation`).
2. **V₀ operator list:** which agent keys are admitted as trusted emitters and verifiers on the hosted field. v0.1 config ships empty except the field key.
3. **MCP Registry namespace** for the eventual listing (`io.github.jdhart81` assumed).
