"""Extensible AST preprocessor for calculator-targeted Python source."""

from __future__ import annotations

import argparse
import ast
import copy
import os
from pathlib import Path
import tempfile
from typing import Protocol

# Configuration boundary: build_profiles owns JSON/schema semantics and gives
# this module one validated ResolvedProfile. AST passes never read JSON.
from build_profiles import (
    CHOICES,
    FEATURE_NAMES,
    ProfileError,
    ResolvedProfile,
    load_resolved_profile,
)


class PreprocessorError(ValueError):
    """Raised when source uses an optimization marker unsafely."""


class AstPass(Protocol):
    """Interface implemented by each independently testable AST pass."""

    name: str

    def run(self, tree: ast.Module) -> ast.Module:
        """Transform and return *tree*."""


class PassPipeline:
    def __init__(self, passes: list[AstPass]) -> None:
        self.passes = passes

    def run(self, tree: ast.Module) -> ast.Module:
        for ast_pass in self.passes:
            tree = ast_pass.run(tree)
            ast.fix_missing_locations(tree)
        return tree


class SelectBuildFeaturesPass(ast.NodeTransformer):
    """Apply a ``ResolvedProfile`` to statically recognized source markers."""

    name = "select build features"
    marker_names = frozenset(("build_feature", "build_choice"))

    def __init__(self, profile: ResolvedProfile) -> None:
        self.profile = profile
        self.selected_branches = 0
        self.removed_branches = 0
        self._condition_calls: set[int] = set()

    @staticmethod
    def _error(node: ast.AST, message: str) -> PreprocessorError:
        return PreprocessorError(f"line {getattr(node, 'lineno', '?')}: {message}")

    def _selection(self, node: ast.expr) -> bool | None:
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in self.marker_names
        ):
            return None
        self._condition_calls.add(id(node))
        if node.keywords:
            raise self._error(node, "build markers do not accept keyword arguments")
        values = [item.value for item in node.args if isinstance(item, ast.Constant)]
        if len(values) != len(node.args) or not all(isinstance(value, str) for value in values):
            raise self._error(node, "build marker arguments must be string literals")
        if node.func.id == "build_feature":
            if len(values) != 1:
                raise self._error(node, "build_feature() requires one argument")
            feature = values[0]
            if feature not in FEATURE_NAMES:
                raise self._error(node, f"unknown build feature {feature!r}")
            return self.profile.features[feature]
        if len(values) != 2:
            raise self._error(node, "build_choice() requires two arguments")
        option, value = values
        if option not in CHOICES:
            raise self._error(node, f"unknown build choice {option!r}")
        if value not in CHOICES[option]:
            raise self._error(node, f"unknown value {value!r} for build choice {option!r}")
        return getattr(self.profile, option) == value

    def _visit_statements(self, statements: list[ast.stmt]) -> list[ast.stmt]:
        result: list[ast.stmt] = []
        for statement in statements:
            transformed = self.visit(statement)
            if isinstance(transformed, list):
                result.extend(transformed)
            elif transformed is not None:
                result.append(transformed)
        return result

    def visit_If(self, node: ast.If) -> ast.If | list[ast.stmt]:
        selected = self._selection(node.test)
        if selected is None:
            node = self.generic_visit(node)
            if not node.body and not node.orelse:
                return []
            return node
        self.selected_branches += 1
        self.removed_branches += 1
        return self._visit_statements(node.body if selected else node.orelse)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef | None:
        node = self.generic_visit(node)
        return node if node.body else None

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef | None:
        node = self.generic_visit(node)
        return node if node.body else None

    def run(self, tree: ast.Module) -> ast.Module:
        # Register supported marker conditions before rejecting marker calls in
        # expressions, assignments, or other unsupported placements.
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                self._selection(node.test)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in self.marker_names
                and id(node) not in self._condition_calls
            ):
                raise self._error(node, "build markers are only supported as complete if conditions")

        tree = self.visit(tree)
        tree.body = [
            statement
            for statement in tree.body
            if not (
                isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                and statement.name in self.marker_names
            )
        ]
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in self.marker_names:
                raise self._error(node, f"build marker {node.id} cannot be read as a value")
        return tree


