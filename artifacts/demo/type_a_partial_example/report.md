# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `101`
**Run:** `db94dd49-c6a1-5bb1-9ef1-2447ecc8bab0`
**Status:** Completed
**Data:** Synthetic · `whyback/synthetic-fixture` @ `whyback-synthetic-fixture-v1`
**Execution:** Scripted Control · backend `scripted` · model `scripted/whyback-v1`
**Generated:** `2026-08-25T01:35:02.981244+00:00` · timing Actual Utc And Monotonic

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

## Investigation path



1. **Coupon campaign history** — Partial
   What campaign and coupon information is known or unavailable?
   Attempts: 1 · Retries: 0 · Recorded latency: 7.35708 ms · Evidence: `ev_call-db94dd49c6-01-coupon_campaign_history_001`, `ev_call-db94dd49c6-01-coupon_campaign_history_002`, `ev_call-db94dd49c6-01-coupon_campaign_history_003`, `ev_call-db94dd49c6-01-coupon_campaign_history_004`, `ev_call-db94dd49c6-01-coupon_campaign_history_005`

2. **Customer trend** — Ok
   Is the decline primarily frequency or value related?
   Attempts: 1 · Retries: 0 · Recorded latency: 8.56846 ms · Evidence: `ev_call-db94dd49c6-02-customer_trend_001`, `ev_call-db94dd49c6-02-customer_trend_002`, `ev_call-db94dd49c6-02-customer_trend_003`, `ev_call-db94dd49c6-02-customer_trend_004`, `ev_call-db94dd49c6-02-customer_trend_005`, `ev_call-db94dd49c6-02-customer_trend_006`, `ev_call-db94dd49c6-02-customer_trend_007`, `ev_call-db94dd49c6-02-customer_trend_008`, `ev_call-db94dd49c6-02-customer_trend_009`, `ev_call-db94dd49c6-02-customer_trend_010`, `ev_call-db94dd49c6-02-customer_trend_011`, `ev_call-db94dd49c6-02-customer_trend_012`, `ev_call-db94dd49c6-02-customer_trend_013`, `ev_call-db94dd49c6-02-customer_trend_014`, `ev_call-db94dd49c6-02-customer_trend_015`, `ev_call-db94dd49c6-02-customer_trend_016`, `ev_call-db94dd49c6-02-customer_trend_017`, `ev_call-db94dd49c6-02-customer_trend_018`, `ev_call-db94dd49c6-02-customer_trend_019`, `ev_call-db94dd49c6-02-customer_trend_020`, `ev_call-db94dd49c6-02-customer_trend_021`, `ev_call-db94dd49c6-02-customer_trend_022`, `ev_call-db94dd49c6-02-customer_trend_023`, `ev_call-db94dd49c6-02-customer_trend_024`, `ev_call-db94dd49c6-02-customer_trend_025`, `ev_call-db94dd49c6-02-customer_trend_026`

3. **Basket behavior** — Ok
   Did basket size, cadence, or store behavior change?
   Attempts: 1 · Retries: 0 · Recorded latency: 2.22658 ms · Evidence: `ev_call-db94dd49c6-03-basket_behavior_001`, `ev_call-db94dd49c6-03-basket_behavior_002`, `ev_call-db94dd49c6-03-basket_behavior_003`, `ev_call-db94dd49c6-03-basket_behavior_004`, `ev_call-db94dd49c6-03-basket_behavior_005`, `ev_call-db94dd49c6-03-basket_behavior_006`, `ev_call-db94dd49c6-03-basket_behavior_007`, `ev_call-db94dd49c6-03-basket_behavior_008`, `ev_call-db94dd49c6-03-basket_behavior_009`, `ev_call-db94dd49c6-03-basket_behavior_010`, `ev_call-db94dd49c6-03-basket_behavior_011`, `ev_call-db94dd49c6-03-basket_behavior_012`, `ev_call-db94dd49c6-03-basket_behavior_013`, `ev_call-db94dd49c6-03-basket_behavior_014`, `ev_call-db94dd49c6-03-basket_behavior_015`, `ev_call-db94dd49c6-03-basket_behavior_016`



## Likely drivers



- Reduced recorded visit cadence is a plausible contributor to the observed engagement decline.
  Grounded by `ev_call-db94dd49c6-02-customer_trend_002`, `ev_call-db94dd49c6-03-basket_behavior_001`.



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




## Counterevidence and alternative explanations



- `ev_call-db94dd49c6-01-coupon_campaign_history_001` — **Campaign Participation Count**; source status Partial. Value 1. Limitations: Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable..




