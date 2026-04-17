"""Contract: the core primitive for governed evolution.

A contract is a directory containing:
- contract.yaml — name, version, refs to frozen/evolvable files
- frozen/ — files that never change via evolution
- evolvable/ — files that can be proposed for changes
- invariants.yaml — checks that must pass before and after evolution
- detection.yaml — rules for detecting patterns across runs
- .holdfast/ — managed storage for evidence and version history

Evolvable refs can be:
- A string path: "evolvable/prompt.md" (reads the whole file)
- A dict with path + symbol: {path: "src/prompts.py", symbol: "SYSTEM_PROMPT"}
  (extracts a Python string literal by symbol name)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_EVOLUTION_MODES = ("monitor", "semi-auto", "auto")
VALID_MODES = ("pipeline", "claude")


def _validate_contract_data(data: Any, config_path: Path) -> None:
    """Validate contract.yaml structure at load time."""
    if not isinstance(data, dict):
        raise ValueError(f"contract.yaml must be a YAML mapping, got {type(data).__name__} in {config_path}")

    if "name" not in data:
        raise ValueError(f"contract.yaml missing required field 'name' in {config_path}")

    if not isinstance(data.get("name"), str):
        raise ValueError(f"contract.yaml 'name' must be a string in {config_path}")

    if "version" in data and not isinstance(data["version"], int):
        raise ValueError(f"contract.yaml 'version' must be an integer in {config_path}")

    # Validate evolvable ref format
    for key, val in data.get("evolvable", {}).items():
        if isinstance(val, str):
            continue
        if isinstance(val, dict):
            if "path" not in val:
                raise ValueError(f"Evolvable ref '{key}' dict must have a 'path' field in {config_path}")
            if "symbol" not in val:
                raise ValueError(f"Evolvable ref '{key}' dict must have a 'symbol' field in {config_path}")
            if not isinstance(val["path"], str) or not isinstance(val["symbol"], str):
                raise ValueError(f"Evolvable ref '{key}' path and symbol must be strings in {config_path}")
        else:
            raise ValueError(
                f"Evolvable ref '{key}' must be a string path or a dict with path+symbol, "
                f"got {type(val).__name__} in {config_path}"
            )


@dataclass
class EvolvableRef:
    """A reference to an evolvable surface — either a file or a Python symbol."""

    path: str
    symbol: str | None = None

    @property
    def is_source_ref(self) -> bool:
        return self.symbol is not None

    @classmethod
    def from_yaml(cls, value: str | dict) -> EvolvableRef:
        if isinstance(value, str):
            return cls(path=value)
        return cls(path=value["path"], symbol=value.get("symbol"))

    def to_yaml(self) -> str | dict:
        if self.symbol is None:
            return self.path
        return {"path": self.path, "symbol": self.symbol}


@dataclass
class Contract:
    """A governed contract with frozen and evolvable surfaces."""

    name: str
    version: int
    root: Path
    frozen: dict[str, str] = field(default_factory=dict)
    evolvable: dict[str, EvolvableRef] = field(default_factory=dict)
    interface_notes: str = ""
    evolution_mode: str = "monitor"
    mode: str = "pipeline"
    project_root: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> Contract:
        """Load a contract from a directory containing contract.yaml."""
        root = Path(path).resolve()
        config_path = root / "contract.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"No contract.yaml found in {root}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        _validate_contract_data(data, config_path)

        frozen_refs = data.get("frozen", {})
        # interface_notes is metadata, not a file ref
        interface_notes = frozen_refs.pop("interface_notes", "")

        evolution_mode = data.get("evolution_mode", "monitor")
        if evolution_mode not in VALID_EVOLUTION_MODES:
            raise ValueError(f"Invalid evolution_mode '{evolution_mode}'. Must be one of: {VALID_EVOLUTION_MODES}")

        mode = data.get("mode", "pipeline")
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of: {VALID_MODES}")

        evolvable_raw = data.get("evolvable", {})
        evolvable_refs = {k: EvolvableRef.from_yaml(v) for k, v in evolvable_raw.items()}

        # project_root: optional, resolved relative to contract root, must be an ancestor
        project_root = None
        if "project_root" in data:
            project_root = (root / data["project_root"]).resolve()
            if not root.is_relative_to(project_root):
                raise ValueError(
                    f"project_root '{data['project_root']}' (resolves to {project_root}) "
                    f"is not an ancestor of contract root {root}"
                )

        return cls(
            name=data["name"],
            version=data.get("version", 1),
            root=root,
            frozen=frozen_refs,
            evolvable=evolvable_refs,
            interface_notes=interface_notes,
            evolution_mode=evolution_mode,
            mode=mode,
            project_root=project_root,
        )

    @property
    def path_boundary(self) -> Path:
        """The boundary for path resolution — project_root if set, otherwise contract root."""
        return self.project_root if self.project_root is not None else self.root

    def resolve_ref_path(self, ref_path: str) -> Path:
        """Resolve a ref path, enforcing path boundaries.

        Paths are resolved relative to project_root (if set) or contract root.
        Raises ValueError if the resolved path escapes the boundary.
        """
        base = self.path_boundary
        resolved = (base / ref_path).resolve()
        if not resolved.is_relative_to(base):
            raise ValueError(f"Path '{ref_path}' escapes path boundary {base}")
        return resolved

    def get_evolvable(self, key: str) -> str:
        """Read the content of an evolvable surface by its key.

        For file refs, reads the whole file.
        For source refs (path + symbol), extracts the symbol value from the Python file.
        """
        ref = self.evolvable.get(key)
        if ref is None:
            raise KeyError(f"No evolvable surface named '{key}' in contract '{self.name}'")

        if ref.is_source_ref:
            from .extract import extract_symbol

            target = self.resolve_ref_path(ref.path)
            loc = extract_symbol(target, ref.symbol)
            return loc.value

        path = self.resolve_ref_path(ref.path)
        if not path.exists():
            raise FileNotFoundError(f"Evolvable file not found: {path}")

        return path.read_text()

    def get_frozen(self, key: str) -> str:
        """Read the content of a frozen file by its key."""
        ref = self.frozen.get(key)
        if ref is None:
            raise KeyError(f"No frozen surface named '{key}' in contract '{self.name}'")

        path = self.resolve_ref_path(ref)
        if not path.exists():
            raise FileNotFoundError(f"Frozen file not found: {path}")

        return path.read_text()

    def get_frozen_json(self, key: str) -> Any:
        """Read and parse a frozen JSON file (e.g., a JSON Schema)."""
        import json

        content = self.get_frozen(key)
        return json.loads(content)

    def evolvable_dir(self) -> Path:
        """Return the path to the evolvable/ directory.

        Note: with source refs, evolvable content may live outside this directory.
        This method returns the conventional evolvable/ dir for file-based refs.
        """
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
            "mode": self.mode,
            "evolution_mode": self.evolution_mode,
            "frozen": {**self.frozen},
            "evolvable": {k: ref.to_yaml() for k, ref in self.evolvable.items()},
        }
        if self.project_root is not None:
            # Store as relative path from contract root
            try:
                data["project_root"] = str(self.project_root.relative_to(self.root))
            except ValueError:
                # project_root is an ancestor, so use os.path.relpath
                import os

                data["project_root"] = os.path.relpath(self.project_root, self.root)
        if self.interface_notes:
            data["frozen"]["interface_notes"] = self.interface_notes

        config_path = self.root / "contract.yaml"
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
