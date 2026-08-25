# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `101`
**Run:** `716a66bd-6ce6-4451-98aa-12f1f67a9937`
**Status:** Failed
**Data:** Synthetic · `whyback/synthetic-fixture` @ `whyback-synthetic-fixture-v1`
**Execution:** Live Gemini · backend `gemini` · model `gemini-3.7-flash`
**Generated:** `2026-08-25T04:39:38.940238+00:00` · timing Actual Utc And Monotonic

## Decline summary

The deterministic detector compared weeks **1–8** with weeks **9–16**.

Detector evidence: `detector_716a66bd-6ce6-4451-98aa-12f1f67a9937` (run- and household-owned).

| Measure | Baseline | Recent | Recorded drop |
|---|---:|---:|---:|
| Retailer sales value | $160.00 | $12.00 | 92.5% |
| Distinct baskets | 16 | 2 | 87.5% |
| Active weeks | 8 | 2 | 75.0% |

- **Decline score:** 0.875 (weighted heuristic, not a probability)
- **Eligible:** yes
- **Flagged:** yes

## Investigation path



1. **Customer trend** — Ok
   Investigate the next permitted evidence source.
   Attempts: 1 · Retries: 0 · Recorded latency: 24.6931 ms · Evidence: `ev_call-716a66bd6c-01-customer_trend_001`, `ev_call-716a66bd6c-01-customer_trend_002`, `ev_call-716a66bd6c-01-customer_trend_003`, `ev_call-716a66bd6c-01-customer_trend_004`, `ev_call-716a66bd6c-01-customer_trend_005`, `ev_call-716a66bd6c-01-customer_trend_006`, `ev_call-716a66bd6c-01-customer_trend_007`, `ev_call-716a66bd6c-01-customer_trend_008`, `ev_call-716a66bd6c-01-customer_trend_009`, `ev_call-716a66bd6c-01-customer_trend_010`, `ev_call-716a66bd6c-01-customer_trend_011`, `ev_call-716a66bd6c-01-customer_trend_012`, `ev_call-716a66bd6c-01-customer_trend_013`, `ev_call-716a66bd6c-01-customer_trend_014`, `ev_call-716a66bd6c-01-customer_trend_015`, `ev_call-716a66bd6c-01-customer_trend_016`, `ev_call-716a66bd6c-01-customer_trend_017`, `ev_call-716a66bd6c-01-customer_trend_018`, `ev_call-716a66bd6c-01-customer_trend_019`, `ev_call-716a66bd6c-01-customer_trend_020`, `ev_call-716a66bd6c-01-customer_trend_021`, `ev_call-716a66bd6c-01-customer_trend_022`, `ev_call-716a66bd6c-01-customer_trend_023`, `ev_call-716a66bd6c-01-customer_trend_024`, `ev_call-716a66bd6c-01-customer_trend_025`, `ev_call-716a66bd6c-01-customer_trend_026`

2. **Category decomposition** — Ok
   Which product categories or departments account for the lost retailer sales value?
   Attempts: 1 · Retries: 0 · Recorded latency: 11.6996 ms · Evidence: `ev_call-716a66bd6c-02-category_decomposition_001`, `ev_call-716a66bd6c-02-category_decomposition_002`, `ev_call-716a66bd6c-02-category_decomposition_003`, `ev_call-716a66bd6c-02-category_decomposition_004`, `ev_call-716a66bd6c-02-category_decomposition_005`, `ev_call-716a66bd6c-02-category_decomposition_006`, `ev_call-716a66bd6c-02-category_decomposition_007`, `ev_call-716a66bd6c-02-category_decomposition_008`, `ev_call-716a66bd6c-02-category_decomposition_009`, `ev_call-716a66bd6c-02-category_decomposition_010`, `ev_call-716a66bd6c-02-category_decomposition_011`, `ev_call-716a66bd6c-02-category_decomposition_012`, `ev_call-716a66bd6c-02-category_decomposition_013`, `ev_call-716a66bd6c-02-category_decomposition_014`, `ev_call-716a66bd6c-02-category_decomposition_015`, `ev_call-716a66bd6c-02-category_decomposition_016`

3. **Basket behavior** — Ok
   Did basket size, basket value, or visit cadence drive the household sales decline?
   Attempts: 1 · Retries: 0 · Recorded latency: 9.21437 ms · Evidence: `ev_call-716a66bd6c-03-basket_behavior_001`, `ev_call-716a66bd6c-03-basket_behavior_002`, `ev_call-716a66bd6c-03-basket_behavior_003`, `ev_call-716a66bd6c-03-basket_behavior_004`, `ev_call-716a66bd6c-03-basket_behavior_005`, `ev_call-716a66bd6c-03-basket_behavior_006`, `ev_call-716a66bd6c-03-basket_behavior_007`, `ev_call-716a66bd6c-03-basket_behavior_008`, `ev_call-716a66bd6c-03-basket_behavior_009`, `ev_call-716a66bd6c-03-basket_behavior_010`, `ev_call-716a66bd6c-03-basket_behavior_011`, `ev_call-716a66bd6c-03-basket_behavior_012`, `ev_call-716a66bd6c-03-basket_behavior_013`, `ev_call-716a66bd6c-03-basket_behavior_014`, `ev_call-716a66bd6c-03-basket_behavior_015`, `ev_call-716a66bd6c-03-basket_behavior_016`



