import runpy
import sys
import warnings
from unittest.mock import MagicMock, patch

import pytest  # type: ignore

from arty_mc.arty_mc import ArtyMc, main, print_usage  # type: ignore


@pytest.mark.parametrize(
    "argv, expected_repo",
    [
        (["arty-mc", "myrepo"], "myrepo"),
    ],
)
def test_main_initializes_app(argv, expected_repo):
    with patch.object(sys, "argv", argv):
        with patch("arty_mc.arty_mc.ArtyMc") as MockApp:
            instance = MockApp.return_value
            instance.run = MagicMock()
            main()
            MockApp.assert_called_once_with(expected_repo)
            instance.run.assert_called_once()


def test_main_help_flag(capsys):
    with patch.object(sys, "argv", ["arty-mc", "--help"]):
        with pytest.raises(SystemExit) as e:
            main()

    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert e.value.code == 0


def test_main_no_arguments(capsys):
    with patch.object(sys, "argv", ["arty-mc"]):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "Usage:" in captured.out


def test_print_usage(capsys):
    print_usage()
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "arty-mc <repository>" in captured.out
    assert "--help" in captured.out


def test_on_mount_sets_config(monkeypatch):
    fake_repo = "test_repo"
    app = ArtyMc(fake_repo)
    fake_config = {}
    monkeypatch.setattr("arty_mc.arty_mc.load_config", lambda: fake_config)
    mock_screen = MagicMock()

    with patch("arty_mc.arty_mc.CommanderScreen", return_value=mock_screen):
        with patch.object(app, "push_screen") as push_mock:
            app.on_mount()

            assert fake_config["default_repo"] == fake_repo
            push_mock.assert_called_once_with(mock_screen)


def test_main_via_runpy(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arty-mc", "myrepo"])

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=RuntimeWarning,
            message=".*found in sys.modules after import of package.*",
        )
        runpy.run_module("arty_mc.arty_mc", run_name="__main__")
