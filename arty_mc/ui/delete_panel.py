from textual.containers import Vertical  # type: ignore
from textual.reactive import reactive  # type: ignore
from textual.widget import Widget  # type: ignore
from textual.widgets import ProgressBar, Static  # type: ignore


class DeletePanel(Widget):
    DEFAULT_CSS = """
    DeletePanel {
        dock: top;
        width: 100%;
        height: 6;
        border: round green;
        padding: 1;
        background: #1f1f1f;
    }
    """

    visible = reactive(False)  # type: ignore[assignment]

    def compose(self):
        self.status = Static("Idle")
        self.progress = ProgressBar(total=100)
        with Vertical():
            yield self.status
            yield self.progress

    def start(self, total_files=None):
        self.status.update("Delete running...")
        if total_files is None:
            total_files = 0
        self.progress.update(total=total_files, progress=0)
        self.visible = True

    def advance(self, step=1):
        self.progress.advance(step)

    def increment_total(self, step=1):
        self.progress.total += step
        self.refresh()

    def finish(self):
        self.status.update("Delete finished")
        self.progress.update(progress=self.progress.total)
        self.visible = False
