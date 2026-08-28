# TI-84 Evo-T Chess — Instructions

These instructions capture the constraints and decisions that future agents must preserve when working on this project.

> Target device is the **TI-84 Evo-T**, not the older TI-84 Plus CE / CE-T. Do not assume CE behavior or APIs apply unless verified on the Evo-T.

## 1. Source of truth and generated test build

`chess_evo.py` is the only source of truth:

- keep it readable, with clear names and useful comments;
- make all calculator-code changes there;
- never hand-edit minified code.

The build pipeline is deliberately ordered as:

```text
chess_evo.py -> AST preprocessing -> python-minifier -> chess_evo_min.py
```

`tools/ast_preprocessor.py` reads the source first and writes a temporary
optimized Python file. The temporary file is build output, not another source
of truth. Add future AST optimizations as separate passes in the
preprocessor's pass pipeline and preserve its generic input/output CLI.

### Preprocessor rules

`const()` marks immutable module-level literals for build-time inlining. Never
use it for runtime state, contents that change, configurable settings or
values whose shared object identity matters. Large composites may be
duplicated at each dynamic read site; inspect and measure the complete pipeline
before marking them. Only the generated build, with all markers removed, goes
onto the calculator.

Before adding or changing `const()` declarations, AST passes, preprocessing or
minifier configuration, **read and follow `PREPROCESSOR.md`**. It contains the
required syntax, inlining policy, architecture, metrics, tests and validation
workflow.

Do not upload `chess_evo.py` directly. The identity calls deliberately make
the readable file more expensive to compile.

`python-minifier` consumes the temporary preprocessed file and produces
`chess_evo_min.py`, the aggressively minified calculator test build:

- generate it after every calculator-code iteration;
- generate it only through the repository build task described below;
- treat it as disposable output, not source;
- do not commit it; it is intentionally listed in `.gitignore`;
- require behavior identical to the readable source.

The minified build has been run successfully on a physical TI-84 Evo-T using
the automated workflow in this repository.

## 2. Memory is the main constraint

The nominal `.py` limit is about 64 KB, but practical memory is much lower because source, parser/compiler structures, bytecode, symbols, globals, containers and runtime data share limited RAM.

Typical failures:

```text
MemoryError: memory allocation failed, allocating 128 bytes
MemoryError: memory allocation failed, allocating 467 bytes
```

The failed allocation is usually only the next allocation that could not fit.

**File size alone is not a reliable measure.** A smaller file can require more parser/compiler memory.

AST node count is an important desktop proxy for this compilation pressure.
While CPython's AST is not necessarily identical to the Evo-T Python parser's
internal representation, every statement, assignment, name, literal,
operator, subscript and container expression generally requires parser and
compiler bookkeeping. Much of that state exists simultaneously while the
module is being compiled, when RAM must also hold source text, symbols and the
emerging bytecode. A failure at this stage happens before gameplay and cannot
be fixed by reducing later AI allocations or calling `gc.collect()` afterward.

Minification can therefore make the byte file smaller while making compilation
harder. One measured example was local argument renaming: it saved characters
by introducing short aliases, but each alias added an assignment, names and
load/store nodes. Preserving function argument names produced a larger file
with substantially fewer nodes and statements, which is the preferred trade
for this project.

When memory is tight, prefer:

- fewer statements;
- fewer AST nodes;
- fewer identifiers;
- fewer list/tuple literals;
- fewer repeated expressions such as `px+7`;
- fewer helper layers unless they replace more syntax than they add.

A previous attempt to split a polygon into several smaller polygons reduced one runtime list allocation but increased parser complexity and made startup memory worse.

Optimize for **simple Python structure**, not only source bytes.

## 3. Minification rules

Minification is automated with `python-minifier`, pinned in
`requirements-dev.txt`. Python is managed by `uv`, with the requested version
stored in `.python-version` and the project environment stored in `.venv`.

One-time setup, or recovery after `.venv` is removed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\setup_minifier.ps1
```

In VS Code, the equivalent task is **Chess: setup minifier**. It downloads the
managed Python runtime when needed, creates `.venv`, and synchronizes the
pinned tools. System Python and pip are not required.

Generate the calculator build with the default VS Code build task
(`Ctrl+Shift+B`), named **Chess: build minified**, or run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_minified.ps1
```

The build task creates `chess_evo_min.py` through temporary preprocessed and
minified files and compile-checks the readable, preprocessed and minified
sources before replacing the output. It reports preprocessing substitutions,
folded indexed reads, AST node counts, final statement count and byte sizes.
After a successful build it also appends a row to the committed
`BUILD_METRICS.csv` when the build inputs or metrics differ from the latest
record. Keep this history file append-only; do not rewrite past measurements.

The required core minifier configuration is:

```python
hoist_literals = False
rename_locals = True
rename_globals = True
preserve_locals = all_function_argument_names
```

