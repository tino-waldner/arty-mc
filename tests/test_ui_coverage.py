import pytest  # type: ignore

from arty_mc.ui.commander_screen import CommanderScreen  # type: ignore
from arty_mc.ui.confirm_dialog import ConfirmDialog  # type: ignore
from arty_mc.ui.delete_panel import DeletePanel  # type: ignore
from arty_mc.ui.transfer_panel import TransferPanel  # type: ignore


@pytest.fixture
def fake_config():
    return {
        "server": "https://fake.server",
        "user": "fake-user",
        "token": "fake-token",
        "default_repo": "repo",
    }


def test_commander_screen_instantiation(fake_config):
    screen = CommanderScreen(fake_config)
    assert screen is not None


def test_confirm_dialog_instantiation():
    dialog = ConfirmDialog("Confirm this?")
    assert dialog is not None


def test_delete_panel_instantiation():
    panel = DeletePanel()
    assert panel is not None


def test_transfer_panel_instantiation():
    panel = TransferPanel()
    assert panel is not None
