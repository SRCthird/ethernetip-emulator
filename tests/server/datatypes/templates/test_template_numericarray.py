# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/templates/test_template_numericarray.py
import unittest

from ethernetip_emulator.server.datatypes.templates import NumericArray


class TestNumericArrayTemplate(unittest.TestCase):

    def test_type_validate(self):
        v = [1, 2, 3, 4]
        self.assertEqual(NumericArray.type_validator(v), v)
