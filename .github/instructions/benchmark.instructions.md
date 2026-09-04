---
applyTo: "benchmarks/**,src/aios_tools/benchmarks/**,.github/workflows/benchmark-registry.yml"
---

# Benchmark department

Load `AGENTS.md`, `docs/VALIDATION.md`, `docs/BENCHMARK_ENVIRONMENT.md` when relevant, and the benchmark registry/workflow before edits.

Preserve benchmark identity, environment provenance, deterministic fixtures, and comparison semantics. Do not present a benchmark delta as a product/runtime acceptance result unless the governing contract says so.

When changing benchmark registration or scoring, update the corresponding tests and evidence surfaces in the same bounded change.
