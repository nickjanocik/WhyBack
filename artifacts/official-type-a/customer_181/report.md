# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `181`
**Run:** `2e442f80-a9d4-5642-9cf3-b66cfc423aa6`
**Status:** Completed
**Data:** Official Complete Journey · `bradleyboehmke/completejourney` @ `5b5d06192b9856edd04e4d405787af2f2e4a1fef`
**Execution:** Scripted Control · backend `scripted` · model `scripted/whyback-v1`
**Generated:** `2026-08-26T06:18:58.167097+00:00` · timing Actual Utc And Monotonic

## Decline summary

The deterministic detector compared weeks **38–45** with weeks **46–53**.

Detector evidence: `detector_2e442f80-a9d4-5642-9cf3-b66cfc423aa6` (run- and household-owned).

| Measure | Baseline | Recent | Recorded drop |
|---|---:|---:|---:|
| Retailer sales value | $304.19 | $0.00 | 100.0% |
| Distinct baskets | 7 | 0 | 100.0% |
| Active weeks | 5 | 0 | 100.0% |

- **Decline score:** 1 (weighted heuristic, not a probability)
- **Eligible:** yes
- **Flagged:** yes

## Population and comparison context

**Classification:** Mixed. Signed change is `(recent - baseline) / baseline`; more negative means a more severe decline. Classification evidence: `ev_call-2e442f80a9-04-peer_comparison_017`.


- **Target retailer-sales change:** -100.0%


| Comparison | Households | Median change | Interquartile range | Target percentile | Share declining | Target minus median |
|---|---:|---:|---:|---:|---:|---:|
| Eligible Population | 1312 | -3.6% | -33.4% to 29.8% | 1.21951 | 53.4% | -96.4% |
| Behavioral Peers | 50 | -9.3% | -49.9% to 3.6% | 2 | 66.0% | -90.7% |


- **Eligible-population construction:** The target is compared with the household-level distribution of signed retailer-sales changes among all other households meeting the declared baseline eligibility policy. The target is excluded, and lower change means a more severe decline.
- **Behavioral-peer construction:** Eligible target-excluded households are robust-scaled on baseline log1p retailer sales value, trip count, median basket value, active weeks, and category concentration. Scaling is fit on comparison households only; nearest Euclidean peers are selected with household-ID tie breaking.
- The target household is excluded from both comparison distributions: yes.


No reliable major-category comparison was computed in this bounded investigation.



- Context limitation: Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Context limitation: Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.



## Investigation path



1. **Coupon campaign history** — Partial
   What campaign and coupon information is known or unavailable?
   Attempts: 1 · Retries: 0 · Recorded latency: 28.1892 ms · Evidence: `ev_call-2e442f80a9-01-coupon_campaign_history_001`, `ev_call-2e442f80a9-01-coupon_campaign_history_002`, `ev_call-2e442f80a9-01-coupon_campaign_history_003`, `ev_call-2e442f80a9-01-coupon_campaign_history_004`, `ev_call-2e442f80a9-01-coupon_campaign_history_005`, `ev_call-2e442f80a9-01-coupon_campaign_history_006`, `ev_call-2e442f80a9-01-coupon_campaign_history_007`

2. **Customer trend** — Partial
   Is the decline primarily frequency or value related?
   Attempts: 1 · Retries: 0 · Recorded latency: 54.9123 ms · Evidence: `ev_call-2e442f80a9-02-customer_trend_001`, `ev_call-2e442f80a9-02-customer_trend_002`, `ev_call-2e442f80a9-02-customer_trend_003`, `ev_call-2e442f80a9-02-customer_trend_004`, `ev_call-2e442f80a9-02-customer_trend_005`, `ev_call-2e442f80a9-02-customer_trend_006`, `ev_call-2e442f80a9-02-customer_trend_007`, `ev_call-2e442f80a9-02-customer_trend_008`, `ev_call-2e442f80a9-02-customer_trend_009`, `ev_call-2e442f80a9-02-customer_trend_010`, `ev_call-2e442f80a9-02-customer_trend_011`, `ev_call-2e442f80a9-02-customer_trend_012`, `ev_call-2e442f80a9-02-customer_trend_013`, `ev_call-2e442f80a9-02-customer_trend_014`, `ev_call-2e442f80a9-02-customer_trend_015`, `ev_call-2e442f80a9-02-customer_trend_016`, `ev_call-2e442f80a9-02-customer_trend_017`, `ev_call-2e442f80a9-02-customer_trend_018`, `ev_call-2e442f80a9-02-customer_trend_019`, `ev_call-2e442f80a9-02-customer_trend_020`, `ev_call-2e442f80a9-02-customer_trend_021`, `ev_call-2e442f80a9-02-customer_trend_022`, `ev_call-2e442f80a9-02-customer_trend_023`, `ev_call-2e442f80a9-02-customer_trend_024`, `ev_call-2e442f80a9-02-customer_trend_025`, `ev_call-2e442f80a9-02-customer_trend_026`

