"""Desktop test support for loading the calculator chess engine."""

import ast
from pathlib import Path
from unittest import mock
import types


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHESS_SOURCE = PROJECT_ROOT / "chess_evo.py"


class CalculatorModuleStub(types.ModuleType):
    """Accept calculator API calls made while the source is initialized."""

    def __getattr__(self, name):
        return lambda *args, **kwargs: 0


def load_chess_engine():
    """Load the production engine without starting its interactive game loop."""
    source = CHESS_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source, CHESS_SOURCE)

    for index, statement in enumerate(tree.body):
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "draw_current_menu"
        ):
            tree.body = tree.body[:index]
            break
    else:
        raise AssertionError("could not find the start of the interactive game loop")

    module = types.ModuleType("chess_evo_under_test")
    module.__file__ = str(CHESS_SOURCE)
    calculator_modules = {
        "ti_draw": CalculatorModuleStub("ti_draw"),
        "ti_system": CalculatorModuleStub("ti_system"),
    }

    with mock.patch.dict("sys.modules", calculator_modules):
        exec(compile(tree, CHESS_SOURCE, "exec"), module.__dict__)

    module.reset_game_state()
    return module
