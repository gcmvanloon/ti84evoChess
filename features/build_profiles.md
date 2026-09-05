# Build profiles and compile-time features

## Status

This document is the implementation brief for configuration-driven calculator
builds. Implement it incrementally. A milestone is complete only when its
enabled behavior is unchanged, disabled code is absent from generated source,
tests pass, and the complete checked-in build workflow succeeds.

The feature system exists to compose builds that fit within the TI-84 Evo-T's
constrained parser/compiler memory. It is not a runtime preferences system.
Disabled code must be removed before `python-minifier` and must contribute no
AST nodes, statements, imports, globals, functions, instrumentation, or input
handling to the calculator build.

Follow `AGENTS.md` and `PREPROCESSOR.md` throughout this work. In particular,
`chess_evo.py` remains the only source of truth, `chess_evo_min.py` remains
generated and ignored, and AST complexity matters more than source bytes alone.

## Settled decisions

- Store all profiles in the root-level file `build_profiles.json`.
- Use JSON from Python's standard library; do not add a configuration parser
  dependency.
- Support multiple named profiles in that one file.
- Do not support inheritance or an `extends` property. Every profile is
  resolved independently and can be understood in isolation.
- Do not implement a generalized feature-dependency system. Relationships are
  expressed only through the fixed configuration shape and feature-specific
  validation, such as debug metrics nested beneath `debug_panel`.
- A root `default_profile` property selects the normal development build.
- An omitted Boolean feature is `false`.
- An omitted debug metric is `false`.
- `piece_style` is mandatory in every profile. Its initial valid values are
  `"graphical"` and `"glyphs"`.
- The `debug` profile must use `"glyphs"` to reserve AST budget for the debug
  panel and its selected instrumentation.
- Keep debug metrics hierarchically nested under the debug panel.
- Do not configure a separate debug-panel `enabled` value. The panel is a
  derived feature and is enabled automatically when one or more of its metrics
  resolve to true.
- The normal build processes only its selected profile and prints its metrics
  directly. Build output is the comparison mechanism; no CSV history is kept.

## Configuration shape

The intended shape is:

```json
{
  "default_profile": "release",
  "profiles": {
    "release": {
      "piece_style": "graphical",
      "features": {
        "show_captures": true,
        "material_advantage": true,
        "move_counter": true,
        "undo_last_move": true
      }
    },
    "debug": {
      "piece_style": "glyphs",
      "features": {
        "debug_panel": {
          "metrics": {
            "last_key": true,
            "free_memory": true,
            "ai_time": true,
            "ai_evaluated_moves": true,
            "ai_candidates": true
          }
        },
        "show_captures": true,
        "material_advantage": true,
        "move_counter": true,
        "undo_last_move": true
      }
    }
  }
}
```

The exact enabled features in the initial committed profiles may be adjusted as
features are migrated, but the following final properties are required:

- `release` uses graphical pieces unless deliberately changed later.
- `debug` uses glyph pieces.
- Each profile explicitly names its piece style.
- Boolean omissions resolve to false rather than inheriting or using a hidden
  default.

The following is therefore a valid minimal profile value:

```json
{
  "piece_style": "glyphs",
  "features": {
    "debug_panel": {
      "metrics": {
        "free_memory": true
      }
    }
  }
}
```

The free-memory metric resolves to true and therefore enables the debug panel.
All other features and debug metrics resolve to false in that example.

## Configuration validation

Fail before preprocessing with a clear property path and message when:

- the root is not a JSON object;
- `default_profile` is missing, is not a string, or names no profile;
- `profiles` is missing, is not an object, or is empty;
- a profile name is invalid;
- a profile is not an object;
- `piece_style` is missing or is not one of the supported values;
- `features`, `debug_panel`, or `metrics` has the wrong type;
- a Boolean setting is not actually a JSON Boolean;
- an unknown property, feature, metric, or piece style is present;
- the JSON contains a duplicate object key; or
- `debug_panel` contains an `enabled` property or anything other than its
  supported nested configuration.

Restrict profile names to a filesystem-safe, documented form, such as lowercase
ASCII letters, digits, underscores, and hyphens. This keeps command-line use
predictable.

Use strict duplicate-key detection when loading JSON. Python's default JSON
object behavior silently keeps the last duplicate, which is unsuitable for a
reproducible build configuration.

Print the selected profile, piece style, and resolved enabled features at the
start of each build. Do not silently correct invalid combinations.

## Feature model

