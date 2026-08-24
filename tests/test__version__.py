# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/__version__.py
from importlib.metadata import PackageNotFoundError, version
import unittest
import runpy
from unittest.mock import patch


class TestMainBlock(unittest.TestCase):
    @patch("builtins.print")
    def test_script_execution(self, mock_print):
        runpy.run_path("src/ethernetip_emulator/__version__.py", run_name="__main__")

        mock_print.assert_called_once_with(version("ethernetip_emulator"))

    @patch("builtins.print")
    @patch("importlib.metadata.version")
    def test_script_execution_package_not_found(self, mock_version, mock_print):
        mock_version.side_effect = PackageNotFoundError("ethernetip_emulator")

        runpy.run_path("src/ethernetip_emulator/__version__.py", run_name="__main__")

        mock_print.assert_called_once_with("0.0.0-unknown")
