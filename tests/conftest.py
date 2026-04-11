"""Shared test fixtures for holdfast."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def contract_dir(tmp_path: Path) -> Path:
    """Create a minimal contract directory for testing."""
    root = tmp_path / "test-contract"
    root.mkdir()

    # Frozen: output schema
    frozen = root / "frozen"
    frozen.mkdir()
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["label", "confidence"],
    }
    (frozen / "output_schema.json").write_text(json.dumps(schema, indent=2))
    (frozen / "guidelines.md").write_text("# Guidelines\n\nClassify inputs into positive, negative, or neutral.\n")

    # Evolvable: prompt
    evolvable = root / "evolvable"
    evolvable.mkdir()
    (evolvable / "prompt.md").write_text(
        "You are a classifier. Given an input, return JSON with 'label' and 'confidence' fields.\n"
    )

    # Examples dir
    examples = evolvable / "examples"
    examples.mkdir()
    (examples / "example1.json").write_text(json.dumps({"input": "great product", "label": "positive", "confidence": 0.95}))

    # Contract YAML
    contract_data = {
        "name": "test-classifier",
        "version": 1,
        "frozen": {
            "output_schema": "frozen/output_schema.json",
            "guidelines": "frozen/guidelines.md",
            "interface_notes": "Returns {label, confidence} for downstream aggregator",
        },
        "evolvable": {
            "prompt": "evolvable/prompt.md",
            "examples": "evolvable/examples/",
        },
    }
    with open(root / "contract.yaml", "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)

    # Invariants
    invariants = [
        {
            "type": "schema",
            "ref": "frozen/output_schema.json",
            "description": "Output must conform to {label, confidence} schema",
        },
        {
            "type": "contains",
            "field": "label",
            "values": ["positive", "negative", "neutral"],
            "description": "Label must be one of the defined categories",
        },
    ]
    with open(root / "invariants.yaml", "w") as f:
        yaml.dump(invariants, f, default_flow_style=False)

    return root
