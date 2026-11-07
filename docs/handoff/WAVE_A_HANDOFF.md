# Wave A handoff — wavefunction-field

**Status: BLOCKED; Wave A is incomplete.** Justin, no WP is marked complete. WP-0 scaffolding is preserved locally; the draft PR contains blocker documentation only. WP-1 through WP-4 were not started. WP-5 was not started.

## PRs

| WP | branch | PR URL | head SHA | status (ready / draft-blocked) |
|---|---|---|---|---|
| WP-0 | `codex/wp-0-bootstrap` → `main` | [PR #1](https://github.com/viridisconservation/wavefunction-field/pull/1) | `8f1448aaf95ab13fd750cfc61d5a96b79a87a30f` | draft-blocked |

Remote scope: `CODEX_NOTES.md` only (56 additions). The local bootstrap source snapshot is commit `153e650fbfd691e6c0d756039c5bd9cc43b733c8`, preserved in `/Users/justinhart/Desktop/Cowork /wavefunction /wavefunction-field-wave-a`. Its source was not pushed because shell GitHub DNS access failed. The remote note commit has a conventional subject and DCO sign-off.

The local and remote branches have different histories. Preserve the remote stop report when transferring the local scaffold; do not force-push over it. No dependent branches or PRs were opened because WP-0 acceptance is incomplete.

## Invariants

WP-0 has no protocol INV ids. Its six static guardrail commands pass on the local scaffold, and strict mypy passes on 17 empty core/identity source files. Full tests and formatting did not run successfully. None of these checks establishes implemented protocol behavior.

| id | test(s) proving it | result |
|---|---|---|
| INV-ID1 | Not implemented (WP-2) | Blocked / not run |
| INV-ID2 | Not implemented (WP-2) | Blocked / not run |
| INV-ID3 | Not implemented (WP-3) | Blocked / not run |
| INV-ID4 | Not implemented (WP-2) | Blocked / not run |
| INV-ID5 | Not implemented (WP-1) | Blocked / not run |
| INV-ID6 | Not implemented (WP-4) | Blocked / not run |
| INV-DY1 | Not implemented (WP-1) | Blocked / not run |
| INV-DY2 | Not implemented (WP-1) | Blocked / not run |
| INV-DY3 | Not implemented (WP-4) | Blocked / not run |
| INV-DY4 | Not implemented (WP-1) | Blocked / not run |
| INV-DY5 | Not implemented (WP-4) | Blocked / not run |
| INV-DY6 | Not implemented (WP-1) | Blocked / not run |
| INV-DY7 | Not implemented (WP-1) | Blocked / not run |
| INV-DY8 | Not implemented (WP-1) | Blocked / not run |
| INV-RT1 | Not implemented (WP-1) | Blocked / not run |
| INV-RT2 | Not implemented (WP-1) | Blocked / not run |
| INV-RT3 | Not implemented (WP-1) | Blocked / not run |
| INV-RT4 | Not implemented (WP-1) | Blocked / not run |
| INV-RT5 | Not implemented (WP-1) | Blocked / not run |
| INV-RT6 | Not implemented (WP-1) | Blocked / not run |
| INV-RT7 | Not implemented (WP-4) | Blocked / not run |
| INV-SM1 | Not implemented (WP-4) | Blocked / not run |
| INV-SM2 | Not implemented (WP-4) | Blocked / not run |
| INV-SM3 | Not implemented (WP-4) | Blocked / not run |
| INV-SM5 | Not implemented (WP-4) | Blocked / not run |
| INV-SM6 | Not implemented (WP-4) | Blocked / not run |
| INV-ST1 | Not implemented (WP-3) | Blocked / not run |
| INV-ST2 | Not implemented (WP-3) | Blocked / not run |
| INV-ST3 | Not implemented (WP-4) | Blocked / not run |
| INV-ST4 | Not implemented (WP-3) | Blocked / not run |
| INV-SF2 | Not implemented (WP-4) | Blocked / not run |
| INV-SF3 | Not implemented (WP-4) | Blocked / not run |
| INV-SF5 | Not implemented (WP-4) | Blocked / not run |

The local scaffold contains network-isolation, FakeClock, profile, ASGI and CLI tests in `tests/unit/test_bootstrap.py`, plus six guardrail mutation tests in `tests/unit/test_guardrails.py`. They await the required toolchain; full pytest did not collect. Hypothesis profiles are prepared at 500 local / 200 CI examples. No property or state-machine execution is claimed.

## Acceptance output

Trimmed actual output on the local bootstrap snapshot, using Python 3.11.5, Ruff 0.0.272 and mypy 1.3.0. These commands were run against the local source, not the remote documentation-only commit. Full output is in `docs/handoff/WP_0_ACCEPTANCE.txt` locally and trimmed output is in the PR body.

```text
$ python -m pip install -e ".[dev]"
Installing build dependencies: finished with status 'error'
Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known
ERROR: Could not find a version that satisfies the requirement hatchling (from versions: none)
ERROR: No matching distribution found for hatchling
exit_code: 1


$ ruff check . && ruff format --check .
error: TOML parse error at line 31, column 12
31 | [tool.ruff.lint]
unknown field `lint`
exit_code: 2


$ mypy --strict src/wavefunction_field/core src/wavefunction_field/identity
Success: no issues found in 17 source files
exit_code: 0


$ pytest -q
ImportError while loading conftest '/private/tmp/wavefunction-field-wave-a-20261107/tests/conftest.py'.
tests/conftest.py:12: in <module>
    from hypothesis import settings
E   ModuleNotFoundError: No module named 'hypothesis'
exit_code: 4


$ python scripts/check_traceability.py
traceability: PASS
exit_code: 0


$ python scripts/check_deps.py
dependencies: PASS (closed direct runtime/dev/build allowlist)
exit_code: 0


$ python scripts/check_claims.py
claims: PASS
exit_code: 0


$ python scripts/check_headers.py
headers: PASS
exit_code: 0


$ python scripts/check_core_purity.py
core purity: PASS
exit_code: 0


$ python scripts/check_prereg_lock.py
preregistration: PASS effcc97f82ba03c5753ae9d55dcfcf0eee599b9b7bf263631b9d26245c16f5fa
exit_code: 0
```

All three installed entry-point help checks failed with `command not found` (exit 127) because editable installation failed. Direct module invocations print the three expected usage messages; those are supplementary checks and do not replace installation acceptance.

## Benchmarks / measurements

- `route`, 1,000 agents × 4 tags: **not run; no timing number available**. WP-1 routing was not implemented, so the ≤20 ms target is unmeasured.
- Local host: macOS 26.7.1, arm64; acceptance interpreter Python 3.11.5.
- Independent fixture sanity, using stdlib and installed cryptography: canonical bytes, SHA-256, public key, agent ID and Ed25519 signature match the frozen test vector. This is a fixture audit, not a passing implementation test.
- Params hash without `$comment`: `10991006b2c282c7065af2d1ea8f78a2c258b1037c7daacdb52443a1ea56d873`.
- Preregistration canonical hash: `effcc97f82ba03c5753ae9d55dcfcf0eee599b9b7bf263631b9d26245c16f5fa`.

## Deviations from spec

1. WP-0 cannot be marked complete: dependency installation fails through blocked DNS, Hypothesis is absent, and the available Ruff cannot perform the required checks. Risk: the prepared bootstrap is unvalidated beyond the reported static checks.
2. The draft PR contains the stop report, while bootstrap source and full acceptance logs remain local. Git push failed with `Could not resolve host: github.com`. Risk: source needs transfer and full validation before review as an implementation PR.
3. The handoff is local rather than in a WP-4 PR because the explicit stop rule prevented reaching WP-4. No completed-WP entry, normative edit, threshold relaxation or alternate protocol behavior was introduced.

## [CONFIRM] resolutions

- Repository/base → private repository and `main@384d16d` confirmed in GitHub UI and the clean original checkout.
- Gitleaks organization license → official Action documentation requires one; the local CI scaffold selects the expressly permitted official Docker CLI image `ghcr.io/gitleaks/gitleaks:v8.30.1`. No license was provisioned and no container pass is claimed. [Official documentation](https://github.com/gitleaks/gitleaks-action/blob/master/README.md).
- Hatch package-data inclusion → unresolved; this belongs to unstarted WP-1 and needs an installed-wheel inclusion/readback check before implementation proceeds.

## Blockers / CODEX_NOTES

1. **Local toolchain/network:** exact editable installation fails retrieving Hatchling; Hypothesis is missing; installed Ruff 0.0.272 lacks the required configuration/formatter support. Recommended resolution: an execution environment with approved package-index/GitHub access. Alternatives: a trusted offline wheelhouse; CI as supplementary evidence while local checks remain blocked.
2. **WP-1 normative contradiction:** PROTOCOL §7.1 requires every sufficiently similar OPEN intent to be linked; `INV-RT5` requires symmetric degree ≤16. Eighteen identical OPEN intents require K18, degree 17. Recommended decision: retain the cap and specify deterministic bounded linking, checking capacity at both endpoints and ordering by similarity descending then intent ID ascending. Alternatives: remove the cap; authorize rejecting capacity-exceeding emissions. No option was implemented.
3. **WP-4 wording conflict:** `INV-DY3` requires all reads to match with/without sweep, while sweep appends an event exposed by `events` and the chain head. Recommended clarification: lifecycle/read models and rankings must match; audit events and log metadata are excluded. Alternatives change read materialization or audit-view semantics.

Details and options are recorded in [the draft stop report](https://github.com/viridisconservation/wavefunction-field/blob/codex/wp-0-bootstrap/CODEX_NOTES.md). Immutable controls and `completed_wps=[]` are unchanged. Main was not pushed or merged; no release, publication, visibility change, deployment or live Viridis endpoint call occurred.

## Questions for Justin / Claude

1. Approve the recommended bounded-resonance rule through a normative decision, or select one of the two alternatives before WP-1.
2. Clarify whether sweep equivalence excludes audit events and chain metadata before WP-4.
3. Resume WP-0 with the allowed dependencies and current developer tools available; all acceptance commands must pass before advancing.

## git diff --stat (wave total)

Remote draft (documentation only):

```text
 CODEX_NOTES.md | 56 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 56 insertions(+)
```

Local bootstrap and handoff, compared with `384d16d` (not pushed):

```text
 .github/workflows/ci.yml                           |  83 +++++++
 .gitignore                                         |  14 ++
 CHANGELOG.md                                       |   5 +
 CODEX_NOTES.md                                     |  50 ++++
 CONTRIBUTING.md                                    |  17 ++
 LICENSE                                            | 202 ++++++++++++++++
 NOTICE                                             |   5 +
 README.md                                          |  26 +++
 SECURITY.md                                        |   5 +
 docs/handoff/WAVE_A_HANDOFF.md                     | 259 +++++++++++++++++++++
 docs/handoff/WP_0_ACCEPTANCE.txt                   |  84 +++++++
 examples/mcp_configs/.gitkeep                      |   0
 examples/two_agents_demo.py                        |   2 +
 pyproject.toml                                     |  42 ++++
 results/v0.1/.gitkeep                              |   0
 scripts/__init__.py                                |   2 +
 scripts/check_claims.py                            |  58 +++++
 scripts/check_core_purity.py                       |  90 +++++++
 scripts/check_deps.py                              |  60 +++++
 scripts/check_headers.py                           |  35 +++
 scripts/check_prereg_lock.py                       |  55 +++++
 scripts/check_traceability.py                      |  55 +++++
 src/wavefunction_field/__init__.py                 |   2 +
 src/wavefunction_field/api/__init__.py             |   2 +
 src/wavefunction_field/api/http.py                 |   2 +
 src/wavefunction_field/api/manifest.py             |   2 +
 src/wavefunction_field/api/untrusted.py            |   2 +
 src/wavefunction_field/core/__init__.py            |   2 +
 src/wavefunction_field/core/canonical.py           |   2 +
 src/wavefunction_field/core/dynamics.py            |   2 +
 src/wavefunction_field/core/entropy.py             |   2 +
 src/wavefunction_field/core/errors.py              |   2 +
 src/wavefunction_field/core/models.py              |   2 +
 src/wavefunction_field/core/params.py              |   2 +
 src/wavefunction_field/core/projection.py          |   2 +
 src/wavefunction_field/core/resonance.py           |   2 +
 src/wavefunction_field/core/routing.py             |   2 +
 src/wavefunction_field/core/sanitize.py            |   2 +
 src/wavefunction_field/core/similarity.py          |   2 +
 src/wavefunction_field/core/views.py               |   2 +
 src/wavefunction_field/fleet/__init__.py           |   2 +
 src/wavefunction_field/fleet/adapters/__init__.py  |   2 +
 .../fleet/adapters/compute_ledger.py               |   2 +
 .../fleet/adapters/identity_registry.py            |   2 +
 .../fleet/adapters/trust_oracle.py                 |   2 +
 src/wavefunction_field/fleet/agent.py              |   2 +
 src/wavefunction_field/fleet/agent.yaml            |   2 +
 src/wavefunction_field/identity/__init__.py        |   2 +
 src/wavefunction_field/identity/envelope.py        |   2 +
 src/wavefunction_field/identity/keys.py            |   2 +
 src/wavefunction_field/identity/signer.py          |   2 +
 src/wavefunction_field/mcp/__init__.py             |   2 +
 src/wavefunction_field/mcp/agent_config.py         |   2 +
 src/wavefunction_field/mcp/agent_server.py         |  15 ++
 src/wavefunction_field/mcp/field_server.py         |  15 ++
 src/wavefunction_field/service/__init__.py         |   2 +
 src/wavefunction_field/service/clock.py            |   2 +
 src/wavefunction_field/service/config.py           |   2 +
 src/wavefunction_field/service/field.py            |   2 +
 src/wavefunction_field/service/limits.py           |   2 +
 src/wavefunction_field/service/metrics.py          |   2 +
 src/wavefunction_field/sim/__init__.py             |   2 +
 src/wavefunction_field/sim/cli.py                  |  15 ++
 src/wavefunction_field/sim/report.py               |   2 +
 src/wavefunction_field/sim/run.py                  |   2 +
 src/wavefunction_field/sim/scenarios.py            |   2 +
 src/wavefunction_field/sim/stats.py                |   2 +
 src/wavefunction_field/sim/svg.py                  |   2 +
 src/wavefunction_field/sim/world.py                |   2 +
 src/wavefunction_field/store/__init__.py           |   2 +
 src/wavefunction_field/store/base.py               |   2 +
 src/wavefunction_field/store/chain.py              |   2 +
 src/wavefunction_field/store/memory.py             |   2 +
 src/wavefunction_field/store/sqlite.py             |   2 +
 src/wavefunction_field/verify/__init__.py          |   2 +
 src/wavefunction_field/verify/base.py              |   2 +
 src/wavefunction_field/verify/designated.py        |   2 +
 src/wavefunction_field/verify/digest.py            |   2 +
 src/wavefunction_field/verify/json_schema.py       |   2 +
 tests/adversarial/__init__.py                      |   1 +
 tests/api/__init__.py                              |   1 +
 tests/conftest.py                                  |  85 +++++++
 tests/fleet/__init__.py                            |   1 +
 tests/mcp/__init__.py                              |   1 +
 tests/property/__init__.py                         |   1 +
 tests/service/__init__.py                          |   1 +
 tests/sim/__init__.py                              |   1 +
 tests/unit/__init__.py                             |   1 +
 tests/unit/test_bootstrap.py                       | 102 ++++++++
 tests/unit/test_guardrails.py                      | 124 ++++++++++
 90 files changed, 1621 insertions(+)
```
