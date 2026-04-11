"""Tests for evidence collection — log_run() and @track decorator."""

from pathlib import Path

from holdfast import Contract, log_run, track
from holdfast.store import list_evidence


def test_log_run_basic(contract_dir: Path):
    contract = Contract.load(contract_dir)
    run_id = log_run(
        contract=contract,
        output={"label": "positive", "confidence": 0.92},
        input_summary="test input 1",
        passed=True,
    )
    assert run_id == "run-001"

    # Verify evidence file exists
    evidence = list_evidence(contract.storage_dir(), contract_name="test-classifier")
    assert len(evidence) == 1
    assert evidence[0]["passed"] is True
    assert evidence[0]["input_summary"] == "test input 1"


def test_log_run_sequential_ids(contract_dir: Path):
    contract = Contract.load(contract_dir)
    id1 = log_run(contract=contract, output={"label": "positive", "confidence": 0.8})
    id2 = log_run(contract=contract, output={"label": "negative", "confidence": 0.6})
    id3 = log_run(contract=contract, output={"label": "neutral", "confidence": 0.5})
    assert id1 == "run-001"
    assert id2 == "run-002"
    assert id3 == "run-003"


def test_log_run_with_failure(contract_dir: Path):
    contract = Contract.load(contract_dir)
    log_run(
        contract=contract,
        output={"label": "unknown"},
        input_summary="ambiguous input",
        passed=False,
        notes="missing confidence field",
    )

    evidence = list_evidence(contract.storage_dir())
    assert evidence[0]["passed"] is False
    assert "confidence" in evidence[0]["notes"]


def test_log_run_varied_data(contract_dir: Path):
    """Evidence should reflect real-world variation — different inputs, different outcomes."""
    contract = Contract.load(contract_dir)

    # Simulate varied real-world runs
    runs = [
        {"output": {"label": "positive", "confidence": 0.95}, "summary": "glowing review", "passed": True},
        {"output": {"label": "negative", "confidence": 0.88}, "summary": "complaint email", "passed": True},
        {"output": {"label": "neutral", "confidence": 0.51}, "summary": "factual statement", "passed": True},
        {"output": {"label": "positive", "confidence": 0.3}, "summary": "sarcastic comment", "passed": False, "notes": "misclassified sarcasm as positive"},
        {"output": {"error": "timeout"}, "summary": "very long input", "passed": False, "notes": "LLM timeout on large input"},
    ]

    for run in runs:
        log_run(
            contract=contract,
            output=run["output"],
            input_summary=run["summary"],
            passed=run["passed"],
            notes=run.get("notes", ""),
        )

    evidence = list_evidence(contract.storage_dir())
    assert len(evidence) == 5
    assert sum(1 for e in evidence if e["passed"]) == 3
    assert sum(1 for e in evidence if not e["passed"]) == 2


def test_track_decorator(contract_dir: Path):
    contract = Contract.load(contract_dir)

    @track(contract)
    def classify(item: dict) -> dict:
        return {"label": "positive", "confidence": 0.9}

    result = classify({"text": "great"})
    assert result["label"] == "positive"

    evidence = list_evidence(contract.storage_dir())
    assert len(evidence) == 1
    assert evidence[0]["passed"] is True


def test_track_decorator_exception(contract_dir: Path):
    contract = Contract.load(contract_dir)

    @track(contract)
    def failing_classify(item: dict) -> dict:
        raise ValueError("something broke")

    try:
        failing_classify({"text": "test"})
    except ValueError:
        pass

    evidence = list_evidence(contract.storage_dir())
    assert len(evidence) == 1
    assert evidence[0]["passed"] is False
    assert "ValueError" in evidence[0]["notes"]


def test_log_run_non_serializable_output(contract_dir: Path):
    """Non-JSON-serializable output should be converted to string, not crash."""
    contract = Contract.load(contract_dir)
    log_run(
        contract=contract,
        output=object(),  # not serializable
        input_summary="weird output",
        passed=False,
    )

    evidence = list_evidence(contract.storage_dir())
    assert len(evidence) == 1
    assert isinstance(evidence[0]["output"], str)
