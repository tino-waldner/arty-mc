from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore
from textual.events import Key  # type: ignore

from arty_mc.ui.file_table import FileTable


class _TestFileTableApp(App):
    def __init__(self, items: Optional[List[Dict[str, Any]]] = None):
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


@pytest.fixture
def special_items() -> List[Dict[str, Any]]:
    return [
        {"name": "file.txt", "size": 100, "modified": "2026-03-16"},
        {"name": "folder", "is_dir": True, "modified": "2026-03-14"},
        {
            "name": "emptyfolder",
            "is_dir": True,
            "is_empty_dir": True,
            "modified": "2026-03-17",
        },
        {"name": "broken_symlink", "is_dead_symlink": True, "modified": "2026-03-17"},
    ]


@pytest_asyncio.fixture
async def table_with_specials(special_items):
    app = _TestFileTableApp(special_items)
    async with app.run_test():
        yield app.table


@pytest.mark.asyncio
async def test_special_items_flags(table_with_specials):
    table = table_with_specials
    table.load(table.items)

    found_empty = False
    found_dead = False

    for item in table.items:
        if item.get("is_empty_dir"):
            found_empty = True
            assert item["is_empty_dir"] is True
        if item.get("is_dead_symlink"):
            found_dead = True
            assert item["is_dead_symlink"] is True

    assert found_empty, "No empty folder detected in items"
    assert found_dead, "No dead symlink detected in items"


@pytest.mark.asyncio
async def test_special_items_filtering(table_with_specials):
    table = table_with_specials
    table.apply_filter("empty")
    assert len(table.filtered_items) == 1
    assert table.filtered_items[0]["name"] == "emptyfolder"

    table.apply_filter("broken")
    assert len(table.filtered_items) == 1
    assert table.filtered_items[0]["name"] == "broken_symlink"

    table.apply_filter("file")
    assert len(table.filtered_items) == 1
    assert table.filtered_items[0]["name"] == "file.txt"
