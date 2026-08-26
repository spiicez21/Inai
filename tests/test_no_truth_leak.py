"""The ground-truth contract. DATA.md §5.3, INAI_SPEC.md §0.6.

    FORBIDDEN: inai/core/**, inai/match/**, inai/classify.py importing inai.sim.truth

Two independent guards, deliberately redundant:
  1. ruff TID251 banned-api (pyproject.toml) — fires in the editor, before the code is saved.
  2. this AST scan — fires in CI, and catches the dynamic forms ruff cannot see.

Written BEFORE sim/truth.py existed (DATA.md §9 day-one checklist).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Packages that make decisions. None of them may see the answers.
QUARANTINED = ("inai/match", "inai/core", "inai/classify.py", "inai/baseline", "inai/channels")

FORBIDDEN_ROOTS = ("inai.sim.truth", "inai.sim")


def _quarantined_files() -> list[Path]:
    files: list[Path] = []
    for target in QUARANTINED:
        p = REPO_ROOT / target
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(p.rglob("*.py"))
    return files


def _imports(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.extend(f"{node.module}.{a.name}" for a in node.names)
            found.append(node.module)
    return found


@pytest.mark.parametrize("path", _quarantined_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_static_truth_import(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for name in _imports(tree):
        assert not name.startswith(FORBIDDEN_ROOTS), (
            f"{path.relative_to(REPO_ROOT)} imports {name!r}. Ground truth must never reach a "
            f"module that makes a decision — it would make every match rate circular. "
            f"See DATA.md §5.3."
        )


def _code_only(path: Path) -> str:
    """Source with comments and docstrings removed.

    The guard must scan CODE, not prose. Searching raw text made it impossible to *explain*
    the rule inside the very modules that have to obey it — this test failed on a docstring
    that said "match/** may not import sim.truth". A rule you cannot document is a rule
    people will break by accident.

    Other string literals survive, because `importlib.import_module("inai.sim.truth")` is
    exactly the dynamic form this check exists to catch.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))

    docstring_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
                and first.end_lineno is not None
            ):
                docstring_lines.update(range(first.lineno, first.end_lineno + 1))

    out: list[str] = []
    for i, line in enumerate(src.splitlines(), start=1):
        if i in docstring_lines:
            continue
        out.append(line.split("#", 1)[0])
    return "\n".join(out)


@pytest.mark.parametrize("path", _quarantined_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_dynamic_truth_import(path: Path) -> None:
    """`importlib.import_module("inai.sim.truth")` and friends — the form ruff cannot see."""
    code = _code_only(path)
    for needle in ("sim.truth", "sim/truth", "ground_truth", "truth_links", "LatentState"):
        assert needle not in code, (
            f"{path.relative_to(REPO_ROOT)} references {needle!r} in CODE. See DATA.md §5.3."
        )


def test_the_dynamic_guard_still_catches_a_real_leak(tmp_path: Path) -> None:
    """The guard is now lenient about prose, so prove it is still strict about code."""
    leak = tmp_path / "leaky.py"
    leak.write_text(
        '"""A docstring mentioning sim.truth is fine."""\n'
        "import importlib\n"
        'mod = importlib.import_module("inai.sim.truth")\n',
        encoding="utf-8",
    )
    code = _code_only(leak)
    assert "sim.truth" in code
    assert "A docstring mentioning" not in code


def test_quarantine_actually_covers_something() -> None:
    """A guard that scans zero files passes vacuously. Fail loudly if the tree moves."""
    assert _quarantined_files(), "quarantine list matched no files — QUARANTINED is stale"
