"""Dead code checks for maintained Python modules."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
TESTS_DIR = ROOT / "tests"

FILE_EXCEPTIONS = {
    # CLI entry point is invoked via console scripts, not imported.
    "src.cli",
}

EXPORT_EXCEPTIONS = {
    # Public API for external consumers; not required in internal call sites.
    "src.deliver::EmailRenderer",
    "src.deliver::send_digest",
    "src.ingest::IngestResult",
    "src.analyze::AnalysisResult",
    "src.llm::Provider",
    "src.llm::RetryClient",
}


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _module_map() -> dict[str, Path]:
    return {_module_name(path): path for path in _iter_py_files(SRC_DIR)}


def _resolve_import_from(
    current_module: str,
    is_package_module: bool,
    node: ast.ImportFrom,
) -> str | None:
    if node.level == 0:
        return node.module

    if not current_module:
        return None

    current_parts = current_module.split(".")
    # For modules, strip final segment to get current package.
    if not is_package_module:
        current_parts = current_parts[:-1]

    keep = len(current_parts) - (node.level - 1)
    if keep <= 0:
        return node.module

    base_parts = current_parts[:keep]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _imports_for_file(
    path: Path,
    modules: dict[str, Path],
) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    current_module = _module_name(path)
    is_package_module = path.name == "__init__.py"
    imported: set[str] = set()

    def add_if_known(name: str) -> None:
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            candidate = ".".join(parts[:i])
            if candidate in modules:
                imported.add(candidate)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src"):
                    add_if_known(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(current_module, is_package_module, node)
            if not base or not base.startswith("src"):
                continue
            add_if_known(base)
            for alias in node.names:
                if alias.name == "*":
                    continue
                candidate = f"{base}.{alias.name}"
                add_if_known(candidate)

    imported.discard(current_module)
    return imported


def _extract_all_exports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    exports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "__all__" not in targets:
                continue
            if not isinstance(node.value, (ast.List, ast.Tuple)):
                continue
            for element in node.value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    exports.append(element.value)
    return exports


def test_source_modules_are_imported() -> None:
    modules = _module_map()
    all_files = _iter_py_files(SRC_DIR) + _iter_py_files(TESTS_DIR)
    incoming: dict[str, int] = dict.fromkeys(modules, 0)

    for path in all_files:
        for imported_module in _imports_for_file(path, modules):
            if imported_module in incoming:
                incoming[imported_module] += 1

    orphaned = [
        module
        for module, refs in sorted(incoming.items())
        if refs == 0 and module not in FILE_EXCEPTIONS
    ]

    if orphaned:
        report = "\n".join(f"  {module}" for module in orphaned)
        raise AssertionError(
            "Found orphaned Python module(s) with no imports.\n"
            "Either remove or add to FILE_EXCEPTIONS:\n"
            f"{report}"
        )


def test_all_exports_are_referenced() -> None:
    modules = _module_map()
    all_files = _iter_py_files(SRC_DIR) + _iter_py_files(TESTS_DIR)
    all_contents = {
        _module_name(path): path.read_text(encoding="utf-8")
        for path in all_files
    }

    unreferenced: list[tuple[str, str]] = []

    for module, module_path in modules.items():
        exports = _extract_all_exports(module_path)
        if not exports:
            continue

        for name in exports:
            if len(name) < 4:
                continue
            key = f"{module}::{name}"
            if key in EXPORT_EXCEPTIONS:
                continue

            re_name = re.compile(rf"\b{re.escape(name)}\b")
            referenced = any(
                re_name.search(content)
                for other_module, content in all_contents.items()
                if other_module != module
            )
            if not referenced:
                unreferenced.append((module, name))

    if unreferenced:
        report = "\n".join(
            f"  {module}::{name}" for module, name in sorted(unreferenced)
        )
        raise AssertionError(
            "Found unreferenced __all__ export(s).\n"
            "Either remove dead code or add to EXPORT_EXCEPTIONS:\n"
            f"{report}"
        )
