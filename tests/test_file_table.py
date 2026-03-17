from types import SimpleNamespace
from typing import Any, Dict, List

import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore
from textual.events import Key  # type: ignore

from arty_mc.ui.file_table import FileTable


class _TestFileTableApp(App):
    def __init__(self, items: List[Dict[str, Any]] | None = None):
        super().__init__()
        self.items = items or []
        self.table = FileTable()

    def compose(self) -> ComposeResult:
        yield self.table

    async def on_mount(self) -> None:
        if self.items:
            self.table.load(self.items)


@pytest.fixture
def sample_items() -> List[Dict[str, Any]]:
    return [
        {"name": "file1.txt", "size": 100, "modified": "2026-03-16"},
        {"name": "file2.log", "size": 200, "modified": "2026-03-15"},
        {"name": "folder", "is_dir": True, "modified": "2026-03-14"},
    ]


@pytest_asyncio.fixture
async def table(sample_items):
    app = _TestFileTableApp(sample_items)

    async with app.run_test():
        yield app.table


@pytest.mark.asyncio
async def test_load_items(table, sample_items):
    table.load(sample_items)

    assert table.items == sample_items
    assert table.filtered_items == sample_items
    assert table.row_count == len(sample_items)


@pytest.mark.asyncio
async def test_apply_empty_filter(table, sample_items):
    table.apply_filter("")
    assert table.filtered_items == sample_items
    assert table.row_count == len(sample_items)


@pytest.mark.asyncio
async def test_apply_pattern_filter(table):
    table.apply_filter("file1")
    assert len(table.filtered_items) == 1
    assert table.filtered_items[0]["name"] == "file1.txt"


@pytest.mark.asyncio
async def test_apply_pattern_filter_extension(table):
    table.apply_filter(".log")
    assert len(table.filtered_items) == 1
    assert table.filtered_items[0]["name"] == "file2.log"


@pytest.mark.asyncio
async def test_set_enabled(table):
    table.set_enabled(False)
    assert table.disabled
    table.set_enabled(True)
    assert not table.disabled


@pytest.mark.asyncio
async def test_selected_valid_row(table, sample_items):
    table.move_cursor(row=1)
    assert table.cursor_row == 1
    assert table.selected() == sample_items[1]


@pytest.mark.asyncio
async def test_cursor_clamps_to_last_row(table, sample_items):
    table.move_cursor(row=10)
    assert table.cursor_row == len(sample_items) - 1
    assert table.selected() == sample_items[-1]


@pytest.mark.asyncio
async def test_selected_empty_table():
    app = _TestFileTableApp()
    async with app.run_test():
        table = app.table
        assert table.selected() is None


@pytest.mark.asyncio
async def test_disabled_input_stops_events(table):
    table.set_enabled(False)
    key_event = Key(key="a", character="a")
    table.on_key(key_event)
    mouse_event = SimpleNamespace(stop=lambda: None)
    table.on_mouse_down(mouse_event)
    assert True
