# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `2059`
**Run:** `9e00da1c-50fa-4c48-8677-6d5d98b38868`
**Status:** Completed
**Data:** Official Complete Journey · `bradleyboehmke/completejourney` @ `5b5d06192b9856edd04e4d405787af2f2e4a1fef`
**Execution:** Live Gemini · backend `gemini` · model `gemini-3.7-flash`
**Generated:** `2026-08-26T20:54:42.148491+00:00` · timing Actual Utc And Monotonic

## Decline summary

The deterministic detector compared weeks **38–45** with weeks **46–53**.

Detector evidence: `detector_9e00da1c-50fa-4c48-8677-6d5d98b38868` (run- and household-owned).

| Measure | Baseline | Recent | Recorded drop |
|---|---:|---:|---:|
| Retailer sales value | $248.25 | $0.00 | 100.0% |
| Distinct baskets | 6 | 0 | 100.0% |
| Active weeks | 4 | 0 | 100.0% |

- **Decline score:** 1 (weighted heuristic, not a probability)
- **Eligible:** yes
- **Flagged:** yes

## Population and comparison context

**Classification:** Customer Specific. Signed change is `(recent - baseline) / baseline`; more negative means a more severe decline. Classification evidence: `ev_call-9e00da1c50-03-peer_comparison_017`.


- **Target retailer-sales change:** -100.0%


| Comparison | Households | Median change | Interquartile range | Target percentile | Share declining | Target minus median |
|---|---:|---:|---:|---:|---:|---:|
| Eligible Population | 1312 | -3.6% | -33.4% to 29.8% | 1.21951 | 53.4% | -96.4% |
| Behavioral Peers | 50 | -4.9% | -43.5% to 32.9% | 2 | 54.0% | -95.1% |


- **Eligible-population construction:** The target is compared with the household-level distribution of signed retailer-sales changes among all other households meeting the declared baseline eligibility policy. The target is excluded, and lower change means a more severe decline.
- **Behavioral-peer construction:** Eligible target-excluded households are robust-scaled on baseline log1p retailer sales value, trip count, median basket value, active weeks, and category concentration. Scaling is fit on comparison households only; nearest Euclidean peers are selected with household-ID tie breaking.
- The target household is excluded from both comparison distributions: yes.


### Major-category contemporaneous context

| Department / category | Target change | Comparison median | Share declining | Target minus median | Households | Classification |
|---|---:|---:|---:|---:|---:|---|
| DRUG GM / CIGARETTES | -100.0% | -48.7% | 62.5% | -51.3% | 248 | Mixed |
| MEAT-PCKGD / BREAKFAST SAUSAGE/SANDWICHES | -100.0% | -45.2% | 63.0% | -54.8% | 438 | Mixed |
| DRUG GM / FALL AND WINTER SEASONAL | -100.0% | Unavailable | Unavailable | Unavailable | 10 | Insufficient Context |
| GROCERY / CHEESE | -100.0% | -13.9% | 55.3% | -86.1% | 1070 | Customer Specific |
| GROCERY / FLUID MILK PRODUCTS | -100.0% | -6.7% | 53.2% | -93.3% | 1139 | Customer Specific |
| DRUG GM / CANDY - PACKAGED | -100.0% | -58.0% | 69.5% | -42.0% | 709 | Mixed |
| GROCERY / BAKING NEEDS | -100.0% | -3.8% | 51.2% | -96.2% | 426 | Customer Specific |
| PASTRY / BREAKFAST SWEETS | -100.0% | -100.0% | 79.3% | 0.0% | 358 | Broad Context |




- Context limitation: Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.

- Context limitation: Category DRUG GM / FALL AND WINTER SEASONAL has 10 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable.

- Context limitation: Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Context limitation: Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.



## Investigation path



1. **Customer trend** — Partial
   Investigate the next permitted evidence source.
   Attempts: 1 · Retries: 0 · Recorded latency: 42.1064 ms · Evidence: `ev_call-9e00da1c50-01-customer_trend_001`, `ev_call-9e00da1c50-01-customer_trend_002`, `ev_call-9e00da1c50-01-customer_trend_003`, `ev_call-9e00da1c50-01-customer_trend_004`, `ev_call-9e00da1c50-01-customer_trend_005`, `ev_call-9e00da1c50-01-customer_trend_006`, `ev_call-9e00da1c50-01-customer_trend_007`, `ev_call-9e00da1c50-01-customer_trend_008`, `ev_call-9e00da1c50-01-customer_trend_009`, `ev_call-9e00da1c50-01-customer_trend_010`, `ev_call-9e00da1c50-01-customer_trend_011`, `ev_call-9e00da1c50-01-customer_trend_012`, `ev_call-9e00da1c50-01-customer_trend_013`, `ev_call-9e00da1c50-01-customer_trend_014`, `ev_call-9e00da1c50-01-customer_trend_015`, `ev_call-9e00da1c50-01-customer_trend_016`, `ev_call-9e00da1c50-01-customer_trend_017`, `ev_call-9e00da1c50-01-customer_trend_018`, `ev_call-9e00da1c50-01-customer_trend_019`, `ev_call-9e00da1c50-01-customer_trend_020`, `ev_call-9e00da1c50-01-customer_trend_021`, `ev_call-9e00da1c50-01-customer_trend_022`, `ev_call-9e00da1c50-01-customer_trend_023`, `ev_call-9e00da1c50-01-customer_trend_024`, `ev_call-9e00da1c50-01-customer_trend_025`, `ev_call-9e00da1c50-01-customer_trend_026`

