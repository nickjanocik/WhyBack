# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `1468`
**Run:** `65e8bdb5-9fcc-46cc-94f1-8dcaef8ad05d`
**Status:** Completed
**Data:** Official Complete Journey · `bradleyboehmke/completejourney` @ `5b5d06192b9856edd04e4d405787af2f2e4a1fef`
**Execution:** Live Gemini · backend `gemini` · model `gemini-3.7-flash`
**Generated:** `2026-08-26T20:53:37.890443+00:00` · timing Actual Utc And Monotonic

## Decline summary

The deterministic detector compared weeks **38–45** with weeks **46–53**.

Detector evidence: `detector_65e8bdb5-9fcc-46cc-94f1-8dcaef8ad05d` (run- and household-owned).

| Measure | Baseline | Recent | Recorded drop |
|---|---:|---:|---:|
| Retailer sales value | $312.05 | $0.00 | 100.0% |
| Distinct baskets | 9 | 0 | 100.0% |
| Active weeks | 4 | 0 | 100.0% |

- **Decline score:** 1 (weighted heuristic, not a probability)
- **Eligible:** yes
- **Flagged:** yes

## Population and comparison context

**Classification:** Insufficient Context. Signed change is `(recent - baseline) / baseline`; more negative means a more severe decline.


- **Target retailer-sales change:** comparison evidence was not computed.


| Comparison | Households | Median change | Interquartile range | Target percentile | Share declining | Target minus median |
|---|---:|---:|---:|---:|---:|---:|
| Eligible Population | 0 | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable |
| Behavioral Peers | 0 | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable |


- **Eligible-population construction:** Households meeting the declared baseline active-week, distinct-basket, and positive retailer-sales eligibility criteria; the target is excluded.
- **Behavioral-peer construction:** Nearest target-excluded households after robust scaling of declared baseline behavioral features; demographics are not used.
- The target household is excluded from both comparison distributions: yes.


### Major-category contemporaneous context

| Department / category | Target change | Comparison median | Share declining | Target minus median | Households | Classification |
|---|---:|---:|---:|---:|---:|---|
| FUEL / COUPON/MISC ITEMS | -100.0% | -25.0% | 64.4% | -75.0% | 509 | Mixed |
| GROCERY / BATH TISSUES | -100.0% | -41.0% | 63.2% | -59.0% | 560 | Mixed |
| GROCERY / CHEESE | -100.0% | -13.9% | 55.3% | -86.1% | 1070 | Customer Specific |
| GROCERY / FRZN NOVELTIES/WTR ICE | -100.0% | -100.0% | 80.3% | 0.0% | 355 | Broad Context |
| GROCERY / SOFT DRINKS | -100.0% | -12.1% | 55.7% | -87.9% | 1034 | Customer Specific |
| PRODUCE / SALAD MIX | -100.0% | -50.0% | 68.0% | -50.0% | 490 | Mixed |
| GROCERY / SOUP | -100.0% | -37.6% | 63.8% | -62.4% | 828 | Mixed |
| DELI / SANDWICHES | -100.0% | -100.0% | 92.1% | 0.0% | 38 | Broad Context |




- Context limitation: Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.



## Investigation path



