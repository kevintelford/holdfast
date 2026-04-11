"""Tests for the detection layer — pure Python pattern detection across runs."""

from pathlib import Path

import yaml

from holdfast import Contract, check_contract, log_run


def _add_detection_rules(contract_dir: Path, rules: list[dict]) -> None:
    """Write detection rules to the contract directory."""
    with open(contract_dir / "detection.yaml", "w") as f:
        yaml.dump(rules, f)


def _log_runs_with_scores(contract: Contract, scores: list[str], passed: bool = True) -> None:
    """Log runs with varying maturity scores — simulating real-world variation."""
    for i, score in enumerate(scores):
        log_run(
            contract=contract,
            output={"label": "positive", "confidence": 0.9, "score": score},
            input_summary=f"varied input batch item {i}",
            passed=passed,
        )


# --- Variance detection ---


def test_variance_triggers(contract_dir: Path):
    """High variance in scores should trigger an alert."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "variance", "field": "score", "max_stddev": 0.5, "window": 10, "description": "Score too variable"},
    ])
    # Scores: 1, 3, 1, 3, 1 — stddev ≈ 1.0
    _log_runs_with_scores(contract, ["1", "3", "1", "3", "1"])

    alerts = check_contract(contract)
    assert len(alerts) == 1
    assert alerts[0].rule_type == "variance"
    assert "stddev" in alerts[0].detail


def test_variance_no_trigger(contract_dir: Path):
    """Consistent scores should not trigger."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "variance", "field": "score", "max_stddev": 0.5, "window": 10, "description": "Score too variable"},
    ])
    # All scores are 3 — stddev = 0
    _log_runs_with_scores(contract, ["3", "3", "3", "3", "3"])

    alerts = check_contract(contract)
    assert len(alerts) == 0


def test_variance_window_limits_scope(contract_dir: Path):
    """Variance should only consider the most recent N runs."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "variance", "field": "score", "max_stddev": 0.5, "window": 3, "description": "Score too variable"},
    ])
    # Old runs are variable, recent 3 are stable
    _log_runs_with_scores(contract, ["1", "5", "1", "3", "3", "3"])

    alerts = check_contract(contract)
    assert len(alerts) == 0


# --- Drift detection ---


def test_drift_triggers(contract_dir: Path):
    """Average score shift between baseline and recent should trigger."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "drift", "field": "score", "baseline_window": 5, "recent_window": 5, "max_shift": 0.5, "description": "Score drifted"},
    ])
    # Baseline: all 3s, Recent: all 1s — shift = 2.0
    _log_runs_with_scores(contract, ["3", "3", "3", "3", "3", "1", "1", "1", "1", "1"])

    alerts = check_contract(contract)
    assert len(alerts) == 1
    assert alerts[0].rule_type == "drift"
    assert "shift" in alerts[0].detail


def test_drift_no_trigger(contract_dir: Path):
    """Stable averages should not trigger drift."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "drift", "field": "score", "baseline_window": 5, "recent_window": 5, "max_shift": 0.5, "description": "Score drifted"},
    ])
    # All 3s — no drift
    _log_runs_with_scores(contract, ["3", "3", "3", "3", "3", "3", "3", "3", "3", "3"])

    alerts = check_contract(contract)
    assert len(alerts) == 0


def test_drift_not_enough_data(contract_dir: Path):
    """Drift check should skip if not enough data for both windows."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "drift", "field": "score", "baseline_window": 20, "recent_window": 10, "max_shift": 0.5, "description": "Score drifted"},
    ])
    _log_runs_with_scores(contract, ["1", "5"])  # Only 2 runs

    alerts = check_contract(contract)
    assert len(alerts) == 0


# --- Failure rate detection ---


def test_failure_rate_triggers(contract_dir: Path):
    """High failure rate should trigger."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "failure_rate", "max_rate": 0.1, "window": 10, "description": "Too many failures"},
    ])
    # 3 failures out of 5 = 60%
    for i in range(5):
        log_run(
            contract=contract,
            output={"label": "positive", "confidence": 0.9},
            input_summary=f"item {i}",
            passed=(i < 2),  # first 2 pass, last 3 fail
        )

    alerts = check_contract(contract)
    assert len(alerts) == 1
    assert alerts[0].rule_type == "failure_rate"
    assert "60" in alerts[0].detail  # 60%


def test_failure_rate_no_trigger(contract_dir: Path):
    """Low failure rate should not trigger."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "failure_rate", "max_rate": 0.2, "window": 10, "description": "Too many failures"},
    ])
    # 1 failure out of 10 = 10%
    for i in range(10):
        log_run(
            contract=contract,
            output={"label": "positive", "confidence": 0.9},
            input_summary=f"item {i}",
            passed=(i != 5),
        )

    alerts = check_contract(contract)
    assert len(alerts) == 0


# --- Multiple rules ---


def test_multiple_rules(contract_dir: Path):
    """Multiple rules can fire independently."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "variance", "field": "score", "max_stddev": 0.3, "window": 10, "description": "Variance alert"},
        {"type": "failure_rate", "max_rate": 0.05, "window": 10, "description": "Failure alert"},
    ])
    # Variable scores AND failures
    for i, (score, passed) in enumerate([("1", True), ("3", True), ("1", False), ("3", True), ("1", False)]):
        log_run(
            contract=contract,
            output={"label": "positive", "confidence": 0.9, "score": score},
            input_summary=f"item {i}",
            passed=passed,
        )

    alerts = check_contract(contract)
    types = {a.rule_type for a in alerts}
    assert "variance" in types
    assert "failure_rate" in types


# --- No rules ---


def test_no_detection_rules(contract_dir: Path):
    """Contract without detection.yaml should return no alerts."""
    contract = Contract.load(contract_dir)
    log_run(contract=contract, output={"label": "positive", "confidence": 0.9})

    alerts = check_contract(contract)
    assert alerts == []


# --- No evidence ---


def test_no_evidence(contract_dir: Path):
    """No evidence should return no alerts even with rules."""
    contract = Contract.load(contract_dir)
    _add_detection_rules(contract_dir, [
        {"type": "failure_rate", "max_rate": 0.1, "window": 10, "description": "Failures"},
    ])

    alerts = check_contract(contract)
    assert alerts == []
