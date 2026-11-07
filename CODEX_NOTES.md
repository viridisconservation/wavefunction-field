# CODEX_NOTES — Wave A stop report

Date: 2026-11-07. Base: main@384d16db13922e99847d026b4d73f529be6307a2.

## WP-0: local validation blocked

The bootstrap scaffold is prepared locally, but WP-0 is incomplete. completed_wps remains empty. This draft contains the stop report only: the local source commit 153e650 has not been pushed because the shell cannot resolve github.com. No protocol logic was implemented. WP-1 through WP-4 have not started.

Evidence from the exact acceptance commands:

- python -m pip install -e ".[dev]": exit 1; build dependency hatchling cannot be retrieved because package-index DNS/network access fails.
- ruff check . && ruff format --check .: exit 2; installed Ruff 0.0.272 rejects [tool.ruff.lint] and lacks the required formatter.
- mypy --strict src/wavefunction_field/core src/wavefunction_field/identity: exit 0, Success: no issues found in 17 source files. Modules are empty scaffolding, not implemented protocol behavior.
- pytest -q: exit 4 during conftest import, ModuleNotFoundError: hypothesis. No tests are claimed passing.
- python scripts/check_traceability.py: exit 0, traceability: PASS.
- python scripts/check_deps.py: exit 0, dependencies: PASS (closed direct runtime/dev/build allowlist).
- python scripts/check_claims.py: exit 0, claims: PASS.
- python scripts/check_headers.py: exit 0, headers: PASS.
- python scripts/check_core_purity.py: exit 0, core purity: PASS.
- python scripts/check_prereg_lock.py: exit 0, preregistration: PASS effcc97f82ba03c5753ae9d55dcfcf0eee599b9b7bf263631b9d26245c16f5fa.
- wf-field --help, wf-agent --help, wf-sim --help: each exit 127 because installation failed. All three stub modules print usage when invoked directly with PYTHONPATH=src. This does not substitute for the console-entry-point checks.

Options:

1. Recommended: resume WP-0 with approved package-index and GitHub access, then run every required local command before marking completed.
2. Supply a trusted offline wheelhouse for the allowlisted dependencies and their transitives, then repeat unchanged acceptance checks.
3. Run CI after transferring the scaffold to the draft branch; keep local acceptance blocked until a suitable local toolchain is available. CI does not replace the required local checks.

## WP-1: normative resonance contradiction

PROTOCOL section 7.1 requires linking a new intent to EVERY sufficiently similar OPEN intent. INV-RT5 requires symmetric links with degree at most resonance.max_links_per_intent, whose locked value is 16.

Counterexample: emit 18 identical tagged intents while all stay OPEN. Their similarity is 1, above theta_res=0.6. The normative rule requires the complete graph K18, with 17 links per intent, violating the cap of 16. Eighteen writes fit within 60 writes/minute and 100 open intents. These requirements cannot both be met.

PROTOCOL remains authoritative. No normative files, parameters, invariant or threshold were changed. WP-1 and dependent WPs are stopped.

Options for Justin / Claude:

1. Recommended: approve a normative decision retaining the 16-link cap and specifying deterministic bounded linking, checking capacity at BOTH endpoints and ranking by similarity descending then intent_id ascending. This changes the every-link requirement and needs approval.
2. Remove the cap normatively and keep every matching link. Memory and update costs then grow with field size.
3. Reject emissions that would exceed either endpoint capacity. This adds an admission rule and may reject otherwise valid goals; explicit protocol approval is required.

## WP-4: sweep-equivalence wording

INV-DY3 requires identical canonical projection and ALL read results with or without sweep. PROTOCOL section 7.2 requires sweep to append an evaporation event, and sections 8 and 10.1 expose events and the chain head. The audit stream necessarily differs.

Recommended clarification: equivalence applies to lifecycle/read models, rankings and semantic metrics, excluding audit events, sequence counts and chain metadata. Alternatives are materializing the same events on every read or redefining the audit view; both alter the current read/write model. No interpretation has been implemented.

## Confirmations and immutable controls

- The private repository and base SHA were confirmed in GitHub UI.
- Gitleaks Action documentation requires a license for organization repositories. The local CI scaffold uses the permitted official Docker CLI image ghcr.io/gitleaks/gitleaks:v8.30.1 instead. No license or live endpoint was used. Source: https://github.com/gitleaks/gitleaks-action/blob/master/README.md .
- Preregistration canonical SHA-256 matches effcc97f82ba03c5753ae9d55dcfcf0eee599b9b7bf263631b9d26245c16f5fa.
- Params canonical SHA-256 without $comment matches 10991006b2c282c7065af2d1ea8f78a2c258b1037c7daacdb52443a1ea56d873.
- Hatch package-data inclusion remains unresolved WP-1 work.
- No completed work package, benchmark, passing full suite, remote implementation, merge, release or deployment is claimed.
