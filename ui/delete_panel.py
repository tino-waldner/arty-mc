from textual.widget import Widget
from textual.widgets import ProgressBar, Static
from textual.containers import Vertical
from textual.reactive import reactive
from textual import events

class DeletePanel(Widget):

    DEFAULT_CSS="""
    DeletePanel {
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

    def start(self, total_files):
        self.status.update("Delete running...")
        self.progress.update(total=total_files, progress=0)
        self.visible = True

    def advance(self, step=1):
        self.progress.advance(step)

    def finish(self):
        self.status.update("Delete finished")
        self.progress.update(progress=self.progress.total)
        self.visible = False
