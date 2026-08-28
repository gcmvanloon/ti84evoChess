# AST preprocessor

The desktop AST preprocessor reduces calculator compilation pressure while
keeping `chess_evo.py` readable. The build order is:

```text
chess_evo.py
  -> SelectBuildFeaturesPass
  -> InlineConstantsPass
  -> python-minifier
  -> chess_evo_min.py
```

The preprocessed file is temporary build output. It is not source and must not
be edited, committed, or uploaded instead of the final minified build.

## Architecture

`tools/ast_preprocessor.py` parses source with Python's built-in `ast` module,
runs a `PassPipeline`, unparses and compile-checks the transformed tree, and
writes the requested output atomically. Parsing, profile resolution, pass
execution, unparsing, compile checking, and file output remain separate.

Each optimization must be an independently testable pass implementing the
existing pass interface. Add new passes explicitly to the pipeline in the
order required by their inputs and outputs. Preserve the generic input/output
command-line interface.

Pass order matters. Feature selection runs first so disabled code never reaches
constant inlining or `python-minifier`. It also allows a `const()` declaration
inside an enabled feature branch to become a module-level declaration before
`InlineConstantsPass` examines it.

### Configuration boundary

Profile configuration and AST transformation are connected through one
explicit value, `ResolvedProfile`:

```text
build_profiles.json
  -> tools/build_profiles.py
     (load JSON, validate schema, resolve defaults and derived features)
  -> ResolvedProfile
  -> tools/ast_preprocessor.py
  -> SelectBuildFeaturesPass(resolved_profile)
```

`build_profiles.py` owns JSON parsing, known feature and choice definitions,
profile-name rules, and configuration error paths. It does not parse or modify
`chess_evo.py`.

`ast_preprocessor.py` imports the resolved-profile type and loader. Its CLI
loads one `ResolvedProfile` before parsing calculator source, then passes that
value into `SelectBuildFeaturesPass`. The pass consumes resolved Booleans and
choices; it never reads JSON or applies profile defaults itself. Keeping this
boundary explicit makes profile validation independently testable and prevents
configuration semantics from leaking into the AST pipeline.

These are not two scripts connected by an intermediate file or subprocess.
During preprocessing, `ast_preprocessor.py` imports `build_profiles.py` as a
normal Python module and calls `load_resolved_profile()`. That function returns
the `ResolvedProfile` object directly in memory:

```python
from build_profiles import load_resolved_profile

profile = load_resolved_profile(config_path, profile_name)
tree = SelectBuildFeaturesPass(profile).run(tree)
```

Both files live in `tools/` because they are parts of the same desktop build
tool. When Python runs `tools/ast_preprocessor.py`, its containing `tools/`
directory is available for sibling imports, so no generic `modules/` directory
is needed. `build_profiles.py` also exposes a small CLI for the profile metrics
workflow, but that does not change its normal role as an imported preprocessing
support module.

## Pass 1: `SelectBuildFeaturesPass`

### Purpose

`SelectBuildFeaturesPass` turns one readable source file into the source for
one selected build profile. Features are compile-time selections, not runtime
preferences. The pass:

1. validates every `build_feature()` and `build_choice()` marker;
2. selects the configured branch;
3. splices the selected statements into their parent scope;
4. removes the unselected branch completely;
5. removes `if` statements and functions left empty by feature selection; and
6. removes the readable-source marker definitions.

Generated source contains no marker calls or runtime feature tests. Disabled
code therefore contributes no imports, globals, functions, statements, or AST
nodes to calculator compilation.

### Build profiles

Profiles are stored in the root-level `build_profiles.json`. The current shape
is represented by this shortened example:

```json
{
  "default_profile": "release",
  "profiles": {
    "release": {
      "piece_style": "graphical",
      "features": {}
    },
    "debug": {
      "piece_style": "glyphs",
      "features": {
        "debug_panel": {
          "metrics": {
            "last_key": true,
            "free_memory": true
          }
        }
      }
    }
  }
}
```

