"""Shared context helpers for key selection and channel animation editor operators."""

from __future__ import annotations

import bpy

from .fcurve_compat import get_fcurves

__all__ = [
    "ANIM_EDITOR_SPACES",
    "in_anim_editor",
    "iter_visible_fcurves",
    "iter_selected_keys",
    "key_identity",
]

ANIM_EDITOR_SPACES = {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}


def in_anim_editor(context: bpy.types.Context) -> bool:
    """Return True if the current context is a Graph Editor or Dopesheet view.

    Used as a poll() guard to disable key selection and channel keyframe operators outside
    animation editors where they would have no meaning.
    """
    space = getattr(context, "space_data", None)
    return bool(space) and space.type in ANIM_EDITOR_SPACES


def iter_visible_fcurves(context: bpy.types.Context, only_selected: bool = False):
    """Yield FCurves visible in the current animation editor.

    Filters by visibility (``fc.hide``), mute, and editability. When
    *only_selected* is ``True`` also restricts to selected channels.
    """
    animated_objects = []
    scene = getattr(context, "scene", None)
    view_layer = getattr(context, "view_layer", None)
    if view_layer is None or scene is None:
        return

    seen_ids: set[int] = set()
    for obj in view_layer.objects:
        ad = obj.animation_data
        if ad and ad.action and id(ad.action) not in seen_ids:
            seen_ids.add(id(ad.action))
            animated_objects.append((obj, ad))

    for obj, ad in animated_objects:
        for fc in get_fcurves(ad.action, anim_data=ad):
            if fc.hide or fc.mute:
                continue
            if only_selected and not fc.select:
                continue
            if fc.lock:
                continue
            yield obj, ad.action, fc


def iter_selected_keys(context: bpy.types.Context):
    """Yield ``(obj, action, fcurve, kp_index, kp)`` for selected keyframes."""
    for obj, action, fc in iter_visible_fcurves(context):
        for i, kp in enumerate(fc.keyframe_points):
            if kp.select_control_point:
                yield obj, action, fc, i, kp


def key_identity(obj_name: str, fc: bpy.types.FCurve, frame: float) -> tuple:
    """Create a hashable identity tuple for a specific keyframe (object, path, index, frame).

    Used by the metadata system (key selection and channel) to index per-key data without relying on
    collection indices, which change when keys are added/deleted.
    """
    return (obj_name, fc.data_path, fc.array_index, round(float(frame), 4))
