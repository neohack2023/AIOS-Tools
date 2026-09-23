# MEMORY_STAGE_DIAGNOSTIC_01

## Phase

Legacy Notion research backlog, phase 3.

## Purpose

Stop labeling every memory failure as a retrieval failure.

Classify sealed probes across three independent stages:

- ingestion / representation;
- retrieval / packet assembly;
- utilization / answer or action.

MULTI_STAGE is allowed only when interaction is positively evidenced. It is not an uncertainty bucket.

## Research basis

IFCMemoryBench explicitly decomposes long-term agent memory performance into ingestion, retrieval, and utilization. Its results show that topically relevant retrieval can coexist with incomplete or fragmented stored memory.

The AIOS prototype maps those stages to existing STONE/MASON, retrieval, Context Envelope, and execution boundaries.

## Minimal decision law

- one failed stage + sufficient evidence => attribute that stage;
- failed ingestion + blocked retrieval => ingestion;
- multiple failed stages + explicit interaction evidence => MULTI_STAGE;
- multiple failed stages without interaction proof => INSUFFICIENT_EVIDENCE;
- any UNKNOWN stage evidence => INSUFFICIENT_EVIDENCE;
- no failures => NO_FAILURE.

## Boundary

This feature does not:
- mutate memory;
- repair retrieval;
- judge semantic answer quality;
- call an LLM judge;
- infer missing evidence;
- change authority;
- create new retrieval infrastructure.

It only emits a deterministic diagnostic receipt with exact evidence pointers.
