---
name: holdfast
description: Review accumulated evidence from pipeline runs or interaction
  patterns and propose governed improvements. Use when the user says "evolve",
  "review evidence", "what's drifting", "improve the prompt", "track my",
  "use holdfast to", or when you notice repeated corrections, failures, or
  inconsistencies across interactions.
---

# Holdfast — Governed Evolution

You govern the evolution of prompts, skills, and agent behavior. The core
rule: **frozen surfaces don't change. Evolvable surfaces improve only with
evidence and approval.**

Holdfast operates in two modes:
- **Pipeline mode** (`mode: pipeline` in contract.yaml) — Python library writes evidence via `log_run()` / `@track`. You read evidence, run detection, and propose changes. **Do not write evidence yourself in pipeline mode.**
- **Claude mode** (`mode: claude`) — you write evidence yourself after tracked interactions. No Python needed.

Check `contract.yaml` for the `mode` field. If missing, assume `pipeline`.

---

## Discovery mode

When the holdfast skill is installed but no contract exists for the current
task type, nudge the user **once per task type per session**.

Trackable task types: code review, test generation, implementation planning,
refactoring, documentation writing, security auditing.

Trigger: you just completed a task matching one of these types and there is
no holdfast contract for it in this project.

Output exactly one line, then move on:

```
holdfast: this looks like a repeatable task (code review). want me to track quality over time? say "use holdfast to track this."
```

Rules:
- One nudge per task type per session. If ignored, don't repeat.
- If `holdfast_discover: false` appears in CLAUDE.md, never nudge.
- If a contract already exists for this task type, skip the nudge — go straight to evidence logging.
- Keep it to one line. Lowercase. No emoji. Near-zero token cost.

---

## Contract setup (claude mode)

When the user says "use holdfast to track X" or their CLAUDE.md says so:

### 1. Ask two questions

1. **What are you tracking?** — "code reviews", "test generation", etc.
2. **What does good look like?** — This becomes the frozen surface.

If the user is vague, draft the frozen standards yourself based on the task
type and ask for confirmation.

### 2. Create the contract

```
holdfast/contracts/{name}/
  contract.yaml
  frozen/
    standards.md          # what good looks like
  evolvable/
    approach.md           # how you approach the task (you draft this)
  invariants.yaml
  detection.yaml
  .holdfast/
    evidence/             # empty, will be populated
```

**contract.yaml:**
```yaml
name: {name}
version: 1
mode: claude
evolution_mode: semi-auto

frozen:
  standards: "frozen/standards.md"

evolvable:
  approach: "evolvable/approach.md"
```

**invariants.yaml:**
```yaml
- type: contains
  field: outcome
  values: ["accepted", "modified", "rejected"]
  description: "Outcome must be a tracked state"
```

**detection.yaml:**
```yaml
- type: failure_rate
  max_rate: 0.25
  window: 20
  description: "User rejection rate above 25%"

- type: drift
  field: satisfaction
  baseline_window: 10
  recent_window: 10
  max_shift: 1.0
  description: "User satisfaction shifted"
```

### 3. Mention where it lives, move on

Tell the user the contract location once, then continue with their work.

---

## Evidence writing (claude mode)

After completing a tracked task, write an evidence file. Do this silently
unless the user has `holdfast_verbose: true` in their CLAUDE.md or
contract.yaml, in which case print: `holdfast: logged run-NNNNN`

### When to log

A tracked interaction ends when:
- The user accepts, modifies, or rejects your output
- The user moves to a different topic
- The task is complete

Do not log mid-conversation. Wait for the outcome.

### How to log

1. List files in `{contract_dir}/.holdfast/evidence/`
2. Find the highest `run-NNNNN` number (parse the digits after `run-`)
3. Increment by 1, zero-pad to 5 digits
4. Write the evidence file:

```json
{
  "id": "run-NNNNN",
  "contract_name": "{name}",
  "contract_version": {version},
  "timestamp": "{ISO 8601 UTC}",
  "mode": "claude",
  "input_summary": "{brief description of the task}",
  "output": {
    "outcome": "accepted | modified | rejected",
    "satisfaction": {1-5},
    "feedback_summary": "{what the user did with your output}",
    "areas_covered": ["{dimensions you addressed}"],
    "areas_missed": ["{dimensions you missed, if any}"]
  },
  "passed": true,
  "notes": "",
  "tags": []
}
```

