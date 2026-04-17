---
description: Review holdfast evidence and detect drift. Use when the user says
  "review evidence", "what's drifting", "how's my classifier doing",
  "check holdfast", "anything drifting", or asks about patterns in their
  pipeline or task quality.
---

# Holdfast — Review

You read accumulated evidence, run detection rules, and summarize what's
working and what's drifting.

**Core rule:** frozen surfaces don't change. Evolvable surfaces improve
only with evidence and approval.

---

## Find contracts

```bash
find . -name "contract.yaml" -not -path "*/.holdfast/*"
```

For each contract, read:
```bash
cat {contract_dir}/contract.yaml
cat {contract_dir}/invariants.yaml
cat {contract_dir}/detection.yaml
ls {contract_dir}/.holdfast/evidence/
```

---

## Run detection

### Pipeline mode — Python API

If Python and holdfast are installed:

```python
from holdfast import Contract, check_contract
contract = Contract.load("{contract_dir}")
alerts = check_contract(contract)
```

### Claude mode — in-context

Read `detection.yaml` for the rules. Read all evidence JSON files. Then
compute each rule. **Show your work** — list the values, show the math,
then state whether the threshold was exceeded.

#### Failure rate

1. Take the most recent N runs (N = `window`)
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

## Summarize findings

Be specific. Cite run IDs. Examples:

- "Across 20 runs, 6 were rejected — all on refactoring tasks where the diff was too large."
- "Satisfaction drifted from 4.2 to 3.1 over the last 15 runs. The approach change in v2 may be too aggressive."
- "All runs pass. No pattern to address."

If there are patterns worth acting on, suggest the user run `/holdfast:evolve`.
