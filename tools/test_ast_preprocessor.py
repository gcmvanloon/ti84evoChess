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
            "if build_feature('show_captures'):\n    result = 'on'\n"
            "else:\n    result = 'off'\n"
        )
        output, _ = preprocess(source, profile=profile("show_captures"))
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
            "if build_feature('show_captures'):\n    VALUE = const(7)\n"
            "result = VALUE\n"
        )
        output, constants_pass = preprocess(
            source, profile=profile("show_captures")
        )
        self.assertEqual(constants_pass.constant_count, 1)
        self.assertNotIn("VALUE", output)

    def test_rejects_unknown_feature_and_unsupported_placement(self):
        with self.assertRaisesRegex(PreprocessorError, "unknown build feature"):
            preprocess("if build_feature('missing'):\n    result = 1\n", profile=profile())
        with self.assertRaisesRegex(PreprocessorError, "complete if conditions"):
            preprocess("result = build_feature('show_captures')\n", profile=profile())

    def test_nested_disabled_markers_leave_no_empty_statement(self):
        source = (
            "if True:\n"
            "    if build_feature('show_captures'):\n"
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
            "debug_panel.metrics.ai_candidates": ("ai_random_tries", "import gc", "import time", "LK ", "ai_evaluated_moves"),
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

    def test_chess_source_removes_captures_without_material_score(self):
        source_path = Path(__file__).resolve().parent.parent / "chess_evo.py"
        source = source_path.read_text(encoding="utf-8")

        with_captures, _ = preprocess(
            source, str(source_path), profile("show_captures")
        )
        self.assertIn("white_captures", with_captures)
        self.assertIn("def draw_captures", with_captures)
        self.assertIn("def record_capture", with_captures)

        without_captures, _ = preprocess(source, str(source_path), profile())
        self.assertNotIn("white_captures", without_captures)
        self.assertNotIn("black_captures", without_captures)
        self.assertNotIn("CAPTURE_X", without_captures)
        self.assertNotIn("def draw_captures", without_captures)
        self.assertNotIn("def record_capture", without_captures)
        self.assertNotIn("capture_kind", without_captures)
        self.assertNotIn("state[14]", without_captures)
        self.assertIn("white_score", without_captures)
        self.assertIn("def draw_score", without_captures)
        self.assertIn("def update_material_state", without_captures)
        self.assertNotIn("build_feature", without_captures)

    def test_chess_source_keeps_only_selected_piece_style(self):
        source_path = Path(__file__).resolve().parent.parent / "chess_evo.py"
        source = source_path.read_text(encoding="utf-8")

        graphical, graphical_stats = preprocess(
            source, str(source_path), profile(piece_style="graphical")
        )
        self.assertNotIn("def draw_pawn", graphical)
        self.assertGreaterEqual(graphical_stats.inlined_function_count, 6)
        self.assertIn("def draw_offset_fill_poly", graphical)
        self.assertIn("ti_draw.fill_poly", graphical)
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


class InlineSingleUseFunctionsTests(unittest.TestCase):
    def execute(self, source):
        output, stats = preprocess(source)
        namespace = {}
        exec(output, namespace)
        return output, stats, namespace

    def test_inlines_generic_single_call_and_renames_colliding_locals(self):
        output, stats, namespace = self.execute(
            "results = []\n"
            "def arbitrary_helper(value):\n"
            "    temporary = value + 1\n"
            "    results.append(temporary)\n"
            "def caller(value):\n"
            "    temporary = 100\n"
            "    arbitrary_helper(value)\n"
            "    results.append(temporary)\n"
            "caller(4)\n"
        )
        self.assertEqual(namespace["results"], [5, 100])
        self.assertEqual(stats.inlined_function_count, 1)
        self.assertNotIn("def arbitrary_helper", output)

    def test_repeats_to_a_fixed_point_for_call_chains(self):
        output, stats, namespace = self.execute(
            "results = []\n"
            "def leaf(value): results.append(value)\n"
            "def middle(value): leaf(value)\n"
            "def outer(value): middle(value)\n"
            "outer(7)\n"
        )
        self.assertEqual(namespace["results"], [7])
        self.assertEqual(stats.inlined_function_count, 2)
        self.assertNotIn("def leaf", output)
        self.assertNotIn("def middle", output)

    def test_ignores_shadowed_uses_of_the_same_name(self):
        output, stats, namespace = self.execute(
            "results = []\n"
            "def helper(value): results.append(value)\n"
            "def unrelated(helper): return helper\n"
            "def caller(value): helper(value)\n"
            "caller(3)\n"
        )
        self.assertEqual(namespace["results"], [3])
        self.assertEqual(stats.inlined_function_count, 1)
        self.assertNotIn("def helper", output)

    def test_requires_one_exclusive_direct_standalone_call(self):
        cases = {
            "two calls": (
                "def helper(value): results.append(value)\n"
                "def caller(value):\n    helper(value)\n    helper(value)\n"
            ),
            "value reference": (
                "def helper(value): results.append(value)\n"
                "alias = helper\n"
                "def caller(value): helper(value)\n"
            ),
            "nested expression": (
                "def helper(value): results.append(value)\n"
                "def caller(value): True and helper(value)\n"
            ),
            "recursion": "def helper(value): helper(value)\n",
            "nested caller": (
                "def helper(value): results.append(value)\n"
                "def outer(value):\n"
                "    def caller(value): helper(value)\n"
                "    caller(value)\n"
            ),
        }
        for label, definitions in cases.items():
            with self.subTest(label=label):
                output, stats = preprocess("results = []\n" + definitions)
                self.assertEqual(stats.inlined_function_count, 0)
                self.assertIn("def helper", output)

    def test_requires_one_exclusive_module_binding(self):
        cases = {
            "duplicate definition": (
                "def helper(value): sink.append(1)\n"
                "def helper(value): sink.append(value)\n"
            ),
            "import alias": (
                "import math as helper\n"
                "def helper(value): sink.append(value)\n"
            ),
            "class binding": (
                "class helper: pass\n"
                "def helper(value): sink.append(value)\n"
            ),
        }
        for label, definitions in cases.items():
            with self.subTest(label=label):
                output, stats = preprocess(
                    "sink = []\n"
                    + definitions
                    + "def caller(value): helper(value)\n"
                )
                self.assertEqual(stats.inlined_function_count, 0)
                self.assertIn("def helper", output)

    def test_rejects_unsupported_function_shapes(self):
        cases = {
            "return": "def helper(value): return value\n",
            "default": "def helper(value=1): sink.append(value)\n",
            "decorator": "@decorate\ndef helper(value): sink.append(value)\n",
            "parameter write": "def helper(value): value = 2\n",
            "global": "def helper(value):\n    global changed\n    changed = value\n",
            "nested closure": (
                "def helper(value):\n"
                "    def nested(): return value\n"
                "    sink.append(nested())\n"
            ),
        }
        for label, definition in cases.items():
            with self.subTest(label=label):
                source = (
                    "sink = []\n"
                    "def decorate(function): return function\n"
                    + definition
                    + "def caller(value): helper(value)\n"
                )
                output, stats = preprocess(source)
                self.assertEqual(stats.inlined_function_count, 0)
                self.assertIn("def helper", output)

    def test_requires_matching_name_arguments_without_keywords(self):
        cases = {
            "different name": "helper(other)",
            "expression": "helper(value + 1)",
            "keyword": "helper(value=value)",
        }
        for label, call in cases.items():
            with self.subTest(label=label):
                output, stats = preprocess(
                    "sink = []\n"
                    "def helper(value): sink.append(value)\n"
                    "def caller(value, other): " + call + "\n"
                )
                self.assertEqual(stats.inlined_function_count, 0)
                self.assertIn("def helper", output)

    def test_rejects_caller_binding_that_would_capture_a_global_read(self):
        output, stats, namespace = self.execute(
            "sink = []\n"
            "shared = 5\n"
            "def helper(value): sink.append(shared + value)\n"
            "def caller(value):\n"
            "    shared = 100\n"
            "    helper(value)\n"
            "caller(1)\n"
        )
        self.assertEqual(namespace["sink"], [6])
        self.assertEqual(stats.inlined_function_count, 0)
        self.assertIn("def helper", output)

        output, stats = preprocess(
            "sink = []\n"
            "shared = 5\n"
            "def helper(value): sink.append(shared + value)\n"
            "def caller(value):\n"
            "    import math as shared\n"
            "    helper(value)\n"
        )
        self.assertEqual(stats.inlined_function_count, 0)
        self.assertIn("def helper", output)

    def test_fresh_locals_avoid_string_encoded_scope_declarations(self):
        output, stats, namespace = self.execute(
            "sink = []\n"
            "_inline_0 = 99\n"
            "def helper(value):\n"
            "    temporary = value + 1\n"
            "    sink.append(temporary)\n"
            "def caller(value):\n"
            "    global _inline_0\n"
            "    helper(value)\n"
            "caller(4)\n"
        )
        self.assertEqual(stats.inlined_function_count, 1)
        self.assertEqual(namespace["sink"], [5])
        self.assertEqual(namespace["_inline_0"], 99)
        self.assertNotIn("def helper", output)


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
