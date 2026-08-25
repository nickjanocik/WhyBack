# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `101`
**Run:** `db94dd49-c6a1-5bb1-9ef1-2447ecc8bab0`
**Status:** Completed
**Data:** Synthetic · `whyback/synthetic-fixture` @ `whyback-synthetic-fixture-v1`
**Execution:** Scripted Control · backend `scripted` · model `scripted/whyback-v1`
**Generated:** `2026-08-25T17:53:44.161456+00:00` · timing Actual Utc And Monotonic

## Decline summary

The deterministic detector compared weeks **1–8** with weeks **9–16**.

Detector evidence: `detector_db94dd49-c6a1-5bb1-9ef1-2447ecc8bab0` (run- and household-owned).

| Measure | Baseline | Recent | Recorded drop |
|---|---:|---:|---:|
| Retailer sales value | $160.00 | $12.00 | 92.5% |
| Distinct baskets | 16 | 2 | 87.5% |
| Active weeks | 8 | 2 | 75.0% |

- **Decline score:** 0.875 (weighted heuristic, not a probability)
- **Eligible:** yes
- **Flagged:** yes

## Population and comparison context

**Classification:** Mixed. Signed change is `(recent - baseline) / baseline`; more negative means a more severe decline. Classification evidence: `ev_call-db94dd49c6-04-peer_comparison_017`.


- **Target retailer-sales change:** -92.5%


| Comparison | Households | Median change | Interquartile range | Target percentile | Share declining | Target minus median |
|---|---:|---:|---:|---:|---:|---:|
| Eligible Population | 23 | -50.0% | -50.0% to -50.0% | 0 | 100.0% | -42.5% |
| Behavioral Peers | 23 | -50.0% | -50.0% to -50.0% | 0 | 100.0% | -42.5% |


- **Eligible-population construction:** The target is compared with the household-level distribution of signed retailer-sales changes among all other households meeting the declared baseline eligibility policy. The target is excluded, and lower change means a more severe decline.
- **Behavioral-peer construction:** Eligible target-excluded households are robust-scaled on baseline log1p retailer sales value, trip count, median basket value, active weeks, and category concentration. Scaling is fit on comparison households only; nearest Euclidean peers are selected with household-ID tie breaking.
- The target household is excluded from both comparison distributions: yes.


No reliable major-category comparison was computed in this bounded investigation.



- Context limitation: Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Context limitation: Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.

- Context limitation: Only 23 eligible peers were available instead of the requested 50.



## Investigation path



1. **Coupon campaign history** — Partial
   What campaign and coupon information is known or unavailable?
   Attempts: 1 · Retries: 0 · Recorded latency: 7.55958 ms · Evidence: `ev_call-db94dd49c6-01-coupon_campaign_history_001`, `ev_call-db94dd49c6-01-coupon_campaign_history_002`, `ev_call-db94dd49c6-01-coupon_campaign_history_003`, `ev_call-db94dd49c6-01-coupon_campaign_history_004`, `ev_call-db94dd49c6-01-coupon_campaign_history_005`

