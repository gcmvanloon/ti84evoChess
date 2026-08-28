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

The build overwrites `chess_evo_min.py`, compile-checks both source files, and
prints their byte counts. Edit only `chess_evo.py`; treat the minified file as
generated output. Literal hoisting is disabled because measurements showed it
adds parser nodes and statements, which is a poor trade on the Evo-T. The core
minifier settings are `hoist_literals=False`, `rename_locals=True`, and
`rename_globals=True`.
