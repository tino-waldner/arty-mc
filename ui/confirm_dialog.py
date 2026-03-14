from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmDialog(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #dialog {
        width: 100%;
        max-width: 200;
        min-width: 20;
        height: 9;
        max-height: 12;
        min-height: 8;
        border: round green;
        padding: 1;
        background: #1f1f1f;
        align-horizontal: center;
        align-vertical: middle;
    }

    .dialog-message {
        align: center middle;
        align-horizontal: center;
        align-vertical: middle;
        content-align: center middle;
    }

    #dialog-buttons {
        layout: horizontal;
        align-horizontal: center;
        align-vertical: middle;
        padding-top: 1;
    }

    #dialog-buttons Button {
        align-horizontal: center;
        align-vertical: middle;
        min-width: 6;
        content-align: center middle;
    }
    """

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self):
        with Vertical(id="dialog"):
            # yield Static(self.message)
            with Static():
                yield Label(self.message, classes="dialog-message")

                with Horizontal(id="dialog-buttons"):
                    yield Button("Yes", id="yes", variant="success")
                    yield Button("No", id="no", variant="error")

    def on_button_pressed(self, event: Button.Pressed):

        if event.button.id == "yes":
            self.dismiss(True)

        if event.button.id == "no":
            self.dismiss(False)