3. **Basket behavior** — Partial
   Did basket size, cadence, or store behavior change?
   Attempts: 1 · Retries: 0 · Recorded latency: 10.5945 ms · Evidence: `ev_call-2e442f80a9-03-basket_behavior_001`, `ev_call-2e442f80a9-03-basket_behavior_002`, `ev_call-2e442f80a9-03-basket_behavior_003`, `ev_call-2e442f80a9-03-basket_behavior_004`, `ev_call-2e442f80a9-03-basket_behavior_005`, `ev_call-2e442f80a9-03-basket_behavior_006`, `ev_call-2e442f80a9-03-basket_behavior_007`, `ev_call-2e442f80a9-03-basket_behavior_008`, `ev_call-2e442f80a9-03-basket_behavior_009`, `ev_call-2e442f80a9-03-basket_behavior_010`, `ev_call-2e442f80a9-03-basket_behavior_011`, `ev_call-2e442f80a9-03-basket_behavior_012`, `ev_call-2e442f80a9-03-basket_behavior_013`, `ev_call-2e442f80a9-03-basket_behavior_014`

4. **Behavioral peer comparison** — Ok
   How unusual is the decline among behaviorally similar households?
   Attempts: 1 · Retries: 0 · Recorded latency: 44.3524 ms · Evidence: `ev_call-2e442f80a9-04-peer_comparison_001`, `ev_call-2e442f80a9-04-peer_comparison_002`, `ev_call-2e442f80a9-04-peer_comparison_003`, `ev_call-2e442f80a9-04-peer_comparison_004`, `ev_call-2e442f80a9-04-peer_comparison_005`, `ev_call-2e442f80a9-04-peer_comparison_006`, `ev_call-2e442f80a9-04-peer_comparison_007`, `ev_call-2e442f80a9-04-peer_comparison_008`, `ev_call-2e442f80a9-04-peer_comparison_009`, `ev_call-2e442f80a9-04-peer_comparison_010`, `ev_call-2e442f80a9-04-peer_comparison_011`, `ev_call-2e442f80a9-04-peer_comparison_012`, `ev_call-2e442f80a9-04-peer_comparison_013`, `ev_call-2e442f80a9-04-peer_comparison_014`, `ev_call-2e442f80a9-04-peer_comparison_015`, `ev_call-2e442f80a9-04-peer_comparison_016`, `ev_call-2e442f80a9-04-peer_comparison_017`



## Likely drivers



- **Associational claim:** Reduced recorded visit cadence is a plausible contributor to the observed engagement decline.
  Grounded by `ev_call-2e442f80a9-02-customer_trend_002`, `ev_call-2e442f80a9-03-basket_behavior_001`.
  Counterevidence: `ev_call-2e442f80a9-04-peer_comparison_017`.
  Claim limitations: The observational evidence supports an association, not a causal explanation of the household's behavior.




## Supporting evidence



### `ev_call-2e442f80a9-02-customer_trend_002` — Distinct Trips

- Source: `customer_trend` / `call-2e442f80a9-02-customer_trend`
- Source status: Partial
- Baseline: 7 Count
- Recent: 0 Count
- Change: -7 Count


### `ev_call-2e442f80a9-03-basket_behavior_001` — Basket Count

- Source: `basket_behavior` / `call-2e442f80a9-03-basket_behavior`
- Source status: Partial
- Baseline: 7 Count
- Recent: 0 Count
- Change: -7 Count




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



- `ev_call-2e442f80a9-04-peer_comparison_017` — **Context Classification**; source status Ok. Limitations: Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group..



## Next Best Action


**VISIT\_FREQUENCY\_REACTIVATION** — Recommend a human-reviewed reactivation test focused on restoring shopping cadence when visit-frequency evidence, rather than basket value alone, supports the decline.

The cited records satisfy the selected catalog action's machine-checkable evidence policy; the recommendation remains a human-reviewed test.

Resolved confidence: **Medium** (deterministic cap applied).

- Confidence adjustment: Population and peer context is mixed, so a uniquely customer-specific interpretation cannot receive high confidence. Maximum confidence: **Medium**. Context: **Mixed**. Evidence: `ev_call-2e442f80a9-04-peer_comparison_017`.



## Measurement plan


- **Framing:** This is a hypothesis to test, not a promised retention effect.
- **Success metric:** Change in distinct shopping trips per week relative to an eligible holdout over the evaluation window.
- **Suggested experiment:** Randomize eligible households between a reviewer-approved cadence treatment and no treatment, then compare distinct trips per week.


## Limitations



- Source week 53 contains fewer calendar days than an ordinary week.

- Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable.

- Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.

- No recent transactions were observed; per-trip statistics for that period are unavailable.

- Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- No recent baskets were observed; basket structure and cadence for that period are unavailable.

- Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.

- Customer intent and activity outside the recorded retailer data are not observed.



## Failures and partial-result warnings



