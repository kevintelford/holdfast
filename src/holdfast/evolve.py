"""Evolution engine: analyze evidence, propose bounded changes.

Gathers evidence from runs, identifies patterns (especially failures),
and calls an LLM to propose a bounded diff to the evolvable surface.
The proposal is never auto-applied — it's returned for human review.

The LLM call is pluggable — you pass your own callable, or use the
build_evolution_prompt() helper to get the prompt and call whatever you want.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .contract import Contract
from .store import list_evidence

logger = logging.getLogger(__name__)


@dataclass
class EvolutionProposal:
    """A proposed bounded edit to a contract's evolvable surface."""

    diff: str
    rationale: str
    evidence_ids: list[str]
    file_changes: dict[str, str] = field(default_factory=dict)
    """Mapping of relative file paths to their new content."""


def propose_evolution(
    contract: Contract,
    *,
    llm: Callable[[str], str],
    min_runs: int = 5,
) -> EvolutionProposal | None:
    """Analyze accumulated evidence and propose an evolution.

    Returns None if there aren't enough runs or no clear pattern emerges.

    Args:
        contract: The contract to evolve.
        llm: A callable that takes a prompt string and returns a response string.
            This is your LLM — holdfast doesn't manage API keys or providers.
        min_runs: Minimum number of runs required before proposing.

    Returns:
        An EvolutionProposal if a pattern is detected, None otherwise.
    """
    storage = contract.storage_dir()
    runs = list_evidence(storage, contract_name=contract.name)

    if len(runs) < min_runs:
        logger.info(
            "Only %s runs for '%s', need at least %s — skipping evolution",
            len(runs),
            contract.name,
            min_runs,
        )
        return None

    prompt = build_evolution_prompt(contract, runs)

    logger.info("Requesting evolution proposal for '%s' (%s runs)", contract.name, len(runs))

    raw = llm(prompt)
    return _parse_proposal(raw, runs)


def build_evolution_prompt(contract: Contract, runs: list[dict[str, Any]] | None = None) -> str:
    """Build the LLM prompt for proposing an evolution.

    You can use this directly if you want to feed the prompt to your own LLM
    (e.g., in a Claude Code session) rather than using propose_evolution().

    Args:
        contract: The contract to build a prompt for.
        runs: Evidence runs. If None, loads from the contract's storage.

    Returns:
        The full prompt string.
    """
    if runs is None:
        storage = contract.storage_dir()
        runs = list_evidence(storage, contract_name=contract.name)

    # Gather the current evolvable content
    evolvable_content = {}
    for key, ref in contract.evolvable.items():
        if ref.is_source_ref:
            from .extract import extract_symbol

            try:
                target = contract.resolve_ref_path(ref.path)
                loc = extract_symbol(target, ref.symbol)
                label = f"{ref.path}::{ref.symbol}"
                evolvable_content[label] = loc.value
            except (ValueError, FileNotFoundError):
                logger.warning("Could not extract symbol '%s' from %s", ref.symbol, ref.path)
        else:
            path = contract.resolve_ref_path(ref.path)
            if path.is_file():
                evolvable_content[ref.path] = path.read_text()

    # Gather frozen content for context (the LLM needs to know what NOT to change)
    frozen_content = {}
    for key, ref in contract.frozen.items():
        path = contract.root / ref
        if path.is_file():
            frozen_content[ref] = path.read_text()

    # Build a mapping of source refs for the prompt, so the LLM knows the format
    source_refs = {}
    for key, ref in contract.evolvable.items():
        if ref.is_source_ref:
            source_refs[key] = {"path": ref.path, "symbol": ref.symbol}

    return _build_evolution_prompt(
        contract_name=contract.name,
        contract_version=contract.version,
        frozen_content=frozen_content,
        evolvable_content=evolvable_content,
        runs=runs,
        interface_notes=contract.interface_notes,
        source_refs=source_refs,
    )


