[EN](README.md) | [SI](README.si.md)

# Analysis plan

What `ipi analyze` computes for each of the thesis's three hypotheses. Every test belongs to exactly one hypothesis,
and everything that belongs to none is listed under [Descriptive tables](#descriptive-tables). The plan is fixed
before the main sweep; nothing in it is chosen after looking at the main sweep's results.

Status: all tables are built (`tables.py`): the descriptive ones and the hypothesis tables below, `h1_attacks`,
`h1_attack_pairs`, `h2_defenses`, `h2_defenses_by_attack`, `h3_coverage`, `h3_levels`, `h3_injection_tasks` and
`h3_breadth`.

## Data

- **Unit.** One security run: model × defense × attack × pair, with the binary outcome `security` (true = the attack
  succeeded). ASR is the share of runs with security true among the runs without a run error.
- **One run per unit.** Every unit is run once at temperature 0, so there are no repetitions to average. The 250
  pairs of the balanced subset are the sample; the same 250 are run in every configuration, so every comparison is
  paired on the pair.
- **Runs used.** Only security runs in the balanced subset. Run errors are left out; a comparison uses a pair only
  when all of its runs in that comparison are without an error.
- **Models are a fixed factor.** Five models are too few to estimate variation between models, so no result is
  generalised to other models. A result is given per model, or over a stated set of models.
- **Dependence.** Pairs are not independent of each other: each user task is in 5 pairs and each injection task in
  10. The tests treat the pair as the independent unit; the intervals of the effect sizes do not (see below).

### Shared definitions

- **Significance.** α = 0.05, two-sided, for every test. A hypothesis that names a direction also needs the estimate
  to point that way.
- **Multiple comparisons.** Holm's correction within the primary tests of one hypothesis, and separately within its
  secondary tests. Nothing is corrected across hypotheses. Each table gives the raw p, the Holm-adjusted p and the
  number of tests in its family.
- **Exact paired test.** For two conditions on the same pairs: `b` = pairs where the first is worse (more successful
  attacks), `c` = pairs where the second is worse, p = the exact two-sided binomial p of min(b, c) of b + c at 0.5
  (`_mcnemar`). With one attack per pair this is McNemar's test. With several attacks, a pair's value is its number
  of successful attacks over them, so the pair stays the unit and the attacks on one pair are not counted as
  independent.
- **Effect size.** The difference of the two ASRs in percentage points, with a 95 % interval from a cluster bootstrap
  over user tasks: the 50 user tasks are resampled with replacement, each with all of its pairs, 10 000 times with a
  fixed seed, and the interval is the 2.5th to 97.5th percentile. The relative reduction, 1 − ASR / baseline ASR, is
  given next to it and is empty when the baseline ASR is 0.
- **Eligible models.** GPT-5.4 mini, Qwen and Mistral Medium 3: the models with at least two attacks at 20 % ASR or
  more with the baseline in `sweeps/pilot-attacks.yaml`. The rule and the list come from the pilot, not from the main
  sweep, so the choice does not bias the main sweep's estimates. Gemini (at most 7 %) and DeepSeek (at most 12 %)
  are not eligible.
- **Defense level.** Content level: `spotlighting`, `sanitizer` (they change what the model reads). Action level:
  `tool-filter`, `security-policy` (they limit what the model can call). The level comes from how the defense works,
  not from its results.
- **Covered pair.** Defined from the suite's ground truths, without a model:
  - `security-policy` covers a pair when the policy blocks a call of the injection task's ground truth:
    12 of the 25 injection tasks, 120 of the 250 pairs; 130 are not covered.
  - `tool-filter` covers a pair when the injection task's ground truth calls a tool that the user task's ground
    truth does not call, so a filter that keeps only the user task's tools removes it: 240 of the 250 pairs; 10 are
    not covered.
- **Power.** The sample is fixed at 250 pairs, so no sample size is derived. An exact paired test can reach
  p < 0.05 only with at least 6 differing pairs, all in one direction, and survive Holm's correction only with at
  least 8 (6 tests) or 9 (12 tests). A cell with fewer differing pairs cannot be significant and is reported as such.

## H1 – attack techniques differ

> Stopnja uspešnosti napadov (ASR) pri agentu brez obrambe se statistično značilno razlikuje glede na uporabljeno
> tehniko napada, pri čemer se upoštevajo razlike med uporabljenimi modeli.

**Runs.** Baseline only, all four attacks, all five models: 5 × 4 × 250 = 5 000 runs.

**Primary test.** Cochran's Q per model, over the four attacks on the pairs where all four runs have no error:
Q = (k − 1)(k ΣCⱼ² − N²) / (kN − ΣRᵢ²), with k = 4 attacks, Cⱼ the successes of attack j, Rᵢ the successes on pair i
and N all successes; p from the χ² distribution with k − 1 degrees of freedom, and p = 1 when no pair differs between
attacks. Testing within each model is how differences between models are taken into account: a model's overall
level never enters its test. 5 tests, Holm.

**Decision.** H1 holds for a model when its adjusted p < 0.05. The thesis states in how many of the five models it
holds; H1 as worded is supported when it holds in at least one, and the count says how general that is.

**Secondary.**
- Each two attacks compared with the exact paired test, per model: 6 × 5 = 30 tests, Holm, with the effect size.
- Cochran's Q over the three attacks of the main sweep only (`fake-completion`, `task-aligned`, `tool-notice`), per
  model, 5 tests. `direct-instruction` was kept as a known weak attack, so the test over four mostly confirms that
  choice; this one asks whether the strong attacks differ.
- The rank of the four attacks by ASR in each model, as the description of the model × attack interaction. It is not
  tested.

**Robustness.**
- The primary test on the 150 pairs whose user task was not in `sweeps/pilot-attacks.yaml` (the fifth to tenth user
  task of each domain). The attacks were chosen on the other 100.
- The primary test on capable pairs only.
- A model whose Q has fewer than 24 cells in the pairs that differ (differing pairs × k) is marked: the χ²
  approximation is poor there.

**Table.** `h1_attacks` (set of runs × model: n, ASR per attack, Q, p, adjusted p) and `h1_attack_pairs` (model × attack ×
attack).

## H2 – defenses lower ASR

> Pri modelih, pri katerih napadi brez obrambe dosegajo uspešnost, obrambni mehanizmi statistično značilno zmanjšajo
> stopnjo uspešnosti napadov (ASR) v primerjavi z agentom brez obrambe.

**Runs.** The eligible models, the three attacks run with every defense, the baseline and the four defenses:
3 × 3 × 5 × 250 = 11 250 runs.

**Primary test.** Each defense against the baseline, per eligible model, with the exact paired test over the three
attacks on all 250 pairs. 3 models × 4 defenses = 12 tests, Holm.

**Decision.** A defense lowers ASR on a model when its adjusted p < 0.05 and its ASR is below the baseline's. H2
holds for a defense when that is so on all three eligible models, and holds as worded when it holds for all four
defenses. Otherwise the thesis says for which defenses and models it holds.

**Effect size.** The absolute and the relative reduction of ASR per model × defense, as defined above.

**Secondary.** The same comparison per attack: model × attack × defense with McNemar's test, 36 tests on the
eligible models, Holm.

**Robustness.**
- The primary test on all five models (20 tests), to show that the conclusion does not rest on the choice of models.
- The primary test on capable pairs only.
- The primary test with every run error counted as a failed attack, since errors differ between defenses.

**Table.** `h2_defenses` (set of runs × model × defense) and `h2_defenses_by_attack` (model × attack × defense).

## H3 – breadth and strength of the defenses

> Obrambe na ravni vsebine zmanjšujejo stopnjo uspešnosti napadov (ASR) v širšem naboru scenarijev napada, vendar je
> njihov učinek omejen. Obrambe na ravni dejanj zmanjšujejo ASR le v scenarijih, ki jih pokrivajo, vendar v teh
> dosegajo večje zmanjšanje ASR kot obrambe na ravni vsebine.

H3 never compares a defense with the baseline in a test; that is H2. It compares an action-level defense directly
with a content-level one, on the pairs the action-level defense covers and on those it does not. Two defenses being
"significant" and "not significant" against the baseline would not show that they differ from each other.

**Runs.** The eligible models, the three attacks run with every defense and the four defenses. A pair's value under
a defense is its number of successful attacks over the three models and the three attacks (0 to 9).

**Primary tests.** The exact paired test between an action-level and a content-level defense. 6 tests, Holm.

| Claim    | Pairs                                    | Compared                                                | H3 predicts             |
|----------|------------------------------------------|---------------------------------------------------------|-------------------------|
| strength | the 120 covered by `security-policy`     | `security-policy` with `spotlighting`, with `sanitizer` | `security-policy` lower |
| strength | the 240 covered by `tool-filter`         | `tool-filter` with `spotlighting`, with `sanitizer`     | `tool-filter` lower     |
| breadth  | the 130 not covered by `security-policy` | `spotlighting`, `sanitizer` with `security-policy`      | content level lower     |

`tool-filter` leaves 10 pairs uncovered, too few for a test, so its breadth claim is only described.

**Decision.** Strength holds for an action-level defense when both of its tests have an adjusted p < 0.05 with its
ASR the lower one. Breadth holds when both breadth tests do, with the content-level defense lower. H3 holds as
worded when strength holds for both action-level defenses and breadth holds.

**Estimates, not tested.**
- *Only where covered.* The reduction of ASR from the baseline for each action-level defense on its covered and on
  its uncovered pairs, with intervals. "No effect where not covered" is claimed only when the whole interval of the
  reduction on the uncovered pairs lies within ±10 percentage points; a test that is not significant does not show it.
- *Limited effect.* The ASR that is left under each content-level defense on all pairs, with its Wilson interval and
  its relative reduction.
- *Coverage by design.* The share of pairs each action-level defense covers: 120 / 250 and 240 / 250.
- *Breadth by injection task.* For each defense, the share of the 25 injection tasks whose ASR falls by at least
  10 percentage points from the baseline, among the injection tasks with a baseline ASR of at least 10 %; also at
  5 and 20 points. Each injection task has 90 runs per defense (10 pairs × 3 attacks × 3 models).

**Secondary.** The six primary tests per eligible model: 18 tests, Holm.

**Robustness.**
- The primary tests on all five models.
- The primary tests on the pairs that are capable for all three eligible models.
- The primary tests on the pairs where an attack succeeded with the baseline at least once, since a pair no attack
  succeeds on cannot show a difference.

**Table.** `h3_levels` (set of runs × model × claim × action-level defense × content-level defense, with the model
`pooled` in every row but the secondary ones: pairs, the two ASRs, b, c, p, adjusted p, the difference with its
interval), `h3_coverage` (defense × covered: pairs, runs, baseline ASR, ASR, reduction with its interval, whether it
lies within the margin), `h3_injection_tasks` (defense × injection task: runs, baseline ASR, ASR, reduction) and `h3_breadth` (defense: its
level, the injection tasks at each threshold and those reduced by as much with their share, and the ASR that is left
on all pairs with its Wilson interval and its relative reduction).

## Descriptive tables

These describe the runs and test no hypothesis: `utility`, `security`, the pooled `security_by_*` tables, `domains`,
`difficulty`, `injection_checks`, `cost`, `subset_validation`, `errors`, and `paired` (what a defense costs in
utility). Their columns are defined in `docs/PROJECT.md`.

## Not done

- **No mixed-effects logistic model.** With one run per unit, cells at or near 0 % ASR (`direct-instruction`, Gemini)
  separate the outcome almost completely, which makes its estimates unstable, and it would need a second toolchain.
  The exact paired tests use the pairing the design already has. `security.csv` and the run files are enough to fit
  one outside `ipi analyze`.
- **No power simulation.** The number of pairs was fixed by the design; the smallest detectable result is stated
  under Power.
- **No empirical coverage of `tool-filter`.** Which tools the filter kept is not in the run file, so coverage is by
  design only.