1. **Customer trend** — Partial
   How did the household's sales value, trips, and cadence change over time?
   Attempts: 1 · Retries: 0 · Recorded latency: 63.3244 ms · Evidence: `ev_call-65e8bdb59f-01-customer_trend_001`, `ev_call-65e8bdb59f-01-customer_trend_002`, `ev_call-65e8bdb59f-01-customer_trend_003`, `ev_call-65e8bdb59f-01-customer_trend_004`, `ev_call-65e8bdb59f-01-customer_trend_005`, `ev_call-65e8bdb59f-01-customer_trend_006`, `ev_call-65e8bdb59f-01-customer_trend_007`, `ev_call-65e8bdb59f-01-customer_trend_008`, `ev_call-65e8bdb59f-01-customer_trend_009`, `ev_call-65e8bdb59f-01-customer_trend_010`, `ev_call-65e8bdb59f-01-customer_trend_011`, `ev_call-65e8bdb59f-01-customer_trend_012`, `ev_call-65e8bdb59f-01-customer_trend_013`, `ev_call-65e8bdb59f-01-customer_trend_014`, `ev_call-65e8bdb59f-01-customer_trend_015`, `ev_call-65e8bdb59f-01-customer_trend_016`, `ev_call-65e8bdb59f-01-customer_trend_017`, `ev_call-65e8bdb59f-01-customer_trend_018`, `ev_call-65e8bdb59f-01-customer_trend_019`, `ev_call-65e8bdb59f-01-customer_trend_020`, `ev_call-65e8bdb59f-01-customer_trend_021`, `ev_call-65e8bdb59f-01-customer_trend_022`, `ev_call-65e8bdb59f-01-customer_trend_023`, `ev_call-65e8bdb59f-01-customer_trend_024`, `ev_call-65e8bdb59f-01-customer_trend_025`, `ev_call-65e8bdb59f-01-customer_trend_026`

2. **Category decomposition** — Partial
   Which departments and product categories contributed most to the change in retailer sales value?
   Attempts: 1 · Retries: 0 · Recorded latency: 111.374 ms · Evidence: `ev_call-65e8bdb59f-02-category_decomposition_001`, `ev_call-65e8bdb59f-02-category_decomposition_002`, `ev_call-65e8bdb59f-02-category_decomposition_003`, `ev_call-65e8bdb59f-02-category_decomposition_004`, `ev_call-65e8bdb59f-02-category_decomposition_005`, `ev_call-65e8bdb59f-02-category_decomposition_006`, `ev_call-65e8bdb59f-02-category_decomposition_007`, `ev_call-65e8bdb59f-02-category_decomposition_008`, `ev_call-65e8bdb59f-02-category_decomposition_009`, `ev_call-65e8bdb59f-02-category_decomposition_010`, `ev_call-65e8bdb59f-02-category_decomposition_011`, `ev_call-65e8bdb59f-02-category_decomposition_012`, `ev_call-65e8bdb59f-02-category_decomposition_013`, `ev_call-65e8bdb59f-02-category_decomposition_014`, `ev_call-65e8bdb59f-02-category_decomposition_015`, `ev_call-65e8bdb59f-02-category_decomposition_016`, `ev_call-65e8bdb59f-02-category_decomposition_017`, `ev_call-65e8bdb59f-02-category_decomposition_018`, `ev_call-65e8bdb59f-02-category_decomposition_019`, `ev_call-65e8bdb59f-02-category_decomposition_020`, `ev_call-65e8bdb59f-02-category_decomposition_021`, `ev_call-65e8bdb59f-02-category_decomposition_022`, `ev_call-65e8bdb59f-02-category_decomposition_023`, `ev_call-65e8bdb59f-02-category_decomposition_024`, `ev_call-65e8bdb59f-02-category_decomposition_025`, `ev_call-65e8bdb59f-02-category_decomposition_026`, `ev_call-65e8bdb59f-02-category_decomposition_027`, `ev_call-65e8bdb59f-02-category_decomposition_028`, `ev_call-65e8bdb59f-02-category_decomposition_029`, `ev_call-65e8bdb59f-02-category_decomposition_030`, `ev_call-65e8bdb59f-02-category_decomposition_031`, `ev_call-65e8bdb59f-02-category_decomposition_032`, `ev_call-65e8bdb59f-02-category_decomposition_033`, `ev_call-65e8bdb59f-02-category_decomposition_034`, `ev_call-65e8bdb59f-02-category_decomposition_035`, `ev_call-65e8bdb59f-02-category_decomposition_036`, `ev_call-65e8bdb59f-02-category_decomposition_037`, `ev_call-65e8bdb59f-02-category_decomposition_038`, `ev_call-65e8bdb59f-02-category_decomposition_039`, `ev_call-65e8bdb59f-02-category_decomposition_040`, `ev_call-65e8bdb59f-02-category_decomposition_041`, `ev_call-65e8bdb59f-02-category_decomposition_042`, `ev_call-65e8bdb59f-02-category_decomposition_043`, `ev_call-65e8bdb59f-02-category_decomposition_044`, `ev_call-65e8bdb59f-02-category_decomposition_045`, `ev_call-65e8bdb59f-02-category_decomposition_046`, `ev_call-65e8bdb59f-02-category_decomposition_047`, `ev_call-65e8bdb59f-02-category_decomposition_048`, `ev_call-65e8bdb59f-02-category_decomposition_049`, `ev_call-65e8bdb59f-02-category_decomposition_050`, `ev_call-65e8bdb59f-02-category_decomposition_051`, `ev_call-65e8bdb59f-02-category_decomposition_052`, `ev_call-65e8bdb59f-02-category_decomposition_053`, `ev_call-65e8bdb59f-02-category_decomposition_054`, `ev_call-65e8bdb59f-02-category_decomposition_055`, `ev_call-65e8bdb59f-02-category_decomposition_056`, `ev_call-65e8bdb59f-02-category_decomposition_057`, `ev_call-65e8bdb59f-02-category_decomposition_058`, `ev_call-65e8bdb59f-02-category_decomposition_059`, `ev_call-65e8bdb59f-02-category_decomposition_060`, `ev_call-65e8bdb59f-02-category_decomposition_061`, `ev_call-65e8bdb59f-02-category_decomposition_062`, `ev_call-65e8bdb59f-02-category_decomposition_063`, `ev_call-65e8bdb59f-02-category_decomposition_064`, `ev_call-65e8bdb59f-02-category_decomposition_065`, `ev_call-65e8bdb59f-02-category_decomposition_066`, `ev_call-65e8bdb59f-02-category_decomposition_067`, `ev_call-65e8bdb59f-02-category_decomposition_068`, `ev_call-65e8bdb59f-02-category_decomposition_069`, `ev_call-65e8bdb59f-02-category_decomposition_070`, `ev_call-65e8bdb59f-02-category_decomposition_071`, `ev_call-65e8bdb59f-02-category_decomposition_072`, `ev_call-65e8bdb59f-02-category_decomposition_073`, `ev_call-65e8bdb59f-02-category_decomposition_074`, `ev_call-65e8bdb59f-02-category_decomposition_075`, `ev_call-65e8bdb59f-02-category_decomposition_076`



