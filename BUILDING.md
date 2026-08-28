# Building the calculator test file

The readable source is `chess_evo.py`. The generated calculator test build is
`chess_evo_min.py`.

## One-time setup

1. Install `uv` using VS Code's Python environment tools if it is not already
   installed.
2. Run **Terminal > Run Task > Chess: setup minifier**.

The setup task asks `uv` to download the Python version in `.python-version`,
creates `.venv` in the repository, and synchronizes the pinned
`python-minifier` version from `requirements-dev.txt`. pip is not required and
no Python packages are installed globally.

The same setup can be run outside VS Code:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\setup_minifier.ps1
```

## Build

Press `Ctrl+Shift+B`, or run **Terminal > Run Build Task** and select
**Chess: build minified**. From a terminal, the equivalent command is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_minified.ps1
```

The build first runs `tools/ast_preprocessor.py`. Its initial optimization pass
inlines module-level `NAME = const(literal)` declarations and folds constant
tuple/dictionary indexes. The temporary preprocessed source is then passed to
`python-minifier`. Both temporary files are removed after the build.
See `PREPROCESSOR.md` for the constant policy, pass architecture and validation
requirements.

The build overwrites `chess_evo_min.py`, compile-checks the readable,
preprocessed, and minified sources, and prints their byte counts. Edit only
`chess_evo.py`; treat the minified file as generated output. Literal hoisting
is disabled because measurements showed it adds parser nodes and statements,
which is a poor trade on the Evo-T. The core minifier settings are
`hoist_literals=False`, `rename_locals=True`, and `rename_globals=True`.
Function argument names are automatically passed through `preserve_locals`.
Without that setting, local renaming introduces short aliases for arguments to
preserve keyword-call compatibility; those assignments save bytes but add
significant AST/compiler pressure. Non-argument locals are still renamed.

The preprocessor can also be used with any input and output paths:

```powershell
.\.venv\Scripts\python.exe .\tools\ast_preprocessor.py input.py output.py
```

Run the preprocessor regression tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py" -v
```
