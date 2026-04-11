"""Contract: the core primitive for governed evolution.

A contract is a directory containing:
- contract.yaml — name, version, refs to frozen/evolvable files
- frozen/ — files that never change via evolution
- evolvable/ — files that can be proposed for changes
- invariants.yaml — checks that must pass before and after evolution
- detection.yaml — rules for detecting patterns across runs
- .holdfast/ — managed storage for evidence and version history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_EVOLUTION_MODES = ("monitor", "semi-auto", "auto")


@dataclass
class Contract:
    """A governed contract with frozen and evolvable surfaces."""

    name: str
    version: int
    root: Path
    frozen: dict[str, str] = field(default_factory=dict)
    evolvable: dict[str, str] = field(default_factory=dict)
    interface_notes: str = ""
    evolution_mode: str = "monitor"

    @classmethod
    def load(cls, path: str | Path) -> Contract:
        """Load a contract from a directory containing contract.yaml."""
        root = Path(path).resolve()
        config_path = root / "contract.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"No contract.yaml found in {root}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        frozen_refs = data.get("frozen", {})
        # interface_notes is metadata, not a file ref
        interface_notes = frozen_refs.pop("interface_notes", "")

        evolution_mode = data.get("evolution_mode", "monitor")
        if evolution_mode not in VALID_EVOLUTION_MODES:
            raise ValueError(f"Invalid evolution_mode '{evolution_mode}'. Must be one of: {VALID_EVOLUTION_MODES}")

        return cls(
            name=data["name"],
            version=data.get("version", 1),
            root=root,
            frozen=frozen_refs,
            evolvable=data.get("evolvable", {}),
            interface_notes=interface_notes,
            evolution_mode=evolution_mode,
        )

    def get_evolvable(self, key: str) -> str:
        """Read the content of an evolvable file by its key.

        For example, contract.get_evolvable("prompt") reads the file
        referenced by evolvable.prompt in contract.yaml.
        """
        ref = self.evolvable.get(key)
        if ref is None:
            raise KeyError(f"No evolvable surface named '{key}' in contract '{self.name}'")

        path = self.root / ref
        if not path.exists():
            raise FileNotFoundError(f"Evolvable file not found: {path}")

        return path.read_text()

    def get_frozen(self, key: str) -> str:
        """Read the content of a frozen file by its key."""
        ref = self.frozen.get(key)
        if ref is None:
            raise KeyError(f"No frozen surface named '{key}' in contract '{self.name}'")

        path = self.root / ref
        if not path.exists():
            raise FileNotFoundError(f"Frozen file not found: {path}")

        return path.read_text()

    def get_frozen_json(self, key: str) -> Any:
        """Read and parse a frozen JSON file (e.g., a JSON Schema)."""
        import json

        content = self.get_frozen(key)
        return json.loads(content)

    def evolvable_dir(self) -> Path:
        """Return the path to the evolvable/ directory."""
        return self.root / "evolvable"

    def storage_dir(self) -> Path:
        """Return the path to .holdfast/ managed storage."""
        d = self.root / ".holdfast"
        d.mkdir(exist_ok=True)
        return d

    def load_detection_rules(self) -> list[dict[str, Any]]:
        """Load detection rules from detection.yaml in the contract directory."""
        path = self.root / "detection.yaml"
        if not path.exists():
            return []
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, list) else []

    def save(self) -> None:
        """Write the current contract state back to contract.yaml."""
        data: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "evolution_mode": self.evolution_mode,
            "frozen": {**self.frozen},
            "evolvable": dict(self.evolvable),
        }
        if self.interface_notes:
            data["frozen"]["interface_notes"] = self.interface_notes

        config_path = self.root / "contract.yaml"
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
