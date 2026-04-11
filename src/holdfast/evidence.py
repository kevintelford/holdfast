"""Evidence collection: log_run() and @track decorator.

Evidence accumulates as JSON files in .holdfast/evidence/.
The decorator is thin sugar over log_run() — it runs invariant
validation to determine pass/fail automatically.
"""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Callable
from typing import Any

from .contract import Contract
from .store import next_run_id, now_iso, write_evidence
from .validate import validate_output

logger = logging.getLogger(__name__)


def log_run(
    contract: Contract,
    output: Any,
    *,
    input_summary: str = "",
    passed: bool = True,
    notes: str = "",
    tags: list[str] | None = None,
) -> str:
    """Log a single run as evidence against a contract.

    Args:
        contract: The contract this run was executed against.
        output: The output of the run (will be serialized to JSON).
        input_summary: Brief description of the input.
        passed: Whether the run met expectations.
        notes: Free-form notes about the run.
        tags: Optional tags for filtering.

    Returns:
        The run ID.
    """
    storage = contract.storage_dir()
    run_id = next_run_id(storage)

    run_data = {
        "id": run_id,
        "contract_name": contract.name,
        "contract_version": contract.version,
        "timestamp": now_iso(),
        "input_summary": input_summary,
        "output": _safe_serialize(output),
        "passed": passed,
        "notes": notes,
        "tags": tags or [],
    }

    write_evidence(storage, run_data)
    logger.info("Logged run %s for contract %s (passed=%s)", run_id, contract.name, passed)
    return run_id


def track(contract: Contract) -> Callable:
    """Decorator that automatically logs evidence for each call.

    Usage:
        contract = Contract.load("path/to/contract/")

        @track(contract)
        def classify(item: dict) -> dict:
            ...
            return result

        # Each call to classify() logs evidence automatically.
        # Pass/fail is determined by whether the output is valid JSON-serializable.
        # For richer pass/fail logic, use log_run() directly.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            input_summary = _summarize_args(fn, args, kwargs)

            try:
                result = fn(*args, **kwargs)

                # Run invariant validation to determine pass/fail
                validation = validate_output(contract.root, result)
                notes = ""
                if not validation.passed:
                    notes = f"Invariant failures: {validation.summary()}"

                log_run(
                    contract=contract,
                    output=result,
                    input_summary=input_summary,
                    passed=validation.passed,
                    notes=notes,
                )
                return result
            except Exception as exc:
                log_run(
                    contract=contract,
                    output={"error": str(exc)},
                    input_summary=input_summary,
                    passed=False,
                    notes=f"Exception: {type(exc).__name__}: {exc}",
                )
                raise

        return wrapper

    return decorator


def _safe_serialize(obj: Any) -> Any:
    """Ensure output is JSON-serializable."""
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _summarize_args(fn: Callable, args: tuple, kwargs: dict) -> str:
    """Build a brief summary of function arguments for the evidence log."""
    parts = []
    for i, arg in enumerate(args):
        parts.append(f"arg{i}={_truncate(arg)}")
    for k, v in kwargs.items():
        parts.append(f"{k}={_truncate(v)}")
    return f"{fn.__name__}({', '.join(parts)})" if parts else fn.__name__


def _truncate(value: Any, max_len: int = 100) -> str:
    """Truncate a value to a reasonable summary length."""
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s