Top-level features are independent. The loader and preprocessor must not support
dependency declarations, dependency graphs, `requires` metadata, or automatic
enabling of related top-level features. Shared update locations or similar
bookkeeping do not establish a dependency. A parent state derived directly from
its nested configuration, as with `debug_panel`, is part of the fixed schema and
is not a dependency relationship.

Where a relationship is intrinsic to the configuration model, represent it
directly in the schema and validate it with ordinary feature-specific code. The
debug metrics are the initial example: they are properties nested beneath
`debug_panel`, and the panel's resolved state is the logical OR of all its
resolved metric values. This rule does not imply or require a reusable
dependency framework.

### Debug panel

`debug_panel` is a derived parent feature with independently selectable metrics:

- `last_key`
- `free_memory`
- `ai_time`
- `ai_evaluated_moves`
- `ai_candidates`

Turning off a metric must remove its complete cost, not just its displayed row.
For example:

- `free_memory` controls the `gc` import and `gc.mem_free()` calls;
- `ai_time` controls the `time` import, timing state, timing calls, formatting,
  and drawing;
- `ai_evaluated_moves` controls its state, search-time increment, formatting,
  and drawing;
- `ai_candidates` controls the `RT` random-candidate re-search count,
  formatting, and drawing; and
- `last_key` controls the key-display refresh and drawing.

When every metric is false or omitted, the debug panel resolves to false and
the build must remove the complete panel, TRACE toggle path, debug state, and
every debug metric. When one or more metrics are true, the panel resolves to
true automatically. There is no independently configurable panel state and no
contradictory panel/metric combination to validate.

Enabled metric rows should be composed without requiring separate hand-written
panel implementations for every combination. Any row-composition mechanism
must itself disappear or become structurally minimal after preprocessing.

### Capture panel and material counter

These are independent features.

The material counter is derived from pieces remaining on `board` by
`update_material_state()`. It does not require capture history.

The `show_captures` feature separately records captured-piece counts in
`white_captures` and `black_captures`. It does not require the material advantage.

They currently share some move-update sites. Feature selection must retain only
the bookkeeping and drawing required by the selected combination.

### Move counter

The move counter owns its state, increments, reset behavior, display, and any
player-undo adjustment. It is independent of the capture and material panels.

### Piece style

Piece rendering is a required build-time variant, not a Boolean feature.
Exactly one of these implementations must remain in generated source:

- `graphical`: the existing native-primitive silhouettes;
- `glyphs`: simple character-based pieces with a materially smaller generated
  AST footprint.

Both styles must preserve board geometry, the 16x16 piece boundary, incremental
redraw behavior, and highlight separation. The unused implementation must be
physically absent from the preprocessed build.

### Undo last move

`undo_last_move` controls only the user-visible ability to undo completed moves.
When disabled it may remove DEL handling, `undo_played_moves()`, retained
`player_move_state`/`ai_move_state`, and gameplay-only rollback data.

Do not remove the underlying search rollback mechanism. Minimax relies on
`undo_move()` to reverse simulated moves regardless of whether player undo is
enabled.

Undo has conditional integration points rather than dependencies:

- `undo_last_move` plus `show_captures` must roll back capture history;
- `undo_last_move` plus `material_advantage` must restore the visible material
  result after the board is restored; and
- `undo_last_move` plus `move_counter` must adjust and redraw the move count.

When either side of an integration is disabled, its integration code and
state must also be absent.

## Preprocessor architecture

Feature selection belongs in a new, independently tested AST pass. Do not add
feature semantics to `const()` and do not use textual `#ifdef` processing or
naive source replacement.

The intended order is:

```text
chess_evo.py
  -> SelectBuildFeaturesPass
  -> InlineConstantsPass
  -> python-minifier
  -> chess_evo_min.py
```

Use valid Python build markers in the readable source. A likely interface is:

```python
if build_feature("debug_panel"):
    ...

if build_feature("debug_panel.metrics.free_memory"):
    ...

if build_choice("piece_style", "graphical"):
    ...
else:
    ...
```

The precise marker API may be refined during implementation, but it must:

- keep `chess_evo.py` readable and executable with documented source defaults;
- be statically recognizable and strictly validated;
- permit only literal, known option names and choice values;
- remove enabled marker branches by splicing in their bodies;
- remove disabled branches completely;
- remove the marker definitions from generated source;
- reject unsupported marker placement or use; and
- leave no runtime feature tests in calculator output.

The calculator must never parse a disabled branch. Replacing a feature
condition with `False` while retaining the branch in generated source is not
sufficient.