The loader uses the standard-library JSON parser with strict duplicate-key
detection. It rejects invalid root/profile types, unsafe profile names, unknown
properties, unknown features or metrics, non-Boolean feature values, and
unsupported choice values. `piece_style` is mandatory. Omitted Boolean
features and debug metrics resolve to `false`; values do not inherit from
another profile.

`debug_panel` is derived from its nested metrics. One or more enabled metrics
enable the panel; when every metric is false, the whole panel is disabled.
There is deliberately no `debug_panel.enabled` property.

The normal build uses `default_profile` unless `-Profile` is supplied. It
validates and resolves the selected profile and prints its name, piece style,
and enabled features before preprocessing. The complete schema and migration
plan are documented in `features/build_profiles.md`.

### Boolean feature markers

`build_feature()` is an identity-like readable-source marker. The readable
definition keeps documented source defaults executable on a desktop, while
configured builds replace the marker structurally.

For example:

```python
if build_feature("debug_panel.metrics.free_memory"):
    import gc

if build_feature("debug_panel"):
    def draw_debug_panel():
        draw_panel_frame()
```

With `free_memory` enabled, the first branch becomes:

```python
import gc
```

With every debug metric disabled, both branches and the `gc` import are absent.
The output does not contain `if False`, `build_feature()`, or an empty function.

Nested markers are supported and are useful when a parent feature owns shared
structure while a metric owns its complete incremental cost:

```python
if build_feature("debug_panel"):
    def draw_debug_panel():
        row = 0
        if build_feature("debug_panel.metrics.last_key"):
            draw_debug_key("--")
            row += 1
        if build_feature("debug_panel.metrics.free_memory"):
            draw_debug_metric(row,"FM "+str(gc.mem_free()))
            row += 1
```

After selection, only enabled rows and their increments remain. This packs
enabled metrics upward without retaining runtime configuration checks.

### Choice markers

`build_choice()` selects exactly one implementation of a non-Boolean build
variant. Use a normal `if`/`else` so one complete implementation remains:

```python
if build_choice("piece_style","graphical"):
    def draw_piece(x,y):
        draw_graphical_piece(x,y)
else:
    def draw_piece(x,y):
        draw_piece_glyph(x,y)
```

For a `glyphs` profile, preprocessing produces only:

```python
def draw_piece(x,y):
    draw_piece_glyph(x,y)
```

The unused graphical implementation is not parsed by the calculator. Choice
names and values must be declared in the fixed profile schema; the marker does
not create new configuration dynamically.

### Marker rules

Use feature markers only as complete `if` conditions:

```python
if build_feature("debug_panel"):
    ...
```

Use only literal, known names and values. The pass rejects:

- marker calls in assignments, expressions, Boolean combinations, or ternaries;
- computed names or values;
- keyword arguments or incorrect argument counts;
- unknown features, choices, or choice values;
- aliases or reads of the marker functions; and
- marker calls left anywhere in the transformed tree.

Do not use textual `#ifdef` conventions, runtime profile dictionaries, or
`const()` for feature selection. Add schema entries and focused tests whenever
a new feature or choice is introduced.

### Readable-source defaults

Running `chess_evo.py` directly uses the defaults implemented by its marker
functions: graphical pieces and all current debug metrics enabled. These
defaults exist only to keep the readable source executable and understandable.

Running the preprocessor without `--config` uses the same documented source
defaults and preserves the generic CLI. Calculator builds always pass
`build_profiles.json` explicitly. Do not upload the readable source merely
because its defaults execute correctly; marker calls intentionally remain in
that file.

## Pass 2: `InlineConstantsPass`

### Purpose

`InlineConstantsPass` replaces immutable module-level literals at their read
sites, folds literal indexed reads when possible, and removes their declarations
and the readable `const()` marker. It runs after feature selection so it sees
only declarations belonging to the selected profile.

`const()` is an identity function in readable source and a build marker:

```python
def const(value):
    return value

KEY_LEFT = const(24)
WHITE_RGB = const((255,255,255))
```

