"""Smoke tests for Wiki CLI and package integration."""

from __future__ import annotations

import subprocess
import sys


def test_import_wiki() -> None:
    """Verify wiki package and commands import cleanly."""
    import wiki
    from wiki.commands.wiki_commands import WikiCommands
    from wiki.commands.agent_commands import AgentCommands

    cmd = WikiCommands()
    group, desc = cmd.get_description()
    assert group == "wiki"
    assert "Document Graph" in desc


def test_cli_wiki_help() -> None:
    """Verify 'cli wiki --help' runs successfully."""
    result = subprocess.run(
        [sys.executable, "-m", "genai_tk.main.cli", "wiki", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "add" in result.stdout
    assert "search" in result.stdout
    assert "ask" in result.stdout


def test_cli_workflow_help() -> None:
    """Verify 'cli workflow --help' runs successfully."""
    result = subprocess.run(
        [sys.executable, "-m", "genai_tk.main.cli", "workflow", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "run" in result.stdout
    assert "list" in result.stdout


def test_prefect_yaml_help() -> None:
    """Verify prefect-yaml CLI is available and functional."""
    result = subprocess.run(
        ["prefect-yaml", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Declarative YAML DSL" in result.stdout
