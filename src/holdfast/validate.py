"""Invariant validation for contracts.

Loads invariants.yaml and runs checks against contract state or proposed outputs.
Supports three invariant types:
- schema: JSON Schema validation
- contains: check that a field contains required values
- custom: run an external Python script
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml


@dataclass
class InvariantResult:
    """Result of a single invariant check."""

    invariant_type: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationResult:
    """Aggregate result of all invariant checks."""

    passed: bool
    results: list[InvariantResult]

    @property
    def failures(self) -> list[InvariantResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        total = len(self.results)
        failed = len(self.failures)
        if self.passed:
            return f"All {total} invariants passed."
        return f"{failed}/{total} invariants failed: " + "; ".join(r.description for r in self.failures)


def load_invariants(contract_root: Path) -> list[dict[str, Any]]:
    """Load invariants from invariants.yaml in the contract directory."""
    path = contract_root / "invariants.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, list) else []


def validate_output(contract_root: Path, output: Any) -> ValidationResult:
    """Validate an output against all invariants defined in the contract."""
    invariants = load_invariants(contract_root)
    if not invariants:
        return ValidationResult(passed=True, results=[])

    results = []
    for inv in invariants:
        inv_type = inv.get("type", "")
        description = inv.get("description", f"{inv_type} check")

        if inv_type == "schema":
            result = _check_schema(contract_root, inv, output)
        elif inv_type == "contains":
            result = _check_contains(inv, output)
        elif inv_type == "custom":
            result = _check_custom(contract_root, inv, output)
        else:
            result = InvariantResult(
                invariant_type=inv_type,
                description=description,
                passed=False,
                detail=f"Unknown invariant type: {inv_type}",
            )

        # Override description from invariant definition
        result.description = description
        results.append(result)

    all_passed = all(r.passed for r in results)
    return ValidationResult(passed=all_passed, results=results)


def _check_schema(contract_root: Path, inv: dict, output: Any) -> InvariantResult:
    """Validate output against a JSON Schema."""
    ref = inv.get("ref", "")
    schema_path = contract_root / ref

    if not schema_path.exists():
        return InvariantResult(
            invariant_type="schema",
            description="",
            passed=False,
            detail=f"Schema file not found: {schema_path}",
        )

    with open(schema_path) as f:
        schema = json.load(f)

    try:
        jsonschema.validate(output, schema)
        return InvariantResult(invariant_type="schema", description="", passed=True)
    except jsonschema.ValidationError as exc:
        return InvariantResult(
            invariant_type="schema",
            description="",
            passed=False,
            detail=str(exc.message),
        )


def _check_contains(inv: dict, output: Any) -> InvariantResult:
    """Check that a field in the output contains required values."""
    field_path = inv.get("field", "")
    required_values = inv.get("values", [])

    # Navigate the output by dot-separated field path
    value = output
    for part in field_path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return InvariantResult(
                invariant_type="contains",
                description="",
                passed=False,
                detail=f"Cannot navigate to '{field_path}': hit non-dict at '{part}'",
            )

    if value is None:
        return InvariantResult(
            invariant_type="contains",
            description="",
            passed=False,
            detail=f"Field '{field_path}' not found in output",
        )

    # Two modes:
    # - If the value is a list, check that all required values are present in it
    # - If the value is a scalar, check that it is one of the required values
    if isinstance(value, list):
        missing = [v for v in required_values if v not in value]
        if missing:
            return InvariantResult(
                invariant_type="contains",
                description="",
                passed=False,
                detail=f"Missing required values: {missing}",
            )
    else:
        if value not in required_values:
            return InvariantResult(
                invariant_type="contains",
                description="",
                passed=False,
                detail=f"Value '{value}' not in allowed values: {required_values}",
            )

    return InvariantResult(invariant_type="contains", description="", passed=True)


def _check_custom(contract_root: Path, inv: dict, output: Any) -> InvariantResult:
    """Run a custom validation script."""
    script = inv.get("script", "")
    script_path = contract_root / script

    if not script_path.exists():
        return InvariantResult(
            invariant_type="custom",
            description="",
            passed=False,
            detail=f"Custom script not found: {script_path}",
        )

    # Pass the output as JSON via stdin
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            input=json.dumps(output),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return InvariantResult(invariant_type="custom", description="", passed=True)
        return InvariantResult(
            invariant_type="custom",
            description="",
            passed=False,
            detail=result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}",
        )
    except subprocess.TimeoutExpired:
        return InvariantResult(
            invariant_type="custom",
            description="",
            passed=False,
            detail="Custom script timed out after 30s",
        )
