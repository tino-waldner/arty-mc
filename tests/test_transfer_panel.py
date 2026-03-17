import pytest  # type: ignore
import pytest_asyncio  # type: ignore
from textual.app import App, ComposeResult  # type: ignore

from arty_mc.ui.transfer_panel import TransferPanel, human_bytes


class _TestTransferPanelApp(App):
    def __init__(self):
        super().__init__()
        self.panel = TransferPanel()

    def compose(self) -> ComposeResult:
        yield self.panel


@pytest_asyncio.fixture
async def panel():
    app = _TestTransferPanelApp()
    async with app.run_test():
        yield app.panel


def test_human_bytes():
    assert human_bytes(500) == "500.0 B"
    assert human_bytes(1024) == "1.0 KB"
    assert human_bytes(1536) == "1.5 KB"
    assert human_bytes(1048576) == "1.0 MB"
    assert human_bytes(1073741824) == "1.0 GB"


def get_plain_text(static_widget):
    line = static_widget.render_line(0)
    return "".join(seg.text for seg in line)


@pytest.mark.asyncio
async def test_start(panel):
    panel.start(2048)
    assert panel.visible
    assert panel.transferred == 0
    assert panel.total == 2048
    assert get_plain_text(panel.status).startswith("Transfer running... 0 / 2.0 KB")
    assert panel.progress.total == 2048
    assert panel.progress.progress == 0


@pytest.mark.asyncio
async def test_advance(panel):
    panel.start(2048)
    panel.advance(1024)
    assert panel.transferred == 1024
    assert "1.0 KB" in get_plain_text(panel.status)
    panel.advance(2048)
    assert panel.transferred == 2048
    assert "2.0 KB" in get_plain_text(panel.status)


@pytest.mark.asyncio
async def test_finish(panel):
    panel.start(2048)
    panel.advance(1024)
    panel.advance(1024)
    panel.finish()
    assert not panel.visible
    assert panel.transferred == 2048
    assert "Transfer finished" in get_plain_text(panel.status)
    assert panel.progress.progress == panel.total
