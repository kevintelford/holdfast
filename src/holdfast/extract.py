"""Symbol extraction and write-back for Python source files.

Supports two symbol formats:
- Module-level: "PROMPT" — a top-level assignment
- Class-attribute: "ClassName.PROMPT" — an attribute on a top-level class

Uses ast.parse() for safe extraction — no code execution.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SymbolLocation:
    """Location of a string literal in a Python source file."""

    path: Path
    symbol: str
    value: str
    lineno: int
    end_lineno: int
    col_offset: int
    end_col_offset: int


def extract_symbol(path: Path, symbol: str) -> SymbolLocation:
    """Extract a string value from a Python source file by symbol name.

    Args:
        path: Path to the Python source file.
        symbol: Symbol name. Either "NAME" (module-level) or "Class.NAME" (class attribute).

    Returns:
        SymbolLocation with the extracted value and position info.

    Raises:
        ValueError: If the symbol is not found or is not a string literal.
    """
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))

    parts = symbol.split(".", 1)
    if len(parts) == 2:
        class_name, attr_name = parts
        node = _find_class_attr(tree, class_name, attr_name)
    else:
        node = _find_module_assign(tree, symbol)

    if node is None:
        raise ValueError(f"Symbol '{symbol}' not found in {path}")

    value_node = _get_string_value_node(node)
    if value_node is None:
        raise ValueError(f"Symbol '{symbol}' in {path} is not a string literal")

    return SymbolLocation(
        path=path,
        symbol=symbol,
        value=value_node.value,
        lineno=value_node.lineno,
        end_lineno=value_node.end_lineno,
        col_offset=value_node.col_offset,
        end_col_offset=value_node.end_col_offset,
    )


def write_symbol(path: Path, symbol: str, new_value: str) -> None:
    """Replace a string symbol's value in a Python source file.

    Preserves all surrounding code. Only the string literal is replaced.

    Args:
        path: Path to the Python source file.
        symbol: Symbol name (same format as extract_symbol).
        new_value: The new string value to write.
    """
    loc = extract_symbol(path, symbol)
    source = path.read_text()
    lines = source.splitlines(keepends=True)

    # Build the replacement string literal
    replacement = _format_string_literal(new_value, loc, lines)

    # Replace the old literal in the source
    new_source = _splice_source(lines, loc, replacement)
    path.write_text(new_source)

    logger.info("Updated symbol '%s' in %s", symbol, path)


def _find_module_assign(tree: ast.Module, name: str) -> ast.Assign | None:
    """Find a module-level assignment by target name."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node
    return None


def _find_class_attr(tree: ast.Module, class_name: str, attr_name: str) -> ast.Assign | None:
    """Find a class-level attribute assignment."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == attr_name:
                            return item
    return None


def _get_string_value_node(node: ast.Assign) -> ast.Constant | None:
    """Extract the string Constant node from an assignment, if it is one."""
    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        return node.value
    return None


def _format_string_literal(value: str, loc: SymbolLocation, lines: list[str]) -> str:
    """Format a new string value, preserving the original quoting style."""
    # Detect original quote style from source
    original_line = lines[loc.lineno - 1]
    after_eq = original_line[loc.col_offset:]

    if after_eq.startswith('"""') or after_eq.startswith("'''"):
        quote = after_eq[:3]
    elif after_eq.startswith('"'):
        quote = '"'
    elif after_eq.startswith("'"):
        quote = "'"
    else:
        quote = '"""'

    # Use triple quotes for multiline values
    if "\n" in value and len(quote) == 1:
        quote = quote * 3

    return f"{quote}{value}{quote}"


def _splice_source(lines: list[str], loc: SymbolLocation, replacement: str) -> str:
    """Replace the string literal at loc with replacement in the source lines."""
    # Lines before the literal
    before = lines[: loc.lineno - 1]

    # The prefix on the first line (everything before the string literal)
    first_line = lines[loc.lineno - 1]
    prefix = first_line[: loc.col_offset]

    # The suffix on the last line (everything after the string literal)
    last_line = lines[loc.end_lineno - 1]
    suffix = last_line[loc.end_col_offset :]

    # Lines after the literal
    after = lines[loc.end_lineno :]

    # Assemble
    replaced_line = prefix + replacement + suffix
    return "".join(before) + replaced_line + "".join(after)
