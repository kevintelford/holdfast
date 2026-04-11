"""Integration test: full lifecycle through contract → evidence → evolve → validate → apply → rollback."""

import json
from pathlib import Path

from holdfast import (
    Contract,
    apply_evolution,
    list_versions,
    log_run,
    propose_evolution,
    rollback,
    validate_output,
)


def test_full_lifecycle(contract_dir: Path):
    """End-to-end: load → log varied runs → propose → validate → apply → verify → rollback."""

    # 1. Load contract
    contract = Contract.load(contract_dir)
    assert contract.version == 1
    original_prompt = contract.get_evolvable("prompt")

    # 2. Log varied evidence — simulating real-world usage over time
    runs = [
        # Day 1: simple inputs, all pass
        {"output": {"label": "positive", "confidence": 0.93}, "summary": "happy customer email", "passed": True},
        {"output": {"label": "negative", "confidence": 0.85}, "summary": "refund request", "passed": True},
        # Day 2: more complex inputs
        {"output": {"label": "neutral", "confidence": 0.60}, "summary": "product comparison blog", "passed": True},
        {"output": {"label": "positive", "confidence": 0.78}, "summary": "casual mention in podcast transcript", "passed": True},
        # Day 3: edge cases start failing
        {"output": {"label": "positive"}, "summary": "sarcastic tweet about the product", "passed": False, "notes": "missing confidence, sarcasm misread"},
        {"output": {"label": "negative"}, "summary": "backhanded compliment in review", "passed": False, "notes": "missing confidence on ambiguous tone"},
        # Day 4: more data
        {"output": {"label": "neutral", "confidence": 0.52}, "summary": "news article mentioning product", "passed": True},
        {"output": {"label": "negative"}, "summary": "ironic positive review", "passed": False, "notes": "missing confidence, tone misclassified"},
    ]

    for run in runs:
        log_run(
            contract=contract,
            output=run["output"],
            input_summary=run["summary"],
            passed=run["passed"],
            notes=run.get("notes", ""),
        )

    # 3. Validate a good output against invariants
    good_output = {"label": "positive", "confidence": 0.87}
    validation = validate_output(contract_dir, good_output)
    assert validation.passed

    # Validate a bad output
    bad_output = {"label": "positive"}  # missing confidence
    validation = validate_output(contract_dir, bad_output)
    assert not validation.passed

    # 4. Propose an evolution (mock LLM callable)
    new_prompt = (
        "You are a classifier. Given an input, return JSON with 'label' and 'confidence' fields.\n"
        "Always include a 'confidence' score between 0.0 and 1.0.\n"
        "For ambiguous inputs (sarcasm, irony, mixed signals), use lower confidence "
        "but still classify and always include the field.\n"
    )

    def mock_llm(prompt: str) -> str:
        return json.dumps({
            "has_proposal": True,
            "rationale": "Runs 5, 6, 8 failed — all missing confidence on ambiguous tone inputs. "
                         "Adding explicit instruction for handling sarcasm and irony.",
            "evidence_ids": ["run-005", "run-006", "run-008"],
            "file_changes": {"evolvable/prompt.md": new_prompt},
            "diff_summary": "Added handling for ambiguous/sarcastic inputs",
        })

    proposal = propose_evolution(contract=contract, llm=mock_llm, min_runs=5)
    assert proposal is not None
    assert len(proposal.evidence_ids) == 3

    # 5. Apply the evolution
    apply_evolution(contract, proposal)
    assert contract.version == 2
    assert "ambiguous" in contract.get_evolvable("prompt").lower()

    # 6. Verify the evolved prompt still produces valid output against invariants
    evolved_good_output = {"label": "neutral", "confidence": 0.45}
    validation = validate_output(contract_dir, evolved_good_output)
    assert validation.passed

    # 7. Version history
    versions = list_versions(contract)
    assert 1 in versions  # original was snapshotted

    # 8. Rollback
    rollback(contract, to_version=1)
    assert contract.version == 1
    assert contract.get_evolvable("prompt") == original_prompt