2. **Category decomposition** — Partial
   Which merchandise categories or departments account for the baseline spend and lost sales value?
   Attempts: 1 · Retries: 0 · Recorded latency: 119.65 ms · Evidence: `ev_call-9e00da1c50-02-category_decomposition_001`, `ev_call-9e00da1c50-02-category_decomposition_002`, `ev_call-9e00da1c50-02-category_decomposition_003`, `ev_call-9e00da1c50-02-category_decomposition_004`, `ev_call-9e00da1c50-02-category_decomposition_005`, `ev_call-9e00da1c50-02-category_decomposition_006`, `ev_call-9e00da1c50-02-category_decomposition_007`, `ev_call-9e00da1c50-02-category_decomposition_008`, `ev_call-9e00da1c50-02-category_decomposition_009`, `ev_call-9e00da1c50-02-category_decomposition_010`, `ev_call-9e00da1c50-02-category_decomposition_011`, `ev_call-9e00da1c50-02-category_decomposition_012`, `ev_call-9e00da1c50-02-category_decomposition_013`, `ev_call-9e00da1c50-02-category_decomposition_014`, `ev_call-9e00da1c50-02-category_decomposition_015`, `ev_call-9e00da1c50-02-category_decomposition_016`, `ev_call-9e00da1c50-02-category_decomposition_017`, `ev_call-9e00da1c50-02-category_decomposition_018`, `ev_call-9e00da1c50-02-category_decomposition_019`, `ev_call-9e00da1c50-02-category_decomposition_020`, `ev_call-9e00da1c50-02-category_decomposition_021`, `ev_call-9e00da1c50-02-category_decomposition_022`, `ev_call-9e00da1c50-02-category_decomposition_023`, `ev_call-9e00da1c50-02-category_decomposition_024`, `ev_call-9e00da1c50-02-category_decomposition_025`, `ev_call-9e00da1c50-02-category_decomposition_026`, `ev_call-9e00da1c50-02-category_decomposition_027`, `ev_call-9e00da1c50-02-category_decomposition_028`, `ev_call-9e00da1c50-02-category_decomposition_029`, `ev_call-9e00da1c50-02-category_decomposition_030`, `ev_call-9e00da1c50-02-category_decomposition_031`, `ev_call-9e00da1c50-02-category_decomposition_032`, `ev_call-9e00da1c50-02-category_decomposition_033`, `ev_call-9e00da1c50-02-category_decomposition_034`, `ev_call-9e00da1c50-02-category_decomposition_035`, `ev_call-9e00da1c50-02-category_decomposition_036`, `ev_call-9e00da1c50-02-category_decomposition_037`, `ev_call-9e00da1c50-02-category_decomposition_038`, `ev_call-9e00da1c50-02-category_decomposition_039`, `ev_call-9e00da1c50-02-category_decomposition_040`, `ev_call-9e00da1c50-02-category_decomposition_041`, `ev_call-9e00da1c50-02-category_decomposition_042`, `ev_call-9e00da1c50-02-category_decomposition_043`, `ev_call-9e00da1c50-02-category_decomposition_044`, `ev_call-9e00da1c50-02-category_decomposition_045`, `ev_call-9e00da1c50-02-category_decomposition_046`, `ev_call-9e00da1c50-02-category_decomposition_047`, `ev_call-9e00da1c50-02-category_decomposition_048`, `ev_call-9e00da1c50-02-category_decomposition_049`, `ev_call-9e00da1c50-02-category_decomposition_050`, `ev_call-9e00da1c50-02-category_decomposition_051`, `ev_call-9e00da1c50-02-category_decomposition_052`, `ev_call-9e00da1c50-02-category_decomposition_053`, `ev_call-9e00da1c50-02-category_decomposition_054`, `ev_call-9e00da1c50-02-category_decomposition_055`, `ev_call-9e00da1c50-02-category_decomposition_056`, `ev_call-9e00da1c50-02-category_decomposition_057`, `ev_call-9e00da1c50-02-category_decomposition_058`, `ev_call-9e00da1c50-02-category_decomposition_059`, `ev_call-9e00da1c50-02-category_decomposition_060`, `ev_call-9e00da1c50-02-category_decomposition_061`, `ev_call-9e00da1c50-02-category_decomposition_062`, `ev_call-9e00da1c50-02-category_decomposition_063`, `ev_call-9e00da1c50-02-category_decomposition_064`, `ev_call-9e00da1c50-02-category_decomposition_065`, `ev_call-9e00da1c50-02-category_decomposition_066`, `ev_call-9e00da1c50-02-category_decomposition_067`, `ev_call-9e00da1c50-02-category_decomposition_068`, `ev_call-9e00da1c50-02-category_decomposition_069`, `ev_call-9e00da1c50-02-category_decomposition_070`, `ev_call-9e00da1c50-02-category_decomposition_071`, `ev_call-9e00da1c50-02-category_decomposition_072`, `ev_call-9e00da1c50-02-category_decomposition_073`

