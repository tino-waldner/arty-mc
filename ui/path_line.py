from textual.reactive import reactive
from textual.widget import Widget


class PathLine(Widget):
    DEFAULT_CSS = """
    PathLine {
        height: 1;
	align: center middle;
    }
    """

    path: reactive[str] = reactive("")

    def __init__(self, initial_path=""):
        super().__init__()
        self.path = initial_path

    def render(self):
        return f"[bold cyan]─ {self.path} ─[/bold cyan]"
