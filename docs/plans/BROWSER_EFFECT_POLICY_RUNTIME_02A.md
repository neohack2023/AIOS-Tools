# BROWSER_EFFECT_POLICY_RUNTIME_02A

## Status

IMPLEMENTATION CANDIDATE / NOT ACTIVE

## Frozen base

- Repository: `neohack2023/AIOS-Tools`
- Base commit: `2913c34d5e156d5f03871d4898b6061123b144ee`
- Branch: `agent/browser-effect-policy-runtime-02a`

## Governing authority

- Notion: `BROWSER_CAPABILITY_RUNTIME_02 — GOVERNED_FULL_POWER`
  - https://app.notion.com/p/3c543bd4ae4a81678197ed28c361b536
- Drive mirror: `BROWSER_CAPABILITY_RUNTIME_02 — drive_shadow v0.1`
  - https://docs.google.com/document/d/1QisEJ_A36Ce-zMr8Ca5YsuJJd5-DrpihTY8jHwykOsg/edit
- Implementation issue: #44
  - https://github.com/neohack2023/AIOS-Tools/issues/44

## Goal

Close the current execution-policy gap before any browser/network executor is registered.

Every registered AIOS tool must declare a trusted `effect_class`. The shared runner must enforce that declaration before handler invocation and record it in the governed execution receipt.

02A intentionally keeps all network and remote-mutation effect classes blocked. It does not weaken the current `external_network_effects_enabled=false` law.

## Effect taxonomy

- `NO_EXTERNAL_EFFECT`: ephemeral computation or session-only state with no durable or remote effect.
- `LOCAL_DURABLE_WRITE`: governed durable mutation confined to admitted local artifact scope.
- `READ_NETWORK`: public or authorized remote reads with no remote mutation.
- `REMOTE_MUTATION_REVERSIBLE`: remote mutation with a verified rollback path.
- `REMOTE_MUTATION_HIGH_IMPACT`: irreversible, destructive, financially consequential, identity-sensitive, publishing, sending, purchasing, permission-changing, or otherwise high-impact remote mutation.

Effect class is policy input. It does not grant authority. Existing mode, approval, write-scope, and authority-transfer checks remain independently enforced.

## In scope

1. Add `effect_class` to every tool registry entry.
2. Bump registry and execution-policy candidate versions.
3. Add an explicit effect-policy section to the execution policy.
4. Validate known classes and effect/mode consistency at configuration load.
5. Fail closed when a registered tool's effect class is not currently admitted.
6. Preserve the global external-network prohibition.
7. Record the declared effect class in every execution receipt, including blocked/failed receipts.
8. Expose effect-policy state through `system.health`.
9. Update the result contract and regression tests.

## Out of scope

- Playwright dependency or browser installation.
- Browser launch or existing-session attachment.
- Any live network read.
- Cross-origin navigation policy.
- Authentication/session storage.
- Downloads or uploads.
- Remote mutation.
- Site profiles.
- Suno-specific execution.
- Any runtime activation or merge authorization.

## Expected registry mapping

- `system.health` → `NO_EXTERNAL_EFFECT`
- `canonical.hash_json` → `NO_EXTERNAL_EFFECT`
- `schema.validate` → `NO_EXTERNAL_EFFECT`
- `audio.demucs.separate` → `LOCAL_DURABLE_WRITE`

## Policy invariants

- `effect_policy.known_effect_classes` is complete and unique.
- `effect_policy.allowed_effect_classes` is a subset of known classes.
- network classes are explicitly identified.
- remote mutation classes are explicitly identified and are also network classes.
- when `external_network_effects_enabled=false`, no network effect class may appear in `allowed_effect_classes`.
- `NO_EXTERNAL_EFFECT` may not be declared by a `WRITE` tool.
- `LOCAL_DURABLE_WRITE` requires `WRITE` mode.
- remote mutation classes require `WRITE` mode.
- missing or unknown effect classes fail configuration closed.

## Runner behavior

Admission order remains fail-closed:

1. load policy and registry;
2. validate request;
3. resolve tool metadata;
4. validate global/tool mode;
5. reject authority transfer;
6. reject disallowed effect class before handler invocation;
7. apply existing WRITE approval gate;
8. invoke handler.

No caller-supplied field may lower or override the registry effect class.

## Receipt behavior

Add `effect_class` to the execution receipt. Use `UNKNOWN` only when no trustworthy registry declaration is available, such as configuration failure or unknown-tool resolution.

`external_effects` remains empty and contract-limited in 02A because no external effect is admitted yet.

## Files

Expected modifications:

- `registry/tools.v0.1.json`
- `policies/execution-policy.v0.1.json`
- `src/aios_tools/config.py`
- `src/aios_tools/runner.py`
- `src/aios_tools/envelope.py`
- `contracts/tool-result.v0.1.schema.json`
- `tests/test_core.py`
- `tests/test_audio_demucs_tool.py` if needed for effect assertions

## Validation

Repository-required validation after implementation:

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

CI and review evidence must be tied to the exact branch head. No pass claim may be made from an untested commit.

Additional 02A assertions:

- missing `effect_class` blocks configuration;
- unknown `effect_class` blocks configuration;
- network-class tool is blocked before handler invocation while network effects are globally disabled;
- local durable write retains the existing WRITE approval gate;
- health receipt exposes the admitted effect classes;
- completed and blocked receipts validate against the result contract with `effect_class` present.

## Risks

- A new required registry field can intentionally fail old/partial registry fixtures. Tests must update fixtures or prove failure is correct.
- Receipt schema changes can expose CLI/MCP parity drift. Both adapters must continue using the shared runner output unchanged.
- Effect classification must not replace existing mode or approval semantics.

## Rollback

Revert the 02A commits on this branch. No browser/network capability is activated by this slice, so rollback has no remote side effects.
