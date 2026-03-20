import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore
from textual.widgets import Button, Label  # type: ignore

from arty_mc.ui.error_dialog import ErrorDialog


class _TestApp(App):
    def __init__(self, message="Something went wrong", title="Error"):
        super().__init__()
        self.dialog = ErrorDialog(message, title=title)

    def compose(self) -> ComposeResult:
        yield self.dialog


@pytest_asyncio.fixture
async def dialog():
    app = _TestApp("Cannot connect to server", title="Connection Error")
    async with app.run_test():
        yield app.dialog


@pytest.mark.asyncio
async def test_dialog_shows_message(dialog):
    labels = dialog.query(Label)
    texts = [str(label.render()) for label in labels]
    combined = " ".join(texts)
    assert "Cannot connect to server" in combined


@pytest.mark.asyncio
async def test_dialog_shows_title(dialog):
    labels = dialog.query(Label)
    texts = [str(label.render()) for label in labels]
    combined = " ".join(texts)
    assert "Connection Error" in combined


@pytest.mark.asyncio
async def test_ok_button_dismisses(dialog):
    called = {}
    dialog.dismiss = lambda: called.setdefault("dismissed", True)
    ok_button = dialog.query_one("#ok-btn", Button)

    class DummyEvent:
        def __init__(self, button):
            self.button = button

    dialog.on_button_pressed(DummyEvent(ok_button))
    assert called.get("dismissed") is True


def test_error_dialog_instantiation():
    dialog = ErrorDialog("Something failed")
    assert dialog.message == "Something failed"
    assert dialog.title_text == "Error"


def test_error_dialog_custom_title():
    dialog = ErrorDialog("Bad token", title="Auth Error")
    assert dialog.title_text == "Auth Error"
