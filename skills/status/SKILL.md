---
description: Quick holdfast status check across all contracts. Use when the user
  says "holdfast status", "how are my contracts", or wants a summary of all
  tracked pipelines and tasks.
---

# Holdfast — Status

Give a concise summary of all holdfast contracts in the project.

---

## Find contracts

```bash
find . -name "contract.yaml" -not -path "*/.holdfast/*"
```

## For each contract, report

### Pipeline mode — Python API

```bash
python -m holdfast status {contract_dir}
```

Or:
```python
from holdfast import Contract, check_contract
from holdfast.store import list_evidence

contract = Contract.load("{contract_dir}")
runs = list_evidence(contract.storage_dir(), contract_name=contract.name)
alerts = check_contract(contract)
```

### Claude mode — read files

1. Count evidence files in `.holdfast/evidence/`
2. Count passed vs failed (read each JSON, check `passed` field)
3. Read `contract.yaml` for version and mode
4. Run detection rules (see `/holdfast:review` for math)

## Output format

Keep it concise:

```
code-reviews (v2, claude, semi-auto) — 34 runs (28 passed, 6 failed), 1 alert
test-generation (v1, claude, monitor) — 12 runs (11 passed, 1 failed), no alerts
classifier-en (v3, pipeline, semi-auto) — 847 runs (812 passed, 35 failed), 2 alerts
```

If there are alerts, list them briefly. If the user wants detail, suggest `/holdfast:review`.