## Likely drivers


No likely driver passed deterministic verification.


## Supporting evidence


No supporting evidence was accepted for a verified conclusion.


## Counterevidence and alternative explanations


- No evidence record was designated as counterevidence.


- No verified alternative explanation was recorded.


## Next Best Action


No Next Best Action passed deterministic verification. No customer action should be taken from this report.


## Measurement plan


No measurement plan is available because no action passed verification.


## Limitations



- Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.

- Gemini Interactions request failed



## Failures and partial-result warnings


- No failed, partial, or retried analytical result was recorded.



- Verification issue: Gemini Interactions request failed



## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Limitations |
|---|---|---|---|---|---|
| `ev_call-716a66bd6c-01-customer_trend_001` | Context | `customer_trend` | Ok | Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_002` | Context | `customer_trend` | Ok | Distinct Trips | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_003` | Context | `customer_trend` | Ok | Active Weeks | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_004` | Context | `customer_trend` | Ok | Average Retailer Sales Value Per Trip | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_005` | Context | `customer_trend` | Ok | Median Retailer Sales Value Per Trip | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_006` | Context | `customer_trend` | Ok | Recorded Quantity | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-716a66bd6c-01-customer_trend_007` | Context | `customer_trend` | Ok | Distinct Products | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_008` | Context | `customer_trend` | Ok | Recency Weeks | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_009` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value Slope | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_010` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_011` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_012` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_013` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_014` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_015` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_016` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_017` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_018` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_019` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_020` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_021` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_022` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_023` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_024` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_025` | Context | `customer_trend` | Ok | Weekly Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-01-customer_trend_026` | Context | `customer_trend` | Ok | Full Window Weekly Retailer Sales Value Slope | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_001` | Context | `category_decomposition` | Ok | Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_002` | Context | `category_decomposition` | Ok | Product Mapping Line Item Coverage | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_003` | Context | `category_decomposition` | Ok | Product Mapping Distinct Product Coverage | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_004` | Context | `category_decomposition` | Ok | Unknown Group Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_005` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_006` | Context | `category_decomposition` | Ok | Category Percentage Change | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_007` | Context | `category_decomposition` | Ok | Category Share Shift | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_008` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_009` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_010` | Context | `category_decomposition` | Ok | Category Percentage Change | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_011` | Context | `category_decomposition` | Ok | Category Share Shift | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_012` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_013` | Context | `category_decomposition` | Ok | Category Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_014` | Context | `category_decomposition` | Ok | Category Percentage Change | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_015` | Context | `category_decomposition` | Ok | Category Share Shift | None recorded |
| `ev_call-716a66bd6c-02-category_decomposition_016` | Context | `category_decomposition` | Ok | Contribution To Lost Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_001` | Context | `basket_behavior` | Ok | Basket Count | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_002` | Context | `basket_behavior` | Ok | Active Weeks | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_003` | Context | `basket_behavior` | Ok | Baskets Per Calendar Week | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_004` | Context | `basket_behavior` | Ok | Mean Basket Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_005` | Context | `basket_behavior` | Ok | Median Basket Retailer Sales Value | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_006` | Context | `basket_behavior` | Ok | Mean Recorded Quantity Per Basket | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-716a66bd6c-03-basket_behavior_007` | Context | `basket_behavior` | Ok | Median Recorded Quantity Per Basket | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-716a66bd6c-03-basket_behavior_008` | Context | `basket_behavior` | Ok | Mean Distinct Products Per Basket | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_009` | Context | `basket_behavior` | Ok | Mean Distinct Categories Per Basket | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_010` | Context | `basket_behavior` | Ok | Mean Basket Interval Days | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_011` | Context | `basket_behavior` | Ok | Median Basket Interval Days | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_012` | Context | `basket_behavior` | Ok | Primary Store Share | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_013` | Context | `basket_behavior` | Ok | Stores Visited | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_014` | Context | `basket_behavior` | Ok | Consecutive Store Switch Rate | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_015` | Context | `basket_behavior` | Ok | Primary Store Changed | None recorded |
| `ev_call-716a66bd6c-03-basket_behavior_016` | Context | `basket_behavior` | Ok | Recent Baskets At New Store Share | None recorded |
