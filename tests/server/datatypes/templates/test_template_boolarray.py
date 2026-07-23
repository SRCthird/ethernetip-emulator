# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/templates/test_template_boolarray.py
import unittest

from ethernetip_emulator.server.datatypes.templates import BoolArray


class TestBoolArrayTemplate(unittest.TestCase):

    def test_type_validate(self):
        v = [True, True, True, True]
        self.assertEqual(BoolArray.type_validator(v), v)