Preserve the preprocessor's generic input/output command-line use. Configuration
and profile selection may be optional arguments, with the checked-in build
script passing them explicitly. Keep parsing, configuration resolution, pass
execution, unparsing, compile checking, and atomic output separate.

## Normal build workflow

The **release build** task remains the default VS Code build task, and the
separate **debug build** task selects the debug profile. Both tasks pass their
profile explicitly to the build script. Each task must:

1. read `build_profiles.json`;
2. pass its named profile explicitly rather than relying on `default_profile`;
3. validate and resolve only the selected profile;
4. preprocess, minify, and compile-check that profile;
5. write `chess_evo_min.py` atomically through the existing workflow;
6. print selected configuration plus clearly labeled byte and AST metrics.

Support an explicit terminal override such as:

```bash
bash tools/build_minified.sh --profile debug
```

The build script may still use `default_profile` when invoked directly without
`--profile`, but checked-in VS Code tasks must be explicit. An ordinary build
must process only one profile. It is the fast, intermittent development path
for the selected profile.

## Build metrics

Each normal build prints the selected profile and preprocessing results,
followed by readable, preprocessed, and minified byte counts, size reduction,
minified AST nodes, and minified statements. Each metric is printed on its own
labeled line so results can be compared directly between builds. The project
does not store a separate metrics history.

## Incremental implementation plan

Keep every commit or milestone buildable. Do not wrap all features in one large
change.

1. **Configuration and validation**
   - Add `build_profiles.json` with profiles that describe only combinations
     supported at that milestone.
   - Add focused loader/resolver tests, including duplicate keys, omitted
     Booleans, mandatory `piece_style`, unknown keys, and debug validation.

2. **Generic AST feature selection**
   - Add marker validation and branch removal as a separate pass.
   - Test enabled/disabled branches, `else` selection, nested markers, invalid
     calls, unknown features, and complete marker removal.
   - Verify the feature pass runs before constant inlining.

3. **Profile-specific builds**
   - Make the normal build select one profile.
   - Add explicit release/debug VS Code build tasks.
   - Print labeled structural and size metrics for direct comparison.

4. **Piece-style variant**
   - Preserve the existing graphical implementation exactly when selected.
   - Add the glyph implementation and ensure only one renderer remains.
   - Establish the required glyph-based `debug` profile.

5. **Debug panel parent feature**
   - Remove or retain the complete panel, state, and TRACE interaction.
   - Preserve current behavior when enabled.

6. **Debug metrics, one at a time**
   - Migrate last key, free memory, AI time, and evaluated moves separately.
   - Measure each metric's true instrumentation and AST cost.

7. **Display/gameplay features, one at a time**
   - Migrate capture panel, material counter, move counter, and player undo in
     small changes.
   - Test all relevant enabled/disabled combinations and conditional
     integrations without declaring false dependencies.

The exact order after the generic infrastructure may change when measurements
show a safer boundary, but do not create a committed profile that selects an
implementation that does not yet exist.

## Testing and acceptance criteria

Add focused desktop tests at each milestone. At minimum, cover:

- strict configuration parsing and resolution;
- every valid piece style and rejected invalid styles;
- default-profile selection and explicit override;
- disabled branches being absent from the preprocessed AST/text;
- enabled behavior matching readable-source behavior;
- marker definitions and calls being absent from generated source;
- independent capture/material combinations;
- every debug metric alone and in useful combinations;
- conditional undo integrations;
- normal builds selecting and reporting only the requested profile; and
- successful builds replacing `chess_evo_min.py` only after validation.

For every calculator-code milestone:

1. run the preprocessor regression tests;
2. run the normal default-profile build;
3. review generated code for disabled-feature residue;
4. compare labeled bytes, AST nodes, and statements in build output; and
5. test affected profiles on a physical TI-84 Evo-T.

Desktop success does not validate Evo-T parser memory, graphics behavior, or
performance. Hardware validation remains mandatory before treating a profile
as proven to fit.

## Non-goals

- Runtime feature toggles on the calculator.
- Multiple hand-maintained versions of `chess_evo.py`.
- Hand-editing or committing `chess_evo_min.py`.
- YAML or a third-party configuration dependency.
- Profile inheritance, recursive merging, or implicit feature enablement.
- A generalized feature-dependency declaration or resolution system.
- Text-based conditional compilation.
- Removing minimax's internal move rollback when player undo is disabled.
- Assuming capture-panel and material-counter dependence merely because both
  currently update after captures.
