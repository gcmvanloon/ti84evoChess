# Building the calculator test file

The readable source is `chess_evo.py`. The generated calculator test build is
`chess_evo_min.py`.

## One-time host setup

1. Install Docker Desktop and make sure it is running. On Windows, use its
   normal WSL 2 backend.
2. Install Visual Studio Code and the **Dev Containers** extension.
3. Open this repository in Visual Studio Code.
4. Open the Command Palette (`F1`) and select **Dev Containers: Reopen in
   Container**.

The first container build downloads the Python 3.11 development image and
installs the pinned tools from `requirements-dev.txt`. No host Python, `uv`,
`pip`, PowerShell setup script or repository-local virtual environment is
required. Later starts reuse the built image.

When `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json` or
`requirements-dev.txt` changes, run **Dev Containers: Rebuild Container** so
the tool environment is rebuilt.

## Build

Inside the Dev Container, press `Ctrl+Shift+B` to run the default **release
build**, or use **Terminal > Run Build Task** and select either **release
build** or **debug build**. The equivalent terminal commands are:

```bash
bash tools/build_minified.sh --profile release
bash tools/build_minified.sh --profile debug
```

The build first runs `tools/ast_preprocessor.py`. It removes disabled profile
branches before inlining module-level `NAME = const(literal)` declarations,
folding constant tuple/dictionary indexes and inlining eligible single-use
functions. The temporary preprocessed source is then passed to
`python-minifier`. Temporary files are removed after success or failure. See
`PREPROCESSOR.md` for the constant policy, pass architecture and validation
requirements.

The build replaces `chess_evo_min.py` only after preprocessing, minification
and compile checks succeed. It reports preprocessing substitutions, folded
indexed reads, AST node counts, final statement count and byte sizes. Edit only
`chess_evo.py`; treat the minified file as generated output.

Literal hoisting is disabled because measurements showed it adds parser nodes
and statements, which is a poor trade on the Evo-T. The core minifier settings
are `hoist_literals=False`, `rename_locals=True`, and `rename_globals=True`.
Function argument names are automatically passed through `preserve_locals`.
Without that setting, local renaming introduces short aliases for arguments to
preserve keyword-call compatibility; those assignments save bytes but add
significant AST/compiler pressure. Non-argument locals are still renamed.

The legacy PowerShell metrics-history workflow and CSV files are intentionally
not part of the Dev Container build. They remain unchanged pending their
separate removal.

## Other development commands

Run the preprocessor with arbitrary input and output paths:

```bash
python tools/ast_preprocessor.py input.py output.py
```

Run the desktop regression tests:

```bash
python -m unittest discover -s tools -p "test_*.py" -v
```

Desktop checks cannot reproduce Evo-T memory limits, graphics behavior or
performance. Upload the generated `chess_evo_min.py` and perform final
validation on the physical calculator.