2. **Customer trend** — Ok
   Is the decline primarily frequency or value related?
   Attempts: 1 · Retries: 0 · Recorded latency: 10.1047 ms · Evidence: `ev_call-db94dd49c6-02-customer_trend_001`, `ev_call-db94dd49c6-02-customer_trend_002`, `ev_call-db94dd49c6-02-customer_trend_003`, `ev_call-db94dd49c6-02-customer_trend_004`, `ev_call-db94dd49c6-02-customer_trend_005`, `ev_call-db94dd49c6-02-customer_trend_006`, `ev_call-db94dd49c6-02-customer_trend_007`, `ev_call-db94dd49c6-02-customer_trend_008`, `ev_call-db94dd49c6-02-customer_trend_009`, `ev_call-db94dd49c6-02-customer_trend_010`, `ev_call-db94dd49c6-02-customer_trend_011`, `ev_call-db94dd49c6-02-customer_trend_012`, `ev_call-db94dd49c6-02-customer_trend_013`, `ev_call-db94dd49c6-02-customer_trend_014`, `ev_call-db94dd49c6-02-customer_trend_015`, `ev_call-db94dd49c6-02-customer_trend_016`, `ev_call-db94dd49c6-02-customer_trend_017`, `ev_call-db94dd49c6-02-customer_trend_018`, `ev_call-db94dd49c6-02-customer_trend_019`, `ev_call-db94dd49c6-02-customer_trend_020`, `ev_call-db94dd49c6-02-customer_trend_021`, `ev_call-db94dd49c6-02-customer_trend_022`, `ev_call-db94dd49c6-02-customer_trend_023`, `ev_call-db94dd49c6-02-customer_trend_024`, `ev_call-db94dd49c6-02-customer_trend_025`, `ev_call-db94dd49c6-02-customer_trend_026`

3. **Basket behavior** — Ok
   Did basket size, cadence, or store behavior change?
   Attempts: 1 · Retries: 0 · Recorded latency: 2.88046 ms · Evidence: `ev_call-db94dd49c6-03-basket_behavior_001`, `ev_call-db94dd49c6-03-basket_behavior_002`, `ev_call-db94dd49c6-03-basket_behavior_003`, `ev_call-db94dd49c6-03-basket_behavior_004`, `ev_call-db94dd49c6-03-basket_behavior_005`, `ev_call-db94dd49c6-03-basket_behavior_006`, `ev_call-db94dd49c6-03-basket_behavior_007`, `ev_call-db94dd49c6-03-basket_behavior_008`, `ev_call-db94dd49c6-03-basket_behavior_009`, `ev_call-db94dd49c6-03-basket_behavior_010`, `ev_call-db94dd49c6-03-basket_behavior_011`, `ev_call-db94dd49c6-03-basket_behavior_012`, `ev_call-db94dd49c6-03-basket_behavior_013`, `ev_call-db94dd49c6-03-basket_behavior_014`, `ev_call-db94dd49c6-03-basket_behavior_015`, `ev_call-db94dd49c6-03-basket_behavior_016`

4. **Behavioral peer comparison** — Partial
   How unusual is the decline among behaviorally similar households?
   Attempts: 1 · Retries: 0 · Recorded latency: 8.21392 ms · Evidence: `ev_call-db94dd49c6-04-peer_comparison_001`, `ev_call-db94dd49c6-04-peer_comparison_002`, `ev_call-db94dd49c6-04-peer_comparison_003`, `ev_call-db94dd49c6-04-peer_comparison_004`, `ev_call-db94dd49c6-04-peer_comparison_005`, `ev_call-db94dd49c6-04-peer_comparison_006`, `ev_call-db94dd49c6-04-peer_comparison_007`, `ev_call-db94dd49c6-04-peer_comparison_008`, `ev_call-db94dd49c6-04-peer_comparison_009`, `ev_call-db94dd49c6-04-peer_comparison_010`, `ev_call-db94dd49c6-04-peer_comparison_011`, `ev_call-db94dd49c6-04-peer_comparison_012`, `ev_call-db94dd49c6-04-peer_comparison_013`, `ev_call-db94dd49c6-04-peer_comparison_014`, `ev_call-db94dd49c6-04-peer_comparison_015`, `ev_call-db94dd49c6-04-peer_comparison_016`, `ev_call-db94dd49c6-04-peer_comparison_017`



## Likely drivers



- **Associational claim:** Reduced recorded visit cadence is a plausible contributor to the observed engagement decline.
  Grounded by `ev_call-db94dd49c6-02-customer_trend_002`, `ev_call-db94dd49c6-03-basket_behavior_001`.
  Counterevidence: `ev_call-db94dd49c6-04-peer_comparison_017`.
  Claim limitations: The observational evidence supports an association, not a causal explanation of the household's behavior.




