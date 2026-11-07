# Wavefunction Field v0.1 — preregistered simulation results

- Preregistration sha256: `effcc97f82ba03c5753ae9d55dcfcf0eee599b9b7bf263631b9d26245c16f5fa`
- Params sha256: `10991006b2c282c7065af2d1ea8f78a2c258b1037c7daacdb52443a1ea56d873`
- Code commit: `7b4b60e`
- Seeds: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] · steps: 2000 · scenarios: S1_steady, S2_shock, S3_sybil
- Mode: FULL preregistered run
- Units: **self-reported tokens** in a simulator. No energy, joule or carbon figures are measured or implied.

| Hypothesis | Verdict | Key numbers | Pass rule |
|---|---|---|---|
| H1_density | **FAIL** | {per_seed_rho: [0.3112, 0.2971, 0.2632, 0.348, 0.2749, 0.2476, 0.2902, 0.342, 0.2614, 0.3031], median_rho: 0.2936, seeds_negative: 0} | median over seeds ≤ -0.20 AND at least 8 of 10 seeds have rho < 0 |
| H2_learning_beats_registry | **FAIL** | {per_seed_ratio_WFP_over_B1: [0.9375, 0.9346, 0.9197, 0.9243, 0.8899, 0.942, 0.9241, 0.9313, 0.9169, 0.9331], seeds_meeting_0.80: 0, B0_random_mean_cost_per_seed: [4942, 5042, 4681, 4992, 4886, 4944, 5089, 4895, 5000, 4913]} | WFP_mean ≤ 0.80 × B1_mean in at least 9 of 10 seeds |
| H3_no_lock_in | **FAIL** | {recovery_steps: {WFP: [0, 157, 76, 639, 195, 6, 61, 45, 134, 25], B2_unbounded: [0, 187, 287, 188, 145, 19, 121, 117, 105, 53]}, median: {WFP: 68.5, B2_unbounded: 119}, uncensored: {WFP: 10, B2_unbounded: 10}} | median_seeds(recovery_WFP) ≤ 0.5 × median_seeds(recovery_B2) AND WFP is uncensored in at least 8 of 10 seeds |
| H4_sybil_resistance | **INCONCLUSIVE** | {m0_per_seed: [0.06279, 0.09097, 0.06745, 0.07255, 0.07786, 0.06503, 0.1092, 0.08627, 0.05811, 0.07672], mean_sybil_mass_late: {WFP: [0.04228, 0.04106, 0.02477, 0.02454, 0.02218, 0.03472, 0.03374, 0.02365, 0.02779, 0.04145], B3_naive_trust: [0.5262, 0.4908, 0.4586, 0.4374, 0.4368, 0.4573, 0.4992, 0.4829, 0.4645, 0.5202]}, wfp_within_2x_m0_all_seeds: True, attack_demonstrated: False} | WFP mean ≤ 2 × m0 in all 10 seeds AND B3_naive_trust mean ≥ 0.5 in at least 8 of 10 seeds |

Exploratory (not tested): mean tokens per bit of hypothesis entropy, S1 second half: {B0_random: 4076, B1_registry: 3414, WFP: 3133}

## Discussion (written after the run; nothing below changes a verdict)

None of the four preregistered hypotheses passed. The thresholds were locked before the run, and parameters were not tuned afterwards.

- **H1 FAIL. The pooled metric is confounded.** Across all post-warmup intents, density at emit correlates *positively* with cost (median ρ = +0.29). `density_at_emit` sums trail mass over an intent's tags, so two-tag intents score about twice as dense, and they are also harder (success = the weakest agent competence across the tags). *Exploratory, not preregistered:* split by tag count and with density per tag, the correlation is negative in 19 of 20 seed groups (median ρ −0.09 for one-tag intents, −0.14 for two-tag). That is consistent with the mechanism but far weaker than the −0.20 bar. A follow-up should preregister a per-tag density metric stratified by tag count.
- **H2 FAIL.** Trail routing was cheaper than capability-similarity routing in **10 of 10 seeds**, by 5.8–11.0% (WFP/B1 cost ratio 0.89–0.94). It never reached the preregistered 20% improvement. Against random routing, WFP is about 23% cheaper.
- **H3 FAIL, narrowly.** Bounded trails recovered faster than unbounded ones (median 68.5 vs 119 steps, ratio 0.58) and recovered in 10 of 10 seeds. The preregistered bar was 0.5.
- **H4 INCONCLUSIVE.** Under the field's default trust view, a self-verifying ring of 10 sybils got *less* routing mass than its starting floor share (mean late mass 0.022–0.042 vs m0 0.058–0.109). The naive trust-everyone arm reached a mean of 0.48 (0.44–0.53), and is ≥ 0.5 in only 3 of 10 seeds, so the rule records the attack as not demonstrated. Exploratory: the naive arm's honest-job cost was 29% higher (5,299 vs 4,111 tokens).

**What this supports, as measured:** verified-trail routing is consistently, modestly cheaper than registry-style matching, and the trust-scoped defense holds against this ring. **What it doesn't support:** the large effect sizes the hypotheses were written for. Any public claim must use these numbers.
