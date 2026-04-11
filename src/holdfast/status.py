"""Status CLI: check contract status, evidence count, alerts.

Usage:
    python -m holdfast status contracts/my-pipeline/
    python -m holdfast status contracts/my-pipeline/ --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contract import Contract
from .detect import check_contract
from .store import list_evidence, list_evolutions


def main() -> int:
    parser = argparse.ArgumentParser(prog="holdfast", description="Holdfast contract status")
    sub = parser.add_subparsers(dest="command")

    status_parser = sub.add_parser("status", help="Check contract status")
    status_parser.add_argument("contract_dir", help="Path to the contract directory")
    status_parser.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command != "status":
        parser.print_help()
        return 1

    contract_dir = Path(args.contract_dir).resolve()
    if not (contract_dir / "contract.yaml").exists():
        print(f"No contract.yaml found in {contract_dir}")
        return 1

    contract = Contract.load(contract_dir)
    storage = contract.storage_dir()
    runs = list_evidence(storage, contract_name=contract.name)
    evolutions = list_evolutions(storage)
    alerts = check_contract(contract)

    passed = sum(1 for r in runs if r.get("passed"))
    failed = len(runs) - passed

    if args.as_json:
        data = {
            "name": contract.name,
            "version": contract.version,
            "evolution_mode": contract.evolution_mode,
            "evidence": {"total": len(runs), "passed": passed, "failed": failed},
            "evolutions": len(evolutions),
            "alerts": [{"type": a.rule_type, "description": a.description, "detail": a.detail} for a in alerts],
        }
        print(json.dumps(data, indent=2))
    else:
        print(f"Contract: {contract.name} (v{contract.version}, mode: {contract.evolution_mode})")
        print(f"Evidence: {len(runs)} runs ({passed} passed, {failed} failed)")
        if evolutions:
            last = evolutions[-1]
            ts = last.get("timestamp", "unknown")[:10]
            print(f"Last evolution: v{last.get('from_version')} → v{last.get('to_version')} on {ts}")
        if alerts:
            print(f"Alerts: {len(alerts)}")
            for alert in alerts:
                print(f"  [{alert.rule_type}] {alert.description} — {alert.detail}")
        else:
            print("Alerts: none")

        if runs and not alerts:
            print("\nNo issues detected. Use Claude Code with the holdfast skill to review evidence in depth.")

    return 0
