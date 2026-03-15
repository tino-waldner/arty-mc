import threading

from textual.containers import Vertical  # type: ignore
from textual.message import Message  # type: ignore
from textual.reactive import reactive  # type: ignore
from textual.widget import Widget  # type: ignore
from textual.widgets import ProgressBar, Static  # type: ignore


def human_bytes(n: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    n = float(n)

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

    class CancelRequested(Message):
        pass

    visible: bool
    visible = reactive(False)  # type: ignore[assignment]

    def compose(self):
        self.status = Static("Idle")
        self.progress = ProgressBar(total=100)

        with Vertical():
            yield self.status
            yield self.progress

    def _dispatch(self, fn, *args):

        if threading.current_thread() is threading.main_thread():
            fn(*args)
        else:
            self.app.call_from_thread(fn, *args)

    def start(self, total_bytes: int):
        self._dispatch(self._start_ui, total_bytes)

    def advance(self, bytes_step: int):
        self._dispatch(self._advance_ui, bytes_step)

    def finish(self):
        self._dispatch(self._finish_ui)

    def _start_ui(self, total_bytes: int):

        self.total = total_bytes
        self.transferred = 0

        self.progress.update(total=total_bytes, progress=0)

        self.status.update(f"Transfer running... 0 / {human_bytes(total_bytes)}")

        self.visible = True

    def _advance_ui(self, bytes_step: int):

        self.transferred += bytes_step

        if self.transferred > self.total:
            self.transferred = self.total

        self.progress.advance(bytes_step)
        self.status.update(
            f"{human_bytes(self.transferred)} / {human_bytes(self.total)}"
        )

    def _finish_ui(self):

        self.progress.update(progress=self.total)

        self.status.update(f"Transfer finished ({human_bytes(self.total)})")

        self.visible = False
