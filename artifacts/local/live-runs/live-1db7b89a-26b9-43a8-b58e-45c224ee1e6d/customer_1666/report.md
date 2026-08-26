# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `1666`
**Run:** `528d20c0-da84-4cc1-9bfa-8c8573f5b9b9`
**Status:** Completed
**Data:** Official Complete Journey · `bradleyboehmke/completejourney` @ `5b5d06192b9856edd04e4d405787af2f2e4a1fef`
**Execution:** Live Gemini · backend `gemini` · model `gemini-3.7-flash`
**Generated:** `2026-08-26T20:57:07.569582+00:00` · timing Actual Utc And Monotonic

## Decline summary

The deterministic detector compared weeks **38–45** with weeks **46–53**.

Detector evidence: `detector_528d20c0-da84-4cc1-9bfa-8c8573f5b9b9` (run- and household-owned).

| Measure | Baseline | Recent | Recorded drop |
|---|---:|---:|---:|
| Retailer sales value | $115.77 | $5.99 | 94.8% |
| Distinct baskets | 9 | 2 | 77.8% |
| Active weeks | 6 | 1 | 83.3% |

- **Decline score:** 0.87413 (weighted heuristic, not a probability)
- **Eligible:** yes
- **Flagged:** yes

## Population and comparison context

**Classification:** Customer Specific. Signed change is `(recent - baseline) / baseline`; more negative means a more severe decline. Classification evidence: `ev_call-528d20c0da-03-peer_comparison_017`.


- **Target retailer-sales change:** -94.8%


| Comparison | Households | Median change | Interquartile range | Target percentile | Share declining | Target minus median |
|---|---:|---:|---:|---:|---:|---:|
| Eligible Population | 1312 | -3.6% | -33.4% to 29.8% | 1.67683 | 53.4% | -91.2% |
| Behavioral Peers | 50 | -0.2% | -46.0% to 68.8% | 0 | 50.0% | -94.6% |


- **Eligible-population construction:** The target is compared with the household-level distribution of signed retailer-sales changes among all other households meeting the declared baseline eligibility policy. The target is excluded, and lower change means a more severe decline.
- **Behavioral-peer construction:** Eligible target-excluded households are robust-scaled on baseline log1p retailer sales value, trip count, median basket value, active weeks, and category concentration. Scaling is fit on comparison households only; nearest Euclidean peers are selected with household-ID tie breaking.
- The target household is excluded from both comparison distributions: yes.


### Major-category contemporaneous context

| Department / category | Target change | Comparison median | Share declining | Target minus median | Households | Classification |
|---|---:|---:|---:|---:|---:|---|
| DRUG GM / ORAL HYGIENE PRODUCTS | -100.0% | -100.0% | 76.4% | 0.0% | 449 | Broad Context |
| MEAT-PCKGD / MEAT - MISC | -100.0% | -100.0% | 79.0% | 0.0% | 367 | Broad Context |
| GROCERY / BATH TISSUES | -100.0% | -41.0% | 63.2% | -59.0% | 560 | Mixed |
| DRUG GM / DEODORANTS | -100.0% | -100.0% | 80.2% | 0.0% | 257 | Broad Context |
| GROCERY / MOLASSES/SYRUP/PANCAKE MIXS | -100.0% | -100.0% | 81.4% | 0.0% | 274 | Broad Context |
| GROCERY / FRZN POTATOES | -100.0% | -68.5% | 68.4% | -31.5% | 361 | Mixed |
| GROCERY / FRZN BREAKFAST FOODS | -100.0% | -100.0% | 75.2% | 0.0% | 327 | Broad Context |
| GROCERY / CHEESE | -100.0% | -13.9% | 55.3% | -86.1% | 1070 | Customer Specific |




- Context limitation: Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.

- Context limitation: Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Context limitation: Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.



## Investigation path



1. **Customer trend** — Ok
   Investigate the next permitted evidence source.
   Attempts: 1 · Retries: 0 · Recorded latency: 72.1968 ms · Evidence: `ev_call-528d20c0da-01-customer_trend_001`, `ev_call-528d20c0da-01-customer_trend_002`, `ev_call-528d20c0da-01-customer_trend_003`, `ev_call-528d20c0da-01-customer_trend_004`, `ev_call-528d20c0da-01-customer_trend_005`, `ev_call-528d20c0da-01-customer_trend_006`, `ev_call-528d20c0da-01-customer_trend_007`, `ev_call-528d20c0da-01-customer_trend_008`, `ev_call-528d20c0da-01-customer_trend_009`, `ev_call-528d20c0da-01-customer_trend_010`, `ev_call-528d20c0da-01-customer_trend_011`, `ev_call-528d20c0da-01-customer_trend_012`, `ev_call-528d20c0da-01-customer_trend_013`, `ev_call-528d20c0da-01-customer_trend_014`, `ev_call-528d20c0da-01-customer_trend_015`, `ev_call-528d20c0da-01-customer_trend_016`, `ev_call-528d20c0da-01-customer_trend_017`, `ev_call-528d20c0da-01-customer_trend_018`, `ev_call-528d20c0da-01-customer_trend_019`, `ev_call-528d20c0da-01-customer_trend_020`, `ev_call-528d20c0da-01-customer_trend_021`, `ev_call-528d20c0da-01-customer_trend_022`, `ev_call-528d20c0da-01-customer_trend_023`, `ev_call-528d20c0da-01-customer_trend_024`, `ev_call-528d20c0da-01-customer_trend_025`, `ev_call-528d20c0da-01-customer_trend_026`

