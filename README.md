# Holdfast

**Stable outcomes, smarter prompts.**

The destination is fixed. The route gets better.

Holdfast separates what your downstream systems depend on (frozen) from how you deliver it (evolvable), then uses evidence from real usage to improve the route while guaranteeing the destination doesn't change.

## How it works

1. **Setup** — define a contract: what's frozen (output schemas, formats), what's evolvable (prompts, examples), and what invariants must hold.
2. **Instrument** — log evidence from your pipeline with `log_run()` or the `@track` decorator (supports sync and async).
3. **Monitor** — detect drift, variance, and failure patterns across runs.
4. **Evolve** — propose bounded improvements to evolvable surfaces, backed by evidence. Claude Code (recommended) or programmatic via `propose_evolution()`.

Human approval required in `monitor` and `semi-auto` modes. Nothing changes without evidence.

## Install

```bash
pip install holdfast
```

Optionally install the Claude Code skill for interactive evolution:

```bash
# Personal — available across all projects
mkdir -p ~/.claude/skills/holdfast
cp skills/holdfast/SKILL.md ~/.claude/skills/holdfast/SKILL.md

# Or via plugin
/plugin add kevintelford/holdfast
```

## Quick start

### 1. Create a contract

By convention, contracts live under `holdfast/contracts/` in your project root:

```
holdfast/
  contracts/
    my-pipeline/
    ├── contract.yaml
    ├── frozen/
    │   └── output_schema.json
    ├── evolvable/
    │   └── prompt.md
    ├── invariants.yaml
    └── detection.yaml          # optional — pattern detection rules
```

**contract.yaml:**
```yaml
name: my-pipeline
version: 1
evolution_mode: monitor     # monitor | semi-auto | auto

frozen:
  output_schema: "frozen/output_schema.json"

evolvable:
  prompt: "evolvable/prompt.md"
```

### 2. Log evidence

```python
from holdfast import Contract, log_run

contract = Contract.load("holdfast/contracts/my-pipeline/")
prompt = contract.get_evolvable("prompt")

result = your_llm_call(prompt, data)

log_run(contract=contract, output=result, passed=validate(result))
```

Or use the decorator:

```python
from holdfast import Contract, track

contract = Contract.load("holdfast/contracts/my-pipeline/")

@track(contract)
def classify(item: dict) -> dict:
    prompt = contract.get_evolvable("prompt")
    # ... your LLM call ...
    return result

# Each call logs evidence. Pass/fail determined by invariant validation.
```

The `@track` decorator also works with async functions:

```python
@track(contract)
async def classify(item: dict) -> dict:
    ...
```

### 3. Monitor for patterns

```bash
python -m holdfast status holdfast/contracts/my-pipeline/
# Contract: my-pipeline (v1, mode: monitor)
# Evidence: 47 runs (42 passed, 5 failed)
# Alerts: 1 — score variance on 'score' (stddev=0.89)
```

Or in Python:

```python
from holdfast import Contract, check_contract

contract = Contract.load("holdfast/contracts/my-pipeline/")
alerts = check_contract(contract)
```

### 4. Evolve

**Interactively with Claude Code** (recommended for `monitor` and `semi-auto` modes):

> "Look at the evidence in holdfast/contracts/my-pipeline/ and propose an evolution."

The skill reads evidence, analyzes patterns, and proposes bounded edits to evolvable surfaces. Frozen surfaces are never touched. You approve before anything changes.

**Programmatically** (for `auto` mode or CI pipelines):

```python
from holdfast import Contract, propose_evolution, apply_evolution

contract = Contract.load("holdfast/contracts/my-pipeline/")
proposal = propose_evolution(contract=contract, llm=my_llm_callable, min_runs=10)

if proposal:
    print(proposal.diff)
    print(proposal.rationale)
    apply_evolution(contract=contract, proposal=proposal)
```

### 5. Rollback if needed

```python
from holdfast import Contract, rollback, list_versions

contract = Contract.load("holdfast/contracts/my-pipeline/")
versions = list_versions(contract)  # [1, 2, 3]
rollback(contract, to_version=2)
```

## Evolvable references

Evolvable surfaces can reference standalone files or Python symbols in existing source files.

### File references (default)

```yaml
evolvable:
  prompt: "evolvable/prompt.md"
```

Reads and writes the entire file.

### Source references (Python symbols)

Point directly at string constants in your source code — no need to extract prompts into separate files:

```yaml
evolvable:
  system_prompt:
    path: "src/pipeline/prompts.py"
    symbol: "SYSTEM_PROMPT"              # module-level assignment

  maturity_prompt:
    path: "src/pipeline/prompts.py"
    symbol: "CyberPrompts.MATURITY_PROMPT"  # class attribute
```

Supports:
- **Module-level assignments**: `PROMPT = "..."` — symbol is `"PROMPT"`
- **Class attributes**: `class Foo: PROMPT = "..."` — symbol is `"Foo.PROMPT"`

Holdfast uses `ast.parse()` for extraction — no code execution. Write-back preserves all surrounding code and original quoting style.

Both formats can be mixed in the same contract. `get_evolvable()` returns the string value regardless of format.

## Contracts

A contract separates outcome (frozen) from method (evolvable):

- **Frozen surface**: output schemas, response formats, scoring scales, coding standards. Protected.
- **Evolvable surface**: prompts, examples, reasoning instructions. Improves from evidence.
- **Invariants** (`invariants.yaml`): automated checks that must pass before and after changes.
- **Detection rules** (`detection.yaml`): pattern detection across runs (variance, drift, failure rate).

### Evolution modes

| Mode | Behavior |
|---|---|
| `monitor` | Detect and alert only. Default. |
| `semi-auto` | Detect, propose, human approves. |
| `auto` | Detect, propose, apply if invariants pass. |

Set in `contract.yaml` as `evolution_mode`. Graduate when you trust the contract.

### Invariant types

| Type | What it checks |
|---|---|
| `schema` | JSON Schema validation against a frozen schema file |
| `contains` | Field value is one of the allowed values (scalar) or contains all required values (list) |
| `custom` | External Python script — passes output as JSON on stdin, checks exit code |

**Security note on custom scripts:** Custom invariant scripts execute as the current user via `subprocess.run()` with full filesystem access. The only guard is a 30-second timeout. This is fine for local development and CI where you control the scripts. Review any custom scripts before trusting third-party contracts.

### Detection rule types

| Type | What it detects |
|---|---|
| `variance` | Field values vary too much within a window. Optional `group_by` to check per-group (e.g. per question). |
| `drift` | Field average shifted between baseline and recent windows |
| `failure_rate` | Too many failed runs in a window |

## Storage

Everything is flat files in `.holdfast/` inside each contract directory:

```
.holdfast/
├── evidence/     # JSON files, one per run
└── versions/     # snapshots + evolution records
```

Human-readable, greppable, no database.

### Gitignore

Add this to your project's `.gitignore`:

```
**/.holdfast/
```

Evidence and version snapshots are managed state, not source. They can get large with many runs. If you want to track them (e.g., for team review of evidence), remove this line — the files are plain JSON and git handles them fine.

## Inspired by

[Memento-Skills](https://arxiv.org/abs/2603.18743) (Zhou et al., 2026) demonstrated that agents can improve by evolving external artifacts rather than retraining models. Holdfast applies that insight with governance — frozen contracts, invariant validation, audit trails, and graduated trust levels for enterprise pipelines.

## License

MIT
