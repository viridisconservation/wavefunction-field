# Release checklist — v0.1.0a1 (each step needs Justin's explicit go)

**Hosting decision (2026-11-07):** the field runs on the Viridis fleet gateway as the `wavefunction-search-agent` mount, at `https://mcp.viridisconservation.com/wavefunction` (MCP at `/wavefunction/mcp`, REST at `/wavefunction/v1`). That way every existing fleet listing picks it up.

| # | Step | How | Status |
|---|---|---|---|
| 1 | Merge this repo's build branch | PR from `claude/v0.1-build` into `main` | pending |
| 2 | Merge the open-core mount | `jdhart81/viridis-agent-fleet`, branch `claude/wavefunction-field-mount` (adapter, agent.yaml 0.3.0, vendored wheel, regenerated manifests and llms.txt) | pending |
| 3 | Merge the fleet release | `jdhart81/viridis-fleet-service` PR #71 (release script, AGENT_SEO listing text, golden fixture) | pending |
| 4 | Release on the droplet | `promote_wavefunction_field_20261107.py prepare --trust <your wf-agent id>` → `rehearse` → off-host backup receipt → `promote` (auto-rollback) | pending |
| 5 | Post-deploy | Live `check_version_coherence.py`; bump `OSS_PIN.json`; regenerate the Glama manifest | pending |
| 6 | Registry update | `mcp-publisher publish deploy/mcp-publish-github/wavefunction-search-agent/server.json` (0.3.0, same name and remote) | pending |
| 7 | Make this repo public | GitHub → Settings → Visibility | pending |
| 8 | PyPI (for `uvx wavefunction-field`) | `python -m build && twine upload dist/*`; then add `packages` to the registry entry | pending |
| 9 | Launch post | LinkedIn / WILDLABS from justin@viridisconservation.com, quoting `results/v0.1/report.md` exactly | pending |

`deploy/fly.toml` and the `Dockerfile` are kept for anyone who wants to run a standalone field. Viridis doesn't use them.
