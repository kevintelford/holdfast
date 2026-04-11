"""Detection layer: pure Python pattern detection across runs.

No LLM needed. Evaluates detection rules (from detection.yaml) against
accumulated evidence and returns structured alerts.

Supports three rule types:
- variance: field values vary too much within a window
- drift: field average shifted between baseline and recent windows
- failure_rate: too many failed runs in a window
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Any

from .contract import Contract
from .store import list_evidence

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """A detection alert — something worth investigating."""

    rule_type: str
    description: str
    detail: str
    evidence_ids: list[str] = field(default_factory=list)


def check_contract(contract: Contract) -> list[Alert]:
    """Run all detection rules against a contract's evidence.

    Returns a list of alerts for any rules that triggered.
    """
    rules = contract.load_detection_rules()
    if not rules:
        return []

    storage = contract.storage_dir()
    runs = list_evidence(storage, contract_name=contract.name)

    if not runs:
        return []

    alerts = []
    for rule in rules:
        rule_type = rule.get("type", "")
        description = rule.get("description", f"{rule_type} check")

        if rule_type == "variance":
            alert = _check_variance(rule, runs)
        elif rule_type == "drift":
            alert = _check_drift(rule, runs)
        elif rule_type == "failure_rate":
            alert = _check_failure_rate(rule, runs)
        else:
            logger.warning("Unknown detection rule type: %s", rule_type)
            continue

        if alert:
            alert.description = description
            alerts.append(alert)

    return alerts


def _extract_field(run: dict[str, Any], field_path: str) -> Any:
    """Extract a value from a run's output by dot-separated field path."""
    value = run.get("output", {})
    for part in field_path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _to_float(value: Any) -> float | None:
    """Try to convert a value to float for numeric analysis."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_variance(rule: dict, runs: list[dict]) -> Alert | None:
    """Check if a field's values vary too much within a window."""
    field_path = rule.get("field", "")
    max_stddev = rule.get("max_stddev", 1.0)
    window = rule.get("window", len(runs))

    recent = runs[-window:]
    values = []
    ids = []
    for run in recent:
        v = _to_float(_extract_field(run, field_path))
        if v is not None:
            values.append(v)
            ids.append(run["id"])

    if len(values) < 2:
        return None

    stddev = statistics.stdev(values)
    if stddev <= max_stddev:
        return None

    return Alert(
        rule_type="variance",
        description="",
        detail=(
            f"Field '{field_path}' stddev={stddev:.2f} exceeds max={max_stddev} "
            f"across {len(values)} runs (values: {values})"
        ),
        evidence_ids=ids,
    )


def _check_drift(rule: dict, runs: list[dict]) -> Alert | None:
    """Check if a field's average shifted between baseline and recent windows."""
    field_path = rule.get("field", "")
    baseline_window = rule.get("baseline_window", 20)
    recent_window = rule.get("recent_window", 10)
    max_shift = rule.get("max_shift", 1.0)

    if len(runs) < baseline_window + recent_window:
        return None

    baseline_runs = runs[:baseline_window]
    recent_runs = runs[-recent_window:]

    baseline_values = [v for r in baseline_runs if (v := _to_float(_extract_field(r, field_path))) is not None]
    recent_values = [v for r in recent_runs if (v := _to_float(_extract_field(r, field_path))) is not None]

    if not baseline_values or not recent_values:
        return None

    baseline_mean = statistics.mean(baseline_values)
    recent_mean = statistics.mean(recent_values)
    shift = abs(recent_mean - baseline_mean)

    if shift <= max_shift:
        return None

    recent_ids = [r["id"] for r in recent_runs]
    return Alert(
        rule_type="drift",
        description="",
        detail=(
            f"Field '{field_path}' drifted: baseline_mean={baseline_mean:.2f}, "
            f"recent_mean={recent_mean:.2f}, shift={shift:.2f} exceeds max={max_shift}"
        ),
        evidence_ids=recent_ids,
    )


def _check_failure_rate(rule: dict, runs: list[dict]) -> Alert | None:
    """Check if too many runs failed in a window."""
    max_rate = rule.get("max_rate", 0.1)
    window = rule.get("window", len(runs))

    recent = runs[-window:]
    if not recent:
        return None

    failed = [r for r in recent if not r.get("passed")]
    rate = len(failed) / len(recent)

    if rate <= max_rate:
        return None

    return Alert(
        rule_type="failure_rate",
        description="",
        detail=f"Failure rate={rate:.1%} ({len(failed)}/{len(recent)}) exceeds max={max_rate:.1%}",
        evidence_ids=[r["id"] for r in failed],
    )
