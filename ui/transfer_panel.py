from textual.widget import Widget
from textual.widgets import ProgressBar, Static
from textual.containers import Vertical
from textual.reactive import reactive


def human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.1f} {units[i]}"


class TransferPanel(Widget):

    DEFAULT_CSS = """
    TransferPanel {
        dock: top;
        width: 100%;
        height: 6;
        border: round green;
        padding: 1;
        background: #1f1f1f;
    }
    """

    visible = reactive(False)

    def compose(self):
        self.status = Static("Idle")
        self.progress = ProgressBar(total=100)
        with Vertical():
            yield self.status
            yield self.progress

    def start(self, total_bytes: int):
        self.total = total_bytes
        self.transferred = 0

        self.progress.update(total=total_bytes, progress=0)

        self.status.update(
            f"Transfer running... 0 / {human_bytes(total_bytes)}"
        )

        self.visible = True

    def advance(self, bytes_step: int):

        self.transferred += bytes_step

        self.progress.advance(bytes_step)

        percent = (self.transferred / self.total) * 100 if self.total else 0

        self.status.update(
            f"{percent:5.1f}%  {human_bytes(self.transferred)} / {human_bytes(self.total)}"
        )

    def finish(self):

        self.progress.update(progress=self.total)

        self.status.update(
            f"Transfer finished ({human_bytes(self.total)})"
        )

        self.visible = False
