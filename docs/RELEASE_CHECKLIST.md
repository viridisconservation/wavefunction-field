# Release checklist — v0.1.0a1 (each step needs Justin's explicit go)

| # | Step | Command / click | Status |
|---|---|---|---|
| 1 | Merge the build branch | Review the PR from `claude/v0.1-build` into `main`, then merge | pending |
| 2 | Choose the default trust view **before first boot** | Pick the agent ids for `WF_TRUSTED_EMITTERS` / `WF_OPERATORS`. The view is fixed at genesis | pending |
| 3 | Deploy the hosted field (standalone Fly app) | `fly launch --no-deploy --copy-config --config deploy/fly.toml` → `fly volumes create wf_data --size 1 --region bos --config deploy/fly.toml` → `fly secrets set WF_TRUSTED_EMITTERS=… WF_OPERATORS=… --config deploy/fly.toml` → `fly deploy --config deploy/fly.toml` | pending |
| 3b | Or route through the fleet gateway | Add a `/field` upstream to the gateway Caddyfile pointing at the field app; set `WF_PUBLIC_URL=https://mcp.viridisconservation.com/field` | alternative |
| 4 | Smoke-test production | `curl -s $URL/healthz` and `curl -s $URL/.well-known/wavefunction-field.json`, then point `wf-agent` at `$URL` and run `field_info` | pending |
| 5 | Make the repo public | GitHub → Settings → Change visibility | pending |
| 6 | Publish to PyPI | `python -m build && twine upload dist/*` (name `wavefunction-field`; check that it is free) | pending |
| 7 | List in the MCP Registry | Update `server.json` with the final remote URL, then `mcp-publisher login github && mcp-publisher publish` (namespace `io.github.jdhart81`) | pending |
| 8 | Fleet contract | Copy `docs/fleet/wavefunction-search-agent.md` into `fleet-mcp-services/contracts/` via PR | pending |
| 9 | Launch post | LinkedIn / WILDLABS from justin@viridisconservation.com, citing results exactly as in `results/v0.1/report.md` | pending |
