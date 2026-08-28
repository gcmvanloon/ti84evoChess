#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
source_file="$project_root/chess_evo.py"
output_file="$project_root/chess_evo_min.py"
preprocessor="$project_root/tools/ast_preprocessor.py"
profiles_config="$project_root/build_profiles.json"
preprocessed_output="$project_root/chess_evo_preprocessed.py.tmp"
temporary_output="$project_root/chess_evo_min.py.tmp"
profile=""

usage() {
    echo "Usage: $0 [--profile PROFILE]"
}

while (( $# )); do
    case "$1" in
        --profile)
            if (( $# < 2 )); then
                echo "Missing value for --profile." >&2
                usage >&2
                exit 2
            fi
            profile="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! command -v python >/dev/null 2>&1 || ! command -v pyminify >/dev/null 2>&1; then
    echo "The build tools are unavailable. Rebuild and reopen the project in its Dev Container." >&2
    exit 1
fi

cleanup() {
    rm -f -- "$preprocessed_output" "$temporary_output"
}
trap cleanup EXIT

preprocessor_arguments=(
    "$preprocessor"
    "$source_file"
    "$preprocessed_output"
    --config "$profiles_config"
)
if [[ -n "$profile" ]]; then
    preprocessor_arguments+=(--profile "$profile")
fi
python "${preprocessor_arguments[@]}"

# Preserve argument names so python-minifier does not add local alias
# assignments for keyword-call compatibility. Non-argument locals remain
# eligible for renaming.
preserved_locals="$(python -c \
    "import ast,sys; tree=ast.parse(open(sys.argv[1],encoding='utf-8').read()); print(','.join(sorted({node.arg for node in ast.walk(tree) if isinstance(node,ast.arg)})))" \
    "$preprocessed_output")"

# Effective python-minifier API settings:
#   hoist_literals=False, rename_locals=True, rename_globals=True,
#   preserve_locals=<all function argument names>
pyminify "$preprocessed_output" \
    --output "$temporary_output" \
    --rename-globals \
    --preserve-locals "$preserved_locals" \
    --remove-literal-statements \
    --prefer-single-line \
    --no-hoist-literals

# Parse and compile without importing the calculator-only ti_* modules.
compile_check="import sys; compile(open(sys.argv[1],encoding='utf-8').read(),sys.argv[1],'exec')"
python -c "$compile_check" "$source_file"
python -c "$compile_check" "$preprocessed_output"
python -c "$compile_check" "$temporary_output"

mv -f -- "$temporary_output" "$output_file"

python -c \
    "import ast,pathlib,sys; source=pathlib.Path(sys.argv[1]); preprocessed=pathlib.Path(sys.argv[2]); output=pathlib.Path(sys.argv[3]); source_bytes=source.stat().st_size; preprocessed_bytes=preprocessed.stat().st_size; output_bytes=output.stat().st_size; saved=round((1-output_bytes/source_bytes)*100,1); tree=ast.parse(output.read_text(encoding='utf-8')); print(f'Built {output.name}: {output_bytes} bytes from {preprocessed_bytes} preprocessed bytes ({saved:g}% smaller than {source_bytes} readable bytes).'); print(f'Minified structure: {sum(1 for _ in ast.walk(tree))} AST nodes, {sum(isinstance(node,ast.stmt) for node in ast.walk(tree))} statements.')" \
    "$source_file" "$preprocessed_output" "$output_file"
