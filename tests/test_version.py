"""Tests for version management — snapshot, apply, rollback."""

from pathlib import Path

from holdfast import Contract, apply_evolution, list_versions, rollback
from holdfast.evolve import EvolutionProposal


def test_apply_evolution(contract_dir: Path):
    contract = Contract.load(contract_dir)
    original_prompt = contract.get_evolvable("prompt")
    assert contract.version == 1

    proposal = EvolutionProposal(
        diff="Added multi-label handling to prompt",
        rationale="Runs showed failures on multi-label inputs",
        evidence_ids=["run-001", "run-003"],
        file_changes={
            "evolvable/prompt.md": original_prompt + "\nWhen multiple labels apply, pick the strongest.\n",
        },
    )

    evo_id = apply_evolution(contract, proposal)
    assert evo_id == "evo-001"
    assert contract.version == 2

    # Verify the prompt was updated
    new_prompt = contract.get_evolvable("prompt")
    assert "strongest" in new_prompt

    # Verify version snapshot exists
    versions = list_versions(contract)
    assert 1 in versions


def test_rollback(contract_dir: Path):
    contract = Contract.load(contract_dir)
    original_prompt = contract.get_evolvable("prompt")

    # Apply an evolution
    proposal = EvolutionProposal(
        diff="Changed prompt",
        rationale="Testing rollback",
        evidence_ids=[],
        file_changes={"evolvable/prompt.md": "Completely new prompt content.\n"},
    )
    apply_evolution(contract, proposal)
    assert contract.version == 2
    assert contract.get_evolvable("prompt") == "Completely new prompt content.\n"

    # Rollback to v1
    rollback(contract, to_version=1)
    assert contract.version == 1

    restored_prompt = contract.get_evolvable("prompt")
    assert restored_prompt == original_prompt


def test_multiple_evolutions(contract_dir: Path):
    contract = Contract.load(contract_dir)

    for i in range(3):
        proposal = EvolutionProposal(
            diff=f"Evolution {i + 1}",
            rationale=f"Improvement round {i + 1}",
            evidence_ids=[f"run-{i:03d}"],
            file_changes={"evolvable/prompt.md": f"Prompt version {i + 2}.\n"},
        )
        apply_evolution(contract, proposal)

    assert contract.version == 4
    assert contract.get_evolvable("prompt") == "Prompt version 4.\n"

    versions = list_versions(contract)
    assert 1 in versions
    assert 2 in versions
    assert 3 in versions


def test_rollback_preserves_current_as_snapshot(contract_dir: Path):
    """Rolling back should snapshot the current state first (safety net)."""
    contract = Contract.load(contract_dir)

    # Apply evolution to v2
    proposal = EvolutionProposal(
        diff="v2 prompt",
        rationale="test",
        evidence_ids=[],
        file_changes={"evolvable/prompt.md": "Version 2 content.\n"},
    )
    apply_evolution(contract, proposal)

    # Rollback to v1 — should snapshot v2 first
    rollback(contract, to_version=1)

    versions = list_versions(contract)
    assert 2 in versions  # v2 was snapshotted before rollback


def test_list_versions_empty(contract_dir: Path):
    contract = Contract.load(contract_dir)
    versions = list_versions(contract)
    assert versions == []
