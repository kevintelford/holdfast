# Changelog

## v0.2.0 — 2026-04-12

### Evolvable source references

Point `contract.yaml` directly at Python string constants in your source files — no need to extract prompts into separate files. Supports module-level assignments (`SYSTEM_PROMPT`) and class attributes (`CyberPrompts.MATURITY_PROMPT`). Uses `ast.parse()` for safe extraction with no code execution. Write-back preserves surrounding code and original quoting style.

```yaml
evolvable:
  system_prompt:
    path: "src/pipeline/prompts.py"
    symbol: "CyberPrompts.SYSTEM_PROMPT"
```

### Async `@track` decorator

The `@track` decorator now supports async functions. Same evidence logging, same invariant validation — just awaited.

```python
@track(contract)
async def classify(item: dict) -> dict:
    ...
```

### Security hardening

- **Path boundary enforcement** — evolvable refs cannot escape the contract root via `../` traversal
- **Contract schema validation** — `contract.yaml` structure validated on load (required fields, ref format)
- **file_changes guard** — `apply_evolution()` rejects changes to files not declared as evolvable refs
- **Source file snapshots** — source-ref symbol values are snapshotted before evolution and restored on rollback

### Documentation

- README restructured as a progression: Setup → Instrument → Monitor → Evolve
- Claude Code positioned as the primary interface
- Trust model documented for custom invariant scripts (unsandboxed subprocess, 30s timeout)
- Evolvable reference formats documented (file refs + source refs)

## v0.1.0 — 2026-04-10

Initial release.

- Contract model: frozen/evolvable separation with `contract.yaml`
- Evidence collection: `log_run()` and `@track` decorator
- Invariant validation: schema, contains, custom script types
- Pattern detection: variance, drift, failure rate (with `group_by` support)
- Evolution engine: `propose_evolution()` with pluggable LLM callable
- Version management: snapshots, `apply_evolution()`, rollback
- CLI: `python -m holdfast status`
- Flat-file storage: human-readable JSON, no database
