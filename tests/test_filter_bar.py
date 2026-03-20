# tests/test_filter_bar.py

from unittest.mock import MagicMock

import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore
from textual.events import Key  # type: ignore

from arty_mc.ui.filter_bar import FilterBar


class _TestApp(App):
    def __init__(self):
        super().__init__()
        self.filter_bar = FilterBar()
        self.captured = []

    def compose(self) -> ComposeResult:
        yield self.filter_bar

    async def handle_filter_bar_changed(self, message: FilterBar.Changed):
        self.captured.append(message)


@pytest_asyncio.fixture
async def app():
    app = _TestApp()
    async with app.run_test():
        yield app


@pytest_asyncio.fixture
async def filter_bar(app):
    return app.filter_bar


def test_input_changed_emits_message():
    filter_bar = FilterBar()

    captured = {}

    def fake_post_message(message):
        captured["message"] = message

    filter_bar.post_message = fake_post_message

    class DummyEvent:
        def __init__(self, value):
            self.value = value

    event = DummyEvent("test")
    filter_bar.on_input_changed(event)
    msg = captured.get("message")
    assert isinstance(msg, FilterBar.Changed)
    assert msg.value == "test"
    assert msg.sender == filter_bar


@pytest.mark.asyncio
async def test_input_submitted_sets_focus(app, filter_bar):
    called = {}

    app.set_focus = lambda w: called.setdefault("focus", True)
    app.screen.get_active = MagicMock(return_value="dummy")

    class DummyEvent:
        pass

    filter_bar.on_input_submitted(DummyEvent())
    assert called.get("focus") is True


@pytest.mark.asyncio
async def test_tab_key_stops_event_and_sets_focus(app, filter_bar):
    called = {"stopped": False, "focus": False}
    app.set_focus = lambda w: called.update(focus=True)
    app.screen.get_active = MagicMock(return_value="dummy")
    key_event = Key(key="tab", character="\t")
    key_event.stop = lambda: called.update(stopped=True)
    filter_bar.on_key(key_event)
    assert called["stopped"] is True
    assert called["focus"] is True


@pytest.mark.asyncio
async def test_non_tab_key_does_nothing(app, filter_bar):
    called = {"stopped": False}

    key_event = Key(key="a", character="a")
    key_event.stop = lambda: called.update(stopped=True)

    filter_bar.on_key(key_event)

    assert called["stopped"] is False
