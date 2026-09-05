import json
import unittest

from build_profiles import (
    ProfileError,
    parse_profile_document,
    resolve_profile,
)


def document(profile=None, default="release"):
    if profile is None:
        profile = {"piece_style": "graphical"}
    return json.dumps({"default_profile": default, "profiles": {"release": profile}})


class BuildProfileTests(unittest.TestCase):
    def resolve(self, profile=None):
        return resolve_profile(parse_profile_document(document(profile)))

    def test_omitted_booleans_and_metrics_resolve_false(self):
        resolved = self.resolve()
        self.assertEqual(resolved.piece_style, "graphical")
        self.assertFalse(any(resolved.features.values()))

    def test_debug_panel_is_derived_from_metrics(self):
        resolved = self.resolve(
            {
                "piece_style": "glyphs",
                "features": {
                    "debug_panel": {"metrics": {"free_memory": True}}
                },
            }
        )
        self.assertTrue(resolved.features["debug_panel"])
        self.assertTrue(resolved.features["debug_panel.metrics.free_memory"])
        self.assertFalse(resolved.features["debug_panel.metrics.last_key"])
        self.assertFalse(resolved.features["debug_panel.metrics.ai_candidates"])

    def test_show_captures_is_an_independent_boolean(self):
        resolved = self.resolve(
            {
                "piece_style": "graphical",
                "features": {"show_captures": True},
            }
        )
        self.assertTrue(resolved.features["show_captures"])
        self.assertFalse(resolved.features["material_advantage"])

    def test_rejects_duplicate_keys(self):
        with self.assertRaisesRegex(
            ProfileError, "root.profiles.release.piece_style: duplicate object key"
        ):
            parse_profile_document(
                '{"default_profile":"release","profiles":{"release":'
                '{"piece_style":"graphical","piece_style":"glyphs"}}}'
            )

    def test_rejects_missing_or_invalid_piece_style(self):
        with self.assertRaisesRegex(ProfileError, "piece_style: is required"):
            self.resolve({})
        with self.assertRaisesRegex(ProfileError, "must be one of"):
            self.resolve({"piece_style": "sprites"})

    def test_rejects_invalid_root_and_profile_collection(self):
        cases = (
            ("[]", "root: must be a JSON object"),
            ('{"profiles":{"release":{}}}', "root.default_profile: is required"),
            ('{"default_profile":1,"profiles":{"release":{}}}', "root.default_profile: must be a string"),
            ('{"default_profile":"release"}', "root.profiles: is required"),
            ('{"default_profile":"release","profiles":[]}', "root.profiles: must be a JSON object"),
            ('{"default_profile":"release","profiles":{}}', "root.profiles: must not be empty"),
            ('{"default_profile":"missing","profiles":{"release":{}}}', "root.default_profile: names unknown profile"),
        )
        for contents, message in cases:
            with self.subTest(contents=contents), self.assertRaisesRegex(ProfileError, message):
                parse_profile_document(contents)

    def test_rejects_wrong_nested_types_and_unknown_metric(self):
        cases = (
            ({"piece_style": "graphical", "features": []}, "features: must be a JSON object"),
            ({"piece_style": "graphical", "features": {"debug_panel": True}}, "debug_panel: must be a JSON object"),
            ({"piece_style": "graphical", "features": {"debug_panel": {"metrics": []}}}, "metrics: must be a JSON object"),
            ({"piece_style": "graphical", "features": {"debug_panel": {"metrics": {"other": True}}}}, "metrics.other: unknown property"),
        )
        for profile, message in cases:
            with self.subTest(profile=profile), self.assertRaisesRegex(ProfileError, message):
                self.resolve(profile)

    def test_rejects_non_booleans_unknowns_and_debug_enabled(self):
        with self.assertRaisesRegex(ProfileError, "must be a JSON Boolean"):
            self.resolve(
                {"piece_style": "graphical", "features": {"show_captures": 1}}
            )
        with self.assertRaisesRegex(ProfileError, "unknown property"):
            self.resolve(
                {"piece_style": "graphical", "features": {"unknown": True}}
            )
        with self.assertRaisesRegex(ProfileError, "debug_panel.enabled: unknown"):
            self.resolve(
                {
                    "piece_style": "graphical",
                    "features": {"debug_panel": {"enabled": True}},
                }
            )

    def test_default_and_explicit_profile_selection(self):
        parsed = parse_profile_document(
            json.dumps(
                {
                    "default_profile": "release",
                    "profiles": {
                        "release": {"piece_style": "graphical"},
                        "debug": {"piece_style": "glyphs"},
                    },
                }
            )
        )
        self.assertEqual(resolve_profile(parsed).name, "release")
        self.assertEqual(resolve_profile(parsed, "debug").name, "debug")

    def test_profile_names_are_validated(self):
        with self.assertRaisesRegex(ProfileError, "profile name"):
            parse_profile_document(
                '{"default_profile":"Bad Name","profiles":{"Bad Name":{}}}'
            )
