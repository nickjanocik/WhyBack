# Complete Journey data semantics

WhyBack uses only the official
[`bradleyboehmke/completejourney`](https://github.com/bradleyboehmke/completejourney)
source pinned to commit
[`5b5d061`](https://github.com/bradleyboehmke/completejourney/tree/5b5d06192b9856edd04e4d405787af2f2e4a1fef).
The preparation manifest records the SHA-256 of every downloaded R file and
every canonical Parquet table. Raw and prepared data are deliberately ignored
by Git.

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

## Product hierarchy and demographics

Product metadata is incomplete. Canonical preparation maps absent hierarchy
labels to an explicit `UNKNOWN` value, and analytical joins are left joins so
economic rows cannot disappear. Category analysis reports mapping coverage and
must reconcile to transaction totals.

Demographics exist for only 801 of the 2,469 transacting households and some
demographic fields remain missing. WhyBack retains the table for documented
context but does not use protected or incomplete demographic attributes to
choose retention actions or primary peers. Peer selection is based on
explainable baseline behavior.

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

## Analytical limits

Complete Journey is observational. Declines, promotion availability, coupon
activity, and category movements may be associated, but they do not establish
why behavior changed or whether an action will cause retention. Recommendations
are hypotheses for human review and controlled measurement, not automated
outreach or causal claims.

Weeks 1 and 53 contain fewer calendar days than ordinary weeks. The specified
detector anchors its recent window to maximum observed week 53, so WhyBack
preserves that transparent rule and discloses the partial-week caveat rather
than silently retuning the score for a more attractive result.

## Official references

- [Pinned Complete Journey vignette](https://github.com/bradleyboehmke/completejourney/blob/5b5d06192b9856edd04e4d405787af2f2e4a1fef/vignettes/completejourney.Rmd)
- [Pinned transaction documentation](https://github.com/bradleyboehmke/completejourney/blob/5b5d06192b9856edd04e4d405787af2f2e4a1fef/R/transactions.R)
- [Pinned promotion documentation](https://github.com/bradleyboehmke/completejourney/blob/5b5d06192b9856edd04e4d405787af2f2e4a1fef/R/promotions.R)
