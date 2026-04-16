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


def test_validate_missing_name(tmp_path: Path):
    """contract.yaml without 'name' should fail validation."""
    import yaml

    root = tmp_path / "bad"
    root.mkdir()
    with open(root / "contract.yaml", "w") as f:
        yaml.dump({"version": 1}, f)

    with pytest.raises(ValueError, match="missing required field 'name'"):
        Contract.load(root)


def test_validate_bad_evolvable_ref(tmp_path: Path):
    """Evolvable ref that's neither string nor dict should fail."""
    import yaml

    root = tmp_path / "bad"
    root.mkdir()
    with open(root / "contract.yaml", "w") as f:
        yaml.dump({"name": "test", "evolvable": {"prompt": 42}}, f)

    with pytest.raises(ValueError, match="must be a string path or a dict"):
        Contract.load(root)


def test_validate_source_ref_missing_symbol(tmp_path: Path):
    """Source ref dict without 'symbol' should fail."""
    import yaml

    root = tmp_path / "bad"
    root.mkdir()
    with open(root / "contract.yaml", "w") as f:
        yaml.dump({"name": "test", "evolvable": {"prompt": {"path": "foo.py"}}}, f)

    with pytest.raises(ValueError, match="must have a 'symbol' field"):
        Contract.load(root)


def test_path_boundary_enforcement(contract_dir: Path):
    """Refs that escape the path boundary via ../ should be rejected."""
    contract = Contract.load(contract_dir)
    with pytest.raises(ValueError, match="escapes path boundary"):
        contract.resolve_ref_path("../../etc/passwd")


def test_project_root_widens_boundary(tmp_path: Path):
    """project_root allows source refs outside the contract dir but inside the project."""
    import yaml

    # Project structure: project_root/src/prompts.py + project_root/contracts/my/contract.yaml
    project = tmp_path / "project"
    project.mkdir()
    src = project / "src"
    src.mkdir()
    prompts_py = src / "prompts.py"
    prompts_py.write_text('PROMPT = "hello"\n')

    contract_root = project / "contracts" / "my"
    contract_root.mkdir(parents=True)
    (contract_root / "frozen").mkdir()
    (contract_root / "evolvable").mkdir()

    contract_data = {
        "name": "test",
        "version": 1,
        "project_root": "../..",
        "evolvable": {
            "prompt": {"path": "src/prompts.py", "symbol": "PROMPT"},
        },
    }
    with open(contract_root / "contract.yaml", "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)
    (contract_root / "invariants.yaml").write_text("[]")

    contract = Contract.load(contract_root)
    assert contract.project_root == project
    assert contract.path_boundary == project

    # Source ref should resolve within project root
    resolved = contract.resolve_ref_path("src/prompts.py")
    assert resolved == prompts_py

    # Still can't escape project root
    with pytest.raises(ValueError, match="escapes path boundary"):
        contract.resolve_ref_path("../../etc/passwd")


def test_project_root_must_be_ancestor(tmp_path: Path):
    """project_root that isn't an ancestor of contract root should fail."""
    import yaml

    contract_root = tmp_path / "contracts" / "my"
    contract_root.mkdir(parents=True)

    contract_data = {
        "name": "test",
        "version": 1,
        "project_root": "../sibling",  # not an ancestor
    }
    with open(contract_root / "contract.yaml", "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)

    with pytest.raises(ValueError, match="not an ancestor"):
        Contract.load(contract_root)


def test_project_root_default_is_contract_root(contract_dir: Path):
    """Without project_root, path boundary defaults to contract root."""
    contract = Contract.load(contract_dir)
    assert contract.project_root is None
    assert contract.path_boundary == contract.root


def test_path_traversal_with_project_root(tmp_path: Path):
    """Various attempts to escape the project_root boundary."""
    import yaml

    project = tmp_path / "project"
    project.mkdir()
    contract_root = project / "contracts" / "my"
    contract_root.mkdir(parents=True)

    contract_data = {
        "name": "test",
        "version": 1,
        "project_root": "../..",
    }
    with open(contract_root / "contract.yaml", "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)
    (contract_root / "invariants.yaml").write_text("[]")

    contract = Contract.load(contract_root)

    # Direct traversal
    with pytest.raises(ValueError, match="escapes path boundary"):
        contract.resolve_ref_path("../../../etc/passwd")

    # Traversal via intermediate dirs
    with pytest.raises(ValueError, match="escapes path boundary"):
        contract.resolve_ref_path("src/../../../../../../etc/shadow")

    # Absolute path injection
    with pytest.raises(ValueError, match="escapes path boundary"):
        contract.resolve_ref_path("/etc/passwd")

    # Null byte (should fail at filesystem level or path resolution)
    try:
        contract.resolve_ref_path("src/\x00/etc/passwd")
    except (ValueError, OSError):
        pass  # Either our check or OS rejects it — both fine

    # Double-encoded traversal stays literal — doesn't escape (correct behavior)
    # ..%2f is not decoded by Path, so it resolves inside the boundary
    resolved = contract.resolve_ref_path("..%2f..%2f..%2fetc/passwd")
    assert resolved.is_relative_to(contract.path_boundary)


def test_symlink_escape_project_root(tmp_path: Path):
    """Symlinks that resolve outside project_root should be caught."""
    import os

    import yaml  # noqa: I001

    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()

    # Create a symlink inside project that points outside
    os.symlink("/etc", project / "src" / "escape_link")

    contract_root = project / "contracts" / "my"
    contract_root.mkdir(parents=True)

    contract_data = {
        "name": "test",
        "version": 1,
        "project_root": "../..",
    }
    with open(contract_root / "contract.yaml", "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)
    (contract_root / "invariants.yaml").write_text("[]")

    contract = Contract.load(contract_root)

    # Symlink resolves to /etc/passwd which is outside project root
    with pytest.raises(ValueError, match="escapes path boundary"):
        contract.resolve_ref_path("src/escape_link/passwd")


def test_project_root_get_evolvable(tmp_path: Path):
    """get_evolvable should work with source refs resolved via project_root."""
    import yaml

    project = tmp_path / "project"
    project.mkdir()
    src = project / "src"
    src.mkdir()
    (src / "prompts.py").write_text('SYSTEM = "You are helpful."\n')

    contract_root = project / "holdfast" / "contracts" / "test"
    contract_root.mkdir(parents=True)
    (contract_root / "frozen").mkdir()
    (contract_root / "evolvable").mkdir()
    (contract_root / "invariants.yaml").write_text("[]")

    contract_data = {
        "name": "test",
        "version": 1,
        "project_root": "../../..",
        "evolvable": {
            "system": {"path": "src/prompts.py", "symbol": "SYSTEM"},
        },
    }
    with open(contract_root / "contract.yaml", "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)

    contract = Contract.load(contract_root)
    assert contract.get_evolvable("system") == "You are helpful."
