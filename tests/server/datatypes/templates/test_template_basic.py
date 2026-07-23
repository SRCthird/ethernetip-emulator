# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/templates/test_template_basic.py
import unittest

from src.ethernetip_emulator.server.datatypes.templates import Basic


class TestBasicTemplate(unittest.TestCase):

    def test_type_validate(self):
        v = "Some Value"
        self.assertEqual(Basic.type_validator(v), v)
