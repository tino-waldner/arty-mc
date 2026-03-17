import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore

from arty_mc.ui.delete_panel import DeletePanel


class _TestDeletePanelApp(App):
    def __init__(self):
        super().__init__()
        self.panel = DeletePanel()

    def compose(self) -> ComposeResult:
        yield self.panel


@pytest_asyncio.fixture
async def panel():
    app = _TestDeletePanelApp()
    async with app.run_test():
        yield app.panel


@pytest.mark.asyncio
async def test_start(panel):
    panel.start(total_files=5)
    assert panel.visible
    assert panel.progress.total == 5
    assert panel.progress.progress == 0
    status_text = "".join(seg.text for seg in panel.status.render_line(0))
    assert status_text == "Delete running..."


@pytest.mark.asyncio
async def test_advance(panel):
    panel.start(total_files=5)
    panel.advance(2)
    assert panel.progress.progress == 2
    panel.advance(3)
    assert panel.progress.progress == 5


@pytest.mark.asyncio
async def test_increment_total(panel):
    panel.start(total_files=2)
    assert panel.progress.total == 2
    panel.increment_total(3)
    assert panel.progress.total == 5


@pytest.mark.asyncio
async def test_finish(panel):
    panel.start(total_files=3)
    panel.advance(2)
    panel.finish()

    assert not panel.visible
    assert panel.progress.progress == panel.progress.total
    status_text = "".join(seg.text for seg in panel.status.render_line(0))
    assert status_text == "Delete finished"


@pytest.mark.asyncio
async def test_start_without_total(panel):
    panel.start()
    assert panel.visible
    assert panel.progress.total == 0
    assert panel.progress.progress == 0
    status_text = "".join(seg.text for seg in panel.status.render_line(0))
    assert status_text == "Delete running..."
