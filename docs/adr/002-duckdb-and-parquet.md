# ADR 002 — DuckDB and Parquet

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

Complete Journey contains about 1.47 million transaction rows and 20.94 million
raw promotion rows. Repeated pandas-only joins would duplicate memory and make
economic reconciliation harder to review. Spark would add a distributed runtime
and operational surface without a distributed-data requirement.

## Decision

Convert the pinned R source once into typed, Zstandard-compressed Parquet.
Canonicalize promotions and materialize household-week and basket grains during
preparation. Put a narrow `DataRepository` around one local DuckDB connection
and named read-only views; analytical tools use parameterized SQL with pushdown
and return small typed boundaries.

The manifest hashes every source and prepared file and records schemas, row
counts, diagnostics, and derived definitions. Existing files are reusable only
when all hashes still match.

## Consequences

- Columnar scans, grouping, and predicate pushdown handle the local data volume
  without a service or cluster.
- Derived grains avoid reparsing R files and repeating expensive preparation.
- SQL and reconciliation diagnostics remain inspectable.
- DuckDB is a local concurrency and durability boundary, not the production
  warehouse. The repository interface is the migration seam.
