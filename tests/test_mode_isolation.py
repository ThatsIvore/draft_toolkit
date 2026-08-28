import ast
from pathlib import Path
import sys

import fpl_toolkit.cli as cli


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_DRAFT_MODULES = (
    "collector.py",
    "h2h.py",
    "opponent_profile.py",
    "waivers.py",
    "planner.py",
    "outcomes.py",
    "changefeed.py",
    "privacy.py",
)
STANDARD_ONLY_MODULES = {
    "standard_fpl",
    "standard_fpl_lineup",
    "standard_fpl_outcomes",
    "standard_fpl_rules",
    "standard_fpl_runner",
    "standard_fpl_snapshot",
    "standard_fpl_transfers",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_standard_only_modules_do_not_enter_draft_or_h2h_engines():
    source_root = ROOT / "src" / "fpl_toolkit"
    violations = {}
    for filename in PROTECTED_DRAFT_MODULES:
        imports = _imports(source_root / filename)
        standard_imports = sorted(
            module
            for module in imports
            if module.split(".")[-1] in STANDARD_ONLY_MODULES
        )
        if standard_imports:
            violations[filename] = standard_imports
    assert violations == {}


def test_default_cli_route_remains_draft(monkeypatch, capsys):
    draft_report = {"summary": {"mode": "draft-test"}}

    monkeypatch.setattr(sys, "argv", ["fpl-toolkit"])
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(cli, "collect", lambda settings: draft_report)

    def fail_standard(*args, **kwargs):
        raise AssertionError("Default CLI route entered Standard FPL mode.")

    monkeypatch.setattr(cli, "collect_standard_fpl", fail_standard)

    assert cli.main() == 0
    assert '"mode": "draft-test"' in capsys.readouterr().out


def test_standard_fpl_mode_cannot_publish(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["fpl-toolkit", "--mode", "standard-fpl", "--publish"],
    )

    def fail_collection(*args, **kwargs):
        raise AssertionError("No collector should run for a rejected Standard FPL publish.")

    monkeypatch.setattr(cli, "collect", fail_collection)
    monkeypatch.setattr(cli, "collect_standard_fpl", fail_collection)

    assert cli.main() == 2
    assert "private and cannot be used with --publish" in capsys.readouterr().err


def test_scheduled_public_collection_stays_on_draft_mode():
    workflow = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    assert "fpl-toolkit --publish" in workflow
    assert "--mode standard-fpl" not in workflow
