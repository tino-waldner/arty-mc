import runpy
from unittest.mock import patch


def test_main_called_when_running_package():
    with patch("arty_mc.arty_mc.main") as mock_main:
        runpy.run_module("arty_mc", run_name="__main__")
        mock_main.assert_called_once()
