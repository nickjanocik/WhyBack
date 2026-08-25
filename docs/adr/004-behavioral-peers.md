# ADR 004 — Behavioral peers

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

Demographics are absent for most Complete Journey households, include sensitive
attributes, and do not directly describe shopping engagement. Requiring them
would shrink or bias the cohort and create a weak basis for retention treatment.

## Decision

Peer comparison uses explainable baseline behavior: log-transformed retailer
sales value, trip count, median basket value, active weeks, and category
concentration. Features are robust-scaled and nearest peers are selected
deterministically. The target is always excluded and the method, cohort size,
distribution context, and limitations are returned.

Demographics may remain in the prepared source for documented context, but they
do not drive primary peer selection or Next Best Action recommendations.

## Consequences

- Every transacting household with sufficient behavior can be considered
  without demographic completeness.
- The peer rationale is inspectable and target exclusion is machine-verified.
- Peers provide descriptive context, not causal controls or proof of why a
  customer declined.
- Production must still monitor behavioral features for proxy effects and
  disparate treatment.
