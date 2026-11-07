# CODEX_NOTES — Wave A stop report

Date: 2026-11-07. Base: `main@384d16db13922e99847d026b4d73f529be6307a2`.

## WP-0 — validation environment blocker

The independent bootstrap scaffold is prepared, but WP-0 is incomplete. `completed_wps` remains empty. No protocol logic has been implemented. WP-1 through WP-4 have not started.

Evidence:

- The exact editable-install acceptance command fails installing `hatchling` because the execution environment cannot resolve the package-index host. The allowed Hypothesis package is absent. The available Ruff is 0.0.272, which cannot parse the modern lint configuration or run the required formatter.
- `pytest -q` exits 4 during conftest import (`ModuleNotFoundError: hypothesis`). This is not a test pass.
- Required console-entry-point checks cannot run because installation failed. The three stub modules print usage when invoked directly with `PYTHONPATH=src`.
- Strict mypy on core/identity and all six stdlib guardrail commands pass. Their source modules are intentionally empty; these checks do not establish protocol behavior.
- A browser download of the allowed build backend succeeded, but a subsequent package-file navigation was blocked by Chrome. No browser block or network protection was bypassed.

Options:

1. **Recommended:** Resume WP-0 in an execution environment with approved package-index and GitHub access; run every required command, then mark completed only after all pass.
2. Supply a trusted offline wheelhouse containing the allowlisted dependencies and their transitives; repeat the same checks without changing dependency policy.
3. Run the prepared CI on the draft branch, retain local acceptance as blocked until a suitable local toolchain is available. Remote CI does not replace the required local checks.

## WP-1 — normative resonance contradiction discovered before implementation

`docs/PROTOCOL.md` §7.1 requires linking a newly emitted intent to **every** sufficiently similar OPEN intent. `INV-RT5` requires symmetric links with degree at most `resonance.max_links_per_intent`, whose locked value is 16.

Counterexample: emit 18 identical tagged intents while all remain OPEN. Their lexical similarity is 1, above 0.6. The normative rule requires the complete graph K18, with 17 links per intent. Therefore no implementation can obey both rules. Eighteen writes fit within the 60/minute and 100-open-intent quotas.

Protocol remains authoritative. No cap, rejection policy, invariant, parameter or threshold has been changed. WP-1 and its dependents remain stopped.

Options for Justin / Claude:

1. **Recommended:** Approve a normative decision retaining the 16-link cap and specifying deterministic bounded linking, checking capacity at both endpoints, ranking by similarity descending then intent_id ascending. This changes the protocol's every-link requirement and needs explicit review.
2. Remove the cap normatively and retain every matching link. This increases memory and update costs with field size.
3. Reject emissions that would exceed any endpoint's capacity. This adds an admission rule and can reject otherwise valid goals; it needs explicit protocol authorization.

## WP-4 — sweep equivalence wording to resolve before implementation

`INV-DY3` asks for identical canonical projection and **all read results** whether or not sweep ran. Protocol §7.2 requires sweep to append an evaporation event, while §8 and §10.1 expose that event and the chain head. The audit stream necessarily differs.

Recommended review clarification: require equivalence of lifecycle/read models, rankings and semantic metrics; explicitly exclude audit events, sequence counts and chain metadata. Alternatives are to materialize the same terminal events on every read, or redefine the audit view; both alter the current read/write model. No interpretation has been silently implemented.

## Confirmations and immutable controls

- Remote repository name and private status were confirmed in GitHub UI; the local checkout is clean at the requested base.
- Gitleaks Action documentation requires a license for organization repositories. CI uses the expressly permitted official Docker CLI image instead: `ghcr.io/gitleaks/gitleaks:v8.30.1`. Sources: https://github.com/gitleaks/gitleaks-action/blob/master/README.md and https://github.com/gitleaks/gitleaks/pkgs/container/gitleaks/ . No license was provisioned. Container execution is not claimed as locally verified.
- Preregistration canonical SHA-256: `effcc97f82ba03c5753ae9d55dcfcf0eee599b9b7bf263631b9d26245c16f5fa` (matches lock).
- Params canonical SHA-256 without `$comment`: `10991006b2c282c7065af2d1ea8f78a2c258b1037c7daacdb52443a1ea56d873` (matches decision).
- Hatch data inclusion is WP-1 work and remains unresolved; no package-data assumption is made.
- The closed dependency list and all normative control files are unchanged.

## Resolved (2026-11-07, build manager)
- Environment blocker: the build moved to Claude's networked workspace. WP-0 fixes applied: ruff format, an IPv6-unavailable skip, dev-tool minimums and the matching check_deps / guardrail fixture.
- WP-1 resonance contradiction and WP-4 sweep wording: resolved by decision 0002 (C1, C2).