def _build_evolution_prompt(
    contract_name: str,
    contract_version: int,
    frozen_content: dict[str, str],
    evolvable_content: dict[str, str],
    runs: list[dict[str, Any]],
    interface_notes: str,
    source_refs: dict[str, dict[str, str]] | None = None,
) -> str:
    """Build the LLM prompt for proposing an evolution."""

    # Summarize runs — focus on failures and patterns
    run_summaries = []
    for run in runs:
        status = "PASS" if run.get("passed") else "FAIL"
        summary = f"[{status}] {run['id']}: {run.get('input_summary', 'no summary')}"
        if run.get("notes"):
            summary += f" — {run['notes']}"
        if not run.get("passed") and run.get("output"):
            # Include output snippet for failures
            output_str = json.dumps(run["output"], default=str)
            if len(output_str) > 300:
                output_str = output_str[:300] + "..."
            summary += f"\n  Output: {output_str}"
        run_summaries.append(summary)

    failed_runs = [r for r in runs if not r.get("passed")]
    passed_runs = [r for r in runs if r.get("passed")]

    source_ref_note = ""
    if source_refs:
        ref_lines = []
        for key, info in source_refs.items():
            ref_lines.append(f"  - {key}: symbol `{info['symbol']}` in `{info['path']}`")
        source_ref_note = (
            "\n\nSome evolvable surfaces are Python symbols (string constants in source files).\n"
            "For these, use the `path::symbol` key in file_changes and provide only the new string value "
            "(not the assignment or quotes).\n\nSource refs:\n" + "\n".join(ref_lines)
        )

    return f"""You are an evolution engine for a governed prompt system called holdfast.

## Contract: {contract_name} (v{contract_version})

{f"Interface notes: {interface_notes}" if interface_notes else ""}

## Frozen surfaces (DO NOT propose changes to these)

{_format_content_block(frozen_content)}

## Evolvable surfaces (you may propose changes to these ONLY)

{_format_content_block(evolvable_content)}{source_ref_note}

## Run evidence ({len(runs)} total: {len(passed_runs)} passed, {len(failed_runs)} failed)

{chr(10).join(run_summaries)}

## Your task

Analyze the evidence above. If you see a clear pattern — especially repeated
failures with a common cause — propose a minimal, bounded change to the
evolvable surfaces.

Rules:
1. ONLY propose changes to evolvable files. Never touch frozen content.
2. Keep changes minimal — one targeted improvement, not a rewrite.
3. The change must preserve compatibility with the frozen schema and interface.
4. Explain your reasoning with specific evidence (cite run IDs).
5. If there's no clear pattern or nothing to improve, say so.

Respond in this exact JSON format:
{{
  "has_proposal": true/false,
  "rationale": "Why this change, citing specific run IDs",
  "evidence_ids": ["run-003", "run-007"],
  "file_changes": {{
    "evolvable/prompt.md": "the complete new content of the file"
  }},
  "diff_summary": "One-line summary of what changed"
}}

If has_proposal is false, set rationale to explain why no change is needed and leave other fields empty.
Respond with ONLY the JSON, no markdown fences or other text."""


def _format_content_block(content: dict[str, str]) -> str:
    """Format a dict of file paths → content for the prompt."""
    if not content:
        return "(none)"
    parts = []
    for path, text in content.items():
        parts.append(f"### {path}\n```\n{text}\n```")
    return "\n\n".join(parts)


def _parse_proposal(raw: str, runs: list[dict[str, Any]]) -> EvolutionProposal | None:
    """Parse the LLM response into an EvolutionProposal."""
    # Strip markdown fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse evolution response as JSON")
        return None

    if not data.get("has_proposal"):
        logger.info("No evolution proposed: %s", data.get("rationale", "no reason given"))
        return None

    return EvolutionProposal(
        diff=data.get("diff_summary", ""),
        rationale=data.get("rationale", ""),
        evidence_ids=data.get("evidence_ids", []),
        file_changes=data.get("file_changes", {}),
    )
