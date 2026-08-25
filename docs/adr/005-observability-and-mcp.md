# ADR 005 — Observability and MCP

- **Status:** Accepted; optional adapters deferred
- **Date:** 2026-08-24

## Context

The submission needs a complete, portable execution record and should remain
usable without an observability vendor or interoperability server. Optional
telemetry and MCP can be useful, but making either part of the core would add
API drift, dependencies, and failure modes unrelated to analytical correctness.

## Decision

Validated append-only JSONL is the authoritative local trace. It records concise
external decision fields, tool attempts, retries, evidence IDs, provenance, and
verifier outcomes; it redacts secrets and rejects hidden-reasoning fields. A
self-contained HTML viewer renders that file without a hosted application.

OpenTelemetry export with OpenInference-compatible semantic attributes is the
preferred future portable telemetry option. It must be opt-in, content-masked
by default, and work with a generic OTLP endpoint or local Phoenix without
making Phoenix required.

A future MCP adapter should expose the existing tool registry over local stdio
using the current MCP SDK. It must not duplicate analytics, serve HTTP, or
become a dependency of the WhyBack Investigator. Neither optional adapter is
implemented in the submitted core.

## Consequences

- Artifacts remain reviewable offline and do not depend on a service account.
- Production telemetry can mirror events without replacing the audit source of
  truth.
- MCP interoperability can be added behind the tested registry boundary.
- Cross-process durability, tamper evidence, and vendor dashboards remain
  production work rather than being implied by local JSONL.