Only use it as a simple module-level assignment:

```python
NAME = const(literal)
```

The value must be supported by `ast.literal_eval`. The pass:

1. validates every declaration and use;
2. replaces reads with copies of the literal AST;
3. folds literal indexes where possible;
4. removes the marked assignments; and
5. removes the identity `const()` function.

It rejects nonliteral values, reassignment, unsupported `const()` calls,
marker aliases, class-scope conflicts, and writes through `global`
declarations. It preserves legitimate function-local and comprehension
shadowing.

### Constant example

```python
RGB = const((255,128,0))
red = RGB[0]
```

becomes:

```python
red = 255
```

The declaration is removed, the read is substituted, and the literal index is
folded. A dynamic index cannot be folded:

```python
TABLE = const((10,20,30))
value = TABLE[index]
```

becomes:

```python
value = (10,20,30)[index]
```

### Inlining policy

The readable identity function does not enforce immutability. `const()` is a
contract maintained by developers: the binding and its contents must never
change, and code must not depend on the value's shared object identity.
Runtime state, mutable buffers, boards, capture state, configurable settings,
and feature selections must not use it.

Use these rules when deciding whether to add `const()`:

- Small scalar constants are normally good candidates.
- A composite read with a literal index can be folded completely.
- A dynamic index copies the complete composite literal to the read site.
- A large composite with one dynamic read site can still be appropriate. The
  current `AI_CENTER_TABLE` intentionally follows this policy.
- A composite with several dynamic read sites may be duplicated several times,
  increasing bytes, AST nodes, and runtime literal construction.
- Count syntactic reads, not functions. Two reads in one function produce two
  substitutions.
- Judge the complete preprocessed and minified output. An improvement in one
  pass can be lost or amplified by the next pass.

Inspect the generated form and measurements before marking a large composite.

## Metrics and minifier interaction

Every preprocessing run reports:

- constants processed;
- reads substituted;
- indexed reads folded; and
- AST nodes before and after the complete pass pipeline.

The build also reports final bytes, AST nodes, and statements. AST structure is
the primary target; a smaller text file can still require more Evo-T parser and
compiler memory.

The checked-in minifier configuration preserves all function argument names.
Without `preserve_locals`, local renaming keeps keyword-call compatibility by
adding short alias assignments inside functions. Those aliases save bytes but
add assignments, names, and load/store AST nodes. Non-argument locals and
globals remain eligible for renaming. Literal hoisting remains disabled because
it added globals, statements, and AST nodes in project measurements.

Keep minifier settings centralized in `tools/build_minified.ps1`. Do not run an
ad hoc configuration or manually post-process generated output.

## Commands

Run the preprocessor with arbitrary input and output paths and readable-source
defaults:

```powershell
.\.venv\Scripts\python.exe .\tools\ast_preprocessor.py input.py output.py
```

Use the configured default profile:

```powershell
.\.venv\Scripts\python.exe .\tools\ast_preprocessor.py input.py output.py --config .\build_profiles.json
```

Select an explicit configured profile:

```powershell
.\.venv\Scripts\python.exe .\tools\ast_preprocessor.py input.py output.py --config .\build_profiles.json --profile debug
```

Run the regression tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py" -v
```

Run the normal default-profile build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_minified.ps1
```

Measure one configured profile without replacing `chess_evo_min.py`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\measure_profile.ps1 -Profile release
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\measure_profile.ps1 -Profile debug
```

## Validation workflow

After changing markers, profiles, pass behavior, or minifier interaction:

1. add or update focused regression tests;
2. run the preprocessor tests;
3. run the normal build;
4. run the relevant profile metrics task when comparison data is wanted;
5. inspect generated source for disabled-feature and marker residue;
6. review substitutions, folds, nodes, statements, and bytes; and
7. test affected generated profiles on a physical TI-84 Evo-T.

Desktop compilation cannot validate Evo-T parser memory, graphics behavior,
or runtime performance. Hardware testing remains required.
