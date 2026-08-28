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

Press `Ctrl+Shift+B` to run the default **release build**, or use
**Terminal > Run Build Task** and select either **release build** or
**debug build**. Both tasks pass their profile explicitly. The equivalent
terminal commands are:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_minified.ps1 -Profile release
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_minified.ps1 -Profile debug
```

The build first runs `tools/ast_preprocessor.py`. It removes disabled profile
branches before inlining module-level `NAME = const(literal)` declarations and
folding constant tuple/dictionary indexes. The temporary preprocessed source
is then passed to `python-minifier`. Both temporary files are removed after the
build.
See `PREPROCESSOR.md` for the constant policy, pass architecture and validation
requirements.

The normal build overwrites `chess_evo_min.py`, compile-checks the readable,
preprocessed, and minified sources, and prints byte and AST metrics. It does not
write metrics history. Run **release metrics** or **debug metrics** to measure
only that profile and update its `BUILD_METRICS_<PROFILE>.csv` history. Both
tasks use temporary output and do not replace `chess_evo_min.py`.
`BUILD_METRICS.csv` remains unchanged as legacy pre-profile history.

Commit the per-profile metrics histories when intentionally measured; Git
history identifies the source change responsible for each entry. Edit only
`chess_evo.py`; treat the minified file as generated output.
Literal hoisting is disabled because measurements showed it adds parser nodes
and statements, which is a poor trade on the Evo-T. The core minifier settings
are `hoist_literals=False`, `rename_locals=True`, and `rename_globals=True`.
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
