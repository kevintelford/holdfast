# Changelog

## v0.5.1 — 2026-04-17

### Marketplace support and corrected install instructions

Added `marketplace.json` so the repo works as a Claude Code marketplace. Fixed install commands in README — the previous `claude plugin add github:` syntax doesn't exist.

Install:
```
/plugin marketplace add kevintelford/holdfast
/plugin install holdfast@holdfast
```

## v0.5.0 — 2026-04-17

### Claude Code plugin with four focused skills

Holdfast is now a proper Claude Code plugin. The monolithic skill is replaced by four focused skills:

- `/holdfast:track` — set up contracts and log evidence (discovery mode included)
- `/holdfast:review` — read evidence, run detection, explain patterns
- `/holdfast:evolve` — propose and apply bounded improvements
- `/holdfast:status` — quick summary across all contracts

All four skills work in both pipeline and Claude-only modes.

Install: `claude plugin add github:kevintelford/holdfast`

### Updated install flow

Plugin is now the primary install path. Python library is secondary, for pipeline instrumentation. README updated to reflect both paths with a skill/mode compatibility table.

## v0.4.0 — 2026-04-17

### Claude-only mode — no Python required

Holdfast now works entirely within Claude Code. Install the skill and say "use holdfast to track my code reviews" — Claude sets up the contract, logs evidence silently after each tracked interaction, runs detection, and proposes improvements. No Python library needed.

- **Discovery mode**: The skill passively notices repeatable tasks (code review, test generation, planning, refactoring, security auditing) and offers to track them. One nudge per task type per session, zero friction if ignored.
- **Evidence writing**: Claude logs evidence after each tracked interaction with outcome (accepted/modified/rejected), satisfaction score (1-5), and feedback summary. Silent by default, configurable with `holdfast_verbose: true`.
- **In-context detection**: Claude reads evidence files and computes failure rate, variance, and drift without Python. Shows its work.
- **Contract setup**: Two questions — what are you tracking, what does good look like — then Claude creates the full contract structure.

### Contract templates

Starter templates for common Claude-only use cases:
- `templates/claude-code-review/` — code review quality tracking
- `templates/claude-test-generation/` — test generation quality tracking

### Contract mode field

New `mode` field in contract.yaml: `"pipeline"` (default) or `"claude"`. The skill uses this to determine whether to write evidence itself or defer to the Python library.

## v0.3.0 — 2026-04-15

### Run ID limit fix

Run and evolution IDs now use 5-digit zero-padded format (`run-00001` instead of `run-001`). The previous 3-digit format capped at 999 runs per contract — production usage was already hitting 500+. The new `_max_seq_id()` helper correctly handles mixed-width IDs from existing evidence directories, so no migration is needed.

### Documentation

- **Detection windows**: Clarified how sliding windows work — runs outside the window are ignored, not deleted
- **Contract patterns**: Added recommended directory structure for multi-pipeline/variant projects

## v0.2.1 — 2026-04-15

### project_root for source refs outside contract directory

Source refs can now point at files outside the contract directory by setting `project_root` in `contract.yaml`. The security boundary widens from contract root to project root — paths must still stay within the boundary.

```yaml
project_root: "../.."    # resolved relative to contract dir, must be an ancestor
evolvable:
  system_prompt:
    path: "src/pipeline/prompts.py"
    symbol: "CyberPrompts.SYSTEM_PROMPT"
```

### Security fixes

- Invariant script and schema ref paths now validated against contract root boundary (previously unchecked — could traverse via `../`)
- New "Security considerations" section in README covering: custom scripts, evidence data sensitivity, auto mode risks, prompt injection via evidence

### Adversarial path traversal tests

Added tests for direct traversal, nested traversal, absolute path injection, null bytes, URL-encoded traversal, and symlink escape attempts.

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
