# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/templates/test_template_realarray.py
import unittest

from ethernetip_emulator.server.datatypes.templates import RealArray


class TestRealArrayTemplate(unittest.TestCase):

    def test_type_validate(self):
        v = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(RealArray.type_validator(v), v)

    def test_is_zero(self):
        self.assertTrue(RealArray._is_zero(1e-10))

    def test_is_not_zero(self):
        self.assertFalse(RealArray._is_zero(1e-8))