class _FunctionBindings(ast.NodeVisitor):
    """Collect names whose reads resolve locally in one function scope."""

    def __init__(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        self.bound: set[str] = set()
        self.stored: set[str] = set()
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()
        arguments = node.args
        for argument in (
            list(arguments.posonlyargs)
            + list(arguments.args)
            + list(arguments.kwonlyargs)
        ):
            self.bound.add(argument.arg)
        if arguments.vararg:
            self.bound.add(arguments.vararg.arg)
        if arguments.kwarg:
            self.bound.add(arguments.kwarg.arg)

        if isinstance(node, ast.Lambda):
            self.visit(node.body)
        else:
            for statement in node.body:
                self.visit(statement)
        self.bound.difference_update(self.global_names)
        self.bound.difference_update(self.nonlocal_names)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound.add(node.id)
            self.stored.add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.bound.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.bound.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bound.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # A nested lambda has its own bindings.
        return

    # Comprehension targets belong to the comprehension's implicit scope.
    visit_ListComp = visit_Lambda
    visit_SetComp = visit_Lambda
    visit_DictComp = visit_Lambda
    visit_GeneratorExp = visit_Lambda


class _ClassBindings(ast.NodeVisitor):
    """Collect bindings made directly by a class body, excluding child scopes."""

    def __init__(self, node: ast.ClassDef) -> None:
        self.bound: set[str] = set()
        for statement in node.body:
            self.visit(statement)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.bound.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.bound.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bound.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    visit_ListComp = visit_Lambda
    visit_SetComp = visit_Lambda
    visit_DictComp = visit_Lambda
    visit_GeneratorExp = visit_Lambda


class _ModuleStores(ast.NodeVisitor):
    """Find stores resolving to the module without entering child scopes."""

    def __init__(self, node: ast.AST) -> None:
        self.names: list[ast.Name] = []
        self.visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.append(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef

    def _visit_comprehension(self, node: ast.expr, result_fields: tuple[str, ...]):
        for generator in node.generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for field in result_fields:
            self.visit(getattr(node, field))

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node, ("elt",))

    visit_SetComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node, ("key", "value"))


