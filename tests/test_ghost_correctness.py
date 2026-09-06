"""Broader Ghost Tool correctness regressions; uses disposable Bforartists scenes."""
import sys, json, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, mock_open
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ghost_regressions import GhostRegression, bpy, gd, fc, Vector
from ghost_tool import export_import as ei, snapshot as sn, physics_suggest as ps
from ghost_tool import mesh_ghosts as mg, diff_mode as dm, utils

class BroaderCorrectness(GhostRegression):
    def import_data(self, data, **kwargs):
        with patch.object(ei.os.path, 'exists', return_value=True), patch('builtins.open', mock_open(read_data=json.dumps(data))):
            return ei.import_ghosts('memory.json', self.scene, **kwargs)

    def test_import_failure_is_atomic(self):
        store = gd.GhostStore.get(self.scene)
        snapshots = sn.SnapshotStore.get(self.scene)
        old = gd.Ghost(frame=5)
        store.replace_all([old])
        snapshot, _ = snapshots.take_snapshot('Keep me', self.scene)
        bad = old.to_dict(); bad['world_position'] = ['bad', 0, 0]
        for payload in ([], {'ghosts': [bad]}, {'ghosts': [None]}, {'ghosts': [], 'snapshots': [None]}):
            with self.subTest(payload=payload):
                self.assertFalse(self.import_data(payload))
                self.assertEqual(store.all_ghosts, [old])
                self.assertIsNotNone(snapshots.get_by_uid(snapshot.uid))

    def test_import_rejects_nonfinite_and_duplicate_ids(self):
        good = gd.Ghost(frame=5).to_dict()
        bad = dict(good, frame=float('nan'))
        self.assertFalse(self.import_data({'ghosts': [bad]}))
        self.assertFalse(self.import_data({'ghosts': [good, good]}))

    def test_import_valid_remaps_snapshot_references(self):
        good = gd.Ghost(frame=5, object_name='OldRig', bone_name=self.bones[0]).to_dict()
        snap = sn.GhostSnapshot(name='Imported', ghost_data=[good], object_names={'OldRig'}).to_dict()
        self.assertTrue(self.import_data({'ghosts': [good], 'snapshots': [snap]}, target_object=self.obj))
        restored = sn.SnapshotStore.get(self.scene).get_all()[0]
        self.assertEqual(restored.ghost_data[0]['object_name'], self.obj.name)
        self.assertEqual(restored.object_names, {self.obj.name})

    def test_duplicate_scene_has_independent_stores(self):
        gd.GhostStore.get(self.scene).add(gd.Ghost(frame=5))
        duplicate = self.scene.copy()
        try:
            self.assertNotEqual(utils.get_scene_id(self.scene), utils.get_scene_id(duplicate))
            self.assertEqual(len(gd.GhostStore.get(duplicate)), 0)
        finally:
            bpy.data.scenes.remove(duplicate)

    def test_mesh_clear_cannot_delete_another_scenes_ghosts(self):
        bpy.ops.mesh.primitive_cube_add(); cube = bpy.context.object
        mg.generate_mesh_ghosts(bpy.context, cube, [2, 8])
        first = {o.name for o in self.scene.objects if o.get(mg.GHOST_TOOL_MESH_GHOST_KEY)}
        second = bpy.data.scenes.new('OtherScene')
        try:
            self.assertEqual(mg.clear_mesh_ghosts(SimpleNamespace(scene=second)), 0)
            self.assertTrue(first.issubset(bpy.data.objects.keys()))
        finally:
            mg.clear_mesh_ghosts(bpy.context)
            bpy.data.scenes.remove(second)
            bpy.context.view_layer.objects.active = self.obj

    def test_physics_failure_does_not_change_ghost(self):
        ghost = gd.Ghost(frame=5, local_value=1, object_name=self.obj.name, bone_name=self.bones[0], channel='location.x')
        store = gd.GhostStore.get(self.scene); store.add(ghost)
        suggestion = dict(uid=ghost.uid, suggested_value=2, suggested_position=Vector((9,9,9)))
        with patch.object(fc, 'recalculate_handles', return_value=False):
            self.assertEqual(ps.apply_suggestions([suggestion], store, self.scene), 0)
        self.assertEqual(ghost.local_value, 1)
        self.assertEqual(tuple(ghost.world_position), (0,0,0))

    def test_quaternion_channels_use_wxyz_indices(self):
        bone = self.obj.pose.bones[0]
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_quaternion = (1, 0.1, 0.2, 0.3)
        bone.keyframe_insert('rotation_quaternion', frame=1)
        for axis, index in zip('wxyz', range(4)):
            channel = 'rotation_quaternion.' + axis
            self.assertEqual(fc.resolve_fcurve(self.obj, bone.name, channel).array_index, index)
            self.assertEqual(gd._get_fcurve_for_channel(self.obj.animation_data.action, bone.name, channel, obj=self.obj).array_index, index)

    def test_diff_keeps_same_named_bones_separate(self):
        duplicate = self.obj.copy(); duplicate.data = self.obj.data.copy()
        self.scene.collection.objects.link(duplicate)
        try:
            positions = dm._collect_current_bone_positions(self.scene)
            self.assertIn((self.obj.name, self.bones[0]), positions)
            self.assertIn((duplicate.name, self.bones[0]), positions)
        finally:
            bpy.data.objects.remove(duplicate, do_unlink=True)

    def test_diff_hash_detects_slotted_curve_changes(self):
        curve = fc.resolve_fcurve(self.obj, self.bones[0], 'location.x')
        saved = fc.snapshot_fcurve(curve)
        before = gd.compute_anchor_hash(self.obj, 1)
        try:
            curve.keyframe_points[0].co.y += 1
            curve.update()
            after = gd.compute_anchor_hash(self.obj, 1)
            self.assertTrue(before)
            self.assertNotEqual(before, after)
        finally:
            fc.restore_fcurve(curve, saved)

    def test_snapshot_restores_keyframes_and_handles_exactly(self):
        ghosts = self.generate('step'); gd.GhostStore.get(self.scene).replace_all(ghosts)
        curve = fc.resolve_fcurve(self.obj, self.bones[0], 'location.x')
        saved = fc.snapshot_fcurve(curve)
        snapshots = sn.SnapshotStore.get(self.scene)
        snap, _ = snapshots.take_snapshot('Exact', self.scene)
        try:
            curve.keyframe_points[0].co.y += 4
            curve.keyframe_points.insert(12, 18)
            curve.update()
            self.assertTrue(snapshots.restore_snapshot(snap.uid, self.scene))
            self.assertEqual(fc.snapshot_fcurve(curve), saved)
        finally:
            fc.restore_fcurve(curve, saved)

    def test_shared_nested_mesh_collection_detaches_safely(self):
        bpy.ops.mesh.primitive_cube_add(); cube = bpy.context.object
        mg.generate_mesh_ghosts(bpy.context, cube, [2, 8])
        original = mg._get_mesh_collection(self.scene)
        ghost_names = {o.name for o in original.objects}
        parent = bpy.data.collections.new('GhostContainer')
        self.scene.collection.children.link(parent)
        self.scene.collection.children.unlink(original)
        parent.children.link(original)
        second = self.scene.copy()
        try:
            self.assertEqual(mg.clear_mesh_ghosts(SimpleNamespace(scene=second)), 2)
            self.assertTrue(ghost_names.issubset(bpy.data.objects.keys()))
            self.assertIs(mg._get_mesh_collection(self.scene), original)
        finally:
            bpy.data.scenes.remove(second)
            mg.clear_mesh_ghosts(bpy.context)
            bpy.context.view_layer.objects.active = self.obj

    def test_incremental_mesh_requires_same_source(self):
        bpy.ops.mesh.primitive_cube_add(); first = bpy.context.object
        mg.generate_mesh_ghosts(bpy.context, first, [2, 8])
        bpy.ops.mesh.primitive_cube_add(); second = bpy.context.object
        try:
            with patch.object(mg, '_compute_desired_mesh_frames_from_settings', return_value={2,8}):
                self.assertFalse(mg.update_mesh_ghosts_incremental(bpy.context))
        finally:
            mg.clear_mesh_ghosts(bpy.context)
            bpy.context.view_layer.objects.active = self.obj

    def test_physics_preview_deduplicates_segments_and_uses_effective_fps(self):
        from ghost_tool.session_state import SessionState
        ghosts = self.generate('step'); store = gd.GhostStore.get(self.scene)
        chain = [g for g in ghosts if g.bone_name == self.bones[0] and g.channel == 'location.x']
        store.replace_all(chain)
        ps._clear_physics_preview()
        state = SimpleNamespace(gravity_strength=9.81, gravity_axis='Z', report=lambda *a: None)
        context = SimpleNamespace(scene=self.scene, window_manager=SimpleNamespace(modal_handler_add=lambda op: None))
        original = ps.compute_parabolic_suggestion
        old_base = self.scene.render.fps_base
        self.scene.render.fps_base = 1.001
        try:
            with patch.object(ps, 'compute_parabolic_suggestion', wraps=original) as compute, patch.object(ps, 'tag_viewport_redraw'):
                self.assertEqual(ps.GHOST_OT_physics_suggest.invoke(state, context, None), {'RUNNING_MODAL'})
            self.assertEqual(compute.call_count, 1)
            self.assertAlmostEqual(compute.call_args.kwargs['frame_rate'], self.scene.render.fps / self.scene.render.fps_base)
            self.assertEqual(len(state._preview_suggestions), len(chain))
        finally:
            ps._clear_physics_preview()
            SessionState.get(self.scene).drag_active = False
            self.scene.render.fps_base = old_base

    def test_scene_selection_is_used_by_tools(self):
        from ghost_tool.session_state import SessionState
        store = gd.GhostStore.get(self.scene)
        a, b = gd.Ghost(frame=3), gd.Ghost(frame=4, is_selected=True)
        store.replace_all([a,b]); SessionState.get(self.scene).select_only(a.uid)
        self.assertEqual(store.get_selected(self.scene), [a])

    def test_api_rejects_failed_curve_update(self):
        from ghost_tool import api
        ghost = self.generate('step')[0]
        gd.GhostStore.get(self.scene).replace_all([ghost])
        old = ghost.local_value
        with patch.object(fc, 'recalculate_handles', return_value=False), patch.object(api, '_fire_ghost_moved') as callback:
            self.assertFalse(api.set_ghost_position(ghost.uid, 999))
        self.assertEqual(ghost.local_value, old)
        self.assertEqual(callback.call_count, 0)

    def test_snapshot_json_roundtrip_keeps_curve_data(self):
        ghosts = self.generate('step'); gd.GhostStore.get(self.scene).replace_all(ghosts)
        snap, _ = sn.SnapshotStore.get(self.scene).take_snapshot('Roundtrip', self.scene)
        loaded = sn.GhostSnapshot.from_dict(json.loads(json.dumps(snap.to_dict())))
        self.assertEqual(json.dumps(loaded.curve_data), json.dumps(snap.curve_data))
        self.assertTrue(loaded.curve_data)
        bad = snap.to_dict(); bad['curve_data'][0]['keys'][0]['interpolation'] = 'INVALID'
        self.assertFalse(self.import_data({'ghosts': [], 'snapshots': [bad]}))

    def test_archetype_bake_rolls_back_on_failure(self):
        curve = fc.resolve_fcurve(self.obj, '', 'location.x')
        if curve is None:
            self.obj.keyframe_insert('location', frame=1)
            self.obj.keyframe_insert('location', frame=21)
            curve = fc.resolve_fcurve(self.obj, '', 'location.x')
        saved = fc.snapshot_fcurve(curve)
        state = SimpleNamespace(report=lambda *args: None,
            _clear_channel_keys=ps.GHOST_OT_archetype_bake._clear_channel_keys,
            _maybe_regenerate_ghosts=lambda *a: None)
        self.settings.archetype_start_frame = 2; self.settings.archetype_end_frame = 8
        context = SimpleNamespace(active_object=self.obj, active_pose_bone=None, scene=self.scene)
        def fail(t):
            if t > 0.3: raise ValueError('injected archetype failure')
            return t
        with patch.dict(ps.ARCHETYPES, {self.settings.archetype_active: fail}), patch.object(bpy.ops.ed, 'undo_push'):
            self.assertEqual(ps.GHOST_OT_archetype_bake.execute(state, context), {'CANCELLED'})
        self.assertEqual(fc.snapshot_fcurve(curve), saved)

    def test_keyframe_restore_rejects_bad_data_before_writing(self):
        curve = fc.resolve_fcurve(self.obj, self.bones[0], 'location.x')
        saved = fc.snapshot_fcurve(curve)
        import copy
        malformed = copy.deepcopy(saved); malformed[0]['handle_left_type'] = 'BOGUS'
        self.assertFalse(fc.restore_fcurve(curve, malformed))
        self.assertEqual(fc.snapshot_fcurve(curve), saved)

    def test_quoted_bone_names_resolve(self):
        bone = self.obj.pose.bones[0]; previous = bone.name
        try:
            bone.name = 'Bone "quoted" \\ name'
            bone.keyframe_insert('location', frame=1)
            self.assertIsNotNone(fc.resolve_fcurve(self.obj, bone.name, 'location.x'))
            self.assertIsNotNone(gd._get_fcurve_for_channel(self.obj.animation_data.action, bone.name, 'location.x', obj=self.obj))
        finally:
            bone.name = previous

    def test_shape_key_frames_are_included_in_mesh_keyframe_mode(self):
        bpy.ops.mesh.primitive_cube_add(); obj = bpy.context.object
        obj.shape_key_add(name='Basis')
        shape = obj.shape_key_add(name='Expression')
        shape.value = 0; shape.keyframe_insert('value', frame=3)
        shape.value = 1; shape.keyframe_insert('value', frame=9)
        try:
            self.assertEqual(mg._get_keyframe_frames_for_object(obj), [3,9])
        finally:
            bpy.context.view_layer.objects.active = self.obj

    def test_export_is_atomic_and_roundtrips(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='ghost-export-test-') as temp:
            path = Path(temp) / 'ghosts.json'
            store = gd.GhostStore.get(self.scene)
            store.replace_all(self.generate('step'))
            self.assertTrue(ei.export_ghosts(str(path), self.scene))
            original = path.read_bytes()
            with patch.object(ei.os, 'replace', side_effect=OSError('injected replacement failure')):
                self.assertFalse(ei.export_ghosts(str(path), self.scene))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(temp).glob('*.tmp')), [])
            store.clear()
            self.assertTrue(ei.import_ghosts(str(path), self.scene))
            self.assertGreater(len(store), 0)

    def test_all_easing_presets_preserve_key_positions(self):
        from ghost_tool import easing_presets as ep
        curve = fc.resolve_fcurve(self.obj, self.bones[0], 'location.x')
        saved = fc.snapshot_fcurve(curve)
        try:
            for name, _label, _description in ep.build_preset_menu_items():
                if not name: continue
                self.assertTrue(ep.apply_preset_to_range(curve, 1, 21, name))
                self.assertEqual([tuple(k.co) for k in curve.keyframe_points], [tuple(k['co']) for k in saved])
                fc.restore_fcurve(curve, saved)
        finally:
            fc.restore_fcurve(curve, saved)

    def test_nla_guard_respects_muted_tracks(self):
        track = self.obj.animation_data.nla_tracks.new()
        strip = track.strips.new('Audit strip', 1, self.obj.animation_data.action)
        try:
            self.assertTrue(ps._has_active_nla_strips(self.obj))
            track.mute = True
            self.assertFalse(ps._has_active_nla_strips(self.obj))
        finally:
            self.obj.animation_data.nla_tracks.remove(track)

    def test_y_actual_undo_redo_restores_curve_and_invalidates_cache(self):
        from ghost_tool import ghost_pipeline as gp
        object_name = self.obj.name
        curve = fc.resolve_fcurve(self.obj, self.bones[0], 'location.x')
        original = curve.keyframe_points[0].co.y
        bpy.context.preferences.edit.use_global_undo = True
        bpy.ops.ed.undo_push(message='Ghost regression before edit')
        curve.keyframe_points[0].co.y = original + 4
        curve.update()
        bpy.ops.ed.undo_push(message='Ghost regression after edit')
        bpy.ops.ed.undo()
        self.__class__.obj = bpy.data.objects[object_name]
        curve = fc.resolve_fcurve(self.obj, self.bones[0], 'location.x')
        self.assertAlmostEqual(curve.keyframe_points[0].co.y, original)
        self.assertTrue(gp.GhostPipeline.get(bpy.context.scene)._get_cache().is_dirty)
        bpy.ops.ed.redo()
        self.__class__.obj = bpy.data.objects[object_name]
        curve = fc.resolve_fcurve(self.obj, self.bones[0], 'location.x')
        self.assertAlmostEqual(curve.keyframe_points[0].co.y, original + 4, places=6)
        curve.keyframe_points[0].co.y = original
        curve.update()

    def test_physics_preview_does_not_leak_to_other_scenes(self):
        ps._set_physics_preview([{'suggested_position': Vector((1,2,3))}])
        other = bpy.data.scenes.new('PreviewOtherScene')
        try:
            self.assertTrue(ps.get_physics_preview())
            with bpy.context.temp_override(scene=other):
                self.assertFalse(ps.get_physics_preview())
            self.assertTrue(ps.get_physics_preview())
        finally:
            ps._clear_physics_preview()
            bpy.data.scenes.remove(other)

    def test_z_file_load_retains_handlers_and_clears_runtime_state(self):
        import tempfile
        from ghost_tool import ghost_pipeline as gp
        with tempfile.TemporaryDirectory(prefix='ghost-load-test-') as temp:
            path = str(Path(temp) / 'fixture.blend')
            bpy.ops.wm.save_as_mainfile(filepath=path)
            gd.GhostStore.get(bpy.context.scene).add(gd.Ghost(frame=99))
            bpy.ops.wm.open_mainfile(filepath=path)
            self.assertIn(gp._on_frame_change_pipeline, bpy.app.handlers.frame_change_post)
            self.assertIn(gp._on_depsgraph_update_pipeline, bpy.app.handlers.depsgraph_update_post)
            self.assertIn(mg._on_frame_change, bpy.app.handlers.frame_change_post)
            self.assertEqual(len(gd.GhostStore.get(bpy.context.scene)), 0)

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BroaderCorrectness))
    print('GHOST_CORRECTNESS_RESULT: ' + ('PASS' if result.wasSuccessful() else 'FAIL'), flush=True)
    if not result.wasSuccessful(): raise RuntimeError('Ghost correctness checks failed')