3. **Behavioral peer comparison** — Ok
   How does the target household's decline compare to the overall population and behavioral peers?
   Attempts: 1 · Retries: 0 · Recorded latency: 60.2816 ms · Evidence: `ev_call-9e00da1c50-03-peer_comparison_001`, `ev_call-9e00da1c50-03-peer_comparison_002`, `ev_call-9e00da1c50-03-peer_comparison_003`, `ev_call-9e00da1c50-03-peer_comparison_004`, `ev_call-9e00da1c50-03-peer_comparison_005`, `ev_call-9e00da1c50-03-peer_comparison_006`, `ev_call-9e00da1c50-03-peer_comparison_007`, `ev_call-9e00da1c50-03-peer_comparison_008`, `ev_call-9e00da1c50-03-peer_comparison_009`, `ev_call-9e00da1c50-03-peer_comparison_010`, `ev_call-9e00da1c50-03-peer_comparison_011`, `ev_call-9e00da1c50-03-peer_comparison_012`, `ev_call-9e00da1c50-03-peer_comparison_013`, `ev_call-9e00da1c50-03-peer_comparison_014`, `ev_call-9e00da1c50-03-peer_comparison_015`, `ev_call-9e00da1c50-03-peer_comparison_016`, `ev_call-9e00da1c50-03-peer_comparison_017`



## Likely drivers



- **Associational claim:** A recorded loss in GROCERY / CHEESE is a plausible contributor to the observed engagement decline.
  Grounded by `ev_call-9e00da1c50-02-category_decomposition_017`, `ev_call-9e00da1c50-02-category_decomposition_020`, `ev_call-9e00da1c50-02-category_decomposition_021`, `ev_call-9e00da1c50-02-category_decomposition_024`, `ev_call-9e00da1c50-02-category_decomposition_029`, `ev_call-9e00da1c50-02-category_decomposition_032`.
  Counterevidence review: No material counterevidence was cited from the available ledger.
  Claim limitations: The observational evidence supports an association, not a causal explanation of the household's behavior.




## Supporting evidence



### `ev_call-9e00da1c50-02-category_decomposition_017` — Category Retailer Sales Value

- Source: `category_decomposition` / `call-9e00da1c50-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `CHEESE`
- Baseline: 12.25 Retailer Sales Value
- Recent: 0 Retailer Sales Value
- Change: -12.25 Retailer Sales Value


### `ev_call-9e00da1c50-02-category_decomposition_020` — Contribution To Lost Retailer Sales Value

- Source: `category_decomposition` / `call-9e00da1c50-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `CHEESE`
- Value: 0.0493454 Share


### `ev_call-9e00da1c50-02-category_decomposition_021` — Category Retailer Sales Value

- Source: `category_decomposition` / `call-9e00da1c50-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `FLUID MILK PRODUCTS`
- Baseline: 11.95 Retailer Sales Value
- Recent: 0 Retailer Sales Value
- Change: -11.95 Retailer Sales Value


### `ev_call-9e00da1c50-02-category_decomposition_024` — Contribution To Lost Retailer Sales Value

- Source: `category_decomposition` / `call-9e00da1c50-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `FLUID MILK PRODUCTS`
- Value: 0.048137 Share


### `ev_call-9e00da1c50-02-category_decomposition_029` — Category Retailer Sales Value

