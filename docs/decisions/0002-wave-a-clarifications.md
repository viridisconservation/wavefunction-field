# 0002 — Wave A clarifications

**Date:** 2026-11-07 · **Author:** Claude (build manager) · **Status:** Proposed. Justin accepts it by merging the WP-0 PR that contains this file.
**Trigger:** the Codex Wave A stop report (`CODEX_NOTES.md`, PR #1) plus a build-manager review of WP-1–WP-4 ahead of implementation.
**Hashes:** `spec/params.json` and `spec/sim_preregistration.json` are **unchanged**. Their locked hashes from decision 0001 still hold.

| # | Issue | Resolution | Files |
|---|---|---|---|
| C1 | PROTOCOL §7.1 linked a new intent to *every* similar OPEN intent, while INV-RT5 capped degree at 16. 18 identical intents need K18 (degree 17). Found by Codex. | **Keep the cap.** Use deterministic bounded linking: candidates are OPEN intents with `sim_ii ≥ θ_res`, visited by sim descending then `intent_id` ascending, and linked iff both endpoints are below the cap. `deg` counts every recorded link (links are permanent). Codex's option 1, made precise. | PROTOCOL §7.1, INV-RT5 |
| C2 | INV-DY3 required "all read results" to match with or without sweep, but sweep appends audit events. Found by Codex. | Equivalence covers the projection, all object fields and get_intent, list_intents, get_agent, sense, route and metrics. It excludes `/v1/events`, seq, event counts and chain metadata. The projection and metrics carry no counts, seq or hashes. | PROTOCOL §7.2, INV-DY3 |
| C3 | INV-RT2's monotonicity broke for agents outside the η-prefiltered candidate set and for raises absorbed by the w_max clamp. | Scope the rule to candidate-set agents and effective raises. | PROTOCOL §7.5, INV-RT2 |
| C4 | INV-DY1's "unclamped sum" was ambiguous because the untrusted cap is a `min`. | Exact decay applies to `S_trusted` and to the raw pre-cap untrusted sum `U` separately; caps apply afterwards. | PROTOCOL §7.1, INV-DY1 |
| C5 | The verify-window hold in evaporation was underspecified. | `hold(i,t)` holds iff a result is SUBMITTED at `t` and `t < t_submit + verify_window_s`. TTL ignores holds. A verification that ends the last hold after the amplitude has fallen sets `t_evap` to that verification's `server_ms`. | PROTOCOL §7.2 |
| C6 | "Qualifying" meant two things: lifecycle collapse and trail reinforcement. | Lifecycle uses **permitted** (the verifier is allowed for the acceptance kind, independent of trust). Trails use **qualifying** (trust-view dependent). | PROTOCOL §4, INV-SM2 |
| C7 | The field key's status as an agent was unspecified. | It is recorded at genesis but never routable, and it cannot emit, deposit or submit results. | PROTOCOL §1.1, INV-RT7 |
| C8 | §2.2 checked the nonce before idempotency, so a byte-identical retry was rejected as a replay. That contradicted the purpose of idempotency keys and the agent-market behaviour. | Check idempotency (rule 7) before the nonce (rule 8). An identical body returns the original result whatever the nonce. Idempotent returns don't consume quota. | PROTOCOL §2.2, INV-ID3, INV-ID6 |
| C9 | Wave A ran in a shell with no network: it fell back to a stale global Ruff 0.0.272, pip installs failed, and a browser was used to fetch packages. | Add a network preflight that stops at once if PyPI or GitHub is unreachable. Set dev-tool minimums (`pytest>=8`, `hypothesis>=6.100`, `ruff>=0.6`, `mypy>=1.11`), always run tools as `python -m` from the project venv, and never fetch packages through a browser. | CODEX_BUILD_SPEC §3.3–3.4, AGENTS.md |

## Build-manager validation of the WP-0 scaffold (commit f5ab8d7)
I ran the full §3.4 suite in a fresh venv with network (Linux, Python 3.13; mcp 1.30.0, ruff 0.17.4, mypy 2.4.1, pytest 9.2.0, hypothesis 6.170.15):
- **Pass:** ruff check, strict mypy (17 files), all six guardrail scripts, and the three `--help` entry points.
- **Fail:** `ruff format --check` wants to reformat 5 files. In pytest, 20 of 22 pass. The 2 failures are `test_connections_on_existing_socket_classes_are_blocked[AF_INET6-*]`: the host cannot create AF_INET6 sockets (`OSError EAFNOSUPPORT`), and the test must skip in that case rather than fail.

The scaffold needs no other changes before WP-0 can be marked complete.