class _ConstantInliner(ast.NodeTransformer):
    def __init__(self, constants: dict[str, ast.expr]) -> None:
        self.constants = constants
        self.local_bindings: list[tuple[set[str], set[str]]] = []
        self.replacements = 0
        self.folded_subscripts = 0

    def _is_shadowed(self, name: str) -> bool:
        for bound, global_names in reversed(self.local_bindings):
            if name in global_names:
                return False
            if name in bound:
                return True
        return False

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if (
            isinstance(node.ctx, ast.Load)
            and node.id in self.constants
            and not self._is_shadowed(node.id)
        ):
            self.replacements += 1
            return ast.copy_location(copy.deepcopy(self.constants[node.id]), node)
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        node = self.generic_visit(node)
        try:
            container = ast.literal_eval(node.value)
            index = ast.literal_eval(node.slice)
            value = container[index]
            replacement = ast.parse(repr(value), mode="eval").body
        except (ValueError, TypeError, SyntaxError, KeyError, IndexError):
            return node
        self.folded_subscripts += 1
        return ast.copy_location(replacement, node)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> ast.FunctionDef | ast.AsyncFunctionDef:
        node.decorator_list = [self.visit(item) for item in node.decorator_list]
        node.args.defaults = [self.visit(item) for item in node.args.defaults]
        node.args.kw_defaults = [
            self.visit(item) if item is not None else None
            for item in node.args.kw_defaults
        ]
        for argument in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        ):
            if argument.annotation:
                argument.annotation = self.visit(argument.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            node.args.vararg.annotation = self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            node.args.kwarg.annotation = self.visit(node.args.kwarg.annotation)
        if node.returns:
            node.returns = self.visit(node.returns)

        bindings = _FunctionBindings(node)
        self.local_bindings.append((bindings.bound, bindings.global_names))
        node.body = [self.visit(statement) for statement in node.body]
        self.local_bindings.pop()
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return self._visit_function(node)

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        return self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:
        node.args.defaults = [self.visit(item) for item in node.args.defaults]
        node.args.kw_defaults = [
            self.visit(item) if item is not None else None
            for item in node.args.kw_defaults
        ]
        bindings = _FunctionBindings(node)
        self.local_bindings.append((bindings.bound, bindings.global_names))
        node.body = self.visit(node.body)
        self.local_bindings.pop()
        return node

    @staticmethod
    def _target_names(target: ast.expr) -> set[str]:
        return {
            node.id
            for node in ast.walk(target)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }

    def _visit_comprehension(self, node: ast.expr, result_fields: tuple[str, ...]):
        pushed = 0
        for generator in node.generators:
            generator.iter = self.visit(generator.iter)
            self.local_bindings.append((self._target_names(generator.target), set()))
            pushed += 1
            generator.target = self.visit(generator.target)
            generator.ifs = [self.visit(item) for item in generator.ifs]
        for field in result_fields:
            setattr(node, field, self.visit(getattr(node, field)))
        for _ in range(pushed):
            self.local_bindings.pop()
        return node

    def visit_ListComp(self, node: ast.ListComp) -> ast.ListComp:
        return self._visit_comprehension(node, ("elt",))

    def visit_SetComp(self, node: ast.SetComp) -> ast.SetComp:
        return self._visit_comprehension(node, ("elt",))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> ast.GeneratorExp:
        return self._visit_comprehension(node, ("elt",))

    def visit_DictComp(self, node: ast.DictComp) -> ast.DictComp:
        return self._visit_comprehension(node, ("key", "value"))


class InlineConstantsPass:
    """Inline module-level ``NAME = const(literal)`` declarations."""

    name = "inline constants"

    def __init__(self) -> None:
        self.constant_count = 0
        self.replacement_count = 0
        self.folded_subscript_count = 0

    @staticmethod
    def _const_argument(node: ast.Assign) -> ast.expr | None:
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "const"
            and len(node.value.args) == 1
            and not node.value.keywords
        ):
            return node.value.args[0]
        return None

    @staticmethod
    def _error(node: ast.AST, message: str) -> PreprocessorError:
        return PreprocessorError(f"line {getattr(node, 'lineno', '?')}: {message}")

    def run(self, tree: ast.Module) -> ast.Module:
        constants: dict[str, ast.expr] = {}
        declarations: set[int] = set()
        marker_calls: set[int] = set()
        marker_names: set[int] = set()

        for statement in tree.body:
            if not isinstance(statement, ast.Assign):
                continue
            argument = self._const_argument(statement)
            if argument is None:
                continue
            name = statement.targets[0].id
            if name in constants:
                raise self._error(statement, f"duplicate const declaration for {name}")
            try:
                ast.literal_eval(argument)
            except (ValueError, TypeError, SyntaxError) as error:
                raise self._error(
                    statement, f"const value for {name} must be a literal"
                ) from error
            constants[name] = argument
            declarations.add(id(statement))
            marker_calls.add(id(statement.value))
            marker_names.add(id(statement.value.func))

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "const"
                and id(node) not in marker_calls
            ):
                raise self._error(
                    node, "const() is only supported in simple module assignments"
                )
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "const"
                and id(node) not in marker_names
            ):
                raise self._error(node, "const marker cannot be read as a value")

        if not constants:
            return tree

        # A second module-scope store would make inlining change semantics.
        for statement in tree.body:
            if id(statement) in declarations:
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for node in _ModuleStores(statement).names:
                if node.id in constants:
                    raise self._error(node, f"cannot modify const {node.id}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bindings = _FunctionBindings(node)
                changed_globals = (
                    bindings.global_names.intersection(bindings.stored).intersection(constants)
                )
                if changed_globals:
                    name = sorted(changed_globals)[0]
                    raise self._error(node, f"cannot modify const {name}")
            elif isinstance(node, ast.ClassDef):
                conflict = _ClassBindings(node).bound.intersection(constants)
                if conflict:
                    name = sorted(conflict)[0]
                    raise self._error(
                        node, f"class-scope shadowing of const {name} is unsupported"
                    )

        tree.body = [
            statement
            for statement in tree.body
            if id(statement) not in declarations
            and not (isinstance(statement, ast.FunctionDef) and statement.name == "const")
        ]
        inliner = _ConstantInliner(constants)
        tree = inliner.visit(tree)
        self.constant_count = len(constants)
        self.replacement_count = inliner.replacements
        self.folded_subscript_count = inliner.folded_subscripts
        return tree


def source_default_profile() -> ResolvedProfile:
    features = {name: False for name in FEATURE_NAMES}
    for name in features:
        if name.startswith("debug_panel.metrics."):
            features[name] = True
    features["debug_panel"] = True
    return ResolvedProfile("source-defaults", "graphical", features)


def preprocess(
    source: str,
    filename: str = "<unknown>",
    profile: ResolvedProfile | None = None,
) -> tuple[str, InlineConstantsPass]:
    tree = ast.parse(source, filename=filename)
    # Profile resolution is complete before this boundary. The pass consumes
    # only resolved feature Booleans and choices, then constant inlining runs
    # on the selected tree.
    features_pass = SelectBuildFeaturesPass(profile or source_default_profile())
    constants_pass = InlineConstantsPass()
    tree = PassPipeline([features_pass, constants_pass]).run(tree)
    output = ast.unparse(tree) + "\n"
    compile(output, filename, "exec")
    return output, constants_pass


def write_atomic(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(contents)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run calculator-oriented AST optimization passes."
    )
    parser.add_argument("input", type=Path, help="readable Python input file")
    parser.add_argument("output", type=Path, help="preprocessed Python output file")
    parser.add_argument("--config", type=Path, help="JSON build-profile configuration")
    parser.add_argument("--profile", help="named profile override")
    arguments = parser.parse_args()

    source = arguments.input.read_text(encoding="utf-8")
    if arguments.profile and not arguments.config:
        parser.error("--profile requires --config")
    try:
        # build_profiles.py owns loading and schema validation. From here on,
        # preprocessing works only with the returned ResolvedProfile.
        profile = (
            load_resolved_profile(arguments.config, arguments.profile)
            if arguments.config
            else source_default_profile()
        )
    except ProfileError as error:
        parser.error(str(error))
    enabled = ", ".join(profile.enabled_features) or "none"
    print(
        f"Build profile: {profile.name}; piece style: {profile.piece_style}; "
        f"enabled features: {enabled}."
    )
    output, constants_pass = preprocess(source, str(arguments.input), profile)
    write_atomic(arguments.output, output)
    before_nodes = sum(1 for _ in ast.walk(ast.parse(source)))
    after_nodes = sum(1 for _ in ast.walk(ast.parse(output)))
    print(
        f"Preprocessed {arguments.input.name}: "
        f"{constants_pass.constant_count} constants, "
        f"{constants_pass.replacement_count} reads, "
        f"{constants_pass.folded_subscript_count} indexed reads folded, "
        f"{before_nodes} -> {after_nodes} AST nodes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
