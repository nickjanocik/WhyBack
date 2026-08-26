# WhyBack investigation report

*Find the why. Choose the way back.*

**Investigator:** WhyBack Investigator
**Household:** `5`
**Run:** `6c421323-bc2e-450b-8709-87b5bdf5cf9a`
**Status:** Insufficient Evidence
**Data:** Official Complete Journey · `bradleyboehmke/completejourney` @ `5b5d06192b9856edd04e4d405787af2f2e4a1fef`
**Execution:** Live Gemini · backend `gemini` · model `gemini-3.7-flash`
**Generated:** `2026-08-26T16:37:05.519262+00:00` · timing Actual Utc And Monotonic

## Decline summary

The deterministic detector compared weeks **38–45** with weeks **46–53**.

Detector evidence: `detector_6c421323-bc2e-450b-8709-87b5bdf5cf9a` (run- and household-owned).

| Measure | Baseline | Recent | Recorded drop |
|---|---:|---:|---:|
| Retailer sales value | $98.37 | $0.00 | 100.0% |
| Distinct baskets | 6 | 0 | 100.0% |
| Active weeks | 4 | 0 | 100.0% |

- **Decline score:** 1 (weighted heuristic, not a probability)
- **Eligible:** yes
- **Flagged:** yes

## Population and comparison context

**Classification:** Customer Specific. Signed change is `(recent - baseline) / baseline`; more negative means a more severe decline. Classification evidence: `ev_call-6c421323bc-04-peer_comparison_017`.


- **Target retailer-sales change:** -100.0%


| Comparison | Households | Median change | Interquartile range | Target percentile | Share declining | Target minus median |
|---|---:|---:|---:|---:|---:|---:|
| Eligible Population | 1312 | -3.6% | -33.4% to 29.8% | 1.21951 | 53.4% | -96.4% |
| Behavioral Peers | 50 | 31.5% | -58.3% to 163.9% | 8 | 42.0% | -131.5% |


- **Eligible-population construction:** The target is compared with the household-level distribution of signed retailer-sales changes among all other households meeting the declared baseline eligibility policy. The target is excluded, and lower change means a more severe decline.
- **Behavioral-peer construction:** Eligible target-excluded households are robust-scaled on baseline log1p retailer sales value, trip count, median basket value, active weeks, and category concentration. Scaling is fit on comparison households only; nearest Euclidean peers are selected with household-ID tie breaking.
- The target household is excluded from both comparison distributions: yes.


### Major-category contemporaneous context

| Department / category | Target change | Comparison median | Share declining | Target minus median | Households | Classification |
|---|---:|---:|---:|---:|---:|---|
| DRUG GM / PERSONAL CARE APPLIANCES | -100.0% | Unavailable | Unavailable | Unavailable | 9 | Insufficient Context |
| GROCERY / BEERS/ALES | -100.0% | -46.5% | 64.2% | -53.5% | 405 | Mixed |
| COSMETICS / MAKEUP AND TREATMENT | -100.0% | -100.0% | 74.5% | 0.0% | 204 | Broad Context |
| DRUG GM / SOAP - LIQUID &amp; BAR | -100.0% | -100.0% | 77.9% | 0.0% | 335 | Broad Context |
| DRUG GM / COLD AND FLU | -100.0% | -100.0% | 73.8% | 0.0% | 321 | Broad Context |
| DRUG GM / FAMILY PLANNING | -100.0% | -100.0% | 84.2% | 0.0% | 38 | Broad Context |
| DRUG GM / HAND/BODY/FACIAL PRODUCTS | -100.0% | -100.0% | 80.6% | 0.0% | 180 | Broad Context |
| DRUG GM / HAIR CARE PRODUCTS | -100.0% | -81.9% | 73.6% | -18.1% | 386 | Mixed |




- Context limitation: Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.

- Context limitation: Category DRUG GM / PERSONAL CARE APPLIANCES has 9 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable.

