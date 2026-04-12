"""Integration test: full lifecycle through contract → evidence → evolve → validate → apply → rollback."""

import json
from pathlib import Path

import yaml

from holdfast import (
    Contract,
    apply_evolution,
    list_versions,
    log_run,
    propose_evolution,
    rollback,
    validate_output,
)
from holdfast.extract import extract_symbol


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


def test_source_ref_lifecycle(tmp_path: Path):
    """End-to-end: source ref → log → propose → apply → verify symbol changed in source file."""

    # Contract root is tmp_path itself — source files live inside it
    contract_root = tmp_path

    # 1. Create a Python source file with a prompt constant inside contract root
    src_dir = contract_root / "src"
    src_dir.mkdir()
    prompts_py = src_dir / "prompts.py"
    prompts_py.write_text(
        'OTHER_SETTING = 42\n'
        '\n'
        '\n'
        'class Prompts:\n'
        '    SYSTEM_PROMPT = "You are a classifier. Return JSON with label and confidence."\n'
        '    FALLBACK = "Default fallback response."\n'
    )

    # 2. Create contract with source ref
    frozen = contract_root / "frozen"
    frozen.mkdir()
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["label", "confidence"],
    }
    (frozen / "output_schema.json").write_text(json.dumps(schema))

    contract_data = {
        "name": "source-ref-test",
        "version": 1,
        "evolution_mode": "monitor",
        "frozen": {"output_schema": "frozen/output_schema.json"},
        "evolvable": {
            "system_prompt": {
                "path": "src/prompts.py",
                "symbol": "Prompts.SYSTEM_PROMPT",
            },
        },
    }
    with open(contract_root / "contract.yaml", "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)

    # Empty invariants (schema-only via frozen ref)
    (contract_root / "invariants.yaml").write_text("[]")

    # Evolvable dir needed for snapshot (can be empty)
    (contract_root / "evolvable").mkdir()

    # 3. Load and verify extraction
    contract = Contract.load(contract_root)
    prompt_value = contract.get_evolvable("system_prompt")
    assert "classifier" in prompt_value

    # 4. Log some evidence
    for i in range(6):
        log_run(
            contract=contract,
            output={"label": "positive", "confidence": 0.8 + i * 0.02},
            input_summary=f"test input {i}",
            passed=i < 4,
            notes="" if i < 4 else "missing handling for edge case",
        )

    # 5. Propose evolution (mock LLM returns source ref change)
    new_prompt_value = "You are a classifier. Return JSON with label and confidence. Handle edge cases carefully."

    def mock_llm(prompt: str) -> str:
        return json.dumps({
            "has_proposal": True,
            "rationale": "Adding edge case handling based on runs 5-6 failures.",
            "evidence_ids": ["run-005", "run-006"],
            "file_changes": {
                "src/prompts.py::Prompts.SYSTEM_PROMPT": new_prompt_value,
            },
            "diff_summary": "Added edge case handling instruction",
        })

    proposal = propose_evolution(contract=contract, llm=mock_llm, min_runs=5)
    assert proposal is not None

    # 6. Apply — this should write back to the Python source file
    apply_evolution(contract, proposal)
    assert contract.version == 2

    # 7. Verify the symbol was updated in the source file
    loc = extract_symbol(prompts_py, "Prompts.SYSTEM_PROMPT")
    assert "edge cases" in loc.value

    # Verify other code in the file is untouched
    source = prompts_py.read_text()
    assert "OTHER_SETTING = 42" in source
    assert 'FALLBACK = "Default fallback response."' in source

    # 8. Verify get_evolvable reads the new value
    reloaded = Contract.load(contract_root)
    assert "edge cases" in reloaded.get_evolvable("system_prompt")
