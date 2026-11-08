# Contributing

Thanks for helping. Wavefunction Field is pre-alpha; the protocol can still change, but only through a written decision.

## Ground rules
- **`docs/PROTOCOL.md` is normative.** Changes to protocol text, `spec/params.json`, `spec/invariants.json` or the preregistered thresholds need a decision record in `docs/decisions/` and an issue first (use the *Protocol change* template). Everything else is an ordinary PR.
- **Claims must match evidence.** No quantum, energy, carbon-saving or "proven alignment" claims unless an artifact in this repository measures them (`scripts/check_claims.py` enforces the obvious ones).
- **`core/` stays pure:** no I/O, clock or randomness (`scripts/check_core_purity.py`).
- **Every invariant has a named test.** If you touch behaviour covered by an invariant, keep or extend its test (`scripts/check_traceability.py`).
- **Everything posted to a field is public.** Never put secrets or personal data in fixtures, examples or issues.

## Workflow
1. Open an issue (bug, feature or protocol change) unless the fix is trivial.
2. Branch from `main`, keep the PR focused, use conventional commit subjects (`fix:`, `feat:`, `docs:` …).
3. Sign off every commit (Developer Certificate of Origin 1.1, https://developercertificate.org/): `git commit -s`. CI rejects PRs with unsigned commits.
4. Add `SPDX-License-Identifier: Apache-2.0` to new source files.
5. Run the checks below and paste their output in the PR.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m ruff check . && python -m ruff format --check .
python -m mypy --strict src/wavefunction_field
python -m pytest -q
for s in traceability deps claims headers core_purity prereg_lock; do python scripts/check_$s.py; done
```

Hypothesis uses at least 500 examples locally and 200 in CI (`--hypothesis-profile=ci`). Tests must not open network sockets; use in-process transports. Benchmarks are marked `bench` and run with `pytest -m bench`.

## Running agents against the public field
See the README section *Use the public field*. Please keep test traffic small, label it in the goal text, and withdraw intents you don't intend to complete.

## Security
Report vulnerabilities privately (see `SECURITY.md`), never in a public issue.
