# Cognition Receipt Slice 3: Retrieval Trajectory Contract

## Objective

Define one deterministic, metadata-only representation of retrieval candidates, packet decisions, and context composition before any live retrieval connector is instrumented.

## Included

- canonical packet IDs from source system plus exact source reference
- authority-role labels
- rank and optional score
- explicit selected or rejected disposition
- mandatory reason codes
- exact context-packet membership
- Cognition Receipt-compatible retrieval and composition events
- JSON Schema Draft 2020-12 contract
- negative-path tests

## Safety boundary

- no raw source content
- no prompts, embeddings, vectors, secrets, or credentials
- no connector reads or writes
- no automatic conflict resolution
- no authority transfer
- no external effects
- no answer generation
- no Observatory integration

## Acceptance criteria

- every decision follows packet consideration
- each packet receives exactly one terminal disposition
- selected packets appear exactly once in the composed context packet
- rejected packets never enter context
- identifiers are deterministic
- content-bearing fields fail closed
- generated event specs are compatible with the Cognition Receipt vocabulary

## Deferred

Live Notion, Google Drive, GitHub, web, or vector retrieval instrumentation requires a real governed retrieval runtime and remains a later slice.
