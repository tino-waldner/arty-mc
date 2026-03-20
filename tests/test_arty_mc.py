import sys
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


def test_on_mount_config_error_shows_dialog(monkeypatch):
    """If load_config raises, on_mount shows a blocking ErrorDialog and exits on dismiss."""
    app = ArtyMc("repo")
    monkeypatch.setattr(
        "arty_mc.arty_mc.load_config",
        lambda: (_ for _ in ()).throw(
            RuntimeError("Config file missing: ~/.arty-mc.yml")
        ),
    )
    push_calls = []
    app.push_screen = lambda screen, callback=None: push_calls.append(
        (screen, callback)
    )

    with patch("arty_mc.arty_mc.CommanderScreen"):
        app.on_mount()

    assert len(push_calls) == 1
    from arty_mc.ui.error_dialog import ErrorDialog

    assert isinstance(push_calls[0][0], ErrorDialog)
    assert "Config file missing" in push_calls[0][0].message
    assert push_calls[0][0].title_text == "Configuration Error"
    exit_calls = []
    app.exit = lambda: exit_calls.append(True)
    push_calls[0][1](None)
    assert exit_calls == [True]


def test_on_mount_config_success_pushes_screen(monkeypatch):
    app = ArtyMc("repo")
    fake_config = {"server": "https://x.com", "user": "u", "token": "t"}
    monkeypatch.setattr("arty_mc.arty_mc.load_config", lambda: dict(fake_config))

    with patch("arty_mc.arty_mc.CommanderScreen"):
        with patch.object(app, "push_screen") as push_mock:
            app.on_mount()
            push_mock.assert_called_once()
