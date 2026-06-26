"""Scene-level data migration helpers."""

from __future__ import annotations

from typing import Callable

import bpy

from .. import constants
from .logging import get_logger

__all__ = ["register_migration", "migrate_scene", "migrate_all_scenes"]

_log = get_logger(__name__)

_MIGRATIONS: list[tuple[int, Callable[[bpy.types.Scene], None]]] = []


def register_migration(version: int) -> Callable:
    """Decorator that registers a scene migration step at *version*."""
    def decorator(fn: Callable[[bpy.types.Scene], None]) -> Callable:
        _MIGRATIONS.append((version, fn))
        _MIGRATIONS.sort(key=lambda x: x[0])
        return fn
    return decorator


@register_migration(1)
def _migration_v1(scene: bpy.types.Scene) -> None:
    """Initial migration - ensure property group is initialised."""
    props = getattr(scene, constants.SCENE_PROP_ATTR, None)
    if props is not None:
        _log.debug("Migration v1: scene '%s' OK", scene.name)


@register_migration(2)
def _migration_v2(scene: bpy.types.Scene) -> None:
    """v11.0.0: ensure the Phase 12 lipsync PropertyGroup exists on the scene."""
    p12 = getattr(scene, constants.P12_SCENE_ATTR, None)
    if p12 is None:
        _log.debug("Migration v2: scene '%s' has no p12 attribute", scene.name)
        return
    _ = p12.enabled  # touch to materialise defaults
    _log.debug("Migration v2: lipsync defaults ensured on scene '%s'", scene.name)


@register_migration(3)
def _migration_v3(scene: bpy.types.Scene) -> None:
    """v12.0.0: backward-compat for v11 lipsync layer links.

    v11 had no concept of target_kind (everything was bone-driven). v12 adds
    a per-link target_kind enum that defaults to SHAPE_KEYS for new links,
    but pre-existing v11 links should keep their original behavior, so we
    pin them to BONES.

    Also defaults mode = SHIPPED for migrated links so they continue to
    play back as baked fcurves until the user opts into PREVIEW.
    """
    p12 = getattr(scene, constants.P12_SCENE_ATTR, None)
    if p12 is None:
        _log.debug("Migration v3: scene '%s' has no p12 attribute", scene.name)
        return

    migrated = 0
    for link in p12.layer_links:
        # If a link has bone wiring already populated and no shape key wiring,
        # it's a v11-era link - pin it to BONES + SHIPPED.
        try:
            link.target_kind = "BONES"
            link.mode = "SHIPPED"
            migrated += 1
        except (AttributeError, TypeError):
            continue
    _log.info("Migration v3: pinned %d v11 links to BONES/SHIPPED on scene '%s'",
              migrated, scene.name)


def migrate_scene(scene: bpy.types.Scene) -> None:
    """Upgrade a single scene's PropertyGroup to the current addon version."""
    props = getattr(scene, constants.SCENE_PROP_ATTR, None)
    if props is None:
        return

    current = props.migration_version
    for version, fn in _MIGRATIONS:
        if version > current:
            try:
                fn(scene)
                props.migration_version = version
                _log.info("Migrated scene '%s' to v%d", scene.name, version)
            except Exception:
                _log.exception("Migration v%d failed for scene '%s'", version, scene.name)
                break


def migrate_all_scenes() -> None:
    """Upgrade all open scenes' PropertyGroups to the current addon version."""
    for scene in bpy.data.scenes:
        migrate_scene(scene)