## Likely drivers



- **Associational claim:** A recorded loss in GROCERY / CHEESE is a plausible contributor to the observed engagement decline.
  Grounded by `ev_call-65e8bdb59f-02-category_decomposition_013`, `ev_call-65e8bdb59f-02-category_decomposition_016`, `ev_call-65e8bdb59f-02-category_decomposition_021`, `ev_call-65e8bdb59f-02-category_decomposition_024`.
  Counterevidence review: No material counterevidence was cited from the available ledger.
  Claim limitations: The observational evidence supports an association, not a causal explanation of the household's behavior.




## Supporting evidence



### `ev_call-65e8bdb59f-02-category_decomposition_013` — Category Retailer Sales Value

- Source: `category_decomposition` / `call-65e8bdb59f-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `CHEESE`
- Baseline: 16.16 Retailer Sales Value
- Recent: 0 Retailer Sales Value
- Change: -16.16 Retailer Sales Value


### `ev_call-65e8bdb59f-02-category_decomposition_016` — Contribution To Lost Retailer Sales Value

- Source: `category_decomposition` / `call-65e8bdb59f-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `CHEESE`
- Value: 0.0517866 Share


### `ev_call-65e8bdb59f-02-category_decomposition_021` — Category Retailer Sales Value

- Source: `category_decomposition` / `call-65e8bdb59f-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `SOFT DRINKS`
- Baseline: 12.12 Retailer Sales Value
- Recent: 0 Retailer Sales Value
- Change: -12.12 Retailer Sales Value


### `ev_call-65e8bdb59f-02-category_decomposition_024` — Contribution To Lost Retailer Sales Value

- Source: `category_decomposition` / `call-65e8bdb59f-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `SOFT DRINKS`
- Value: 0.0388399 Share




