import ast
from pathlib import Path
import unittest

from ast_preprocessor import PreprocessorError, preprocess
from build_profiles import FEATURE_NAMES, ResolvedProfile


def profile(*enabled, piece_style="graphical"):
    features = {name: name in enabled for name in FEATURE_NAMES}
    features["debug_panel"] = any(
        features[name] for name in features if name.startswith("debug_panel.metrics.")
    )
    return ResolvedProfile("test", piece_style, features)


class SelectBuildFeaturesTests(unittest.TestCase):
    def test_splices_enabled_body_and_disabled_else(self):
        source = (
            "def build_feature(name): return True\n"
            "if build_feature('capture_panel'):\n    result = 'on'\n"
            "else:\n    result = 'off'\n"
        )
        output, _ = preprocess(source, profile=profile("capture_panel"))
        namespace = {}
        exec(output, namespace)
        self.assertEqual(namespace["result"], "on")
        self.assertNotIn("build_feature", output)

        output, _ = preprocess(source, profile=profile())
        namespace = {}
        exec(output, namespace)
        self.assertEqual(namespace["result"], "off")

    def test_selects_choice_and_removes_unused_branch(self):
        source = (
            "def build_choice(option, value): return value == 'graphical'\n"
            "if build_choice('piece_style', 'graphical'):\n    result = 'graphics'\n"
            "else:\n    result = 'glyphs'\n"
        )
        output, _ = preprocess(source, profile=profile(piece_style="glyphs"))
        self.assertIn("result = 'glyphs'", output)
        self.assertNotIn("graphics", output)
        self.assertNotIn("build_choice", output)

    def test_processes_features_before_constant_inlining(self):
        source = (
            "def build_feature(name): return True\n"
            "def const(value): return value\n"
            "if build_feature('capture_panel'):\n    VALUE = const(7)\n"
            "result = VALUE\n"
        )
        output, constants_pass = preprocess(
            source, profile=profile("capture_panel")
        )
        self.assertEqual(constants_pass.constant_count, 1)
        self.assertNotIn("VALUE", output)

    def test_rejects_unknown_feature_and_unsupported_placement(self):
        with self.assertRaisesRegex(PreprocessorError, "unknown build feature"):
            preprocess("if build_feature('missing'):\n    result = 1\n", profile=profile())
        with self.assertRaisesRegex(PreprocessorError, "complete if conditions"):
            preprocess("result = build_feature('capture_panel')\n", profile=profile())

    def test_nested_disabled_markers_leave_no_empty_statement(self):
        source = (
            "if True:\n"
            "    if build_feature('capture_panel'):\n"
            "        result = 1\n"
            "result = 2\n"
        )
        output, _ = preprocess(source, profile=profile())
        self.assertNotIn("if True", output)
        compile(output, "<test>", "exec")

    def test_chess_source_metrics_are_independently_removable(self):
        source_path = Path(__file__).resolve().parent.parent / "chess_evo.py"
        source = source_path.read_text(encoding="utf-8")
        cases = {
            "debug_panel.metrics.last_key": ("def draw_debug_key", "import gc", "import time", "ai_evaluated_moves", "draw_ai_debug_metrics"),
            "debug_panel.metrics.free_memory": ("gc.mem_free", "LK ", "import time", "ai_evaluated_moves", "draw_ai_debug_metrics"),
            "debug_panel.metrics.ai_time": ("time.monotonic", "import gc", "LK ", "ai_evaluated_moves"),
            "debug_panel.metrics.ai_evaluated_moves": ("ai_evaluated_moves", "import gc", "import time", "LK "),
        }
        for metric, (present, *absent) in cases.items():
            with self.subTest(metric=metric):
                output, _ = preprocess(source, str(source_path), profile(metric))
                self.assertIn(present, output)
                for text in absent:
                    self.assertNotIn(text, output)
                self.assertNotIn("build_feature", output)

        release, _ = preprocess(source, str(source_path), profile())
        self.assertNotIn("DEBUG", release)
        self.assertNotIn("KEY_TRACE", release)
        self.assertNotIn("build_feature", release)

    def test_chess_source_keeps_only_selected_piece_style(self):
        source_path = Path(__file__).resolve().parent.parent / "chess_evo.py"
        source = source_path.read_text(encoding="utf-8")

        graphical, _ = preprocess(
            source, str(source_path), profile(piece_style="graphical")
        )
        self.assertIn("def draw_pawn", graphical)
        self.assertIn("def draw_offset_fill_poly", graphical)
        self.assertNotIn("ti_draw.draw_text(px + 4, py, p)", graphical)

        glyphs, _ = preprocess(
            source, str(source_path), profile(piece_style="glyphs")
        )
        self.assertNotIn("def draw_pawn", glyphs)
        self.assertNotIn("def draw_offset_fill_poly", glyphs)
        self.assertNotIn("WHITE_RGB", glyphs)
        self.assertIn("ti_draw.draw_text(px + 4, py, p)", glyphs)

        tree = ast.parse(glyphs)
        renderer = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "draw_piece_shape"
        )
        draw_text_calls = [
            node
            for node in ast.walk(renderer)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "draw_text"
        ]
        self.assertEqual(len(draw_text_calls), 1)


