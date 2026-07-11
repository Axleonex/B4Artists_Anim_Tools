"""Bforartists-only registration and onboarding smoke check.

Run with:
    bforartists --background --factory-startup --python tests/smoke_bforartists.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import anim_assist  # noqa: E402
import ghost_tool  # noqa: E402


def main() -> None:
    assert anim_assist._is_bforartists()
    assert ghost_tool._is_bforartists()

    anim_assist.register()
    try:
        assert bpy.ops.animassist.p10_first_run_setup() == {'FINISHED'}
        assert bpy.context.scene.anim_assist_p10.shelf_mode == "COMPACT"
        assert bpy.context.scene.anim_assist_p10.first_run_complete

        from anim_assist.core import help_draw

        anim_context = SimpleNamespace(
            preferences=SimpleNamespace(
                addons={
                    "anim_assist": SimpleNamespace(
                        preferences=SimpleNamespace(show_explainer_help=False)
                    )
                }
            )
        )
        assert not help_draw._is_enabled(anim_context)

        ghost_tool.register()
        registered_classes = [
            cls
            for module_name in ghost_tool._REGISTER_ORDER
            for cls in getattr(sys.modules[f"ghost_tool.{module_name}"], "CLASSES", ())
        ]
        assert registered_classes
        assert all(hasattr(cls, "bl_rna") for cls in registered_classes)

        from ghost_tool import ui_panel

        class HelpLayout:
            def __init__(self):
                self.calls = 0

            def operator(self, *args, **kwargs):
                self.calls += 1
                return SimpleNamespace(topic="")

        ghost_context = SimpleNamespace(
            preferences=SimpleNamespace(
                addons={
                    "ghost_tool": SimpleNamespace(
                        preferences=SimpleNamespace(show_extended_help=False)
                    )
                }
            )
        )
        help_layout = HelpLayout()
        ui_panel._draw_help_icon(help_layout, ghost_context, "overview")
        assert help_layout.calls == 0

        ghost_tool.unregister()
        assert not ghost_tool._real_addon_registered
    finally:
        if ghost_tool._real_addon_registered:
            ghost_tool.unregister()
        anim_assist.unregister()

    print("Bforartists smoke check passed", flush=True)


if __name__ == "__main__":
    main()
