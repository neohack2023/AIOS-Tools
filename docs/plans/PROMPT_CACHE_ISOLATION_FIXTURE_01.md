# PROMPT_CACHE_ISOLATION_FIXTURE_01

Phase 7 of the legacy Notion research backlog.

Prompt caching is reusable performance state, not memory, correctness evidence, or authority.

A reusable cache identity is bounded by:
- tenant;
- reusable prefix;
- system prompt;
- tool definitions;
- policy revision;
- TTL.

Decisions:
- REUSE_ALLOWED;
- MISS_REBUILD;
- BLOCK_CROSS_TENANT;
- FRESHNESS_EVIDENCE_REQUIRED;
- BYPASS_CACHE.

A cache hit never satisfies an independent freshness requirement. Cache unavailability degrades cost/latency only and must allow the uncached correctness path to continue.

This module does not implement a cache, store prompt content, or confer authority.
