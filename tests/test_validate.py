"""Tests for invariant validation."""

from pathlib import Path

from holdfast.validate import load_invariants, validate_output


def test_load_invariants(contract_dir: Path):
    invariants = load_invariants(contract_dir)
    assert len(invariants) == 2
    assert invariants[0]["type"] == "schema"
    assert invariants[1]["type"] == "contains"


def test_load_invariants_missing_file(tmp_path: Path):
    invariants = load_invariants(tmp_path)
    assert invariants == []


def test_validate_schema_pass(contract_dir: Path):
    output = {"label": "positive", "confidence": 0.85}
    result = validate_output(contract_dir, output)
    assert result.passed


def test_validate_schema_fail_missing_field(contract_dir: Path):
    output = {"label": "positive"}  # missing confidence
    result = validate_output(contract_dir, output)
    assert not result.passed
    assert any("schema" in r.invariant_type for r in result.failures)


def test_validate_schema_fail_wrong_type(contract_dir: Path):
    output = {"label": "positive", "confidence": "high"}  # wrong type
    result = validate_output(contract_dir, output)
    assert not result.passed


def test_validate_schema_fail_enum(contract_dir: Path):
    output = {"label": "unknown", "confidence": 0.5}  # invalid enum
    result = validate_output(contract_dir, output)
    assert not result.passed


def test_validate_contains_pass(contract_dir: Path):
    output = {"label": "positive", "confidence": 0.9}
    result = validate_output(contract_dir, output)
    assert result.passed


def test_validate_contains_fail(contract_dir: Path):
    output = {"label": "maybe", "confidence": 0.5}
    result = validate_output(contract_dir, output)
    assert not result.passed


def test_validate_summary(contract_dir: Path):
    output = {"label": "positive", "confidence": 0.85}
    result = validate_output(contract_dir, output)
    assert "passed" in result.summary().lower()

    bad_output = {"label": "invalid"}
    result = validate_output(contract_dir, bad_output)
    assert "failed" in result.summary().lower()


def test_validate_custom_script(contract_dir: Path, tmp_path: Path):
    """Test custom invariant with a real script."""
    import yaml

    # Write a custom validation script
    script_dir = contract_dir / "invariants"
    script_dir.mkdir()
    script = script_dir / "check_confidence.py"
    script.write_text(
        'import json, sys\n'
        'data = json.loads(sys.stdin.read())\n'
        'c = data.get("confidence", -1)\n'
        'if not (0 <= c <= 1): sys.exit(1)\n'
    )

    # Add custom invariant
    invariants = load_invariants(contract_dir)
    invariants.append({
        "type": "custom",
        "script": "invariants/check_confidence.py",
        "description": "Confidence must be 0-1",
    })
    with open(contract_dir / "invariants.yaml", "w") as f:
        yaml.dump(invariants, f)

    # Should pass
    result = validate_output(contract_dir, {"label": "positive", "confidence": 0.5})
    assert result.passed

    # Should fail
    result = validate_output(contract_dir, {"label": "positive", "confidence": 1.5})
    assert not result.passed


def test_custom_script_path_traversal(contract_dir: Path):
    """Custom script paths that escape the contract root should fail, not execute."""
    import yaml

    invariants = [
        {
            "type": "custom",
            "script": "../../etc/malicious.py",
            "description": "Should be rejected",
        },
    ]
    with open(contract_dir / "invariants.yaml", "w") as f:
        yaml.dump(invariants, f)

    result = validate_output(contract_dir, {"label": "positive", "confidence": 0.5})
    assert not result.passed
    assert "escapes contract root" in result.results[0].detail


def test_schema_ref_path_traversal(contract_dir: Path):
    """Schema ref paths that escape the contract root should fail."""
    import yaml

    invariants = [
        {
            "type": "schema",
            "ref": "../../../etc/shadow",
            "description": "Should be rejected",
        },
    ]
    with open(contract_dir / "invariants.yaml", "w") as f:
        yaml.dump(invariants, f)

    result = validate_output(contract_dir, {"label": "positive", "confidence": 0.5})
    assert not result.passed
    assert "escapes contract root" in result.results[0].detail
