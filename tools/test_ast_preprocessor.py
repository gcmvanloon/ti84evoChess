import ast
import unittest

from ast_preprocessor import PreprocessorError, preprocess


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
