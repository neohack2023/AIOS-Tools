---
applyTo: "src/aios_tools/audio_*.py,.github/workflows/audio-model-dependency-lock.yml,.github/workflows/demucs-model-quarantine.yml"
---

# Audio/model department

Load `AGENTS.md`, `docs/VALIDATION.md`, and the relevant dependency-lock/quarantine workflow before modifying audio/model behavior.

Preserve model provenance, dependency locking, quarantine boundaries, deterministic fixtures, and receipt semantics. Never widen download/network/model-execution authority merely to make a test pass.

A model becoming available does not imply it is approved for unrestricted runtime use. Keep availability, eligibility, verification, and authorization separate.
