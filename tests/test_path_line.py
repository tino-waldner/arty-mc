import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore

from arty_mc.ui.path_line import PathLine


class _TestPathLineApp(App):
    def __init__(self, initial_path=""):
        super().__init__()
        self.path_line = PathLine(initial_path=initial_path)

    def compose(self) -> ComposeResult:
        yield self.path_line


@pytest_asyncio.fixture
async def path_line_widget():
    app = _TestPathLineApp(initial_path="/home/user")
    async with app.run_test():
        yield app.path_line


@pytest.mark.asyncio
async def test_initial_path(path_line_widget):
    assert path_line_widget.path == "/home/user"
    rendered = path_line_widget.render()
    assert rendered == "[bold cyan]─ /home/user ─[/bold cyan]"


@pytest.mark.asyncio
async def test_update_path(path_line_widget):
    path_line_widget.path = "/tmp"
    assert path_line_widget.path == "/tmp"
    rendered = path_line_widget.render()
    assert rendered == "[bold cyan]─ /tmp ─[/bold cyan]"


@pytest.mark.asyncio
async def test_empty_path():
    app = _TestPathLineApp()
    async with app.run_test():
        widget = app.path_line
        assert widget.path == ""
        rendered = widget.render()
        assert rendered == "[bold cyan]─  ─[/bold cyan]"
