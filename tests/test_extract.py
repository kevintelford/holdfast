"""Tests for Python symbol extraction and write-back."""

from pathlib import Path

import pytest

from holdfast.extract import extract_symbol, write_symbol


@pytest.fixture
def py_module(tmp_path: Path) -> Path:
    """A Python file with module-level and class-level string constants."""
    p = tmp_path / "prompts.py"
    p.write_text(
        'SYSTEM_PROMPT = "You are a helpful assistant."\n'
        "\n"
        "OTHER_VAR = 42\n"
        "\n"
        "\n"
        "class CyberPrompts:\n"
        '    MATURITY_PROMPT = "Assess the maturity level."\n'
        '    EVALUATION_PROMPT = "Evaluate the control."\n'
    )
    return p


@pytest.fixture
def py_multiline(tmp_path: Path) -> Path:
    """A Python file with triple-quoted string constants."""
    p = tmp_path / "prompts_ml.py"
    p.write_text(
        'SYSTEM_PROMPT = """You are a helpful assistant.\n'
        "Respond in JSON format.\n"
        'Always include a confidence score."""\n'
    )
    return p


def test_extract_module_level(py_module: Path):
    loc = extract_symbol(py_module, "SYSTEM_PROMPT")
    assert loc.value == "You are a helpful assistant."
    assert loc.symbol == "SYSTEM_PROMPT"
    assert loc.path == py_module
    assert loc.lineno == 1


def test_extract_class_attr(py_module: Path):
    loc = extract_symbol(py_module, "CyberPrompts.MATURITY_PROMPT")
    assert loc.value == "Assess the maturity level."


def test_extract_class_attr_second(py_module: Path):
    loc = extract_symbol(py_module, "CyberPrompts.EVALUATION_PROMPT")
    assert loc.value == "Evaluate the control."


def test_extract_multiline(py_multiline: Path):
    loc = extract_symbol(py_multiline, "SYSTEM_PROMPT")
    assert "Respond in JSON format." in loc.value
    assert loc.lineno == 1
    assert loc.end_lineno == 3


def test_extract_not_found(py_module: Path):
    with pytest.raises(ValueError, match="not found"):
        extract_symbol(py_module, "NONEXISTENT")


def test_extract_not_string(py_module: Path):
    with pytest.raises(ValueError, match="not a string literal"):
        extract_symbol(py_module, "OTHER_VAR")


def test_extract_class_not_found(py_module: Path):
    with pytest.raises(ValueError, match="not found"):
        extract_symbol(py_module, "NoSuchClass.PROMPT")


def test_extract_attr_not_found(py_module: Path):
    with pytest.raises(ValueError, match="not found"):
        extract_symbol(py_module, "CyberPrompts.NONEXISTENT")


def test_write_module_level(py_module: Path):
    write_symbol(py_module, "SYSTEM_PROMPT", "You are a new assistant.")
    loc = extract_symbol(py_module, "SYSTEM_PROMPT")
    assert loc.value == "You are a new assistant."
    # Other code preserved
    source = py_module.read_text()
    assert "OTHER_VAR = 42" in source
    assert "CyberPrompts" in source


def test_write_class_attr(py_module: Path):
    write_symbol(py_module, "CyberPrompts.MATURITY_PROMPT", "New maturity prompt.")
    loc = extract_symbol(py_module, "CyberPrompts.MATURITY_PROMPT")
    assert loc.value == "New maturity prompt."
    # Other attrs preserved
    loc2 = extract_symbol(py_module, "CyberPrompts.EVALUATION_PROMPT")
    assert loc2.value == "Evaluate the control."


def test_write_multiline(py_multiline: Path):
    new_value = "New system prompt.\nWith multiple lines.\nAnd a third."
    write_symbol(py_multiline, "SYSTEM_PROMPT", new_value)
    loc = extract_symbol(py_multiline, "SYSTEM_PROMPT")
    assert loc.value == new_value