2. **Category decomposition** — Ok
   Which product categories contributed most to the decline in retailer sales value?
   Attempts: 1 · Retries: 0 · Recorded latency: 137.492 ms · Evidence: `ev_call-528d20c0da-02-category_decomposition_001`, `ev_call-528d20c0da-02-category_decomposition_002`, `ev_call-528d20c0da-02-category_decomposition_003`, `ev_call-528d20c0da-02-category_decomposition_004`, `ev_call-528d20c0da-02-category_decomposition_005`, `ev_call-528d20c0da-02-category_decomposition_006`, `ev_call-528d20c0da-02-category_decomposition_007`, `ev_call-528d20c0da-02-category_decomposition_008`, `ev_call-528d20c0da-02-category_decomposition_009`, `ev_call-528d20c0da-02-category_decomposition_010`, `ev_call-528d20c0da-02-category_decomposition_011`, `ev_call-528d20c0da-02-category_decomposition_012`, `ev_call-528d20c0da-02-category_decomposition_013`, `ev_call-528d20c0da-02-category_decomposition_014`, `ev_call-528d20c0da-02-category_decomposition_015`, `ev_call-528d20c0da-02-category_decomposition_016`, `ev_call-528d20c0da-02-category_decomposition_017`, `ev_call-528d20c0da-02-category_decomposition_018`, `ev_call-528d20c0da-02-category_decomposition_019`, `ev_call-528d20c0da-02-category_decomposition_020`, `ev_call-528d20c0da-02-category_decomposition_021`, `ev_call-528d20c0da-02-category_decomposition_022`, `ev_call-528d20c0da-02-category_decomposition_023`, `ev_call-528d20c0da-02-category_decomposition_024`, `ev_call-528d20c0da-02-category_decomposition_025`, `ev_call-528d20c0da-02-category_decomposition_026`, `ev_call-528d20c0da-02-category_decomposition_027`, `ev_call-528d20c0da-02-category_decomposition_028`, `ev_call-528d20c0da-02-category_decomposition_029`, `ev_call-528d20c0da-02-category_decomposition_030`, `ev_call-528d20c0da-02-category_decomposition_031`, `ev_call-528d20c0da-02-category_decomposition_032`, `ev_call-528d20c0da-02-category_decomposition_033`, `ev_call-528d20c0da-02-category_decomposition_034`, `ev_call-528d20c0da-02-category_decomposition_035`, `ev_call-528d20c0da-02-category_decomposition_036`, `ev_call-528d20c0da-02-category_decomposition_037`, `ev_call-528d20c0da-02-category_decomposition_038`, `ev_call-528d20c0da-02-category_decomposition_039`, `ev_call-528d20c0da-02-category_decomposition_040`, `ev_call-528d20c0da-02-category_decomposition_041`, `ev_call-528d20c0da-02-category_decomposition_042`, `ev_call-528d20c0da-02-category_decomposition_043`, `ev_call-528d20c0da-02-category_decomposition_044`, `ev_call-528d20c0da-02-category_decomposition_045`, `ev_call-528d20c0da-02-category_decomposition_046`, `ev_call-528d20c0da-02-category_decomposition_047`, `ev_call-528d20c0da-02-category_decomposition_048`, `ev_call-528d20c0da-02-category_decomposition_049`, `ev_call-528d20c0da-02-category_decomposition_050`, `ev_call-528d20c0da-02-category_decomposition_051`, `ev_call-528d20c0da-02-category_decomposition_052`, `ev_call-528d20c0da-02-category_decomposition_053`, `ev_call-528d20c0da-02-category_decomposition_054`, `ev_call-528d20c0da-02-category_decomposition_055`, `ev_call-528d20c0da-02-category_decomposition_056`, `ev_call-528d20c0da-02-category_decomposition_057`, `ev_call-528d20c0da-02-category_decomposition_058`, `ev_call-528d20c0da-02-category_decomposition_059`, `ev_call-528d20c0da-02-category_decomposition_060`, `ev_call-528d20c0da-02-category_decomposition_061`, `ev_call-528d20c0da-02-category_decomposition_062`, `ev_call-528d20c0da-02-category_decomposition_063`, `ev_call-528d20c0da-02-category_decomposition_064`, `ev_call-528d20c0da-02-category_decomposition_065`, `ev_call-528d20c0da-02-category_decomposition_066`, `ev_call-528d20c0da-02-category_decomposition_067`, `ev_call-528d20c0da-02-category_decomposition_068`, `ev_call-528d20c0da-02-category_decomposition_069`, `ev_call-528d20c0da-02-category_decomposition_070`, `ev_call-528d20c0da-02-category_decomposition_071`, `ev_call-528d20c0da-02-category_decomposition_072`, `ev_call-528d20c0da-02-category_decomposition_073`, `ev_call-528d20c0da-02-category_decomposition_074`, `ev_call-528d20c0da-02-category_decomposition_075`, `ev_call-528d20c0da-02-category_decomposition_076`

