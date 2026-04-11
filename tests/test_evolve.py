"""Tests for the evolution engine — mocked LLM calls with varied evidence."""

import json
from pathlib import Path

from holdfast import Contract, log_run, propose_evolution
from holdfast.evolve import build_evolution_prompt


def _log_varied_runs(contract: Contract) -> None:
    """Log a realistic set of varied runs — different inputs, different outcomes.

    This simulates real-world usage where data and patterns change between runs.
    The evolution engine should detect the repeated failure pattern (missing
    confidence on multi-label inputs) across varied successful and failing runs.
    """
    varied_runs = [
        # Straightforward cases — these pass fine
        {"output": {"label": "positive", "confidence": 0.95}, "summary": "product review: 5 stars", "passed": True},
        {"output": {"label": "negative", "confidence": 0.88}, "summary": "customer complaint about shipping", "passed": True},
        {"output": {"label": "neutral", "confidence": 0.72}, "summary": "factual news article", "passed": True},
        {"output": {"label": "positive", "confidence": 0.91}, "summary": "enthusiastic recommendation", "passed": True},
        # Edge case failures — the pattern we want the evolution engine to catch
        {"output": {"label": "positive"}, "summary": "mixed review with sarcasm", "passed": False, "notes": "missing confidence on ambiguous input"},
        {"output": {"label": "neutral"}, "summary": "comparative product review", "passed": False, "notes": "missing confidence on multi-aspect input"},
        # More passing runs with different characteristics
        {"output": {"label": "negative", "confidence": 0.67}, "summary": "subtle disappointment in email", "passed": True},
        {"output": {"label": "positive", "confidence": 0.99}, "summary": "short tweet: love it", "passed": True},
        # Another failure with the same pattern
        {"output": {"label": "negative"}, "summary": "review with mixed positive and negative", "passed": False, "notes": "missing confidence on multi-label input"},
        # One more pass to round it out
        {"output": {"label": "neutral", "confidence": 0.55}, "summary": "technical documentation excerpt", "passed": True},
    ]

    for run in varied_runs:
        log_run(
            contract=contract,
            output=run["output"],
            input_summary=run["summary"],
            passed=run["passed"],
            notes=run.get("notes", ""),
        )


def _make_mock_llm(response_data: dict) -> callable:
    """Create a mock LLM callable that returns a JSON string."""
    def mock_llm(prompt: str) -> str:
        return json.dumps(response_data)
    return mock_llm


def test_propose_evolution_not_enough_runs(contract_dir: Path):
    """Should return None if fewer than min_runs."""
    contract = Contract.load(contract_dir)
    log_run(contract=contract, output={"label": "positive", "confidence": 0.9})

    result = propose_evolution(contract=contract, llm=lambda p: "", min_runs=5)
    assert result is None


def test_propose_evolution_with_pattern(contract_dir: Path):
    """Should detect the missing-confidence pattern and propose a fix."""
    contract = Contract.load(contract_dir)
    _log_varied_runs(contract)

    mock_llm = _make_mock_llm({
        "has_proposal": True,
        "rationale": "Runs run-005, run-006, run-009 all failed with missing confidence field. "
                     "These failures occur specifically on ambiguous or multi-aspect inputs where "
                     "the model seems uncertain. Adding explicit instruction to always include "
                     "confidence even when uncertain.",
        "evidence_ids": ["run-005", "run-006", "run-009"],
        "file_changes": {
            "evolvable/prompt.md": (
                "You are a classifier. Given an input, return JSON with 'label' and 'confidence' fields.\n"
                "Always include a 'confidence' score between 0.0 and 1.0, even when the input is ambiguous "
                "or contains mixed signals. For uncertain cases, use a lower confidence value.\n"
            ),
        },
        "diff_summary": "Added instruction to always include confidence, especially for ambiguous inputs",
    })

    proposal = propose_evolution(contract=contract, llm=mock_llm, min_runs=5)

    assert proposal is not None
    assert "confidence" in proposal.rationale.lower()
    assert len(proposal.evidence_ids) == 3
    assert "evolvable/prompt.md" in proposal.file_changes


def test_propose_evolution_no_pattern(contract_dir: Path):
    """LLM sees no clear pattern — should return None."""
    contract = Contract.load(contract_dir)

    # Log runs that all pass — no pattern to fix
    for i in range(6):
        log_run(
            contract=contract,
            output={"label": "positive", "confidence": 0.8 + i * 0.02},
            input_summary=f"varied input {i}",
            passed=True,
        )

    mock_llm = _make_mock_llm({
        "has_proposal": False,
        "rationale": "All runs passed successfully. No failure pattern detected.",
        "evidence_ids": [],
        "file_changes": {},
        "diff_summary": "",
    })

    proposal = propose_evolution(contract=contract, llm=mock_llm, min_runs=5)
    assert proposal is None


def test_propose_evolution_prompt_includes_evidence(contract_dir: Path):
    """Verify the LLM prompt includes both passing and failing evidence."""
    contract = Contract.load(contract_dir)
    _log_varied_runs(contract)

    captured_prompt = None

    def capturing_llm(prompt: str) -> str:
        nonlocal captured_prompt
        captured_prompt = prompt
        return json.dumps({
            "has_proposal": False,
            "rationale": "no pattern",
            "evidence_ids": [],
            "file_changes": {},
            "diff_summary": "",
        })

    propose_evolution(contract=contract, llm=capturing_llm, min_runs=5)

    assert captured_prompt is not None
    # Should include both passing and failing runs
    assert "PASS" in captured_prompt
    assert "FAIL" in captured_prompt
    # Should include the frozen content as context
    assert "DO NOT propose changes" in captured_prompt
    # Should include current evolvable content
    assert "classifier" in captured_prompt.lower()


def test_build_evolution_prompt_standalone(contract_dir: Path):
    """build_evolution_prompt can be used without propose_evolution."""
    contract = Contract.load(contract_dir)
    _log_varied_runs(contract)

    prompt = build_evolution_prompt(contract)
    assert "PASS" in prompt
    assert "FAIL" in prompt
    assert contract.name in prompt
