---
description: Propose and apply a holdfast evolution based on evidence. Use when
  the user says "evolve", "propose an evolution", "improve the prompt",
  "improve the approach", or after /holdfast:review surfaces actionable patterns.
---

# Holdfast — Evolve

You propose bounded changes to evolvable surfaces based on accumulated
evidence, then apply them with user approval.

**Core rule:** frozen surfaces don't change. Evolvable surfaces improve
only with evidence and approval.

---

## Propose

Read the evidence (or use findings from a recent `/holdfast:review`).

If there's a clear pattern, propose a bounded edit to the evolvable surface:

- State exactly what changes
- State what does NOT change (frozen surfaces, invariants)
- Cite the evidence (run IDs, patterns)
- Explain why this change addresses the pattern

If there's no clear pattern, say so. Don't propose changes for the sake of it.

### Pipeline mode — build the prompt

```python
from holdfast import Contract, build_evolution_prompt
contract = Contract.load("{contract_dir}")
prompt = build_evolution_prompt(contract)
```

Read and analyze the prompt — it contains all evidence and context.

### Claude mode — read directly

Read the evolvable files, the frozen standards, and the evidence. Formulate
your proposal based on what the evidence shows.

---

## Wait for approval

Never apply without the user saying yes. Present the proposal and stop.
In `monitor` mode, don't even propose — just report findings.

---

## Apply

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
