# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/templates/test_template_stringarray.py
import unittest

from ethernetip_emulator.server.datatypes.templates import StringArray


class TestStringArrayTemplate(unittest.TestCase):

    def test_type_validate(self):
        v = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(StringArray.type_validator(v), v)