3. **Behavioral peer comparison** — Ok
   How does the target household spend trajectory compare to eligible households and behavioral peers?
   Attempts: 1 · Retries: 0 · Recorded latency: 58.6613 ms · Evidence: `ev_call-528d20c0da-03-peer_comparison_001`, `ev_call-528d20c0da-03-peer_comparison_002`, `ev_call-528d20c0da-03-peer_comparison_003`, `ev_call-528d20c0da-03-peer_comparison_004`, `ev_call-528d20c0da-03-peer_comparison_005`, `ev_call-528d20c0da-03-peer_comparison_006`, `ev_call-528d20c0da-03-peer_comparison_007`, `ev_call-528d20c0da-03-peer_comparison_008`, `ev_call-528d20c0da-03-peer_comparison_009`, `ev_call-528d20c0da-03-peer_comparison_010`, `ev_call-528d20c0da-03-peer_comparison_011`, `ev_call-528d20c0da-03-peer_comparison_012`, `ev_call-528d20c0da-03-peer_comparison_013`, `ev_call-528d20c0da-03-peer_comparison_014`, `ev_call-528d20c0da-03-peer_comparison_015`, `ev_call-528d20c0da-03-peer_comparison_016`, `ev_call-528d20c0da-03-peer_comparison_017`



## Likely drivers



- **Associational claim:** A recorded loss in GROCERY / CHEESE is a plausible contributor to the observed engagement decline.
  Grounded by `ev_call-528d20c0da-02-category_decomposition_033`, `ev_call-528d20c0da-02-category_decomposition_036`.
  Counterevidence review: No material counterevidence was cited from the available ledger.
  Claim limitations: The observational evidence supports an association, not a causal explanation of the household's behavior.




## Supporting evidence



### `ev_call-528d20c0da-02-category_decomposition_033` — Category Retailer Sales Value

- Source: `category_decomposition` / `call-528d20c0da-02-category_decomposition`
- Source status: Ok
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `CHEESE`
- Baseline: 5.49 Retailer Sales Value
- Recent: 0 Retailer Sales Value
- Change: -5.49 Retailer Sales Value


### `ev_call-528d20c0da-02-category_decomposition_036` — Contribution To Lost Retailer Sales Value

- Source: `category_decomposition` / `call-528d20c0da-02-category_decomposition`
- Source status: Ok
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `CHEESE`
- Value: 0.0500091 Share




## What this analysis can establish


- Recorded retailer sales value, distinct baskets, and active weeks in the declared baseline and recent windows.

- Recorded category movement, including explicit UNKNOWN mappings and reconciled retailer-sales totals.

- The household's relative position among target-excluded eligible households and behavioral peers.


## What this analysis cannot establish


- The source is observational: current evidence supports descriptive and associational claims, not causal claims.

- Marketing treatment may be targeted from prior behavior, so campaign and purchasing associations can reflect selection into treatment.

- Whether a recommended action changes behavior must be learned through a valid prospective design such as the stated randomized holdout.


## Unobserved factors and alternative explanations


- Unobserved: Purchases at competitors, restaurants, and other online or offline channels.

- Unobserved: Relocation, travel, income or employment changes, household-composition changes, health, diet, and transportation access.

- Unobserved: Customer satisfaction, service experiences, stockouts, discontinuations, assortment changes, and competitor conditions.

- Unobserved: Customer intent and whether a particular household member noticed an advertisement or promotion.



- Alternative: Recorded evidence does not distinguish the observed signal from unobserved activity outside this retailer.



## Counterevidence review


- No evidence record was designated as counterevidence.