- Context limitation: Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Context limitation: Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.



## Investigation path



1. **Customer trend** — Partial
   Investigate the next permitted evidence source.
   Attempts: 1 · Retries: 0 · Recorded latency: 66.1555 ms · Evidence: `ev_call-6c421323bc-01-customer_trend_001`, `ev_call-6c421323bc-01-customer_trend_002`, `ev_call-6c421323bc-01-customer_trend_003`, `ev_call-6c421323bc-01-customer_trend_004`, `ev_call-6c421323bc-01-customer_trend_005`, `ev_call-6c421323bc-01-customer_trend_006`, `ev_call-6c421323bc-01-customer_trend_007`, `ev_call-6c421323bc-01-customer_trend_008`, `ev_call-6c421323bc-01-customer_trend_009`, `ev_call-6c421323bc-01-customer_trend_010`, `ev_call-6c421323bc-01-customer_trend_011`, `ev_call-6c421323bc-01-customer_trend_012`, `ev_call-6c421323bc-01-customer_trend_013`, `ev_call-6c421323bc-01-customer_trend_014`, `ev_call-6c421323bc-01-customer_trend_015`, `ev_call-6c421323bc-01-customer_trend_016`, `ev_call-6c421323bc-01-customer_trend_017`, `ev_call-6c421323bc-01-customer_trend_018`, `ev_call-6c421323bc-01-customer_trend_019`, `ev_call-6c421323bc-01-customer_trend_020`, `ev_call-6c421323bc-01-customer_trend_021`, `ev_call-6c421323bc-01-customer_trend_022`, `ev_call-6c421323bc-01-customer_trend_023`, `ev_call-6c421323bc-01-customer_trend_024`, `ev_call-6c421323bc-01-customer_trend_025`, `ev_call-6c421323bc-01-customer_trend_026`

