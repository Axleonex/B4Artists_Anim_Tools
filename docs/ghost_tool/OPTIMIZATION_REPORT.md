# Ghost Tool 3.3.2 optimization audit

Historical optimization results. The current 3.3.3 candidate and broader fixes are documented in [CORRECTNESS_REPORT.md](CORRECTNESS_REPORT.md).

Date: 2026-09-05. Baseline: commit `184d894`, Ghost Tool 3.3.1.
Working checkout: `X:/Scripting Attempts/B4Artists_Tools/B4Artists_Anim_Tools_github`.
Target remote: `https://github.com/Axleonex/B4Artists_Anim_Tools`.

## Results

| Measurement | Before | After | Interpretation |
|---|---:|---:|---|
| Generate 2,280 point ghosts: 40 bones, 19 sample frames, 3 location channels | 213.21 ms | 28.73 ms | 7.42x faster; 86.5% less time |
| Frame changes in that generation pass, including restoration | 761 | 20 | Each requested frame evaluated once for all bones |
| Internal live-regeneration scheduling, 12 bones and 4 sample frames | 49 calls | 0 calls | Sampling no longer schedules another bake |
| CPU marker preparation, 2,280 markers, unchanged LEVEL view | 30.80 ms uncached | 1.06 ms cached | Same geometry builder compared with warm cache |
| Marker batch builds across 20 unchanged redraw preparations | 20 | 0 | Reuses the existing batches |

Generation times are medians of three measured runs following one warm-up. The marker comparison uses 20 runs after warm-up and replaces GPU upload with a payload collector. It measures CPU geometry/batch preparation, **not viewport FPS or GPU driver time**. Timings are specific to this desktop and fixture; complex modifiers, constraints, large meshes, view changes, and actual animation edits still require evaluation or rebuilding.

## Fixed issues

- **Repeated frame evaluation:** all three point generators now gather every requested bone's evaluated position during one frame visit. The cache is local to each pass and supports constrained poses, object origins, and fractional/negative frames.
- **Regeneration feedback:** internal sampling suppresses Ghost Tool's frame/depsgraph scheduling and mesh appearance handlers. User-driven updates remain enabled. Throttled timers return a delay instead of registering themselves again.
- **Playhead loss:** point and mesh sampling restore both frame and subframe in exception-safe cleanup. The prohibition on sampling inside draw callbacks remains enforced.
- **Point-store data loss:** failed manual/preview evaluations preserve existing ghosts; `clear_existing=False` now appends. Cache metadata is updated after successful evaluation.
- **Stale range/key caches:** removing a level invalidates the store range/version. Sorted-key caching checks current frame positions and keeps only index permutations, avoiding stale Keyframe RNA references and channel collisions across action slots. It is bounded to 512 curves.
- **API refresh:** external curve edits are sampled using a fresh, per-pass world-position cache; refresh also benefits from batching and playhead restoration.
- **Viewport rebuild cost:** unchanged base marker batches are reused. Cache inputs include actual ghost positions/frames/levels, colors, visibility, radius, playhead, billboard axes, and viewport context. In-place drag/API edits invalidate correctly. Only one viewport's batches are retained. Selection, hover, arcs, snapshots, physics overlays, and diff drawing remain separate and available.
- **Preview cache identity:** archetype preview invalidation includes the store identity and actual position/frame data.
- **Custom range callback errors:** direct callback references replace lambdas that raised NameError during RNA property updates.
- **Drag state:** live timers defer while a drag holds references to ghosts. Cancellation restores values for falloff neighbors and other selected ghosts as well as the primary ghost.
- **Bforartists selection compatibility:** supports selection on PoseBone in the installed 5.x runtime and the older Bone selection property.
- **Mesh correctness and cleanup:** fractional mesh sampling, evaluated-mesh release on conversion failures, preservation of loose edges, connectivity-aware topology checks, user colors during incremental updates, initial visibility/base alpha, cleanup of unused outline materials, and preservation of untagged objects in the ghost collection.
- **Lifecycle:** pending live/forced timers, marker batches, preview keys, and key/world-position caches are released on teardown; undo also clears the world-position cache.

