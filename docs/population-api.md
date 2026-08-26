# Population intelligence API

Population intelligence is a collection-level, descriptive comparison of three
explicitly nested cohorts: all baseline-eligible households, the subset flagged
at the configured detector threshold, and the investigated batch selected from
that flagged cohort. These cohorts are selected and are not statistically
independent. The API does not calculate p-values or make causal, recoverable-
revenue, churn-probability, or expected-uplift claims.

## Endpoints

- `GET /api/population?collection=<collection-id>` returns the verified
  collection-level population contract.
- `GET /api/population/export?collection=<collection-id>&format=json` downloads
  the same safe JSON projection.
- `GET /api/population/export?collection=<collection-id>&format=csv` downloads
  its long-form CSV representation.

The response declares `availability` as `full`, `partial`, or `unavailable` and
lists missing-data reasons. New manifests that declare `population_summary` and
`population_schema_version` must pass artifact hash and schema reconciliation.
Preserved collections without those fields receive an honest partial response
derived from their reports and detector-sensitivity counts; absent
distributions remain unavailable rather than being represented as zero.

## CSV long format

Every row has these columns:

```text
record_type,cohort,metric,key,bin_start,bin_end,value,count,household_id,status,context,factor_type,factor_label,action,confidence,warnings
```

`record_type` determines which columns are populated:

| Record type | Meaning |
| --- | --- |
| `cohort_stat` | Count, mean, median, quartiles, deciles, and range for one cohort metric. |
| `histogram_bin` | A common-bin count for one cohort metric. |
| `sensitivity` | Declared threshold and resulting flagged count/share. |
| `action_mix`, `factor_mix`, `context_mix` | Executive aggregate counts. |
| `investigated_household` | Rank, outcome, context, structured factor, governed action, confidence, and warnings for an investigated row. |

## Identifier boundary

Eligible and flagged household identifiers never cross the bridge. Density
cells and aggregate cohort records contain counts only. Only household IDs in
the investigated batch are exposed in JSON or CSV, because those IDs already
have report drill-downs in the collection.
