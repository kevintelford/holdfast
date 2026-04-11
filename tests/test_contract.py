"""Tests for contract loading and management."""

from pathlib import Path

import pytest

from holdfast import Contract


def test_load_contract(contract_dir: Path):
    contract = Contract.load(contract_dir)
    assert contract.name == "test-classifier"
    assert contract.version == 1
    assert "output_schema" in contract.frozen
    assert "prompt" in contract.evolvable


def test_get_evolvable(contract_dir: Path):
    contract = Contract.load(contract_dir)
    prompt = contract.get_evolvable("prompt")
    assert "classifier" in prompt.lower()


def test_get_evolvable_missing_key(contract_dir: Path):
    contract = Contract.load(contract_dir)
    with pytest.raises(KeyError, match="nonexistent"):
        contract.get_evolvable("nonexistent")


def test_get_frozen(contract_dir: Path):
    contract = Contract.load(contract_dir)
    guidelines = contract.get_frozen("guidelines")
    assert "Guidelines" in guidelines


def test_get_frozen_json(contract_dir: Path):
    contract = Contract.load(contract_dir)
    schema = contract.get_frozen_json("output_schema")
    assert schema["type"] == "object"
    assert "label" in schema["properties"]


def test_interface_notes(contract_dir: Path):
    contract = Contract.load(contract_dir)
    assert "downstream" in contract.interface_notes.lower()


def test_save_roundtrip(contract_dir: Path):
    contract = Contract.load(contract_dir)
    contract.version = 5
    contract.save()

    reloaded = Contract.load(contract_dir)
    assert reloaded.version == 5
    assert reloaded.name == "test-classifier"


def test_storage_dir_created(contract_dir: Path):
    contract = Contract.load(contract_dir)
    storage = contract.storage_dir()
    assert storage.exists()
    assert storage.name == ".holdfast"


def test_load_missing_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Contract.load(tmp_path / "nonexistent")


def test_default_evolution_mode(contract_dir: Path):
    contract = Contract.load(contract_dir)
    assert contract.evolution_mode == "monitor"


def test_evolution_mode_roundtrip(contract_dir: Path):
    contract = Contract.load(contract_dir)
    contract.evolution_mode = "semi-auto"
    contract.save()

    reloaded = Contract.load(contract_dir)
    assert reloaded.evolution_mode == "semi-auto"


def test_invalid_evolution_mode(contract_dir: Path):
    import yaml

    config_path = contract_dir / "contract.yaml"
    with open(config_path) as f:
        data = yaml.safe_load(f)
    data["evolution_mode"] = "yolo"
    with open(config_path, "w") as f:
        yaml.dump(data, f)

    with pytest.raises(ValueError, match="yolo"):
        Contract.load(contract_dir)


def test_load_detection_rules(contract_dir: Path):
    import yaml

    rules = [{"type": "variance", "field": "score", "max_stddev": 0.5}]
    with open(contract_dir / "detection.yaml", "w") as f:
        yaml.dump(rules, f)

    contract = Contract.load(contract_dir)
    loaded = contract.load_detection_rules()
    assert len(loaded) == 1
    assert loaded[0]["type"] == "variance"


def test_load_detection_rules_missing_file(contract_dir: Path):
    contract = Contract.load(contract_dir)
    assert contract.load_detection_rules() == []