No animation tools, operator IDs, or settings were removed. Anim Assist source and its release archives were not edited. The Ghost Tool remains independently installable; this update does not add the future Machine Learning product or Cascadeur connector.

## Validation

- 20 regression tests pass against both the working source and the packaged 3.3.2 ZIP inside Bforartists, including all three generation modes, evaluated positions, constrained bones, fractional/negative sampling, error restoration, append/failure behavior, live generation, drag deferral/cancellation, all five marker color modes and cache invalidation, mesh generation/incremental topology, custom range callbacks, external API refresh, and timer cleanup.
- Existing `tests/smoke_bforartists.py` passes its assertions with Anim Assist and Ghost Tool registered together.
- All four existing tooltip coverage checks pass; Python syntax and `git diff --check` pass.
- Source-interface comparison against HEAD confirms the same 35 existing operator/panel identifiers and 113 property names.
- The release archive is checked byte-for-byte against the current Ghost Tool source.

Runtime: `X:/5.1.0/bforartists.exe`, Bforartists 5.1.0 distribution reporting underlying Blender 5.2.0 Alpha, hash `dd23ab17120d`, built 2026-03-25.

**Runtime caveat:** this executable crashes in `ucrtbase.dll` during shutdown and exits with code 1 even for `--background --factory-startup --python-expr "print('EMPTY_CONTROL_OK')"` with no addon imported. Test assertions finish successfully before this identical shutdown failure. These results are assertion passes, not clean process-exit passes. No installed application binaries or settings were changed to hide the crash.

Interactive mouse/keyboard feel, final GPU rendering/FPS, and every production-rig configuration were not manually verified. No claim of zero latency or universal feature coverage is made. Existing mesh rebuilds remain incremental/destructive operations; restoration of the playhead on error does not imply a transaction for every scene object.

## Reproduce

Use a disposable, factory-startup Bforartists process. These scripts generate their own scene fixtures.

```powershell
# [PowerShell] Run from the repository root
& 'X:\5.1.0\bforartists.exe' --background --factory-startup --python-exit-code 1 --python tests/test_ghost_regressions.py
& 'X:\5.1.0\bforartists.exe' --background --factory-startup --python-exit-code 1 --python tests/benchmark_ghost.py
& 'X:\5.1.0\bforartists.exe' --background --factory-startup --python-exit-code 1 --python tests/smoke_bforartists.py
```

For the original generation timing, the generation section of the benchmark was run against untouched 3.3.1 before adding the marker-cache benchmark section. Compare the explicit `GHOST_REGRESSION_RESULT`, unittest results, and smoke success message separately from the known executable shutdown problem.

## Execution decision and delivery

The required `prime-code-execute.py` routing entry was attempted. Windows preflight returned `REMOTE_EXECUTOR_REQUIRED`; the approved SSH/WSL preflight returned `BLOCKED` because `/mnt/x/Scripting Attempts/B4Artists_Tools/B4Artists_Anim_Tools_github` does not exist on the executor. A separate remote directory check returned `remote_project_exists=False`; OMP itself reported READY. No patch had been applied by the executor. Recommended/actual execution lanes were not emitted by the blocked preflight.

Decision: `DEGRADED_NATIVE_CONTINUE` under the current canonical recoverable pre-host-apply infrastructure fallback policy. Local work was limited to Ghost Tool, its regression/benchmark scripts, this audit report, and Ghost Tool release metadata/packaging. The installed runtime was used for deterministic validation. No paid API route, remote repository copy, or provider change was used.

Deliverable: `releases/b4_ghost_tool_v3.3.2.zip`. Existing release archives remain available. Changes are local and uncommitted; no commit, merge, push, or GitHub publication was performed.

Package SHA-256: `baf88562eb34202bce96183cb7c5e57b884a4913543058e4016d9a74ca3a88da`.
