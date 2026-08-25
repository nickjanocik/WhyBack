# Complete Journey data semantics

WhyBack uses only the official
[`bradleyboehmke/completejourney`](https://github.com/bradleyboehmke/completejourney)
source pinned to commit
[`5b5d061`](https://github.com/bradleyboehmke/completejourney/tree/5b5d06192b9856edd04e4d405787af2f2e4a1fef).
The preparation manifest records the SHA-256 of every downloaded R file and
every canonical Parquet table. Raw and prepared data are deliberately ignored
by Git.

This document is the authoritative interpretation guide for that dataset in
WhyBack. It describes the population and measurement boundary as well as the
meaning of individual fields.

## What story the data can tell

Complete Journey is well suited to describing retailer-visible household
purchasing over time: transaction frequency, basket composition, category
movement, promotion availability, campaign participation, coupon redemption,
and changes in observed engagement. It primarily tells a **retailer-centered
behavioral story**. It records what happened inside the observed retailer's
ecosystem; it generally does not reveal customer intent or the household's
complete purchasing and life context.

Appropriate uses include:

- descriptive longitudinal analysis of observed household behavior;
- customer-engagement, category, and basket exploration;
- exploration of recorded marketing response;
- hypothesis generation; and
- testing evidence-grounded, agentic analytical workflows.

Inappropriate uses include:

- claiming that these households represent consumers nationally;
- diagnosing a household's personal motives;
- claiming causal effects from observational patterns;
- making high-stakes decisions about individual people; or
- assuming that no recorded transaction means no grocery purchase occurred
  elsewhere.

## Population represented

The official data contains approximately 2,469 frequent-shopper households
associated with one grocery-retail ecosystem and roughly one year of
observations. The unit is a household identifier, not an identified person. One
identifier can reflect purchases by multiple household members, so WhyBack
must not interpret a household pattern as the behavior or intent of a specific
individual.

Demographics exist for only 801 of the 2,469 transacting households, and some
demographic fields remain missing within that subset. Transaction and marketing
visibility is limited to the observed retailer. The source does not establish
national representativeness, and WhyBack does not infer geographic, racial,
ethnic, or socioeconomic representativeness that the official documentation
does not support.

## Selection and observability biases

The data has important, overlapping limitations:

- **Frequent-shopper selection:** identified frequent shoppers can differ from
  occasional, anonymous, or non-participating shoppers.
- **Loyalty and identity observability:** purchases not linked to an observed
  household identifier are outside the household history.
- **Retailer-only visibility:** purchases from competitors, restaurants, and
  other online or offline channels are missing.
- **Continued-observation or survivorship bias:** remaining observable in the
  retailer ecosystem is not the same as remaining in the underlying consumer
  population.
- **Household aggregation:** multiple people's purchases and changes can be
  combined under one identifier.
- **Missing demographics:** demographic comparisons use an incomplete subset
  and are not the basis for primary peer matching or recommendations.
- **Campaign-targeting bias:** households selected for campaigns may already
  differ because of prior behavior or an estimated risk signal.
- **Promotion observability:** product/store/week availability does not show
  that any household member noticed an offer.
- **Temporal coverage:** roughly one year is a narrow basis for separating
  recurring patterns from one-time conditions.
- **Retailer-value framing:** recorded retailer sales value describes value
  received by the retailer, not total household expenditure or welfare.

Accordingly, disappearance from this retailer's transaction history does not
prove that a household stopped purchasing groceries. Competitor behavior is
unobserved rather than absent.

## Language used in WhyBack

- `sales_value` is the amount received by the retailer after the recorded
  discounts. It is not necessarily a household's out-of-pocket payment.
  WhyBack renames and reports it as **retailer sales value**.
- A basket is a distinct `basket_id` within a household. A trip is represented
  by a distinct basket in the available data.
- Recency is anchored to the maximum timestamp/week in the dataset, never to
  today's wall-clock date.
- The source covers weeks 1–53. WhyBack anchors baseline and recent windows to
  the maximum observed week.

## Variables observed

The meaningful observed variables include:

- household, store, basket, and product identifiers;
- product hierarchy;
- recorded quantity;
- retailer sales value and recorded discounts;
- week and transaction timestamp;
- campaign participation, type, and timing;
- coupon redemption;
- product/store/week promotion availability; and
- limited household demographics.

These fields retain the semantic qualifications in the sections below.

## Product hierarchy and recorded quantity

Product metadata is incomplete. Canonical preparation maps absent hierarchy
labels to an explicit `UNKNOWN` value, and analytical joins are left joins so
economic rows cannot disappear. Category analysis reports mapping coverage and
must reconcile to transaction totals.

WhyBack retains the incomplete demographics table for documented context but
does not use protected or incomplete demographic attributes to choose
retention actions or primary peers. Peer selection is based on explainable
baseline behavior.

The recorded `quantity` field is not a safe primary engagement measure because
fuel uses a much larger quantity scale than ordinary packaged products. WhyBack
may expose it as recorded quantity with that limitation; decline detection and
primary conclusions rely on retailer sales value, distinct baskets, and active
weeks.

## Promotions mean availability, not exposure

Promotion records describe product placement or mailer availability by
`product_id`, `store_id`, and `week`. They do not establish that a household saw
an advertisement or display. Reports therefore use language such as:

> Promotion availability existed for this product at this store during this
> week.

The pinned source contains duplicate promotion keys. Preparation collapses
them to one state per `(product_id, store_id, week)` using Boolean presence and
sorted location-code sets before joining to transactions. The enrichment is
required to preserve transaction row counts and retailer sales totals.

## Campaigns and coupons

Campaign participation, campaign type, the campaign coupon-to-product pool,
redemptions, and transaction coupon discounts are observed separately. Coupon
UPCs are reused across campaigns, so preparation removes exact bridge
duplicates and redemption joins use both `coupon_upc` and `campaign_id`.

- Type B and Type C participants received the corresponding campaign coupon
  set.
- Type A participants received 16 coupons selected from a larger campaign pool,
  but the exact 16 identities delivered to a particular household are absent.

For Type A, WhyBack may report known participation and observed redemptions. It
must return a partial result and preserve the limitation when a question needs
the unavailable delivered identities. It never labels pool coupons as ignored,
infers category-level unredeemed exposure, or claims a missing purchase matched
an unseen offer.

## Variables not observed or inadequately controlled

WhyBack does not observe or adequately control for many plausible influences,
including:

- competitor pricing, promotions, store openings, and household purchases;
- household relocation, travel, transportation access, and local events;
- customer satisfaction, service problems, and customer intent;
- stockouts, product discontinuation, assortment changes, and changing prices;
- employment, income, and household-composition changes;
- health and dietary changes;
- weather;
- restaurant spending and online grocery activity elsewhere; and
- whether a particular person noticed a promotion or advertisement.

This list is illustrative, not exhaustive. These factors are alternative
possibilities, not explanations established by the data.

## What comparisons account for

WhyBack is not a randomized controlled experiment. Where the corresponding
evidence is available, it can make comparisons more consistent by using:

- the same declared baseline and recent calendar windows;
- consistent metric definitions and eligible-household criteria;
- behaviorally similar peers, with the target excluded;
- contemporaneous movement among eligible households;
- contemporaneous category movement among households with meaningful baseline
  category activity; and
- product/store/week promotion availability where relevant.

These comparisons account for selected observed dimensions only. They do not
balance every measured characteristic, and they do not control unobserved
confounders such as competitor activity, life events, satisfaction, or local
conditions. Behavioral peers are descriptive comparison households, not a
causal control group.

## Marketing-treatment confounding

Marketing treatment may not be random. Offers can be targeted using previous
purchase behavior, and households believed to be at risk can receive more
marketing. An observed relationship between campaigns, coupons, promotion-
associated purchasing, and later behavior can therefore reflect selection into
treatment rather than an effect of treatment. WhyBack must not say that a
coupon, campaign, or promotion caused a behavioral outcome unless a separate,
valid causal design supports that statement.

## Descriptive, associational, and causal limits

Complete Journey is observational. Declines, promotion availability, coupon
activity, and category movements may be associated, but they do not establish
why behavior changed or whether an action will cause retention. Recommendations
are hypotheses for human review and controlled measurement, not automated
outreach or causal claims.

Directly computed statements about recorded trips, retailer sales value,
categories, promotion availability, participation, redemption, and relative
position are descriptive. Evidence-grounded relationships among those observed
measures may support cautious associational language such as "associated with,"
"consistent with," "coincided with," or "may reflect." Ordinary WhyBack
evidence does not support causal language such as "caused," "drove," or
"resulted in."

## Temporal coverage and broad contemporaneous context

The source covers weeks 1–53, or roughly one year. That is not enough to
estimate recurring annual seasonality robustly. WhyBack therefore describes
widespread movement during the same periods as **broad contemporaneous
context**, not proven seasonality. A common movement may reflect holidays,
prices, assortment changes, retailer-wide conditions, economic effects,
weather, or other factors, and this dataset generally cannot distinguish among
them.

Weeks 1 and 53 contain fewer calendar days than ordinary weeks. The specified
detector anchors its recent window to maximum observed week 53, so WhyBack
preserves that transparent rule and discloses the partial-week caveat rather
than silently retuning the score for a more attractive result.

## Official references

- [Pinned Complete Journey vignette](https://github.com/bradleyboehmke/completejourney/blob/5b5d06192b9856edd04e4d405787af2f2e4a1fef/vignettes/completejourney.Rmd)
- [Pinned transaction documentation](https://github.com/bradleyboehmke/completejourney/blob/5b5d06192b9856edd04e4d405787af2f2e4a1fef/R/transactions.R)
- [Pinned promotion documentation](https://github.com/bradleyboehmke/completejourney/blob/5b5d06192b9856edd04e4d405787af2f2e4a1fef/R/promotions.R)
