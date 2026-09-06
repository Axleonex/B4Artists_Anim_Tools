"""Repeatable CPU generation benchmark; run in a factory-startup Bforartists process."""
import sys
import json
import statistics
import time
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ghost_regressions import bpy, ghost_tool, gd, vd, Vector, make_rig, patch
with patch.object(ghost_tool, '_clear_pycache'):
    ghost_tool.register()
obj = make_rig(40)
bones = [b.name for b in obj.pose.bones]
scene = bpy.context.scene
settings = scene.ghost_tool
settings.is_active = False
frames = list(range(2, 21))
visits = []
def record(scene, depsgraph=None):
    visits.append(scene.frame_current_final)
bpy.app.handlers.frame_change_post.append(record)
timings, counts = [], []
try:
    for _ in range(4):
        scene.frame_set(7, subframe=0.25)
        visits.clear()
        start = time.perf_counter()
        ghosts = gd.generate_ghosts_frame_step(obj, obj, bones, gd.LOCATION_CHANNELS, frames)
        timings.append((time.perf_counter() - start) * 1000)
        counts.append(len(visits))
    print('GHOST_BENCHMARK ' + json.dumps(dict(bones=len(bones), frames=len(frames), ghosts=len(ghosts),
        median_ms=statistics.median(timings[1:]), runs_ms=timings, frame_changes=counts)))
    store = gd.GhostStore.get(scene)
    store.replace_all(ghosts)
    settings.ghost_color_mode = 'LEVEL'
    args = (None, store, ghosts, settings, 0.05, Vector((1,0,0)), Vector((0,1,0)), 7, store.frame_range)
    # CPU marker preparation only. GPU driver time/FPS are intentionally excluded.
    def payload(shader, mode, data, indices):
        return (data, indices)
    with patch.object(vd, 'batch_for_shader', side_effect=payload) as upload:
        results = {}
        for name, operation in (('uncached', vd._build_marker_batches), ('cached', vd._get_marker_batches)):
            vd._batch_cache.clear()
            operation(*args)
            samples = []
            upload.reset_mock()
            for _ in range(20):
                start = time.perf_counter()
                operation(*args)
                samples.append((time.perf_counter() - start) * 1000)
            results[name] = dict(median_ms=statistics.median(samples), batch_builds=upload.call_count)
        print('MARKER_CPU_BENCHMARK ' + json.dumps(results))

finally:
    bpy.app.handlers.frame_change_post.remove(record)
    ghost_tool.unregister()
