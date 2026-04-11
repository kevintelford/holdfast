---
name: holdfast
description: Review accumulated evidence from pipeline runs or interaction
  patterns and propose governed improvements. Use when the user says "evolve",
  "review evidence", "what's drifting", "improve the prompt", or when you
  notice repeated corrections, failures, or inconsistencies across interactions.
---

# Holdfast — Evidence Review & Evolution Proposals

You review evidence accumulated from pipeline runs or interaction patterns,
identify what's working and what's drifting, and propose bounded improvements.
The core rule: **frozen surfaces don't change. Evolvable surfaces improve
only with evidence and approval.**

## Step 1: Find and read evidence

Look for contracts in the project:

```bash
find . -name "contract.yaml" -not -path "*/.holdfast/*"
```

For each contract, read the evidence:

```bash
ls <contract_dir>/.holdfast/evidence/
```

Read the contract to understand what's frozen and what's evolvable:

```bash
cat <contract_dir>/contract.yaml
cat <contract_dir>/invariants.yaml
cat <contract_dir>/detection.yaml  # if it exists
```

You can also use the Python API to get a pre-built analysis prompt:

```python
from holdfast import Contract, build_evolution_prompt
contract = Contract.load("<contract_dir>")
prompt = build_evolution_prompt(contract)
```

Read and analyze that prompt — it contains all the evidence and context.

## Step 2: Summarize what you see

Be specific. Cite run IDs. Examples:

- "Across 12 runs, 3 failed with missing confidence fields — all on ambiguous inputs."
- "Scores range from 1 to 3 on identical inputs — the prompt doesn't handle edge case X."
- "All runs pass. No pattern to address."

If there are detection alerts, check those too:

```python
from holdfast import Contract, check_contract
contract = Contract.load("<contract_dir>")
alerts = check_contract(contract)
```

## Step 3: Propose or don't

If there's a clear pattern, propose a bounded edit:

- State exactly what changes in the evolvable surface
- State what does NOT change (frozen surfaces, invariants)
- Cite the evidence (run IDs, patterns)
- Explain why this change addresses the pattern

If there's no clear pattern, say so. Don't propose changes for the sake of it.

## Step 4: Wait for approval

Never apply without the user saying yes. Present the proposal and stop.

If approved, apply via:

```python
from holdfast import Contract, apply_evolution
from holdfast.evolve import EvolutionProposal

contract = Contract.load("<contract_dir>")
proposal = EvolutionProposal(
    diff="<summary>",
    rationale="<why>",
    evidence_ids=["run-001", "run-003"],
    file_changes={"evolvable/prompt.md": "<new content>"},
)
apply_evolution(contract, proposal)
```

Or just edit the evolvable file directly and bump the version if it's simpler.
