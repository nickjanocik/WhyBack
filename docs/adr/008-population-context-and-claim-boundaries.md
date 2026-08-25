# ADR 008 — Population context and claim boundaries

- **Status:** Accepted
- **Date:** 2026-08-25

## Context

A household-level decline can coincide with movement across the retailer,
behavioral peers, or an entire category. Interpreting the target in isolation
can make a common contemporaneous change look uniquely customer-specific. The
Complete Journey source is also observational and spans roughly one year, so it
does not identify customer intent, control all confounders, or establish a
recurring annual seasonal pattern.

WhyBack already had a deterministic behavioral-peer tool, evidence ledger,
confidence cap, and causal-language defense. It lacked a full eligible-
population benchmark, protected category context, and a typed claim ceiling
that survived from evidence through final reports.

## Decision

Keep exactly six model-visible tools. Extend `peer_comparison` to compute the
target's signed retailer-sales change against both the full eligible household
population and robust behavioral peers. Extend `category_decomposition` to
compare selected loss categories with eligible households that had meaningful
baseline activity in the same category. Every comparison excludes the target;
peer scaling is fitted without it. Household distributions, not aggregate
retailer totals, are primary.

Centralize cohort and classification thresholds in immutable `ContextPolicy`:

- baseline eligibility requires four active weeks, six distinct baskets, and
  positive retailer sales value;
- reliable context requires 20 population households, five peers, or 20
  category households;
- meaningful baseline category activity requires retailer sales value of at
  least 1.0;
- broad movement means at least a 0.60 declining share;
- a material target-to-median gap is 0.10; and
- movement is similar within 0.10.

Signed change is `(recent - baseline) / baseline`, so lower is worse. A target
that is materially worse than both population and peer medians is
`customer_specific` only when broad movement is absent; with broad movement it
is `mixed`. Movement is `broad_context` only when both declining shares meet
the broad threshold and the target is similar to both medians. Unreliable
cohorts are `insufficient_context`; all other reliable combinations are
`mixed`. These rules are deterministic and are not tuned by the model.
When more than one bounded context call exists, WhyBack resolves it with the
conservative precedence `broad_context`, `insufficient_context`, `mixed`, then
`customer_specific`; displayed distribution values must come from the exact
call that supplied the winning classification. Every cited category must have
matching category context. A missing category comparison is treated as
insufficient unless broad evidence imposes the lower confidence cap.

Introduce `ClaimType` with `descriptive`, `associational`, and `causal` values.
Each evidence record declares its maximum supported type. Final drivers declare
a type, cite supporting evidence, cite counterevidence or explain why none was
material, and retain limitations. The verifier rejects claims above any cited
evidence ceiling and rejects all causal drivers from the current observational
tools. Code-owned report drivers inherit the weakest cited ceiling; model prose
cannot promote it.

Counterevidence is driver-scoped rather than a free-form evidence label. A
counter must be broad or mixed context that qualifies the claimed uniqueness,
or an action-relevant observed measure that does not satisfy the action's
adverse-direction predicate. Category counters must match a supported category.
Otherwise the verifier rejects it as unrelated; when no such record exists the
driver must state that no material counterevidence was identified. Limitations
from every valid partial tool result remain visible even when that result is not
used as support or counterevidence.

Context is authoritative even when the model does not cite it. Broad context
caps confidence at low; mixed or insufficient context caps it at medium.
Matching broad category context also caps a category action at low. Missing
context is a limitation, never neutral evidence. Every adjustment and its
evidence IDs are recorded in `verification_passed` audit events and the report.
Reports explicitly separate observed scope, unsupported causal conclusions,
unobserved factors, counterevidence, and the human-reviewed experiment. They
call common movement **broad contemporaneous context**, not proven seasonality.

## Consequences

- Reviewers can see target, population, peer, and category distributions with
  cohort sizes, sign conventions, exclusion, provenance, and limitations.
- Population context can temper a customer-specific interpretation but cannot
  prove a particular broad cause such as holidays, prices, or seasonality.
- Current evidence can support descriptive and cautious associational claims,
  never causal treatment claims.
- Category and peer cohorts become partial when declared minimums are not met;
  unstable percentiles or medians are not fabricated.
- Recommendations remain catalog-governed hypotheses for human review and
  prospective measurement, not promises of retention.