- Source: `category_decomposition` / `call-9e00da1c50-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `BAKING NEEDS`
- Baseline: 8.56 Retailer Sales Value
- Recent: 0 Retailer Sales Value
- Change: -8.56 Retailer Sales Value


### `ev_call-9e00da1c50-02-category_decomposition_032` — Contribution To Lost Retailer Sales Value

- Source: `category_decomposition` / `call-9e00da1c50-02-category_decomposition`
- Source status: Partial
- Dimensions: Department = `GROCERY`; Direction = `loss`; Product Category = `BAKING NEEDS`
- Value: 0.0344814 Share




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

- No recent transactions were observed; per-trip statistics for that period are unavailable.

- Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.

- No recent transactions were observed; changes from that period cannot be fully compared.

- Category DRUG GM / FALL AND WINTER SEASONAL has 10 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable.

- Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.

- Customer intent and activity outside the recorded retailer data are not observed.



## Failures and partial-result warnings



- **Customer Trend — Partial.** Attempts: 1; retries: 0; recorded latency: 42.1064 ms. Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.; No recent transactions were observed; per-trip statistics for that period are unavailable.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- **Category Decomposition — Partial.** Attempts: 1; retries: 0; recorded latency: 119.65 ms. Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.; No recent transactions were observed; changes from that period cannot be fully compared.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.; Category DRUG GM / FALL AND WINTER SEASONAL has 10 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable.




## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Maximum claim | Limitations |
|---|---|---|---|---|---|---|
| `ev_call-9e00da1c50-01-customer_trend_001` | Context | `customer_trend` | Partial | Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_002` | Context | `customer_trend` | Partial | Distinct Trips | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_003` | Context | `customer_trend` | Partial | Active Weeks | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_004` | Context | `customer_trend` | Partial | Average Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_005` | Context | `customer_trend` | Partial | Median Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_006` | Context | `customer_trend` | Partial | Recorded Quantity | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-9e00da1c50-01-customer_trend_007` | Context | `customer_trend` | Partial | Distinct Products | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_008` | Context | `customer_trend` | Partial | Recency Weeks | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_009` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_010` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_011` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_012` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_013` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_014` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_015` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_016` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_017` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_018` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_019` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_020` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_021` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_022` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_023` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_024` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_025` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-01-customer_trend_026` | Context | `customer_trend` | Partial | Full Window Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_001` | Context | `category_decomposition` | Partial | Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_002` | Context | `category_decomposition` | Partial | Product Mapping Line Item Coverage | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_003` | Context | `category_decomposition` | Partial | Product Mapping Distinct Product Coverage | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_004` | Context | `category_decomposition` | Partial | Unknown Group Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_005` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_006` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_007` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_008` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_009` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_010` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_011` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_012` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_013` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_014` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_015` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_016` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_017` | Supporting | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_018` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_019` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_020` | Supporting | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_021` | Supporting | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_022` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_023` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_024` | Supporting | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_025` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_026` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_027` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_028` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_029` | Supporting | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_030` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_031` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_032` | Supporting | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_033` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_034` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_035` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_036` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-9e00da1c50-02-category_decomposition_037` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_038` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_039` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_040` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_041` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_042` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_043` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_044` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_045` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_046` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_047` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.; Category DRUG GM / FALL AND WINTER SEASONAL has 10 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable. |
| `ev_call-9e00da1c50-02-category_decomposition_048` | Context | `category_decomposition` | Partial | Category Context Classification: insufficient\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.; Category DRUG GM / FALL AND WINTER SEASONAL has 10 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable. |
| `ev_call-9e00da1c50-02-category_decomposition_049` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_050` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_051` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_052` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_053` | Context | `category_decomposition` | Partial | Category Context Classification: customer\_specific | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_054` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_055` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_056` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_057` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_058` | Context | `category_decomposition` | Partial | Category Context Classification: customer\_specific | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_059` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_060` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_061` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_062` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_063` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_064` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_065` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_066` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_067` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_068` | Context | `category_decomposition` | Partial | Category Context Classification: customer\_specific | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_069` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_070` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_071` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_072` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-02-category_decomposition_073` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-9e00da1c50-03-peer_comparison_001` | Context | `peer_comparison` | Ok | Target Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_002` | Context | `peer_comparison` | Ok | Population Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_003` | Context | `peer_comparison` | Ok | Peer Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_004` | Context | `peer_comparison` | Ok | Population Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_005` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_006` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_007` | Context | `peer_comparison` | Ok | Target Population Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_008` | Context | `peer_comparison` | Ok | Population Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_009` | Context | `peer_comparison` | Ok | Target Minus Population Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_010` | Context | `peer_comparison` | Ok | Peer Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_011` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_012` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_013` | Context | `peer_comparison` | Ok | Target Peer Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_014` | Context | `peer_comparison` | Ok | Peer Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_015` | Context | `peer_comparison` | Ok | Target Minus Peer Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_016` | Context | `peer_comparison` | Ok | Target Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-9e00da1c50-03-peer_comparison_017` | Context | `peer_comparison` | Ok | Context Classification: customer\_specific | Associational | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