- **Coupon Campaign History — Partial.** Attempts: 1; retries: 0; recorded latency: 28.1892 ms. Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable.

- **Customer Trend — Partial.** Attempts: 1; retries: 0; recorded latency: 54.9123 ms. Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.; No recent transactions were observed; per-trip statistics for that period are unavailable.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- **Basket Behavior — Partial.** Attempts: 1; retries: 0; recorded latency: 10.5945 ms. Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.; No recent baskets were observed; basket structure and cadence for that period are unavailable.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.




## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Maximum claim | Limitations |
|---|---|---|---|---|---|---|
| `ev_call-2e442f80a9-01-coupon_campaign_history_001` | Context | `coupon_campaign_history` | Partial | Campaign Participation Count | Associational | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-2e442f80a9-01-coupon_campaign_history_002` | Context | `coupon_campaign_history` | Partial | Coupon Redemption Count | Associational | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-2e442f80a9-01-coupon_campaign_history_003` | Context | `coupon_campaign_history` | Partial | Transaction Coupon Baskets | Associational | None recorded |
| `ev_call-2e442f80a9-01-coupon_campaign_history_004` | Context | `coupon_campaign_history` | Partial | Recorded Coupon Discount | Associational | None recorded |
| `ev_call-2e442f80a9-01-coupon_campaign_history_005` | Context | `coupon_campaign_history` | Partial | Campaign Participation | Associational | None recorded |
| `ev_call-2e442f80a9-01-coupon_campaign_history_006` | Context | `coupon_campaign_history` | Partial | Known Delivered Campaign Coupon Count | Associational | None recorded |
| `ev_call-2e442f80a9-01-coupon_campaign_history_007` | Context | `coupon_campaign_history` | Partial | Campaign Participation | Associational | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-2e442f80a9-02-customer_trend_001` | Context | `customer_trend` | Partial | Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_002` | Supporting | `customer_trend` | Partial | Distinct Trips | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_003` | Context | `customer_trend` | Partial | Active Weeks | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_004` | Context | `customer_trend` | Partial | Average Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_005` | Context | `customer_trend` | Partial | Median Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_006` | Context | `customer_trend` | Partial | Recorded Quantity | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-2e442f80a9-02-customer_trend_007` | Context | `customer_trend` | Partial | Distinct Products | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_008` | Context | `customer_trend` | Partial | Recency Weeks | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_009` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_010` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_011` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_012` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_013` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_014` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_015` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_016` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_017` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_018` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_019` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_020` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_021` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_022` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_023` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_024` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_025` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-02-customer_trend_026` | Context | `customer_trend` | Partial | Full Window Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_001` | Supporting | `basket_behavior` | Partial | Basket Count | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_002` | Context | `basket_behavior` | Partial | Active Weeks | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_003` | Context | `basket_behavior` | Partial | Baskets Per Calendar Week | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_004` | Context | `basket_behavior` | Partial | Mean Basket Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_005` | Context | `basket_behavior` | Partial | Median Basket Retailer Sales Value | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_006` | Context | `basket_behavior` | Partial | Mean Recorded Quantity Per Basket | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-2e442f80a9-03-basket_behavior_007` | Context | `basket_behavior` | Partial | Median Recorded Quantity Per Basket | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-2e442f80a9-03-basket_behavior_008` | Context | `basket_behavior` | Partial | Mean Distinct Products Per Basket | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_009` | Context | `basket_behavior` | Partial | Mean Distinct Categories Per Basket | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_010` | Context | `basket_behavior` | Partial | Mean Basket Interval Days | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_011` | Context | `basket_behavior` | Partial | Median Basket Interval Days | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_012` | Context | `basket_behavior` | Partial | Primary Store Share | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_013` | Context | `basket_behavior` | Partial | Stores Visited | Associational | None recorded |
| `ev_call-2e442f80a9-03-basket_behavior_014` | Context | `basket_behavior` | Partial | Consecutive Store Switch Rate | Associational | None recorded |
| `ev_call-2e442f80a9-04-peer_comparison_001` | Context | `peer_comparison` | Ok | Target Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_002` | Context | `peer_comparison` | Ok | Population Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_003` | Context | `peer_comparison` | Ok | Peer Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_004` | Context | `peer_comparison` | Ok | Population Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_005` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_006` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_007` | Context | `peer_comparison` | Ok | Target Population Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_008` | Context | `peer_comparison` | Ok | Population Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_009` | Context | `peer_comparison` | Ok | Target Minus Population Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_010` | Context | `peer_comparison` | Ok | Peer Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_011` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_012` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_013` | Context | `peer_comparison` | Ok | Target Peer Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_014` | Context | `peer_comparison` | Ok | Peer Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_015` | Context | `peer_comparison` | Ok | Target Minus Peer Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_016` | Context | `peer_comparison` | Ok | Target Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-2e442f80a9-04-peer_comparison_017` | Counterevidence | `peer_comparison` | Ok | Context Classification: mixed | Associational | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