2. **Category decomposition** — Partial
   Investigate the next permitted evidence source.
   Attempts: 1 · Retries: 0 · Recorded latency: 108.514 ms · Evidence: `ev_call-6c421323bc-02-category_decomposition_001`, `ev_call-6c421323bc-02-category_decomposition_002`, `ev_call-6c421323bc-02-category_decomposition_003`, `ev_call-6c421323bc-02-category_decomposition_004`, `ev_call-6c421323bc-02-category_decomposition_005`, `ev_call-6c421323bc-02-category_decomposition_006`, `ev_call-6c421323bc-02-category_decomposition_007`, `ev_call-6c421323bc-02-category_decomposition_008`, `ev_call-6c421323bc-02-category_decomposition_009`, `ev_call-6c421323bc-02-category_decomposition_010`, `ev_call-6c421323bc-02-category_decomposition_011`, `ev_call-6c421323bc-02-category_decomposition_012`, `ev_call-6c421323bc-02-category_decomposition_013`, `ev_call-6c421323bc-02-category_decomposition_014`, `ev_call-6c421323bc-02-category_decomposition_015`, `ev_call-6c421323bc-02-category_decomposition_016`, `ev_call-6c421323bc-02-category_decomposition_017`, `ev_call-6c421323bc-02-category_decomposition_018`, `ev_call-6c421323bc-02-category_decomposition_019`, `ev_call-6c421323bc-02-category_decomposition_020`, `ev_call-6c421323bc-02-category_decomposition_021`, `ev_call-6c421323bc-02-category_decomposition_022`, `ev_call-6c421323bc-02-category_decomposition_023`, `ev_call-6c421323bc-02-category_decomposition_024`, `ev_call-6c421323bc-02-category_decomposition_025`, `ev_call-6c421323bc-02-category_decomposition_026`, `ev_call-6c421323bc-02-category_decomposition_027`, `ev_call-6c421323bc-02-category_decomposition_028`, `ev_call-6c421323bc-02-category_decomposition_029`, `ev_call-6c421323bc-02-category_decomposition_030`, `ev_call-6c421323bc-02-category_decomposition_031`, `ev_call-6c421323bc-02-category_decomposition_032`, `ev_call-6c421323bc-02-category_decomposition_033`, `ev_call-6c421323bc-02-category_decomposition_034`, `ev_call-6c421323bc-02-category_decomposition_035`, `ev_call-6c421323bc-02-category_decomposition_036`, `ev_call-6c421323bc-02-category_decomposition_037`, `ev_call-6c421323bc-02-category_decomposition_038`, `ev_call-6c421323bc-02-category_decomposition_039`, `ev_call-6c421323bc-02-category_decomposition_040`, `ev_call-6c421323bc-02-category_decomposition_041`, `ev_call-6c421323bc-02-category_decomposition_042`, `ev_call-6c421323bc-02-category_decomposition_043`, `ev_call-6c421323bc-02-category_decomposition_044`, `ev_call-6c421323bc-02-category_decomposition_045`, `ev_call-6c421323bc-02-category_decomposition_046`, `ev_call-6c421323bc-02-category_decomposition_047`, `ev_call-6c421323bc-02-category_decomposition_048`, `ev_call-6c421323bc-02-category_decomposition_049`, `ev_call-6c421323bc-02-category_decomposition_050`, `ev_call-6c421323bc-02-category_decomposition_051`, `ev_call-6c421323bc-02-category_decomposition_052`, `ev_call-6c421323bc-02-category_decomposition_053`, `ev_call-6c421323bc-02-category_decomposition_054`, `ev_call-6c421323bc-02-category_decomposition_055`, `ev_call-6c421323bc-02-category_decomposition_056`, `ev_call-6c421323bc-02-category_decomposition_057`, `ev_call-6c421323bc-02-category_decomposition_058`, `ev_call-6c421323bc-02-category_decomposition_059`, `ev_call-6c421323bc-02-category_decomposition_060`, `ev_call-6c421323bc-02-category_decomposition_061`, `ev_call-6c421323bc-02-category_decomposition_062`, `ev_call-6c421323bc-02-category_decomposition_063`, `ev_call-6c421323bc-02-category_decomposition_064`, `ev_call-6c421323bc-02-category_decomposition_065`, `ev_call-6c421323bc-02-category_decomposition_066`, `ev_call-6c421323bc-02-category_decomposition_067`, `ev_call-6c421323bc-02-category_decomposition_068`, `ev_call-6c421323bc-02-category_decomposition_069`, `ev_call-6c421323bc-02-category_decomposition_070`, `ev_call-6c421323bc-02-category_decomposition_071`, `ev_call-6c421323bc-02-category_decomposition_072`, `ev_call-6c421323bc-02-category_decomposition_073`

3. **Basket behavior** — Partial
   Investigate the next permitted evidence source.
   Attempts: 1 · Retries: 0 · Recorded latency: 20.0968 ms · Evidence: `ev_call-6c421323bc-03-basket_behavior_001`, `ev_call-6c421323bc-03-basket_behavior_002`, `ev_call-6c421323bc-03-basket_behavior_003`, `ev_call-6c421323bc-03-basket_behavior_004`, `ev_call-6c421323bc-03-basket_behavior_005`, `ev_call-6c421323bc-03-basket_behavior_006`, `ev_call-6c421323bc-03-basket_behavior_007`, `ev_call-6c421323bc-03-basket_behavior_008`, `ev_call-6c421323bc-03-basket_behavior_009`, `ev_call-6c421323bc-03-basket_behavior_010`, `ev_call-6c421323bc-03-basket_behavior_011`, `ev_call-6c421323bc-03-basket_behavior_012`, `ev_call-6c421323bc-03-basket_behavior_013`, `ev_call-6c421323bc-03-basket_behavior_014`

