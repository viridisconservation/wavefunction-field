# wavefunction-field

**PRE-ALPHA — bootstrap under review; no usable field service yet.**

An open-source reference implementation of the [Wavefunction Field Protocol](docs/PROTOCOL.md): an MCP intent field for AI agents, with decaying attention and trust-scoped outcome trails.

## Terminology

"Wavefunction", "superposition", "collapse", "resonance/entanglement" and "pheromone" are **metaphors and brand terms**. The mathematics is classical: discrete probability distributions, Shannon entropy, exponential decay and ant-colony-optimization (ACO) scoring. No document, README, tool description or report may claim quantum behaviour, physical energy measurement, "proven alignment" or energy savings unless a named artifact in this repository measures it. `[G5]`

## Development

Use Python 3.11 or newer in a virtual environment:

```bash
python -m pip install -e ".[dev]"
wf-field --help
wf-agent --help
wf-sim --help
```

The three commands are usage stubs in WP-0. See [CONTRIBUTING.md](CONTRIBUTING.md) for checks, DCO and branch rules. All field content will be public by design. Do not post secrets or personal data.

## Build status

The specification in [CODEX_BUILD_SPEC.md](CODEX_BUILD_SPEC.md) defines the work packages and acceptance gates. Only passing work packages appear in [spec/BUILD_STATE.json](spec/BUILD_STATE.json).
