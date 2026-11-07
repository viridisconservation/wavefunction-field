# SPDX-License-Identifier: Apache-2.0
"""``wf-sim``: run the preregistered simulation suite."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from wavefunction_field.core.canonical import digest


def _seeds(text: str) -> list[int]:
    if "-" in text:
        a, b = text.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="wf-sim", description="Run the preregistered WFP simulations."
    )
    sub = parser.add_subparsers(dest="cmd")
    run = sub.add_parser("run", help="run scenarios and write a report")
    run.add_argument(
        "--scenario",
        default="all",
        choices=["all", "S1_steady", "S2_shock", "S3_sybil"],
    )
    run.add_argument("--seeds", default=None, help="e.g. 1-10 or 1,2")
    run.add_argument("--out", default="results/run")
    run.add_argument(
        "--quick",
        action="store_true",
        help="120 steps, 2 seeds (smoke test, not evidence)",
    )
    run.add_argument("--jobs", type=int, default=1)
    run.add_argument("--prereg", default="spec/sim_preregistration.json")
    run.add_argument("--commit", default=os.environ.get("WF_COMMIT", "unknown"))
    args = parser.parse_args(argv)
    if args.cmd != "run":
        parser.print_help()
        return
    from wavefunction_field.service.config import default_params_mapping
    from wavefunction_field.sim import report
    from wavefunction_field.sim.run import evaluate, run_all

    prereg: dict[str, Any] = json.loads(Path(args.prereg).read_text())
    params_raw = default_params_mapping()
    seeds = (
        _seeds(args.seeds)
        if args.seeds
        else ([1, 2] if args.quick else list(prereg["seeds"]))
    )
    steps = 120 if args.quick else prereg["time"]["steps"]
    scenarios = list(prereg["scenarios"]) if args.scenario == "all" else [args.scenario]
    t0 = time.monotonic()
    results = run_all(
        prereg, params_raw, scenarios, seeds, steps if args.quick else None, args.jobs
    )
    shock_step = (
        steps // 2
        if args.quick
        else prereg["scenarios"]["S2_shock"]["shock"]["at_step"]
    )
    ev = evaluate(prereg, results, seeds, steps, shock_step)
    meta = {
        "seeds": seeds,
        "steps": steps,
        "scenarios": scenarios,
        "full": not args.quick,
        "warmup": prereg["time"]["warmup_steps"],
        "params_sha256": digest(
            {k: v for k, v in params_raw.items() if k != "$comment"}
        ),
        "commit": args.commit,
    }
    report.write(Path(args.out), results, ev, meta)
    print(
        json.dumps(
            {
                k: v.get("verdict")
                for k, v in ev.items()
                if isinstance(v, dict) and "verdict" in v
            }
        )
    )
    print(f"wall_s={time.monotonic() - t0:.1f}", flush=True)


if __name__ == "__main__":
    main()