The CLI expresses this with `--no-hoist-literals` and `--rename-globals`.
Local renaming is enabled by default in the pinned `python-minifier` version;
the CLI only exposes the inverse `--no-rename-locals` switch. Keep these
settings centralized in `tools/build_minified.ps1`.

Preserving function argument names is intentional. Renaming them caused the
minifier to insert short local alias assignments so keyword calls remain
compatible. On this project those aliases added substantially more AST nodes
and statements. Non-argument locals remain eligible for renaming.

Literal hoisting was measured on this project and rejected: it saved some
source bytes but added globals, statements, and AST nodes, increasing the kind
of parser/compiler pressure that matters on the Evo-T.

Safe techniques:

- remove comments/docstrings;
- remove optional whitespace;
- pack safe statements;
- shorten project-owned identifiers;
- alias frequently used `ti_draw` calls when beneficial.

### Readable-source simplifications

Keep straightforward structural optimizations in `chess_evo.py` rather than
adding AST passes for them:

- use `+=` and `-=` for numeric counters, coordinates and scores instead of
  repeating the target in `value = value + ...` or `value = value - ...`;
- when a value is guaranteed to be one character, prefer membership such as
  `piece in "pP"` over repeated equality tests such as
  `piece == "p" or piece == "P"`; do not use this rewrite when an empty or
  multi-character string is possible because string-membership semantics then
  differ;
- use container truth tests such as `if not moves` instead of
  `if len(moves) == 0` when only emptiness matters.

These forms are both readable and structurally smaller, so future changes
should use them directly in the source of truth. As with every optimization,
retain a more explicit form if it is required to preserve semantics.

Do not use naive text replacement. Protect:

- keyword arguments such as `sort(key=...)`;
- imported API names;
- attributes;
- strings;
- Python syntax.

Use the AST-aware minifier rather than implementing manual identifier
replacement. Do not invoke `pyminify` ad hoc with different options and do not
post-process `chess_evo_min.py` by hand. If minifier settings or the pinned
version change, compare output size and syntax/AST complexity, then revalidate
the result on the physical calculator.

### Bitboards

Do not replace the current board representation with bitboards.

A calculator-side benchmark already compared equivalent move-generation work:

> **The existing array/list representation was about 85% faster than the tested bitboard approach on the TI-84 Evo-T.**

Only reconsider bitboards after a new Evo-T benchmark proves an improvement.

## 4. Evo-T graphics constraints

The project uses:

```python
import ti_draw
import ti_system
```

No usable Evo-T Python API has been found for raw framebuffer/memcpy-style pixel blitting.

Do not rely on CE-specific APIs such as `ti_image` unless verified on the Evo-T.

`use_buffer()` was unsupported in the tested Evo-T environment.

### Y-coordinate correction

Shape primitives require the project-specific correction:

```python
SHAPE_Y_FIX = -18
```

Wrappers such as `fill_rect_at()` and `draw_rect_at()` centralize this offset. Keep the correction centralized unless the whole coordinate model is deliberately redesigned and tested on hardware.

## 5. `fill_rect()` and `draw_rect()` behave differently

This caused several one-pixel rendering bugs.

Observed on the real Evo-T:

- `draw_rect()` behaves as if the far edge is included.
- `fill_rect()` effectively excludes the far right/bottom edge.

Therefore identical width/height values do not necessarily cover identical pixels.

Example: an exact 18×18 rectangle outline uses approximately:

```python
draw_rect_at(x, y, 17, 17)
```

Full fills may require an extra pixel in width/height to avoid a white seam on the right or bottom.

Do not “normalize” these calls without testing on the real calculator.

Close-up photos can also show RGB subpixel fringes. Judge alignment by logical pixel cells, not colored camera fringes.

## 6. Board geometry

```python
BOARD_X = 115
BOARD_Y = 26
SQUARE = 18
```

The board is 8×8 adjacent 18×18 tiles with **no intentional white spacing**.

Pieces must stay inside the inner **16×16** area:

```python
piece_x = BOARD_X + x*SQUARE + 1
piece_y = BOARD_Y + y*SQUARE + 1
```

Never let piece graphics overwrite the tile-border/highlight pixels.

## 7. Initial board rendering

Initial drawing is intentionally optimized:

1. fill the complete board once with one square color;
2. paint only the 32 squares of the opposite color;
3. draw all starting pieces afterward.

Do not repaint all 64 squares individually during initialization unless there is a measured reason.

During gameplay redraw only affected squares, e.g.:

- source;
- destination;
- en-passant capture square;
- rook squares during castling;
- changed CHECK king;
- promotion square.

Never redraw the whole board after each move.

## 8. Keep square drawing and highlighting separate

`draw_square(x,y)` handles only:

- square interior;
- piece on that square.