4. **Behavioral peer comparison** — Ok
   How does the target household's decline compare to full population and behavioral peer benchmarks?
   Attempts: 1 · Retries: 0 · Recorded latency: 76.9929 ms · Evidence: `ev_call-6c421323bc-04-peer_comparison_001`, `ev_call-6c421323bc-04-peer_comparison_002`, `ev_call-6c421323bc-04-peer_comparison_003`, `ev_call-6c421323bc-04-peer_comparison_004`, `ev_call-6c421323bc-04-peer_comparison_005`, `ev_call-6c421323bc-04-peer_comparison_006`, `ev_call-6c421323bc-04-peer_comparison_007`, `ev_call-6c421323bc-04-peer_comparison_008`, `ev_call-6c421323bc-04-peer_comparison_009`, `ev_call-6c421323bc-04-peer_comparison_010`, `ev_call-6c421323bc-04-peer_comparison_011`, `ev_call-6c421323bc-04-peer_comparison_012`, `ev_call-6c421323bc-04-peer_comparison_013`, `ev_call-6c421323bc-04-peer_comparison_014`, `ev_call-6c421323bc-04-peer_comparison_015`, `ev_call-6c421323bc-04-peer_comparison_016`, `ev_call-6c421323bc-04-peer_comparison_017`



## Likely drivers


No likely driver passed deterministic verification.


## Supporting evidence


No supporting evidence was accepted for a verified conclusion.


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


**INSUFFICIENT\_EVIDENCE** — Recommend no customer action because valid evidence does not support another catalog choice; preserve failures and limitations for human review and request evidence recovery or later reassessment.

Available verified evidence does not support a customer action.

Resolved confidence: **Insufficient** (deterministic cap applied).



## Measurement plan


- **Framing:** This is a hypothesis to test, not a promised retention effect.
- **Success metric:** Share of insufficient-evidence cases that reviewers resolve through data recovery or a documented no-action decision.
- **Suggested experiment:** Audit a random holdout of closed cases to estimate false insufficiency and verify that no unsupported customer action was recommended.


## Limitations



- Source week 53 contains fewer calendar days than an ordinary week.

- Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.

- No recent transactions were observed; per-trip statistics for that period are unavailable.

- Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.

- No recent transactions were observed; changes from that period cannot be fully compared.

- Category DRUG GM / PERSONAL CARE APPLIANCES has 9 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable.

- No recent baskets were observed; basket structure and cadence for that period are unavailable.

- Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.

- Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group.

- Customer intent and activity outside the recorded retailer data are not observed.

- Final verification failed after the permitted repair attempt.

- unsupported\_causal\_claim: Final text contains unsupported causal or guaranteed-retention language.

- unsupported\_numerical\_claim: Free-form final text contains a raw numerical claim; reports must resolve numbers from evidence IDs.

- irrelevant\_counterevidence: Driver counterevidence is not a deterministic qualifier for VISIT\_FREQUENCY\_REACTIVATION: ev\_call-6c421323bc-02-category\_decomposition\_048

- irrelevant\_counterevidence: Driver counterevidence is not a deterministic qualifier for VISIT\_FREQUENCY\_REACTIVATION: ev\_call-6c421323bc-02-category\_decomposition\_053

- irrelevant\_counterevidence: Driver counterevidence is not a deterministic qualifier for VISIT\_FREQUENCY\_REACTIVATION: ev\_call-6c421323bc-02-category\_decomposition\_058



## Failures and partial-result warnings



- **Customer Trend — Partial.** Attempts: 1; retries: 0; recorded latency: 66.1555 ms. Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.; No recent transactions were observed; per-trip statistics for that period are unavailable.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.

- **Category Decomposition — Partial.** Attempts: 1; retries: 0; recorded latency: 108.514 ms. Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.; No recent transactions were observed; changes from that period cannot be fully compared.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.; Category DRUG GM / PERSONAL CARE APPLIANCES has 9 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable.

