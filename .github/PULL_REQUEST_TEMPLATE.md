## What and why
<!-- One paragraph. Link the issue. -->

## Invariants touched
<!-- List INV-* ids (spec/invariants.json) and the tests that cover them, or "none". -->

## Protocol / params / thresholds
- [ ] No normative change (PROTOCOL.md, spec/*) — or a decision record is included in docs/decisions/

## Checks (paste output)
```
ruff check / ruff format --check:
mypy --strict:
pytest -q:
scripts/check_*.py:
```

- [ ] Every commit is signed off (`git commit -s`)
- [ ] No secrets, personal data or unsupported claims (quantum, energy, carbon savings)
