"""Version management: snapshot, apply evolution, rollback.

Each evolution snapshots the current evolvable/ state before applying changes,
enabling rollback to any previous version.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .contract import Contract
from .extract import extract_symbol, write_symbol
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

    # 1. Snapshot current state (evolvable/ dir + source file symbols)
    snapshot_evolvable(storage, contract.evolvable_dir(), old_version)
    _snapshot_source_refs(contract, storage, old_version)
    logger.info("Snapshotted evolvable/ at v%s", old_version)

    # 2. Apply the proposed changes
    # Build lookup of allowed change keys from declared evolvable refs
    source_ref_keys = {}
    file_ref_paths = set()
    for key, ref in contract.evolvable.items():
        if ref.is_source_ref:
            source_ref_keys[f"{ref.path}::{ref.symbol}"] = ref
        else:
            file_ref_paths.add(ref.path)

    for change_key, new_content in proposal.file_changes.items():
        if "::" in change_key and change_key in source_ref_keys:
            # Source ref: write back to Python symbol
            ref = source_ref_keys[change_key]
            target = contract.resolve_ref_path(ref.path)
            write_symbol(target, ref.symbol, new_content)
            logger.info("Updated symbol %s in %s", ref.symbol, ref.path)
        elif change_key in file_ref_paths:
            # File ref: write whole file
            target = contract.resolve_ref_path(change_key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_content)
            logger.info("Updated %s", change_key)
        else:
            logger.warning(
                "Rejected file_changes key '%s' — not a declared evolvable ref",
                change_key,
            )

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
    _snapshot_source_refs(contract, storage, contract.version)

    # Restore the target version
    restore_evolvable(storage, contract.evolvable_dir(), to_version)
    _restore_source_refs(contract, storage, to_version)

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


def _snapshot_source_refs(contract: Contract, storage: Path, version: int) -> None:
    """Snapshot current values of source-ref symbols before evolution."""
    source_refs = {}
    for key, ref in contract.evolvable.items():
        if ref.is_source_ref:
            try:
                target = contract.resolve_ref_path(ref.path)
                loc = extract_symbol(target, ref.symbol)
                source_refs[key] = {
                    "path": ref.path,
                    "symbol": ref.symbol,
                    "value": loc.value,
                }
            except (ValueError, FileNotFoundError):
                logger.warning("Could not snapshot source ref '%s'", key)

    if source_refs:
        snapshot_dir = storage / "versions" / f"v{version}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / "source_refs.json"
        snapshot_file.write_text(json.dumps(source_refs, indent=2))
        logger.info("Snapshotted %s source ref(s) at v%s", len(source_refs), version)


def _restore_source_refs(contract: Contract, storage: Path, version: int) -> None:
    """Restore source-ref symbol values from a version snapshot."""
    snapshot_file = storage / "versions" / f"v{version}" / "source_refs.json"
    if not snapshot_file.exists():
        return

    source_refs = json.loads(snapshot_file.read_text())
    for key, info in source_refs.items():
        try:
            target = contract.resolve_ref_path(info["path"])
            write_symbol(target, info["symbol"], info["value"])
            logger.info("Restored source ref '%s' from v%s", key, version)
        except (ValueError, FileNotFoundError):
            logger.warning("Could not restore source ref '%s' from v%s", key, version)
