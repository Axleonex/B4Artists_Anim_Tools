"""Static coverage checks for animator-facing hover tooltips."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (ROOT / "anim_assist", ROOT / "ghost_tool")


def _trees():
    for package in PACKAGES:
        for path in package.rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path, ast.parse(path.read_text(encoding="utf-8"))


def _property_call(node: ast.AST) -> ast.Call | None:
    if isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Call):
        return node.annotation
    if isinstance(node, (ast.AnnAssign, ast.Assign)) and isinstance(node.value, ast.Call):
        return node.value
    return None


def test_operator_tooltips_are_complete():
    missing = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            values = {}
            for statement in node.body:
                if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name) and isinstance(statement.value, ast.Constant):
                        values[target.id] = statement.value.value
            op_id = values.get("bl_idname")
            if op_id and "." in op_id and not (values.get("bl_description") or ast.get_docstring(node)):
                missing.append(f"{op_id} ({path.name}:{node.lineno})")
    assert not missing, "Operators without hover text: " + ", ".join(missing)


def test_drawn_properties_have_descriptions():
    declarations = defaultdict(list)
    drawn_names = set()
    for path, tree in _trees():
        for node in ast.walk(tree):
            call = _property_call(node)
            target = node.target if isinstance(node, ast.AnnAssign) else None
            if isinstance(target, ast.Name) and call:
                function = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
                if function.endswith("Property"):
                    described = any(keyword.arg == "description" for keyword in call.keywords)
                    declarations[target.id].append((described, path.name, node.lineno))
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"prop", "prop_search"}
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                drawn_names.add(node.args[1].value)

    missing = []
    for name in sorted(drawn_names):
        for described, filename, line in declarations.get(name, ()):
            if not described:
                missing.append(f"{name} ({filename}:{line})")
    assert not missing, "Drawn properties without hover text: " + ", ".join(missing)


def test_addon_preferences_have_descriptions():
    missing = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {
                base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                for base in node.bases
            }
            if "AddonPreferences" not in base_names:
                continue
            for statement in node.body:
                call = _property_call(statement)
                target = statement.target if isinstance(statement, ast.AnnAssign) else None
                if not isinstance(target, ast.Name) or call is None:
                    continue
                function = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
                if function.endswith("Property") and not any(
                    keyword.arg == "description" for keyword in call.keywords
                ):
                    missing.append(f"{target.id} ({path.name}:{statement.lineno})")
    assert not missing, "Preferences without hover text: " + ", ".join(missing)


def test_extended_help_is_per_addon_and_never_global():
    anim_prefs = (ROOT / "anim_assist" / "prefs.py").read_text(encoding="utf-8")
    ghost_prefs = (ROOT / "ghost_tool" / "preferences.py").read_text(encoding="utf-8")
    ghost_ui = (ROOT / "ghost_tool" / "ui_panel.py").read_text(encoding="utf-8")

    assert "show_explainer_help" in anim_prefs
    assert "show_extended_help" in ghost_prefs
    assert "ghost_tool.show_help_popup" in ghost_ui

    all_source = "\n".join(
        path.read_text(encoding="utf-8")
        for package in PACKAGES
        for path in package.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    assert "show_tooltips" not in all_source
