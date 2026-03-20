import fnmatch
from typing import Any, Dict, List, Optional

from rich.text import Text  # type: ignore
from textual.widgets import DataTable  # type: ignore


class FileTable(DataTable):
    can_focus = True

    DEFAULT_CSS = """
    FileTable {
        height: 1fr;
    }
    """

    def on_mount(self) -> None:
        self.add_columns("Name", "Size", "Modified")
        self.items: List[Dict[str, Any]] = []
        self.filtered_items: List[Dict[str, Any]] = []
        self.cursor_type = "row"
        self.disabled = False

    def set_enabled(self, enabled: bool) -> None:
        self.disabled = not enabled

    def on_key(self, event) -> None:
        if self.disabled:
            event.stop()

    def on_mouse_down(self, event) -> None:
        if self.disabled:
            event.stop()

    def load(self, items: List[Dict[str, Any]]) -> None:
        self.items = items
        self.filtered_items = items.copy()
        self.refresh_table()

    def apply_filter(self, pattern: str) -> None:
        if not pattern.strip():
            self.filtered_items = self.items.copy()
        else:
            pattern = f"*{pattern}*"
            self.filtered_items = [f for f in self.items if fnmatch.fnmatch(f["name"], pattern)]
        self.refresh_table()

    def refresh_table(self):
        self.clear()
        for f in self.filtered_items:
            name = f["name"]
            if f.get("is_dir"):
                name = "/ " + name
            if f.get("is_dead_symlink"):
                style = "red"
            elif f.get("is_unreadable"):
                style = "grey50"
            elif f.get("is_empty_dir"):
                style = "yellow"
            else:
                style = None

            name_cell = Text(name, style=style)
            size_cell = Text(str(f.get("size", "")), style=style)
            modified_cell = Text(str(f.get("modified", "")), style=style)
            self.add_row(name_cell, size_cell, modified_cell)

    def selected(self) -> Optional[Dict[str, Any]]:
        if self.cursor_row is None or self.cursor_row >= len(self.filtered_items):
            return None
        return self.filtered_items[self.cursor_row]
