"""Version management: snapshot, apply evolution, rollback.

Each evolution snapshots the current evolvable/ state before applying changes,
enabling rollback to any previous version.
"""

from __future__ import annotations

import logging
from typing import Any

from .contract import Contract
from .store import (
    next_evolution_id,
    now_iso,
    restore_evolvable,
    snapshot_evolvable,
    write_evolution,
)

logger = logging.getLogger(__name__)


def apply_evolution(contract: Contract, proposal: Any) -> str:
    """Apply an approved evolution proposal.

    Steps:
    1. Snapshot current evolvable/ state
    2. Write the new evolvable files from the proposal
    3. Bump the contract version
    4. Record the evolution
    5. Save the updated contract.yaml

    Args:
        contract: The contract to evolve.
        proposal: An EvolutionProposal (from evolve.py).

    Returns:
        The evolution ID.
    """
    storage = contract.storage_dir()
    old_version = contract.version
    new_version = old_version + 1

    # 1. Snapshot current state
    snapshot_evolvable(storage, contract.evolvable_dir(), old_version)
    logger.info("Snapshotted evolvable/ at v%s", old_version)

    # 2. Apply the proposed changes to evolvable files
    for rel_path, new_content in proposal.file_changes.items():
        target = contract.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content)
        logger.info("Updated %s", rel_path)

    # 3. Bump version
    contract.version = new_version

    # 4. Record the evolution
    evo_id = next_evolution_id(storage)
    evolution_data = {
        "id": evo_id,
        "from_version": old_version,
        "to_version": new_version,
        "timestamp": now_iso(),
        "diff": proposal.diff,
        "rationale": proposal.rationale,
        "evidence_ids": proposal.evidence_ids,
        "status": "applied",
    }
    write_evolution(storage, evolution_data)

    # 5. Save updated contract.yaml
    contract.save()

    logger.info("Applied evolution %s: v%s → v%s", evo_id, old_version, new_version)
    return evo_id


def rollback(contract: Contract, to_version: int) -> None:
    """Rollback the contract's evolvable/ to a previous version.

    Args:
        contract: The contract to rollback.
        to_version: The version to restore.
    """
    storage = contract.storage_dir()

    # Snapshot current state before rollback (safety net)
    snapshot_evolvable(storage, contract.evolvable_dir(), contract.version)

    # Restore the target version
    restore_evolvable(storage, contract.evolvable_dir(), to_version)

    # Record the rollback as an evolution
    old_version = contract.version
    evo_id = next_evolution_id(storage)
    evolution_data = {
        "id": evo_id,
        "from_version": old_version,
        "to_version": to_version,
        "timestamp": now_iso(),
        "diff": f"Rollback from v{old_version} to v{to_version}",
        "rationale": "Manual rollback",
        "evidence_ids": [],
        "status": "applied",
    }
    write_evolution(storage, evolution_data)

    # Update contract version
    contract.version = to_version
    contract.save()

    logger.info("Rolled back contract '%s' from v%s to v%s", contract.name, old_version, to_version)


def list_versions(contract: Contract) -> list[int]:
    """List all available version snapshots."""
    storage = contract.storage_dir()
    versions_path = storage / "versions"
    if not versions_path.exists():
        return []

    versions = []
    for d in sorted(versions_path.iterdir()):
        if d.is_dir() and d.name.startswith("v"):
            try:
                versions.append(int(d.name[1:]))
            except ValueError:
                continue
    return versions