class InlineConstantsTests(unittest.TestCase):
    def execute(self, source):
        output, _ = preprocess(source)
        namespace = {}
        exec(output, namespace)
        return output, namespace

    def test_inlines_scalars_and_removes_marker(self):
        output, namespace = self.execute(
            "def const(value): return value\nANSWER = const(42)\nresult = ANSWER + 1\n"
        )
        self.assertEqual(namespace["result"], 43)
        self.assertNotIn("ANSWER", namespace)
        self.assertNotIn("const", namespace)
        self.assertNotIn("ANSWER", output)

    def test_folds_tuple_and_dictionary_indexes(self):
        output, namespace = self.execute(
            "def const(value): return value\n"
            "RGB = const((255, 128, 0))\n"
            "VALUES = const({'pawn': 100})\n"
            "result = (RGB[0], RGB[2], VALUES['pawn'])\n"
        )
        self.assertEqual(namespace["result"], (255, 0, 100))
        tree = ast.parse(output)
        self.assertFalse(any(isinstance(node, ast.Subscript) for node in ast.walk(tree)))

    def test_preserves_function_local_shadowing(self):
        _, namespace = self.execute(
            "def const(value): return value\n"
            "VALUE = const(7)\n"
            "def global_value(): return VALUE\n"
            "def local_value(VALUE): return VALUE\n"
            "result = (global_value(), local_value(9))\n"
        )
        self.assertEqual(namespace["result"], (7, 9))

    def test_preserves_comprehension_target_shadowing(self):
        _, namespace = self.execute(
            "def const(value): return value\n"
            "VALUE = const(7)\n"
            "result = ([VALUE for VALUE in range(3)], VALUE)\n"
        )
        self.assertEqual(namespace["result"], ([0, 1, 2], 7))

    def test_rejects_non_literal_values(self):
        with self.assertRaisesRegex(PreprocessorError, "must be a literal"):
            preprocess(
                "def const(value): return value\n"
                "OTHER = 2\nVALUE = const(OTHER + 1)\n"
            )

    def test_rejects_reassignment(self):
        with self.assertRaisesRegex(PreprocessorError, "cannot modify const VALUE"):
            preprocess(
                "def const(value): return value\n"
                "VALUE = const(1)\nVALUE = 2\n"
            )

    def test_rejects_const_calls_outside_declarations(self):
        with self.assertRaisesRegex(PreprocessorError, "only supported"):
            preprocess("def const(value): return value\nresult = [const(1)]\n")

    def test_rejects_const_marker_aliases(self):
        with self.assertRaisesRegex(PreprocessorError, "cannot be read"):
            preprocess(
                "def const(value): return value\n"
                "VALUE = const(1)\nmarker = const\n"
            )


if __name__ == "__main__":
    unittest.main()