## Supporting evidence



### `ev_call-db94dd49c6-02-customer_trend_002` — Distinct Trips

- Source: `customer_trend` / `call-db94dd49c6-02-customer_trend`
- Source status: Ok
- Baseline: 16 Count
- Recent: 2 Count
- Change: -14 Count


### `ev_call-db94dd49c6-03-basket_behavior_001` — Basket Count

- Source: `basket_behavior` / `call-db94dd49c6-03-basket_behavior`
- Source status: Ok
- Baseline: 16 Count
- Recent: 2 Count
- Change: -14 Count




## What this analysis can establish


- Recorded retailer sales value, distinct baskets, and active weeks in the declared baseline and recent windows.

- The household's relative position among target-excluded eligible households and behavioral peers.

- Recorded campaign participation, coupon redemption, and available delivery facts.


## What this analysis cannot establish


- The source is observational: current evidence supports descriptive and associational claims, not causal claims.

- Marketing treatment may be targeted from prior behavior, so campaign and purchasing associations can reflect selection into treatment.

- Whether a recommended action changes behavior must be learned through a valid prospective design such as the stated randomized holdout.


## Unobserved factors and alternative explanations


- Unobserved: Purchases at competitors, restaurants, and other online or offline channels.

- Unobserved: Relocation, travel, income or employment changes, household-composition changes, health, diet, and transportation access.

- Unobserved: Customer satisfaction, service experiences, stockouts, discontinuations, assortment changes, and competitor conditions.

- Unobserved: Customer intent and whether a particular household member noticed an advertisement or promotion.

- Unobserved: The data cannot distinguish broad contemporaneous movement caused by holidays, prices, retailer conditions, economic effects, weather, or other common factors.



- Alternative: Recorded evidence does not distinguish the observed signal from unobserved activity outside this retailer.



## Counterevidence review



- `ev_call-db94dd49c6-04-peer_comparison_017` — **Context Classification**; source status Partial. Limitations: Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50..



## Next Best Action


**VISIT\_FREQUENCY\_REACTIVATION** — Recommend a human-reviewed reactivation test focused on restoring shopping cadence when visit-frequency evidence, rather than basket value alone, supports the decline.

The cited records satisfy the selected catalog action's machine-checkable evidence policy; the recommendation remains a human-reviewed test.

Resolved confidence: **Medium** (deterministic cap applied).

- Confidence adjustment: Population and peer context is mixed, so a uniquely customer-specific interpretation cannot receive high confidence. Maximum confidence: **Medium**. Context: **Mixed**. Evidence: `ev_call-db94dd49c6-04-peer_comparison_017`.



## Measurement plan


- **Framing:** This is a hypothesis to test, not a promised retention effect.
- **Success metric:** Change in distinct shopping trips per week relative to an eligible holdout over the evaluation window.
- **Suggested experiment:** Randomize eligible households between a reviewer-approved cadence treatment and no treatment, then compare distinct trips per week.


## Limitations



- Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable.

- Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.

- Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.

- Only 23 eligible peers were available instead of the requested 50.

- Customer intent and activity outside the recorded retailer data are not observed.



## Failures and partial-result warnings



- **Coupon Campaign History — Partial.** Attempts: 1; retries: 0; recorded latency: 7.55958 ms. Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable.

- **Peer Comparison — Partial.** Attempts: 1; retries: 0; recorded latency: 8.21392 ms. Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50.




## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Maximum claim | Limitations |
|---|---|---|---|---|---|---|
| `ev_call-db94dd49c6-01-coupon_campaign_history_001` | Context | `coupon_campaign_history` | Partial | Campaign Participation Count | Associational | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-db94dd49c6-01-coupon_campaign_history_002` | Context | `coupon_campaign_history` | Partial | Coupon Redemption Count | Associational | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-db94dd49c6-01-coupon_campaign_history_003` | Context | `coupon_campaign_history` | Partial | Transaction Coupon Baskets | Associational | None recorded |
| `ev_call-db94dd49c6-01-coupon_campaign_history_004` | Context | `coupon_campaign_history` | Partial | Recorded Coupon Discount | Associational | None recorded |
| `ev_call-db94dd49c6-01-coupon_campaign_history_005` | Context | `coupon_campaign_history` | Partial | Campaign Participation | Associational | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-db94dd49c6-02-customer_trend_001` | Context | `customer_trend` | Ok | Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_002` | Supporting | `customer_trend` | Ok | Distinct Trips | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_003` | Context | `customer_trend` | Ok | Active Weeks | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_004` | Context | `customer_trend` | Ok | Average Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_005` | Context | `customer_trend` | Ok | Median Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_006` | Context | `customer_trend` | Ok | Recorded Quantity | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-db94dd49c6-02-customer_trend_007` | Context | `customer_trend` | Ok | Distinct Products | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_008` | Context | `customer_trend` | Ok | Recency Weeks | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_009` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_010` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_011` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_012` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_013` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_014` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_015` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_016` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_017` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_018` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_019` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_020` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_021` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_022` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_023` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_024` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_025` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_026` | Context | `customer_trend` | Ok | Full Window Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_001` | Supporting | `basket_behavior` | Ok | Basket Count | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_002` | Context | `basket_behavior` | Ok | Active Weeks | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_003` | Context | `basket_behavior` | Ok | Baskets Per Calendar Week | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_004` | Context | `basket_behavior` | Ok | Mean Basket Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_005` | Context | `basket_behavior` | Ok | Median Basket Retailer Sales Value | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_006` | Context | `basket_behavior` | Ok | Mean Recorded Quantity Per Basket | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-db94dd49c6-03-basket_behavior_007` | Context | `basket_behavior` | Ok | Median Recorded Quantity Per Basket | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-db94dd49c6-03-basket_behavior_008` | Context | `basket_behavior` | Ok | Mean Distinct Products Per Basket | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_009` | Context | `basket_behavior` | Ok | Mean Distinct Categories Per Basket | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_010` | Context | `basket_behavior` | Ok | Mean Basket Interval Days | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_011` | Context | `basket_behavior` | Ok | Median Basket Interval Days | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_012` | Context | `basket_behavior` | Ok | Primary Store Share | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_013` | Context | `basket_behavior` | Ok | Stores Visited | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_014` | Context | `basket_behavior` | Ok | Consecutive Store Switch Rate | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_015` | Context | `basket_behavior` | Ok | Primary Store Changed | Associational | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_016` | Context | `basket_behavior` | Ok | Recent Baskets At New Store Share | Associational | None recorded |
| `ev_call-db94dd49c6-04-peer_comparison_001` | Context | `peer_comparison` | Partial | Target Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_002` | Context | `peer_comparison` | Partial | Population Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_003` | Context | `peer_comparison` | Partial | Peer Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_004` | Context | `peer_comparison` | Partial | Population Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_005` | Context | `peer_comparison` | Partial | Population Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_006` | Context | `peer_comparison` | Partial | Population Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_007` | Context | `peer_comparison` | Partial | Target Population Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_008` | Context | `peer_comparison` | Partial | Population Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_009` | Context | `peer_comparison` | Partial | Target Minus Population Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_010` | Context | `peer_comparison` | Partial | Peer Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_011` | Context | `peer_comparison` | Partial | Peer Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_012` | Context | `peer_comparison` | Partial | Peer Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_013` | Context | `peer_comparison` | Partial | Target Peer Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_014` | Context | `peer_comparison` | Partial | Peer Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_015` | Context | `peer_comparison` | Partial | Target Minus Peer Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_016` | Context | `peer_comparison` | Partial | Target Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
| `ev_call-db94dd49c6-04-peer_comparison_017` | Counterevidence | `peer_comparison` | Partial | Context Classification: mixed | Associational | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.; Only 23 eligible peers were available instead of the requested 50. |