- **Basket Behavior — Partial.** Attempts: 1; retries: 0; recorded latency: 20.0968 ms. Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure.; No recent baskets were observed; basket structure and cadence for that period are unavailable.; Source weeks 1 and 53 are partial calendar weeks, so comparisons including either week may not be like-for-like.




- Verification issue: unsupported\_causal\_claim: Final text contains unsupported causal or guaranteed-retention language.

- Verification issue: unsupported\_numerical\_claim: Free-form final text contains a raw numerical claim; reports must resolve numbers from evidence IDs.

- Verification issue: irrelevant\_counterevidence: Driver counterevidence is not a deterministic qualifier for VISIT\_FREQUENCY\_REACTIVATION: ev\_call-6c421323bc-02-category\_decomposition\_048

- Verification issue: irrelevant\_counterevidence: Driver counterevidence is not a deterministic qualifier for VISIT\_FREQUENCY\_REACTIVATION: ev\_call-6c421323bc-02-category\_decomposition\_053

- Verification issue: irrelevant\_counterevidence: Driver counterevidence is not a deterministic qualifier for VISIT\_FREQUENCY\_REACTIVATION: ev\_call-6c421323bc-02-category\_decomposition\_058

- Verification issue: Final verification failed after the permitted repair attempt.



## Human-review requirement

**Human review is required before any action.** WhyBack recommends catalog-governed actions for review; it does not contact customers, mutate a CRM, or execute outreach.

## Evidence ledger


