"""Record reproducible size and AST metrics for successful calculator builds."""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import os
from pathlib import Path
import platform
import tempfile

from ast_preprocessor import preprocess


FIELDNAMES = (
    "timestamp_utc",
    "build_input_sha256",
    "source_bytes",
    "source_ast_nodes",
    "source_statements",
    "preprocessed_bytes",
    "preprocessed_ast_nodes",
    "preprocessed_statements",
    "minified_bytes",
    "minified_ast_nodes",
    "minified_statements",
    "constants",
    "substituted_reads",
    "folded_indexed_reads",
    "python_version",
    "python_minifier_version",
)

COMPARISON_FIELDS = (
    ("Minified bytes", "minified_bytes"),
    ("Minified AST nodes", "minified_ast_nodes"),
    ("Minified statements", "minified_statements"),
)


def file_metrics(path: Path) -> dict[str, int]:
    contents = path.read_bytes()
    tree = ast.parse(contents.decode("utf-8"), filename=str(path))
    return {
        "bytes": len(contents),
        "ast_nodes": sum(1 for _ in ast.walk(tree)),
        "statements": sum(isinstance(node, ast.stmt) for node in ast.walk(tree)),
    }


def build_input_hash(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.resolve().as_posix()):
        resolved = path.resolve()
        try:
            label = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            label = resolved.as_posix()
        contents = resolved.read_bytes()
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def make_record(
    source: Path,
    preprocessed: Path,
    minified: Path,
    build_inputs: list[Path],
    root: Path,
) -> dict[str, str]:
    source_values = file_metrics(source)
    preprocessed_values = file_metrics(preprocessed)
    minified_values = file_metrics(minified)
    _, constants_pass = preprocess(source.read_text(encoding="utf-8"), str(source))

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "build_input_sha256": build_input_hash(build_inputs, root),
        "source_bytes": str(source_values["bytes"]),
        "source_ast_nodes": str(source_values["ast_nodes"]),
        "source_statements": str(source_values["statements"]),
        "preprocessed_bytes": str(preprocessed_values["bytes"]),
        "preprocessed_ast_nodes": str(preprocessed_values["ast_nodes"]),
        "preprocessed_statements": str(preprocessed_values["statements"]),
        "minified_bytes": str(minified_values["bytes"]),
        "minified_ast_nodes": str(minified_values["ast_nodes"]),
        "minified_statements": str(minified_values["statements"]),
        "constants": str(constants_pass.constant_count),
        "substituted_reads": str(constants_pass.replacement_count),
        "folded_indexed_reads": str(constants_pass.folded_subscript_count),
        "python_version": platform.python_version(),
        "python_minifier_version": version("python-minifier"),
    }


def read_history(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != FIELDNAMES:
            raise ValueError(f"unexpected build metrics header in {path}")
        return list(reader)


def write_history(path: Path, records: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES, lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def record_build(
    history_path: Path, record: dict[str, str]
) -> tuple[dict[str, str] | None, bool]:
    records = read_history(history_path)
    previous = records[-1] if records else None
    if previous and all(
        previous[field] == record[field] for field in FIELDNAMES if field != "timestamp_utc"
    ):
        return previous, False
    records.append(record)
    write_history(history_path, records)
    return previous, True


def format_change(label: str, field: str, previous: dict[str, str], current: dict[str, str]) -> str:
    old_value = int(previous[field])
    new_value = int(current[field])
    difference = new_value - old_value
    percent = difference / old_value * 100 if old_value else 0
    return (
        f"{label}: {old_value:,} -> {new_value:,} "
        f"({difference:+,}, {percent:+.1f}%)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--preprocessed", required=True, type=Path)
    parser.add_argument("--minified", required=True, type=Path)
    parser.add_argument("--inputs", required=True, nargs="+", type=Path)
    arguments = parser.parse_args()

    root = arguments.history.resolve().parent
    record = make_record(
        arguments.source,
        arguments.preprocessed,
        arguments.minified,
        arguments.inputs,
        root,
    )
    previous, appended = record_build(arguments.history, record)

    if previous:
        print("Build metric changes from the previous recorded build:")
        for label, field in COMPARISON_FIELDS:
            print("  " + format_change(label, field, previous, record))
    else:
        print("Recorded initial build metrics baseline.")

    if appended:
        print(f"Appended build metrics to {arguments.history.name}.")
    else:
        print("Build inputs and metrics are unchanged; history was not appended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
