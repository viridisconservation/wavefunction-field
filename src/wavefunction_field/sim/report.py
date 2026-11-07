# SPDX-License-Identifier: Apache-2.0
"""Write report.md / report.json / CSVs / SVG plots. Units: self-reported tokens."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from wavefunction_field.sim import stats
from wavefunction_field.sim.svg import chart

INTENT_COLS = [
    "scenario",
    "arm",
    "seed",
    "step",
    "intent_id",
    "tags",
    "density_at_emit",
    "H_bits",
    "attempts",
    "cost_to_collapse_tokens",
    "collapsed",
    "sybil_mass",
]
PROBE_COLS = ["scenario", "arm", "seed", "step", "E_s", "newcomer_share"]


def _csv(rows: list[dict[str, Any]], cols: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: (repr(r[c]) if isinstance(r[c], float) else r[c]) for c in cols})
    return buf.getvalue()


def _binned(
    rows: list[dict[str, Any]], steps: int, bins: int = 40
) -> list[tuple[float, float]]:
    size = max(1, steps // bins)
    out = []
    for b in range(0, steps, size):
        vals = [r["cost_to_collapse_tokens"] for r in rows if b <= r["step"] < b + size]
        if vals:
            out.append((b + size / 2, stats.mean(vals)))
    return out


def write(
    out_dir: Path,
    results: list[dict[str, Any]],
    evaluation: dict[str, Any],
    meta: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for res in results for r in res["rows"]]
    probe = [p for res in results for p in res["probe"]]
    (out_dir / "intents.csv").write_text(_csv(rows, INTENT_COLS))
    (out_dir / "probe.csv").write_text(_csv(probe, PROBE_COLS))
    report = {"meta": meta, "hypotheses": evaluation}
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    steps = meta["steps"]
    arms = sorted({(r["scenario"], r["arm"]) for r in rows})
    s1 = [
        (
            arm,
            _binned(
                [r for r in rows if r["scenario"] == sc and r["arm"] == arm], steps
            ),
        )
        for sc, arm in arms
        if sc == "S1_steady"
    ]
    if s1:
        (out_dir / "s1_cost_over_time.svg").write_text(
            chart(
                "S1: mean self-reported tokens to collapse (all seeds)",
                s1,
                "step",
                "tokens",
            )
        )
        wfp = [
            r
            for r in rows
            if r["scenario"] == "S1_steady"
            and r["arm"] == "WFP"
            and r["step"] >= meta["warmup"]
        ]
        (out_dir / "s1_density_vs_cost.svg").write_text(
            chart(
                "S1 WFP: density at emit vs tokens to collapse",
                [
                    (
                        "WFP",
                        [
                            (r["density_at_emit"], r["cost_to_collapse_tokens"])
                            for r in wfp
                        ],
                    )
                ],
                "density_at_emit",
                "tokens",
                scatter=True,
            )
        )
    if probe:
        series = []
        for arm in sorted({p["arm"] for p in probe}):
            by_step: dict[int, list[float]] = {}
            for p in probe:
                if p["arm"] == arm:
                    by_step.setdefault(p["step"], []).append(p["E_s"])
            series.append(
                (arm, [(float(s), stats.mean(v)) for s, v in sorted(by_step.items())])
            )
        (out_dir / "s2_expected_success_probe.svg").write_text(
            chart(
                "S2: expected success of routing for t00 (mean over seeds)",
                series,
                "step",
                "E_s",
            )
        )
    s3 = [
        (
            arm,
            [
                (
                    float(s),
                    stats.mean(
                        [
                            r["sybil_mass"]
                            for r in rows
                            if r["scenario"] == "S3_sybil"
                            and r["arm"] == arm
                            and r["step"] == s
                        ]
                    ),
                )
                for s in range(0, steps, max(1, steps // 40))
                if any(
                    r["scenario"] == "S3_sybil" and r["arm"] == arm and r["step"] == s
                    for r in rows
                )
            ],
        )
        for sc, arm in arms
        if sc == "S3_sybil"
    ]
    if s3:
        (out_dir / "s3_sybil_mass.svg").write_text(
            chart(
                "S3: routing mass on sybil agents (honest intents)",
                s3,
                "step",
                "sybil mass",
            )
        )
    (out_dir / "report.md").write_text(markdown(evaluation, meta))


def _fmt(x: Any) -> str:
    if isinstance(x, float):
        return f"{x:.4g}"
    if isinstance(x, list):
        return "[" + ", ".join(_fmt(v) for v in x) + "]"
    if isinstance(x, dict):
        return "{" + ", ".join(f"{k}: {_fmt(v)}" for k, v in x.items()) + "}"
    return str(x)


def markdown(ev: dict[str, Any], meta: dict[str, Any]) -> str:
    lines = [
        "# Wavefunction Field v0.1 — preregistered simulation results",
        "",
        f"- Preregistration sha256: `{ev['prereg_sha256']}`",
        f"- Params sha256: `{meta['params_sha256']}`",
        f"- Code commit: `{meta['commit']}`",
        f"- Seeds: {meta['seeds']} · steps: {meta['steps']} · scenarios: {', '.join(meta['scenarios'])}",
        f"- Mode: {'FULL preregistered run' if meta['full'] else 'QUICK smoke run (not preregistered evidence)'}",
        "- Units: **self-reported tokens** in a simulator. No energy or carbon figures are measured or implied.",
        "",
        "| Hypothesis | Verdict | Key numbers | Pass rule |",
        "|---|---|---|---|",
    ]
    for key in (
        "H1_density",
        "H2_learning_beats_registry",
        "H3_no_lock_in",
        "H4_sybil_resistance",
    ):
        if key not in ev:
            continue
        h = ev[key]
        nums = {k: v for k, v in h.items() if k not in ("verdict", "rule")}
        lines.append(f"| {key} | **{h['verdict']}** | {_fmt(nums)} | {h['rule']} |")
    lines += [
        "",
        "Exploratory (not tested): mean tokens per bit of hypothesis entropy, S1 second half: "
        + _fmt(ev.get("exploratory_tokens_per_bit_S1_second_half", {})),
        "",
    ]
    return "\n".join(lines)