- Alternative: Recorded evidence does not distinguish the observed signal from unobserved activity outside this retailer.



## Next Best Action


**VISIT\_FREQUENCY\_REACTIVATION** — Recommend a human-reviewed reactivation test focused on restoring shopping cadence when visit-frequency evidence, rather than basket value alone, supports the decline.

The cited records satisfy the selected catalog action's machine-checkable evidence policy; the recommendation remains a human-reviewed test.

Resolved confidence: **Medium** (deterministic cap applied).


## Measurement plan


- **Success metric:** Change in distinct shopping trips per week relative to an eligible holdout over the evaluation window.
- **Suggested experiment:** Randomize eligible households between a reviewer-approved cadence treatment and no treatment, then compare distinct trips per week.


## Limitations



- Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable.

- Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.

- Customer intent and activity outside the recorded retailer data are not observed.



## Failures and partial-result warnings



- **Coupon Campaign History — Partial.** Attempts: 1; retries: 0; recorded latency: 7.35708 ms. Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable.




## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Limitations |
|---|---|---|---|---|---|
| `ev_call-db94dd49c6-01-coupon_campaign_history_001` | Counterevidence | `coupon_campaign_history` | Partial | Campaign Participation Count | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-db94dd49c6-01-coupon_campaign_history_002` | Context | `coupon_campaign_history` | Partial | Coupon Redemption Count | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-db94dd49c6-01-coupon_campaign_history_003` | Context | `coupon_campaign_history` | Partial | Transaction Coupon Baskets | None recorded |
| `ev_call-db94dd49c6-01-coupon_campaign_history_004` | Context | `coupon_campaign_history` | Partial | Recorded Coupon Discount | None recorded |
| `ev_call-db94dd49c6-01-coupon_campaign_history_005` | Context | `coupon_campaign_history` | Partial | Campaign Participation | Type A participants received 16 coupons selected from a larger pool, but the household-specific delivered coupon identities are unavailable. |
| `ev_call-db94dd49c6-02-customer_trend_001` | Context | `customer_trend` | Ok | Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_002` | Supporting | `customer_trend` | Ok | Distinct Trips | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_003` | Context | `customer_trend` | Ok | Active Weeks | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_004` | Context | `customer_trend` | Ok | Average Retailer Sales Value Per Trip | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_005` | Context | `customer_trend` | Ok | Median Retailer Sales Value Per Trip | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_006` | Context | `customer_trend` | Ok | Recorded Quantity | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-db94dd49c6-02-customer_trend_007` | Context | `customer_trend` | Ok | Distinct Products | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_008` | Context | `customer_trend` | Ok | Recency Weeks | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_009` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value Slope | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_010` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_011` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_012` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_013` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_014` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_015` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_016` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_017` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_018` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_019` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_020` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_021` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_022` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_023` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_024` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_025` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-02-customer_trend_026` | Context | `customer_trend` | Ok | Full Window Weekly Retailer Sales Value Slope | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_001` | Supporting | `basket_behavior` | Ok | Basket Count | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_002` | Context | `basket_behavior` | Ok | Active Weeks | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_003` | Context | `basket_behavior` | Ok | Baskets Per Calendar Week | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_004` | Context | `basket_behavior` | Ok | Mean Basket Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_005` | Context | `basket_behavior` | Ok | Median Basket Retailer Sales Value | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_006` | Context | `basket_behavior` | Ok | Mean Recorded Quantity Per Basket | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-db94dd49c6-03-basket_behavior_007` | Context | `basket_behavior` | Ok | Median Recorded Quantity Per Basket | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-db94dd49c6-03-basket_behavior_008` | Context | `basket_behavior` | Ok | Mean Distinct Products Per Basket | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_009` | Context | `basket_behavior` | Ok | Mean Distinct Categories Per Basket | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_010` | Context | `basket_behavior` | Ok | Mean Basket Interval Days | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_011` | Context | `basket_behavior` | Ok | Median Basket Interval Days | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_012` | Context | `basket_behavior` | Ok | Primary Store Share | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_013` | Context | `basket_behavior` | Ok | Stores Visited | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_014` | Context | `basket_behavior` | Ok | Consecutive Store Switch Rate | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_015` | Context | `basket_behavior` | Ok | Primary Store Changed | None recorded |
| `ev_call-db94dd49c6-03-basket_behavior_016` | Context | `basket_behavior` | Ok | Recent Baskets At New Store Share | None recorded |
