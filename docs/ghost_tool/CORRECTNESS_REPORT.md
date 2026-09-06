# Ghost Tool 3.3.3 broader correctness pass

This update includes the 3.3.2 optimization work and a broader correctness audit. It is a local, uncommitted candidate for B4Artists_Anim_Tools; Anim Assist is unchanged. The earlier 3.3.2 ZIP is retained as an archive, not the current recommendation.

## Scope and evidence

The audit searched the 20 Ghost Tool source modules for shared state, action access, selection ownership, keyframe writes, serialization, handler lifecycle, and repeated work. Runtime tests exercise the affected paths; static interface checks confirm the same 35 existing operator/panel identifiers and 113 property names. This is not a proof that every possible rig or UI interaction is correct.

| Area reviewed | Changes / verification |
|---|---|
| Import/export | Validate both stores before replacement; reject malformed roots, nonfinite values, duplicate IDs and invalid nested snapshots; remap snapshot references with ghosts; write exports through atomic replacement. Invalid input preserves existing data. Actual disk roundtrip and injected replacement failure tested. |
| Snapshot/curve restoration | New snapshots capture full keys, times, handles, interpolation, easing and easing parameters for involved channels. Restore reconstructs the captured curve and removes subsequently added keys. Validation precedes mutation; multi-curve restore rolls back on failure. JSON retains this data. |
| Mesh onion skins | Scene-local collection lookup; detach shared root or nested collection paths and copy ghost objects/materials before mutation. Clearing scene B preserves scene A. Incremental update rejects a different source mesh. Keyframe-only mode includes shape-key animations. Cleanup targets materials belonging to removed ghosts. |
| Point generation / caches | Previous batching, playhead restoration, cache invalidation, timer and draw guards remain covered by the original 20 tests. Copied scenes now have independent transient store identities. |
| Visual Diff | Bone keys include armature identity; changing the active armature cannot redirect the anchor hash. Hashing supports slotted actions and includes key/handle changes. Staleness hashing is capped at 10 Hz, separate from geometry drawing. |
| Physics / archetypes | Failed curve updates no longer report success or change the displayed ghost; duplicate suggestions apply once; pinned ghosts and active NLA are guarded. Preview work runs once per segment, uses fps/fps_base, stays in its scene, and defers live regeneration. Archetype baking uses fast key insertion, reacquires keys during deletion, and restores the original curve on failure. |
| Channel mapping | Quaternion W/X/Y/Z uses indices 0/1/2/3. Quoted/backslashed bone names are escaped in RNA paths. |
| Selection / API / dragging | Easing and physics use SessionState selection. API curve-update failure preserves ghost values and suppresses success callbacks. Modal error cleanup releases the live-regeneration hold. |
| File lifecycle / undo | Persistent live and appearance handlers survive file opening; file-load reset clears transient stores and pending work. Undo/redo invalidates caches and schedules refresh. Actual save/open and actual undo/redo tested. |
| Easing / UI / other overlays | All easing presets tested for preserving key positions. Existing tooltip/help and combined Anim Assist registration smoke checks retained. All tool identifiers/properties preserved. The original marker cache tests cover all five color modes. |

The new 10-case baseline initially produced 12 assertion failures and one error across subtests, while the earlier performance regressions remained passing. Additional tests cover the follow-up edge cases. The final suite has **46 tests**, including the original 20, rather than 46 plus 20.

## Compatibility and behavioral details

- New JSON exports use format 1.1.0; format 1.0.0 remains readable. New snapshots carry optional curve_data. Old snapshots do not contain original keys/handles and retain their approximate sample-based restoration behavior.
- Exact snapshots capture keyframe data for involved channels, not the entire scene, modifiers, constraints, or NLA stack. Missing original curves abort exact restore before modification.
- Ghosts, snapshots, and previews remain transient Python state. Use JSON export/import for persistence. Opening another file clears transient state instead of retaining stale references.
- Bone selection supports both the installed PoseBone API and older Bone selection storage.
- Physics suggestions remain an artistic heuristic. Approximate physics/bookend previews are not a complete physical simulation or a guarantee of exact results on arbitrarily transformed rigs. This pass does not turn Ghost Tool into the proposed Machine Learning tool.

## Validation and performance

Runtime: X:/5.1.0/bforartists.exe, Bforartists 5.1.0 distribution with Blender 5.2.0 Alpha core, hash dd23ab17120d. Assertions pass before the already-isolated ucrtbase.dll shutdown crash. This executable also crashes on shutdown in an empty factory-startup process without the addon. Process exit is therefore **not** being represented as clean.

Back-to-back generation comparisons on the same 40-bone, 19-frame, 2,280-marker fixture:

| Candidate | Median generation times from two processes | Frame changes per pass |
|---|---|---:|
| Archived 3.3.2 | 32.17 ms; 32.65 ms | 20 |
| 3.3.3 candidate | 34.03 ms; 32.17 ms | 20 |

Warm marker preparation in the candidate measured 1.075?1.081 ms, with zero batch rebuilds across 20 unchanged preparations; uncached preparation measured 36.49?37.43 ms. These are CPU preparation timings with GPU upload replaced by a payload collector, not viewport FPS. An earlier noisier candidate run measured 49.82 ms generation; the repeated interleaved comparison above is included to avoid hiding that variability. The original unoptimized generation measurement was 213.21 ms and 761 frame changes.

Commands, from the repository root:

```powershell
# [PowerShell]
& 'X:\5.1.0\bforartists.exe' --background --factory-startup --python-exit-code 1 --python tests/test_ghost_correctness.py
& 'X:\5.1.0\bforartists.exe' --background --factory-startup --python-exit-code 1 --python tests/benchmark_ghost.py
& 'X:\5.1.0\bforartists.exe' --background --factory-startup --python-exit-code 1 --python tests/smoke_bforartists.py
```

Interactive viewport rendering, sustained mouse/keyboard usage, GPU-driver behavior, and production-scale rigs remain manual validation limits. No claim of universal correctness or zero latency is made.

## Execution record

Expanded scope: ghost_tool, tests, docs/ghost_tool, README.md, releases/b4_ghost_tool_v3.3.3.zip. User explicitly authorized the broader bug-fix pass. No commits, merges, pushes, deployments, credential changes, or paid API calls.

The required prime-code-execute.py SSH/WSL preflight was attempted again. OMP reported READY; preflight returned BLOCKED for the executor workspace /mnt/x/Scripting Attempts/B4Artists_Tools/B4Artists_Anim_Tools_github, which the earlier verified directory check established is unavailable there. No executor patch was applied. Recommended/actual lanes were not emitted. Continued with DEGRADED_NATIVE_CONTINUE under the canonical automatic native continuation rule for recoverable pre-host-apply infrastructure failures. No fallback approval was required.

Package: `releases/b4_ghost_tool_v3.3.3.zip`. SHA-256: `e5b298611abf22cfa0fb47c7cb058b48c252e575d634fc09825e7cb2022d0bdb`.

Final verification: all 46 tests passed when importing the addon directly from the 3.3.3 ZIP. The unchanged combined Anim Assist/Ghost Tool smoke test passed. All four tooltip tests, syntax parsing, retained-interface comparison, and diff whitespace checks passed. Each Bforartists process still exhibited the separately documented shutdown crash after successful assertions.