| Evidence ID | Role | Tool | Status | Metric | Maximum claim | Limitations |
|---|---|---|---|---|---|---|
| `ev_call-6c421323bc-01-customer_trend_001` | Context | `customer_trend` | Partial | Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_002` | Context | `customer_trend` | Partial | Distinct Trips | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_003` | Context | `customer_trend` | Partial | Active Weeks | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_004` | Context | `customer_trend` | Partial | Average Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_005` | Context | `customer_trend` | Partial | Median Retailer Sales Value Per Trip | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_006` | Context | `customer_trend` | Partial | Recorded Quantity | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-6c421323bc-01-customer_trend_007` | Context | `customer_trend` | Partial | Distinct Products | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_008` | Context | `customer_trend` | Partial | Recency Weeks | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_009` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_010` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_011` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_012` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_013` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_014` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_015` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_016` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_017` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_018` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_019` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_020` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_021` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_022` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_023` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_024` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_025` | Context | `customer_trend` | Partial | Weekly Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-01-customer_trend_026` | Context | `customer_trend` | Partial | Full Window Weekly Retailer Sales Value Slope | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_001` | Context | `category_decomposition` | Partial | Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_002` | Context | `category_decomposition` | Partial | Product Mapping Line Item Coverage | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_003` | Context | `category_decomposition` | Partial | Product Mapping Distinct Product Coverage | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_004` | Context | `category_decomposition` | Partial | Unknown Group Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_005` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_006` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_007` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_008` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_009` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_010` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_011` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_012` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_013` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_014` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_015` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_016` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_017` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_018` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_019` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_020` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_021` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_022` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_023` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_024` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_025` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_026` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_027` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_028` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_029` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_030` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_031` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_032` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_033` | Context | `category_decomposition` | Partial | Category Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_034` | Context | `category_decomposition` | Partial | Category Percentage Change | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_035` | Context | `category_decomposition` | Partial | Category Share Shift | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_036` | Context | `category_decomposition` | Partial | Contribution To Lost Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-02-category_decomposition_037` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.; Category DRUG GM / PERSONAL CARE APPLIANCES has 9 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable. |
| `ev_call-6c421323bc-02-category_decomposition_038` | Context | `category_decomposition` | Partial | Category Context Classification: insufficient\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation.; Category DRUG GM / PERSONAL CARE APPLIANCES has 9 eligible target-excluded households with meaningful baseline activity; policy requires at least 20, so category population distribution statistics are unavailable. |
| `ev_call-6c421323bc-02-category_decomposition_039` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_040` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_041` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_042` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_043` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_044` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_045` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_046` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_047` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_048` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_049` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_050` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_051` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_052` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_053` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_054` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_055` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_056` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_057` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_058` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_059` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_060` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_061` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_062` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_063` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_064` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_065` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_066` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_067` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_068` | Context | `category_decomposition` | Partial | Category Context Classification: broad\_context | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_069` | Context | `category_decomposition` | Partial | Category Population Household Count | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_070` | Context | `category_decomposition` | Partial | Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_071` | Context | `category_decomposition` | Partial | Category Population Declining Share | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_072` | Context | `category_decomposition` | Partial | Target Minus Category Population Median Change | Descriptive | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-02-category_decomposition_073` | Context | `category_decomposition` | Partial | Category Context Classification: mixed | Associational | Category comparison is a target-excluded household-level descriptive benchmark among eligible households with meaningful baseline category activity. Broad contemporaneous movement does not establish seasonality or causation. |
| `ev_call-6c421323bc-03-basket_behavior_001` | Context | `basket_behavior` | Partial | Basket Count | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_002` | Context | `basket_behavior` | Partial | Active Weeks | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_003` | Context | `basket_behavior` | Partial | Baskets Per Calendar Week | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_004` | Context | `basket_behavior` | Partial | Mean Basket Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_005` | Context | `basket_behavior` | Partial | Median Basket Retailer Sales Value | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_006` | Context | `basket_behavior` | Partial | Mean Recorded Quantity Per Basket | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-6c421323bc-03-basket_behavior_007` | Context | `basket_behavior` | Partial | Median Recorded Quantity Per Basket | Associational | Recorded quantity is not comparable across all departments because fuel uses a different scale; it is not used as the primary engagement measure. |
| `ev_call-6c421323bc-03-basket_behavior_008` | Context | `basket_behavior` | Partial | Mean Distinct Products Per Basket | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_009` | Context | `basket_behavior` | Partial | Mean Distinct Categories Per Basket | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_010` | Context | `basket_behavior` | Partial | Mean Basket Interval Days | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_011` | Context | `basket_behavior` | Partial | Median Basket Interval Days | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_012` | Context | `basket_behavior` | Partial | Primary Store Share | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_013` | Context | `basket_behavior` | Partial | Stores Visited | Associational | None recorded |
| `ev_call-6c421323bc-03-basket_behavior_014` | Context | `basket_behavior` | Partial | Consecutive Store Switch Rate | Associational | None recorded |
| `ev_call-6c421323bc-04-peer_comparison_001` | Context | `peer_comparison` | Ok | Target Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_002` | Context | `peer_comparison` | Ok | Population Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_003` | Context | `peer_comparison` | Ok | Peer Household Count | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_004` | Context | `peer_comparison` | Ok | Population Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_005` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_006` | Context | `peer_comparison` | Ok | Population Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_007` | Context | `peer_comparison` | Ok | Target Population Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_008` | Context | `peer_comparison` | Ok | Population Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_009` | Context | `peer_comparison` | Ok | Target Minus Population Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_010` | Context | `peer_comparison` | Ok | Peer Median Retailer Sales Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_011` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q25 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_012` | Context | `peer_comparison` | Ok | Peer Retailer Sales Change Q75 | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_013` | Context | `peer_comparison` | Ok | Target Peer Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_014` | Context | `peer_comparison` | Ok | Peer Declining Household Share | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_015` | Context | `peer_comparison` | Ok | Target Minus Peer Median Change | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_016` | Context | `peer_comparison` | Ok | Target Retailer Sales Change Percentile | Descriptive | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
| `ev_call-6c421323bc-04-peer_comparison_017` | Context | `peer_comparison` | Ok | Context Classification: customer\_specific | Associational | Eligible-population context is a household-level descriptive benchmark, excludes the target, and does not identify seasonality or a cause of change.; Peer similarity is descriptive, depends on the selected baseline features, excludes the target, and does not establish a causal control group. |
