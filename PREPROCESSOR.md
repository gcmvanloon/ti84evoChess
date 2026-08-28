# AST preprocessor

The desktop AST preprocessor reduces calculator compilation pressure while
keeping `chess_evo.py` readable. The build order is:

```text
chess_evo.py -> tools/ast_preprocessor.py -> python-minifier -> chess_evo_min.py
```

The preprocessed file is temporary build output. It is not source and must not
be edited or committed.

## Architecture

`tools/ast_preprocessor.py` parses source with Python's built-in `ast` module,
runs a `PassPipeline`, unparses and compile-checks the transformed tree, and
writes the requested output atomically. Each future optimization must be an
independently testable pass implementing the existing pass interface. Keep
parsing, pass execution and file output separate, and preserve the generic
input/output CLI.

The initial pass is `InlineConstantsPass`.

## Build-time constants with `const()`

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

The current pass accepts values supported by `ast.literal_eval`. It:

1. validates every declaration and use;
2. replaces reads with copies of the literal AST;
3. folds literal indexes where possible;
4. removes the marked assignments;
5. removes the identity `const()` function.

It rejects nonliteral values, reassignment, unsupported `const()` calls,
marker aliases, class-scope conflicts and writes through `global` declarations.
It preserves legitimate function-local and comprehension shadowing.

The readable identity function does not enforce immutability. `const()` is a
contract maintained by developers: the binding and its contents must never
change, and code must not depend on the value's shared object identity.
Runtime state, mutable buffers, boards, capture state and configurable settings
must not use it.

## Inlining policy

Use these rules when deciding whether to add `const()`:

- Small scalar constants are normally good candidates.
- A composite read with a literal index can be folded completely. For example,
  `WHITE_RGB[0]` becomes `255`.
- A dynamic index cannot be folded. `TABLE[y*8+x]` becomes the complete table
  literal followed by `[y*8+x]`.
- A large composite with one dynamic read site can still be appropriate. The
  current `AI_CENTER_TABLE` intentionally follows this policy: it is moved to
  its only use site and is not duplicated.
- A composite with several dynamic read sites may be copied at every site,
  increasing bytes, AST nodes and possible runtime literal construction.
  Usually retain it as an ordinary shared global unless measurements prove
  inlining is better.
- Count syntactic reads, not functions. Two reads in one function can produce
  two copies of a composite literal.
- Judge the complete preprocessed and minified output. An improvement in one
  pass can be lost or amplified by the next pass.

For example:

```python
RGB = const((255,128,0))
red = RGB[0]
```

becomes:

```python
red = 255
```

But:

```python
TABLE = const((10,20,30))
value = TABLE[index]
```

becomes:

```python
value = (10,20,30)[index]
```

Inspect this generated form for every large composite.

## Metrics and minifier interaction

Every preprocessing run reports:

- constants processed;
- reads substituted;
- indexed reads folded;
- AST nodes before and after preprocessing.

The build also reports final bytes, AST nodes and statements. AST structure is
the primary target; a smaller text file can still require more Evo-T parser and
compiler memory.

The checked-in minifier configuration preserves all function argument names.
Without `preserve_locals`, local renaming keeps keyword-call compatibility by
adding short alias assignments inside functions. Those aliases save bytes but
add assignments, names and load/store AST nodes. Non-argument locals and
globals remain eligible for renaming. Literal hoisting remains disabled because
it also added globals, statements and AST nodes in project measurements.

Keep minifier settings centralized in `tools/build_minified.ps1`. Do not run an
ad hoc configuration or manually post-process generated output.

## Commands

Run the preprocessor with arbitrary input and output paths:

```powershell
.\.venv\Scripts\python.exe .\tools\ast_preprocessor.py input.py output.py
```

Run its regression tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py" -v
```

Run the complete calculator build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_minified.ps1
```

After changing declarations, passes or minifier interaction:

1. add or update focused regression tests;
2. run the preprocessor tests;
3. run the complete build;
4. review substitutions, folds, nodes, statements and bytes;
5. inspect transformed large composites;
6. test the generated `chess_evo_min.py` on a physical TI-84 Evo-T.

Desktop compilation cannot validate Evo-T parser memory or runtime allocation
behavior. Hardware testing remains required.
