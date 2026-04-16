"""Flat-file storage for evidence and version snapshots.

Evidence: JSON files in .holdfast/evidence/
Versions: directory snapshots in .holdfast/versions/
Evolutions: JSON files in .holdfast/versions/ alongside snapshots
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- Evidence ---


def evidence_dir(storage_root: Path) -> Path:
    return _ensure_dir(storage_root / "evidence")


def write_evidence(storage_root: Path, run_data: dict[str, Any]) -> Path:
    """Write a run evidence file. Returns the path written."""
    d = evidence_dir(storage_root)
    run_id = run_data["id"]
    path = d / f"{run_id}.json"
    with open(path, "w") as f:
        json.dump(run_data, f, indent=2, default=str)
    return path


def read_evidence(storage_root: Path, run_id: str) -> dict[str, Any]:
    """Read a single evidence file by run ID."""
    path = evidence_dir(storage_root) / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No evidence found for run '{run_id}'")
    with open(path) as f:
        return json.load(f)


def list_evidence(storage_root: Path, contract_name: str | None = None) -> list[dict[str, Any]]:
    """List all evidence, optionally filtered by contract name.

    Returns evidence sorted by timestamp (oldest first).
    """
    d = evidence_dir(storage_root)
    runs = []
    for p in sorted(d.glob("*.json")):
        with open(p) as f:
            data = json.load(f)
        if contract_name and data.get("contract_name") != contract_name:
            continue
        runs.append(data)
    return sorted(runs, key=lambda r: r.get("timestamp", ""))


# --- Version snapshots ---


def versions_dir(storage_root: Path) -> Path:
    return _ensure_dir(storage_root / "versions")


def snapshot_evolvable(storage_root: Path, evolvable_dir: Path, version: int) -> Path:
    """Copy the current evolvable/ directory into a versioned snapshot."""
    dest = versions_dir(storage_root) / f"v{version}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(evolvable_dir, dest)
    return dest


def restore_evolvable(storage_root: Path, evolvable_dir: Path, version: int) -> None:
    """Restore evolvable/ from a versioned snapshot."""
    src = versions_dir(storage_root) / f"v{version}"
    if not src.exists():
        raise FileNotFoundError(f"No snapshot found for version {version}")

    # Clear current evolvable and copy snapshot back
    if evolvable_dir.exists():
        shutil.rmtree(evolvable_dir)
    shutil.copytree(src, evolvable_dir)


# --- Evolution records ---


def write_evolution(storage_root: Path, evolution_data: dict[str, Any]) -> Path:
    """Write an evolution record."""
    d = versions_dir(storage_root)
    evo_id = evolution_data["id"]
    path = d / f"{evo_id}.json"
    with open(path, "w") as f:
        json.dump(evolution_data, f, indent=2, default=str)
    return path


def read_evolution(storage_root: Path, evo_id: str) -> dict[str, Any]:
    """Read an evolution record."""
    path = versions_dir(storage_root) / f"{evo_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No evolution record found for '{evo_id}'")
    with open(path) as f:
        return json.load(f)


def list_evolutions(storage_root: Path) -> list[dict[str, Any]]:
    """List all evolution records, sorted by timestamp."""
    d = versions_dir(storage_root)
    evos = []
    for p in sorted(d.glob("evo-*.json")):
        with open(p) as f:
            evos.append(json.load(f))
    return sorted(evos, key=lambda e: e.get("timestamp", ""))


def _max_seq_id(directory: Path, prefix: str) -> int:
    """Find the highest sequential ID number for a given prefix (e.g. 'run', 'evo')."""
    max_num = 0
    for p in directory.glob(f"{prefix}-*.json"):
        try:
            num = int(p.stem.split("-", 1)[1])
            max_num = max(max_num, num)
        except (ValueError, IndexError):
            continue
    return max_num


def next_run_id(storage_root: Path) -> str:
    """Generate the next sequential run ID."""
    d = evidence_dir(storage_root)
    num = _max_seq_id(d, "run") + 1
    return f"run-{num:05d}"


def next_evolution_id(storage_root: Path) -> str:
    """Generate the next sequential evolution ID."""
    d = versions_dir(storage_root)
    num = _max_seq_id(d, "evo") + 1
    return f"evo-{num:05d}"


def now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(UTC).isoformat()