## Next Best Action


**CATEGORY\_WINBACK** — Recommend a human-reviewed test intended to rebuild engagement in a specifically evidenced declining category; the catalog does not prescribe an outreach channel or execute a treatment.

The cited records satisfy the selected catalog action's machine-checkable evidence policy; the recommendation remains a human-reviewed test.

Resolved confidence: **Medium** (deterministic cap applied).



## Measurement plan


- **Framing:** This is a hypothesis to test, not a promised retention effect.
- **Success metric:** Change in retailer sales value for the selected category relative to an eligible holdout over the evaluation window.
- **Suggested experiment:** Randomize eligible households between a reviewer-approved category treatment and no treatment, preserving a ten-percent holdout.


## Limitations



- Source week 53 contains fewer calendar days than an ordinary week.

- Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.

- Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.

- Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.

- Customer intent and activity outside the recorded retailer data are not observed.



## Failures and partial-result warnings


- No failed, partial, or retried analytical result was recorded.



## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Maximum claim | Limitations |
|---|---|---|---|---|---|---|
| `ev_call-528d20c0da-01-customer_trend_001` | Context | `customer_trend` | Ok | Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_002` | Context | `customer_trend` | Ok | Distinct Trips | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_003` | Context | `customer_trend` | Ok | Active Weeks | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_004` | Context | `customer_trend` | Ok | Average Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_005` | Context | `customer_trend` | Ok | Median Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_006` | Context | `customer_trend` | Ok | Recorded Quantity | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-528d20c0da-01-customer_trend_007` | Context | `customer_trend` | Ok | Distinct Products | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_008` | Context | `customer_trend` | Ok | Recency Weeks | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_009` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_010` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_011` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_012` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_013` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_014` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_015` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_016` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_017` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_018` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_019` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_020` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_021` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_022` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_023` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_024` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_025` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-01-customer_trend_026` | Context | `customer_trend` | Ok | Full Window Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_001` | Context | `category_decomposition` | Ok | Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_002` | Context | `category_decomposition` | Ok | Product Mapping Line Item Coverage | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_003` | Context | `category_decomposition` | Ok | Product Mapping Distinct Product Coverage | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_004` | Context | `category_decomposition` | Ok | Unknown Group Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_005` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_006` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_007` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_008` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_009` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_010` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_011` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_012` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_013` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_014` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_015` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_016` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_017` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_018` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_019` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_020` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_021` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_022` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_023` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_024` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_025` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_026` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_027` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_028` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_029` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_030` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_031` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_032` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_033` | Supporting | `category_decomposition` | Ok | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_034` | Context | `category_decomposition` | Ok | Category Percentage Change | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_035` | Context | `category_decomposition` | Ok | Category Share Shift | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_036` | Supporting | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-528d20c0da-02-category_decomposition_037` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_038` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_039` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_040` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_041` | Context | `category_decomposition` | Ok | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_042` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_043` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_044` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_045` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_046` | Context | `category_decomposition` | Ok | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_047` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_048` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_049` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_050` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_051` | Context | `category_decomposition` | Ok | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_052` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_053` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_054` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_055` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_056` | Context | `category_decomposition` | Ok | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_057` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_058` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_059` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_060` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_061` | Context | `category_decomposition` | Ok | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_062` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_063` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_064` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_065` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_066` | Context | `category_decomposition` | Ok | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_067` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_068` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_069` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_070` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_071` | Context | `category_decomposition` | Ok | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_072` | Context | `category_decomposition` | Ok | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_073` | Context | `category_decomposition` | Ok | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_074` | Context | `category_decomposition` | Ok | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_075` | Context | `category_decomposition` | Ok | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-02-category_decomposition_076` | Context | `category_decomposition` | Ok | Category Context Classification: customer\_specific | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-528d20c0da-03-peer_comparison_001` | Context | `peer_comparison` | Ok | Target Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_002` | Context | `peer_comparison` | Ok | Population Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_003` | Context | `peer_comparison` | Ok | Peer Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_004` | Context | `peer_comparison` | Ok | Population Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_005` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_006` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_007` | Context | `peer_comparison` | Ok | Target Population Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_008` | Context | `peer_comparison` | Ok | Population Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_009` | Context | `peer_comparison` | Ok | Target Minus Population Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_010` | Context | `peer_comparison` | Ok | Peer Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_011` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_012` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_013` | Context | `peer_comparison` | Ok | Target Peer Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_014` | Context | `peer_comparison` | Ok | Peer Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_015` | Context | `peer_comparison` | Ok | Target Minus Peer Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_016` | Context | `peer_comparison` | Ok | Target Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-528d20c0da-03-peer_comparison_017` | Context | `peer_comparison` | Ok | Context Classification: customer\_specific | Associational | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
