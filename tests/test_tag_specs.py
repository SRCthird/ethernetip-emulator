# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

import unittest
from src.server.tag_specs import build_tag_specs_argv, TAG_ARGV


class TestTagSpecs(unittest.TestCase):

    def test_build_tag_specs_argv(self):
        tag_specs = [("TEST_TAG", "BOOL", 1)]
        argv = build_tag_specs_argv(tag_specs, base_args=["--test"])
        self.assertEqual(argv, ["--test", "TEST_TAG=BOOL"])

    def test_default_tag_argv(self):
        self.assertIn("I_TEXT=BOOL", TAG_ARGV)
        self.assertIn("O_TEXT=BOOL", TAG_ARGV)
        self.assertIn("O_INCR=DINT", TAG_ARGV)

    def test_build_tag_specs_argv_base_args_none(self):
        tag_specs = [("A", "BOOL", 0)]
        argv = build_tag_specs_argv(tag_specs, base_args=None)
        self.assertEqual(argv, ["A=BOOL"])


if __name__ == "__main__":
    unittest.main()