### Satisfaction scoring

Assess based on the user's behavior, not by asking them:

| Score | Meaning |
|-------|---------|
| 5 | Accepted without changes |
| 4 | Accepted with minor modifications |
| 3 | Used some parts, rewrote others |
| 2 | Mostly rejected, kept one idea |
| 1 | Rejected entirely |

### Pass/fail

- `passed: true` if outcome is "accepted" or "modified"
- `passed: false` if outcome is "rejected"

---

## Reading evidence (both modes)

Find contracts in the project:

```bash
find . -name "contract.yaml" -not -path "*/.holdfast/*"
```

For each contract, read the evidence:

```bash
ls {contract_dir}/.holdfast/evidence/
```

Read the contract to understand what's frozen and what's evolvable:

```bash
cat {contract_dir}/contract.yaml
cat {contract_dir}/invariants.yaml
cat {contract_dir}/detection.yaml
```

### Pipeline mode — Python API available

If Python and holdfast are installed, you can use the API:

```python
from holdfast import Contract, build_evolution_prompt, check_contract

contract = Contract.load("{contract_dir}")
prompt = build_evolution_prompt(contract)  # pre-built analysis prompt
alerts = check_contract(contract)          # run detection rules
```

### Claude mode — read files directly

Read the JSON evidence files and analyze them yourself. See detection
section below.

---

## Running detection

### With Python API (pipeline mode)

```python
from holdfast import Contract, check_contract
contract = Contract.load("{contract_dir}")
alerts = check_contract(contract)
```

### In-context (claude mode)

Read `detection.yaml` for the rules. Read all evidence JSON files. Then
compute each rule. **Show your work** — list the values, show the math,
then state whether the threshold was exceeded.

#### Failure rate

1. Take the most recent N runs (N = `window` from the rule)
2. Count runs where `passed` is false
3. Compute: `failure_count / total_count`
4. Alert if result exceeds `max_rate`

#### Variance

1. Take the most recent N runs (N = `window`)
2. Extract the target field value from each run (e.g., `output.satisfaction`)
3. Compute mean: `sum(values) / count`
4. Compute stddev: `sqrt(sum((v - mean)^2 for v in values) / (count - 1))`
5. Alert if stddev exceeds `max_stddev`
6. If `group_by` is set, bucket runs by that field and check each group separately

#### Drift

1. Take the first N runs as baseline (N = `baseline_window`)
2. Take the last M runs as recent (M = `recent_window`)
3. Compute mean of the target field for each window
4. Compute: `abs(recent_mean - baseline_mean)`
5. Alert if shift exceeds `max_shift`

---

## Summarize findings (both modes)

Be specific. Cite run IDs. Examples:

- "Across 20 runs, 6 were rejected — all on refactoring tasks where the diff was too large."
- "Satisfaction drifted from 4.2 to 3.1 over the last 15 runs. The approach change in v2 may be too aggressive."
- "All runs pass. No pattern to address."

---

## Propose evolution (both modes)

If there's a clear pattern, propose a bounded edit to the evolvable surface:

- State exactly what changes
- State what does NOT change (frozen surfaces, invariants)
- Cite the evidence (run IDs, patterns)
- Explain why this change addresses the pattern

If there's no clear pattern, say so. Don't propose changes for the sake of it.

---

## Apply evolution

### Pipeline mode — Python API

```python
from holdfast import Contract, apply_evolution
from holdfast.evolve import EvolutionProposal

contract = Contract.load("{contract_dir}")
proposal = EvolutionProposal(
    diff="{summary}",
    rationale="{why}",
    evidence_ids=["run-00012", "run-00015"],
    file_changes={"evolvable/approach.md": "{new content}"},
)
apply_evolution(contract, proposal)
```

### Claude mode — direct file edit

1. Copy current evolvable content to `.holdfast/versions/v{current_version}/`
2. Edit the evolvable file with the proposed changes
3. Bump `version` in `contract.yaml`
4. Tell the user what changed and how to rollback

---

## Wait for approval

Never apply without the user saying yes. Present the proposal and stop.
In `monitor` mode, don't even propose — just report findings.