## What this analysis can establish


- Recorded retailer sales value, distinct baskets, and active weeks in the declared baseline and recent windows.

- Recorded category movement, including explicit UNKNOWN mappings and reconciled retailer-sales totals.


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

Resolved confidence: **Medium**.

- Confidence adjustment: Population or peer context is insufficient, so missing comparison evidence cannot be treated as neutral. Maximum confidence: **Medium**. Context: **Insufficient Context**.



## Measurement plan


- **Framing:** This is a hypothesis to test, not a promised retention effect.
- **Success metric:** Change in retailer sales value for the selected category relative to an eligible holdout over the evaluation window.
- **Suggested experiment:** Randomize eligible households between a reviewer-approved category treatment and no treatment, preserving a ten-percent holdout.


## Limitations



- Source week 53 contains fewer calendar days than an ordinary week.

- Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.

- No recent transactions were observed; per-trip statistics for that period are unavailable.

- Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.

- No recent transactions were observed; changes from that period cannot be fully compared.

- Eligible-population and behavioral-peer context was not available; missing context must not be interpreted as neutral movement.

- Customer intent and activity outside the recorded retailer data are not observed.



## Failures and partial-result warnings



- **Customer Trend — Partial.** Attempts: 1; retries: 0; recorded latency: 63.3244 ms. Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.; No recent transactions were observed; per-trip statistics for that period are unavailable.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- **Category Decomposition — Partial.** Attempts: 1; retries: 0; recorded latency: 111.374 ms. Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.; No recent transactions were observed; changes from that period cannot be fully compared.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.




## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Maximum claim | Limitations |
|---|---|---|---|---|---|---|
| `ev_call-65e8bdb59f-01-customer_trend_001` | Context | `customer_trend` | Partial | Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_002` | Context | `customer_trend` | Partial | Distinct Trips | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_003` | Context | `customer_trend` | Partial | Active Weeks | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_004` | Context | `customer_trend` | Partial | Average Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_005` | Context | `customer_trend` | Partial | Median Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_006` | Context | `customer_trend` | Partial | Recorded Quantity | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-65e8bdb59f-01-customer_trend_007` | Context | `customer_trend` | Partial | Distinct Products | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_008` | Context | `customer_trend` | Partial | Recency Weeks | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_009` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_010` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_011` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_012` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_013` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_014` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_015` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_016` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_017` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_018` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_019` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_020` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_021` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_022` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_023` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_024` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_025` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-01-customer_trend_026` | Context | `customer_trend` | Partial | Full Window Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_001` | Context | `category_decomposition` | Partial | Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_002` | Context | `category_decomposition` | Partial | Product Mapping Line Item Coverage | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_003` | Context | `category_decomposition` | Partial | Product Mapping Distinct Product Coverage | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_004` | Context | `category_decomposition` | Partial | Unknown Group Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_005` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_006` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_007` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_008` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_009` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_010` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_011` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_012` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_013` | Supporting | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_014` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_015` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_016` | Supporting | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_017` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_018` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_019` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_020` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_021` | Supporting | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_022` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_023` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_024` | Supporting | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_025` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_026` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_027` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_028` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_029` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_030` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_031` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_032` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_033` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_034` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_035` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_036` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-65e8bdb59f-02-category_decomposition_037` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_038` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_039` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_040` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_041` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_042` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_043` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_044` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_045` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_046` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_047` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_048` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_049` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_050` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_051` | Context | `category_decomposition` | Partial | Category Context Classification: customer\_specific | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_052` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_053` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_054` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_055` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_056` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_057` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_058` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_059` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_060` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_061` | Context | `category_decomposition` | Partial | Category Context Classification: customer\_specific | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_062` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_063` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_064` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_065` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_066` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_067` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_068` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_069` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_070` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_071` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_072` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_073` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_074` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_075` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-65e8bdb59f-02-category_decomposition_076` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