def test_write_preserves_quote_style(tmp_path: Path):
    """Single-quoted strings stay single-quoted after write-back."""
    p = tmp_path / "single.py"
    p.write_text("PROMPT = 'hello world'\n")
    write_symbol(p, "PROMPT", "goodbye world")
    source = p.read_text()
    assert "'goodbye world'" in source
    assert '"goodbye world"' not in source


def test_roundtrip_preserves_surrounding_code(py_module: Path):
    """Write-back should not alter any lines outside the target symbol."""
    original = py_module.read_text()
    original_lines = original.splitlines()

    write_symbol(py_module, "SYSTEM_PROMPT", "replaced")
    new_lines = py_module.read_text().splitlines()

    # Line 1 changed (the assignment), rest should be identical
    assert new_lines[0] != original_lines[0]
    assert new_lines[1:] == original_lines[1:]


# -- Parametrized quoting edge cases --


@pytest.mark.parametrize(
    "source_template,symbol,expected_quote",
    [
        ('PROMPT = "hello"', "PROMPT", '"'),
        ("PROMPT = 'hello'", "PROMPT", "'"),
        ('PROMPT = """hello"""', "PROMPT", '"""'),
        ("PROMPT = '''hello'''", "PROMPT", "'''"),
    ],
    ids=["double", "single", "triple-double", "triple-single"],
)
def test_write_preserves_various_quote_styles(tmp_path: Path, source_template, symbol, expected_quote):
    """Write-back preserves the original quoting style across all standard quote types."""
    p = tmp_path / "q.py"
    p.write_text(source_template + "\n")
    write_symbol(p, symbol, "replaced")
    source = p.read_text()
    assert f"{expected_quote}replaced{expected_quote}" in source


def test_write_string_with_embedded_quotes(tmp_path: Path):
    """Strings containing the opposite quote character should survive write-back."""
    p = tmp_path / "q.py"
    p.write_text('PROMPT = "hello"\n')
    write_symbol(p, "PROMPT", "it's a test")
    loc = extract_symbol(p, "PROMPT")
    assert loc.value == "it's a test"


def test_write_string_with_newlines_upgrades_to_triple(tmp_path: Path):
    """Writing a multiline value into a single-quoted string upgrades to triple quotes."""
    p = tmp_path / "q.py"
    p.write_text('PROMPT = "single line"\n')
    write_symbol(p, "PROMPT", "line one\nline two")
    loc = extract_symbol(p, "PROMPT")
    assert loc.value == "line one\nline two"
    # Should have been upgraded to triple quotes
    source = p.read_text()
    assert '"""' in source


def test_write_empty_string(tmp_path: Path):
    """Writing an empty string should work."""
    p = tmp_path / "q.py"
    p.write_text('PROMPT = "hello"\n')
    write_symbol(p, "PROMPT", "")
    loc = extract_symbol(p, "PROMPT")
    assert loc.value == ""


def test_write_string_with_escaped_chars(tmp_path: Path):
    """Strings with tab and newline escape sequences should round-trip correctly."""
    p = tmp_path / "q.py"
    p.write_text('PROMPT = """original"""\n')
    new_val = "header\n\tbody: indented\n\tmore"
    write_symbol(p, "PROMPT", new_val)
    loc = extract_symbol(p, "PROMPT")
    assert loc.value == new_val


def test_write_multiline_class_attr(tmp_path: Path):
    """Multiline write-back inside a class should preserve indentation of surrounding code."""
    p = tmp_path / "q.py"
    p.write_text(
        "class Foo:\n"
        '    PROMPT = "short"\n'
        '    OTHER = "kept"\n'
    )
    write_symbol(p, "Foo.PROMPT", "line one\nline two")
    # Other attr preserved
    loc = extract_symbol(p, "Foo.OTHER")
    assert loc.value == "kept"
    # New value readable
    loc = extract_symbol(p, "Foo.PROMPT")
    assert "line two" in loc.value
