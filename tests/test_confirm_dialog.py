from unittest.mock import MagicMock

import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore
from textual.widgets import Button, Label  # type: ignore

from arty_mc.ui.confirm_dialog import ConfirmDialog


class _TestApp(App):
    def __init__(self, message="Are you sure?"):
        super().__init__()
        self.dialog = ConfirmDialog(message)

    def compose(self) -> ComposeResult:
        yield self.dialog


@pytest_asyncio.fixture
async def dialog():
    app = _TestApp("Delete file?")
    async with app.run_test():
        yield app.dialog


@pytest.mark.asyncio
async def test_dialog_message(dialog):
    labels = dialog.query(Label)
    assert len(labels) == 1
    label = labels.first()
    renderable = label.render()
    text = str(renderable)
    assert "Delete file?" in text


@pytest.mark.asyncio
async def test_yes_button_dismiss(dialog):
    called = {}
    dialog.dismiss = lambda value: called.setdefault("value", value)
    yes_button = dialog.query_one("#yes", Button)

    class DummyEvent:
        def __init__(self, button):
            self.button = button

    dialog.on_button_pressed(DummyEvent(yes_button))
    assert called.get("value") is True


@pytest.mark.asyncio
async def test_no_button_dismiss(dialog):
    called = {}
    dialog.dismiss = lambda value: called.setdefault("value", value)
    no_button = dialog.query_one("#no", Button)

    class DummyEvent:
        def __init__(self, button):
            self.button = button

    dialog.on_button_pressed(DummyEvent(no_button))
    assert called.get("value") is False


@pytest.mark.asyncio
async def test_unknown_button_does_nothing(dialog):
    called = {"value": None}
    dialog.dismiss = lambda value: called.update(value=value)
    fake_button = MagicMock()
    fake_button.id = "other"

    class DummyEvent:
        def __init__(self, button):
            self.button = button

    dialog.on_button_pressed(DummyEvent(fake_button))
    assert called["value"] is None