It must not decide cursor/selection/last-move state.

All tile highlights must use:

```python
draw_tile_highlight(x, y, color)
clear_tile_highlight(x, y)
```

Coordinates:

- `(0,0)` = upper-left;
- `(7,7)` = lower-right.

`clear_tile_highlight(x,y)` restores the border using `square_color(x,y)`, not white.

Yellow cursor, cyan selection and green last-move highlights must use the same geometry and code path.

The current highlight uses a **thin** pen. Medium was more visible but could overlap neighboring highlights and required neighbor restoration.

## 9. Piece-rendering rules

There are six specialized renderers:

```python
draw_pawn(...)
draw_rook(...)
draw_knight(...)
draw_bishop(...)
draw_queen(...)
draw_king(...)
```

Rules:

- stay within the 16×16 piece area;
- use very few native graphics primitives;
- prefer a recognizable simple silhouette over pixel-perfect detail;
- avoid hundreds of hard-coded `draw_line()` statements;
- avoid the old horizontal-run sprite renderer unless a benchmark proves it better.

Preferred primitives:

```python
fill_poly
draw_poly
fill_circle
draw_circle
fill_rect
draw_rect
draw_line
```

### Fill and outline

`ti_draw` has one active color, not separate fill/stroke colors.

Preferred pattern:

```python
set fill color
fill_poly(...)

set opposite outline color
draw_poly(...)
```

This avoids drawing a large outline silhouette underneath and repainting most of it.

White pieces use white fill/black outline. Black pieces use black fill/white outline. A king in check uses red fill with the contrasting outline.

### Polygon complexity

Keep vertex counts low.

Repeated expressions like `px+7`, `py+12` increase parser complexity. The current code uses relative-coordinate data and a shared polygon helper to reduce repeated syntax.

Do not split one polygon into many smaller polygons merely to reduce temporary list size; that can increase startup/compiler memory.

## 10. Cursor and redraw behavior

Cursor movement should not redraw pieces.

Typical flow:

1. clear the old tile highlight;
2. restore any logical highlight that belongs there;
3. draw the new cursor highlight.

If cursor movement starts repainting pieces, the rendering/highlight separation has been broken.

## 11. Input

Key codes:

```text
LEFT   24
UP     25
RIGHT  26
DOWN   34
CLEAR  45
ENTER  105
```

Use `ti_system.get_key(0)` with key-release handling so one physical press gives one movement.

Avoid `input()` because it does not fit the graphical UI.

## 12. Validation

The repository build task automatically compile-checks `chess_evo.py` and
`chess_evo_min.py` without importing the calculator-only `ti_*` modules. A
successful build is the minimum desktop validation for every calculator-code
change.

Desktop tests are useful for:

- syntax errors;
- missing names;
- broken minification;
- basic startup flow.

They do **not** reproduce Evo-T:

- memory limits;
- parser/compiler pressure;
- drawing extents;
- graphics performance;
- LCD appearance.

Final validation must happen on the real calculator. The current pinned
minifier workflow and settings have passed that hardware check, but future code
or tool changes still require calculator testing.

If a build fails with `MemoryError` before gameplay starts, first suspect parser/compiler footprint rather than the AI or drawing-time allocations.

## 13. Things not to casually reintroduce

Avoid unless measured on the Evo-T:

- bitboards;
- full-board redraws during gameplay;
- dozens/hundreds of hard-coded line calls per piece;
- tuple-driven horizontal sprite runs;
- piece pixels in the highlight border;
- separate highlight implementations for different colors;
- medium/thick highlights without neighbor restoration;
- many small polygons replacing one compact polygon;
- CE/CE-T-specific APIs;
- raw framebuffer assumptions;
- unrelated AI changes.

## 14. Preferred workflow

For every calculator-code change:

1. start from the latest readable source;
2. change only the requested subsystem;
3. preserve AI unless explicitly asked;
4. keep piece graphics inside 16×16;
5. preserve incremental redraws and highlight separation;
6. favor fewer Python constructs and fewer graphics calls;
7. run **Chess: setup minifier** only if `.venv` or its pinned tools are missing;
8. run **Chess: build minified** to regenerate and compile-check
   `chess_evo_min.py`;
9. review the reported minified size and, when memory is tight, compare
   statement count, identifier count, and AST complexity;
10. upload the generated `chess_evo_min.py` to the calculator and test it on the
    actual Evo-T; *(This is a manual step performed by a human.)*
11. commit the readable source and workflow changes, but not the ignored
    generated minified file.

See `BUILDING.md` for the concise operator instructions. Agents should execute
the same checked-in scripts a human uses; do not reproduce minification in a
prompt or maintain a separate hand-minified version.

Core principle:

> **On the TI-84 Evo-T, fewer Python constructs and fewer native drawing calls matter more than blindly minimizing source-file bytes.**
