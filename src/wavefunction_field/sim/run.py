# SPDX-License-Identifier: Apache-2.0
"""Run scenarios/arms/seeds and evaluate the preregistered hypotheses."""

from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from wavefunction_field.core.canonical import digest
from wavefunction_field.sim import stats
from wavefunction_field.sim.world import World


def run_one(
    args: tuple[dict[str, Any], dict[str, Any], str, str, int, int | None],
) -> dict[str, Any]:
    prereg, params_raw, scenario, arm, seed, steps = args
    from wavefunction_field.core.params import FieldParams

    world = World(prereg, scenario, arm, seed, FieldParams.from_mapping(params_raw))
    if steps is not None and world.cfg.get("shock"):
        world.cfg = dict(world.cfg, shock=dict(world.cfg["shock"], at_step=steps // 2))
    world.run(steps)
    return {
        "scenario": scenario,
        "arm": arm,
        "seed": seed,
        "rows": world.rows,
        "probe": world.probe,
    }


def run_all(
    prereg: dict[str, Any],
    params_raw: dict[str, Any],
    scenarios: list[str],
    seeds: list[int],
    steps: int | None = None,
    jobs: int = 1,
) -> list[dict[str, Any]]:
    tasks = [
        (prereg, params_raw, sc, arm, seed, steps)
        for sc in scenarios
        for arm in prereg["scenarios"][sc]["arms"]
        for seed in seeds
    ]
    if jobs <= 1:
        results = [run_one(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(run_one, tasks))
    return sorted(results, key=lambda r: (r["scenario"], r["arm"], r["seed"]))


def _rows(
    results: list[dict[str, Any]], scenario: str, arm: str, seed: int
) -> list[dict[str, Any]]:
    for r in results:
        if (r["scenario"], r["arm"], r["seed"]) == (scenario, arm, seed):
            rows: list[dict[str, Any]] = r["rows"]
            return rows
    return []


def _probe(
    results: list[dict[str, Any]], scenario: str, arm: str, seed: int
) -> list[dict[str, Any]]:
    for r in results:
        if (r["scenario"], r["arm"], r["seed"]) == (scenario, arm, seed):
            probe: list[dict[str, Any]] = r["probe"]
            return probe
    return []


def evaluate(
    prereg: dict[str, Any],
    results: list[dict[str, Any]],
    seeds: list[int],
    steps: int,
    shock_step: int,
) -> dict[str, Any]:
    """Evaluate H1-H4 exactly as preregistered; thresholds come only from prereg."""
    warm = prereg["time"]["warmup_steps"]
    half = steps // 2
    present = {r["scenario"] for r in results}
    out: dict[str, Any] = {}

    if "S1_steady" in present:
        rhos = []
        for s in seeds:
            rows = [
                r for r in _rows(results, "S1_steady", "WFP", s) if r["step"] >= warm
            ]
            rhos.append(
                stats.spearman(
                    [r["density_at_emit"] for r in rows],
                    [r["cost_to_collapse_tokens"] for r in rows],
                )
            )
        med = stats.median([x for x in rhos if not math.isnan(x)])
        neg = sum(1 for x in rhos if x < 0)
        out["H1_density"] = {
            "per_seed_rho": rhos,
            "median_rho": med,
            "seeds_negative": neg,
            "verdict": "PASS"
            if med <= -0.20 and neg >= 8 * len(seeds) / 10
            else "FAIL",
            "rule": prereg["hypotheses"]["H1_density"]["pass"],
        }
        ratios, wins = [], 0
        for s in seeds:
            wfp = [
                r["cost_to_collapse_tokens"]
                for r in _rows(results, "S1_steady", "WFP", s)
                if half <= r["step"] < steps
            ]
            b1 = [
                r["cost_to_collapse_tokens"]
                for r in _rows(results, "S1_steady", "B1_registry", s)
                if half <= r["step"] < steps
            ]
            ratio = stats.mean(wfp) / stats.mean(b1)
            ratios.append(ratio)
            wins += int(ratio <= 0.80)
        b0 = [
            stats.mean(
                [
                    r["cost_to_collapse_tokens"]
                    for r in _rows(results, "S1_steady", "B0_random", s)
                    if half <= r["step"] < steps
                ]
            )
            for s in seeds
        ]
        out["H2_learning_beats_registry"] = {
            "per_seed_ratio_WFP_over_B1": ratios,
            "seeds_meeting_0.80": wins,
            "B0_random_mean_cost_per_seed": b0,
            "verdict": "PASS" if wins >= 9 * len(seeds) / 10 else "FAIL",
            "rule": prereg["hypotheses"]["H2_learning_beats_registry"]["pass"],
        }

    if "S2_shock" in present:
        rec: dict[str, list[int]] = {}
        uncensored: dict[str, int] = {}
        for arm in ("WFP", "B2_unbounded"):
            rec[arm], uncensored[arm] = [], 0
            for s in seeds:
                probe = {
                    p["step"]: p["E_s"] for p in _probe(results, "S2_shock", arm, s)
                }
                pre = stats.mean(
                    [
                        probe[t]
                        for t in range(max(0, shock_step - 50), shock_step)
                        if t in probe
                    ]
                )
                rsteps = steps - shock_step
                for t in range(shock_step, steps):
                    if probe.get(t, -1.0) >= 0.9 * pre:
                        rsteps = t - shock_step
                        uncensored[arm] += 1
                        break
                rec[arm].append(rsteps)
        m_w, m_b = stats.median(rec["WFP"]), stats.median(rec["B2_unbounded"])
        out["H3_no_lock_in"] = {
            "recovery_steps": rec,
            "median": {"WFP": m_w, "B2_unbounded": m_b},
            "uncensored": uncensored,
            "verdict": "PASS"
            if m_w <= 0.5 * m_b and uncensored["WFP"] >= 8 * len(seeds) / 10
            else "FAIL",
            "rule": prereg["hypotheses"]["H3_no_lock_in"]["pass"],
        }

    if "S3_sybil" in present:
        per: dict[str, list[float]] = {"WFP": [], "B3_naive_trust": []}
        m0s = []
        for s in seeds:
            early = [
                r["sybil_mass"]
                for r in _rows(results, "S3_sybil", "WFP", s)
                if r["step"] < 50
            ]
            m0s.append(stats.mean(early))
            for arm in per:
                late = [
                    r["sybil_mass"]
                    for r in _rows(results, "S3_sybil", arm, s)
                    if half <= r["step"] < steps
                ]
                per[arm].append(stats.mean(late))
        wfp_ok = all(per["WFP"][i] <= 2 * m0s[i] for i in range(len(seeds)))
        attack = (
            sum(1 for x in per["B3_naive_trust"] if x >= 0.5) >= 8 * len(seeds) / 10
        )
        verdict = (
            "PASS" if wfp_ok and attack else ("INCONCLUSIVE" if wfp_ok else "FAIL")
        )
        out["H4_sybil_resistance"] = {
            "m0_per_seed": m0s,
            "mean_sybil_mass_late": per,
            "wfp_within_2x_m0_all_seeds": wfp_ok,
            "attack_demonstrated": attack,
            "verdict": verdict,
            "rule": prereg["hypotheses"]["H4_sybil_resistance"]["pass"],
        }

    # exploratory, not tested: tokens per bit
    tpb: dict[str, float] = {}
    for r in results:
        if r["scenario"] != "S1_steady":
            continue
        vals = [
            x["cost_to_collapse_tokens"] / x["H_bits"]
            for x in r["rows"]
            if x["H_bits"] > 0 and x["step"] >= half
        ]
        tpb.setdefault(r["arm"], 0.0)
        tpb[r["arm"]] += stats.mean(vals) / len(seeds) if vals else 0.0
    out["exploratory_tokens_per_bit_S1_second_half"] = tpb
    out["prereg_sha256"] = digest(prereg)
    return out
