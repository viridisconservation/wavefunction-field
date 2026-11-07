# Contributing

This pre-alpha repository follows AGENTS.md and CODEX_BUILD_SPEC.md. PROTOCOL.md is normative. Open one branch and PR per work package; stacked PRs target the previous work package branch. Do not merge or publish from a build-agent session.

Use conventional commit subjects and sign off every commit with the Developer Certificate of Origin, Version 1.1: https://developercertificate.org/.

```bash
git commit --signoff -m "chore: describe the change"
```

The sign-off certifies your right to contribute under the Apache-2.0 license. Add `SPDX-License-Identifier: Apache-2.0` to source files.

Run every acceptance command from CODEX_BUILD_SPEC.md §3.4 before opening a ready PR. Paste the actual command outputs into the PR using the §0.6 template. A blocked work package stays incomplete and opens a draft PR with CODEX_NOTES.md.

Hypothesis uses the `local` profile (at least 500 examples) by default. CI selects `--hypothesis-profile=ci` (at least 200 examples). Benchmarks marked `bench` are excluded from ordinary pytest runs; select them with `pytest -m bench`.

Use generated test keys only in temporary directories. Tests prohibit network sockets; use Unix sockets or in-process transports. No normative protocol, parameter, invariant or experiment-threshold changes without an approved decision record.
