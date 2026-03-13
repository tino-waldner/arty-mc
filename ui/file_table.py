import fnmatch
from textual.widgets import DataTable

class FileTable(DataTable):

    can_focus = True

    def on_mount(self):
        self.add_columns(
            "Name",
            "Size",
            "Modified"
        )

        self.item = []
        self.filtered_items = []
        self.cursor_type = "row"

    def load(self, items):
        self.items = items
        self.filtered_items = items
        self.refresh_table()

    def apply_filter(self, pattern: str):
        if not pattern or pattern.strip() == "":
            self.filtered_items = self.items
        else:
            self.filtered_items = [
                f for f in self.items
                if fnmatch.fnmatch(f["name"], pattern)
             ]
        self.refresh_table()

    def refresh_table(self):
        self.clear()

        for f in self.filtered_items:
            name = f["name"]
            if f.get("is_dir"):
                name = "/ " + name
            self.add_row(
                name,
                str(f.get("size", "")),
                str(f.get("modified", ""))
            )

    def selected(self):
        if self.cursor_row is None:
            return None
        if self.cursor_row >= len(self.filtered_items):
            return None
        return self.filtered_items[self.cursor_row]
